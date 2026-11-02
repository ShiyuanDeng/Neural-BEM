"""Bounded GGB-002 tuning, 30-case run, report and per-run Git preservation."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np

from experiments.benchmark.scenes import CASES
from .__main__ import _write, save_gaugal_fit
from . import tg002_data as D

REPO = Path(__file__).resolve().parents[2]
OUT = REPO/'results/validation/cleaned_interfaces/GGB-002'
REPORT = REPO/'docs/iterations/gaugal_comparison/iteration_01'
ENV = dict(os.environ, PYTHONPATH='solvers:.:/home/drdeng/Gau-Gal/src',
           OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
           MPLCONFIGDIR='/tmp/ggb002-mpl')
CIRCLES = ('circle__c0.5', 'circle__c4', 'circle__c13.3')
TUNING_STEPS = (1, .01, .05)


def status(phase, **details):
    payload = dict(phase=phase, updated=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                   pid=os.getpid(), **details)
    _write(OUT/'status.json', payload)
    print(json.dumps(payload), flush=True)


def preserve(message, report=False):
    paths = [str(OUT.relative_to(REPO))]
    if report:
        paths += [str(REPORT.relative_to(REPO)), 'experiments/gaugal_comparison']
    subprocess.run(['git', 'add', '--', *paths], cwd=REPO, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=REPO).returncode:
        subprocess.run(['git', 'commit', '-m', message], cwd=REPO, check=True,
                       stdout=subprocess.DEVNULL)
    for attempt in range(3):
        result = subprocess.run(['git', 'push'], cwd=REPO, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        print(result.stdout.strip(), flush=True)
        if result.returncode == 0:
            return
        time.sleep(10)
    print('Push pending after three attempts; local commit preserved.', flush=True)


def recover_partial(case, folder, reason):
    meta = folder/f'{case}.progress.json'
    arrays = folder/f'{case}.progress.npz'
    if meta.exists() and arrays.exists():
        fit = json.loads(meta.read_text())
        with np.load(arrays) as data:
            fit.update({key: data[key] for key in data.files})
        fit['stop_reason'] = reason
        try:
            return save_gaugal_fit(D.load(case), fit, folder, failure=reason)
        except Exception:
            reason += '\nPartial scoring failed:\n'+traceback.format_exc()
    row = dict(case=case, status='failed', stop_reason=reason, failure=reason,
               iterations=0, settings=None)
    _write(folder/f'{case}.json', row)
    return row


def run_one(case, folder, step, iterations, seconds, outer_seconds):
    target = folder/f'{case}.json'
    if target.exists():
        return json.loads(target.read_text())
    folder.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-u', '-m', 'experiments.gaugal_comparison', 'ggb-run',
        '--cases', case, '--grid', '51', '--sigma-scale', '.7', '--lambda-scale', '.5',
        '--step-size', str(step), '--contrast-max', '15', '--num-iter', str(iterations),
        '--max-seconds', str(seconds), '--frequencies', '19', '--out', str(folder)]
    status('running', case=case, folder=str(folder.relative_to(REPO)), step=step,
           iterations=iterations, outer_seconds=outer_seconds)
    start = time.perf_counter()
    with (folder/f'{case}.log').open('w') as log:
        try:
            code = subprocess.run(command, cwd=REPO, env=ENV, stdout=log,
                                  stderr=subprocess.STDOUT, timeout=outer_seconds).returncode
        except subprocess.TimeoutExpired:
            code = 124
    elapsed = time.perf_counter()-start
    if target.exists():
        row = json.loads(target.read_text())
    else:
        reason = 'outer_time_limit' if code == 124 else f'process_exit_{code}'
        row = recover_partial(case, folder, reason)
    row.update(process_returncode=code, wall_seconds=elapsed, outer_limit_seconds=outer_seconds)
    _write(target, row)
    preserve(f'experiment(GGB-002): {folder.name} {case} {row["status"]}')
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    _write(OUT/'overnight_manifest.json', dict(started=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
        target='2026-11-02 08:00 Europe/London', cases=list(CASES),
        tuning_steps=list(TUNING_STEPS), tuning_iterations=30, final_iterations=80,
        tuning_seconds=170, final_seconds=400, tuning_outer_seconds=210,
        final_outer_seconds=480, grid=51, sigma_scale=.7, lambda_scale=.5,
        frequencies=19, contrast_max=15, inner_iteration_cap=100,
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()))
    table = []
    for step in TUNING_STEPS:
        folder = OUT/'G1_tuning'/f'step{step}'
        rows = [run_one(case, folder, step, 30, 170, 210) for case in CIRCLES]
        values = [r.get('image', {}).get('rrmse', float('nan')) for r in rows]
        finite = [v for v in values if math.isfinite(v)]
        table.append(dict(step=step, finite_cases=len(finite),
            mean_rrmse=float(np.mean(finite)) if finite else float('inf'),
            rows=[dict(case=r['case'], status=r['status'], iterations=r['iterations'],
                       rrmse=v) for r, v in zip(rows, values)]))
    chosen = min(table, key=lambda r: (-r['finite_cases'], r['mean_rrmse']))
    _write(OUT/'G1_tuning/tuning.json', dict(table=table, chosen=chosen,
        rule='lowest mean circle image RRMSE; most finite circles first if incomplete'))
    preserve('experiment(GGB-002): freeze circle-selected shared setting')
    status('frozen', chosen=chosen)
    for case in CASES:
        run_one(case, OUT/'G2_all', chosen['step'], 80, 400, 480)
    status('reporting', attempted=30)
    subprocess.run([sys.executable, '-m', 'experiments.gaugal_comparison.report'],
                   cwd=REPO, env=ENV, check=True, timeout=600)
    status('complete', attempted=30, report=str((REPORT/'report.md').relative_to(REPO)))
    preserve('report(GGB-002): all-30 BEM and GauGal comparison', report=True)
    print('Final Git status:', subprocess.check_output(['git', 'status', '--short'],
          cwd=REPO, text=True).strip() or 'clean', flush=True)
    print('Local/remote difference:', subprocess.check_output(
          ['git', 'rev-list', '--left-right', '--count', 'HEAD...@{upstream}'],
          cwd=REPO, text=True).strip(), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        status('stopped_with_error', error=traceback.format_exc())
        try:
            preserve('experiment(GGB-002): preserve runner failure')
        except Exception:
            traceback.print_exc()
        raise
