"""SC-040: the current pipeline on all six development scenes.

Pipeline: SC-035's low state band (stages 1-4) then SC-038's update-band
release (all 19 frequencies, M 11/15/19, K=192). C and kite already have it.
This runs the missing parts with the settings of those two experiments:

- circle, hook: SC-035 low prefix (not run before), then the release;
- star, peanut: the release from SC-035's saved stage-4 state.

A release stage that hard-stops on the 512/1024 field gate is replayed once,
with the remaining stages, at 768/1536 nodes (SC-038's kite rule). Truth enters
only in scoring after a run returns. `collect` then stores SC-039-format data
for every new accepted state. Plan: docs/iterations/shape_frequency_continuation/
iteration_21/03_plan.md. Run from the repository root under EMNerf:

PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-040-six-scene-pipeline/run.py run
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-040-six-scene-pipeline/run.py collect
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import time
import traceback

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation import trajectory_atlas as ta
from experiments.shape_continuation.finite_path_study import geometric_score
from experiments.shape_continuation.lm_backend import (Ledger, NORMAL_RETURN, STAGE_QUOTA, Objective, Stop,
                                                       relative_columns, stage_record)

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
SC035, SC038 = RESULTS / 'SC-035-state-band', RESULTS / 'SC-038-update-band-release'
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_21/03_plan.md'
spec = importlib.util.spec_from_file_location('sc038_run', SC038 / 'run.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)          # also puts SC-035 on sys.path and loads its run.py as `old`
old, ProjectedUpdate = release.old, release.ProjectedUpdate
JOBS = (('wrong_circle', True), ('hook', True), ('circle_to_star', False), ('peanut', False))
DONE = ('COMPLETED_SCHEDULE',)


def hashes():
    return dict(release.hashes(), **{str(p.relative_to(sc.ROOT)): sc.digest(p) for p in (Path(__file__).resolve(), PLAN)})


def fit(curve, stages, update, config, ledger, folder):
    """run_stages with SC-038's handling of a Stop raised inside a stage."""
    try:
        return old.run_stages(curve, stages, update, config, ledger, folder)
    except Stop as exc:
        saved = folder / 'checkpoint.json'
        rows = sc.read(saved)['stages'] if saved.exists() else []
        return (ast.curve_from(sc.read(saved)['curve']) if saved.exists() else curve), rows, 'HARD_STOP', exc.code


def state_band(case):
    """SC-035 `low` worker settings: stage 1 (600 units, 900 s), then stages 2-4 (3,000 total, 2,700 s total)."""
    folder = HERE / 'runs' / case / 'state_band'
    folder.mkdir(parents=True, exist_ok=False)
    catalog = ast.catalog_only(case)
    stages, config = ast.schedules(catalog, 'baseline')
    stages = [replace(s, curve_modes=2 * s.update_modes + 2) for s in stages]
    update = ProjectedUpdate(sc.LENGTH)
    curve, _ = update.regauge(ac.start_curve(), stages[0].curve_modes)
    sc.write(folder / 'configuration.json', dict(case=case, arm='low', update=update.settings(), backend=asdict(config),
             stages=[stage_record(s) for s in stages], initial=ast.curve_record(curve)))
    ledger = Ledger(cap=600, seconds=900)
    started = time.perf_counter()
    curve, rows, status, reason = fit(curve, stages[:1], update, config, ledger, folder)
    pilot = time.perf_counter() - started
    work = ledger.snapshot()
    if status in DONE:
        ledger = Ledger(cap=3000, seconds=max(0, 2700 - pilot))
        ledger.units = work['work_units']
        ledger.solves, ledger.reciprocal = dict(work['solves']), dict(work['reciprocal_batches'])
        ledger.failed = dict(work['failed'])
        curve, more, status, reason = fit(curve, stages[1:], update, config, ledger, folder)
        rows += more
        work = ledger.snapshot()
    result = dict(case=case, arm='low', status=status, reason=reason, curve=ast.curve_record(curve), stages=rows,
                  work=work, seconds=time.perf_counter() - started, score=ast.score(case, curve, catalog))
    sc.write(folder / 'result.json', result)
    print('PREFIX', case, status, reason, result['score']['symmetric_rms_mm'], work['work_units'], flush=True)
    return curve, work['work_units'], status


def saved_prefix(case):
    curve, work = release.prefix(case)                       # SC-035 low, last stage-4 row
    return curve, work['work_units']


def release_run(case, curve, prefix_units, folder, stages, nodes=None, cap=4500):
    folder.mkdir(parents=True, exist_ok=False)
    _, config, catalog = release.schedules(case, 'release_m')
    if nodes:
        stages = [replace(s, nodes=nodes, refined_nodes=2 * nodes) for s in stages]
    update = ProjectedUpdate(sc.LENGTH)
    ledger = Ledger(cap=cap, seconds=1800)
    sc.write(folder / 'configuration.json', dict(case=case, arm='release_m', stages=[stage_record(s) for s in stages],
             frequencies_hz=ac.CATALOG_HZ, backend=asdict(config), update=update.settings(),
             initial=ast.curve_record(curve), prefix_units=prefix_units, new_inverse_cap=cap, new_inverse_seconds=1800))
    started = time.perf_counter()
    curve, rows, status, reason = fit(curve, stages, update, config, ledger, folder)
    result = dict(case=case, arm='release_m', curve=ast.curve_record(curve), stages=rows, status=status, reason=reason,
                  work=ledger.snapshot(), seconds=time.perf_counter() - started, prefix_units=prefix_units,
                  complete_path_units=prefix_units + ledger.units, geometry_work=update.counts,
                  score=ast.score(case, curve, catalog))
    sc.write(folder / 'result.json', result)
    print('RELEASE', case, folder.name, status, reason, result['score']['symmetric_rms_mm'], ledger.units, flush=True)
    return result, stages, config


def audit(curve, stage, config):
    """SC-038's endpoint audit at the stage's own M: 2x-node fields and Jacobian, full-trial FD."""
    ledger = Ledger(cap=130, seconds=600, endpoint_reserve=0)
    update = ProjectedUpdate(sc.LENGTH)
    space = update.prepare(curve, stage.update_modes, 192)
    coarse = Objective(stage, ac.contrast(), config, ledger)
    fine = Objective(replace(stage, nodes=2 * stage.nodes, refined_nodes=4 * stage.nodes), ac.contrast(), config, ledger)
    a, b = coarse.production(curve, 'audit_refinement'), fine.production(curve, 'audit_refinement')
    ja, jb = coarse.jacobian(a, update, space), fine.jacobian(b, update, space)
    fields = relative_columns(a.prediction, b.prediction)
    jacobian = np.linalg.norm(ja - jb, axis=0) / np.maximum(np.linalg.norm(jb, axis=0), 1e-30)
    direction = np.random.default_rng(40019).normal(size=jb.shape[1])
    direction /= np.linalg.norm(direction)
    difference, refusal = None, None
    try:
        plus, minus = [fine.production(update.trial(space, s * 1e-7 * direction)[0], 'audit_fd').residual for s in (1, -1)]
        fd = (plus - minus) / 2e-7
        difference = float(np.linalg.norm(fd - jb @ direction) / np.linalg.norm(fd))
    except ValueError as exc:
        refusal = str(exc)
    return dict(M=stage.update_modes, nodes=stage.nodes, field_refinement_relative=fields,
                jacobian_refinement_relative=jacobian, full_trial_fd_relative=difference, fd_refusal=refusal,
                work=ledger.snapshot(),
                passed=bool(np.all(fields <= stage.discrepancy_tolerances) and max(jacobian) <= 1e-3
                            and difference is not None and difference <= 1e-3))


def worker(job):
    case, needs_prefix = job
    try:
        before = hashes()
        if needs_prefix:
            curve, units, status = state_band(case)
            if status not in DONE:
                return dict(case=case, status='PREFIX_' + status)
        else:
            curve, units = saved_prefix(case)
        stages, _, _ = release.schedules(case, 'release_m')
        result, used, config = release_run(case, curve, units, HERE / 'runs' / case / 'release_m', stages)
        final = [('release_m', result, used)]
        if result['status'] == 'HARD_STOP' and result['reason'] == 'NUMERICAL_FAILURE':
            folder = HERE / 'runs' / case / 'release_m'
            completed = [r for r in result['stages'] if r['outcome'] in (NORMAL_RETURN, STAGE_QUOTA)]
            start = (ast.curve_from(sc.read(folder / f"{completed[-1]['stage']}_history.json")['history'][-1]['coefficients'])
                     if completed else curve)
            spent = sum(r['work']['work_units'] for r in completed) if completed else 0
            dense, used, config = release_run(case, start, units + spent, HERE / 'runs' / case / 'release_m_dense',
                                              stages[len(completed):], nodes=768, cap=max(1, 4500 - spent))
            final.append(('release_m_dense', dense, used))
        name, last, used = final[-1]
        checked = audit(ast.curve_from(last['curve']), used[min(len(last['stages']), len(used)) - 1], config)
        sc.write(HERE / 'runs' / case / 'audit.json', dict(folder=name, **checked))
        assert hashes() == before, 'frozen numerical source changed'
        print('AUDIT', case, name, checked['passed'], flush=True)
        return dict(case=case, status=last['status'], reason=last['reason'], folder=name,
                    score=last['score'], audit_passed=checked['passed'])
    except Exception:
        failure = dict(case=case, status='EXCEPTION', traceback=traceback.format_exc())
        (HERE / 'runs' / case).mkdir(parents=True, exist_ok=True)
        sc.write(HERE / 'runs' / case / 'failure.json', failure)
        print(failure, flush=True)
        return failure


def run():
    (HERE / 'runs').mkdir(exist_ok=False)
    sc.write(HERE / 'manifest.json', dict(experiment='SC-040', plan_sha256=sc.digest(PLAN), sources=hashes(),
             parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=sc.ROOT, text=True).strip(),
             command=sys.argv, jobs=JOBS, workers=len(JOBS),
             threads={k: os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}))
    rows = []
    with ProcessPoolExecutor(max_workers=len(JOBS)) as pool:
        for future in as_completed([pool.submit(worker, job) for job in JOBS]):
            rows.append(future.result())
            sc.write(HERE / 'summary.json', dict(rows=rows))


# ------------------------------------------------------------------ trajectories and data

def trajectories():
    """One trajectory per scene through the current pipeline, in SC-039's format."""
    existing = {t.id: t for t in ta.trajectories()}
    out = {case: existing[f'F_released_m/{case}'] for case in ('circle_to_c', 'kite')}
    for case, needs_prefix in JOBS:
        t = ta.Trajectory(f'SC040/{case}', 'SC-035 low state band, then SC-038 release', case)
        if needs_prefix:
            folder = HERE / 'runs' / case / 'state_band'
            ta.lm_run(t, folder, sc.read(folder / 'configuration.json')['stages'], 'result.json', 'curve')
        else:
            t.extend(ta.prefix(existing[f'B_state_band/{case}'], 'stage_4'))
        for name in ('release_m', 'release_m_dense'):
            folder = HERE / 'runs' / case / name
            if folder.exists():
                if name == 'release_m_dense':   # the replay restarts from the last completed stage
                    first = sc.read(folder / 'configuration.json')['stages'][0]['label']
                    t.steps = [s for s in t.steps if s.stage != first and s.iteration != 'recorded_endpoint']
                ta.lm_run(t, folder, sc.read(folder / 'configuration.json')['stages'], 'result.json', 'curve')
        out[case] = t
    return {case: out[case] for case in ast.CASES}


def collect(workers=20):
    declared = trajectories()
    table = ta.shots(declared.values())
    have = {p.stem for p in ta.OUTPUT.glob('shots/*.npz')}
    jobs = [('shots', key, entry['curve'].coefficients, sorted(entry['grids']),
             dict(cases=sorted(entry['cases']), steps=entry['steps']), str(HERE))
            for key, entry in table.items() if key not in have]
    print('new shots', len(jobs), 'reused', len(table) - len(jobs), flush=True)
    records = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name, record in pool.map(ta._worker, jobs):
            records[name] = record
            assert record.get('status') != 'EXCEPTION', record
    steps = []
    for case, t in declared.items():
        steps.append(dict(id=t.id, case=case, status=t.status, reason=t.reason, algorithm=t.algorithm,
                          steps=[dict(shot=ta.shot_key(s.curve), stage=s.stage, iteration=s.iteration,
                                      update_modes=s.update_modes, curve_band=s.curve_band,
                                      active_wavenumbers=list(s.wavenumbers), nodes=s.nodes, source=s.source,
                                      saved_loss=s.loss) for s in t.steps]))
    sc.write(HERE / 'trajectories.json', dict(trajectories=steps, new_shots=sorted(records),
             collector_sha256=sc.digest(Path(ta.__file__))))


if __name__ == '__main__':
    {'run': run, 'collect': collect}[sys.argv[1]]()
