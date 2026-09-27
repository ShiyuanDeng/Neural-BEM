"""Replay archived SC-043 inverse workers under a new execution setting, then compare.

The SC-043 worker runs unchanged against a fresh output folder. Only its
source-hash check is replaced, because the execution change under test is
itself a source change. Every frozen input hash is still verified, and the
source drift is recorded. Timing fields are excluded from the comparison;
everything else, including ledger snapshots, trials and audits, must match.

    run      OUT --cases peanut wrong_circle [--policy fixed] [--workers 2]
    compare  OUT
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[4]
ARCHIVE = ROOT / 'results/validation/shape_continuation/SC-043-prospective-band'
FILES = ('decisions.json', 'accepted.json', 'block_1.json', 'block_2.json', 'block_3.json',
         'checkpoint.json', 'audit.json', 'result.json', 'progress.json')
TIMING = {'seconds'}


def load_sc043(out):
    spec = importlib.util.spec_from_file_location('sc043_replay', ARCHIVE / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.c.sc.read(ARCHIVE / 'manifest.json')

    def verify():
        # Frozen inputs must match exactly; sources are allowed to drift and are recorded.
        assert all(module.c.sc.digest(module.c.sc.ROOT / p) == h for p, h in manifest['inputs'].items())

    module.HERE, module.verify = Path(out), verify
    return module, manifest


def environment():
    keys = ('SC_FREQUENCY_THREADS', 'SC_FORWARD_BACKEND', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
            'MKL_NUM_THREADS')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True)
    return dict(env={k: os.environ.get(k) for k in keys}, commit=commit, dirty_tracked_files=dirty.split('\n')[:-1],
                python=sys.version, host=platform.node(), cpus=os.cpu_count())


def job(args):
    out, case, policy = args
    module, _ = load_sc043(out)
    return module.worker((case, policy))


def run(out, cases, policy, workers):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    module, manifest = load_sc043(out)
    module.c.write(out / 'manifest.json', manifest)
    drift = sorted(p for p, h in module.sources().items() if manifest['sources'].get(p) != h)
    load, stop = [], threading.Event()

    def sample():
        while not stop.is_set():
            load.append(dict(t=time.time(), loadavg=os.getloadavg()))
            stop.wait(30)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.time()
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(job, [(str(out), case, policy) for case in cases]))
    stop.set()
    sampler.join()
    module.c.write(out / 'replay.json', dict(cases=cases, policy=policy, workers=workers, started=started,
        wall_seconds=time.time() - started, environment=environment(), source_drift=drift,
        host_load=load, outcomes={r['case']: r['outcome'] for r in rows}))


def compare_values(a, b, path, report):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) - TIMING != set(b) - TIMING:
            report['differences'].append(dict(path=path, kind='keys'))
            return
        for key in sorted(set(a) - TIMING):
            compare_values(a[key], b[key], f'{path}/{key}', report)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            report['differences'].append(dict(path=path, kind='length', archive=len(a), replay=len(b)))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            compare_values(x, y, f'{path}[{i}]', report)
    elif isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        report['leaves'] += 1
        if a != b:
            report['differences'].append(dict(path=path, kind='value', archive=a, replay=b))
    else:
        report['leaves'] += 1
        if a != b:
            deviation = abs(a - b) / max(abs(a), abs(b), 1e-300)
            report['numeric_differences'] += 1
            report['max_relative'] = max(report['max_relative'], deviation)
            if len(report['differences']) < 20:
                report['differences'].append(dict(path=path, kind='number', archive=a, replay=b,
                                                  relative=deviation))


def compare(out):
    out = Path(out)
    replay = json.loads((out / 'replay.json').read_text())
    cases = {}
    for case in replay['cases']:
        files = {}
        for name in FILES:
            archived = ARCHIVE / 'runs' / case / replay['policy'] / name
            fresh = out / 'runs' / case / replay['policy'] / name
            if not fresh.exists():
                files[name] = dict(missing=True, identical=False)
                continue
            report = dict(leaves=0, numeric_differences=0, max_relative=0.0, differences=[])
            compare_values(json.loads(archived.read_text()), json.loads(fresh.read_text()), name, report)
            report['identical'] = not report['differences']
            files[name] = report
        archived = json.loads((ARCHIVE / 'runs' / case / replay['policy'] / 'result.json').read_text())
        fresh_path = out / 'runs' / case / replay['policy'] / 'result.json'
        fresh = json.loads(fresh_path.read_text()) if fresh_path.exists() else {}
        cases[case] = dict(identical=all(f['identical'] for f in files.values()), files=files,
            archive_seconds=archived['seconds'], replay_seconds=fresh.get('seconds'),
            speedup=archived['seconds'] / fresh['seconds'] if fresh.get('seconds') else None,
            archive_rms_mm=archived['score'].get('rms_mm'), replay_rms_mm=fresh.get('score', {}).get('rms_mm'),
            total_units=(archived['total_units'], fresh.get('total_units')))
    summary = dict(all_identical=all(c['identical'] for c in cases.values()), cases=cases,
                   environment=replay['environment'], source_drift=replay['source_drift'])
    (out / 'comparison.json').write_text(json.dumps(summary, indent=1))
    for case, row in cases.items():
        print(case, 'IDENTICAL' if row['identical'] else 'DIFFERENT', f"{row['archive_seconds']:.1f} s ->",
              f"{row['replay_seconds']:.1f} s" if row['replay_seconds'] else 'n/a',
              f"({row['speedup']:.2f}x)" if row['speedup'] else '')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('run', 'compare'))
    parser.add_argument('out')
    parser.add_argument('--cases', nargs='+', default=['wrong_circle', 'peanut'])
    parser.add_argument('--policy', default='fixed')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.mode == 'run':
        run(args.out, args.cases, args.policy, args.workers)
    compare(args.out)


if __name__ == '__main__':
    main()
