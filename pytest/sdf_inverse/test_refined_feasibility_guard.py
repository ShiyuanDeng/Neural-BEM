"""The optimizer must not leave states the refined evaluation then refuses."""
import json
from pathlib import Path

import numpy as np
import pytest

import run_fourier_topology_controller as driver
from sdf_inverse import MultiRadialFourierState, circle_radial_fourier_state
from sdf_inverse.radial_topology import (
    MultiRadialObjectiveEvaluation, multiradial_geometry_admissible, run_multiradial_fd_inverse,
)
from sdf_inverse import radial_topology
from sdf_inverse.optimization import ParameterFDConfig
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, TopologyWorkspace, _run_topology_aware_fourier_inverse,
)
from sdf_inverse import topology_controller
from gpr_bem_kress.multicomponent import MultiComponentTopologyError

ROOT = Path(__file__).resolve().parents[2]
ABORTED = ROOT / ('results/validation/topology/TOP-006-20260911-scenes-v1/'
                  'runs/A/far-ellipse-star/checkpoint.json')
SOLVE = driver.baseline.iteration01_solve_config()
PRODUCTION = driver.baseline._geometry_config(64)
REFINED = driver.baseline._geometry_config(128)


def synthetic_objective(target_centers):
    """A cheap smooth objective, so feasibility is tested without any BIE solve.

    It refuses inadmissible geometry at its own resolution exactly as the real
    objective does, because that refusal is what defines the feasible set the
    unguarded optimizer searches.
    """
    def evaluate(state, data, geometry_config, *, solve_config=None):
        if not multiradial_geometry_admissible(state, geometry_config, solve_config=solve_config):
            raise MultiComponentTopologyError('synthetic objective: inadmissible geometry.')
        centers = np.array([np.asarray(c.center) for c in state.components])
        residual = 50. * (centers - np.asarray(target_centers)).ravel()
        return MultiRadialObjectiveEvaluation(
            state=state, loss=.5 * float(residual @ residual),
            relative_l2_error=float(np.linalg.norm(residual)), residual=residual,
            prediction=np.zeros(1, dtype=complex), maximum_system_residual=0., forward_seconds=0.)
    return evaluate


def two_circles(gap_m, radius_m=.03):
    offset = radius_m + gap_m / 2
    return MultiRadialFourierState((
        circle_radial_fourier_state((.5 - offset, .5), radius_m, 'left'),
        circle_radial_fourier_state((.5 + offset, .5), radius_m, 'right')))


def optimizer_config():
    return ParameterFDConfig(max_iterations=4, finite_difference_steps=1.e-4, max_steps=6.e-3,
        initial_damping=1.e-3, max_damping_trials=5, max_backtracks=7, gradient_tolerance=1.e-7,
        loss_tolerance=1.e-10, relative_step_tolerance=1.e-7, max_parameters=64,
        infeasible_trial_policy='reject')


def test_recorded_abort_state_is_admissible_at_production_and_refused_when_refined():
    """The measured TOP-006 abort, replayed from its saved state without physics."""
    state = driver.deserialize_state(json.loads(ABORTED.read_text())['state'])
    assert multiradial_geometry_admissible(state, PRODUCTION, solve_config=SOLVE)
    assert not multiradial_geometry_admissible(state, REFINED, solve_config=SOLVE)
    assert not multiradial_geometry_admissible(
        state, driver.baseline._geometry_config(256), solve_config=SOLVE)


def test_guarded_optimizer_refuses_that_state_the_unguarded_one_accepts(monkeypatch):
    monkeypatch.setattr(radial_topology, 'evaluate_multiradial_objective',
                        synthetic_objective([(.5, .5), (.5, .5), (.5, .5)]))
    state = driver.deserialize_state(json.loads(ABORTED.read_text())['state'])
    unguarded = run_multiradial_fd_inverse(state, None, PRODUCTION, solve_config=SOLVE,
        config=optimizer_config(), cartesian_gauge=True)
    assert unguarded.feasibility_rejected_trial_count == 0
    with pytest.raises(ValueError, match='not solver-ready'):
        run_multiradial_fd_inverse(state, None, PRODUCTION, solve_config=SOLVE,
            config=optimizer_config(), cartesian_gauge=True,
            feasibility_geometry_configs=(REFINED,))


def test_guard_is_inert_where_the_refined_resolution_refuses_nothing(monkeypatch):
    monkeypatch.setattr(radial_topology, 'evaluate_multiradial_objective',
                        synthetic_objective([(.44, .5), (.56, .5)]))
    arms = [run_multiradial_fd_inverse(two_circles(.05), None, PRODUCTION, solve_config=SOLVE,
                config=optimizer_config(), feasibility_geometry_configs=extra)
            for extra in ((), (REFINED,))]
    assert [arm.feasibility_rejected_trial_count for arm in arms] == [0, 0]
    assert arms[0].stop_reason == arms[1].stop_reason
    np.testing.assert_array_equal(arms[0].final_state.parameter_vector(),
                                  arms[1].final_state.parameter_vector())


def test_guarded_optimizer_stops_inside_the_refined_feasible_set_not_beyond_it(monkeypatch):
    """Pulled hard onto the clearance floor, each arm stops where its own checks bite."""
    monkeypatch.setattr(radial_topology, 'evaluate_multiradial_objective',
                        synthetic_objective([(.5, .5), (.5, .5)]))
    unguarded, guarded = [run_multiradial_fd_inverse(two_circles(.02), None, PRODUCTION,
        solve_config=SOLVE, config=optimizer_config(), feasibility_geometry_configs=extra)
        for extra in ((), (REFINED,))]
    assert unguarded.feasibility_rejected_trial_count == 0
    assert guarded.feasibility_rejected_trial_count > 0
    assert multiradial_geometry_admissible(unguarded.final_state, PRODUCTION, solve_config=SOLVE)
    assert multiradial_geometry_admissible(guarded.final_state, PRODUCTION, solve_config=SOLVE)
    assert multiradial_geometry_admissible(guarded.final_state, REFINED, solve_config=SOLVE)
    # Where the step ladder happens to stop short of the gap between the two
    # floors, both arms land on the same state; what differs is that the
    # guarded arm refused the trials that would have entered it. The recorded
    # abort above is the case where the unguarded arm entered it and stayed.


def stub_controller(monkeypatch, refined_raises):
    """Isolate the refined-base seam: no optimizer, no sensitivities, no candidates."""
    class Result:
        final_state = None
        stop_reason = 'stubbed'
        feasibility_rejected_trial_count = 0

    def objective(state, data, geometry, solve_config):
        if refined_raises and geometry is REFINED:
            raise MultiComponentTopologyError('components are too close for ordinary quadrature.')
        return 1., 1.

    def refinement(state, *args, **kwargs):
        Result.final_state = state
        return Result

    grid = np.zeros((2, 2), dtype=bool)
    workspace = TopologyWorkspace(np.zeros((2, 2, 2)), np.zeros(2), np.zeros(2), grid, grid,
                                  (), np.zeros((2, 2)), np.zeros((2, 2)), 1.)
    monkeypatch.setattr(topology_controller, 'topology_objective', objective)
    monkeypatch.setattr(topology_controller, 'run_multiradial_fd_inverse', refinement)
    monkeypatch.setattr(topology_controller, 'build_topology_workspace', lambda *a, **k: workspace)
    monkeypatch.setattr(topology_controller, 'generate_topology_candidates', lambda *a, **k: ((), ()))


def run_stubbed(guard):
    return _run_topology_aware_fourier_inverse(two_circles(.05), None, PRODUCTION, REFINED,
        solve_config=SOLVE, config=TopologyControllerConfig(
            chart='radial', maximum_cycles=2, refined_feasibility_guard=guard))


def test_refined_geometry_failure_stops_the_guarded_run_instead_of_aborting_it(monkeypatch):
    stub_controller(monkeypatch, refined_raises=True)
    result = run_stubbed(guard=True)
    assert result.stop_reason == 'refined_infeasible'
    assert result.passes[-1]['refined_base_loss'] is None
    assert 'too close' in result.passes[-1]['refined_base_reason']


def test_unguarded_refined_geometry_failure_keeps_its_recorded_behaviour(monkeypatch):
    stub_controller(monkeypatch, refined_raises=True)
    with pytest.raises(MultiComponentTopologyError):
        run_stubbed(guard=False)


def test_guard_records_its_rejections_only_when_it_is_switched_on(monkeypatch):
    stub_controller(monkeypatch, refined_raises=False)
    guarded, default = run_stubbed(guard=True), run_stubbed(guard=False)
    assert guarded.passes[0]['refined_feasibility_rejected_trials'] == 0
    assert guarded.passes[0]['refined_infeasible_rollback'] is False
    assert 'refined_feasibility_rejected_trials' not in default.passes[0]
    assert 'refined_infeasible_rollback' not in default.passes[0]


def test_state_the_refined_resolution_refuses_stops_a_guarded_run_without_an_anchor(monkeypatch):
    stub_controller(monkeypatch, refined_raises=False)
    monkeypatch.setattr(topology_controller, 'multiradial_geometry_admissible', lambda *a, **k: False)
    assert run_stubbed(guard=True).stop_reason == 'refined_infeasible'
