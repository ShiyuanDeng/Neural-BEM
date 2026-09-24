"""Legacy single-object step safeguards in the fixed-topology SPD LM (SC-034).

The physics-free objective below isolates the step logic: it refuses
inadmissible geometry exactly like the real objective and has a residual that
is linear in the gauge-fixed coordinates.
"""
import numpy as np
import pytest

import run_fourier_topology_controller as driver
from gpr_bem_kress.multicomponent import MultiComponentTopologyError
from sdf_inverse import radial_topology
from sdf_inverse.curve_updates import cartesian_fourier_displacement_basis
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.optimization import ParameterFDConfig
from sdf_inverse.radial_topology import (
    MultiRadialFourierState, MultiRadialObjectiveEvaluation, StepSafeguards,
    gauge_normal_displacement_operator, gauge_radial_orders, multiradial_geometry_admissible,
    run_multiradial_fd_inverse,
)

SOLVE = driver.baseline.iteration01_solve_config()
PRODUCTION = driver.baseline._geometry_config(64)
MODES = 6


def state(center=(.48, .52), radius=.065, modes=MODES):
    return MultiRadialFourierState((circle_cartesian_fourier_state(center, radius, 'one', maximum_mode=modes),))


def star_state(modes=MODES, amplitude=.004):
    """A gauge-fixed radial-mode-4 perturbation of the true circle."""
    base = state((.5, .5), .05, modes)
    step = np.zeros(len(base.gauge_tangent_basis()))
    step[3 + 2 * (4 - 2)] = amplitude
    return base.incremented(base.gauge_tangent_basis().T @ step).polar_angle_gauge_fixed()[0]


def linear_objective(target, weights):
    target_reduced = target.gauge_tangent_basis() @ target.parameter_vector()

    def evaluate(current, data, geometry_config, *, solve_config=None, **_):
        if not multiradial_geometry_admissible(current, geometry_config, solve_config=solve_config):
            raise MultiComponentTopologyError('synthetic objective: inadmissible geometry.')
        reduced = current.gauge_tangent_basis() @ current.parameter_vector()
        residual = weights * (reduced - target_reduced)
        return MultiRadialObjectiveEvaluation(
            state=current, loss=.5 * float(residual @ residual), relative_l2_error=float(np.linalg.norm(residual)),
            residual=residual, prediction=np.zeros(1, complex), maximum_system_residual=0., forward_seconds=0.)
    return evaluate


def optimizer(iterations=6):
    return ParameterFDConfig(max_iterations=iterations, finite_difference_steps=1.e-5, max_steps=2.e-2,
        initial_damping=1.e-3, max_damping_trials=5, max_backtracks=7, gradient_tolerance=1.e-12,
        loss_tolerance=1.e-16, relative_step_tolerance=1.e-12, max_parameters=64,
        infeasible_trial_policy='reject')


def run(monkeypatch, safeguards=None, iterations=6, target=None, events=None, **kw):
    target = star_state() if target is None else target
    weights = np.r_[50., 50., 50., np.full(len(target.gauge_tangent_basis()) - 3, 20.)]
    monkeypatch.setattr(radial_topology, 'evaluate_multiradial_objective', linear_objective(target, weights))
    extra = {} if safeguards is None else dict(step_safeguards=safeguards)
    callback = None if events is None else (lambda name, payload: events.append((name, payload)))
    return run_multiradial_fd_inverse(state(), None, PRODUCTION, solve_config=SOLVE, config=optimizer(iterations),
        cartesian_gauge=True, jacobian_mode='fd', diagnostic_callback=callback, **extra, **kw)


def test_gauge_directions_are_unit_radial_harmonics_in_order():
    current = state(modes=7)
    basis = current.gauge_tangent_basis()
    orders = gauge_radial_orders(current)
    assert orders.tolist() == [0, 0, 0, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6]
    np.testing.assert_allclose(basis @ basis.T, np.eye(len(basis)), atol=1e-12)
    angles = 2 * np.pi * np.arange(512) / 512
    radial = np.column_stack((np.cos(angles), np.sin(angles)))
    displacement = cartesian_fourier_displacement_basis(angles, maximum_mode=7)
    for index in range(3, len(basis)):
        move = np.einsum('npd,p->nd', displacement, basis[index])
        amplitude = np.einsum('nd,nd->n', move, radial)
        mode, trig = int(orders[index]), (np.cos if index % 2 else np.sin)
        # A unit reduced coordinate is a 1 m radial harmonic of that order, with no tangential part.
        assert abs(abs(amplitude @ trig(mode * angles)) / 256 - 1) < 1e-12
        np.testing.assert_allclose(move, amplitude[:, None] * radial, atol=1e-12)


def test_normal_displacement_operator_matches_exact_curve_difference():
    current = star_state(modes=7, amplitude=.006)
    basis = current.gauge_tangent_basis()
    operator = gauge_normal_displacement_operator(current, basis, 512)
    rng = np.random.default_rng(3)
    step = 1e-3 * rng.standard_normal(len(basis))
    component = current.components[0]
    moved = current.incremented(basis.T @ step).components[0]
    angles = 2 * np.pi * np.arange(len(operator)) / len(operator)
    points = lambda c: cartesian_fourier_displacement_basis(angles, maximum_mode=7).transpose(0, 2, 1) @ c.parameter_vector()
    orders = np.arange(8)
    tangent = (-(np.sin(np.outer(angles, orders)) * orders) @ component.cosine_coefficients
               + (np.cos(np.outer(angles, orders)) * orders) @ component.sine_coefficients)
    normals = np.column_stack((tangent[:, 1], -tangent[:, 0])) / np.linalg.norm(tangent, axis=1)[:, None]
    exact = np.einsum('nd,nd->n', points(moved) - points(component), normals)
    np.testing.assert_allclose(operator @ step, exact, atol=1e-15)


def test_safeguards_require_the_cartesian_gauge():
    with pytest.raises(ValueError, match='cartesian_gauge'):
        run_multiradial_fd_inverse(state(), None, PRODUCTION, solve_config=SOLVE, config=optimizer(),
            cartesian_gauge=False, step_safeguards=StepSafeguards())
    with pytest.raises(ValueError, match='positive or None'):
        StepSafeguards(maximum_normal_displacement_m=0.)
    with pytest.raises(ValueError, match='smaller than one'):
        StepSafeguards(armijo_coefficient=1.)


def test_inert_safeguards_reproduce_the_historical_path(monkeypatch):
    inert = StepSafeguards(curvature_penalty_weight=0., minimum_damping=0., maximum_normal_displacement_m=None,
                           armijo_coefficient=0.)
    default, off = run(monkeypatch), run(monkeypatch, inert)
    assert len(default.iterations) == len(off.iterations) > 1
    for a, b in zip(default.iterations, off.iterations):
        np.testing.assert_array_equal(a.parameter_vector, b.parameter_vector)
        assert a.loss == b.loss and a.damping == b.damping
    assert default.stop_reason == off.stop_reason


def test_accepted_steps_respect_the_normal_bound_floor_and_armijo(monkeypatch):
    unbounded = run(monkeypatch, iterations=2)
    first = unbounded.iterations[1]
    basis = unbounded.iterations[0].state.gauge_tangent_basis()
    free_move = np.max(np.abs(gauge_normal_displacement_operator(unbounded.iterations[0].state, basis)
                              @ (basis @ first.step)))
    assert free_move > 5e-3  # The historical path takes a much larger first move.

    events = []
    guarded = run(monkeypatch, StepSafeguards(), iterations=8, events=events)
    assert len(guarded.iterations) == 9
    for before, after in zip(guarded.iterations, guarded.iterations[1:]):
        basis = before.state.gauge_tangent_basis()
        move = gauge_normal_displacement_operator(before.state, basis) @ (basis @ after.step)
        assert np.max(np.abs(move)) <= 2e-3 * (1 + 1e-9)
        assert after.damping >= 1e-6
        assert after.loss < before.loss
    proposals = [p for name, p in events if name == 'step_safeguards' and p['kind'] == 'proposal']
    assert proposals and max(p['maximum_normal_displacement_m'] for p in proposals) <= 2e-3 * (1 + 1e-9)
    # The bound is active: the search had to raise the damping above the carried value.
    assert max(p['damping'] for p in proposals) > 1e-3
    # Armijo on every accepted step: realized <= 1e-4 * (g . d), with g the
    # gradient recorded at the state the step left.
    for before, after in zip(guarded.iterations, guarded.iterations[1:]):
        predicted = float(before.gradient @ after.step)
        assert predicted < 0 and after.loss - before.loss <= 1e-4 * predicted


def test_damping_floor_replaces_the_machine_tiny_floor(monkeypatch):
    target = state((.5, .5), .05)
    weights = np.full(len(target.gauge_tangent_basis()), 50.)
    monkeypatch.setattr(radial_topology, 'evaluate_multiradial_objective', linear_objective(target, weights))
    config = ParameterFDConfig(max_iterations=3, finite_difference_steps=1.e-5, max_steps=2.e-2,
        initial_damping=1.e-3, damping_decrease=1.e-3, max_damping_trials=5, max_backtracks=7,
        gradient_tolerance=1.e-30, loss_tolerance=1.e-30, relative_step_tolerance=1.e-30, max_parameters=64,
        infeasible_trial_policy='reject')
    arms = [run_multiradial_fd_inverse(state((.5, .5), .0501), None, PRODUCTION, solve_config=SOLVE,
                config=config, cartesian_gauge=True, jacobian_mode='fd', loss_change_stopping=False, **extra)
            for extra in ({}, dict(step_safeguards=StepSafeguards(minimum_damping=1e-5)))]
    assert arms[0].iterations[2].damping == pytest.approx(1e-6)
    assert arms[1].iterations[2].damping == pytest.approx(1e-5)
