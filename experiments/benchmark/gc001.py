"""GC-001: frozen TG-002 geometry replay, with no physics calls or fitting.

Run from the repository root in EMNerf with PYTHONPATH=solvers:. and single
BLAS/OpenMP threads. Receipts are incremental and existing output is refused.
The B adapter changes preparation only; all production mathematics stay intact.
"""
import argparse
from collections import defaultdict
from contextlib import contextmanager
import hashlib
from pathlib import Path
import platform
import resource
import subprocess
import time
import traceback
from unittest.mock import patch

import numpy as np
import scipy
from scipy.interpolate import CubicSpline
import torch

from bem_inverse import geometry as G, spectral as F, batched as B, certified as C
from bem_inverse.continuation import geometry as CG
from bem_inverse.continuation.geometry import FourierCurve, grid_size, normal_basis, arclength_angles
from bem_inverse.continuation.geometry_runtime import geometry_runtime, geometry_batch
from bem_inverse.continuation.updates import UpdateRefused
from bem_inverse.device_certified import DeviceCertifiedUpdate
from bem_inverse.io import read, write, digest, curve_from, curve_record
from . import campaign, scenes

UNIT = .05
ARMS = ('S', 'F', 'B', 'C')
DIAGNOSTIC_IDS = ('start', 'circle__c4', 'kite__c4', 'hook__c4', 'aphex_twin__c4')
DEFAULT_OUTPUT = campaign.ROOT/'results/validation/cleaned_interfaces/GC-001'
SOURCE = campaign.ROOT/'results/validation/cleaned_interfaces/PC-002/NS/runs'


class BatchedSampled(B.BatchedCertifiedUpdate):
    """Exact existing spectral trial, existing batched preparation; no certificates."""
    trial = G.ProjectedUpdate.trial


def make_arm(name, *, device='cuda', step=1e-7):
    kwargs = dict(derivative_step_m=step)
    if name == 'S':
        return G.ProjectedUpdate(UNIT, **kwargs)
    if name == 'F':
        return F.SpectralProjectedUpdate(UNIT, **kwargs)
    if name == 'B':
        return BatchedSampled(UNIT, device=device, **kwargs)
    if name == 'C':
        return DeviceCertifiedUpdate(UNIT, device=device, **kwargs)
    raise ValueError(name)


def sync():
    if torch.cuda.is_available() and torch.cuda.is_initialized():
        torch.cuda.synchronize()


def timed(function):
    sync()
    started = time.perf_counter()
    result = function()
    sync()
    return result, time.perf_counter()-started


def state_inputs():
    campaign.verify(require_inputs=True)
    start_path = campaign.start_path()
    start = G.resize(curve_from(read(start_path)), 64)
    states = [dict(id='start', curve=curve_record(start), M=1, stage='start',
                   source=str(start_path.relative_to(campaign.ROOT)), sha256=digest(start_path))]
    expected = {scenes.case_id(c, s) for s in scenes.SCENES for c in scenes.CONTRASTS}
    paths = sorted(SOURCE.glob('*/accepted.json'))
    if {p.parent.name for p in paths} != expected:
        raise RuntimeError('PC-002 last-accepted state coverage differs from TG-002')
    for p in paths:
        state = read(p)['states'][-1]
        states.append(dict(id=p.parent.name, curve=state['curve'], M=state['M'], stage=state['stage'],
                           source=str(p.relative_to(campaign.ROOT)), sha256=digest(p)))
    for row in states:
        curve = curve_from(row['curve'])
        n = grid_size(max(curve.band, row['M']))
        nodes = curve.nodes(n)
        row.update(K=curve.band, N=n, sigma0=nodes.perimeter/(2*np.pi),
                   speed_ratio=float(nodes.speeds.max()/nodes.speeds.min()),
                   maximum_abs_curvature_per_m=float(np.max(np.abs(nodes.curvatures))/UNIT),
                   timing_panel=row['id']=='start' or row['id'].endswith('__c4'),
                   exact_key=hashlib.sha256(curve.coefficients.tobytes()+
                       np.array([curve.band, row['M']], dtype=np.int64).tobytes()).hexdigest())
    return states


def common_moves(curve, modes, count):
    basis = normal_basis(curve.nodes(count), modes)
    rng = np.random.default_rng(3)
    directions = rng.normal(size=(3, 2*modes+1))
    directions /= np.max(np.abs(basis@directions.T), axis=0)[:, None]
    return [dict(id=f'{size:g}m-d{j}', size_m=size, direction=j, coefficients=a*size)
            for size in (1e-7, .001, .006) for j, a in enumerate(directions)]


def field_error(delta, count, sigma0, tangent=None):
    z = G.values(delta, count)
    out = dict(maximum_m=float(np.max(np.abs(z))*UNIT),
               rms_m=float(np.sqrt(np.mean(np.abs(z)**2))*UNIT),
               relative=float(np.max(np.abs(z))/sigma0),
               coefficient_l2_m=float(np.linalg.norm(delta)*UNIT))
    if tangent is not None:
        components = z*np.conj(tangent)
        out.update(tangential_maximum_m=float(np.max(np.abs(components.real))*UNIT),
                   normal_maximum_m=float(np.max(np.abs(components.imag))*UNIT))
    return out


def column_error(a, b):
    error = np.linalg.norm(a-b, axis=0)/np.maximum(np.linalg.norm(b, axis=0), 1e-30)
    return dict(maximum=float(np.max(error)), median=float(np.median(error)), columns=error)


def trial_call(update, space, a):
    def call():
        try:
            with geometry_batch():
                candidate, receipt = update.trial(space, a)
            return dict(accepted=True, curve=curve_record(candidate), receipt=receipt)
        except (UpdateRefused, ValueError) as exc:
            return dict(accepted=False, reason=getattr(exc, 'reason', type(exc).__name__), detail=str(exc))
    result, seconds = timed(call)
    result.update(seconds=seconds, tiers=list(getattr(update, 'records', [])))
    return result


def moved_curve(curve, a, count):
    nodes = curve.nodes(count)
    normal = nodes.normals@np.array([1, 1j])
    h = normal_basis(nodes, len(a)//2)@a/UNIT
    return FourierCurve.from_samples(curve.values(count)+h*normal, count//2-1)


def coefficients_only(moved, nodes, band):
    """Diagnostic ablation: identical CPU quadrature minus discarded reconstruction."""
    angles, length = arclength_angles(nodes)
    weights = moved.values(nodes.num_nodes)*nodes.speeds/(length/(2*np.pi))
    powers = np.empty((band+1, nodes.num_nodes), complex)
    powers[0] = 1
    step = np.exp(-1j*angles)
    for k in range(1, band+1):
        powers[k] = powers[k-1]*step
    positive = powers@weights/nodes.num_nodes
    negative = powers[1:].conj()@weights/nodes.num_nodes
    return np.concatenate((negative[::-1], positive))


class CoefficientsOnly(F.SpectralProjectedUpdate):
    def _project(self, curve, a, band, count, length_unit_m, *, validate=False):
        if validate:
            raise ValueError('Preparation-only diagnostic')
        self.counts['geometry_projections'] += 1
        moved = moved_curve(curve, a, count)
        return coefficients_only(moved, moved.nodes(count), band), 0.


def sparse_evaluate(coefficients, modes, theta, *, tail_budget=2e-13):
    """Chunked Fourier sum, with a recorded l1 bound on negligible omitted modes."""
    coefficients, modes = np.asarray(coefficients), np.asarray(modes)
    order = np.argsort(np.abs(coefficients))
    drop = order[np.cumsum(np.abs(coefficients[order])) <= tail_budget]
    keep = np.ones(len(coefficients), bool)
    keep[drop] = False
    active, k = coefficients[keep], modes[keep]
    out = np.empty(len(theta), complex)
    for i in range(0, len(theta), 128):
        out[i:i+128] = np.exp(1j*np.asarray(theta[i:i+128])[:, None]*k)@active
    return out, float(np.sum(np.abs(coefficients[~keep])))


def inverse_panel(moved, count, band):
    """Factorial interpolation ablation, holding the native arclength primitive fixed."""
    nodes = moved.nodes(count)
    angles, _ = arclength_angles(nodes)
    target = nodes.parameters
    native = CubicSpline(np.r_[angles, 2*np.pi], np.r_[target, 2*np.pi])(target)
    speed = np.fft.fft(nodes.speeds)/count
    modes = np.fft.fftfreq(count)*count
    primitive = np.zeros(count, complex)
    primitive[1:] = speed[1:]/(1j*modes[1:])
    anchor = float(np.real(primitive.sum()))
    mu = speed[0].real
    inverse = []
    for factor in (4, 8):
        size = count*factor
        spectrum = np.zeros(size, complex)
        spectrum[modes.astype(int) % size] = primitive
        theta = 2*np.pi*np.arange(size)/size
        alpha = (mu*theta+(np.fft.ifft(spectrum)*size).real-anchor)/mu
        alpha[0] = 0.
        if np.any(np.diff(np.r_[alpha, 2*np.pi]) <= 0):
            raise ValueError('Refined inverse of native primitive is not monotone')
        inverse.append(CubicSpline(np.r_[alpha, 2*np.pi], np.r_[theta, 2*np.pi])(target))
    theta = inverse[-1]
    residual, bound = sparse_evaluate(primitive, modes, theta)
    residual = (mu*theta+residual.real-anchor)/mu-target
    position = CubicSpline(np.r_[target, 2*np.pi],
                           np.r_[moved.values(count), moved.values(count)[0]], bc_type='periodic')
    exact_native, position_bound = sparse_evaluate(moved.coefficients, moved.modes, native)
    exact_refined, position_bound_2 = sparse_evaluate(moved.coefficients, moved.modes, theta)
    samples = dict(native=position(native), inverse=position(theta),
                   position=exact_native, both=exact_refined)
    outputs = {k: FourierCurve.from_samples(v, band).coefficients for k, v in samples.items()}
    # Shift of the direct Fourier curve has its own dense diagnostic, distinct
    # from the four retained-band outputs used for error-vector attribution.
    return outputs, dict(inverse_residual_max=float(np.max(np.abs(residual))),
                          inverse_4N_8N_max=float(np.max(np.abs(inverse[0]-theta))),
                          primitive_omitted_l1=bound,
                          position_omitted_l1=max(position_bound, position_bound_2))


def validate_adapter():
    curve = G.resize(FourierCurve.circle(1.3, 10+10j), 8)
    updates = {arm: make_arm(arm) for arm in ('F', 'B', 'C')}
    spaces = {a: u.prepare(curve, 1, 8) for a, u in updates.items()}
    column = column_error(spaces['B'].derivatives, spaces['F'].derivatives)
    np.testing.assert_allclose(spaces['B'].base_projection, spaces['C'].base_projection, atol=1e-14)
    np.testing.assert_allclose(spaces['B'].derivatives, spaces['C'].derivatives, atol=1e-12)
    if column['maximum'] > 1e-6:
        raise AssertionError('B preparation differs from F above diagnostic gate')
    a = np.array([.001, .0002, -.0001])
    f, b = trial_call(updates['F'], spaces['F'], a), trial_call(updates['B'], spaces['B'], a)
    if f['accepted'] != b['accepted']:
        raise AssertionError('B sampled decision differs from F')
    np.testing.assert_allclose(curve_from(f['curve']).coefficients,
                               curve_from(b['curve']).coefficients, rtol=0, atol=1e-13)
    if any(updates[x].counts.get('prepare_fallbacks', 0) for x in updates):
        raise AssertionError('Adapter qualification fell back from CUDA')
    return dict(passed=True, column_relative=column, cuda=True)


def precision_state(row, output):
    curve, m, n = curve_from(row['curve']), row['M'], row['N']
    moves = common_moves(curve, m, n)
    updates, spaces, preparations = {}, {}, {}
    for arm in ARMS:
        updates[arm] = make_arm(arm)
        spaces[arm], seconds = timed(lambda: updates[arm].prepare(curve, m, curve.band))
        preparations[arm] = dict(seconds=seconds, settings=updates[arm].settings())
    write(output/'preparation.json', dict(state=row, arms=preparations,
        columns={a: column_error(spaces[a].derivatives, spaces['F'].derivatives) for a in ('S', 'B', 'C')},
        base_S_F=field_error(spaces['S'].base_projection-spaces['F'].base_projection, 2*n, row['sigma0'])))
    zeros = np.zeros(2*m+1)
    projectors = {'S': G.project, 'F': F.spectral_project}
    bases = {a: {factor: projectors[a](curve, zeros, curve.band, factor*n, UNIT)[0]
                  for factor in (1, 2)} for a in ('S', 'F')}
    refbase = {factor: F.spectral_project(curve, zeros, curve.band, factor*n, UNIT)[0]
               for factor in (4, 8)}
    summary = []
    for move in moves:
        a = move['coefficients']
        projections = {arm: {factor: p(curve, a, curve.band, factor*n, UNIT)[0]
                       for factor in (1, 2)} for arm, p in projectors.items()}
        increments = {arm: {factor: curve.coefficients+v-bases[arm][factor]
                       for factor, v in p.items()} for arm, p in projections.items()}
        reference = {factor: curve.coefficients+
                     F.spectral_project(curve, a, curve.band, factor*n, UNIT)[0]-refbase[factor]
                     for factor in (4, 8)}
        derivative = FourierCurve(reference[8]).values(2*n, derivative=1)
        tangent = derivative/np.maximum(np.abs(derivative), 1e-30)
        reference_error = field_error(reference[4]-reference[8], 2*n, row['sigma0'])
        trial = {arm: trial_call(updates[arm], spaces[arm], a) for arm in ARMS}
        for arm in ('B', 'C'):
            if updates[arm].counts.get('prepare_fallbacks', 0) or updates[arm].counts.get('device_certificate_fallbacks', 0):
                raise RuntimeError(f'{arm} device fallback: retain state, stop causal comparison')
        receipt = dict(move=move, reference=reference_error, reference_qualified=reference_error['relative']<=1e-10,
            S_F=field_error(increments['S'][1]-increments['F'][1], 2*n, row['sigma0'], tangent),
            moved_S_F=field_error(projections['S'][1]-projections['F'][1], 2*n, row['sigma0']),
            refinement={arm: field_error(p[1]-p[2], 2*n, row['sigma0']) for arm, p in increments.items()},
            reference_errors={arm: field_error(p[1]-reference[8], 2*n, row['sigma0'], tangent)
                              for arm, p in increments.items()},
            raw_retained_coefficients={arm: p[1] for arm, p in increments.items()},
            reference_coefficients=reference[8], trials=trial)
        # Adapter's map should differ only by CUDA base-projection rounding.
        if trial['B']['accepted'] != trial['F']['accepted']:
            receipt['adapter_decision_disagreement'] = True
        write(output/(move['id']+'.json'), receipt)
        summary.append(dict(state=row['id'], move=move['id'], relative=receipt['S_F']['relative']))
    write(output/'counts.json', {a: u.counts for a, u in updates.items()})
    return summary


def timing_panel(states, output):
    rows = []
    for state in (r for r in states if r['timing_panel']):
        curve, m = curve_from(state['curve']), state['M']
        moves = common_moves(curve, m, state['N'])
        # One first trial and one later trial in each newly prepared space.
        selected = [moves[3], moves[6]]
        state_rows = []
        for repeat in range(3):
            order = ARMS[repeat:]+ARMS[:repeat]
            for arm in order:
                update = make_arm(arm)
                with geometry_batch():
                    space, prep = timed(lambda: update.prepare(curve, m, curve.band))
                    calls = [trial_call(update, space, a['coefficients']) for a in selected]
                state_rows.append(dict(state=state['id'], arm=arm, repeat=repeat, order=list(order),
                    preparation_seconds=prep, first_trial=calls[0], subsequent_trial=calls[1], counts=update.counts))
        write(output/(state['id']+'.json'), state_rows)
        rows.extend(state_rows)
        print('TIMING', state['id'], flush=True)
    return rows


def preparation_ablations(states, output):
    rows = []
    for state in (r for r in states if r['id'] in DIAGNOSTIC_IDS):
        curve, m, n = curve_from(state['curve']), state['M'], state['N']
        prepared = {}
        entry = dict(state=state['id'], seconds={})
        for name, update in (('spectral', make_arm('F')), ('coefficient_only', CoefficientsOnly(UNIT)),
                             ('torch_cpu', make_arm('B', device='cpu')), ('torch_cuda', make_arm('B'))):
            prepared[name], entry['seconds'][name] = timed(lambda: update.prepare(curve, m, curve.band))
        entry['columns'] = {name: column_error(p.derivatives, prepared['spectral'].derivatives)
                            for name, p in prepared.items()}
        entry['base_differences'] = {name: field_error(p.base_projection-prepared['spectral'].base_projection,
                                     2*n, state['sigma0']) for name, p in prepared.items()}
        np.testing.assert_allclose(prepared['coefficient_only'].derivatives,
                                   prepared['spectral'].derivatives, rtol=0, atol=0)
        write(output/(state['id']+'.json'), entry)
        rows.append(entry)
        print('ABLATION', state['id'], flush=True)
    return rows


def derivative_panel(states, output):
    for state in (r for r in states if r['id'] in DIAGNOSTIC_IDS):
        curve, m, n = curve_from(state['curve']), state['M'], state['N']
        dim = 2*m+1
        row = dict(state=state['id'], steps=[])
        for step in (1e-6, 1e-7, 1e-8):
            native = {arm: make_arm(arm, step=step).prepare(curve, m, curve.band).derivatives
                      for arm in ('S', 'F', 'B')}
            refined = {}
            for factor in (4, 8):
                columns = []
                for a in np.eye(dim)*step:
                    plus = F.spectral_project(curve, a, curve.band, factor*n, UNIT)[0]
                    minus = F.spectral_project(curve, -a, curve.band, factor*n, UNIT)[0]
                    columns.append((plus-minus)/(2*step))
                refined[factor] = np.stack(columns, axis=1)
            comparison = column_error(refined[4], refined[8])
            row['steps'].append(dict(step_m=step, reference_refinement=comparison,
                reference_qualified=comparison['maximum']<=1e-5,
                reference_errors={arm: column_error(columns, refined[8]) for arm, columns in native.items()},
                S_F=column_error(native['S'], native['F']), B_F=column_error(native['B'], native['F'])))
            write(output/(state['id']+'.json'), row)
        print('DERIVATIVE', state['id'], flush=True)


def interpolation_panel(states, ranked, output, precision):
    index = {r['id']: r for r in states}
    for rank, item in enumerate(sorted(ranked, key=lambda r: (-r['relative'], r['state'], r['move']))[:6]):
        state = index[item['state']]
        curve, n = curve_from(state['curve']), state['N']
        receipt = read(precision/item['state']/(item['move']+'.json'))
        a = np.asarray(receipt['move']['coefficients'])
        parts, bases, checks = {}, {}, {}
        for name, step in (('moved', a), ('base', np.zeros_like(a))):
            moved = moved_curve(curve, step, n)
            panel, checks[name] = inverse_panel(moved, n, curve.band)
            if name == 'moved':
                parts = panel
            else:
                bases = panel
        candidate = {name: curve.coefficients+v-bases[name] for name, v in parts.items()}
        # Complex array receipts are lists of {real,imag}, unlike curve records.
        ref = np.array([complex(v['real'], v['imag']) for v in receipt['reference_coefficients']])
        vectors = dict(inverse=candidate['inverse']-candidate['native'],
                       position=candidate['position']-candidate['native'],
                       interaction=candidate['both']-candidate['inverse']-candidate['position']+candidate['native'],
                       remaining=candidate['both']-ref)
        closure = candidate['native']-ref+vectors['inverse']+vectors['position']+vectors['interaction']-vectors['remaining']
        # Separately refine the moved curve's speed/arclength integration while
        # keeping the native moved Fourier interpolant itself fixed.
        integrated = {}
        moved = moved_curve(curve, a, n)
        base = moved_curve(curve, np.zeros_like(a), n)
        for factor in (1, 2, 4, 8):
            p = F.arclength_quadrature(moved, moved.nodes(factor*n), curve.band)[0]
            b = F.arclength_quadrature(base, base.nodes(factor*n), curve.band)[0]
            integrated[factor] = curve.coefficients+p-b
        row = dict(rank=rank+1, selection=item, checks=checks,
                   reference_qualified=receipt['reference_qualified'],
                   errors={name: field_error(v-ref, 2*n, state['sigma0']) for name, v in candidate.items()},
                   vectors=vectors, vector_norms={name: field_error(v, 2*n, state['sigma0']) for name, v in vectors.items()},
                   closure_maximum=float(np.max(np.abs(closure))),
                   fixed_moved_curve_quadrature={str(f): field_error(v-integrated[8], 2*n, state['sigma0'])
                                                for f, v in integrated.items()},
                   native_reproduction=field_error(candidate['native']-
                       np.array([complex(v['real'], v['imag']) for v in receipt['raw_retained_coefficients']['S']]),
                       2*n, state['sigma0']))
        write(output/f'{rank+1:02d}.json', row)
        print('INTERPOLATION', rank+1, item['state'], item['move'], flush=True)


class Profile:
    """Sequential exclusive nested wall timers; overhead is reported, never subtracted."""
    def __init__(self):
        self.seconds, self.calls, self.stack = defaultdict(float), defaultdict(int), []

    def wrap(self, name, function):
        def call(*args, **kwargs):
            sync()
            begin = time.perf_counter()
            self.stack.append(0.)
            try:
                return function(*args, **kwargs)
            finally:
                sync()
                elapsed = time.perf_counter()-begin
                children = self.stack.pop()
                self.seconds[name] += elapsed-children
                self.calls[name] += 1
                if self.stack:
                    self.stack[-1] += elapsed
        return call


@contextmanager
def instrument(profile):
    from contextlib import ExitStack
    with ExitStack() as stack:
        targets = [(FourierCurve, 'nodes', 'base_or_moved_jets'),
                   (FourierCurve, 'values', 'Fourier_evaluation'),
                   (FourierCurve, 'validate', 'sampled_candidate_validity'),
                   (CG, 'arclength_angles', 'speed_arclength'),
                   (G, 'arclength_angles', 'speed_arclength'),
                   (F, 'arclength_angles', 'speed_arclength'),
                   (G, 'normal_basis', 'normal_basis'), (F, 'normal_basis', 'normal_basis'),
                   (B, 'normal_basis', 'normal_basis'), (C, 'normal_basis', 'normal_basis'),
                   (G, 'self_intersections', 'sampled_intersections'),
                   (F, 'self_intersections', 'sampled_intersections'),
                   (C, 'self_intersections', 'sampled_intersections'),
                   (DeviceCertifiedUpdate, '_certificate', 'certificate'),
                   (C.CertifiedSpectralUpdate, 'check', 'validity_tiers'),
                   (B, 'batched_projection', 'batched_projection_other'),
                   (torch, 'as_tensor', 'tensor_setup_host_to_device'),
                   (torch.Tensor, 'cpu', 'device_to_host'),
                   (torch, 'exp', 'torch_phase'), (torch, 'einsum', 'torch_quadrature'),
                   (np.fft, 'fft', 'numpy_FFT'), (np.fft, 'ifft', 'numpy_FFT'),
                   (torch.fft, 'fft', 'torch_FFT'), (torch.fft, 'ifft', 'torch_FFT')]
        for obj, attr, name in targets:
            stack.enter_context(patch.object(obj, attr, profile.wrap(name, getattr(obj, attr))))
        real_spline = G.CubicSpline
        def spline(*args, **kwargs):
            label = 'spline_position' if kwargs.get('bc_type') == 'periodic' else 'spline_inverse'
            value = profile.wrap(label+'_construction', real_spline)(*args, **kwargs)
            return profile.wrap(label+'_evaluation', value)
        stack.enter_context(patch.object(G, 'CubicSpline', spline))
        # Split the retained production quadrature into its coefficient and
        # crop diagnostic phases for this profiled pass only. Equivalence is
        # checked by focused validation; headline timing always uses production.
        def quadrature(moved, nodes, band):
            def coefficient_phase():
                angles, length = F.arclength_angles(nodes)
                w = moved.values(nodes.num_nodes)
                weights = w*nodes.speeds/(length/(2*np.pi))
                powers = np.empty((band+1, nodes.num_nodes), complex)
                powers[0] = 1
                step = np.exp(-1j*angles)
                for k in range(1, band+1):
                    powers[k] = powers[k-1]*step
                positive = powers@weights/nodes.num_nodes
                negative = powers[1:].conj()@weights/nodes.num_nodes
                coefficients = np.concatenate((negative[::-1], positive))
                return coefficients, w, powers, positive, negative
            coefficients, w, powers, positive, negative = profile.wrap('spectral_coefficients', coefficient_phase)()
            def crop():
                evaluated = coefficients[band]+powers[1:].conj().T@positive[1:]+powers[1:].T@negative
                return float(np.max(np.abs(evaluated-w)))
            return coefficients, profile.wrap('crop_diagnostic', crop)()
        stack.enter_context(patch.object(F, 'arclength_quadrature', quadrature))
        stack.enter_context(patch.object(C, 'arclength_quadrature', quadrature))
        yield


def profile_panel(states, output):
    for state in (r for r in states if r['id'] in DIAGNOSTIC_IDS):
        curve = curve_from(state['curve'])
        a = common_moves(curve, state['M'], state['N'])[3]['coefficients']
        rows = []
        for arm in ARMS:
            update = make_arm(arm)
            profile = Profile()
            with geometry_batch(), instrument(profile):
                space, prep = timed(lambda: update.prepare(curve, state['M'], curve.band))
                prep_components = dict(profile.seconds)
                prep_calls = dict(profile.calls)
                trial = trial_call(update, space, a)
            trial_components = {k: v-prep_components.get(k, 0.) for k, v in profile.seconds.items()}
            rows.append(dict(arm=arm, preparation_seconds=prep, preparation_components=prep_components,
                preparation_calls=prep_calls, preparation_other=prep-sum(prep_components.values()),
                trial=trial, trial_components=trial_components,
                trial_other=trial['seconds']-sum(trial_components.values()),
                semantics='exclusive nested synchronized wall times; overhead retained; separate from headline'))
        write(output/(state['id']+'.json'), rows)
        print('PROFILE', state['id'], flush=True)


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    begun = time.perf_counter()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    try:
        states = state_inputs()
        sources = sorted((campaign.ROOT/'solvers/bem_inverse').rglob('*.py'))
        sources += [Path(__file__), Path(__file__).with_name('test_gc001.py')]
        manifest = dict(experiment='GC-001', approval='user: run, 2026-10-05',
            source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_hashes={str(p.relative_to(campaign.ROOT)):digest(p) for p in sources},
            tg002_manifest_sha256=digest(campaign.INPUTS/'manifest.json'), states=states,
            unique_states=len({r['exact_key'] for r in states}),
            environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                torch=torch.__version__, cpu=platform.processor(), platform=platform.platform(),
                gpu_status=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu',
                                                   '--format=csv,noheader'],text=True),
                gpu_processes=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory',
                                                       '--format=csv,noheader'],text=True),
                cpu_threads=1, workers=1, dtype='float64/complex128'), physics_calls=0,
            cache_scope='geometry runtime both; fresh sampled cache per precision trial and timing/profile arm; lazy C certificate per space')
        write(output/'manifest.json', manifest)
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable; no CPU substitution')
        _, startup = timed(lambda: torch.ones(1,device='cuda'))
        write(output/'startup.json', dict(device_seconds=startup, import_process_start_not_in_timer=True))
        with geometry_runtime('both'), geometry_batch():
            qualification = validate_adapter()
        write(output/'adapter_qualification.json', qualification)
        warmup = {}
        curve = curve_from(states[0]['curve'])
        for arm in ARMS:
            with geometry_runtime('both'), geometry_batch():
                update = make_arm(arm)
                space, prep = timed(lambda: update.prepare(curve, 1, 64))
                trial = trial_call(update, space, np.array([.001, .0001, -.0001]))
                warmup[arm] = dict(preparation_seconds=prep, trial=trial)
        write(output/'warmup.json', warmup)
        torch.cuda.reset_peak_memory_stats()
        phases = {}
        ranked = []
        with geometry_runtime('both'):
            begin = time.perf_counter()
            for i, state in enumerate(states):
                ranked.extend(precision_state(state, output/'precision'/state['id']))
                print('PRECISION', i+1, '/',len(states),state['id'],flush=True)
            phases['precision'] = time.perf_counter()-begin
            for name, function in (
                    ('timing', lambda: timing_panel(states, output/'timing')),
                    ('preparation_ablations', lambda: preparation_ablations(states, output/'preparation_ablations')),
                    ('derivatives', lambda: derivative_panel(states, output/'derivatives')),
                    ('interpolation', lambda: interpolation_panel(states, ranked, output/'interpolation', output/'precision')),
                    ('profiling', lambda: profile_panel(states, output/'profiling'))):
                begin = time.perf_counter()
                function()
                phases[name] = time.perf_counter()-begin
                write(output/'phases.json', phases)
        write(output/'completion.json', dict(completed=True, states=len(states), trials=len(ranked),
            phases_seconds=phases, total_seconds=time.perf_counter()-begun, physics_calls=0,
            host_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved()))
    except BaseException:
        write(output/'failure.json',dict(traceback=traceback.format_exc(), elapsed_seconds=time.perf_counter()-begun))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.output)
