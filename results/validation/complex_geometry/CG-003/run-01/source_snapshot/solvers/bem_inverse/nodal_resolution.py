"""Truth-free stage-entry nodal field/Jacobian qualification."""
from dataclasses import replace
from time import perf_counter
import numpy as np
from .continuation.lm_backend import normalize, NumericalFailure


def ladder(seed):
    if seed >= 1024:
        return (seed, max(2048, seed+64))
    return (*range(seed, 1024, 64), 1024, 2048)


def select_stage(physics, curve, stage, config, contrast, update, ledger):
    started = perf_counter()
    space = update.prepare(curve, stage.update_modes, stage.curve_modes)
    observed = np.column_stack([o.scattered.reshape(-1) for o in stage.observations])
    attempts = []
    candidates = ladder(stage.nodes)
    for nodes, finer in zip(candidates[:-1], candidates[1:]):
        low_fields, high_fields, low_jac, high_jac = [], [], [], []
        for observation in stage.observations:
            blocks = []
            for resolution in (nodes, finer):
                ledger.reserve(1)
                ledger.charge('solve', 'resolution_selection')
                try:
                    state = physics.evaluate(curve, observation, contrast, resolution)
                except Exception:
                    ledger.fail('resolution_selection')
                    raise
                field = np.array(state.prediction, copy=True).reshape(-1)
                ledger.reserve(1)
                ledger.charge('reciprocal', 'resolution_selection')
                try:
                    jac = physics.derivative(state, update, space)
                except Exception:
                    ledger.fail('resolution_selection')
                    raise
                blocks.append((field, jac.reshape(-1, jac.shape[-1])))
                del state
            low_fields.append(blocks[0][0]); high_fields.append(blocks[1][0])
            low_jac.append(blocks[0][1]); high_jac.append(blocks[1][1])
        a, b = np.column_stack(low_fields), np.column_stack(high_fields)
        fields = np.linalg.norm(a-b, axis=0)/np.maximum(np.linalg.norm(b, axis=0), 1e-30)
        ja = normalize(np.stack(low_jac, axis=1), observed, stage.weights, config.residual_floor)
        jb = normalize(np.stack(high_jac, axis=1), observed, stage.weights, config.residual_floor)
        derivatives = np.linalg.norm(ja-jb, axis=0)/np.maximum(np.linalg.norm(jb, axis=0), 1e-30)
        passed = bool(np.all(np.isfinite(fields)) and np.all(np.isfinite(derivatives)) and
                      np.all(fields <= stage.discrepancy_tolerances) and np.all(derivatives <= 1e-3))
        attempts.append(dict(nodes=nodes, refined_nodes=finer, field_relative=fields,
                             jacobian_relative=derivatives, passed=passed))
        if passed:
            return replace(stage, nodes=nodes, refined_nodes=finer), dict(
                seed=stage.nodes, selected=nodes, refined=finer, escalated=nodes != stage.nodes,
                seconds=perf_counter()-started, attempts=attempts)
    error = NumericalFailure('No nodal stage profile passed field/Jacobian qualification through N1024/2048')
    error.resolution_selection = dict(seed=stage.nodes, selected=None, seconds=perf_counter()-started,
                                      attempts=attempts)
    raise error
