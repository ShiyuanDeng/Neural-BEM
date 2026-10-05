"""RG-001 gate contracts; finite default paths retain exact decisions."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from bem_inverse.continuation import lm_backend as lm
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.policy import CumulativePolicy
from bem_inverse.physics import Prediction, Execution
from test_resolution_resume import ScalarPhysics, ScalarUpdate, setup


def states(losses=(10., 8., 10., 8.), predictions=(2., 1.2, 2., 1.24)):
    return [SimpleNamespace(loss=x, prediction=np.array([[p]], complex)) for x,p in zip(losses,predictions)]


def test_gate_values_and_policy_plumbing():
    assert CumulativePolicy().resolution_gate == lm.BackendConfig().resolution_gate == 'absolute'
    for bad in ('relative', '', None):
        with pytest.raises(ValueError, match='resolution_gate'):
            lm.BackendConfig(resolution_gate=bad)
    from experiments.cleaned_interface.test_audit_streaming import fixture
    config, _, _ = CumulativePolicy(resolution_gate='decision')._config(fixture(), fixture().real)
    assert config.resolution_gate == 'decision'


def test_agreeing_gains_accept_overshoot_and_default_refuses():
    stage = SimpleNamespace(discrepancy_tolerances=(1e-3,))
    default, qualified = lm.resolution_check(*states(), stage, lm.BackendConfig())
    decision, qualified2 = lm.resolution_check(*states(), stage, lm.BackendConfig(resolution_gate='decision'))
    assert not qualified and not qualified2
    assert not default['accepted'] and decision['accepted']
    assert default['numerical_obstruction'] and decision['numerical_obstruction']
    assert decision['gate'] == 'decision'
    assert decision['prediction_discrepancy_ratios'][0] > 1


def test_disagreeing_gains_reject_overshoot_without_raising():
    row, accurate = lm.resolution_check(*states(losses=(10.,8.,10.,9.9)),
        SimpleNamespace(discrepancy_tolerances=(1e-3,)), lm.BackendConfig(resolution_gate='decision'))
    assert not row['accepted'] and not accurate


@pytest.mark.parametrize('gate', ['absolute', 'decision'])
@pytest.mark.parametrize('index', range(4))
@pytest.mark.parametrize('field', ['loss', 'prediction', 'failed'])
def test_nonfinite_or_failed_evaluation_remains_fatal(gate, index, field):
    values = states()
    if field == 'failed':
        values[index] = None
    else:
        setattr(values[index], field, np.nan if field == 'loss' else np.array([[np.nan]], complex))
    with pytest.raises(lm.NumericalFailure):
        lm.resolution_check(*values, SimpleNamespace(discrepancy_tolerances=(1e-3,)),
                            lm.BackendConfig(resolution_gate=gate))


def scalar(gate='absolute', physics=None, iterations=1):
    default_physics, stage, config, ledger = setup(iterations=iterations)
    return lm.fit_stage(FourierCurve.circle(2.), stage, .5, ScalarUpdate(),
        replace(config, resolution_gate=gate, log_model=True), ledger, physics=physics or default_physics)


def test_actual_stage_absolute_failure_and_decision_acceptance():
    old = scalar()
    new = scalar('decision')
    assert old.outcome == 'NUMERICAL_FAILURE' and old.accepted_steps == 0
    assert new.accepted_steps == 1
    assert new.acceptance_checks[-1]['numerical_obstruction']
    assert new.acceptance_checks[-1]['accepted']
    assert new.trials[-1]['status'] == 'accepted'


def test_actual_stage_gain_rejection_follows_backtracking():
    class Disagree(ScalarPhysics):
        def evaluate(self, curve, obs, contrast, nodes):
            if nodes == 16 and curve.coefficients[-1].real < 1.5:
                return Prediction(np.array([2.1], complex), {}, nodes)
            return super().evaluate(curve, obs, contrast, nodes)
    r = scalar('decision', Disagree())
    assert r.accepted_steps == 1 and r.curve.coefficients[-1].real == pytest.approx(1.6)
    assert r.trials[0]['status'] == 'numerical_rejection'
    assert r.trials[1]['status'] == 'accepted'


@pytest.mark.parametrize('gate', ['absolute', 'decision'])
@pytest.mark.parametrize('nodes', [8, 16])
def test_nonfinite_candidate_is_fatal_in_stage(gate, nodes):
    class Nonfinite(ScalarPhysics):
        def evaluate(self, curve, obs, contrast, resolution):
            if resolution == nodes and curve.coefficients[-1].real < 1.5:
                return Prediction(np.array([np.nan], complex), {}, resolution)
            return super().evaluate(curve, obs, contrast, resolution)
    result = scalar(gate, Nonfinite())
    assert result.outcome == 'NUMERICAL_FAILURE' and result.accepted_steps == 0
    assert 'non-finite' in result.detail


def test_finite_absolute_default_is_identical_to_explicit_default():
    # Disable the synthetic coarse bias for a fully qualified reference path.
    physics, stage, config, ledger = setup(iterations=2, nodes=16)
    a = lm.fit_stage(FourierCurve.circle(2.), stage, .5, ScalarUpdate(), config, ledger, physics=physics)
    physics, stage, config, ledger = setup(iterations=2, nodes=16)
    b = lm.fit_stage(FourierCurve.circle(2.), stage, .5, ScalarUpdate(),
                     replace(config, resolution_gate='absolute'), ledger, physics=physics)
    np.testing.assert_array_equal(a.curve.coefficients, b.curve.coefficients)
    assert a.acceptance_checks == b.acceptance_checks
    assert [(t.get('status'), t.get('backtrack')) for t in a.trials] == [(t.get('status'), t.get('backtrack')) for t in b.trials]


def test_endpoint_audit_is_independent_of_gate_and_fails_underresolution():
    from experiments.cleaned_interface.test_audit_streaming import fixture
    from bem_inverse.modal_muller import ModalMuller, ModalSettings, token
    from bem_inverse.geometry import ProjectedUpdate
    from bem_inverse.runner import audit
    p = fixture()
    stage = lm.FitStage('underresolved', p.real, (.2,)*5, (1e-5,)*3+(1e-7,)*2,
                        3, 8, token(4), token(8), 1)
    results = []
    for gate in ('absolute', 'decision'):
        physics = ModalMuller(Execution(device='cpu', frequency_threads=1),
                             ModalSettings(trace_minimum=4, trace_step=4, window_margin=16))
        results.append(audit(p.initial, stage, lm.BackendConfig(resolution_gate=gate), p, physics,
                             ProjectedUpdate(.05), 30.))
    assert not results[0]['passed'] and not results[1]['passed']
    assert 'field_relative' in results[0]
    for field in ('field_relative', 'jacobian_relative', 'full_trial_fd_relative', 'relative_residual'):
        np.testing.assert_array_equal(results[0][field], results[1][field])
