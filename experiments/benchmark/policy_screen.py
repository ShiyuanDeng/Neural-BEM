"""PS-001: systematic TG-002 screen of the named continuation policies.

Every case runs under every screened policy in its own fresh interpreter, interleaved
case by case so that machine drift affects all policies alike, under the shared compute
lock. Receipts go to ``<root>/<policy>/runs/<case>/``; each policy directory holds one
setting (its manifest refuses mixed settings). The report attributes every case's time
to exclusive phases and compares each policy with its registry parent, including the
accepted-path identity that an exact policy must keep. Plan: ``docs/iterations/CI-SPD/PS-001_plan.md``.

    python -m experiments.benchmark.policy_screen prepare
    python -m experiments.benchmark.policy_screen run [--policies ...] [--cases ...]
    python -m experiments.benchmark.policy_screen report
"""
import argparse
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from time import perf_counter

from bem_inverse import policies as R
from bem_inverse.io import read, write, digest
from bem_inverse.physics import Execution
from experiments.cleaned_interface import benchmark as ci
from . import campaign as c, runtime_report as T, scenes as S

ID = 'PS-001'
OUTPUT = c.ROOT/'results/validation/cleaned_interfaces'/ID
PLAN = c.ROOT/'docs/iterations/CI-SPD/PS-001_plan.md'
SCREEN = ('baseline', 'accuracy_exit', 'feedback', 'decision_gate', 'four_phase', 'validity_first', 'entry_reuse',
          'exact_fast', 'compact_release', 'resolution_response', 'adaptive_resolution')
EXECUTION = Execution(device='cuda', frequency_threads=4)
COORD = Path('/tmp/neural-sdf-bem-ad-coordination')
SINGLE_THREAD = dict(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')


def sources():
    return sorted({*c.ROOT.glob('solvers/bem_inverse/**/*.py'), Path(__file__), *(Path(__file__).parent/name for name in
                   ('__init__.py', 'campaign.py', 'scenes.py', 'runtime_report.py')),
                   c.ROOT/'experiments/cleaned_interface/benchmark.py'})


def hashes():
    return {str(p.relative_to(c.ROOT)): digest(p) for p in sources()}


def settings(policy):
    return c.settings_for(localization='none', execution=EXECUTION, policy=policy)


def prepare(policies=SCREEN, cases=S.CASES):
    """Seal sources, per-policy settings and executable plans; no fits."""
    c.verify(require_inputs=True)
    folder = OUTPUT/'preparation'
    folder.mkdir(parents=True, exist_ok=False)
    with tarfile.open(folder/'sources.tar.gz', 'w:gz') as archive:
        for path in sources():
            archive.add(path, arcname=str(path.relative_to(c.ROOT)), recursive=False)
    plans = {}
    for name in policies:
        c.open_run(OUTPUT/name, cases, settings(name), experiment=ID)
        physics = c.physics_for(settings(name))
        plans[name] = R.build(name, **R.BENCHMARK_CONTRACT).plan(c.problem(cases[0]), physics)
    write(folder/'plans.json', plans)
    manifest = dict(experiment=ID, policies=list(policies), cases=list(cases), source_hashes=hashes(),
        source_archive_sha256=digest(folder/'sources.tar.gz'), plans_sha256=digest(folder/'plans.json'),
        plan_sha256=digest(PLAN) if PLAN.exists() else None, input_manifest_sha256=digest(c.INPUTS/'manifest.json'),
        registry={name: R.settings(name, R.BENCHMARK_CONTRACT) for name in policies},
        execution=dict(base=asdict(EXECUTION), workers=1, fresh_interpreter=True, **SINGLE_THREAD),
        order='for each case, every policy in registry order', environment=ci.environment(),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=c.ROOT, text=True).strip(),
        status=subprocess.check_output(['git', 'status', '--short'], cwd=c.ROOT, text=True))
    write(folder/'manifest.json', manifest)
    return manifest


def verify():
    c.verify(require_inputs=True)
    saved = read(OUTPUT/'preparation'/'manifest.json')
    if saved['source_hashes'] != hashes():
        changed = sorted(k for k in set(saved['source_hashes']) | set(hashes())
                         if saved['source_hashes'].get(k) != hashes().get(k))
        raise ValueError(f'Sources changed since preparation: {changed}')
    if saved['input_manifest_sha256'] != digest(c.INPUTS/'manifest.json'):
        raise ValueError('TG-002 inputs changed since preparation')
    return saved


def run_one(policy, case):
    """Internal fresh-interpreter worker for one (policy, case)."""
    if os.environ.get('PS001_WORKER') != '1':
        raise ValueError('case is an internal fresh-interpreter worker')
    return c.run_case((OUTPUT/policy, c.row(case), settings(policy)))


def run(policies=SCREEN, cases=S.CASES):
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute, (COORD/'source.lock').open('a') as source:
        fcntl.flock(compute, fcntl.LOCK_EX)
        fcntl.flock(source, fcntl.LOCK_SH)
        saved = verify()
        unknown = set(policies)-set(saved['policies']) or set(cases)-set(saved['cases'])
        if unknown:
            raise ValueError(f'Not prepared: {sorted(unknown)}')
        env = dict(os.environ, PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}', PS001_WORKER='1', **SINGLE_THREAD)
        for case in cases:
            for policy in policies:
                folder = OUTPUT/policy/'runs'/case
                if (folder/'result.json').exists():
                    continue
                if folder.exists():
                    raise FileExistsError(f'Incomplete run preserved at {folder}; resolve it before continuing')
                started = perf_counter()
                done = subprocess.run([sys.executable, '-m', 'experiments.benchmark.policy_screen', 'case',
                                       '--policy', policy, '--case', case], cwd=c.ROOT, env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                folder.mkdir(parents=True, exist_ok=True)
                (folder/'stdout.log').write_text(done.stdout)
                if not (folder/'result.json').exists():
                    write(folder/'result.json', dict(case=c.row(case), settings=settings(policy), recovered=False,
                          outcome='PROCESS_FAILED', returncode=done.returncode))
                result = read(folder/'result.json')
                result.update(process_seconds=perf_counter()-started, process_returncode=done.returncode)
                write(folder/'result.json', result)
                print(ID, case, policy, result.get('outcome'), result.get('recovered'),
                      f'{result.get("audited_output_seconds", float("nan")):.2f}s', flush=True)
        if verify() != saved:
            raise ValueError('Preparation record changed during the screen')
    return report()


def report(policies=None):
    """Attribution for every screened policy and each policy against its registry parent."""
    names = [n for n in (policies or read(OUTPUT/'preparation'/'manifest.json')['policies'])
             if (OUTPUT/n/'runs').exists()]
    pairs = [(OUTPUT/R.get(n).parent, OUTPUT/n) for n in names if R.get(n).parent in names]
    value, _ = T.report([OUTPUT/n for n in names], pairs, OUTPUT/'report')
    exact = {n: next(p for p in value['pairs'] if p['child'] == str(OUTPUT/n))
             for n in names if R.get(n).exact and R.get(n).parent in names}
    write(OUTPUT/'report'/'exactness.json', {n: dict(parent=R.get(n).parent, identical=p['identical_paths'],
                                                      common=p['common_cases']) for n, p in exact.items()})
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('prepare', 'verify', 'run', 'case', 'report'))
    parser.add_argument('--policies', nargs='+', choices=list(R.POLICIES))
    parser.add_argument('--policy', choices=list(R.POLICIES))
    parser.add_argument('--cases', nargs='+', choices=list(S.CASES))
    parser.add_argument('--case', choices=list(S.CASES))
    args = parser.parse_args()
    policies, cases = tuple(args.policies or SCREEN), tuple(args.cases or S.CASES)
    if args.command == 'prepare':
        print(ID, 'prepared', len(prepare(policies, cases)['policies']), 'policies', flush=True)
    elif args.command == 'verify':
        verify()
        print(ID, 'verified', flush=True)
    elif args.command == 'run':
        run(policies, cases)
    elif args.command == 'case':
        if args.policy is None or args.case is None:
            parser.error('case needs --policy and --case')
        run_one(args.policy, args.case)
    else:
        report(args.policies)


if __name__ == '__main__':
    main()
