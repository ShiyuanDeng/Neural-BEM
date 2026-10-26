"""Keep an accepted state when its next linearization exhausts the quota."""
from dataclasses import replace

import numpy as np

from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.fit_stage import fit_stage
from bem_inverse.work import Ledger
from test_resolution_resume import ScalarUpdate, scalar_stage, scalar_trial


def test_recording_keeps_acceptance_before_linearization_quota_stop():
    results = []
    for recording in (False, True):
        physics, stage, config, _ = scalar_stage()
        stage = replace(stage, quota=3)
        ledger = Ledger(cap=500, clock=lambda: 0., endpoint_reserve=0)
        ledger.begin_stage(stage.label, stage.quota)
        accepted = []
        result = fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(),
            replace(config, record_diagnostics=recording), ledger, physics=physics,
            forward_solve=physics.forward_solve, geometry_update=scalar_trial,
            on_accept=lambda iteration, evaluation: accepted.append((iteration, evaluation.loss)))
        results.append((result, physics, accepted))

    (plain, plain_physics, plain_accepted), (recorded, recorded_physics, recorded_accepted) = results
    assert plain.outcome == recorded.outcome == 'STAGE_QUOTA_REACHED'
    assert plain.accepted_steps == recorded.accepted_steps == 1
    assert plain.work == recorded.work
    assert [t['status'] for t in plain.trials] == [t['status'] for t in recorded.trials]
    assert plain_physics.calls == recorded_physics.calls
    assert plain_physics.derivatives == recorded_physics.derivatives
    assert plain_accepted == recorded_accepted
    np.testing.assert_array_equal(plain.curve.coefficients, recorded.curve.coefficients)
    assert len(recorded.history) == recorded.accepted_steps + 1
    final = recorded.history[-1]
    assert final['loss'] == recorded.final_loss == recorded_accepted[-1][1]
    assert final['iteration'] == 1 and final['gradient_inf'] is None
    assert final['linearization_interrupted'] == recorded.outcome
    assert not final.get('terminal_linearization_skipped', False)
    assert final['work'] == recorded.work
    assert final['raw_step_norm_m'] == recorded.trials[-1]['raw_step_norm_m']
