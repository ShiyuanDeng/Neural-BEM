"""Replay archived SC-047 strategy runs and SC-048 arms, then compare with the archive.

Each archived `fit` runs unchanged from its stored inputs into a fresh folder.
Scores use the archived truth after the optimizer returns, exactly as the
original drivers did. The environment is recorded when the replay starts.

    run      OUT [--studies sc047 sc048] [--workers 6]
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

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
RESULTS = ROOT / 'results/validation/shape_continuation'
SC047 = RESULTS / 'SC-047-coupled-continuation'
SC048 = RESULTS / 'SC-048-global-motion-directions'
TIMING = {'seconds', 'preparation_seconds', 'trial_seconds'}
FILES = ('unscored.json', 'result.json', 'checkpoint.json')


def jobs(studies):
    rows = []
    if 'sc047' in studies:
        for sep in (.14, .20):
            for noisy in (False, True):
                for arm in ('joint', 'round_robin', 'conditional'):
                    rows.append(('sc047', f"sep{sep:.2f}_{'noise' if noisy else 'clean'}", arm))
    if 'sc048' in studies:
        rows += [('sc048', 'sep0.14_clean', arm) for arm in ('normal_m5', 'normal_m9', 'global_m5')]
    return rows


def archive(study, case, arm):
    return (SC047 if study == 'sc047' else SC048) / 'runs' / case / arm


def load(path, name):
    sys.path[:0] = [str(ROOT), str(ROOT / 'solvers'), str(SC047)]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job(args):
    out, study, case, arm = args
    folder = Path(out) / 'runs' / study / case / arm
    strategies = load(SC047 / 'strategies.py', 'sc047_strategies')
    q = strategies  # qualify helpers are re-exported through strategies' imports
    catalog, contrast, _ = strategies.setup()
    Observation = strategies.Observation
    if study == 'sc047':
        sep = float(case[3:7])
        inputs = json.loads((SC047 / 'inputs' / f'separation_{sep:.2f}' / 'input.json').read_text())
        data = np.array(inputs['clean_real']) + 1j * np.array(inputs['clean_imag'])
        if case.endswith('noise'):
            data = data + np.array(inputs['noise_real']) + 1j * np.array(inputs['noise_imag'])
        fit, score = strategies.fit, strategies.score
    else:
        run = load(SC048 / 'run.py', 'sc048_run')
        inputs = json.loads((SC048 / 'inputs' / f'{case}.json').read_text())
        data = np.array(inputs['observed_real']) + 1j * np.array(inputs['observed_imag'])
        fit, score = run.fit, run.score
    initial, truth = q.load_scene(inputs['initial']), q.load_scene(inputs['truth'])
    observations = tuple(Observation(o.wavenumber, o.acquisition, data[:, j]) for j, o in enumerate(catalog))
    started = time.perf_counter()
    endpoint, row = fit(initial, observations, contrast, arm, folder)
    wall = time.perf_counter() - started
    row.update(case=case, initial_score=score(initial, truth), score=score(endpoint, truth))
    q.write(folder / 'result.json', row)
    return dict(study=study, case=case, arm=arm, wall_seconds=wall, outcome=row['outcome'])


def environment():
    keys = ('SC_FREQUENCY_THREADS', 'SC_FORWARD_BACKEND', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
            'MKL_NUM_THREADS', 'CUDA_VISIBLE_DEVICES')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True)
    return dict(env={k: os.environ.get(k) for k in keys}, commit=commit, dirty_tracked_files=dirty.split('\n')[:-1],
                python=sys.version, host=platform.node(), cpus=os.cpu_count())


def run(out, studies, workers):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    record = dict(studies=studies, workers=workers, environment=environment(), started=time.time())
    (out / 'replay.json').write_text(json.dumps(record, indent=1))
    load_samples, stop = [], threading.Event()

    def sample():
        while not stop.is_set():
            load_samples.append(dict(t=time.time(), loadavg=os.getloadavg()))
            stop.wait(30)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(job, [(str(out), *j) for j in jobs(studies)]))
    stop.set()
    sampler.join()
    record.update(wall_seconds=time.time() - record['started'], host_load=load_samples, jobs=rows)
    (out / 'replay.json').write_text(json.dumps(record, indent=1))


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
            report['numeric_differences'] += 1
            report['max_relative'] = max(report['max_relative'], abs(a - b) / max(abs(a), abs(b), 1e-300))
            if len(report['differences']) < 20:
                report['differences'].append(dict(path=path, kind='number', archive=a, replay=b))


def signature(unscored):
    return [{k: r.get(k) for k in ('dispatch', 'outcome', 'stop', 'accepted', 'units', 'active', 'modes')}
            for r in unscored['records']]


def compare(out):
    out = Path(out)
    replay = json.loads((out / 'replay.json').read_text())
    seconds = {(j['study'], j['case'], j['arm']): j['wall_seconds'] for j in replay.get('jobs', [])}
    rows = []
    for study, case, arm in jobs(replay['studies']):
        old, new = archive(study, case, arm), out / 'runs' / study / case / arm
        files = {}
        for name in FILES:
            report = dict(leaves=0, numeric_differences=0, max_relative=0.0, differences=[])
            compare_values(json.loads((old / name).read_text()), json.loads((new / name).read_text()), name, report)
            report['identical'] = not report['differences']
            files[name] = report
        a, b = (json.loads((p / 'result.json').read_text()) for p in (old, new))
        rms = abs(b['score']['worst_rms_mm'] - a['score']['worst_rms_mm']) / a['score']['worst_rms_mm']
        row = dict(study=study, case=case, arm=arm, bit_identical=all(f['identical'] for f in files.values()),
            outcome=(a['outcome'], b['outcome']), dispatches_equal=signature(a) == signature(b),
            work_units=(a['work']['work_units'], b['work']['work_units']),
            worst_rms_mm=(a['score']['worst_rms_mm'], b['score']['worst_rms_mm']), rms_relative=rms,
            audit_passed=(a['audit'].get('passed'), b['audit'].get('passed')),
            archive_seconds=a['work']['seconds'], replay_seconds=seconds.get((study, case, arm)),
            files={k: {x: v[x] for x in ('leaves', 'numeric_differences', 'max_relative', 'identical')}
                   for k, v in files.items()},
            first_differences={k: v['differences'][:3] for k, v in files.items() if v['differences']})
        row['trajectory_gate'] = bool(row['outcome'][0] == row['outcome'][1] and row['dispatches_equal']
                                      and row['work_units'][0] == row['work_units'][1] and rms <= 1e-6
                                      and row['audit_passed'][1] is True)
        rows.append(row)
        print(study, case, arm, 'BIT-IDENTICAL' if row['bit_identical'] else 'differs',
              'gate', 'PASS' if row['trajectory_gate'] else 'FAIL',
              f"{row['archive_seconds']:.1f} -> {row['replay_seconds'] or float('nan'):.1f} s",
              'rms rel %.1e' % rms, 'units', row['work_units'], flush=True)
    summary = dict(all_bit_identical=all(r['bit_identical'] for r in rows),
                   all_trajectory_gates=all(r['trajectory_gate'] for r in rows),
                   environment=replay['environment'], wall_seconds=replay.get('wall_seconds'),
                   host_load=replay.get('host_load'), workers=replay['workers'], rows=rows)
    (out / 'comparison.json').write_text(json.dumps(summary, indent=1))
    print('ALL BIT-IDENTICAL' if summary['all_bit_identical'] else 'NOT ALL BIT-IDENTICAL',
          '| TRAJECTORY GATES', 'PASS' if summary['all_trajectory_gates'] else 'FAIL')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('run', 'compare'))
    parser.add_argument('out')
    parser.add_argument('--studies', nargs='+', default=['sc047', 'sc048'], choices=('sc047', 'sc048'))
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    if args.mode == 'run':
        run(args.out, args.studies, args.workers)
    compare(args.out)


if __name__ == '__main__':
    main()
