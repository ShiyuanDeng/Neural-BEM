"""NU-003 spectral increment map: the CI-001 trial map with its spline resampler replaced by eq. 9.

CI-001 (``geometry.ProjectedUpdate``):  T_z(a) = z + P_K[A(z + h n) - A(z)], where A
samples the moved curve, inverts its arclength with a cubic spline and interpolates
it with a second spline at uniform arclength. NU-003 keeps every other step
(normal move h(alpha) n on the uniform theta grid, FFT fit, finite-difference
columns, coarse/fine refinement check, validation) and replaces A by the
change-of-variables quadrature of the proposal's eq. 9,

    R(w)_k = <w(theta) alpha'(theta) e^{-i k alpha(theta)}>_0,   |k| <= K,

evaluated on the same uniform grid. No spline, interpolation or inversion theta(alpha)
remains; grids serve as FFT and quadrature engines. This is spline-free, not
sample-free or exact nonlinear convolution. The increment form keeps the first-order cancellation of
the arclength crop that NU-002 found necessary at the damped bands.

    python -m experiments.cleaned_interface.nu003 precheck --output DIR
    python -m experiments.cleaned_interface.nu003 prepare --output CAMPAIGN
    python -m experiments.cleaned_interface.nu003 run --output CAMPAIGN --cases ...
    python -m experiments.cleaned_interface.nu003 drift --output DIR
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time

import numpy as np

from experiments.shape_continuation.geometry import FourierCurve, arclength_angles, grid_size, normal_basis
from experiments.shape_continuation.updates import UpdateRefused
from experiments.shape_continuation.validation import self_intersections
from . import benchmark as b
from . import runner
from .geometry import ProjectedUpdate, project, values
from .io import read, write, curve_from, portable
from .n_update_audit import ArmPolicy, CORE, case_drift, relative_columns
from .physics import Execution
from .policy import CumulativePolicy

ROOT = b.ROOT
BASE = ROOT/'results/validation/cleaned_interfaces'
ROUNDOFF = 1e-12   # refinement differences below this are round-off (pre-registered, iteration 11)
CONSTRUCTION = 'z + P_K[R(z+h*n)-R(z)], R = eq. 9 arclength quadrature (no splines); FD derivative of the complete trial'


def arclength_quadrature(moved, nodes, band):
    """Coefficients |k| <= band of the arclength curve of ``moved`` by eq. 9 on its uniform nodes.

    Returns (coefficients, crop error): the error is max |P_band R(moved)(alpha_i) - moved(theta_i)|,
    the same intentional-smoothing quantity ``project`` reports, sampled at alpha(theta_i).
    """
    angles, length = arclength_angles(nodes)
    count = nodes.num_nodes
    w = moved.values(count)
    weights = w*nodes.speeds/(length/(2*np.pi))
    step = np.exp(-1j*angles)
    powers = np.empty((band+1, count), complex)
    powers[0] = 1.
    for k in range(1, band+1):
        powers[k] = powers[k-1]*step                       # e^{-i k alpha}
    positive = powers@weights/count                        # k = 0..band
    negative = np.conj(powers[1:])@weights/count           # k = -1..-band
    coefficients = np.concatenate((negative[::-1], positive))
    evaluated = coefficients[band]+np.conj(powers[1:]).T@positive[1:]+powers[1:].T@negative
    return coefficients, float(np.max(np.abs(evaluated-w)))


def spectral_project(curve, coefficients, band, count, length_unit_m, *, validate=False):
    """``geometry.project`` with A replaced by ``arclength_quadrature``; same signature and checks."""
    nodes = curve.nodes(count)
    z = curve.values(count)
    h = normal_basis(nodes, len(coefficients)//2)@coefficients/length_unit_m
    normal = nodes.normals@np.array([1, 1j])
    moved = FourierCurve.from_samples(z+h*normal, count//2-1)
    n = moved.nodes(count)
    if validate:
        if n.signed_area <= 0 or np.min(n.speeds) < 1e-6*np.mean(n.speeds):
            raise UpdateRefused('irregular_parameterization', 'Invalid displaced curve.')
        if self_intersections(n.points):
            raise UpdateRefused('self_intersection', 'Displaced curve self-intersects.')
    return arclength_quadrature(moved, n, band)


class SpectralProjectedUpdate(ProjectedUpdate):
    name = 'centred_state_band_spectral_projection'

    def settings(self):
        return dict(super().settings(), construction=CONSTRUCTION,
                    resampler='eq. 9 quadrature on the uniform grid (count and 2*count); no splines',
                    boundary_samples=True, projection_error_control='coarse/fine diagnostic; not a rigorous bound')

    def _project(self, *args, **kwargs):
        self.counts['geometry_projections'] += 1
        return spectral_project(*args, **kwargs)


# --------------------------------------------------------------------------- pre-check

def _distance(c, d, count):
    return float(np.max(np.abs(values(c-d, count))))


def precheck_state(curve, update_modes, length_unit_m=.05, sizes_m=(1e-7, 1e-3, 6e-3), directions=3, seed=3):
    K, M = curve.band, update_modes
    count = grid_size(max(K, M))
    radius = curve.nodes(count).perimeter/(2*np.pi)
    spline, spectral = ProjectedUpdate(length_unit_m), SpectralProjectedUpdate(length_unit_m)
    t0 = time.perf_counter(); s_spline = spline.prepare(curve, M, K); t_spline = time.perf_counter()-t0
    t0 = time.perf_counter(); s_spec = spectral.prepare(curve, M, K); t_spec = time.perf_counter()-t0
    columns = relative_columns(s_spec.derivatives, s_spline.derivatives)
    rng = np.random.default_rng(seed)
    trials = []
    for size in sizes_m:
        for _ in range(directions):
            a = rng.normal(size=len(s_spline.orders))
            a *= size/max(spline.measure(s_spline, a)['maximum_normal_m'], 1e-300)
            row = dict(size_m=size)
            try:
                coarse = [f(curve, a, K, c, length_unit_m)[0] for f, c in
                          ((project, count), (project, 2*count), (spectral_project, count), (spectral_project, 2*count))]
            except (UpdateRefused, ValueError) as exc:
                trials.append(dict(row, refused=str(exc)))
                continue
            sc, sf, pc, pf = coarse
            T = dict(spline=curve.coefficients+sc-s_spline.base_projection,
                     spline_fine=curve.coefficients+sf-s_spline.fine_base_projection,
                     spectral=curve.coefficients+pc-s_spec.base_projection,
                     spectral_fine=curve.coefficients+pf-s_spec.fine_base_projection)
            g = 2*count
            trials.append(dict(row,
                spectral_vs_spline=_distance(T['spectral'], T['spline'], g)/radius,
                spline_refinement=_distance(T['spline'], T['spline_fine'], g)/radius,
                spectral_refinement=_distance(T['spectral'], T['spectral_fine'], g)/radius,
                spectral_vs_spline_fine=_distance(T['spectral'], T['spline_fine'], g)/radius,
                step_relative=_distance(T['spline'], curve.coefficients, g)/radius))
    return dict(K=K, M=M, count=count, column_relative_max=float(np.max(columns)),
                column_relative_median=float(np.median(columns)), trials=trials,
                prepare_seconds=dict(spline=t_spline, spectral=t_spec))


def precheck(output, source=BASE/'CI-001/runs', **kwargs):
    rows = []
    for case in CORE:
        last = {}
        for state in read(Path(source)/case/'accepted.json')['states']:
            last[state['stage']] = state
        for stage, state in last.items():
            row = dict(case=case, stage=stage, **precheck_state(curve_from(state['curve']), state['M'], **kwargs))
            rows.append(row)
            done = [t for t in row['trials'] if 'refused' not in t]
            print(case, stage, 'K', row['K'], 'M', row['M'], 'col', f"{row['column_relative_max']:.1e}",
                  'trial', f"{max((t['spectral_vs_spline'] for t in done), default=float('nan')):.1e}",
                  'refused', len(row['trials'])-len(done),
                  'prep', {k: round(v, 2) for k, v in row['prepare_seconds'].items()}, flush=True)
    done = [t for r in rows for t in r['trials'] if 'refused' not in t]
    gates = dict(
        trial_within_projection_tolerance=max(t['spectral_vs_spline'] for t in done) <= 1e-5,
        spectral_refines_no_worse=float(np.mean([t['spectral_refinement'] <= max(t['spline_refinement'], ROUNDOFF)
                                                 for t in done])) >= .9,
        columns_within_audit_gate=max(r['column_relative_max'] for r in rows) <= 1e-3)
    result = dict(experiment='NU-003 pre-check', source=str(Path(source).relative_to(ROOT)), states=len(rows),
                  trials=len(done), refused=sum(len(r['trials']) for r in rows)-len(done),
                  worst=dict(spectral_vs_spline=max(t['spectral_vs_spline'] for t in done),
                             spectral_refinement=max(t['spectral_refinement'] for t in done),
                             spline_refinement=max(t['spline_refinement'] for t in done),
                             column_relative=max(r['column_relative_max'] for r in rows)),
                  fraction_spectral_refines_no_worse=float(np.mean(
                      [t['spectral_refinement'] <= max(t['spline_refinement'], ROUNDOFF) for t in done])),
                  prepare_seconds=dict(spline=float(sum(r['prepare_seconds']['spline'] for r in rows)),
                                       spectral=float(sum(r['prepare_seconds']['spectral'] for r in rows))),
                  gates=gates, passed=all(gates.values()), rows=rows)
    write(Path(output)/'precheck.json', result)
    return {k: v for k, v in result.items() if k != 'rows'}


# --------------------------------------------------------------------------- campaign

@contextmanager
def substitution():
    saved = runner.ProjectedUpdate, runner.CumulativePolicy
    runner.ProjectedUpdate = SpectralProjectedUpdate
    runner.CumulativePolicy = lambda: ArmPolicy(geometry_update=CONSTRUCTION)
    try:
        yield
    finally:
        runner.ProjectedUpdate, runner.CumulativePolicy = saved


def prepare(output):
    output = Path(output)
    value = b.prepare(output)
    b.augment(output, None, allow_new_damped_data=True, reuse_from=BASE/'CI-001')
    write(output/'arm.json', dict(experiment='NU-003', arm='S', update='SpectralProjectedUpdate',
        construction=CONSTRUCTION, update_settings=SpectralProjectedUpdate(.05).settings(), cases=list(CORE),
        policy_changes=dict(fit_seconds=[CumulativePolicy.fit_seconds, ArmPolicy.fit_seconds],
                            audit_seconds=[CumulativePolicy.audit_seconds, ArmPolicy.audit_seconds],
                            reason='identical to NU-001 arms A and B; unit caps unchanged')))
    return value


def run(output, execution, cases):
    with substitution():
        return b.run(output, execution, solver='nodal_kress', workers=1, cases=cases)


def decide(nodal, arm):
    """NU-001 rules, unchanged (iteration 08 plan), applied to arm S."""
    drift, match = {}, {}
    for case, row in arm['cases'].items():
        base = nodal['cases'][case]
        degree = {s['stage']: s.get('log_degree') for s in base['stages']}
        flags = []
        if row['max_speed_ratio'] > 1.5:
            flags.append('speed_ratio>1.5')
        if row['max_speed_ratio'] > base['max_speed_ratio']*1.1:
            flags.append('speed_ratio>1.1x nodal')
        for s in row['stages']:
            d0 = degree.get(s['stage'])
            if s.get('log_degree') and d0 and s['log_degree'] > 1.3*d0:
                flags.append(f"log_degree>1.3x nodal at {s['stage']}")
                break
        drift[case] = flags
        status, base_status = arm['status'].get(case), nodal['status'].get(case)
        match[case] = bool((status == 'PASS' or base_status != 'PASS') and (row['recovered'] or not base['recovered']))
    qualifies = not any(drift.values()) and sum(match.values()) >= 5
    return dict(drift_flags=drift, drifts=any(drift.values()), matches=sum(match.values()), match=match,
                qualifies=qualifies,
                outcome='adopt the spectral increment map' if qualifies else 'keep the spline resampler')


def identity(nodal_folder, arm_folder):
    """Logged, not decisive: per-stage accepted steps and final-curve distance against the nodal run."""
    rows = []
    for stage_file in sorted(Path(nodal_folder).glob('*.json')):
        other = Path(arm_folder)/stage_file.name
        data = read(stage_file)
        if 'accepted_steps' not in data or not other.exists():
            continue
        mine = read(other)
        rows.append(dict(stage=stage_file.stem, nodal_accepted=data.get('accepted_steps'),
                         accepted=mine.get('accepted_steps'), nodal_loss=data.get('history', [{}])[-1].get('loss'),
                         loss=mine.get('history', [{}])[-1].get('loss')))
    a, c = read(Path(nodal_folder)/'accepted.json')['states'], read(Path(arm_folder)/'accepted.json')['states']
    za, zc = curve_from(a[-1]['curve']), curve_from(c[-1]['curve'])
    K = max(za.band, zc.band)
    pa, pc = np.pad(za.coefficients, K-za.band), np.pad(zc.coefficients, K-zc.band)
    radius = za.nodes(grid_size(K)).perimeter/(2*np.pi)
    return dict(stages=rows, same_accepted_steps=all(r['nodal_accepted'] == r['accepted'] for r in rows),
                final_curve_relative=_distance(pa, pc, grid_size(K))/radius)


def drift(output, nodal=BASE/'CI-001', arm=BASE/'NU-003', certificate=True):
    report = dict(experiment='NU-003 drift audit', arms={})
    for name, campaign in (('nodal', Path(nodal)), ('S', Path(arm))):
        comparison = read(campaign/'comparison.json') if (campaign/'comparison.json').exists() else dict(rows=[])
        status = {r['id']: r['status'] for r in comparison['rows'] if r['id'] in CORE}
        cases = {}
        for case in CORE:
            folder = campaign/'runs'/case
            if (folder/'accepted.json').exists():
                cases[case] = case_drift(folder, certificate)
                if name == 'S':
                    cases[case]['identity'] = identity(Path(nodal)/'runs'/case, folder)
                print(name, case, 'max r', round(cases[case]['max_speed_ratio'], 4), cases[case]['outcome'], flush=True)
        report['arms'][name] = dict(campaign=str(campaign.resolve().relative_to(ROOT)), status=status, cases=cases)
    if all(len(report['arms'][a]['cases']) == len(CORE) for a in ('nodal', 'S')):
        report['decision'] = decide(report['arms']['nodal'], report['arms']['S'])
    write(Path(output)/'drift.json', report)
    return report.get('decision', 'incomplete')


def main(argv=None):
    parser = argparse.ArgumentParser(description='NU-003 spectral increment map')
    parser.add_argument('command', choices=('precheck', 'prepare', 'run', 'report', 'drift'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', default=list(CORE))
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--frequency-threads', type=int, default=4)
    args = parser.parse_args(argv)
    if args.command == 'precheck':
        value = precheck(args.output)
    elif args.command == 'prepare':
        value = prepare(args.output)
    elif args.command == 'run':
        value = run(args.output, Execution(args.device, args.frequency_threads), args.cases)
    elif args.command == 'report':
        value = b.report(args.output)
    else:
        value = drift(args.output)
    print(json.dumps(portable(value), indent=2))


if __name__ == '__main__':
    main(sys.argv[1:])
