"""Allocation, replay and measured-work contracts for TOP-001."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

import run_radial_fourier_topology_inverse as baseline
from sdf_inverse import ComplexScatteredData, MultiRadialFourierState, circle_radial_fourier_state
import sdf_inverse.topology_controller as controller
from sdf_inverse.radial_topology import evaluate_multiradial_objective, run_multiradial_fd_inverse
from sdf_inverse.work_accounting import collect_work, accounted_call


def disk(cid, radius=.03):
    return MultiRadialFourierState((circle_radial_fourier_state((.5, .5), radius, cid),))


@pytest.mark.parametrize('count,winner,polished', [(1, 'first', ['first']),
                                                 (2, 'second', ['first', 'second'])])
def test_top_two_can_select_better_polished_candidate_without_reranking(monkeypatch, count, winner, polished):
    initial, first, second, third = [disk(name) for name in ('initial', 'first', 'second', 'third')]
    candidates = tuple(controller.TopologyCandidate('merge', s, ('initial',), s.component_ids,
                                                     -1., s.component_ids[0])
                       for s in (first, second, third))
    raw = {'initial': 1., 'first': .4, 'second': .5, 'third': .6}
    losses = {'first': .2, 'second': .01, 'third': .001}
    calls = []
    def objective(state, *args):
        return raw[state.component_ids[0]], 1.
    def optimize(state, *args, **kwargs):
        name = state.component_ids[0]
        assert name != 'initial', 'Replay must not optimize the saved pre-event state.'
        calls.append(name)
        loss = losses[name]
        raw[name] = loss
        return SimpleNamespace(final_state=state, iterations=[SimpleNamespace(loss=1.), SimpleNamespace(loss=loss)],
                               evaluation_count=13, infeasible_trial_count=0)
    monkeypatch.setattr(controller, 'topology_objective', objective)
    monkeypatch.setattr(controller, 'run_multiradial_fd_inverse', optimize)
    monkeypatch.setattr(controller, 'build_topology_workspace', lambda *args: None)
    monkeypatch.setattr(controller, 'generate_topology_candidates', lambda *args: (candidates, ()))
    result = controller.run_topology_aware_fourier_inverse(initial, None, None, None, solve_config=None,
        config=controller.TopologyControllerConfig(maximum_cycles=1, candidates_refined_per_group=count),
        replay_first_event=True)
    assert calls == polished
    assert result.events[0]['construction'] == winner
    assert result.frames[0].state is initial
    assert result.passes[0]['trigger'] == 'saved_pre_event_replay'


def test_work_counts_actual_uncached_bie_and_frequencies_and_ignores_empty_domain():
    state = disk('a')
    geometry, solve = baseline._geometry_config(32), baseline.iteration01_solve_config()
    problem = baseline._problem(np.array([.5e9, 1.5e9]))
    observed = baseline._oracle_response(np.array([[.51, .5]]), np.array([.032]), np.array([.5e9, 1.5e9]),
                                         component_ids=('truth',))
    data = ComplexScatteredData(problem, observed)
    with collect_work() as ledger:
        accounted_call('empty', controller.topology_objective, None, data, geometry, solve)
        result = accounted_call('optimizer', run_multiradial_fd_inverse, state, data, geometry,
            solve_config=solve, config=controller._optimizer_config(state, controller.TopologyControllerConfig(), 1))
        work = ledger.snapshot()
    assert work['totals']['evaluation_count'] == result.evaluation_count
    assert work['totals']['forward_evaluation_count'] == result.evaluation_count
    assert work['totals']['bie_frequency_solve_count'] == 2 * result.evaluation_count
    assert 'empty' not in work['stages']
    with collect_work() as fresh:
        with pytest.raises(TypeError):
            accounted_call('invalid', evaluate_multiradial_objective, state, data, None, solve_config=solve)
        assert fresh.snapshot()['totals']['evaluation_count'] == 1
        assert fresh.snapshot()['totals']['forward_evaluation_count'] == 0
    assert ledger.snapshot() == work


@pytest.mark.parametrize('kwargs', [dict(candidates_refined_per_group=0),
    dict(candidates_refined_per_group=1.0),
    dict(candidates_refined_per_group=True), dict(candidate_refinement_iterations=1.5),
    dict(candidate_refinement_iterations=True)])
def test_allocation_config_rejects_invalid_budgets(kwargs):
    with pytest.raises(ValueError):
        controller.TopologyControllerConfig(**kwargs)


def test_topological_derivative_counts_rhs_batches_not_field_points():
    from sdf_inverse.radial_topology import evaluate_current_domain_topological_derivative
    state = disk('a')
    frequencies = np.array([.5e9, 1.5e9])
    problem = baseline._problem(frequencies)
    observed = baseline._oracle_response(np.array([[.51, .5]]), np.array([.032]), frequencies,
                                         component_ids=('truth',))
    data = ComplexScatteredData(problem, observed)
    with collect_work() as ledger:
        for current in (None, state):
            accounted_call('TD', evaluate_current_domain_topological_derivative, current, data,
                np.array([[.6, .5], [.6, .6], [.4, .4]]),
                geometry_config=baseline._geometry_config(32), solve_config=baseline.iteration01_solve_config())
    assert ledger.snapshot()['totals']['td_evaluation_count'] == 2
    assert ledger.snapshot()['totals']['td_frequency_solve_count'] == 2
    assert ledger.snapshot()['totals']['evaluation_count'] == 0


@pytest.mark.parametrize('chart', ('radial', 'cartesian'))
def test_replay_perturbations_are_deterministic_and_preserve_input(chart):
    from run_fourier_topology_controller import case_spec
    from run_topology_allocation_experiment import perturbed_state
    initial = case_spec('split', chart=chart)[0]
    original = initial.parameter_vector().copy()
    first, info = perturbed_state(initial, 1e-3, 11, chart)
    second, _ = perturbed_state(initial, 1e-3, 11, chart)
    assert info['sampled_displacement_maximum_m'] > 0
    np.testing.assert_array_equal(first.parameter_vector(), second.parameter_vector())
    np.testing.assert_array_equal(initial.parameter_vector(), original)
    assert perturbed_state(initial, 0., 11, chart)[0] is initial


def test_rejections_do_not_confuse_eligible_losers_with_physics_failures():
    from run_topology_allocation_experiment import rejection_class
    assert rejection_class(dict(eligible=True)) == 'eligible_not_selected'
    assert rejection_class(dict(kind='unsupported_nested_hole')) == 'representation_restriction'
    assert rejection_class(dict(reason='No gauge-fixed polar-angle contour represents this mask.')) == 'representation_restriction'
    assert rejection_class(dict(reason='unknown new failure')) == 'unclassified'


def test_cartesian_replay_rejects_a_state_that_would_be_moved_by_gauge_fixing():
    from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
    seed = circle_cartesian_fourier_state((.5, .5), .03, 'seed', maximum_mode=3)
    cosine, sine = seed.cosine_coefficients.copy(), seed.sine_coefficients.copy()
    phase = .7
    cosine[1] = .03 * np.array([np.cos(phase), np.sin(phase)])
    sine[1] = .03 * np.array([-np.sin(phase), np.cos(phase)])
    shifted = MultiRadialFourierState((seed._replaced(cosine, sine),))
    with pytest.raises(ValueError, match='must already satisfy'):
        controller.run_topology_aware_fourier_inverse(shifted, None, None, None, solve_config=None,
            config=controller.TopologyControllerConfig(chart='cartesian'), replay_first_event=True)
