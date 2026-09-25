"""SC-036 bounded matched-path replay; truth is read only for post-trial scoring."""
import argparse
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from . import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from .atlas_survey import symmetric_rms_distance
from .finite_paths import RayUpdate
from .geometry import grid_size, normal_basis
from .lm_backend import Objective, Ledger, acceptance, control_step, relative_columns
from .updates import BorgesUpdate, UpdateRefused

SOURCE = sc.ROOT / 'results/validation/shape_continuation/SC-029-atlas-strategies/runs/baseline'
OUTPUT = sc.ROOT / 'results/validation/shape_continuation/SC-036-matched-finite-paths'
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_16/03_plan.md'
STATES = (('peanut', 3), ('peanut', 4), ('peanut', -1), ('kite', 4), ('circle_to_star', 2))


def geometric_score(curve, truth):
    nodes = curve.nodes(4096)
    return dict(rms_mm=1e3*symmetric_rms_distance(curve, truth.values(4096), sc.LENGTH),
                radius_mm=float(1e3*sc.LENGTH/np.max(np.abs(nodes.curvatures))))


def frozen_sources():
    paths = list((sc.ROOT / 'experiments/shape_continuation').glob('*.py'))
    return {str(p.relative_to(sc.ROOT)): sc.digest(p) for p in paths}


def replay(case, index, folder, ledger):
    history_path = SOURCE / case / 'none/stage_1_history.json'
    history = sc.read(history_path)['history']
    item = history[index]
    curve = ast.curve_from(item['coefficients'])
    catalog = ast.catalog_only(case)
    stages, config = ast.schedules(catalog, 'baseline')
    stage = stages[0]
    normal, ray = BorgesUpdate(sc.LENGTH, projection_tolerance=1e-5), RayUpdate(sc.LENGTH)
    space = normal.prepare(curve, stage.update_modes, stage.curve_modes)
    objective = Objective(stage, ac.contrast(), config, ledger)
    base = objective.production(curve, 'base')
    refined_base = objective.refined(curve)
    matrix = objective.jacobian(base, normal, space)
    gram = matrix.T @ matrix
    gradient = matrix.T @ base.residual
    damping = item['next_damping']
    step = control_step(np.linalg.solve(gram+damping*np.diag(np.maximum(np.diag(gram), config.scaling_floor)),
                                       -gradient), space, normal, config)
    result = dict(case=case, history_index=index, iteration=item['iteration'],
                  saved_loss=item['loss'], base_loss=base.loss, base_refined_loss=refined_base.loss,
                  damping=damping, coefficients_m=step, qualification=[], trials=[],
                  history_sha256=sc.digest(history_path),
                  base_discrepancy=relative_columns(base.prediction, refined_base.prediction))
    assert abs(base.loss-item['loss']) < max(1e-13, 1e-10*base.loss), 'saved-state replay mismatch'
    direction = step/np.linalg.norm(step)
    predicted = matrix @ direction
    for name, update in (('normal', normal), ('ray', ray)):
        row = dict(path=name)
        try:
            eps = 1e-7
            a, b = [update.trial(space, sign*eps*direction)[0] for sign in (1, -1)]
            plus, minus = [objective.production(c, 'qualification').residual for c in (a, b)]
            error = float(np.linalg.norm((plus-minus)/(2*eps)-predicted)/np.linalg.norm(predicted))
            row.update(relative_derivative_error=error, passed=error <= 1e-3)
        except UpdateRefused as exc:
            row.update(passed=False, reason=exc.reason, detail=exc.detail)
        result['qualification'].append(row)
    print(case, index, 'derivatives', result['qualification'], flush=True)
    # Selection of the LM direction and all test multipliers is complete before
    # this evaluation-only truth read. Scores cannot influence trials.
    truth = ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))
    result['base_geometry'] = geometric_score(curve, truth)
    for name, update in (('normal', normal), ('ray', ray)):
        qualified = next(q['passed'] for q in result['qualification'] if q['path']==name)
        for backtrack in range(8):
            scale = .5**backtrack
            move = scale*step
            predicted_decrease = float(-gradient@move-.5*move@gram@move)
            row = dict(path=name, scale=scale, predicted_decrease=predicted_decrease)
            try:
                candidate, geometry = update.trial(space, move)
                row.update(geometry)
                row.update(geometric_score(candidate, truth))
                p, r = objective.production(candidate, 'trial'), objective.refined(candidate)
                if p is None or r is None:
                    row.update(status='physics_failed', accepted=False)
                else:
                    discrepancy = relative_columns(p.prediction, r.prediction)
                    numerical = bool(np.all(discrepancy <= stage.discrepancy_tolerances))
                    decision = acceptance(base.loss, p.loss, refined_base.loss, r.loss, config)
                    row.update(status='evaluated', loss=p.loss, refined_loss=r.loss,
                               actual_decrease=base.loss-p.loss,
                               refined_decrease=refined_base.loss-r.loss,
                               discrepancy=discrepancy, numerical_pass=numerical,
                               accepted=bool(qualified and numerical and decision['accepted']),
                               linear_model_error=float(np.linalg.norm(p.residual-base.residual-matrix@move)
                                                        /max(np.linalg.norm(matrix@move), 1e-30)))
                    sc.write(folder / f'{name}_{backtrack}_curve.json', ast.curve_record(candidate))
            except UpdateRefused as exc:
                row.update(status='geometry_refused', reason=exc.reason, detail=exc.detail, accepted=False)
            result['trials'].append(row)
            sc.write(folder/'result.json', dict(result, work=ledger.snapshot()))
            print(case, index, name, scale, row['status'], row.get('accepted'),
                  row.get('refined_decrease', row.get('reason')), flush=True)
    normal_best = max([r['refined_decrease'] for r in result['trials'] if r['path']=='normal' and r['accepted']], default=0.)
    result['release_inverse'] = any(r['path']=='ray' and r['accepted'] and
        r['refined_decrease'] > 2*normal_best and r['rms_mm'] < result['base_geometry']['rms_mm']
        for r in result['trials'])
    sc.write(folder/'result.json', dict(result, work=ledger.snapshot()))
    return dict(case=case, index=index, release_inverse=result['release_inverse'],
                base_geometry=result['base_geometry'], qualification=result['qualification'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources = frozen_sources()
    inputs = {str(p.relative_to(sc.ROOT)): sc.digest(p) for case, _ in STATES for p in
              (ast.source_folder(case)/'observations.json', ast.source_folder(case)/'truth.json',
               SOURCE/case/'none/stage_1_history.json')}
    sc.write(args.output/'manifest.json', dict(experiment='SC-036', sources=sources, inputs=inputs,
        plan_sha256=sc.digest(PLAN), command=sys.argv, python=sys.executable, states=STATES,
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        timestamp=time.strftime('%Y-%m-%dT%H:%M:%S%z'), cap=1800, seconds=2700))
    ledger = Ledger(cap=1800, seconds=2700, endpoint_reserve=0)
    rows=[]
    for case,index in STATES:
        folder=args.output/f'{case}_{index}'
        folder.mkdir()
        rows.append(replay(case,index,folder,ledger))
        sc.write(args.output/'summary.json', dict(rows=rows, work=ledger.snapshot(),
            release_inverse=any(r['release_inverse'] for r in rows)))
    assert frozen_sources()==sources, 'sources changed during screen'
    assert all(sc.digest(sc.ROOT/p)==digest for p,digest in inputs.items()), 'inputs changed'


if __name__ == '__main__':
    main()
