"""CG-001: measured transmission folds, complex-radius paths and read-only report."""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
from time import perf_counter
import traceback

import numpy as np
from scipy.optimize import brentq, newton

from bem_inverse.complex_radius import (DiskHomotopy, circle_path, coefficient_jets,
    pseudo_arclength, track)
from bem_inverse.continuation.forward import shape_jacobian, solve
from bem_inverse.continuation.geometry import FourierCurve
from . import campaign

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'results/validation/complex_geometry/CG-001/run-01'
SPECS = [(13.3, (f,)) for f in (.5, 1., 1.5, 2., 2.5)]+[(4., (2.5,)), (.5, (2.5,)), (13.3, None)]
ACTIVE_BUDGET = None


def portable(value):
    if isinstance(value, dict):
        return {str(k): portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable(v) for v in value]
    if isinstance(value, np.ndarray):
        return portable(value.tolist())
    if isinstance(value, (complex, np.complexfloating)):
        return [float(value.real), float(value.imag)]
    if isinstance(value, np.generic):
        return value.item()
    return value


def write(path, value):
    path.write_text(json.dumps(portable(value), indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def instrument(contrast, frequencies, extra=0):
    problem = campaign.problem(f'circle__c{contrast:g}')
    obs = problem.real if frequencies is None else tuple(
        o for o in problem.real if o.frequency_hz/1e9 in frequencies)
    return DiskHomotopy(obs, contrast, extra_cutoff=extra,
                        work_check=None if ACTIVE_BUDGET is None else ACTIVE_BUDGET.check)


def relative(a, b):
    return float(np.linalg.norm(np.asarray(a)-b)/max(np.linalg.norm(b), 1e-30))


@dataclass
class Budget:
    started: float
    seconds: float = 1800.

    def check(self):
        if perf_counter()-self.started > self.seconds:
            raise TimeoutError('CG-001 overall 30 minute wall budget exhausted')


def qualification(folder, budget):
    rows, complex_rows = [], []
    work = []
    started = perf_counter()
    for contrast in (.5, 4., 13.3):
        for frequency in (.5, 2.5):
            model = instrument(contrast, (frequency,))
            refined = instrument(contrast, (frequency,), 12)
            obs = model.observations[0]
            for radius in (.7, 1.3, 1.8):
                budget.check()
                row_started = perf_counter()
                exact = model.jets(radius)[0]*model.scales[0]
                state = solve(FourierCurve.circle(radius), obs.wavenumber, contrast,
                              obs.acquisition, 512, execution_backend='cpu')
                fine = solve(FourierCurve.circle(radius), obs.wavenumber, contrast,
                             obs.acquisition, 1024, execution_backend='cpu')
                derivative = np.asarray(shape_jacobian(fine, np.ones((1024, 1)))).reshape(-1)
                row = dict(contrast=contrast, frequency_ghz=frequency, radius=radius,
                    field_error=relative(exact[0], fine.prediction),
                    nodal_refinement=relative(state.prediction, fine.prediction),
                    derivative_error=relative(exact[1], derivative), seconds=perf_counter()-row_started)
                row['passed'] = (row['field_error'] <= 1e-8 and row['nodal_refinement'] <= 1e-8
                                 and row['derivative_error'] <= 1e-6)
                rows.append(row)
                write(folder/'qualification_progress.json', dict(real_rows=rows, complex_rows=complex_rows))
                print('QUALIFY', contrast, frequency, radius, row['passed'], row['field_error'], flush=True)
            for radius in (1.1+.03j, 1.3-.02j):
                jets = model.jets(radius)[0]
                fine = refined.jets(radius)[0]
                errors = []
                for step in (2e-6, 1e-6):
                    for direction in (1., 1j):
                        fd = (model.jets(radius+direction*step)[0]-
                              model.jets(radius-direction*step)[0])/(2*direction*step)
                        errors.extend(relative(fd[j], jets[j+1]) for j in range(3))
                angles = 2*np.pi*np.arange(64)/64
                rho = .004
                samples = model.jets(radius+rho*np.exp(1j*angles))[0][:, 0, :]
                cauchy_errors = []
                for order, factorial in ((1, 1), (2, 2), (3, 6)):
                    cauchy = factorial*np.mean(samples*np.exp(-1j*order*angles[:, None]), axis=0)/rho**order
                    cauchy_errors.append(relative(cauchy, jets[order]))
                row = dict(contrast=contrast, frequency_ghz=frequency, radius=radius,
                    refinement=[relative(a, b) for a, b in zip(jets, fine)], derivative_errors=errors,
                    derivative_steps=[2e-6, 1e-6], cauchy_radius=rho, cauchy_points=64,
                    cauchy_errors=cauchy_errors)
                row['passed'] = (max(row['refinement']) <= 1e-8 and max(errors) <= 1e-6
                                 and max(cauchy_errors) <= 1e-6)
                complex_rows.append(row)
            work.append(dict(contrast=contrast, frequency_ghz=frequency,
                             counters=model.counters(), refined_counters=refined.counters()))
    answer = dict(passed=all(r['passed'] for r in rows+complex_rows), real_rows=rows,
                  complex_rows=complex_rows, nodal_solves=2*len(rows), nodal_derivatives=len(rows),
                  seconds=perf_counter()-started, work=work)
    write(folder/'qualification.json', answer)
    return answer


def fold_record(model, q):
    A, B, margin = model.ab(q)
    t = float((A[0]/B[0]).real)
    st = model.state(q, t)
    fq_scale = max(1., abs(A[1])+abs(t*B[1]))
    passed = (abs(st['F']) <= 1e-8*st['scale'] and abs(st['Fq']) <= 1e-8*fq_scale
              and abs(st['Ft']) > 1e-6 and abs(st['Fqq']) > 1e-6)
    return dict(q=float(q), t=t, **st, local_passed=bool(passed))


def census(folder, budget):
    all_rows = []
    for index, (contrast, frequencies) in enumerate(SPECS):
        budget.check()
        started = perf_counter()
        model, refined = instrument(contrast, frequencies), instrument(contrast, frequencies, 12)
        qs = np.linspace(.5, 2., 601)
        A, B, margins = model.ab(qs)
        determinant = (A[:, 1]*B[:, 0]-A[:, 0]*B[:, 1]).real
        # Finite plot values plus the denominator preserve pole discontinuities.
        ts = np.divide(A[:, 0].real, B[:, 0].real,
                       out=np.zeros(len(qs)), where=B[:, 0].real != 0)
        folds, failures, excluded = [], [], []
        for lo, hi, fl, fh in zip(qs[:-1], qs[1:], determinant[:-1], determinant[1:]):
            if fl*fh >= 0:
                continue
            try:
                def det(q, service=model):
                    a, b, _ = service.ab(q)
                    return float((a[1]*b[0]-a[0]*b[1]).real)
                q = brentq(det, lo, hi, xtol=2e-13)
                row = fold_record(model, q)
                if not -2 <= row['t'] <= 3:
                    excluded.append(dict(**row, reason='Outside registered t in [-2,3]'))
                    continue
                qr = brentq(lambda q: det(q, refined), lo, hi, xtol=2e-13)
                rr = fold_record(refined, qr)
                row.update(refinement_q=abs(q-qr), refinement_t=abs(row['t']-rr['t']))
                row['qualified'] = bool(row['local_passed'] and rr['local_passed']
                    and max(row['refinement_q'], row['refinement_t']) <= 1e-7)
                folds.append(row)
            except Exception as exc:
                failures.append(dict(bracket=[lo, hi], exception=repr(exc)))
        row = dict(index=index, contrast=contrast, frequencies_ghz=frequencies,
            cutoffs=model.cutoffs, q=qs, t=ts, B=B[:, 0].real,
            determinant=determinant, pole_margin=margins, folds=folds,
            failures=failures, excluded=excluded, counters=model.counters(), refined_counters=refined.counters(),
            seconds=perf_counter()-started)
        all_rows.append(row)
        write(folder/f'census_{index:02d}.json', row)
        print('CENSUS', index, contrast, frequencies, 'folds', len(folds),
              'in [0,1]', sum(0 <= r['t'] <= 1 and r['qualified'] for r in folds), flush=True)
    return all_rows


def select_fold(rows):
    # Start-connected means the first turning point along the increasing-t
    # branch from q0, with no sign change/near-zero B or decreasing t en route.
    fallback = []
    work = []
    for row in rows:
        model = instrument(row['contrast'], row['frequencies_ghz'])
        st = model.state(1.3, 0.)
        direction = np.sign((-st['Ft']/st['Fq']).real)
        candidates = sorted([f for f in row['folds'] if f['qualified'] and
            direction*(f['q']-1.3) > 0], key=lambda f: abs(f['q']-1.3))
        for fold in candidates[:1]:
            q = np.linspace(1.3, fold['q'], 1001)
            a, b, _ = model.ab(q)
            t = (a[:, 0]/b[:, 0]).real
            no_pole = (np.min(abs(b[:, 0])) > 1e-8 and
                       np.all(np.sign(b[:, 0].real) == np.sign(b[0, 0].real)))
            if 0 < fold['t'] <= 1 and no_pole and np.min(np.diff(t)) >= -1e-9:
                work.append(dict(index=row['index'], **model.counters()))
                return row, fold, True, work
        work.append(dict(index=row['index'], **model.counters()))
        fallback += [(abs(f['q']-1.3), row['index'], row, f) for f in row['folds'] if f['qualified']]
    if not fallback:
        return None
    _, _, row, fold = min(fallback, key=lambda item: item[:2])
    return row, fold, False, work


def local_pair(model, fold, radius):
    sign = np.sign((-fold['Ft']/fold['Fqq']).real)
    t = fold['t']+sign*radius
    splitting = np.sqrt(abs(2*(-fold['Ft']/fold['Fqq']).real*radius))
    roots = []
    for side in (-1, 1):
        root = newton(lambda q: model.state(q, t)['F'].real,
                      fold['q']+side*splitting,
                      fprime=lambda q: model.state(q, t)['Fq'].real, tol=1e-13, maxiter=30)
        roots.append(float(root))
    if not roots[0] < fold['q'] < roots[1]:
        raise ValueError('Local fold pair could not be isolated')
    return t, roots, float(splitting)


def path_summary(model, result):
    end = result['states'][-1]
    q, t = end['q'], end['t']
    real = abs(q.imag) <= 1e-8 and abs(t.imag) <= 1e-8
    return dict(status=result['status'], endpoint_q=q, endpoint_t=t,
        stationarity=abs(end['F'])/end['scale'], real=real,
        hessian=float(end['Fq'].real) if real else None,
        homotopy_loss=model.real_loss(q, t) if real else None,
        measured_data_loss=model.real_loss(q, 1.) if real else None,
        max_imaginary_radius=max(abs(r['q'].imag) for r in result['states']),
        minimum_pole_margin=min(r['margin'] for r in result['states']),
        accepted_steps=len(result['states'])-1, rejected_steps=len(result['rejected']),
        seconds=result['seconds'])


def continuation(folder, rows, budget):
    selection = select_fold(rows)
    if selection is None:
        answer = dict(status='NO_QUALIFIED_FOLD')
        write(folder/'continuation.json', answer)
        return answer
    row, fold, connected, selection_counters = selection
    model = instrument(row['contrast'], row['frequencies_ghz'])
    refined = instrument(row['contrast'], row['frequencies_ghz'], 12)
    others = [abs(f['t']-fold['t']) for f in row['folds'] if f['qualified'] and f != fold]
    radius = min(.02, .2*min(others)) if others else .02
    radius = max(1e-5, radius)
    tb, pair, splitting = local_pair(model, fold, radius)
    qb = min(pair, key=lambda q: abs(q-1.3))
    angle = 0. if tb > fold['t'] else np.pi
    arms, summaries = {}, {}

    def save_arm(name, thunk):
        budget.check()
        before = model.counters()
        result = thunk()
        result['counter_delta'] = {k: model.counters()[k]-before[k] for k in before}
        result['summary'] = path_summary(model, result)
        write(folder/f'path_{name}.json', result)
        # Recompute every accepted state's field and stationarity at fixed finer cutoff.
        checks = []
        for state in result['states']:
            fine = refined.state(state['q'], state['t'])
            coarse_fields = model.jets(state['q'])[0][0]
            fine_fields = refined.jets(state['q'])[0][0]
            checks.append(dict(field=relative(coarse_fields, fine_fields),
                stationarity=abs(fine['F'])/fine['scale'],
                Fq_relative=abs(fine['Fq']-state['Fq'])/max(1., abs(state['Fq']))))
        result['refined_checks'] = checks
        arms[name] = result
        summaries[name] = result['summary']
        write(folder/f'path_{name}.json', result)
        print('PATH', name, result['summary'], flush=True)
        return result

    if connected:
        prefix = save_arm('start_connection', lambda: track(model, 1.3, [0., tb]))
        if prefix['status'] != 'COMPLETED' or abs(prefix['states'][-1]['q']-qb) > 1e-7:
            answer = dict(status='START_CONNECTION_FAILED', model_index=row['index'],
                          fold=fold, summaries=summaries)
            write(folder/'continuation.json', answer)
            return answer
        qb = prefix['states'][-1]['q'].real

    save_arm('natural', lambda: track(model, qb, [tb, 2*fold['t']-tb]))
    save_arm('arclength', lambda: pseudo_arclength(model, qb, tb,
        direction=np.sign(fold['q']-qb), steps=200, ds=min(.002, splitting/30)))
    upper_orientation = 1 if angle == 0 else -1
    for name, turns, orientation in [('upper_detour', .5, upper_orientation), ('lower_detour', .5, -upper_orientation),
                                    ('one_loop', 1, 1), ('two_loops', 2, 1)]:
        save_arm(name, lambda turns=turns, orientation=orientation: track(model, qb,
            circle_path(fold['t'], radius, angle, turns, orientation, points=int(256*turns))))
    one = arms['one_loop']
    save_arm('reverse_transport', lambda: track(model, one['states'][-1]['q'],
        circle_path(fold['t'], radius, angle, 1, -1)))
    save_arm('half_step', lambda: track(model, qb,
        circle_path(fold['t'], radius, angle, 1, 1, points=512), max_step=.002))
    th, pairh, splith = local_pair(model, fold, radius/2)
    qh = min(pairh, key=lambda q: abs(q-qb))
    save_arm('half_radius_one', lambda: track(model, qh,
        circle_path(fold['t'], radius/2, angle, 1, 1, points=256)))
    save_arm('half_radius_two', lambda: track(model, qh,
        circle_path(fold['t'], radius/2, angle, 2, 1, points=512)))
    other = max(pair, key=lambda q: abs(q-qb))
    otherh = max(pairh, key=lambda q: abs(q-qh))
    checks = dict(one_loop_swap=abs(summaries['one_loop']['endpoint_q']-other),
        two_loop_restoration=abs(summaries['two_loops']['endpoint_q']-qb),
        reverse_restoration=abs(summaries['reverse_transport']['endpoint_q']-qb),
        half_step_agreement=abs(summaries['half_step']['endpoint_q']-summaries['one_loop']['endpoint_q']),
        half_radius_swap=abs(summaries['half_radius_one']['endpoint_q']-otherh),
        half_radius_restoration=abs(summaries['half_radius_two']['endpoint_q']-qh),
        conjugate_detours=abs(summaries['upper_detour']['endpoint_q']-
                              np.conj(summaries['lower_detour']['endpoint_q'])),
        splitting_ratio=(pair[1]-pair[0])/(2*splitting),
        half_splitting_ratio=(pairh[1]-pairh[0])/(2*splith))
    arclength_crossed = (summaries['arclength']['endpoint_q'].real-fold['q'])*(qb-fold['q']) < 0
    local_qualified = (max(v for k, v in checks.items() if 'splitting' not in k) <= 1e-7
        and abs(checks['half_splitting_ratio']-1) < .1
        and arclength_crossed
        and all(summaries[n]['real'] for n in ('one_loop', 'two_loops', 'reverse_transport',
                                              'half_step', 'half_radius_one', 'half_radius_two'))
        and all(summaries[n]['max_imaginary_radius'] > 1e-8
                for n in ('one_loop', 'two_loops', 'half_radius_one', 'half_radius_two'))
        and all(summaries[n]['status'] == 'COMPLETED' for n in summaries if n != 'natural')
        and all(max(c['field'] for c in arm['refined_checks']) <= 1e-8 for arm in arms.values())
        and all(max(c['stationarity'] for c in arm['refined_checks']) <= 1e-8 for arm in arms.values()))
    # Conditional second fold is chosen geometrically on the exchanged sheet.
    exploration = dict(status='NO_ADJACENT_QUALIFIED_FOLD')
    adjacent = sorted([f for f in row['folds'] if f['qualified'] and
        (f['q']-fold['q'])*(other-fold['q']) > 0], key=lambda f: abs(f['q']-other))
    if local_qualified and adjacent:
        nextfold = adjacent[0]
        # An exact t(q)=A/B branch parameterization is an independent control,
        # not an alternate inverse initializer. It keeps real geometry while
        # transporting the already-exchanged stationary sheet to the next fold.
        eps2 = min(radius, .2*abs(nextfold['t']-fold['t']))
        t2, p2, sp2 = local_pair(model, nextfold, eps2)
        q2 = min(p2, key=lambda q: abs(q-other))
        qtravel = np.linspace(other, q2, 301)
        a, b, _ = model.ab(qtravel)
        ttravel = (a[:, 0]/b[:, 0]).real
        exploration = dict(status='ADJACENT_BRANCH_CHARACTERIZED', next_fold=nextfold,
            branch_q=qtravel, branch_t=ttravel,
            minimum_B=float(np.min(abs(b[:, 0]))),
            explanation='Real t(q) diagnostic precedes a second local loop; not a global path guarantee.')
        no_pole = (np.min(abs(b[:, 0])) > 1e-8 and
                   np.all(np.sign(b[:, 0].real) == np.sign(b[0, 0].real)))
        if no_pole and np.min(ttravel) >= -2 and np.max(ttravel) <= 3:
            angle2 = 0. if t2 > nextfold['t'] else np.pi
            second = save_arm('adjacent_fold_loop', lambda: track(model, q2,
                circle_path(nextfold['t'], eps2, angle2, 1, 1, points=256)))
            exploration.update(start_q=q2, start_t=t2, start_hessian=model.state(q2,t2)['Fq'].real,
                start_measured_loss=model.real_loss(q2), summary=second['summary'],
                note='Local adjacent-fold tour attached by the real branch diagnostic; no t=1 solution claim.')
        else:
            exploration.update(status='BRANCH_DOMAIN_REFUSAL',
                               reason='Sampled attachment crosses B=0 or leaves t in [-2,3]')
    answer = dict(status='QUALIFIED_LOCAL_MONODROMY' if local_qualified else 'UNQUALIFIED_TRANSPORT',
        model_index=row['index'], contrast=row['contrast'], frequencies_ghz=row['frequencies_ghz'],
        start_connected=connected, fold=fold, loop_radius=radius, base_q=qb, base_t=tb,
        local_pair=pair, start_hessian=model.state(qb, tb)['Fq'].real,
        arclength_crossed_fold=arclength_crossed,
        start_measured_loss=model.real_loss(qb), checks=checks, summaries=summaries,
        exploration=exploration, counters=model.counters(), refined_counters=refined.counters(),
        selection_counters=selection_counters)
    write(folder/'continuation.json', answer)
    return answer


def run(folder):
    global ACTIVE_BUDGET
    if folder.exists():
        raise FileExistsError('Preserve the existing run; use a fresh directory')
    folder.mkdir(parents=True)
    started = perf_counter()
    paths = [Path(__file__), ROOT/'solvers/bem_inverse/complex_radius.py',
        ROOT/'pytest/bem_inverse/test_complex_radius.py',
        ROOT/'docs/iterations/complex_geometry/CG-001_plan.md']
    paths = sorted(set(paths+list((ROOT/'solvers').rglob('*.py'))+[
        Path(campaign.__file__), ROOT/'experiments/benchmark/scenes.py',
        ROOT/'experiments/cleaned_interface/benchmark.py']))
    manifest = dict(experiment='CG-001', parent_commit=subprocess.check_output(
        ['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in paths},
        input_manifest_sha256=sha(campaign.INPUTS/'manifest.json'),
        specs=SPECS, environment=dict(python=platform.python_version(), platform=platform.platform(),
        numpy=np.__version__, threading='OMP/OPENBLAS/MKL=1', workers=1))
    write(folder/'manifest.json', manifest)
    budget = Budget(started)
    ACTIVE_BUDGET = budget
    outcome = dict(status='STARTED')
    try:
        campaign.verify(require_inputs=True)
        qualified = qualification(folder, budget)
        if not qualified['passed']:
            outcome = dict(status='PHYSICS_QUALIFICATION_FAILED')
        else:
            rows = census(folder, budget)
            result = continuation(folder, rows, budget)
            outcome = dict(status=result['status'])
    except Exception:
        outcome = dict(status='EXCEPTION', traceback=traceback.format_exc())
        print(outcome['traceback'], flush=True)
    outcome.update(seconds=perf_counter()-started,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        sources_unchanged=all(sha(ROOT/p)==v for p,v in manifest['source_hashes'].items()))
    write(folder/'outcome.json', outcome)
    print('OUTCOME', outcome, flush=True)
    return outcome


def z(value):
    return complex(*value)


def report(folder):
    """Read saved measurements only; no forward, fitting, or branch selection."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    outcome = json.loads((folder/'outcome.json').read_text())
    continuation_path = folder/'continuation.json'
    if not continuation_path.exists():
        return outcome
    saved = json.loads(continuation_path.read_text())
    if 'summaries' not in saved:
        return outcome
    census_row = json.loads((folder/f'census_{saved["model_index"]:02d}.json').read_text())
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4), constrained_layout=True)
    q, t = np.asarray(census_row['q']), np.asarray(census_row['t'])
    good = np.abs(t)<3
    plotted = np.where(good, t, np.nan)
    # Avoid drawing across a pole in the branch parametrization.
    plotted[1:][np.abs(np.diff(t))>.5] = np.nan
    ax[0].plot(q*50, plotted, color='.65', lw=1, label='Real stationary branch')
    fold = saved['fold']
    ax[0].scatter([fold['q']*50],[fold['t']], color='black', marker='x', label='Qualified fold')
    colors = dict(natural='#C44E52', arclength='#55A868', one_loop='#4C72B0', two_loops='#8172B2')
    for name in colors:
        p = folder/f'path_{name}.json'
        if not p.exists():
            continue
        receipt = json.loads(p.read_text())
        qs = np.array([z(s['q']) for s in receipt['states']])
        ts = np.array([z(s['t']) for s in receipt['states']])
        if name in ('natural','arclength'):
            ax[0].plot(qs.real*50, ts.real, color=colors[name], lw=2, label=name.replace('_',' '))
        else:
            ax[1].plot(ts.real, ts.imag, color=colors[name], lw=1.5, label=name.replace('_',' '))
            ax[2].plot(qs.real*50, qs.imag*50, color=colors[name], lw=1.5, label=name.replace('_',' '))
            ax[2].scatter([qs[-1].real*50], [qs[-1].imag*50], color=colors[name], s=24)
    ax[0].set(xlabel='Real radius (mm)', ylabel='Data homotopy t', ylim=(-.05, min(1.1,fold['t']+.2)),
              title='The physical fold and real controls')
    ax[1].set(xlabel='Re(t)', ylabel='Im(t)', title='Loops in the data parameter')
    ax[2].set(xlabel='Re(radius) (mm)', ylabel='Im(radius) (mm)', title='Genuinely complex geometry')
    for a in ax:
        a.grid(alpha=.18); a.legend(fontsize=8)
    fig.suptitle('CG-001 · transmission disk · fixed-center radius family', fontsize=13)
    fig.savefig(folder/'continuation.png', dpi=180)
    fig.savefig(folder/'continuation.svg')
    plt.close(fig)
    lines = ['# CG-001 saved measurements', '', f'Run status: **{outcome["status"]}**.', '',
        'This is a fixed-center radius component study, not a TG-002 recovery result.', '',
        '| Model | Qualified folds, t in [0,1] | Qualified folds, t in [-2,3] | Seconds |',
        '|---|---:|---:|---:|']
    for p in sorted(folder.glob('census_*.json')):
        r=json.loads(p.read_text()); fs=[f for f in r['folds'] if f['qualified']]
        lines.append(f'| c{r["contrast"]}, {r["frequencies_ghz"] or "all 19"} GHz | '
            f'{sum(0<=f["t"]<=1 for f in fs)} | {len(fs)} | {r["seconds"]:.2f} |')
    lines += ['', '| Path | Status | Endpoint radius (mm), real + imaginary | Hessian |', '|---|---|---:|---:|']
    for name, s in saved['summaries'].items():
        radius=z(s['endpoint_q'])*50
        lines.append(f'| {name} | {s["status"]} | {radius.real:.9f} {radius.imag:+.9f}i | {s["hessian"]} |')
    lines += ['', f'Total measured seconds: {outcome["seconds"]:.3f}. Peak process RSS: '
              f'{outcome["peak_rss_mib"]:.1f} MiB.', '', '![Continuation](continuation.png)', '']
    (folder/'README.md').write_text('\n'.join(lines))
    return outcome


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run','report'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args=parser.parse_args()
    if args.command=='run':
        outcome=run(args.output)
        if outcome['status'] in ('EXCEPTION','PHYSICS_QUALIFICATION_FAILED'):
            raise SystemExit(1)
    else:
        print(report(args.output))


if __name__=='__main__':
    main()
