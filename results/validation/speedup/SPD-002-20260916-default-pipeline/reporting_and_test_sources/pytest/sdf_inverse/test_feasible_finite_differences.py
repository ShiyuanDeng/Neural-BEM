"""A probe the constraint refuses is not a derivative of zero.

Every test here uses an analytic residual with a known Jacobian, so the stencil,
its sign convention and the stopping semantics are checked without a BIE solve.
"""
import numpy as np
import pytest

import run_fourier_topology_controller as driver
from sdf_inverse import MultiRadialFourierState
from sdf_inverse.curve_updates import RadialFourierCurveState
from sdf_inverse.radial_topology import (
    MultiRadialObjectiveEvaluation, component_radius_floor, run_multiradial_fd_inverse,
)
from sdf_inverse import radial_topology
from sdf_inverse.optimization import ParameterFDConfig
from sdf_inverse.topology_controller import TopologyControllerConfig

SOLVE = driver.baseline.iteration01_solve_config()
PRODUCTION = driver.baseline._geometry_config(64)
FLOOR = .03
# Reachable only by growing: the floor blocks the inward probe, and the defect
# freezes that column rather than measuring the outward one.
TARGET = dict(radius_m=.035, center=(.5, .5))


def objective_for(target_radius_m):
    """Residual linear in mean radius and centre, so the Jacobian is exact.

    Linear means a central and a one-sided quotient must agree to rounding, so
    any disagreement between them is the stencil and not curvature. The centre
    entries keep the Jacobian non-degenerate: without them every column would be
    zero and a frozen one would be indistinguishable from a measured one.
    """
    def evaluate(state, data, geometry_config, *, solve_config=None):
        component = state.components[0]
        residual = 50. * np.array([
            float(component.mean_radius_m) - target_radius_m,
            float(component.center[0]) - TARGET['center'][0],
            float(component.center[1]) - TARGET['center'][1],
        ])
        return MultiRadialObjectiveEvaluation(
            state=state, loss=.5 * float(residual @ residual),
            relative_l2_error=float(np.linalg.norm(residual)), residual=residual,
            prediction=np.zeros(1, dtype=complex), maximum_system_residual=0., forward_seconds=0.)
    return evaluate


def circle(radius_m, *, modes=1, center=(.5, .5)):
    """A circle carrying harmonics up to ``modes``, all zero.

    With zero harmonics the radial certificate is the mean radius, so a circle
    at the floor is exactly on the constraint. Mode 1 is the translation gauge
    and carries no free parameter, so ``modes=1`` leaves the radius as the only
    constrained direction. From ``modes=2`` the free harmonics are the case the
    verdict singles out: the certificate subtracts a norm, so moving a zero
    coefficient *either* way lowers it and both probes are refused.
    """
    return MultiRadialFourierState((RadialFourierCurveState(
        center=np.asarray(center, dtype=float),
        radius_cosine_coefficients=np.array([radius_m] + [0.] * modes),
        radius_sine_coefficients=np.zeros(modes + 1),
        component_id='only'),))


def optimizer_config(**overrides):
    settings = dict(max_iterations=6, finite_difference_steps=1.e-4, max_steps=6.e-3,
        initial_damping=1.e-3, max_damping_trials=5, max_backtracks=7, gradient_tolerance=1.e-7,
        loss_tolerance=1.e-10, relative_step_tolerance=1.e-7, max_parameters=64,
        infeasible_trial_policy='reject')
    settings.update(overrides)
    return ParameterFDConfig(**settings)


def run(state, *, floor, feasible_fd, **overrides):
    return run_multiradial_fd_inverse(
        state, None, PRODUCTION, solve_config=SOLVE, config=optimizer_config(**overrides),
        minimum_component_radius_m=floor, feasible_fd_jacobian=feasible_fd,
        cartesian_gauge=False)


def final_radius(result):
    return float(result.final_state.components[0].mean_radius_m)


@pytest.fixture(autouse=True)
def analytic_objective(monkeypatch):
    monkeypatch.setattr(radial_topology, 'evaluate_multiradial_objective',
                        objective_for(TARGET['radius_m']))


@pytest.fixture
def unreachable_target(monkeypatch):
    """An optimum inside the floor, so the state stays pinned to the constraint.

    With a reachable target the run grows past the floor within one step and
    every column becomes measurable again -- which is the correct answer, and
    the wrong setting in which to test what happens while a column is still
    unresolved.
    """
    monkeypatch.setattr(radial_topology, 'evaluate_multiradial_objective',
                        objective_for(FLOOR - .005))


# --- the defect, and the escape it blocks --------------------------------

def test_the_defect_freezes_a_column_and_then_calls_it_convergence():
    """Both faults in one run, recorded so the correction has a reference."""
    result = run(circle(FLOOR), floor=FLOOR, feasible_fd=False)
    assert result.unresolved_jacobian_column_count > 0
    assert result.one_sided_jacobian_column_count == 0
    # The radius never moves: its column was frozen, so the model reports no
    # reason to grow. The target is 5 mm away and outward is feasible the whole
    # time.
    assert final_radius(result) == pytest.approx(FLOOR, abs=1.e-12)
    # And the run then certifies itself, from a gradient whose radius entry is a
    # zero nothing measured.
    assert (result.stop_reason, result.converged) == ('gradient_tolerance', True)


def test_the_correction_reaches_the_target_the_defect_pinned():
    """The same state and the same floor, with the feasible side measured."""
    result = run(circle(FLOOR), floor=FLOOR, feasible_fd=True)
    assert result.one_sided_jacobian_column_count > 0
    assert result.unresolved_jacobian_column_count == 0
    assert final_radius(result) == pytest.approx(TARGET['radius_m'], abs=1.e-6)


def test_one_sided_and_central_agree_on_a_linear_residual():
    """Both stencils estimate +Jd; on a linear residual they agree exactly.

    This is the sign convention under test. A backward difference formed as
    ``(r(x - hd) - r(x)) / h`` comes out negated and would still look plausible
    in a norm, so the comparison is against the unconstrained central answer.
    """
    free = run(circle(FLOOR), floor=0., feasible_fd=True, max_iterations=1)
    pinned = run(circle(FLOOR), floor=FLOOR, feasible_fd=True, max_iterations=1)
    assert free.one_sided_jacobian_column_count == 0
    assert pinned.one_sided_jacobian_column_count > 0
    # Iteration zero records the gradient assembled before any step is taken.
    np.testing.assert_allclose(free.iterations[0].gradient, pinned.iterations[0].gradient,
                               rtol=1.e-6, atol=1.e-9)


def test_a_direction_blocked_on_both_sides_stays_unresolved():
    """The correction claims nothing where nothing was measured."""
    result = run(circle(FLOOR, modes=2), floor=FLOOR, feasible_fd=True, max_iterations=1)
    # The radius has a feasible side; the two zero harmonics have neither.
    assert result.one_sided_jacobian_column_count > 0
    assert result.unresolved_jacobian_column_count > 0


# --- stopping semantics --------------------------------------------------

def test_a_gradient_built_from_unresolved_columns_is_not_convergence(unreachable_target):
    """The branch the verdict identified: gradient_tolerance never checked."""
    result = run(circle(FLOOR, modes=2), floor=FLOOR, feasible_fd=True, gradient_tolerance=1.e9)
    assert result.unresolved_jacobian_column_count > 0
    assert (result.stop_reason, result.converged) == ('infeasible_jacobian', False)


def test_the_legacy_path_keeps_its_historical_answer(unreachable_target):
    """Off must reproduce the recorded arms, including the branch that is wrong."""
    result = run(circle(FLOOR, modes=2), floor=FLOOR, feasible_fd=False, gradient_tolerance=1.e9)
    assert (result.stop_reason, result.converged) == ('gradient_tolerance', True)


def test_resolving_every_column_still_certifies_convergence(unreachable_target):
    """The correction must not turn a genuinely measured gradient into a stop."""
    result = run(circle(FLOOR, modes=2), floor=0., feasible_fd=True, gradient_tolerance=1.e9)
    assert result.unresolved_jacobian_column_count == 0
    assert (result.stop_reason, result.converged) == ('gradient_tolerance', True)


def test_an_unconstrained_run_is_unchanged_by_the_flag():
    """No active constraint means no one-sided column and no behaviour change."""
    off = run(circle(FLOOR), floor=0., feasible_fd=False)
    on = run(circle(FLOOR), floor=0., feasible_fd=True)
    assert on.one_sided_jacobian_column_count == 0
    assert (off.stop_reason, off.converged) == (on.stop_reason, on.converged)
    np.testing.assert_allclose(off.final_state.parameter_vector(),
                               on.final_state.parameter_vector(), rtol=0., atol=0.)


def test_the_correction_does_not_move_the_feasible_set():
    """Whatever the stencil, the floor still holds at the returned state."""
    result = run(circle(FLOOR), floor=FLOOR, feasible_fd=True)
    assert all(component_radius_floor(c) >= FLOOR - 1.e-12
               for c in result.final_state.components)


# --- plumbing ------------------------------------------------------------

def test_the_controller_flag_is_off_by_default_and_validated():
    assert TopologyControllerConfig().feasible_fd_jacobian is False
    with pytest.raises(ValueError, match='feasible_fd_jacobian must be boolean'):
        TopologyControllerConfig(feasible_fd_jacobian=1)
