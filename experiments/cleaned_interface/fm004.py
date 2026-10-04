"""FM-004: continue every below-gap FM-003 stage-2 endpoint through the frozen suffix.

The candidate rule is truth-free (stage-2 loss against the census mode); truth is
read only by the frozen scoring after each fixed run. FM-003 evidence is read-only.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tarfile
import traceback

import numpy as np

from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.runner import deadline, fit
from . import fm003 as f
from . import fm003_suffix as suffix

OUTPUT = f.b.ROOT/'results/validation/cleaned_interfaces/FM-004'
PLAN = f.b.ROOT/'docs/iterations/cleaned_interfaces/iteration_22/03_plan.md'
FM003 = f.OUTPUT
RATIO = .9
EXPECTED = (289, 82, 399, 142, 139, 431, 30, 383, 443, 262, 479)
REUSED = 289
CONTROL = 166
NEAR = (82, 142, 139, 431, 30, 383, 443, 262)
FIT_UNITS, FIT_SECONDS, RUN_SECONDS = 13250, 1784.5, 900.


def endpoint(phase, index):
    return FM003/phase/'runs'/f'{index:04d}'/'result.json'


def candidates(output=FM003):
    """Truth-free selection from Phase 1 endpoint losses and the z1 cluster."""
    summary = read(output/'phase1/summary.json')
    mode = next(c for c in summary['clusters'] if 0 in c['indices'])
    threshold = RATIO*mode['loss']
    losses = {i: read(output/'phase1/runs'/f'{i:04d}'/'result.json')['final_loss']
              for i in range(summary['completed'])}
    chosen = sorted((loss, i) for i, loss in losses.items() if np.isfinite(loss) and loss <= threshold)
    return dict(mode_loss=mode['loss'], mode_size=mode['size'], ratio=RATIO, threshold=threshold,
                order=[i for _, i in chosen], losses={str(i): loss for loss, i in chosen},
                next_loss=min(l for l in losses.values() if l > threshold))


def schedule():
    picked = candidates()
    if tuple(picked['order']) != EXPECTED:
        raise ValueError(f'Candidate rule no longer reproduces the frozen list: {picked["order"]}')
    if read(FM003/'phase4/census.json')['winner_index'] != CONTROL:
        raise ValueError('Phase 4 winner differs from the frozen control')
    runs = [(f.HIGH, 'phase1', i) for i in EXPECTED if i != REUSED]
    return picked, runs + [(f.LOW, 'phase4', CONTROL)]


def seal(output=OUTPUT):
    if (output/'implementation.json').exists():
        return verify(output)
    f.verify(FM003)
    picked, runs = schedule()
    sources = sorted(set(f.b.ROOT.glob('experiments/cleaned_interface/*.py')) |
        set(f.b.ROOT.glob('experiments/shape_continuation/*.py')) |
        set(f.b.ROOT.glob('solvers/**/*.py')) | {f.b.ROOT/'experiments/modal_atlas/mie_localize.py'})
    inputs = {PLAN, FM003/'implementation.json', FM003/'implementation.tar.gz',
              FM003/'suffix_implementation.json', FM003/'phase2/result.json',
              FM003/'phase1/census.json', FM003/'phase1/summary.json',
              FM003/'phase4/census.json', FM003/'phase4/summary.json',
              *(endpoint('phase1', i) for i in range(read(FM003/'phase1/census.json')['completed'])),
              *(endpoint(phase, i) for _, phase, i in runs)}
    for case in (f.HIGH, f.LOW):
        inputs.add(f.b.DEFAULT_OUTPUT/'runs'/case/'initial_audit.json')
        row = f.descriptor(case)
        inputs.update(f.b.ROOT/row[key] for key in ('truth', 'data', 'initial', 'damped', 'reference_receipt') if key in row)
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output/'implementation.tar.gz', 'w:gz') as tar:
        for path in sources:
            tar.add(path, arcname=f.b.path_ref(path), recursive=False)
    git = lambda *a: subprocess.check_output(['git', *a], text=True).strip()
    record = dict(experiment='FM-004', commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
        created_utc=datetime.now(timezone.utc).isoformat(),
        sources={f.b.path_ref(p): digest(p) for p in sources},
        inputs={f.b.path_ref(p): digest(p) for p in sorted(inputs)},
        archive_sha256=digest(output/'implementation.tar.gz'), environment=f.b.environment(),
        execution=asdict(f.EXECUTION), workers=1, selection=picked,
        runs=[dict(case=c, phase=p, start=i) for c, p, i in runs], reused=dict(case=f.HIGH, start=REUSED,
            result=f.b.path_ref(FM003/'phase2/result.json')),
        budget=dict(fit_units=FIT_UNITS, fit_seconds=FIT_SECONDS, run_seconds=RUN_SECONDS),
        certified='final_audit_passed and all per-frequency relative residuals <= residual limits',
        recovery=f.b.COMPARISON['recovery'])
    write(output/'implementation.json', record)
    return record


def verify(output=OUTPUT):
    record = read(output/'implementation.json')
    for group in ('sources', 'inputs'):
        for name, expected in record[group].items():
            if digest(f.b.ROOT/name) != expected:
                raise ValueError(f'Sealed {group} changed: {name}')
    if digest(output/'implementation.tar.gz') != record['archive_sha256']:
        raise ValueError('Source archive changed')
    return record


def certified(result):
    residual = result.get('relative_residual')
    return bool(result.get('final_audit_passed') and residual is not None and
                np.all(np.asarray(residual) <= np.asarray(result['residual_limits'])))


def continue_one(case, phase, index, output=OUTPUT):
    source = endpoint(phase, index)
    folder = output/'runs'/case/f'{index:04d}'
    if folder.exists():
        raise FileExistsError('Preserve prior continuation: '+str(folder))
    start = read(source)
    row = f.descriptor(case)
    problem = replace(f.b.fitting_problem(row, f.b.DEFAULT_OUTPUT), initial=curve_from(start['curve']))
    policy = f.ContinuationPolicy(fit_units=FIT_UNITS, fit_seconds=FIT_SECONDS)
    original = f.b.DEFAULT_OUTPUT/'runs'/case/'initial_audit.json'
    write(folder/'selection.json', dict(case=case, phase=phase, start=index, stage2_loss=start['final_loss'],
        source=f.b.path_ref(source), source_sha256=digest(source),
        implementation_sha256=digest(output/'implementation.json')))
    try:
        with deadline(RUN_SECONDS):
            result = fit(problem, policy=policy, execution=f.EXECUTION, output=folder,
                audit_adapter=suffix.SuffixAudit(original),
                on_event=lambda e: print(case, index, e['operation']['label'], e['reason'], flush=True))
        limits = f.b.residual_limits(row)
        result = f.fm001.scored(row, result, limits)
        result.update(certified=certified(result))
    except Exception:
        result = dict(outcome='CONTINUATION_EXCEPTION', recovered=False, certified=False,
                      traceback=traceback.format_exc())
    result.update(case=case, start=index, stage2_loss=start['final_loss'],
                  initial_audit_reused_from_prefix=True, continued_endpoint_initial_audit_performed=False)
    write(folder/'result.json', result)
    return result


def run(output=OUTPUT):
    verify(output)
    _, runs = schedule()
    for case, phase, index in runs:
        if (output/'runs'/case/f'{index:04d}'/'result.json').exists():
            continue
        result = continue_one(case, phase, index, output)
        print('FM-004', case, index, result.get('outcome'), 'recovered', result['recovered'],
              'certified', result['certified'], flush=True)
    verify(output)


def row_of(result, stage2_distance):
    metrics = result.get('metrics') or {}
    return dict(case=result['case'], start=result.get('start', result.get('winner_index')),
        stage2_loss=result['stage2_loss'], stage2_truth_distance_mm=stage2_distance,
        outcome=result.get('outcome'), final_audit_passed=result.get('final_audit_passed'),
        maximum_residual=result.get('maximum_residual'), rms_mm=metrics.get('rms_mm'),
        hausdorff_upper_mm=metrics.get('hausdorff_upper_mm'), recovered=bool(result['recovered']),
        certified=bool(result.get('certified', certified(result) if 'relative_residual' in result else False)),
        units=result.get('total_units'), seconds=result.get('total_seconds'))


def report(output=OUTPUT):
    record = verify(output)
    distances = {ph: read(FM003/ph/'summary.json')['truth_distance_mm'] for ph in ('phase1', 'phase4')}
    rows = []
    reused = read(FM003/'phase2/result.json')
    reused.update(case=f.HIGH, start=REUSED, stage2_loss=record['selection']['losses'][str(REUSED)],
                  certified=certified(reused))
    rows.append(dict(row_of(reused, distances['phase1'][str(REUSED)]), reused_from='FM-003 phase2'))
    for item in record['runs']:
        path = output/'runs'/item['case']/f'{item["start"]:04d}'/'result.json'
        if not path.exists():
            rows.append(dict(case=item['case'], start=item['start'], outcome='NOT_RUN', recovered=False, certified=False))
            continue
        rows.append(row_of(read(path), distances[item['phase']][str(item['start'])]))
    paired = [r for r in rows if r['case'] == f.HIGH]
    near = [r for r in paired if r['start'] in NEAR]
    control = next(r for r in rows if r['case'] == f.LOW)
    r1 = sum(r['recovered'] for r in near)
    census = read(FM003/'phase1/census.json')
    suffix_units = [r['units'] for r in paired if r.get('units') is not None]
    suffix_seconds = [r['seconds'] for r in paired if r.get('seconds') is not None]
    first = next((k for k, r in enumerate(paired) if r['certified']), None)
    recovered = sum(r['recovered'] for r in paired)
    readings = dict(
        R1=dict(recovered=r1, n=len(near), reading='basin' if r1 >= 6 else 'luck' if r1 <= 2 else 'mixed'),
        R2=dict(agree=all(r['certified'] == r['recovered'] for r in rows),
                certified_not_recovered=[(r['case'], r['start']) for r in rows if r['certified'] and not r['recovered']],
                recovered_not_certified=[(r['case'], r['start']) for r in rows if r['recovered'] and not r['certified']]),
        R3=dict(start=399, **{k: next(r[k] for r in paired if r['start'] == 399) for k in ('recovered', 'certified')}),
        R4=dict(start=CONTROL, recovered=control['recovered'], certified=control['certified']))
    cost = dict(census_units=census['work_units'], census_seconds=census['seconds'],
        paired_recovered=recovered, paired_continued=len(paired),
        mean_suffix_units=float(np.mean(suffix_units)), mean_suffix_seconds=float(np.mean(suffix_seconds)),
        census_units_per_recovery=census['work_units']/recovered if recovered else None,
        census_seconds_per_recovery=census['seconds']/recovered if recovered else None,
        sequential_stop=None if first is None else dict(position=first+1, start=paired[first]['start'],
            units=census['work_units']+sum(r['units'] for r in paired[:first+1]),
            seconds=census['seconds']+sum(r['seconds'] for r in paired[:first+1])))
    summary = dict(experiment='FM-004', implementation_sha256=digest(output/'implementation.json'),
                   selection=record['selection'], rows=rows, readings=readings, cost=cost)
    write(output/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('seal', 'verify', 'run', 'report', 'candidates'))
    args = parser.parse_args()
    result = dict(seal=seal, verify=verify, run=run, report=report, candidates=candidates)[args.command]()
    if args.command in ('report', 'candidates'):
        print(result if args.command == 'candidates' else result['readings'], flush=True)


if __name__ == '__main__':
    main()
