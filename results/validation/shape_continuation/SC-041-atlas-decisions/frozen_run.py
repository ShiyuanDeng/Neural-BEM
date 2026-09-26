"""SC-041: complete-update predictions, finite probes and five matched LM arms.

Run once with `run`; `summarize` rebuilds the report without any field solves.
Numerical sources are frozen throughout. All files are local to this bundle.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np

from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast
from experiments.shape_continuation import atlas_video as av, spd_cases as sc, trajectory_atlas as ta
from experiments.shape_continuation.action_atlas import predict, descent_lower_bound
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.finite_path_study import frozen_sources
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import (
    Ledger, Objective, acceptance, fit_stage, inside_box, normalize, relative_columns, stage_record,
)
from experiments.shape_continuation.updates import UpdateRefused

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_22/03_plan.md'
INDEX = RESULTS / 'SC-040-six-scene-pipeline/trajectories.json'
ARMS = {'circle_to_star': (19, 22, 25), 'kite': (19, 22)}
spec = importlib.util.spec_from_file_location('sc041_reference', RESULTS / 'SC-038-update-band-release/run.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
ProjectedUpdate = reference.ProjectedUpdate


def sources():
    shared = sc.read(RESULTS / 'SC-036-logs/shared_environment.json')['numerical_dependencies']
    paths = [sc.ROOT / p for p in shared]
    paths += [Path(__file__), PLAN, reference.BASE / 'state_update.py', reference.BASE / 'run.py',
              RESULTS / 'SC-038-update-band-release/run.py']
    return dict(frozen_sources(), **{str(p.relative_to(sc.ROOT)): sc.digest(p) for p in paths})


def verify():
    manifest = sc.read(HERE / 'manifest.json')
    assert sources() == manifest['sources'], 'Frozen numerical source changed'
    assert all(sc.digest(sc.ROOT / p) == h for p, h in manifest['inputs'].items()), 'Input changed'


def endpoint(case):
    return next(t for t in sc.read(INDEX)['trajectories'] if t['case'] == case)['steps'][-1]


def setup(case, M):
    stages, config, catalog = reference.schedules(case, 'release_m')
    saved = endpoint(case)
    stage = replace(stages[-1], label=f'M{M}', update_modes=M, nodes=saved['nodes'],
                    refined_nodes=2*saved['nodes'], quota=1500, iterations=22)
    config = replace(config, log_model=True)
    return stage, config, catalog


def start(case):
    with np.load(av.shot_path(endpoint(case)['shot'])) as shot:
        return FourierCurve(shot['coefficients'])


def stored_model(case, M, shot):
    stage, config, _ = setup(case, M)
    curve = FourierCurve(shot['coefficients'])
    update = ProjectedUpdate(sc.LENGTH)
    space = update.prepare(curve, M, 192)
    observed = np.column_stack([o.scattered for o in stage.observations])
    arrays = {}
    for grid, suffix in ((stage.nodes, ''), (stage.refined_nodes, '_fine')):
        h = update.velocities(space, curve.nodes(grid))
        blocks = np.stack([ta.jacobian(shot, f, grid, h) for f in range(19)], axis=1)
        predictions = np.column_stack([np.diag(p) for p in shot[f'prediction_{grid}']])
        arrays['J'+suffix] = normalize(blocks, observed, stage.weights, config.residual_floor)
        arrays['r'+suffix] = normalize(predictions-observed, observed, stage.weights, config.residual_floor)
    G = update.metric(space, 'mass')
    radius = .12/max(o.wavenumber for o in stage.observations)*sc.LENGTH
    model = predict(arrays['J'], arrays['r'], G, radius)
    return model, dict(arrays, metric=G, step=model.step, singular_values=model.singular_values)


def qualify(objective, fine, base, refined, update, space, saved=None):
    J = objective.jacobian(base, update, space)
    Jf = fine.jacobian(refined, update, space)
    fields = relative_columns(base.prediction, refined.prediction)
    derivative = np.linalg.norm(J-Jf, axis=0)/np.maximum(np.linalg.norm(Jf, axis=0), 1e-30)
    direction = np.random.default_rng(41001).normal(size=J.shape[1])
    direction /= np.linalg.norm(direction)
    plus, minus = [fine.production(update.trial(space, sign*1e-7*direction)[0], 'full_trial_fd')
                   for sign in (1, -1)]
    if plus is None or minus is None:
        raise ValueError('FD field evaluation failed')
    fd = (plus.residual-minus.residual)/2e-7
    error = float(np.linalg.norm(fd-Jf@direction)/max(np.linalg.norm(fd), 1e-30))
    row = dict(field_relative=fields, jacobian_relative=derivative, full_trial_fd_relative=error)
    row['passed'] = bool(np.all(fields <= objective.stage.discrepancy_tolerances)
                         and max(derivative) <= 1e-3 and error <= 1e-3)
    if saved is not None:
        row['stored_J_relative'] = float(np.linalg.norm(J-saved['J'])/np.linalg.norm(J))
        row['stored_residual_relative'] = float(np.linalg.norm(base.residual-saved['r'])/np.linalg.norm(base.residual))
        row['saved_loss_relative'] = float(abs(base.loss-endpoint(saved['case'])['saved_loss'])/base.loss)
        row['passed'] &= max(row['stored_J_relative'], row['stored_residual_relative'], row['saved_loss_relative']) <= 1e-8
    return row


def screen(case):
    ledger = Ledger(cap=1000, seconds=1500, endpoint_reserve=0)
    folder = HERE / 'diagnostics' / case
    rows = []
    try:
        verify()
        curve = start(case)
        stage, config, _ = setup(case, max(ARMS[case]))
        objective = Objective(stage, ac.contrast(), config, ledger)
        fine = Objective(replace(stage, nodes=stage.refined_nodes, refined_nodes=2*stage.refined_nodes),
                         ac.contrast(), config, ledger)
        with geometry_validation('cache'):
            base = objective.production(curve, 'screen_base')
            refined = fine.production(curve, 'screen_refined_base')
            if base is None or refined is None:
                raise ValueError('Unresolved starting field')
            for M in ARMS[case]:
                model = sc.read(folder / f'M{M}_prediction.json')
                with np.load(folder / f'M{M}_model.npz') as data:
                    saved = {k: data[k] for k in data.files}
                update = ProjectedUpdate(sc.LENGTH)
                space = update.prepare(curve, M, 192)
                q = qualify(objective, fine, base, refined, update, space, dict(saved, case=case))
                row = dict(M=M, qualification=q, prediction=model, trials=[], finite_gate=False)
                rows.append(row)
                sc.write(folder / 'screen.json', dict(case=case, rows=rows, work=ledger.snapshot()))
                if not q['passed']:
                    continue
                for scale in (1., .5, .25, .125):
                    p = scale*saved['step']
                    pred = float(-base.residual@(saved['J']@p)-.5*np.linalg.norm(saved['J']@p)**2)
                    trial = dict(scale=scale, predicted_decrease=pred, passed=False)
                    row['trials'].append(trial)
                    try:
                        candidate, geometry = update.trial(space, p)
                        if not inside_box(candidate, config.domain_box):
                            raise UpdateRefused('outside_domain', 'Candidate leaves the frozen domain.')
                        a = objective.production(candidate, 'screen_trial')
                        b = fine.production(candidate, 'screen_refined_trial')
                        if a is None or b is None:
                            raise ValueError('Trial field evaluation failed')
                        agreement = relative_columns(a.prediction, b.prediction)
                        accept = acceptance(base.loss, a.loss, refined.loss, b.loss, config)
                        remainder = float(np.linalg.norm(b.residual-(refined.residual+saved['J_fine']@p)))
                        pred_fine = float(-refined.residual@(saved['J_fine']@p)-.5*np.linalg.norm(saved['J_fine']@p)**2)
                        actual = refined.loss-b.loss
                        rho = actual/pred_fine if pred_fine > 0 else None
                        trial.update(geometry=geometry, acceptance=accept, field_relative=agreement,
                                     actual_decrease=actual, decrease_fraction=actual/refined.loss,
                                     predicted_decrease_fine=pred_fine, rho=rho, remainder_norm=remainder,
                                     measured_remainder_lower_bound=descent_lower_bound(
                                         pred_fine, np.linalg.norm(refined.residual+saved['J_fine']@p), remainder),
                                     curve=ast.curve_record(candidate),
                                     passed=bool(np.all(agreement <= stage.discrepancy_tolerances)
                                                 and accept['accepted'] and rho is not None and rho >= .5
                                                 and actual/refined.loss >= .1))
                    except (UpdateRefused, ValueError) as exc:
                        trial['refusal'] = str(exc)
                    sc.write(folder / 'screen.json', dict(case=case, rows=rows, work=ledger.snapshot()))
                    print('PROBE', case, M, scale, trial['passed'], trial.get('rho'), trial.get('refusal'), flush=True)
                    if trial['passed']:
                        row['finite_gate'] = True
                        break
        report = dict(case=case, rows=rows, passed=bool(all(r['qualification']['passed'] for r in rows)
                      and len(rows)==len(ARMS[case]) and any(r['finite_gate'] for r in rows)), work=ledger.snapshot())
        verify()
    except Exception:
        report = dict(case=case, rows=rows, passed=False, traceback=traceback.format_exc(), work=ledger.snapshot())
    sc.write(folder / 'screen.json', report)
    print('SCREEN', case, report['passed'], ledger.units, report.get('traceback', ''), flush=True)
    return report


def geometry_score(case, curve):
    # Evaluation only. No caller uses this to select a step, endpoint or arm.
    truth = ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    from experiments.shape_continuation.metrics import boundary_distance
    distance, error = boundary_distance(truth, curve)
    radii = [float(1e3*sc.LENGTH/np.max(np.abs(curve.nodes(n).curvatures))) for n in (8192, 16384)]
    return dict(rms_mm=1e3*symmetric_rms_distance(curve, truth.values(16384), sc.LENGTH),
                hausdorff_mm=1e3*sc.LENGTH*distance, hausdorff_upper_mm=1e3*sc.LENGTH*(distance+error),
                tightest_radius_mm=radii[0], tightest_radius_fine_mm=radii[1])


def run_arm(job):
    case, M = job
    folder = HERE / 'runs' / case / f'M{M}'
    folder.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(cap=1500, seconds=900)
    try:
        verify()
        stage, config, _ = setup(case, M)
        curve, update = start(case), ProjectedUpdate(sc.LENGTH)
        sc.write(folder/'configuration.json', dict(case=case, M=M, stage=stage_record(stage),
                 backend=asdict(config), update=update.settings(), initial=ast.curve_record(curve),
                 initial_source=endpoint(case), cap=1500, seconds=900))
        accepted = []

        def checkpoint(i, value):
            accepted.append(dict(iteration=i, loss=value.loss, curve=ast.curve_record(value.curve),
                                 work=ledger.snapshot()))
            sc.write(folder/'accepted.json', dict(states=accepted))

        ledger.begin_stage(stage.label, stage.quota)
        with geometry_validation('cache'):
            result = fit_stage(curve, stage, ac.contrast(), update, config, ledger, on_accept=checkpoint)
        row = dict(case=case, M=M, outcome=result.outcome, stop=result.stop_reason, detail=result.detail,
                   initial_loss=result.initial_loss, final_loss=result.final_loss,
                   curve=ast.curve_record(result.curve), accepted_steps=len(accepted)-1,
                   work=ledger.snapshot(), seconds=result.seconds, geometry_work=update.counts)
        sc.write(folder/'history.json', dict(history=result.history, trials=result.trials,
                                           acceptance_checks=result.acceptance_checks))
        sc.write(folder/'result.json', row)
        # Numerical endpoint audit has a separate bounded ledger.
        audit_ledger = Ledger(cap=130, seconds=600, endpoint_reserve=0)
        try:
            coarse = Objective(stage, ac.contrast(), config, audit_ledger)
            fine = Objective(replace(stage, nodes=stage.refined_nodes, refined_nodes=2*stage.refined_nodes),
                             ac.contrast(), config, audit_ledger)
            with geometry_validation('cache'):
                a = coarse.production(result.curve, 'endpoint_audit')
                b = fine.production(result.curve, 'endpoint_audit_fine')
                if a is None or b is None:
                    raise ValueError('Endpoint field failed')
                space = update.prepare(result.curve, M, 192)
                audit = qualify(coarse, fine, a, b, update, space)
                audit['catalog_relative_residual'] = relative_columns(b.prediction, coarse.observed)
        except Exception:
            audit = dict(passed=False, traceback=traceback.format_exc())
        audit['work'] = audit_ledger.snapshot()
        sc.write(folder/'audit.json', audit)
        row['score'] = geometry_score(case, result.curve)
        row['initial_score'] = geometry_score(case, curve)
        sc.write(folder/'result.json', row)
        # Every accepted state is retained, including one accepted just before a
        # quota interrupts the following derivative. Truth scoring happens now.
        sc.write(folder/'progress.json', dict(states=[dict(s, score=geometry_score(case, ast.curve_from(s['curve'])))
                                                    for s in accepted]))
        verify()
        print('DONE', case, M, row['outcome'], row['stop'], row['score'], ledger.units, flush=True)
        return dict(case=case, M=M, outcome=row['outcome'], audit_passed=audit['passed'])
    except Exception:
        failure = dict(case=case, M=M, traceback=traceback.format_exc(), work=ledger.snapshot())
        sc.write(folder/'failure.json', failure)
        print('FAILED', case, M, failure['traceback'], flush=True)
        return failure


def summarize():
    rows, screens = [], [sc.read(p) for p in sorted((HERE/'diagnostics').glob('*/screen.json'))]
    for path in sorted((HERE/'runs').glob('*/*/result.json')):
        row = sc.read(path)
        audit = sc.read(path.parent/'audit.json')
        history = sc.read(path.parent/'history.json')
        old_loss, ratios = row['initial_loss'], []
        for trial in history['trials']:
            if trial['status'] == 'accepted':
                gain = old_loss-trial['loss']
                ratios.append(gain/trial['predicted_decrease'] if trial['predicted_decrease'] > 0 else None)
                old_loss = trial['loss']
        rows.append(dict(case=row['case'], M=row['M'], outcome=row['outcome'], stop=row['stop'],
                         initial_loss=row['initial_loss'], final_loss=row['final_loss'],
                         initial_score=row.get('initial_score'), score=row.get('score'),
                         accepted_steps=row['accepted_steps'], units=row['work']['work_units'],
                         seconds=row['seconds'], audit_passed=audit['passed'],
                         audit_units=audit['work']['work_units'], accepted_rho=ratios,
                         trials=len(history['trials']),
                         catalog_relative_residual=audit.get('catalog_relative_residual')))
    sc.write(HERE/'summary.json', dict(rows=rows, screens=[dict(case=s['case'], passed=s['passed'],
                  units=s['work']['work_units']) for s in screens],
                  screen_units=sum(s['work']['work_units'] for s in screens),
                  inverse_units=sum(r['units'] for r in rows), audit_units=sum(r['audit_units'] for r in rows),
                  failures=[str(p.relative_to(HERE)) for p in (HERE/'runs').glob('*/*/failure.json')]))
    return rows


def run():
    (HERE/'diagnostics').mkdir(exist_ok=False)
    inputs = [INDEX]
    for case in ARMS:
        inputs += [av.shot_path(endpoint(case)['shot']), ast.source_folder(case)/'observations.json',
                   ast.source_folder(case)/'truth.json', sc.ROOT/endpoint(case)['source']]
    sc.write(HERE/'manifest.json', dict(experiment='SC-041', sources=sources(),
             inputs={str(p.relative_to(sc.ROOT)):sc.digest(p) for p in inputs}, arms=ARMS,
             parent_commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
             command=sys.argv, workers=2, threads={k:os.environ.get(k) for k in
             ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
             screen_cap=2000, inverse_cap=7500, audit_cap=650,
             hardware=dict(cpu_count=os.cpu_count(), platform=sys.platform)))
    # Freeze every local prediction before any new finite-step field evaluation.
    for case, bands in ARMS.items():
        folder = HERE/'diagnostics'/case
        folder.mkdir()
        shot = ta.load(av.shot_path(endpoint(case)['shot']))
        for M in bands:
            model, arrays = stored_model(case, M, shot)
            np.savez_compressed(folder/f'M{M}_model.npz', **arrays)
            sc.write(folder/f'M{M}_prediction.json', dict(case=case, M=M, **model.record(),
                     step=model.step, singular_values=model.singular_values,
                     arrays_sha256=sc.digest(folder/f'M{M}_model.npz')))
            print('PREDICT', case, M, model.record(), flush=True)
    with ProcessPoolExecutor(max_workers=2) as pool:
        screens = list(pool.map(screen, ARMS))
    jobs = [(s['case'], M) for s in screens if s['passed'] for M in ARMS[s['case']]]
    sc.write(HERE/'gate.json', dict(released_jobs=jobs, screens_passed={s['case']:s['passed'] for s in screens}))
    with ProcessPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run_arm, jobs))
    verify()
    rows = summarize()
    sc.write(HERE/'completion.json', dict(status='COMPLETE', outcomes=outcomes,
             all_cases_released=len(jobs)==5, all_endpoints_qualified=len(rows)==len(jobs)
             and all(r['audit_passed'] for r in rows), sources_and_inputs_unchanged=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run','summarize'))
    args = parser.parse_args()
    run() if args.action == 'run' else summarize()
