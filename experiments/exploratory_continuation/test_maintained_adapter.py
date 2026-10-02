"""Tests of the extension's information contract and coupled complete derivative."""
from dataclasses import replace
import numpy as np
import pytest

from experiments.cleaned_interface.physics import Execution
from experiments.cleaned_interface.policy import CumulativePolicy
from experiments.cleaned_interface.problem import Observation, Problem
from experiments.shape_continuation import forward as F
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.multi_object import MultiCurve
from .maintained_adapter import CoupledGeometry, CoupledNodalKress, CoupledCumulativePolicy


def inputs(damping=0):
    theta = np.linspace(0, 2*np.pi, 12, endpoint=False)
    sources = 5*np.column_stack((np.cos(theta), np.sin(theta)))
    scan = F.PointSourceAcquisition(sources, 1.1*np.roll(sources, 1, axis=0), 1e-6)
    shape = MultiCurve((FourierCurve.circle(.6, -1.2+.1j), FourierCurve.circle(.5, 1.3-.1j)), ('a', 'b'))
    shape = CoupledGeometry.resize(shape, 8)
    real = tuple(Observation(k, scan, np.ones(12, complex), f) for k, f in
                 zip((.5, .75, 1, 1.5, 2), (.25e9, .375e9, .5e9, .75e9, 1e9)))
    damped = tuple(replace(o, wavenumber=o.wavenumber*(1+1j*damping)) for o in real)
    return Problem(shape, real, damped, .5, damping_ratio=damping)


def test_real_alias_requires_explicit_contract_and_does_not_add_observations():
    p = inputs()
    assert all(a.wavenumber == b.wavenumber for a, b in zip(p.real, p.damped))
    with pytest.raises(ValueError, match='Damped catalog'):
        replace(p, damping_ratio=.25)
    with pytest.raises(ValueError, match='nonnegative'):
        replace(p, damping_ratio=-.1)
    backend = CoupledNodalKress(Execution(device='cpu', frequency_threads=1))
    backend.validate(p)


def test_coupled_policy_keeps_actual_maintained_fit_cleanup_and_tail_operations():
    p = inputs()
    physics = CoupledNodalKress(Execution(device='cpu', frequency_threads=1))
    kwargs = dict(gamma=0., prefix_frequencies_hz=(.375e9, .5e9, .75e9, 1e9))
    actual, base = CoupledCumulativePolicy(**kwargs), CumulativePolicy(**kwargs)
    a, b = actual.operations(p, physics), base.operations(p, physics)
    assert [o.stage for o in a if o.kind == 'fit'] == [o.stage for o in b if o.kind == 'fit']
    assert [o.optimizer for o in a if o.kind == 'fit'] == [o.optimizer for o in b if o.kind == 'fit']
    assert [o.kind for o in a] == [o.kind for o in b]
    assert actual.tail(p, physics, 95) == base.tail(p, physics, 95)
    assert actual.plan(p, physics)['adaptations']['frozen_default_reproduction'] is False


def test_matched_arms_use_common_numerics_and_no_heldouts():
    from .maintained_matched import MatchedPolicy
    p = inputs()
    physics = CoupledNodalKress(Execution(device='cpu', frequency_threads=1))
    for kind in ('cumulative', 'rla', 'scif'):
        policy = MatchedPolicy(kind=kind, gamma=0., fit_units=512,
            prefix_frequencies_hz=(.375e9, .5e9, .75e9, 1e9))
        ops = policy.operations(p, physics)
        for op in (op for op in ops if op.kind == 'fit'):
            assert (op.stage.curve_modes, op.stage.nodes, op.stage.refined_nodes, op.stage.iterations) == (192, 512, 1024, 22)
            assert all(o.frequency_hz <= 1e9 and complex(o.wavenumber).imag == 0 for o in op.stage.observations)
        if kind == 'scif':
            assert policy.frequency_path(p)['completed']
            assert len([op for op in ops if op.kind == 'fit']) == 22


@pytest.mark.parametrize('damping', [0., .25])
def test_coupled_projected_trial_derivative_and_complex_service(damping):
    p = inputs(damping)
    physics = CoupledNodalKress(Execution(device='cpu', frequency_threads=1))
    o = p.damped[2]
    update = CoupledGeometry.update(.05)
    space = update.prepare(p.initial, 3, p.initial.band)
    state = physics.evaluate(p.initial, o, p.contrast, 64)
    jac = physics.derivative(state, update, space)
    direction = np.random.default_rng(48).normal(size=len(space.orders))
    direction /= np.linalg.norm(direction)
    plus, minus = [physics.evaluate(update.trial(space, sign*1e-7*direction)[0], o, p.contrast, 64).prediction
                   for sign in (1, -1)]
    fd = (plus-minus)/2e-7
    assert np.linalg.norm(fd-jac@direction)/np.linalg.norm(fd) < 1e-3
    restored = CoupledGeometry.restore(CoupledGeometry.record(p.initial))
    np.testing.assert_array_equal(restored.coefficients, p.initial.coefficients)
    assert restored.ids == p.initial.ids
    # Existing generic F.solve is independent of the service injection for real k.
    if not damping:
        np.testing.assert_array_equal(state.prediction,
            F.solve(p.initial, o.wavenumber, p.contrast, o.acquisition, 64, execution_backend='cpu').prediction)


def test_streaming_audit_matches_original_dense_audit_bitwise():
    from experiments.cleaned_interface.runner import audit
    from experiments.shape_continuation.lm_backend import FitStage, BackendConfig, Ledger, Objective
    p = inputs()
    stage = FitStage('audit_test', p.real, (.2,)*5, (1e-5,)*3+(1e-7,)*2, 3, 8, 64, 128, 1)
    config = BackendConfig()
    physics = CoupledNodalKress(Execution(device='cpu', frequency_threads=1))
    update = CoupledGeometry.update(.05)
    # Reproduce the pre-streaming Objective audit rather than copy new logic.
    ledger = Ledger(cap=46, seconds=300, endpoint_reserve=0)
    coarse = Objective(stage, p.contrast, config, ledger, physics=physics)
    fine = Objective(replace(stage, nodes=128, refined_nodes=256), p.contrast, config, ledger, physics=physics)
    low, high = coarse.production(p.initial, 'audit_base'), fine.production(p.initial, 'audit_fine')
    space = update.prepare(p.initial, 3, 8)
    ja, jb = coarse.jacobian(low, update, space), fine.jacobian(high, update, space)
    direction = np.random.default_rng(42001).normal(size=ja.shape[1]); direction /= np.linalg.norm(direction)
    plus, minus = [fine.production(update.trial(space, s*1e-7*direction)[0], 'audit_fd') for s in (1, -1)]
    fd = (plus.residual-minus.residual)/2e-7
    old = dict(field_relative=np.linalg.norm(low.prediction-high.prediction, axis=0)/np.linalg.norm(high.prediction, axis=0),
        jacobian_relative=np.linalg.norm(ja-jb, axis=0)/np.maximum(np.linalg.norm(jb, axis=0), 1e-30),
        jacobian_column_norm=np.linalg.norm(jb, axis=0),
        full_trial_fd_relative=float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30)),
        fine_loss=high.loss, relative_residual=np.linalg.norm(high.prediction-fine.observed, axis=0)/np.linalg.norm(fine.observed, axis=0))
    new = audit(p.initial, stage, config, p, physics, update, 300)
    for name, expected in old.items(): np.testing.assert_array_equal(new[name], expected)
    assert new['work']['work_units'] == ledger.units == 30
