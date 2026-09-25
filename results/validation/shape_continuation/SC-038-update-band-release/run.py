"""SC-038: a fixed three-stage update-band release on the full catalog."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import time
import traceback

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.finite_path_study import frozen_sources, geometric_score
from experiments.shape_continuation.lm_backend import Ledger, Objective, Stop, relative_columns, stage_record

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'SC-035-state-band'
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_19/03_plan.md'
sys.path.insert(0, str(BASE))
from state_update import ProjectedUpdate, resize
spec = importlib.util.spec_from_file_location('sc035_driver', BASE / 'run.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
CASES = ('circle_to_c', 'kite')
ARMS = ('fixed_m9', 'release_m')


def hashes():
    shared = sc.read(HERE.parent / 'SC-036-logs/shared_environment.json')['numerical_dependencies']
    paths = [sc.ROOT / p for p in shared]
    paths += [BASE / 'state_update.py', BASE / 'run.py', Path(__file__).resolve(), PLAN]
    return dict(frozen_sources(), **{str(p.relative_to(sc.ROOT)): sc.digest(p) for p in paths})


def prefix(case):
    folder = BASE / 'runs' / case / 'low'
    history = sc.read(folder / 'stage_4_history.json')['history']
    record = sc.read(folder / 'continue.json')
    stage = next(r for r in record['stages'] if r['stage'] == 'stage_4')
    return ast.curve_from(history[-1]['coefficients']), stage['work']


def schedules(case, arm):
    catalog = ast.catalog_only(case)
    previous, config = ast.schedules(catalog, 'baseline')
    bands = [ac.BAND_RULES['borges'](catalog[ac.CATALOG_HZ.index(f)].wavenumber,
             catalog[ac.CATALOG_HZ.index(f)].wavenumber * np.sqrt(ac.contrast()))
             for f in (1.5e9, 2e9, 2.5e9)]
    assert bands == [11, 15, 19], bands
    if arm == 'fixed_m9':
        bands = [9, 9, 9]
    stages = [replace(previous[-1], label=f'release_{i}', observations=tuple(catalog),
              weights=tuple(np.ones(len(catalog)) / len(catalog)),
              discrepancy_tolerances=tuple(1e-5 if f <= .5e9 else 1e-7 for f in ac.CATALOG_HZ),
              update_modes=m, curve_modes=192, quota=1500)
              for i, m in enumerate(bands, 1)]
    return stages, config, catalog


def audit(case, arm=None):
    if arm is None:
        curve = resize(prefix(case)[0], 192)
        stages, config, _ = schedules(case, 'release_m')
    else:
        saved = sc.read(HERE / 'runs' / case / arm / 'result.json')
        curve = ast.curve_from(saved['curve'])
        stages, config, _ = schedules(case, arm)
        stages = stages[:len(saved['stages'])] or stages[:1]
    stage = stages[-1]
    ledger = Ledger(cap=130, seconds=600, endpoint_reserve=0)
    update = ProjectedUpdate(sc.LENGTH)
    space = update.prepare(curve, stage.update_modes, 192)
    coarse = Objective(stage, ac.contrast(), config, ledger)
    fine = Objective(replace(stage, nodes=1024, refined_nodes=2048), ac.contrast(), config, ledger)
    a = coarse.production(curve, 'audit_refinement')
    b = fine.production(curve, 'audit_refinement')
    ja = coarse.jacobian(a, update, space)
    jb = fine.jacobian(b, update, space)
    fields = relative_columns(a.prediction, b.prediction)
    relative = np.linalg.norm(ja - jb, axis=0) / np.maximum(np.linalg.norm(jb, axis=0), 1e-30)
    direction = np.random.default_rng(38019).normal(size=jb.shape[1])
    direction /= np.linalg.norm(direction)
    difference, refusal = None, None
    try:
        plus, minus = [fine.production(update.trial(space, s * 1e-7 * direction)[0], 'audit_fd').residual
                       for s in (1, -1)]
        fd = (plus - minus) / 2e-7
        difference = float(np.linalg.norm(fd - jb @ direction) / np.linalg.norm(fd))
    except ValueError as exc:
        refusal = str(exc)
    row = dict(case=case, arm=arm, M=stage.update_modes, K=192,
               field_refinement_relative=fields, jacobian_refinement_relative=relative,
               full_trial_fd_relative=difference, fd_refusal=refusal, work=ledger.snapshot(),
               passed=bool(np.all(fields <= stage.discrepancy_tolerances) and max(relative) <= 1e-3
                           and difference is not None and difference <= 1e-3))
    print('AUDIT', case, arm, row['passed'], 'field', max(fields), 'J', max(relative), 'FD', difference, flush=True)
    return row


def worker(job):
    case, arm = job
    folder = HERE / 'runs' / case / arm
    folder.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(cap=4500, seconds=1800)
    try:
        before = hashes()
        curve, prefix_work = prefix(case)
        stages, config, catalog = schedules(case, arm)
        update = ProjectedUpdate(sc.LENGTH)
        sc.write(folder / 'configuration.json', dict(case=case, arm=arm,
                 stages=[stage_record(s) for s in stages], frequencies_hz=ac.CATALOG_HZ,
                 backend=asdict(config), update=update.settings(), initial=ast.curve_record(curve),
                 prefix_work=prefix_work, new_inverse_cap=4500, new_inverse_seconds=1800))
        started = time.perf_counter()
        try:
            curve, rows, status, reason = old.run_stages(curve, stages, update, config, ledger, folder)
        except Stop as exc:
            checkpoint = folder / 'checkpoint.json'
            saved = sc.read(checkpoint) if checkpoint.exists() else None
            if saved:
                curve, rows = ast.curve_from(saved['curve']), saved['stages']
            else:
                curve, rows = resize(curve, 192), []
            status, reason = 'HARD_STOP', exc.code
        elapsed = time.perf_counter() - started
        # Truth enters only after the inverse returns; no state selection uses it.
        result = dict(case=case, arm=arm, curve=ast.curve_record(curve), stages=rows,
                      status=status, reason=reason, work=ledger.snapshot(), seconds=elapsed,
                      prefix_units=prefix_work['work_units'],
                      complete_path_units=prefix_work['work_units'] + ledger.units,
                      geometry_work=update.counts, score=ast.score(case, curve, catalog))
        assert hashes() == before, 'frozen numerical source changed'
        sc.write(folder / 'result.json', result)
        print('DONE', case, arm, status, result['score']['symmetric_rms_mm'], ledger.units, flush=True)
        return {k: result[k] for k in ('case', 'arm', 'status', 'reason', 'score', 'work', 'prefix_units', 'complete_path_units')}
    except Exception:
        failure = dict(case=case, arm=arm, status='EXCEPTION', traceback=traceback.format_exc(), work=ledger.snapshot())
        sc.write(folder / 'failure.json', failure)
        print(failure, flush=True)
        return failure


def main():
    (HERE / 'runs').mkdir(exist_ok=False)
    inputs = [p for c in CASES for p in
              (BASE / 'runs' / c / 'low/stage_4_history.json', BASE / 'runs' / c / 'low/continue.json',
               ast.source_folder(c) / 'observations.json', ast.source_folder(c) / 'truth.json')]
    sources = hashes()
    sc.write(HERE / 'manifest.json', dict(experiment='SC-038', sources=sources,
             inputs={str(p.relative_to(sc.ROOT)): sc.digest(p) for p in inputs},
             parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
             command=sys.argv, workers=4, threads={k: os.environ.get(k) for k in
             ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
             cases=CASES, arms=ARMS, frequencies_hz=ac.CATALOG_HZ,
             new_inverse_cap=18000, audit_cap=800, final_evaluation_fields=76))
    with ProcessPoolExecutor(max_workers=2) as pool:
        qualified = list(pool.map(audit, CASES))
    passed = all(r['passed'] for r in qualified)
    sc.write(HERE / 'qualification.json', dict(rows=qualified, passed=passed))
    if not passed:
        sc.write(HERE / 'completion.json', dict(status='QUALIFICATION_FAILED'))
        return
    rows = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(worker, (c, a)) for c in CASES for a in ARMS]
        for future in as_completed(futures):
            rows.append(future.result())
            sc.write(HERE / 'summary.json', dict(rows=rows))
    audits = []
    if all(r['status'] != 'EXCEPTION' for r in rows):
        with ProcessPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(audit, c, a) for c in CASES for a in ARMS]
            for future in as_completed(futures):
                audits.append(future.result())
                sc.write(HERE / 'final_audit.json', dict(rows=audits, passed=all(r['passed'] for r in audits)))
    assert hashes() == sources
    assert all(sc.digest(sc.ROOT / p) == h for p, h in sc.read(HERE / 'manifest.json')['inputs'].items())
    sc.write(HERE / 'completion.json', dict(status='COMPLETE' if len(audits) == 4 else 'FAILED',
             audits_passed=len(audits) == 4 and all(r['passed'] for r in audits), sources_unchanged=True,
             new_inverse_units=sum(r['work']['work_units'] for r in rows),
             audit_units=sum(r['work']['work_units'] for r in qualified + audits)))


if __name__ == '__main__':
    main()
