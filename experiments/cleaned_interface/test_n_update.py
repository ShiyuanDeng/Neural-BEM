"""NU-001 coefficient normal update: identities, validity tiers, control and runner substitution."""
from dataclasses import replace

import numpy as np
import pytest

from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, fit_stage
from experiments.shape_continuation.updates import UpdateRefused
from . import benchmark as b
from . import runner
from .geometry import ProjectedUpdate, resize, values
from .io import read, curve_from
from .n_update import NormalUpdate, basis_products, tangential_terms, curve_certificate, signed_area
from .n_update_audit import (ArmPolicy, ARMS, arm_substitution, baseline_linearization, control_state,
                             CumulativePolicy)
from .physics import Execution, make_backend
from .policy import Operation
from .problem import Observation


def saved_state(case='core__kite', stage='release_M19'):
    states = read(b.ROOT/f'results/validation/cleaned_interfaces/CI-001/runs/{case}/accepted.json')['states']
    state = [s for s in states if s['stage'] == stage][-1]
    return curve_from(state['curve']), state['M']


def grid_basis(theta, M):
    phase = theta[:, None]*np.arange(1, M+1)
    return np.column_stack((np.ones(len(theta)), np.cos(phase), np.sin(phase)))


def test_basis_products_are_exact_shifts():
    rng = np.random.default_rng(1)
    poly = rng.normal(size=9)+1j*rng.normal(size=9)
    out = basis_products(poly, 3)
    theta = 2*np.pi*np.arange(64)/64
    np.testing.assert_allclose(values(out.T, 64), grid_basis(theta, 3)*values(poly[:, None], 64), atol=1e-12)


def test_circle_step_is_exact_metres():
    curve = resize(FourierCurve.circle(1.3, .2+.1j), 8)
    update = NormalUpdate(.05)
    space = update.prepare(curve, 3, 8)
    candidate, info = update.trial(space, np.r_[1e-3, np.zeros(6)])
    assert abs(abs(candidate.coefficients[9])*.05-(1.3*.05+1e-3)) < 1e-15
    assert info['maximum_normal_m'] == pytest.approx(1e-3, rel=1e-12)
    assert update.trial(space, np.zeros(7))[0] is curve


@pytest.mark.parametrize('tangential', [False, True])
def test_weights_identity_lemma1_and_affine_trial(tangential):
    curve, M = saved_state()
    update = NormalUpdate(.05, tangential=tangential)
    space = update.prepare(curve, M, curve.band)
    count = 2048
    theta = 2*np.pi*np.arange(count)/count
    normal = values((curve.modes*curve.coefficients)[:, None], count)[:, 0]
    weights = (values(space.derivatives, count)*np.conj(normal)[:, None]).real*space.mean_speed*.05
    expected = grid_basis(theta, M)*(np.abs(normal)**2)[:, None]       # eq. 3: phi_q S
    assert np.max(np.abs(weights-expected))/np.max(np.abs(expected)) < 1e-9
    if tangential:
        moves, _ = tangential_terms(curve.coefficients, M, space.mean_speed**2)
        band = (moves.shape[1]-1)//2
        assert 2*band < 4096
        tangent = (values(moves.T, 4096)*np.conj(values((curve.modes*curve.coefficients)[:, None], 4096))).real
        assert np.max(np.abs(tangent)) < 1e-12*np.max(np.abs(values(moves.T, 4096)))   # Lemma 1
    step = np.random.default_rng(3).normal(size=2*M+1)*1e-4
    plus, minus = [update.trial(space, s*step)[0].coefficients for s in (1, -1)]
    np.testing.assert_allclose((plus-minus)/2, space.derivatives@step, atol=1e-15)


def test_tangential_term_holds_uniform_speed_to_first_order():
    # On an arclength-parametrized curve, arm B's first-order speed change is uniform (a constant).
    curve, M = saved_state()
    from experiments.shape_continuation.geometry import reparameterize
    curve, _ = reparameterize(curve, curve.band)
    update = NormalUpdate(.05, tangential=True)
    space = update.prepare(curve, M, curve.band)
    plain = NormalUpdate(.05).prepare(curve, M, curve.band)
    count = 4096
    speed = lambda c: np.abs(FourierCurve(c).values(count, 1))**2
    eps = 1e-6
    for q in (3, M+5):
        a = np.zeros(2*M+1)
        a[q] = eps
        vary = lambda s: (speed(curve.coefficients+s.derivatives@a)-speed(curve.coefficients-s.derivatives@a))/(2*eps)
        with_term, without = vary(space), vary(plain)
        assert np.std(with_term) < .05*np.std(without)


def test_validity_tiers_refuse_and_certify():
    curve, M = saved_state('core__kite', 'stage_2_damped')
    update = NormalUpdate(.05, certificate_window=32)
    space = update.prepare(curve, M, curve.band)
    assert space.certificate['rho'] < 1
    small = np.zeros(2*M+1)
    small[0] = 1e-5
    _, info = update.trial(space, small)
    assert info['validity_tier'] == 'incremental_certificate'
    FourierCurve(curve.coefficients+space.derivatives@small).validate()   # the certificate is sufficient
    clockwise = curve.coefficients[::-1]
    with pytest.raises(UpdateRefused, match='exact signed area') as refused:
        update.validate(space, clockwise-curve.coefficients, clockwise)
    assert refused.value.reason == 'irregular_parameterization'
    large = np.zeros(2*M+1)
    large[M] = .03                                         # a big cos(M theta) fold
    with pytest.raises(UpdateRefused):
        update.trial(space, large)
    assert update.counts['tier_certificate_accepted'] == 1 and update.counts['refused_trials'] == 1
    assert update.counts['tier_area_refused'] == 1


def test_signed_area_and_certificate_match_modal_geometry():
    from .modal_geometry import ModalGeometry
    curve, _ = saved_state('core__hook', 'stage_2_damped')
    geometry = ModalGeometry(curve, 32)
    cert = curve_certificate(curve, 32, tolerance=1e-16)
    assert cert['beta'] == geometry.log_interval['lower']
    assert signed_area(curve.coefficients) > 0


@pytest.mark.parametrize('stage', ['stage_2_damped', 'release_M19'])
def test_baseline_linearization_reproduces_projected_fd_columns(stage):
    curve, M = saved_state('core__kite', stage)
    fd = ProjectedUpdate(.05).prepare(curve, M, curve.band).derivatives
    linear = baseline_linearization(curve, M, .05)
    assert np.max(np.linalg.norm(fd-linear, axis=0)/np.linalg.norm(linear, axis=0)) < 1e-6


def test_control_row_shows_arclength_hybrid_is_not_the_baseline_basis():
    curve, M = saved_state('core__hook', 'fixed_M37')
    row = control_state(curve, M)
    assert row['baseline_fd_vs_linearization']['max'] < 1e-6
    vs = row['baseline_weights_vs']
    assert vs['arclength_hybrid']['median'] > 5*vs['theta_unit_normal']['median']
    assert row['n_update_weights_vs_eq3']['max'] < 1e-10


def test_physics_complete_trial_derivative_with_n_update():
    backend = make_backend(execution_settings=Execution(device='cpu', frequency_threads=1))
    observation = Observation(1.2, b.acquisition(), np.ones(24, complex), .5e9)
    curve = resize(FourierCurve(np.r_[0, .03j, .05, .03+.02j, 1.02, .04, -.02j]), 8)
    state = backend.evaluate(curve, observation, .5, 128)
    for tangential in (False, True):
        update = NormalUpdate(.05, tangential=tangential)
        space = update.prepare(curve, 3, 8)
        jacobian = backend.derivative(state, update, space)
        direction = np.random.default_rng(42).normal(size=7)
        direction /= np.linalg.norm(direction)
        plus, minus = [backend.evaluate(update.trial(space, s*1e-7*direction)[0], observation, .5, 128).prediction
                       for s in (1, -1)]
        fd = (plus-minus)/2e-7
        assert np.linalg.norm(fd-jacobian@direction)/np.linalg.norm(fd) < 1e-3


def test_lm_stage_runs_with_n_update():
    from experiments.shape_continuation import forward as F
    scan = b.acquisition()
    target = FourierCurve.circle(1.0)
    obs = (Observation(1.2, scan, F.solve(target, 1.2, .5, scan, 128, execution_backend='cpu').prediction, .5e9),)
    stage = FitStage('equivalence', obs, (1.,), (1e-5,), 3, 8, 64, 128, 3, 300)
    backend = make_backend(execution_settings=Execution(device='cpu', frequency_threads=1))
    ledger = Ledger(cap=400, seconds=120)
    ledger.begin_stage(stage.label, stage.quota)
    update = NormalUpdate(.05, certificate_window=32)
    result = fit_stage(resize(FourierCurve.circle(1.03, .01j), 8), stage, .5, update, BackendConfig(), ledger,
                       physics=backend)
    assert result.accepted_steps >= 1 and result.final_loss < result.initial_loss
    assert all('validity_tier' in t for t in result.trials if t.get('status') == 'accepted')


def test_arm_policy_records_update_and_only_changes_time_caps():
    p = b.fitting_problem(next(r for r in b.descriptors() if r['id'] == 'modal__c4__development_c'), b.DEFAULT_OUTPUT)
    backend = make_backend(execution_settings=Execution(device='cpu'))
    base, arm = CumulativePolicy(), ArmPolicy(geometry_update=ARMS['A']['construction'])
    a, c = base.operations(p, backend), arm.operations(p, backend)
    assert [o.kind for o in a] == [o.kind for o in c] and [o.stage for o in a] == [o.stage for o in c]
    assert all(r.get('geometry_update', ARMS['A']['construction']) == ARMS['A']['construction']
               for r in (o.record() for o in c))
    assert arm.plan(p, backend)['operations'] == [o.record() for o in c]
    assert all(t.record()['geometry_update'] == ARMS['A']['construction']
               for t in arm.tail(p, backend, 95) if t.kind == 'fit')
    changed = {k for k in base.__dataclass_fields__ if getattr(base, k) != getattr(arm, k)}
    assert changed == {'fit_seconds', 'audit_seconds'}
    saved = runner.ProjectedUpdate, runner.CumulativePolicy
    with arm_substitution('B'):
        assert runner.ProjectedUpdate(.05).name == 'coefficient_normal_hls'
        assert isinstance(runner.CumulativePolicy(), ArmPolicy)
    assert (runner.ProjectedUpdate, runner.CumulativePolicy) == saved


def test_runner_end_to_end_under_arm_substitution(tmp_path):
    from .runner import fit
    from .problem import Problem
    from .physics import NodalKress
    from .policy import LocalizationRule

    class SmallBackend(NodalKress):
        def resolution_profile(self, storage_band):
            row = super().resolution_profile(storage_band)
            row.update(production=64, refined=128, nodal_resolution=64)
            return row

    class ShortPolicy(ArmPolicy):
        def operations(self, p, physics):
            ops = super().operations(p, physics)
            fits = [o for o in ops if o.kind == 'fit']
            warm = replace(fits[0], stage=replace(fits[0].stage, iterations=1))
            next_fit = replace(fits[1], stage=replace(fits[1].stage, iterations=1))
            return (ops[0], ops[1], warm, next_fit, ops[-2], ops[-1])

        def tail(self, p, physics, frontier):
            return ()
    backend = SmallBackend(Execution(device='cpu', frequency_threads=1))
    template = b.fitting_problem(next(r for r in b.descriptors() if r['id'] == 'modal__c4__development_c'),
                                 b.DEFAULT_OUTPUT)
    truth = FourierCurve.circle()
    real = tuple(replace(o, scattered=backend.evaluate(truth, o, .5, 128).prediction) for o in template.real)
    damped = tuple(replace(o, scattered=backend.evaluate(truth, o, .5, 128).prediction) for o in template.damped)
    p = Problem(FourierCurve.circle(1.02), real, damped, .5)
    policy = ShortPolicy(storage_band=24, frontier_top=7, geometry_update=ARMS['A']['construction'],
        localization=LocalizationRule(center_min_m=.5, center_max_m=.5, center_step_m=.004,
            radius_min_m=.05, radius_max_m=.05, radius_step_m=.001, max_starts=1, refinement_iterations=1))
    with arm_substitution('A'):
        result = fit(p, physics=backend, policy=policy, output=tmp_path)
    assert result['outcome'] == 'COMPLETED_SCHEDULE', result['detail']
    assert result['initial_audit_passed'] and result['final_audit_passed']
    assert read(tmp_path/'configuration.json')['update']['name'] == 'coefficient_normal'
    assert result['geometry_work']['geometry_projections'] == 0
