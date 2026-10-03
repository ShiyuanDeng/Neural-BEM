"""Read-only diagnostic of FM-001's relaxed warmup at its saved C state.

Run from the repository with EMNerf Python and PYTHONPATH=solvers:.
No fit, tuning, or campaign evidence is modified.
"""
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import numpy as np
from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.fm001 import OUTPUT, full_problem
from experiments.cleaned_interface.full_matrix import RelaxedObjective, RealRelaxedPrefix
from experiments.cleaned_interface.physics import NodalKress, Execution
from experiments.cleaned_interface.geometry import ProjectedUpdate
from experiments.cleaned_interface.io import curve_from
from experiments.shape_continuation.lm_backend import Ledger, normalize
from experiments.cleaned_interface.full_matrix import apply_receiver_weights

case = 'modal__c13.3__development_c'
record = OUTPUT/'FRr'/'runs'/case/'warmup_025_real_relaxed.json'
saved = json.loads(record.read_text())
assert saved['accepted_steps'] == 0
curve = curve_from(saved['curve'])
row = next(r for r in b.descriptors() if r['id'] == case)
problem, _ = full_problem(row, OUTPUT)
backend = NodalKress(Execution(device='cpu', frequency_threads=1))
op = next(op for op in RealRelaxedPrefix().operations(problem, backend) if op.kind == 'fit')
update = ProjectedUpdate(problem.length_unit_m)
space = update.prepare(curve, op.stage.update_modes, curve.band)
objective = RelaxedObjective(op.stage, problem.contrast, op.optimizer, Ledger(), physics=backend)
base = objective.production(curve, 'review_base')
jac = objective.jacobian(base, update, space)
gradient = jac.T @ base.residual
checks = []
for step in (1e-5, 1e-6, 1e-7):
    full, frozen = [], []
    for direction in np.eye(len(gradient)):
        pair = [objective.production(update.trial(space, sign*step*direction)[0], 'review_fd')
                for sign in (1, -1)]
        full.append((pair[0].loss-pair[1].loss)/(2*step))
    full = np.array(full)
    checks.append(dict(step_m=step, exact_loss_fd_gradient=full.tolist(),
        relative_gradient_error=float(np.linalg.norm(full-gradient)/np.linalg.norm(full)),
        gradient_cosine=float(full@gradient/np.linalg.norm(full)/np.linalg.norm(gradient)),
        exact_slope_along_negative_approx_gradient=float(-full@gradient)))
control = []
step = 1e-7
for direction in np.eye(len(gradient)):
    losses = []
    for sign in (1, -1):
        trial = objective.production(update.trial(space, sign*step*direction)[0], 'review_frozen')
        columns = []
        for i, obs in enumerate(op.stage.observations):
            columns.append(apply_receiver_weights(
                trial.prediction[:, i]-obs.scattered.reshape(-1), base.receiver_weights[i],
                obs.scattered.shape))
        residual = normalize(np.column_stack(columns), objective.observed,
                             op.stage.weights, op.optimizer.residual_floor)
        losses.append(.5*float(residual@residual))
    control.append((losses[0]-losses[1])/(2*step))
control = np.asarray(control)
fine_stage = replace(op.stage, nodes=1024, refined_nodes=2048)
fine_objective = RelaxedObjective(fine_stage, problem.contrast, op.optimizer, Ledger(), physics=backend)
fine_base = fine_objective.production(curve, 'review_fine')
fine_gradient = []
for direction in np.eye(len(gradient)):
    pair = [fine_objective.production(update.trial(space, sign*step*direction)[0], 'review_fine_fd')
            for sign in (1, -1)]
    fine_gradient.append((pair[0].loss-pair[1].loss)/(2*step))
fine_gradient = np.asarray(fine_gradient)
direction = -gradient/np.linalg.norm(gradient)
uphill = objective.production(update.trial(space, step*direction)[0], 'review_uphill').loss-base.loss
downhill_direction = -fine_gradient/np.linalg.norm(fine_gradient)
downhill = objective.production(update.trial(space, step*downhill_direction)[0], 'review_downhill').loss-base.loss
result = dict(case=case, stage=op.label, production_nodes=op.stage.nodes,
    archived_initial_loss=saved['initial_loss'], replayed_loss=base.loss,
    archived_gradient_inf=saved['history'][0]['gradient_inf'],
    frozen_weight_gradient=gradient.tolist(), checks=checks,
    frozen_weight_fd_control=dict(gradient=control.tolist(),
        relative_error=float(np.linalg.norm(control-gradient)/np.linalg.norm(control))),
    refined_check=dict(nodes=1024, loss=fine_base.loss, gradient=fine_gradient.tolist(),
        gradient_cosine=float(fine_gradient@gradient/np.linalg.norm(fine_gradient)/np.linalg.norm(gradient)),
        relative_loss_change=float(abs(fine_base.loss/base.loss-1))),
    local_steps=dict(step_m=step, loss_change_negative_approx_gradient=uphill,
        loss_change_negative_finite_difference_gradient=downhill),
    record_sha256=hashlib.sha256(record.read_bytes()).hexdigest(),
    source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path('solvers/bem_inverse/full_matrix.py'), Path(__file__)]},
    scope='Local derivative diagnostic only; no claim that a corrected derivative recovers this case.')
target = Path('/tmp/relaxed_bie_review_20261003.json')
target.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
