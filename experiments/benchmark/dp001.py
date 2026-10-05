"""DP-001: frozen ON-001 E versus CI-SPD feedback/reuse fixes on TG-002."""
import argparse
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback

import numpy as np
from bem_inverse.io import read, write, digest, curve_from, portable
from . import campaign as c, scenes as S
from experiments.cleaned_interface import benchmark as ci

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/DP-001'
BASELINE = '334699bd'
SCREEN = ('aphex_twin__c0.5', 'aphex_twin__c4', 'aphex_twin__c13.3', 'hook__c13.3',
          'circle__c4', 'c_shape__c13.3', 'kite__c0.5', 'star__c13.3', 'cog__c13.3')
COORD = Path('/tmp/neural-sdf-bem-ad-coordination')


def sources():
    return sorted({*c.ROOT.glob('solvers/**/*.py'), Path(__file__).resolve(),
        *(Path(__file__).parent/name for name in ('__init__.py', 'campaign.py', 'scenes.py')),
        c.ROOT/'experiments/cleaned_interface/benchmark.py'})


def hashes():
    return {str(p.relative_to(c.ROOT)): digest(p) for p in sources()}


def prepare():
    """Archive sources and verify existing inputs; never perform a new solve."""
    c.verify(require_inputs=True)
    folder = OUTPUT/'preparation'
    folder.mkdir(parents=True, exist_ok=False)
    baseline = subprocess.check_output(['git', 'rev-parse', BASELINE], cwd=c.ROOT, text=True).strip()
    subprocess.run(['git', 'archive', '--format=tar.gz', f'--output={folder}/baseline.tar.gz',
                    baseline, 'solvers'], cwd=c.ROOT, check=True)
    with tarfile.open(folder/'candidate.tar.gz', 'w:gz') as archive:
        for p in sources():
            archive.add(p, arcname=str(p.relative_to(c.ROOT)), recursive=False)
    value = dict(experiment='DP-001', status='prepared; inverse runs require explicit ID approval',
        baseline_commit=baseline, candidate_hashes=hashes(),
        archives={name: digest(folder/name) for name in ('baseline.tar.gz', 'candidate.tar.gz')},
        inputs_manifest_sha256=digest(c.INPUTS/'manifest.json'),
        plan_sha256=digest(c.ROOT/'docs/iterations/CI-SPD/DP-001_plan.md'),
        branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=c.ROOT, text=True).strip(),
        environment=ci.environment(), workers=1, blas_threads=1, frequency_threads=4,
        screen=list(SCREEN), remaining=[k for k in S.CASES if k not in SCREEN])
    write(folder/'manifest.json', value)
    return value


def verify():
    c.verify(require_inputs=True)
    folder = OUTPUT/'preparation'
    value = read(folder/'manifest.json')
    for name, expected in value['archives'].items():
        if digest(folder/name) != expected:
            raise ValueError(f'Altered DP-001 source archive: {name}')
    if hashes() != value['candidate_hashes']:
        raise ValueError('Candidate sources differ from the preparation seal')
    if digest(c.INPUTS/'manifest.json') != value['inputs_manifest_sha256']:
        raise ValueError('TG-002 input manifest changed')
    if digest(c.ROOT/'docs/iterations/CI-SPD/DP-001_plan.md') != value['plan_sha256']:
        raise ValueError('DP-001 pre-registration changed')
    return value


def interpreter_env(arm):
    root = COORD/'DP-001-baseline'
    manifest = read(OUTPUT/'preparation/manifest.json')
    # Ordinary immutable source extraction, never a Git branch or worktree.
    if root.exists():
        for path, expected in read(root/'extracted_hashes.json').items():
            if digest(root/path) != expected:
                raise ValueError('Extracted baseline source changed')
        if read(root/'extracted_hashes.json')['baseline.tar.gz'] != manifest['archives']['baseline.tar.gz']:
            raise ValueError('Different baseline extraction exists')
    else:
        root.mkdir(parents=True)
        archive = OUTPUT/'preparation/baseline.tar.gz'
        with tarfile.open(archive) as saved:
            saved.extractall(root, filter='data')
        # Include the archive identity without copying a potentially large archive.
        (root/'baseline.tar.gz').symlink_to(archive)
        write(root/'extracted_hashes.json', {str(p.relative_to(root)): digest(p)
            for p in [*root.glob('solvers/**/*.py'), root/'baseline.tar.gz']})
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env['PYTHONPATH'] = f"{root/'solvers' if arm=='E' else c.ROOT/'solvers'}:{c.ROOT}"
    env['DP001_IMPORTED_ROOT'] = str(root/'solvers' if arm=='E' else c.ROOT/'solvers')
    return env


def run_case(arm, case, folder):
    import bem_inverse
    from bem_inverse.physics import Execution
    from bem_inverse.policy import CumulativePolicy
    from bem_inverse.runner import fit
    expected = Path(os.environ['DP001_IMPORTED_ROOT']).resolve()
    if not Path(bem_inverse.__file__).resolve().is_relative_to(expected):
        raise ValueError('Wrong numerical package imported')
    folder.mkdir(parents=True, exist_ok=False)
    settings = dict(required_accuracy=.003, fit_seconds=120., audit_seconds=30.,
                    audit_aggregate_seconds=30., log_model=True)
    execution_settings = dict(device='cuda', frequency_threads=4)
    if arm == 'F':
        settings.update(damping_rule='agreement', avoid_terminal_linearization=True)
        execution_settings['audit_frequency_batch'] = 2
    policy, execution = CumulativePolicy(**settings), Execution(**execution_settings)
    row, started = c.row(case), perf_counter()
    try:
        result = fit(ci.fitting_problem(row, c.INPUTS), solver='modal_muller', execution=execution,
            physics=c._physics('modal_muller', execution), policy=policy, output=folder,
            geometry_update='certified_spectral', localization_adapter=c.keep_start)
        returned = perf_counter()
        metrics = ci.score(row, curve_from(result['final_curve']))
        residual, limits = result.get('relative_residual'), ci.residual_limits(row)
        result.update(case=row, metrics=metrics, residual_limits=limits,
            recovered=bool(result['final_audit_passed'] and metrics['rms_mm'] <= 1. and
                metrics['hausdorff_upper_mm'] <= 2. and residual is not None and np.all(residual <= limits)),
            maximum_residual=None if residual is None else float(max(residual)),
            audited_output_seconds=returned-started, scoring_seconds=perf_counter()-returned)
    except Exception:
        result = dict(case=row, outcome='WORKER_EXCEPTION', recovered=False, traceback=traceback.format_exc())
    result.update(arm=arm, policy=asdict(policy), execution=asdict(execution),
        imported_solver=str(Path(bem_inverse.__file__).resolve()), case_seconds=perf_counter()-started)
    write(folder/'result.json', result)
    print('RESULT', case, arm, result['outcome'], result['recovered'], flush=True)
    return result


def rows(arm):
    result = {}
    for path in sorted(OUTPUT.glob(f'{arm}_*/runs/*/result.json')):
        r = read(path)
        case = r['case']['id']
        if case in result:
            raise ValueError(f'Duplicate measured case {arm}/{case}')
        trial_rows = [t for s in r.get('stages', [])
                      for t in read(path.parent/(s['stage']+'.json')).get('trials', [])]
        result[case] = dict(recovered=r['recovered'], outcome=r['outcome'],
            audited_output_seconds=r.get('audited_output_seconds'), case_seconds=r['case_seconds'],
            metrics=r.get('metrics'), maximum_residual=r.get('maximum_residual'),
            exclusive_wall_seconds=r.get('exclusive_wall_seconds'),
            physics=r.get('physics'), geometry=r.get('geometry_work'),
            geometry_proposals=sum(t.get('geometry_constructed', True) for t in trial_rows),
            trial_records=len(trial_rows),
            geometry_refusals=sum(t.get('reason') in ('self_intersection','irregular_parameterization',
                'unresolved_projection') for t in trial_rows),
            geometry_refusal_seconds=sum(t.get('geometry_seconds',0.) for t in trial_rows
                if t.get('reason') in ('self_intersection','irregular_parameterization','unresolved_projection')),
            shortened_accepts=sum(t.get('status')=='accepted' and t.get('accepted_fraction',1.)<=.25 for t in trial_rows),
            physics_failures=[f for s in r.get('stages', []) for f in s.get('physics_failures', [])],
            result=str(path.relative_to(c.ROOT)))
    return result


def report():
    e, f = rows('E'), rows('F')
    paired = [k for k in S.CASES if k in e and k in f]
    common = [k for k in paired if e[k]['recovered'] and f[k]['recovered']]
    speed = {k:e[k]['audited_output_seconds']/f[k]['audited_output_seconds'] for k in common}
    regression = [k for k in paired if e[k]['recovered'] and not f[k]['recovered']]
    screen_complete = all(k in paired for k in SCREEN)
    value = dict(experiment='DP-001', E=e, F=f, paired=paired, recovery_regressions=regression,
        new_recoveries=[k for k in paired if f[k]['recovered'] and not e[k]['recovered']],
        paired_success_speedups=speed, median_success_speedup=float(np.median(list(speed.values()))) if speed else None,
        screen_complete=screen_complete, remaining_allowed=screen_complete and not regression,
        summed_output_seconds={arm:sum(v['audited_output_seconds'] or v['case_seconds'] for v in data.values())
                              for arm,data in (('E',e),('F',f))})
    write(OUTPUT/'report.json', value)
    lines = ['# DP-001 measured evidence', '', 'Unrun cases remain unrun. Failures are retained.', '',
             '| Case | E recovery / output seconds | F recovery / output seconds |', '|---|---|---|']
    for case in S.CASES:
        cells=[]
        for data in (e,f):
            r=data.get(case)
            cells.append('unrun' if r is None else f"{r['recovered']} / {r['audited_output_seconds']}")
        lines.append('| '+case+' | '+' | '.join(cells)+' |')
    (OUTPUT/'table.md').write_text('\n'.join(lines)+'\n')
    return value


def run(arm, cohort, approved_id):
    if approved_id != 'DP-001':
        raise ValueError('Explicit DP-001 ID approval is required before inverse runs')
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute, (COORD/'source.lock').open('a') as source:
        requested = perf_counter()
        fcntl.flock(compute, fcntl.LOCK_EX)
        fcntl.flock(source, fcntl.LOCK_SH)
        wait = perf_counter()-requested
        preparation = verify()
        if cohort == 'remaining' and not report()['remaining_allowed']:
            raise ValueError('Remaining cases require both screens and no recovery regressions')
        cases = list(SCREEN) if cohort=='screen' else [k for k in S.CASES if k not in SCREEN]
        env = interpreter_env(arm)
        folder = OUTPUT/f'{arm}_{cohort}'
        folder.mkdir(parents=True, exist_ok=False)
        write(folder/'manifest.json', dict(experiment='DP-001', approval_id=approved_id, arm=arm,
            cohort=cohort, cases=cases, preparation_sha256=digest(OUTPUT/'preparation/manifest.json'),
            baseline_commit=preparation['baseline_commit'], compute_wait_seconds=wait,
            environment=ci.environment(), imported_source_root=env['DP001_IMPORTED_ROOT'],
            workers=1, blas_threads=1, warmup='none excluded; CUDA startup included'))
        for case in cases:
            dispatched = perf_counter()
            completed = subprocess.run([sys.executable, '-m', 'experiments.benchmark.dp001', 'case',
                '--arm', arm, '--cohort', cohort, '--case', case], cwd=c.ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            (folder/f'{case}.log').write_text(completed.stdout)
            result_path = folder/'runs'/case/'result.json'
            if completed.returncode != 0 and not result_path.exists():
                write(result_path, dict(case=c.row(case), arm=arm, recovered=False,
                    outcome='PROCESS_FAILED', returncode=completed.returncode,
                    audited_output_seconds=None, case_seconds=perf_counter()-dispatched))
            report()
        verified = verify() == preparation
        write(folder/'source_check.json', dict(passed=verified))
        if not verified:
            raise ValueError('Source/evidence seal changed during the measured batch')
        return report()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','verify','run','case','report'))
    parser.add_argument('--arm', choices=('E','F'), default='F')
    parser.add_argument('--cohort', choices=('screen','remaining'), default='screen')
    parser.add_argument('--case', choices=S.CASES)
    parser.add_argument('--approved-id')
    args=parser.parse_args()
    if args.command=='run':
        value=run(args.arm,args.cohort,args.approved_id)
    elif args.command=='case':
        if args.case is None or 'DP001_IMPORTED_ROOT' not in os.environ:
            parser.error('case is an internal fresh-interpreter worker')
        value=run_case(args.arm,args.case,OUTPUT/f'{args.arm}_{args.cohort}'/'runs'/args.case)
    else:
        value={'prepare':prepare,'verify':verify,'report':report}[args.command]()
    print(json.dumps(portable(value), indent=2))


if __name__=='__main__':
    main()
