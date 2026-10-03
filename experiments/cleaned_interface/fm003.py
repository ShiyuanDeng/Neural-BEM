"""FM-003 frozen lifting gates, stage-2 censuses and external scoring.

Only this campaign reads archived endpoints or truth. Production solvers and
policy defaults are unchanged. Commands refuse to overwrite incomplete runs.
"""
import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tarfile
from time import perf_counter
import traceback

import numpy as np
from scipy.optimize import minimize_scalar

from bem_inverse.continuation.geometry import FourierCurve, grid_size
from bem_inverse.continuation.geometry_runtime import geometry_runtime
from bem_inverse.continuation.lm_backend import Ledger, fit_stage, inside_box
from bem_inverse.continuation.updates import UpdateRefused
from bem_inverse.geometry import ProjectedUpdate, resize, project
from bem_inverse.io import curve_from, curve_record, digest, read, write
from bem_inverse.physics import Execution, NodalKress
from bem_inverse.policy import CumulativePolicy
from bem_inverse.runner import fit
from . import benchmark as b
from . import fm001

OUTPUT = b.ROOT/'results/validation/cleaned_interfaces/FM-003'
PLAN = b.ROOT/'docs/iterations/cleaned_interfaces/iteration_20/03_plan.md'
HIGH = 'modal__c13.3__development_c'
LOW = 'modal__c4__development_c'
PHASES = {'phase1': (HIGH, False, 512, 4*3600.),
          'phase3': (HIGH, True, 256, 1.5*3600.),
          'phase4': (LOW, False, 256, 1.5*3600.)}
EXECUTION = Execution(device='auto', frequency_threads=4)


def descriptor(case):
    return next(r for r in b.descriptors() if r['id'] == case)


def z1(case):
    return curve_from(read(b.DEFAULT_OUTPUT/'runs'/case/'stage_1_damped.json')['curve'])


def stage_problem(case, full=False, execution=EXECUTION, converged=True):
    row = descriptor(case)
    problem = fm001.full_problem(row, fm001.OUTPUT)[0] if full else b.fitting_problem(row, b.DEFAULT_OUTPUT)
    physics = NodalKress(execution)
    physics.validate(problem)
    op = next(op for op in CumulativePolicy().operations(problem, physics) if op.label == 'stage_2_damped')
    if converged:
        op = replace(op, stage=replace(op.stage, iterations=200, quota=10000))
    return problem, physics, op


def verify(output):
    seal = read(output/'implementation.json')
    for group in ('sources', 'inputs'):
        for name, expected in seal[group].items():
            if digest(b.ROOT/name) != expected:
                raise ValueError(f'Sealed {group} changed: {name}')
    if digest(output/'implementation.tar.gz') != seal['archive_sha256']:
        raise ValueError('Source archive changed')
    return seal


def seal(output):
    if (output/'implementation.json').exists():
        return verify(output)
    sources = sorted(set(b.ROOT.glob('experiments/cleaned_interface/*.py')) |
        set(b.ROOT.glob('experiments/shape_continuation/*.py')) |
        set(b.ROOT.glob('solvers/**/*.py')) | {b.ROOT/'experiments/modal_atlas/mie_localize.py'})
    inputs = {PLAN, b.SOURCE_MANIFEST, b.ROOT/'docs/iterations/FM-003.zip',
              PLAN.parent/'04_execution.md', output/'lift/lift.json',
              output/'lift/implementation.json'}
    for case in (HIGH, LOW):
        row = descriptor(case)
        inputs.update(b.ROOT/row[key] for key in ('truth', 'data', 'initial', 'damped', 'reference_receipt') if key in row)
        for name in ('stage_1_damped.json', 'stage_2_damped.json', 'result.json'):
            inputs.add(b.DEFAULT_OUTPUT/'runs'/case/name)
    for name in ('qualification.json', 'data.npz'):
        inputs.add(fm001.OUTPUT/'catalogs'/HIGH/name)
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output/'implementation.tar.gz', 'w:gz') as tar:
        for path in sources:
            tar.add(path, arcname=b.path_ref(path), recursive=False)
    record = dict(experiment='FM-003', commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
        created_utc=datetime.now(timezone.utc).isoformat(),
        sources={b.path_ref(p):digest(p) for p in sources},
        inputs={b.path_ref(p):digest(p) for p in sorted(inputs)},
        archive_sha256=digest(output/'implementation.tar.gz'), environment=b.environment(),
        execution=asdict(EXECUTION), workers=1, phases=PHASES,
        start_construction=dict(seed=20261004, rho=[.05,.1,.2,.4],
            draw_order='alpha[0:6], beta[0:6] (beta_0 drawn but unused), then rotation when i%8>=4',
            attempts='initial scalar seed, then up to 10 redraws with SeedSequence([20261004+i, attempt])',
            centroid='area centroid of the displaced curve, spectral periodic line integral',
            validity='same projected trial map, curve validation and policy domain box'),
        clustering=dict(linkage='single', loss_relative=.02, loss_scale='max(abs(a),abs(b))', distance_mm=.5),
        recovery=b.COMPARISON['recovery'])
    write(output/'implementation.json', record)
    return record


def lift_gates(output):
    verify(output/'lift')
    row = read(output/'lift/lift.json')
    checks = dict(disk=row['disk']['max_abs_S_nn_minus_1'] <= 1e-10,
        unitarity=all(f['unitarity_error'] <= 1e-8 for f in row['frequencies']),
        symmetry=all(f['symmetry_error'] <= 1e-8 for f in row['frequencies']),
        node_doubling=all(f['resolution_change'] <= 1e-8 for f in row['frequencies']))
    result = dict(passed=all(checks.values()), checks=checks,
        usable=[dict(frequency_hz=f['frequency_hz'], N=lift['N']) for f in row['frequencies']
                for lift in f['lifts'] if lift['ambiguity_among_best'] < 1e-3 and lift['best_paired_residual'] < 1e-2],
        lift_sha256=digest(output/'lift/lift.json'))
    write(output/'lift/gates.json', result)
    return result


def area_centroid(curve):
    z, dz = (curve.values(grid_size(curve.band), j) for j in (0, 1))
    area = np.pi*np.mean(np.imag(np.conj(z)*dz))
    return complex(np.pi*np.mean(z.real**2*dz.imag)/area,
                   -np.pi*np.mean(z.imag**2*dz.real)/area)


def make_start(case, index, output):
    path = output/'starts'/case/f'{index:04d}.json'
    if path.exists():
        return read(path)
    problem, _, op = stage_problem(case)
    base = resize(z1(case), op.stage.curve_modes)
    record = dict(case=case, index=index, attempts=[], source_z1_sha256=digest(
        b.DEFAULT_OUTPUT/'runs'/case/'stage_1_damped.json'))
    if index == 0:
        record.update(valid=True, curve=curve_record(base), rho=0., rotation=0.)
    else:
        update = ProjectedUpdate(problem.length_unit_m)
        rho = (.05, .1, .2, .4)[index % 4]
        sigma = base.nodes(grid_size(base.band)).perimeter/(2*np.pi)
        with geometry_runtime(EXECUTION.geometry):
            space = update.prepare(base, 5, op.stage.curve_modes)
            for attempt in range(11):
                seed = 20261004 + index if attempt == 0 else [20261004 + index, attempt]
                rng = np.random.default_rng(seed)
                alpha, beta = rng.normal(0., rho/(1+np.arange(6)), size=(2, 6))
                angle = float(rng.uniform(0., 2*np.pi)) if index % 8 >= 4 else 0.
                coefficients = sigma*problem.length_unit_m*np.r_[alpha, beta[1:]]
                draw = dict(attempt=attempt, seed=seed, alpha=alpha, beta=beta,
                            rotation=angle, normal_coefficients_m=coefficients)
                try:
                    curve, geometry = update.trial(space, coefficients)
                    center = area_centroid(curve)
                    if angle:
                        values = curve.coefficients*np.exp(1j*angle)
                        values[curve.band] += center*(1-np.exp(1j*angle))
                        curve = FourierCurve(values)
                    curve.validate()
                    if not inside_box(curve, op.optimizer.domain_box):
                        raise UpdateRefused('outside_domain', 'Draw leaves the policy domain box')
                    draw.update(valid=True, geometry=geometry, area_centroid=center)
                    record['attempts'].append(draw)
                    record.update(valid=True, curve=curve_record(curve), rho=rho, rotation=angle)
                    break
                except (UpdateRefused, ValueError) as exc:
                    draw.update(valid=False, reason=getattr(exc, 'reason', type(exc).__name__), detail=str(exc))
                    record['attempts'].append(draw)
            else:
                record.update(valid=False, rho=rho, outcome='START_GEOMETRY_REFUSED')
    write(path, record)
    return read(path)


def run_stage(case, start, folder, *, full=False, converged=True, execution=EXECUTION, seconds=4*3600.):
    if folder.exists():
        raise FileExistsError('Preserve prior stage: '+str(folder))
    folder.mkdir(parents=True)
    write(folder/'input.json', start)
    if not start['valid']:
        row = dict(index=start['index'], outcome='START_GEOMETRY_REFUSED', stop=None,
                   final_loss=None, work=dict(work_units=0), seconds=0.)
        write(folder/'result.json', row)
        return row
    problem, physics, op = stage_problem(case, full, execution, converged)
    update = ProjectedUpdate(problem.length_unit_m)
    ledger = Ledger(cap=10012 if converged else CumulativePolicy().fit_units,
                    seconds=seconds, endpoint_reserve=12)
    write(folder/'configuration.json', dict(operation=op.record(), execution=asdict(execution),
        case=case, full=full, converged_stage=converged, workers=1, seconds_cap=seconds,
        start_sha256=digest(folder/'input.json'), update=update.settings()))
    accepted = []
    def checkpoint(iteration, evaluation):
        accepted.append(dict(iteration=iteration, loss=evaluation.loss, curve=curve_record(evaluation.curve),
                             work_units=ledger.units))
        write(folder/'accepted.json', dict(states=accepted))
    started = perf_counter()
    try:
        ledger.begin_stage(op.label, op.stage.quota)
        with geometry_runtime(execution.geometry):
            result = fit_stage(curve_from(start['curve']), op.stage, problem.contrast, update,
                op.optimizer, ledger, physics=physics, on_accept=checkpoint)
        row = dict(index=start['index'], outcome=result.outcome, stop=result.stop_reason,
            detail=result.detail, initial_loss=result.initial_loss, final_loss=result.final_loss,
            accepted_steps=result.accepted_steps, curve=curve_record(result.curve),
            history=result.history, trials=result.trials, acceptance_checks=result.acceptance_checks,
            work=ledger.snapshot(), seconds=perf_counter()-started, physics=physics.receipt(),
            geometry_work=update.counts)
    except Exception:
        row = dict(index=start['index'], outcome='WORKER_EXCEPTION', stop=None, final_loss=None,
            traceback=traceback.format_exc(), work=ledger.snapshot(), seconds=perf_counter()-started,
            last_accepted=accepted[-1] if accepted else None)
    write(folder/'result.json', row)
    return read(folder/'result.json')


def replay(output):
    verify(output)
    if not lift_gates(output)['passed']:
        raise ValueError('Phase L gates failed')
    start = make_start(HIGH, 0, output)
    result = run_stage(HIGH, start, output/'phase0/replay', converged=False)
    reference = read(b.DEFAULT_OUTPUT/'runs'/HIGH/'stage_2_damped.json')
    c = curve_from(reference['curve']).coefficients
    a = curve_from(result['curve']).coefficients if 'curve' in result else None
    relative = (abs(result['final_loss']/reference['final_loss']-1)
                if result.get('final_loss') is not None else float('inf'))
    checks = dict(accepted_steps=result.get('accepted_steps') == 4,
        stop=result.get('stop') == 'no_decreasing_step',
        loss=relative <= 1e-10,
        identical_coefficients=bool(a is not None and np.array_equal(a, c)))
    gate = dict(passed=all(checks.values()), checks=checks,
        maximum_coefficient_difference=float(np.max(abs(a-c))) if a is not None else None,
        loss_relative_difference=relative,
        reference_final_loss=reference['final_loss'], final_loss=result['final_loss'])
    write(output/'phase0/gates.json', gate)
    if not gate['passed']:
        raise ValueError('Strict Phase 0 replay failed; preserve evidence and stop')
    baseline = run_stage(HIGH, start, output/'phase0/start0')
    serial = run_stage(HIGH, start, output/'phase0/threads1', execution=replace(EXECUTION, frequency_threads=1))
    equivalence = dict(curve_identical=baseline['curve'] == serial['curve'],
        loss_identical=baseline['final_loss'] == serial['final_loss'],
        stop_identical=(baseline['outcome'],baseline['stop']) == (serial['outcome'],serial['stop']),
        accepted_steps_identical=baseline['accepted_steps'] == serial['accepted_steps'],
        work_identical=baseline['work']['work_units'] == serial['work']['work_units'])
    write(output/'phase0/execution_gate.json', dict(passed=all(equivalence.values()),
          checks=equivalence, workers=[1], frequency_threads=[1, 4]))
    if not all(equivalence.values()):
        raise ValueError('Frequency-thread invariance failed')
    return gate


def census(output, phase):
    verify(output)
    if not read(output/'phase0/gates.json')['passed'] or not read(output/'phase0/execution_gate.json')['passed']:
        raise ValueError('Phase 0 gates required')
    predecessor = {'phase3':'phase2/result.json', 'phase4':'phase3/summary.json'}.get(phase)
    if predecessor and not (output/predecessor).exists():
        raise ValueError('Frozen phase order requires '+predecessor)
    case, full, count, cap = PHASES[phase]
    folder = output/phase
    if folder.exists():
        raise FileExistsError('Preserve prior census: '+str(folder))
    folder.mkdir(parents=True)
    started = perf_counter()
    rows = []
    for index in range(count):
        remaining = cap-(perf_counter()-started)
        if remaining <= 0:
            break
        start = make_start(case, index, output)
        if phase == 'phase1' and index == 0:
            row = read(output/'phase0/start0/result.json')
            target = folder/'runs'/f'{index:04d}'
            write(target/'result.json', dict(row, reused_from='phase0/start0/result.json',
                                           reused_sha256=digest(output/'phase0/start0/result.json')))
        else:
            remaining = cap-(perf_counter()-started)
            if remaining <= 0:
                break
            row = run_stage(case, start, folder/'runs'/f'{index:04d}', full=full, seconds=remaining)
        if row['outcome'] == 'TRIAL_WALL_LIMIT':
            write(folder/'timeout.json', dict(index=index, result=row,
                note='Incomplete timed-out start retained, excluded from completed prefix'))
            break
        rows.append(row)
        write(folder/'progress.json', dict(phase=phase, completed=len(rows), scheduled=count,
            seconds=perf_counter()-started, cap_seconds=cap, last_index=index,
            best_loss=min((r['final_loss'] for r in rows if r.get('final_loss') is not None),default=None)))
        print(phase, index, row['outcome'], row.get('stop'), row.get('final_loss'),
              f'{row["seconds"]:.1f}s', flush=True)
    # Winner is frozen before scoring and clustering; no truth loaded above.
    valid = [r for r in rows if r.get('final_loss') is not None and 'curve' in r]
    winner = min(valid, key=lambda r:(r['final_loss'],r['index'])) if valid else None
    receipt = dict(phase=phase, case=case, full=full, completed=len(rows), scheduled=count,
        cap_seconds=cap, seconds=perf_counter()-started, capped=len(rows)<count,
        winner_index=winner['index'] if winner else None, winner_loss=winner['final_loss'] if winner else None,
        work_units=sum(r['work']['work_units'] for r in rows),
        stage_seconds=sum(r['seconds'] for r in rows), workers=1, execution=asdict(EXECUTION),
        implementation_sha256=digest(output/'implementation.json'),
        results={f'runs/{r["index"]:04d}/result.json':digest(folder/'runs'/f'{r["index"]:04d}'/'result.json') for r in rows})
    write(folder/'census.json', receipt)
    summarize(output, phase)
    return receipt


def arclength_curve(curve):
    band = max(192, curve.band)
    return FourierCurve(project(curve, np.zeros(1), band, grid_size(band), .05)[0])


def aligned_preprojected_mm(first, second):
    """FM-001 distance with cached projection and FFT of its 2048-angle search."""
    band = max(first.band, second.band)
    a, c = (resize(curve, band).coefficients for curve in (first, second))
    modes = np.arange(-band, band+1)
    spectrum = np.zeros(2048, complex)
    spectrum[modes % 2048] = c*np.conj(a)
    center = 2*np.pi*int(np.argmax(np.fft.ifft(spectrum).real))/2048
    objective = lambda t: float(np.sum(abs(a-c*np.exp(1j*modes*t))**2))
    minimum = minimize_scalar(objective, bounds=(center-2*np.pi/2048, center+2*np.pi/2048),
                              method='bounded', options=dict(xatol=1e-13))
    return float(50*np.sqrt(max(minimum.fun, 0.)))


def loss_close(a, c):
    return abs(a-c) <= .02*max(abs(a),abs(c))


def single_linkage(rows, curves):
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    edges = []
    for i, row in enumerate(rows):
        for j in range(i):
            if not loss_close(row['final_loss'], rows[j]['final_loss']):
                continue
            # A rigorous lower bound independent of phase saves distant pairs.
            if 50*np.linalg.norm(abs(curves[i].coefficients)-abs(curves[j].coefficients)) >= .5:
                continue
            distance = aligned_preprojected_mm(curves[i], curves[j])
            if distance < .5:
                parent[root(i)] = root(j)
                edges.append(dict(first=row['index'], second=rows[j]['index'], distance_mm=distance))
    groups = {}
    for i in range(len(rows)):
        groups.setdefault(root(i), []).append(i)
    return list(groups.values()), edges


def wilson(hits, total):
    if total == 0:
        return None
    z = 1.959963984540054
    p, d = hits/total, 1+z*z/total
    center = (p+z*z/(2*total))/d
    half = z*np.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return dict(hits=hits, n=total, share=p, wilson95=[max(0.,center-half),min(1.,center+half)],
                zero_hit_one_sided_exact95_upper=1-.05**(1/total) if hits == 0 else None)


def summarize(output, phase):
    census_record = read(output/phase/'census.json')
    rows = [read(output/phase/name) for name in census_record['results']]
    valid = [r for r in rows if r.get('final_loss') is not None and 'curve' in r]
    curves = [arclength_curve(curve_from(r['curve'])) for r in valid]
    groups, edges = single_linkage(valid, curves)
    write(output/phase/'clusters_unscored.json', dict(
        groups=[[valid[i]['index'] for i in group] for group in groups], edges=edges,
        selection='single linkage, relative loss within 2% of larger loss, aligned RMS <0.5 mm'))
    # First access to truth occurs only after the completed census and winner seal.
    truth = arclength_curve(curve_from(read(b.ROOT/descriptor(census_record['case'])['truth'])))
    distances = {r['index']:aligned_preprojected_mm(c, truth) for r,c in zip(valid,curves)}
    clusters = []
    n = len(rows)
    for group in groups:
        members = [valid[i] for i in group]
        rep = min(members, key=lambda r:(r['final_loss'],r['index']))
        clusters.append(dict(size=len(members), share=len(members)/n,
            indices=[r['index'] for r in members], representative=rep['index'],
            loss=rep['final_loss'], loss_range=[min(r['final_loss'] for r in members),max(r['final_loss'] for r in members)],
            stop_reasons=dict(Counter(r['stop'] or r['outcome'] for r in members)),
            representative_truth_distance_mm=distances[rep['index']]))
    clusters.sort(key=lambda c:(c['loss'],c['representative']))
    zcluster = next((c for c in clusters if 0 in c['indices']), None)
    summary = dict(census_record, clusters=clusters, truth_distance_mm=distances,
        stop_reasons=dict(Counter(r['stop'] or r['outcome'] for r in rows)),
        failed_starts=[r['index'] for r in rows if r.get('final_loss') is None],
        lowest_cluster=wilson(clusters[0]['size'] if clusters else 0,n),
        within_5mm=wilson(sum(d<5 for d in distances.values()),n),
        zero_loss=wilson(sum(r['final_loss']<1e-6 for r in valid),n),
        z1_cluster=wilson(zcluster['size'] if zcluster else 0,n),
        G1=bool(clusters and clusters[0]['representative_truth_distance_mm'] < 5))
    write(output/phase/'summary.json', summary)
    return summary


class ContinuationPolicy(CumulativePolicy):
    """Exact CI-001 suffix; spent prefix budget is removed once."""
    def operations(self, problem, physics):
        operations = super().operations(problem, physics)
        first = next(i for i, op in enumerate(operations) if op.label == 'stage_3_damped')
        return (operations[0], *operations[first:])


def continuation(output):
    verify(output)
    census_record = read(output/'phase1/census.json')
    winner = census_record['winner_index']
    if winner is None:
        raise ValueError('No finite stage-2 endpoint to continue')
    source = output/'phase1/runs'/f'{winner:04d}'/'result.json'
    endpoint = read(source)
    folder = output/'phase2'
    if folder.exists():
        raise FileExistsError('Preserve prior continuation: '+str(folder))
    row = descriptor(HIGH)
    problem = replace(b.fitting_problem(row, b.DEFAULT_OUTPUT), initial=curve_from(endpoint['curve']))
    policy = ContinuationPolicy(fit_units=CumulativePolicy().fit_units-162,
                                fit_seconds=CumulativePolicy().fit_seconds-15.5)
    # The phase cap is separately bounded at 15 min including audits; the policy
    # itself retains its specified 1800-15.5 second budget.
    write(folder/'selection.json', dict(winner_index=winner, stage2_loss=endpoint['final_loss'],
        source_sha256=digest(source), selection='lowest stage-2 loss, then lowest start index',
        removed_prefix_units=162, removed_prefix_seconds=15.5, census_cost=census_record))
    from .runner import deadline
    try:
        with deadline(15*60.):
            result = fit(problem, policy=policy, execution=EXECUTION, output=folder,
                on_event=lambda e:print('phase2',e['operation']['label'],e['reason'],flush=True))
        result = fm001.scored(row,result,b.residual_limits(row))
        result.update(winner_index=winner, census_work_units=census_record['work_units'],
            census_seconds=census_record['seconds'],
            total_with_census_and_prefix_units=result['total_units']+162+census_record['work_units'],
            total_with_census_and_prefix_seconds=result['total_seconds']+15.5+census_record['seconds'])
    except Exception:
        result = dict(outcome='CONTINUATION_EXCEPTION', recovered=False, winner_index=winner,
                      traceback=traceback.format_exc())
    write(folder/'result.json', result)
    return result


def report(output):
    report_path = b.ROOT/'docs/iterations/cleaned_interfaces/iteration_21/01_results.md'
    lines = ['# FM-003 results', '',
        'Frozen plan: [iteration 20](../iteration_20/03_plan.md). '
        'Existing `feature/shape-frequency-continuation` branch; production policy unchanged.', '']
    if (output/'implementation.json').exists():
        record=verify(output)
        lines += [f'Baseline `{record["commit"]}`. One worker, four frequency threads, auto device; single-threaded BLAS.', '']
    if (output/'lift/lift.json').exists():
        gates=lift_gates(output)
        lines += [f'Phase L gates: **{"PASS" if gates["passed"] else "FAIL"}**. Usable lifts: `{gates["usable"]}`.', '',
            '| GHz | N | Full truncation floor | Paired residual | Full lift error | Ambiguity | Linear error |',
            '|---|---|---|---|---|---|---|']
        for f in read(output/'lift/lift.json')['frequencies']:
            for l in f['lifts']:
                lines.append(f'| {f["frequency_hz"]/1e9:g} | {l["N"]} | {l["floors"]["full"]:.4g} | '
                    f'{l["best_paired_residual"]:.4g} | {l["chosen_full_error"]:.4g} | '
                    f'{l["ambiguity_among_best"]:.4g} | {l["linear_lift_error"]:.4g} |')
        lines += ['']
    if (output/'phase0/gates.json').exists():
        gate=read(output/'phase0/gates.json')
        lines += [f'Phase 0 strict replay: **{"PASS" if gate["passed"] else "FAIL"}**. '
            f'Checks: `{gate["checks"]}`. Loss relative difference {gate["loss_relative_difference"]:.3g}; '
            f'maximum coefficient difference {gate["maximum_coefficient_difference"]:.3g}.', '']
        if not gate['passed']:
            lines += ['The frozen replay gate stops execution before the census. No search-versus-information conclusion is supported.', '']
    summaries = {}
    for phase in PHASES:
        if not (output/phase/'summary.json').exists():
            continue
        s=read(output/phase/'summary.json'); summaries[phase]=s
        lines += [f'## {phase}: {s["case"]}, {"full" if s["full"] else "paired"}', '',
            f'{s["completed"]}/{s["scheduled"]} starts; {s["seconds"]:.1f} s; {s["work_units"]} units; capped: {s["capped"]}. '
            f'Stop reasons: `{s["stop_reasons"]}`.', '',
            '| Event | Hits / n | Share | Wilson 95% interval |', '|---|---|---|---|']
        for name in ('lowest_cluster','within_5mm','zero_loss','z1_cluster'):
            w=s[name]
            if w:
                lines.append(f'| {name} | {w["hits"]}/{w["n"]} | {w["share"]:.4g} | '
                    f'[{w["wilson95"][0]:.4g}, {w["wilson95"][1]:.4g}] |')
        lines += ['', '| Cluster | Size | Loss | Representative | Truth distance (mm) | Stops |',
            '|---|---|---|---|---|---|']
        for i,c in enumerate(s['clusters']):
            lines.append(f'| {i} | {c["size"]} | {c["loss"]:.9g} | {c["representative"]} | '
                f'{c["representative_truth_distance_mm"]:.5g} | `{c["stop_reasons"]}` |')
        lines += ['']
    if (output/'phase2/result.json').exists():
        result=read(output/'phase2/result.json')
        lines += ['## Continued paired winner', '',
            f'Start {result["winner_index"]}; outcome `{result["outcome"]}`; '
            f'G2 recovered: **{result["recovered"]}**. Metrics: `{result.get("metrics")}`. '
            f'Maximum residual: {result.get("maximum_residual")}.', '']
        if 'total_with_census_and_prefix_units' in result:
            lines += [f'Census + historical prefix + continuation/audits: '
                f'{result["total_with_census_and_prefix_units"]} units, '
                f'{result["total_with_census_and_prefix_seconds"]:.1f} s.', '']
    if 'phase1' in summaries:
        s=summaries['phase1']
        lines += [f'G1: **{s["G1"]}**. Winner chosen by stage-2 loss before truth scoring.', '']
        if s['within_5mm']['hits'] == 0:
            lines += [f'No sampled endpoint is within 5 mm: inconclusive for search. Exact one-sided 95% '
                f'zero-hit upper bound {s["within_5mm"]["zero_hit_one_sided_exact95_upper"]:.4g}.', '']
    lines += ['All start draws, refusals, optimizer trials, timeouts and source/input seals are in '
        '`results/validation/cleaned_interfaces/FM-003/`. Damped synthetic catalogs support no realism claim.', '']
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text('\n'.join(lines))
    return dict(report=b.path_ref(report_path), completed_phases=list(summaries))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['seal','verify','lift-gates','replay','census','continue','report'])
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--phase',choices=PHASES,default='phase1')
    args=parser.parse_args()
    calls={'seal':seal,'verify':verify,'lift-gates':lift_gates,'replay':replay,
           'continue':continuation,'report':report}
    result=census(args.output,args.phase) if args.command=='census' else calls[args.command](args.output)
    print(result if args.command not in ('seal','verify') else {'verified':True},flush=True)


if __name__ == '__main__':
    main()
