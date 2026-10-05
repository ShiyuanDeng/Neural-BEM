"""CS-001: paired TG-002 screen of the revised four-phase continuation."""
import argparse
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback

import numpy as np

from bem_inverse.continuation_policy import ShapeFrequencyPolicy
from bem_inverse.geometry import resize
from bem_inverse.io import read, write, digest, curve_from
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from bem_inverse.runner import fit
from bem_inverse.similarity import SimilarityUpdate
from . import campaign as c
from experiments.cleaned_interface import benchmark as ci

ID = 'CS-001'
OUTPUT = c.ROOT/'results/validation/cleaned_interfaces'/ID
PLAN = c.ROOT/'docs/iterations/CI-SPD/CS-001_plan.md'
CASES = ('circle__c4', 'kite__c4', 'peanut__c0.5', 'cog__c4', 'c_shape__c13.3',
         'hook__c13.3', 'aphex_twin__c4', 'aphex_twin__c13.3')
COORD = Path('/tmp/neural-sdf-bem-ad-coordination')


def sources():
    return sorted({*c.ROOT.glob('solvers/**/*.py'), Path(__file__),
        *(Path(__file__).parent/name for name in ('__init__.py', 'campaign.py', 'scenes.py')),
        Path(__file__).with_name('cs001_report.py'),
        c.ROOT/'experiments/cleaned_interface/benchmark.py', PLAN,
        c.ROOT/'pytest/bem_inverse/test_continuation_policy.py'})


def hashes():
    return {str(p.relative_to(c.ROOT)): digest(p) for p in sources()}


def policy(arm):
    cls = CumulativePolicy if arm == 'control' else ShapeFrequencyPolicy
    return cls(required_accuracy=.003, damping_rule='agreement', avoid_terminal_linearization=True,
        fit_seconds=120., audit_seconds=30., audit_aggregate_seconds=30., log_model=True)


def execution():
    return Execution(device='cuda', frequency_threads=4, audit_frequency_batch=2)


def prepare():
    c.verify(require_inputs=True)
    folder = OUTPUT/'preparation'
    folder.mkdir(parents=True, exist_ok=False)
    before = hashes()
    write(folder/'qualification.json', dict(status='RUNNING', rows=[]))
    rows = []
    try:
        # Independent per-coordinate central differences at TG-002's metre units.
        for device in ('cpu', 'cuda'):
            service = c._physics('modal_muller', Execution(device=device, frequency_threads=1))
            for contrast in ('0.5', '4', '13.3'):
                p = c.problem('circle__c'+contrast)
                curve = resize(p.initial, 4)
                update = SimilarityUpdate(p.length_unit_m)
                space = update.prepare(curve, 0, 4)
                resolution = service.resolution_profile(4)['production']
                state = service.evaluate(curve, p.damped[0], p.contrast, resolution)
                jac = service.derivative(state, update, space)
                errors = []
                for column in range(3):
                    delta = np.eye(3)[column]*1e-6
                    high = service.evaluate(update.trial(space, delta)[0], p.damped[0], p.contrast, resolution)
                    low = service.evaluate(update.trial(space, -delta)[0], p.damped[0], p.contrast, resolution)
                    fd = (high.prediction-low.prediction)/2e-6
                    errors.append(float(np.linalg.norm(fd-jac[:, column])/np.linalg.norm(fd)))
                rows.append(dict(device=device, contrast=p.contrast, frequency_hz=p.damped[0].frequency_hz,
                                 relative_column_errors=errors))
                write(folder/'qualification.json', dict(status='RUNNING', rows=rows))
        errors = np.asarray([e for row in rows for e in row['relative_column_errors']])
        maximum = float(errors.max())
        if not np.isfinite(errors).all() or maximum > 1e-5:
            raise ValueError('TG-002 similarity derivative qualification failed')
        if before != hashes():
            raise ValueError('Source changed during qualification')
        write(folder/'qualification.json', dict(status='PASSED', rows=rows, maximum_relative_error=maximum))
    except Exception:
        write(folder/'qualification.json', dict(status='FAILED', rows=rows, traceback=traceback.format_exc()))
        raise
    with tarfile.open(folder/'sources.tar.gz', 'w:gz') as archive:
        for path in sources():
            archive.add(path, arcname=str(path.relative_to(c.ROOT)), recursive=False)
    plans = {}
    for arm in ('control', 'revised'):
        physics = c._physics('modal_muller', execution())
        plans[arm] = policy(arm).plan(c.problem(CASES[0]), physics)
    write(folder/'plans.json', plans)
    manifest = dict(experiment=ID, cases=CASES, source_hashes=before,
        source_archive_sha256=digest(folder/'sources.tar.gz'), qualification_sha256=digest(folder/'qualification.json'),
        plans_sha256=digest(folder/'plans.json'), input_manifest_sha256=digest(c.INPUTS/'manifest.json'),
        plan_sha256=digest(PLAN), commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        branch=subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
        environment=ci.environment(), policy={arm: asdict(policy(arm)) for arm in ('control', 'revised')},
        execution=asdict(execution()), workers=1, blas_threads=1)
    write(folder/'manifest.json', manifest)
    print('Prepared', ID, 'maximum derivative error', maximum, flush=True)


def verify():
    c.verify(require_inputs=True)
    folder = OUTPUT/'preparation'
    saved = read(folder/'manifest.json')
    if saved['source_hashes'] != hashes() or saved['input_manifest_sha256'] != digest(c.INPUTS/'manifest.json'):
        raise ValueError('Prepared sources or TG-002 inputs changed')
    for name, key in (('sources.tar.gz', 'source_archive_sha256'),
                      ('qualification.json', 'qualification_sha256'), ('plans.json', 'plans_sha256')):
        if digest(folder/name) != saved[key]:
            raise ValueError('Preparation evidence changed: '+name)
    if read(folder/'qualification.json')['status'] != 'PASSED':
        raise ValueError('Qualification did not pass')
    return saved


def run_case(arm, case):
    folder = OUTPUT/arm/'runs'/case
    folder.mkdir(parents=True, exist_ok=False)
    row, started = c.row(case), perf_counter()
    try:
        result = fit(ci.fitting_problem(row, c.INPUTS), solver='modal_muller', execution=execution(),
            physics=c._physics('modal_muller', execution()), policy=policy(arm), output=folder,
            geometry_update='certified_spectral', localization_adapter=c.keep_start,
            on_event=lambda e: print(case, arm, e['operation']['label'], e['reason'], flush=True))
        returned = perf_counter()
        metrics = ci.score(row, curve_from(result['final_curve']))
        residual, limits = result.get('relative_residual'), ci.residual_limits(row)
        result.update(metrics=metrics, residual_limits=limits,
            recovered=bool(result['final_audit_passed'] and metrics['rms_mm'] <= 1. and
                metrics['hausdorff_upper_mm'] <= 2. and residual is not None and np.all(residual <= limits)),
            maximum_residual=None if residual is None else float(max(residual)),
            audited_output_seconds=returned-started, scoring_seconds=perf_counter()-returned)
    except Exception:
        result = dict(outcome='WORKER_EXCEPTION', recovered=False, traceback=traceback.format_exc())
    result.update(case=row, arm=arm, policy_settings=asdict(policy(arm)), execution=asdict(execution()),
                  case_seconds=perf_counter()-started)
    write(folder/'result.json', result)
    print('RESULT', case, arm, result['outcome'], result['recovered'], flush=True)


def report():
    rows, regressions, new, speedups = [], [], [], []
    for case in CASES:
        paired = {}
        for arm in ('control', 'revised'):
            path = OUTPUT/arm/'runs'/case/'result.json'
            if not path.exists():
                continue
            result = read(path)
            stages = result.get('stages', [])
            decisions = result.get('decisions', [])
            entered = [d['operation']['label'] for d in decisions if d['reason'] == 'resolved stage entered']
            # RequiredAccuracyReached can interrupt before the stage-return receipt.
            paired[arm] = dict(recovered=result['recovered'], outcome=result['outcome'],
                metrics=result.get('metrics'), maximum_residual=result.get('maximum_residual'),
                audited_output_seconds=result.get('audited_output_seconds'),
                audit=result.get('final_audit_passed'), detail=result.get('detail'),
                last_stage=entered[-1] if entered else None,
                shape_stages_entered=[s for s in entered if s.startswith(('shape_', 'full_release_'))],
                initial_stage=stages[0] if stages else None,
                result=str(path.relative_to(c.ROOT)))
        rows.append(dict(case=case, **paired))
        if len(paired) == 2:
            a, b = paired['control'], paired['revised']
            if a['recovered'] and not b['recovered']:
                regressions.append(case)
            if b['recovered'] and not a['recovered']:
                new.append(case)
            if a['recovered'] and b['recovered']:
                speedups.append(a['audited_output_seconds']/b['audited_output_seconds'])
    value = dict(experiment=ID, rows=rows, completed={arm: sum(arm in r for r in rows) for arm in ('control', 'revised')},
        recovered={arm: sum(r.get(arm, {}).get('recovered', False) for r in rows) for arm in ('control', 'revised')},
        recovery_regressions=regressions, new_recoveries=new,
        median_paired_success_speedup=float(np.median(speedups)) if speedups else None)
    write(OUTPUT/'report.json', value)
    return value


def run(approved_id):
    if approved_id != ID or not read(OUTPUT/'authorization.json').get('authorized'):
        raise ValueError('Explicit CS-001 approval must be recorded before fitting')
    if read(OUTPUT/'authorization.json').get('experiment_id') != ID:
        raise ValueError('Wrong experiment authorization')
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute, (COORD/'source.lock').open('a') as source:
        fcntl.flock(compute, fcntl.LOCK_EX)
        fcntl.flock(source, fcntl.LOCK_SH)
        preparation = verify()
        if (OUTPUT/'run_manifest.json').exists():
            raise ValueError('Preserve previous measured runs; this screen cannot be rerun')
        write(OUTPUT/'run_manifest.json', dict(experiment=ID, approval_id=approved_id,
            authorization_sha256=digest(OUTPUT/'authorization.json'), cases=CASES,
            preparation_sha256=digest(OUTPUT/'preparation/manifest.json'),
            order='control then revised for each case', fresh_interpreter=True))
        env = dict(os.environ, PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}',
                   OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', CS001_WORKER='1')
        for case in CASES:
            for arm in ('control', 'revised'):
                started = perf_counter()
                completed = subprocess.run([sys.executable, '-m', 'experiments.benchmark.cs001', 'case',
                    '--arm', arm, '--case', case], cwd=c.ROOT, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                folder = OUTPUT/arm/'runs'/case
                folder.mkdir(parents=True, exist_ok=True)
                (folder/'stdout.log').write_text(completed.stdout)
                if not (folder/'result.json').exists():
                    write(folder/'result.json', dict(case=c.row(case), arm=arm, recovered=False,
                        outcome='PROCESS_FAILED', returncode=completed.returncode, case_seconds=perf_counter()-started))
                result = read(folder/'result.json')
                result['process_seconds'] = perf_counter()-started
                result['process_returncode'] = completed.returncode
                write(folder/'result.json', result)
                print(case, arm, result['outcome'], result['recovered'], flush=True)
                report()
        passed = verify() == preparation
        write(OUTPUT/'source_check.json', dict(passed=passed))
        if not passed:
            raise ValueError('Sources changed during measured runs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'verify', 'run', 'case', 'report'))
    parser.add_argument('--approved-id')
    parser.add_argument('--arm', choices=('control', 'revised'))
    parser.add_argument('--case', choices=CASES)
    args = parser.parse_args()
    if args.command == 'run':
        run(args.approved_id)
    elif args.command == 'case':
        if os.environ.get('CS001_WORKER') != '1' or args.case is None or args.arm is None:
            parser.error('case is an internal fresh-interpreter worker')
        run_case(args.arm, args.case)
    else:
        value = {'prepare': prepare, 'verify': verify, 'report': report}[args.command]()
        if args.command != 'prepare':
            print(ID, args.command, 'passed' if args.command == 'verify' else value['recovered'], flush=True)


if __name__ == '__main__':
    main()
