"""Small before/after reference capture; run with either source tree on PYTHONPATH.

This is a deterministic component/stage comparison, not a benchmark campaign.
Wall timings and exception tracebacks are excluded; numerical values, decisions,
dispatches, work charges and callback order are retained.
"""
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

from bem_inverse import Observation
from bem_inverse.errors import Stop
from bem_inverse.fit_stage import fit_stage
from bem_inverse.objective import Objective
from bem_inverse.stage_types import BackendConfig, FitStage, ResolutionResponse
from bem_inverse.work import Ledger
from bem_inverse.continuation.forward import PointSourceAcquisition
from bem_inverse.continuation.geometry import FourierCurve, resize
from bem_inverse.geometry_update_methods.certified_spectral import CertifiedSpectralUpdate
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings
from bem_inverse.physics import Execution
from test_resolution_resume import ScalarUpdate, setup


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()
                if 'seconds' not in k and k not in ('traceback', 'candidate_sha256')}
    if isinstance(value, (list, tuple)):
        return [stable(v) for v in value]
    if isinstance(value, np.ndarray):
        return stable(value.tolist())
    if isinstance(value, np.generic):
        return stable(value.item())
    if isinstance(value, complex):
        return dict(real=value.real, imag=value.imag)
    if isinstance(value, float) and not np.isfinite(value):
        return repr(value)
    return value


def stage_record(result):
    return stable({key: getattr(result, key) for key in (
        'outcome', 'stop_reason', 'converged', 'accepted_steps', 'initial_loss',
        'final_loss', 'history', 'trials', 'acceptance_checks', 'work',
        'resolution_events', 'final_nodes', 'final_refined_nodes',
        'geometry_proposals', 'entry_reused')})


def control_paths():
    """Small fixtures exercise optional responses without a physical inverse run."""
    records = {}
    for mode in ('agreement', 'hanke', 'terminal', 'callback_stop', 'quota', 'wall'):
        physics, stage, config, _ = setup('refine', iterations=2, nodes=16)
        ledger = Ledger(cap=500, seconds=10, endpoint_reserve=0, clock=lambda: 0.)
        ledger.begin_stage(stage.label, 3 if mode == 'quota' else None)
        if mode == 'wall':
            ledger.clock = lambda: 11.
        if mode in ('agreement', 'hanke'):
            config = replace(config, damping_rule=mode)
        if mode == 'terminal':
            config = replace(config, avoid_terminal_linearization=True)
        callbacks = []
        def callback(i, evaluation):
            callbacks.append((i, evaluation.loss))
            if mode == 'callback_stop' and i == 1:
                raise Stop('reference callback stop')
        result = fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(),
                           config, ledger, physics=physics, on_accept=callback)
        records[mode] = dict(result=stage_record(result), calls=stable(physics.calls),
                             derivatives=physics.derivatives, callbacks=callbacks)
    return records


def capture():
    arrays, records = {}, {}
    for mode, response in (
        ('refine', False), ('refine', True), ('backtrack', True),
        ('exhaust', True), ('base_failure', True),
    ):
        physics, stage, config, ledger = setup(mode, iterations=2)
        callbacks = []
        result = fit_stage(
            FourierCurve.circle(2), stage, .5, ScalarUpdate(), config, ledger,
            physics=physics,
            on_accept=lambda i, e: callbacks.append((i, e.loss, e.curve.coefficients.copy())),
            resolution_response=ResolutionResponse(16, 32, physics) if response else None,
        )
        key = f'{mode}_{response}'
        records[key] = dict(result=stage_record(result), calls=stable(physics.calls),
                            derivatives=physics.derivatives, callbacks=stable(callbacks))
        arrays[key] = result.curve.coefficients

    physics, stage, config, ledger = setup('refine', iterations=4, nodes=16)
    part = fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(), config,
                        ledger, physics=physics, pause_after=2)
    checkpoint = part.checkpoint
    restored = Ledger.restore(checkpoint.work, seconds=3600, endpoint_reserve=0)
    resumed = fit_stage(part.curve, stage, .5, ScalarUpdate(), config, restored,
                           physics=physics, resume=checkpoint)
    records['resume'] = dict(part=stage_record(part), result=stage_record(resumed),
                             calls=stable(physics.calls), derivatives=physics.derivatives,
                             signature=checkpoint.signature)
    arrays['resume'] = resumed.curve.coefficients

    # Real modal path: both real and damped frequencies, small trace/workspace.
    events = {}
    def observe(kind, row):
        if kind == 'field' and 'A_f' not in events:
            events.update(A_f=row['A'].copy(), source_rhs=row['B_s'].copy(),
                          reciprocal_rhs=row['B_r'].copy(), receiver=row['R'].copy(),
                          traces=row['X_s'].copy())
        if kind == 'reciprocal' and 'reciprocal_traces' not in events:
            events.update(reciprocal_traces=row['X_r'].copy(),
                          normal_weights=row['normal_velocity_weights'].copy())
    physics = ModalMuller(Execution(device='cpu', frequency_threads=1),
                          ModalSettings(trace_minimum=8, trace_step=8, window_margin=16),
                          observer=observe)
    theta = np.arange(4)*2*np.pi/4
    sources = 5*np.column_stack((np.cos(theta), np.sin(theta)))
    acquisition = PointSourceAcquisition(sources, sources*1.1, 1e-6)
    target = resize(FourierCurve.circle(), 4)
    observations = []
    for k in (.6, .6*(1+.25j)):
        observation = Observation(k, acquisition, np.ones(4, complex)*1e-6, .25e9)
        data = physics.evaluate(target, observation, .5, 128).prediction
        observations.append(replace(observation, scattered=data))
    events.clear()
    curve = resize(FourierCurve.circle(1.03), 4)
    update = CertifiedSpectralUpdate(.05, device='cpu', batched=True)
    stage = FitStage('modal_reference', tuple(observations), (.5, .5),
                        (1e-3, 1e-3), 1, 4, 64, 128, 2, resolution_kind='modal')
    config = BackendConfig()
    ledger = Ledger(cap=300, seconds=3600, endpoint_reserve=0)
    ledger.begin_stage(stage.label, None)
    objective = Objective(stage, .5, config, ledger, physics=physics)
    evaluation = objective.production(curve, 'reference')
    space = update.prepare(curve, 1, 4)
    J = objective.jacobian(evaluation, update, space)
    arrays.update(events)
    arrays.update(prediction=evaluation.prediction, residual=evaluation.residual,
                  coefficient_velocities=space.derivatives, J=J,
                  g=J.T@evaluation.residual, H_GN=J.T@J)
    a = np.array([.0001, -.0002, .00015])
    candidate, report = update.geometry_update(a, prepared=space)
    arrays['c_trial'] = candidate.coefficients
    records['geometry_trial'] = stable(report)
    callbacks = []
    result = fit_stage(curve, stage, .5, update, config, ledger, physics=physics,
                          on_accept=lambda i, e: callbacks.append((i, e.loss)),
                          retain_final=True)
    arrays['modal_endpoint'] = result.curve.coefficients
    records['modal'] = dict(result=stage_record(result), callbacks=callbacks,
                            counts=physics.receipt()['counts'])
    records['control_paths'] = control_paths()
    return arrays, records


if __name__ == '__main__':
    prefix = Path(sys.argv[1])
    arrays, records = capture()
    np.savez_compressed(str(prefix)+'.npz', **arrays)
    Path(str(prefix)+'.json').write_text(json.dumps(records, indent=2, sort_keys=True))
    print(f'{len(arrays)} arrays; {len(records)} decision records -> {prefix}')
