"""Matched state-treatment suffixes; immutable inputs and portable JSON evidence."""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
import importlib.util
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np
from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import Ledger, Objective, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
PLAN = sc.ROOT/'docs/iterations/shape_frequency_continuation/iteration_23/03_plan.md'
spec = importlib.util.spec_from_file_location('sc042_reference', RESULTS/'SC-041-atlas-decisions/run.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
CASES = ('circle_to_star', 'kite', 'wrong_circle', 'circle_to_c', 'peanut', 'hook')
ARMS = ('none', 'once', 'boundary', 'cap')
QUOTA = 608


def write(path, value):
    """Atomic snapshots remain parseable while workers run."""
    path = Path(path)
    temp = path.with_suffix(path.suffix+'.tmp')
    sc.write(temp, value)
    temp.replace(path)


def start_record(case):
    if case in ('circle_to_star', 'kite'):
        m = 25 if case == 'circle_to_star' else 22
        path = RESULTS/f'SC-041-atlas-decisions/runs/{case}/M{m}/result.json'
        row = sc.read(path)
        return ast.curve_from(row['curve']), path, row['final_loss'], 512 if m == 25 else 768
    row = reference.endpoint(case)
    path = sc.ROOT/row['source']
    saved = sc.read(path)
    item = next(r for r in saved['history'] if r['iteration'] == row['iteration'])
    return ast.curve_from(item['coefficients']), path, row['saved_loss'], row['nodes']


def resize(curve, band):
    if band < curve.band:
        return FourierCurve(curve.coefficients[curve.band-band:curve.band+band+1])
    return FourierCurve(np.pad(curve.coefficients, (band-curve.band,)*2))


def treatment(curve, arm, stage_index):
    if arm not in ARMS:
        raise ValueError(arm)
    cleanup = arm in ('boundary', 'cap') or (arm == 'once' and stage_index == 0)
    cleaned = resize(curve, 64) if cleanup else curve
    target = 64 if arm == 'cap' else 192
    return resize(cleaned, target), cleanup


def stages_for(case, arm):
    start, path, loss, nodes = start_record(case)
    bands = (25, 31, 37) if case == 'circle_to_star' else (22, 28, 34) if case == 'kite' else (19, 25, 31)
    stage, config, catalog = reference.setup(case, bands[0])
    stages = [replace(stage, label=f'stage_{i+1}_M{m}', update_modes=m,
                      curve_modes=64 if arm == 'cap' else 192, nodes=nodes,
                      refined_nodes=2*nodes, iterations=22, quota=QUOTA) for i, m in enumerate(bands)]
    return start, stages, config, path, loss


def sources():
    paths = list(sc.ROOT.glob('experiments/shape_continuation/*.py')) + list(sc.ROOT.glob('solvers/**/*.py'))
    paths += [Path(__file__), PLAN, RESULTS/'SC-035-state-band/state_update.py',
              RESULTS/'SC-035-state-band/run.py', RESULTS/'SC-038-update-band-release/run.py',
              RESULTS/'SC-041-atlas-decisions/run.py']
    return {str(p.relative_to(sc.ROOT)): sc.digest(p) for p in sorted(set(paths))}


def prepare():
    if (HERE/'manifest.json').exists():
        verify()
        return
    inputs = {RESULTS/'SC-040-six-scene-pipeline/trajectories.json'}
    for case in CASES:
        inputs.update((start_record(case)[1], ast.source_folder(case)/'observations.json', ast.source_folder(case)/'truth.json'))
    write(HERE/'manifest.json', dict(experiment='SC-042', parent_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip(), sources=sources(),
        inputs={str(p.relative_to(sc.ROOT)): sc.digest(p) for p in sorted(inputs)},
        cases=CASES, arms=ARMS, quota=QUOTA, workers_max=6, seconds_per_stage=3600,
        prepared=time.strftime('%Y-%m-%dT%H:%M:%S%z')))


def verify():
    m = sc.read(HERE/'manifest.json')
    assert m['sources'] == sources(), 'Frozen numerical source changed'
    assert all(sc.digest(sc.ROOT/p) == h for p, h in m['inputs'].items()), 'Frozen input changed'


def audit(curve, stage, config):
    ledger = Ledger(cap=130, seconds=900, endpoint_reserve=0)
    try:
        update = reference.ProjectedUpdate(sc.LENGTH)
        coarse = Objective(stage, ac.contrast(), config, ledger)
        fine = Objective(replace(stage, nodes=stage.refined_nodes, refined_nodes=2*stage.refined_nodes),
                         ac.contrast(), config, ledger)
        with geometry_validation('cache'):
            a = coarse.production(curve, 'audit_base')
            b = fine.production(curve, 'audit_fine')
            if a is None or b is None:
                raise ValueError('Endpoint field evaluation failed')
            space = update.prepare(curve, stage.update_modes, stage.curve_modes)
            # SC-041's qualified full-trial audit uses a fixed seed (41001).
            # Explicit version here follows SC-042's frozen 42001 seed.
            ja, jb = coarse.jacobian(a, update, space), fine.jacobian(b, update, space)
            fields = reference.relative_columns(a.prediction, b.prediction)
            derivative = np.linalg.norm(ja-jb, axis=0)/np.maximum(np.linalg.norm(jb, axis=0), 1e-30)
            direction = np.random.default_rng(42001).normal(size=ja.shape[1])
            direction /= np.linalg.norm(direction)
            plus, minus = [fine.production(update.trial(space, s*1e-7*direction)[0], 'audit_fd') for s in (1, -1)]
            fd = (plus.residual-minus.residual)/2e-7
            error = float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30))
            row = dict(passed=bool(np.all(fields <= stage.discrepancy_tolerances) and max(derivative) <= 1e-3 and error <= 1e-3),
                       field_relative=fields, jacobian_relative=derivative, full_trial_fd_relative=error,
                       fine_loss=b.loss)
    except Exception:
        row = dict(passed=False, traceback=traceback.format_exc())
    return dict(row, work=ledger.snapshot())


def worker(job):
    case, arm = job
    folder = HERE/'runs'/case/arm
    folder.mkdir(parents=True, exist_ok=False)
    total_started = time.perf_counter()
    records, accepted, interventions = [], [], []
    try:
        verify()
        curve, stages, config, parent, saved_loss = stages_for(case, arm)
        initial = curve
        update = reference.ProjectedUpdate(sc.LENGTH)
        write(folder/'configuration.json', dict(case=case, arm=arm, parent=str(parent.relative_to(sc.ROOT)),
              initial=ast.curve_record(initial), saved_loss=saved_loss,
              stages=[stage_record(s) for s in stages], backend=asdict(config), update=update.settings()))
        total_units = 0
        outcome = 'COMPLETED_SCHEDULE'
        last_stage = stages[0]
        for i, stage in enumerate(stages):
            before = curve
            curve, cleaned = treatment(curve, arm, i)
            with geometry_validation('cache'):
                curve.validate()
            intervention = dict(stage=stage.label, cleanup=cleaned, before=ast.curve_record(before),
                after=ast.curve_record(curve), prior_loss=records[-1]['final_loss'] if records else saved_loss)
            interventions.append(intervention)
            ledger = Ledger(cap=QUOTA+1, seconds=3600)
            ledger.begin_stage(stage.label, QUOTA)
            base_units = total_units

            def checkpoint(iteration, evaluation):
                if iteration == 0:
                    intervention['after_loss'] = evaluation.loss
                    intervention['loss_jump'] = evaluation.loss-intervention['prior_loss']
                    write(folder/'interventions.json', dict(rows=interventions))
                    if i == 0 and arm == 'none':
                        assert abs(evaluation.loss-saved_loss) <= max(1e-14, 1e-8*saved_loss), 'Starting loss mismatch'
                accepted.append(dict(stage=stage.label, M=stage.update_modes, iteration=iteration,
                    loss=evaluation.loss, curve=ast.curve_record(evaluation.curve),
                    total_units=base_units+ledger.units, stage_units=ledger.units))
                write(folder/'accepted.json', dict(states=accepted))

            with geometry_validation('cache'):
                result = fit_stage(curve, stage, ac.contrast(), update, config, ledger, on_accept=checkpoint)
            curve = result.curve
            last_stage = stage
            total_units += ledger.units
            row = dict(stage=stage.label, M=stage.update_modes, K=stage.curve_modes,
                outcome=result.outcome, stop=result.stop_reason, detail=result.detail,
                initial_loss=result.initial_loss, final_loss=result.final_loss,
                work=ledger.snapshot(), total_units=total_units, curve=ast.curve_record(curve))
            records.append(row)
            write(folder/f'{stage.label}.json', dict(row, history=result.history, trials=result.trials,
                                                  acceptance_checks=result.acceptance_checks))
            write(folder/'checkpoint.json', dict(stages=records, total_units=total_units, curve=ast.curve_record(curve)))
            print('STAGE', case, arm, stage.label, result.outcome, result.final_loss, total_units, flush=True)
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                outcome = result.outcome
                break
        final_audit = audit(curve, last_stage, config)
        write(folder/'audit.json', final_audit)
        # Truth only after the entire suffix returns; never consumed by decisions.
        row = dict(case=case, arm=arm, outcome=outcome, stages=records, total_units=total_units,
            audit_passed=final_audit['passed'], audit_units=final_audit['work']['work_units'],
            initial_score=reference.geometry_score(case, initial), score=reference.geometry_score(case, curve),
            curve=ast.curve_record(curve), seconds=time.perf_counter()-total_started,
            geometry_work=update.counts)
        write(folder/'progress.json', dict(states=[dict(s, score=reference.geometry_score(case, ast.curve_from(s['curve']))) for s in accepted]))
        verify()
        write(folder/'result.json', row)
        print('DONE', case, arm, outcome, row['score'], 'audit', final_audit['passed'], flush=True)
        return {k: row[k] for k in ('case', 'arm', 'outcome', 'total_units', 'audit_passed', 'audit_units', 'score')}
    except Exception:
        row = dict(case=case, arm=arm, outcome='EXCEPTION', traceback=traceback.format_exc(),
                   stages=records, seconds=time.perf_counter()-total_started)
        write(folder/'failure.json', row)
        print('FAILED', case, arm, row['traceback'], flush=True)
        return row


def summarize():
    rows = []
    for p in sorted((HERE/'runs').glob('*/*/result.json')):
        d = sc.read(p)
        rows.append({k: d[k] for k in ('case', 'arm', 'outcome', 'total_units', 'audit_passed', 'audit_units', 'score')})
    failures = [dict(path=str(p.relative_to(HERE)), **sc.read(p)) for p in sorted((HERE/'runs').glob('*/*/failure.json'))]
    write(HERE/'summary.json', dict(rows=rows, failures=failures, completed=len(rows), planned=24,
          inverse_units=sum(r['total_units'] for r in rows), audit_units=sum(r['audit_units'] for r in rows)))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'run', 'summarize'))
    parser.add_argument('--cases', nargs='+', choices=CASES, default=CASES)
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
    elif args.mode == 'summarize':
        summarize()
    else:
        if not 1 <= args.workers <= 6:
            parser.error('workers must be between 1 and 6')
        verify()
        jobs = [(c, a) for c in args.cases for a in ARMS if not (HERE/'runs'/c/a).exists()]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(worker, j) for j in jobs]
            for future in as_completed(futures):
                future.result()
                summarize()
        verify()
        summarize()


if __name__ == '__main__':
    main()
