"""FM-005: FM-004 continuations with RB-001's opt-in resolution response.

Identical to FM-004 except ``resolution_response`` (reject unresolved trials;
promote once to N1024/2048) and the execution deadlines forced by slower solves.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import subprocess
import tarfile
from time import perf_counter
import traceback

import numpy as np

from bem_inverse.continuation.lm_backend import ResolutionResponse
from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.physics import Execution, NodalKress
from bem_inverse.runner import deadline, fit
from . import fm004 as g

f = g.f
OUTPUT = f.b.ROOT/'results/validation/cleaned_interfaces/FM-005'
PLAN = f.b.ROOT/'docs/iterations/cleaned_interfaces/iteration_24/03_plan.md'
FM004 = g.OUTPUT
FINER = Execution(device='auto', frequency_threads=4, resolution=1024)
NODES, REFINED = 1024, 2048
RUN_SECONDS, CAMPAIGN_SECONDS = 2400., 3*3600.
REFUSED = (82, 399, 139, 431, 30, 383, 479)
NEAR = (82, 139, 431, 30, 383, 479)
RECOVERED = (289, 142, 443, 262)
RUNS = ([(f.HIGH, 'phase1', i) for i in REFUSED] + [(f.LOW, 'phase4', g.CONTROL)] +
        [(f.HIGH, 'phase1', i) for i in RECOVERED])


def fm004_result(case, index):
    if case == f.HIGH and index == g.REUSED:
        return g.FM003/'phase2/result.json'
    return FM004/'runs'/case/f'{index:04d}'/'result.json'


def fm004_accepted(case, index):
    folder = g.FM003/'phase2' if case == f.HIGH and index == g.REUSED else FM004/'runs'/case/f'{index:04d}'
    return folder/'accepted.json'


def schedule():
    g.schedule()
    for case, _, index in RUNS:
        outcome = read(fm004_result(case, index))
        refused = outcome['outcome'] == 'NUMERICAL_FAILURE'
        if refused != (index in REFUSED or index == g.CONTROL):
            raise ValueError(f'FM-004 outcome of {case} {index} differs from the frozen split')
    return RUNS


def seal(output=OUTPUT):
    if (output/'implementation.json').exists():
        return verify(output)
    g.verify(FM004)
    f.verify(g.FM003)
    runs = schedule()
    sources = sorted(set(f.b.ROOT.glob('experiments/cleaned_interface/*.py')) |
        set(f.b.ROOT.glob('experiments/shape_continuation/*.py')) |
        set(f.b.ROOT.glob('solvers/**/*.py')) | {f.b.ROOT/'experiments/modal_atlas/mie_localize.py'})
    inputs = {PLAN, FM004/'implementation.json', FM004/'implementation.tar.gz', FM004/'summary.json',
              *(g.endpoint(phase, i) for _, phase, i in runs),
              *(fm004_result(c, i) for c, _, i in runs), *(fm004_accepted(c, i) for c, _, i in runs)}
    for case in (f.HIGH, f.LOW):
        inputs.add(f.b.DEFAULT_OUTPUT/'runs'/case/'initial_audit.json')
        row = f.descriptor(case)
        inputs.update(f.b.ROOT/row[key] for key in ('truth', 'data', 'initial', 'damped', 'reference_receipt') if key in row)
    output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output/'implementation.tar.gz', 'w:gz') as tar:
        for path in sources:
            tar.add(path, arcname=f.b.path_ref(path), recursive=False)
    git = lambda *a: subprocess.check_output(['git', *a], text=True).strip()
    record = dict(experiment='FM-005', commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
        created_utc=datetime.now(timezone.utc).isoformat(),
        sources={f.b.path_ref(p): digest(p) for p in sources},
        inputs={f.b.path_ref(p): digest(p) for p in sorted(inputs)},
        archive_sha256=digest(output/'implementation.tar.gz'), environment=f.b.environment(),
        execution=asdict(f.EXECUTION), finer_execution=asdict(FINER), workers=1,
        resolution_response=dict(production_nodes=NODES, refined_nodes=REFINED),
        runs=[dict(case=c, phase=p, start=i, block='primary' if c == f.LOW or i in REFUSED else 'non_regression')
              for c, p, i in runs],
        budget=dict(fit_units=g.FIT_UNITS, fit_seconds=g.FIT_SECONDS, run_seconds=RUN_SECONDS,
                    campaign_seconds=CAMPAIGN_SECONDS),
        certified=read(FM004/'implementation.json')['certified'], recovery=f.b.COMPARISON['recovery'])
    write(output/'implementation.json', record)
    return record


def verify(output=OUTPUT):
    return g.verify(output)


def continue_one(case, phase, index, output=OUTPUT):
    source = g.endpoint(phase, index)
    folder = output/'runs'/case/f'{index:04d}'
    if folder.exists():
        raise FileExistsError('Preserve prior continuation: '+str(folder))
    start = read(source)
    row = f.descriptor(case)
    problem = replace(f.b.fitting_problem(row, f.b.DEFAULT_OUTPUT), initial=curve_from(start['curve']))
    policy = f.ContinuationPolicy(fit_units=g.FIT_UNITS, fit_seconds=g.FIT_SECONDS)
    original = f.b.DEFAULT_OUTPUT/'runs'/case/'initial_audit.json'
    write(folder/'selection.json', dict(case=case, phase=phase, start=index, stage2_loss=start['final_loss'],
        source=f.b.path_ref(source), source_sha256=digest(source),
        implementation_sha256=digest(output/'implementation.json')))
    started = perf_counter()
    try:
        with deadline(RUN_SECONDS):
            result = fit(problem, policy=policy, execution=f.EXECUTION, output=folder,
                audit_adapter=g.suffix.SuffixAudit(original),
                resolution_response=ResolutionResponse(NODES, REFINED, NodalKress(FINER)),
                on_event=lambda e: print(case, index, e['operation']['label'], e['reason'], flush=True))
        result = f.fm001.scored(row, result, f.b.residual_limits(row))
        result.update(certified=g.certified(result))
    except Exception:
        result = dict(outcome='CONTINUATION_EXCEPTION', recovered=False, certified=False,
                      traceback=traceback.format_exc())
    result.update(case=case, start=index, stage2_loss=start['final_loss'], wall_seconds=perf_counter()-started,
                  initial_audit_reused_from_prefix=True, continued_endpoint_initial_audit_performed=False)
    write(folder/'result.json', result)
    return result


def run(output=OUTPUT):
    verify(output)
    started = perf_counter()
    skipped = []
    for case, phase, index in schedule():
        if (output/'runs'/case/f'{index:04d}'/'result.json').exists():
            continue
        if perf_counter()-started > CAMPAIGN_SECONDS:
            skipped.append(dict(case=case, start=index))
            continue
        result = continue_one(case, phase, index, output)
        print('FM-005', case, index, result.get('outcome'), 'recovered', result['recovered'],
              'certified', result['certified'], flush=True)
    write(output/'campaign.json', dict(seconds=perf_counter()-started, skipped_by_campaign_cap=skipped))
    verify(output)


def first_difference(case, index, output=OUTPUT):
    """Index of the first accepted state whose curve differs from FM-004's, else None."""
    before = read(fm004_accepted(case, index))['states']
    path = output/'runs'/case/f'{index:04d}'/'accepted.json'
    after = read(path)['states'] if path.exists() else []
    for k, (a, b) in enumerate(zip(before, after)):
        if a['stage'] != b['stage'] or a['curve'] != b['curve']:
            return k
    return None if len(before) == len(after) else min(len(before), len(after))


def resolution_summary(result):
    events = [e for s in result.get('stages', []) for e in s.get('resolution_events') or []]
    return dict(promoted=result.get('resolution_promoted'),
        promotion_stage=next((s['stage'] for s in result.get('stages', []) if s.get('nodes') == NODES), None),
        rejected_unresolved=sum(e['action'] == 'reject_inaccurate_candidate' for e in events),
        refinement_attempts=sum(e['action'] == 'refinement_attempt' for e in events),
        stop_stage=next((s['stage'] for s in result.get('stages', [])
                         if s['outcome'] not in ('NORMAL_OPTIMIZER_RETURN', 'STAGE_QUOTA_REACHED')), None))


def report(output=OUTPUT):
    record = verify(output)
    distances = {ph: read(g.FM003/ph/'summary.json')['truth_distance_mm'] for ph in ('phase1', 'phase4')}
    rows = []
    for item in record['runs']:
        case, start = item['case'], item['start']
        path = output/'runs'/case/f'{start:04d}'/'result.json'
        before = read(fm004_result(case, start))
        if not path.exists():
            rows.append(dict(case=case, start=start, block=item['block'], outcome='NOT_RUN',
                             recovered=False, certified=False, fm004_recovered=bool(before['recovered'])))
            continue
        result = read(path)
        rows.append(dict(g.row_of(result, distances[item['phase']][str(start)]), block=item['block'],
            detail=result.get('detail'), fm004_outcome=before['outcome'], fm004_recovered=bool(before['recovered']),
            first_differing_accepted_state=first_difference(case, start, output), **resolution_summary(result)))
    near = [r for r in rows if r['case'] == f.HIGH and r['start'] in NEAR]
    control = next(r for r in rows if r['case'] == f.LOW)
    p1 = sum(r['recovered'] for r in near)
    paired = [r for r in rows if r['case'] == f.HIGH]
    recovered = sum(r['recovered'] for r in paired)
    census = read(g.FM003/'phase1/census.json')
    readings = dict(
        P1=dict(recovered=p1, n=len(near), reading='gate' if p1 >= 5 else 'not_gate' if p1 <= 1 else 'mixed'),
        P2=dict(start=g.CONTROL, recovered=control['recovered'], certified=control['certified']),
        P3=dict(start=399, **{k: next(r[k] for r in paired if r['start'] == 399) for k in ('recovered', 'certified')}),
        P4=dict(kept=[r['start'] for r in paired if r['start'] in RECOVERED and r['recovered']],
                lost=[r['start'] for r in paired if r['start'] in RECOVERED and not r['recovered']]),
        P5=dict(agree=all(r['certified'] == r['recovered'] for r in rows),
                certified_not_recovered=[(r['case'], r['start']) for r in rows if r['certified'] and not r['recovered']],
                recovered_not_certified=[(r['case'], r['start']) for r in rows if r['recovered'] and not r['certified']]))
    cost = dict(census_units=census['work_units'], census_seconds=census['seconds'], paired_recovered=recovered,
        paired_continued=len(paired),
        census_units_per_recovery=census['work_units']/recovered if recovered else None,
        census_seconds_per_recovery=census['seconds']/recovered if recovered else None,
        mean_suffix_units=float(np.mean([r['units'] for r in paired if r.get('units') is not None])),
        mean_suffix_seconds=float(np.mean([r['seconds'] for r in paired if r.get('seconds') is not None])))
    summary = dict(experiment='FM-005', implementation_sha256=digest(output/'implementation.json'),
                   campaign=read(output/'campaign.json') if (output/'campaign.json').exists() else None,
                   rows=rows, readings=readings, cost=cost)
    write(output/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('seal', 'verify', 'run', 'report'))
    args = parser.parse_args()
    result = dict(seal=seal, verify=verify, run=run, report=report)[args.command]()
    if args.command == 'report':
        print(result['readings'], flush=True)


if __name__ == '__main__':
    main()
