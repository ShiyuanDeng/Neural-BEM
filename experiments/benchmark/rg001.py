"""RG-001 preregistered decision-relative gate experiment on sealed TG-002."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback
import numpy as np
from bem_inverse.continuation import lm_backend as lm
from bem_inverse.geometry_selection import make_update
from bem_inverse.geometry import resize
from bem_inverse.io import read, write, digest, curve_from
from bem_inverse.physics import Execution, NodalKress
from bem_inverse.policy import CumulativePolicy
from bem_inverse.runner import audit, fit, deadline
from experiments.cleaned_interface import benchmark as ci
from . import campaign as B, scenes as S

OUT = B.ROOT/'results/validation/cleaned_interfaces/RG-001'
DOC = B.ROOT/'docs/iterations/cleaned_interfaces/iteration_31'
COORD = Path('/tmp/neural-sdf-bem-ad-coordination')
EXECUTION = Execution(device='cuda', frequency_threads=4)
FAILURES = ('aphex_twin__c0.5', 'aphex_twin__c4', 'aphex_twin__c13.3', 'hook__c13.3')
TIMING = ('circle__c4', 'kite__c0.5', 'star__c13.3')
OWNED = ['solvers/bem_inverse/continuation/lm_backend.py', 'solvers/bem_inverse/policy.py',
         'solvers/bem_inverse/runner.py', 'pytest/bem_inverse/test_rg001.py',
         'experiments/benchmark/rg001.py', str(OUT.relative_to(B.ROOT)),
         'docs/iterations/cleaned_interfaces/iteration_31/04_rg001_execution.md',
         'docs/iterations/cleaned_interfaces/iteration_31/05_results.md']


def git(*args):
    return subprocess.check_output(['git', *args], cwd=B.ROOT, text=True, stderr=subprocess.STDOUT).strip()


def sources():
    paths = sorted([*B.ROOT.glob('solvers/**/*.py'), Path(__file__),
        *(Path(__file__).parent/n for n in ('__init__.py', 'campaign.py', 'scenes.py')),
        B.ROOT/'experiments/cleaned_interface/benchmark.py'])
    return {str(p.relative_to(B.ROOT)): digest(p) for p in paths}


def policy(arm='C', extended=False):
    return CumulativePolicy(required_accuracy=.003, resolution_gate='decision' if arm == 'RG' else 'absolute',
        fit_seconds=900. if extended else 120., fit_units=67060 if extended else 13412,
        audit_seconds=30., audit_aggregate_seconds=30., log_model=True)


@contextmanager
def locked():
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute, (COORD/'source.lock').open('a') as source:
        with deadline(60.):
            fcntl.flock(compute, fcntl.LOCK_EX)
            fcntl.flock(source, fcntl.LOCK_SH)
        yield


def publish(label):
    with (COORD/'git.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if git('diff', '--cached', '--name-only'):
            raise RuntimeError('Another publisher has staged changes')
        existing = [p for p in OWNED if (B.ROOT/p).exists()]
        git('diff', '--check', '--', *existing)
        git('add', '--', *existing)
        if git('diff', '--cached', '--name-only'):
            git('commit', '-m', label)
        git('push')
        branch = git('branch', '--show-current')
        head = git('rev-parse', 'HEAD')
        remote = git('config', f'branch.{branch}.remote')
        ref = git('config', f'branch.{branch}.merge')
        assert git('ls-remote', remote, ref).split()[0] == head
        assert not git('status', '--short', '--', *existing)
        write(COORD/'rg001_publication.json', dict(commit=head, remote_verified=True,
            owned_tree_clean=True, full_status=git('status', '--short')))
        print('PUBLISHED', label, head, flush=True)


def freeze():
    B.verify(require_inputs=True)
    hashes = sources()
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    manifest = OUT/'manifest.json'
    if manifest.exists():
        assert read(manifest)['source_hashes'] == hashes, 'Frozen campaign sources changed'
        return read(manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT/'sources.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for p in hashes:
            bundle.add(B.ROOT/p, arcname=p, recursive=False)
    value = dict(experiment='RG-001', approved_by='user: go on RG-001',
        started_utc=datetime.now(timezone.utc).isoformat(), source_hashes=hashes,
        source_fingerprint=fingerprint, archive_sha256=digest(archive),
        inputs_sha256=digest(B.INPUTS/'manifest.json'), cases=list(S.CASES),
        execution=asdict(EXECUTION), workers=1, blas_threads=1,
        settings={a: asdict(policy(a)) for a in ('C', 'RG')},
        commit=git('rev-parse', 'HEAD'), environment=ci.environment())
    write(manifest, value)
    return value


def check_sources():
    assert read(OUT/'manifest.json')['source_hashes'] == sources()


def truth_case(case):
    """Stage 0 only: never crop the truth to a stage's storage band."""
    p, physics = B.problem(case), B._physics('modal_muller', EXECUTION)
    truth = curve_from(read(B.ROOT/B.row(case)['truth']))
    ops = [o for o in policy().operations(p, physics) if o.kind == 'fit']
    update = make_update('certified_spectral', p.length_unit_m, EXECUTION)
    endpoint = audit(resize(truth, 192), ops[-1].stage, ops[-1].optimizer, p, physics, update, 30.)
    # The same catalog/resolution pair is evaluated once and reused for every
    # policy stage that requests it; no truth-dependent choice of tolerances.
    cache, stages = {}, []
    all_ops = ops + [o for o in policy().tail(p, physics, policy().frontier_top) if o.kind == 'fit']
    for op in all_ops:
        columns = []
        for obs in op.stage.observations:
            key = (obs.frequency_hz, complex(obs.wavenumber), op.stage.nodes, op.stage.refined_nodes)
            if key not in cache:
                low = physics.evaluate(truth, obs, p.contrast, op.stage.nodes).prediction
                high = physics.evaluate(truth, obs, p.contrast, op.stage.refined_nodes).prediction
                cache[key] = float(np.linalg.norm(low-high)/np.linalg.norm(high))
            columns.append(cache[key])
        ratio = np.asarray(columns)/op.stage.discrepancy_tolerances
        stages.append(dict(label=op.label, production=op.stage.nodes, refined=op.stage.refined_nodes,
            frequencies_hz=[o.frequency_hz for o in op.stage.observations],
            damping=[complex(o.wavenumber).imag/complex(o.wavenumber).real for o in op.stage.observations],
            field_relative=columns, tolerances=op.stage.discrepancy_tolerances,
            ratios=ratio, passed=bool(np.all(ratio <= 1)), worst_ratio=float(ratio.max())))
    value = dict(case=case, truth_band=truth.band, endpoint=endpoint, stages=stages,
        endpoint_prediction_passed=bool(endpoint['passed'] and max(endpoint.get('relative_residual', [np.inf])) <= .003),
        gate_limited_by_construction=any(not r['passed'] for r in stages))
    write(OUT/'stage0'/f'{case}.json', value)
    physics.close()
    print('TRUTH', case, value['endpoint_prediction_passed'], max(r['worst_ratio'] for r in stages), flush=True)
    return value


def stage0():
    started = perf_counter()
    with locked():
        freeze()
        folder = OUT/'stage0'
        if folder.exists():
            raise FileExistsError('Preserve Stage 0 evidence')
        folder.mkdir()
        with deadline(900.):
            for case in S.CASES:
                truth_case(case)
        check_sources()
    rows = [read(p) for p in sorted(folder.glob('*.json'))]
    write(OUT/'stage0_summary.json', dict(complete=len(rows) == 30, seconds=perf_counter()-started,
        endpoint_prediction_failures=[r['case'] for r in rows if not r['endpoint_prediction_passed']],
        gate_limited=[r['case'] for r in rows if r['gate_limited_by_construction']]))
    publish('Record RG-001 Stage 0 truth feasibility')


def replay():
    """Four fatal trials rebuilt from saved accepted coefficients and step_m."""
    rows = []
    for case in FAILURES:
        root = B.ROOT/'results/validation/cleaned_interfaces/ON-001/all_B/runs'/case
        saved = read(root/'fit_result.json')
        name = saved['stages'][-1]['stage']
        receipt = read(root/(name+'.json'))
        p, physics = B.problem(case), B._physics('modal_muller', EXECUTION)
        op = next(o for o in policy('RG').operations(p, physics) if o.label == name)
        base_curve = curve_from(receipt['history'][-1]['coefficients'])
        update = make_update('certified_spectral', p.length_unit_m, EXECUTION)
        space = update.prepare(base_curve, op.stage.update_modes, op.stage.curve_modes)
        candidate, _ = update.trial(space, np.asarray(receipt['trials'][-1]['step_m']))
        ledger = lm.Ledger(cap=1000, seconds=120., endpoint_reserve=0)
        obj = lm.Objective(op.stage, p.contrast, op.optimizer, ledger, physics=physics)
        base, trial = obj.production(base_curve, 'replay_base'), obj.production(candidate, 'replay_trial')
        rb, rc = obj.refined(base_curve), obj.refined(candidate)
        row, accurate = lm.resolution_check(base, trial, rb, rc, op.stage, op.optimizer)
        old = receipt['acceptance_checks'][-1]
        differences = {k: abs(row[k]-old[k])/max(abs(old[k]), 1e-30)
                       for k in ('production_gain', 'refined_gain')}
        passed = bool(row['accepted'] and not accurate and max(differences.values()) <= 1e-6)
        rows.append(dict(case=case, stage=name, check=row, saved_check=old,
                         relative_gain_differences=differences, passed=passed))
        physics.close()
        print('REPLAY', case, passed, differences, flush=True)
    value = dict(passed=all(r['passed'] for r in rows), rows=rows)
    write(OUT/'qualification/replay.json', value)
    return value


def run_case(arm, case, batch, extended=False):
    folder = OUT/batch/arm/'runs'/case
    folder.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    settings = policy(arm, extended)
    row = B.row(case)
    try:
        result = fit(ci.fitting_problem(row, B.INPUTS), solver='modal_muller', execution=EXECUTION,
            physics=B._physics('modal_muller', EXECUTION), policy=settings, output=folder,
            geometry_update='certified_spectral', localization_adapter=B.keep_start,
            on_event=lambda e: print(case, arm, e['operation']['label'], e['reason'], flush=True))
        returned = perf_counter()
        metrics = ci.score(row, curve_from(result['final_curve']))
        limits = ci.residual_limits(row)
        residual = result.get('relative_residual')
        result.update(case=row, metrics=metrics, residual_limits=limits,
            recovered=bool(result['final_audit_passed'] and metrics['rms_mm'] <= 1. and
                metrics['hausdorff_upper_mm'] <= 2. and residual is not None and np.all(residual <= limits)),
            maximum_residual=None if residual is None else float(max(residual)),
            audited_output_seconds=returned-started, scoring_seconds=perf_counter()-returned)
    except Exception:
        result = dict(case=row, outcome='WORKER_EXCEPTION', recovered=False, traceback=traceback.format_exc())
    result.update(arm=arm, rg001_settings=asdict(settings), extended_budget_diagnostic=extended,
                  case_seconds=perf_counter()-started)
    write(folder/'result.json', result)
    print('RESULT', case, arm, result['outcome'], result['recovered'], result.get('metrics'), flush=True)
    return result


def validate_result(path):
    r = read(path)
    assert r['case']['id'] in S.CASES
    if r['outcome'] == 'WORKER_EXCEPTION':
        return r
    f = read(path.parent/'fit_result.json')
    assert r['final_curve'] == f['final_curve']
    assert r['fit_work']['work_units'] <= r['rg001_settings']['fit_units']
    m, residual = r['metrics'], r.get('relative_residual')
    assert r['recovered'] == bool(r['final_audit_passed'] and m['rms_mm'] <= 1. and
        m['hausdorff_upper_mm'] <= 2. and residual is not None and np.all(np.asarray(residual) <= r['residual_limits']))
    for s in r['stages']:
        receipt = read(path.parent/(s['stage']+'.json'))
        for check in receipt['acceptance_checks']:
            if check['accepted']:
                assert min(check['production_gain'], check['refined_gain']) > check['margin']+check['disagreement_allowance']
                if r['arm'] == 'C':
                    assert not check.get('numerical_obstruction')
    return r


def child(arm, case, batch, extended=False):
    log = OUT/'logs'/f'{batch}_{arm}_{case}.log'
    log.parent.mkdir(exist_ok=True)
    with log.open('x') as stream:
        subprocess.run([sys.executable, '-m', 'experiments.benchmark.rg001', 'case',
            '--arm', arm, '--cases', case, '--batch', batch, *(['--extended'] if extended else [])],
            stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=1020 if extended else 210)
    return validate_result(OUT/batch/arm/'runs'/case/'result.json')


def accepted_path(result, path):
    coefficients, decisions = [], []
    for stage in result['stages']:
        data = read(path.parent/(stage['stage']+'.json'))
        coefficients += [(stage['stage'], h['coefficients']) for h in data['history']]
        decisions += [(stage['stage'], t.get('status'), t.get('backtrack'), t.get('damping')) for t in data['trials']]
    return coefficients, decisions


def compare(c, rg, cpath, rgpath, tolerance):
    cc, cd = accepted_path(c, cpath)
    rc, rd = accepted_path(rg, rgpath)
    matching = len(cc) == len(rc) and all(a[0] == b[0] for a,b in zip(cc,rc))
    difference = max((float(np.max(abs(curve_from(a[1]).coefficients-curve_from(b[1]).coefficients)))
                      for a,b in zip(cc,rc)), default=0.) if matching else None
    return dict(decisions_identical=cd == rd, coefficients_matching_topology=matching,
                maximum_coefficient_difference=difference, coefficient_tolerance=tolerance,
                passed=bool(c['recovered'] and rg['recovered'] and cd == rd and matching and difference <= tolerance))


def pair(case, batch='all', baseline=False):
    with locked():
        freeze()
        values = {arm: child(arm, case, batch) for arm in ('C', 'RG')}
        check_sources()
    record = dict(case=case, batch=batch, source_fingerprint=read(OUT/'manifest.json')['source_fingerprint'],
                  validated=True, arms={a: {k: v.get(k) for k in ('recovered', 'outcome', 'audited_output_seconds',
                    'metrics', 'final_audit_passed', 'maximum_residual', 'accepted_resolution_overshoots',
                    'largest_accepted_resolution_overshoot')} for a,v in values.items()})
    if values['C']['recovered']:
        tol = read(OUT/'qualification/baseline.json')['coefficient_tolerance']
        record['P1'] = compare(values['C'], values['RG'],
            OUT/batch/'C/runs'/case/'result.json', OUT/batch/'RG/runs'/case/'result.json', tol)
    write(OUT/batch/'pairs'/f'{case}.json', record)
    report()
    publish(f'Record RG-001 {batch} matched pair {case}')
    if 'P1' in record and not record['P1']['passed']:
        raise RuntimeError('P1 fails: stop RG-001 and diagnose')
    return record


def baseline():
    rows = []
    for case in TIMING[:2]:
        with locked():
            runs = [child('C', case, f'baseline{i}') for i in (1,2)]
            check_sources()
        paths = [OUT/f'baseline{i}/C/runs'/case/'result.json' for i in (1,2)]
        result = compare(*runs, *paths, np.inf)
        rows.append(dict(case=case, comparison=result))
        assert runs[0]['recovered'] and runs[1]['recovered'] and result['decisions_identical']
        publish(f'Record RG-001 reproducibility controls {case}')
    value = dict(passed=True, rows=rows,
        coefficient_tolerance=max(r['comparison']['maximum_coefficient_difference'] for r in rows))
    write(OUT/'qualification/baseline.json', value)
    publish('Qualify RG-001 control reproducibility tolerance')
    return value


def independent(case):
    r = read(OUT/'all/RG/runs'/case/'result.json')
    p = B.problem(case)
    curve = curve_from(r['final_curve'])
    physics = NodalKress(Execution(device='cuda', frequency_threads=1))
    op = [o for o in policy().operations(p, physics) if o.kind == 'fit'][-1]
    stage = replace(op.stage, nodes=1024, refined_nodes=2048)
    update = make_update('certified_spectral', p.length_unit_m, EXECUTION)
    result = audit(curve, stage, op.optimizer, p, physics, update, 120.)
    write(OUT/'independent'/f'{case}.json', result)
    physics.close()
    return result


def report():
    rows = [read(p) for p in sorted((OUT/'all/pairs').glob('*.json'))]
    value = dict(completed_pairs=len(rows), recovery={a: sum(r['arms'][a]['recovered'] for r in rows) for a in ('C','RG')},
        additions=[r['case'] for r in rows if r['arms']['RG']['recovered'] and not r['arms']['C']['recovered']],
        regressions=[r['case'] for r in rows if r['arms']['C']['recovered'] and not r['arms']['RG']['recovered']],
        P1_failures=[r['case'] for r in rows if 'P1' in r and not r['P1']['passed']], rows=rows)
    write(OUT/'report.json', value)
    lines = ['# RG-001 paired TG-002 evidence', '', 'Unrun cases remain unrun; extended runs are diagnostic only.', '',
             '| Case | C recovery | RG recovery | RG RMS mm | RG audit | Accepted overshoots |', '|---|---|---|---|---|---|']
    lookup = {r['case']: r for r in rows}
    for case in S.CASES:
        r = lookup.get(case)
        if not r:
            lines.append(f'| {case} | unrun | unrun | — | — | — |')
            continue
        c, rg = r['arms']['C'], r['arms']['RG']
        lines.append(f"| {case} | {c['recovered']} | {rg['recovered']} | {(rg.get('metrics') or {}).get('rms_mm')} | {rg['final_audit_passed']} | {rg['accepted_resolution_overshoots']} |")
    (OUT/'table.md').write_text('\n'.join(lines)+'\n')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('stage0', 'replay', 'baseline', 'pairs', 'case', 'extended', 'independent', 'report'))
    parser.add_argument('--cases', default='all')
    parser.add_argument('--batch', default='all')
    parser.add_argument('--arm', choices=('C','RG'), default='C')
    parser.add_argument('--extended', action='store_true')
    args = parser.parse_args()
    cases = list(S.CASES) if args.cases == 'all' else args.cases.split(',')
    assert cases and all(k in S.CASES for k in cases)
    if args.command == 'stage0':
        stage0()
    elif args.command == 'replay':
        with locked():
            result = replay()
            check_sources()
        publish('Record RG-001 killing-trial replay qualification')
        if not result['passed']:
            raise RuntimeError('Replay qualification incomplete; only one construction repair allowed')
    elif args.command == 'baseline':
        baseline()
    elif args.command == 'pairs':
        assert read(OUT/'qualification/replay.json')['passed']
        assert read(OUT/'qualification/baseline.json')['passed']
        assert read(OUT/'qualification/tests.json')['passed']
        for case in cases:
            pair(case, args.batch)
    elif args.command == 'case':
        assert len(cases) == 1
        run_case(args.arm, cases[0], args.batch, args.extended)
    elif args.command == 'extended':
        assert all(k in FAILURES for k in cases)
        for case in cases:
            with locked():
                child('RG', case, args.batch, True)
                check_sources()
            publish(f'Record RG-001 extended-budget diagnostic {case}')
    elif args.command == 'independent':
        for case in cases:
            with locked():
                independent(case)
                check_sources()
            publish(f'Record RG-001 independent nodal check {case}')
    else:
        report()


if __name__ == '__main__':
    main()
