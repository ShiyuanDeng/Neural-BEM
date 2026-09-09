"""Numerical physics and discrete-state regressions for iteration 02."""
from dataclasses import replace

import numpy as np
import pytest

import run_radial_fourier_topology_inverse as baseline
from ordered_boundary import OrderedBoundary2D, circle, fourier_curve
from gpr_bem_kress.multicomponent import (
    evaluate_multicomponent_interior_total_field, multicomponent_incident_trace_on_boundary,
    MultiComponentFieldPointError,
)
from sdf_inverse import ComplexScatteredData, MultiRadialFourierState, circle_radial_fourier_state
from sdf_inverse.radial_topology import _free_space_field, evaluate_current_domain_topological_derivative, evaluate_multiradial_objective
from sdf_inverse.explicit_fourier import CartesianFourierCurveState
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, TopologyWorkspace, classify_material_change,
    fit_mask_component, run_topology_aware_fourier_inverse,
)


def test_interior_representation_matches_manufactured_fields_in_each_component():
    boundary = OrderedBoundary2D((circle((.42, .5), .04, component_id='a').discretize(128),
                                  circle((.57, .5), .03, component_id='b').discretize(128)))
    sources = np.array([[.5, .9], [.2, .5]])
    strengths = np.array([1e-6, 2e-6j])
    wave = 13.2
    u, q = multicomponent_incident_trace_on_boundary(boundary, sources, wave, strengths)
    points = np.array([[.42, .5], [.437, .51], [.57, .51]])
    evaluated = evaluate_multicomponent_interior_total_field(boundary, points, wave, u, q)
    np.testing.assert_allclose(evaluated, _free_space_field(points, sources, wave, strengths), rtol=1e-11, atol=1e-18)
    with pytest.raises(MultiComponentFieldPointError):
        evaluate_multicomponent_interior_total_field(boundary, [[.5, .5]], wave, u, q)


def test_integrated_removal_td_matches_uniform_material_finite_difference():
    """Integrating local replacement equals a uniform permittivity direction.

    This checks contrast sign, reciprocal-source scaling, the objective's
    conjugation and normalization, and interior Green representation together.
    It needs no unsupported nested-hole forward model.
    """
    problem = baseline._problem(np.array([.5e9]))
    geometry = baseline._geometry_config(256)
    solve = baseline.iteration01_solve_config()
    state = MultiRadialFourierState((circle_radial_fourier_state((.47, .5), .04, 'a'),))
    observed = baseline._oracle_response(np.array([[.48, .5]]), np.array([.033]), np.array([.5e9]), component_ids=('truth',))
    data = ComplexScatteredData(problem, observed)
    nradial, nangle = 16, 96
    # Midpoint quadrature in squared radius has equal-area weights and avoids
    # the unsupported near-boundary evaluation regime.
    radius = .04 * np.sqrt((np.arange(nradial) + .5) / nradial)
    angle = np.arange(nangle) * 2 * np.pi / nangle
    points = np.array([.47, .5]) + (radius[:, None, None] * np.stack((np.cos(angle), np.sin(angle)), axis=-1)).reshape(-1, 2)
    td = evaluate_current_domain_topological_derivative(state, data, points, geometry_config=geometry,
                                                       solve_config=solve, material_change='removal')
    integrated = np.mean(td.values) * np.pi * .04**2
    h = 1e-4
    direction = problem.exterior.epsr - problem.interior.epsr
    values = []
    for sign in (-1, 1):
        perturbed = replace(problem, interior=replace(problem.interior, epsr=problem.interior.epsr + sign * h * direction))
        values.append(evaluate_multiradial_objective(state, ComplexScatteredData(perturbed, observed),
                                                     geometry, solve_config=solve).loss)
    finite_difference = (values[1] - values[0]) / (2 * h)
    assert np.sign(integrated) == np.sign(finite_difference)
    assert integrated == pytest.approx(finite_difference, rel=.003)


def test_connectivity_classifies_all_events_and_rejects_a_hole():
    a = np.zeros((40, 40), bool); a[10:20, 5:15] = True
    b = np.zeros_like(a); b[10:20, 25:35] = True
    bridge = a | b; bridge[12:18, 14:26] = True
    assert classify_material_change((), a) == 'birth'
    assert classify_material_change((a,), a | b) == 'birth'
    assert classify_material_change((a, b), a) == 'death'
    assert classify_material_change((a,), np.zeros_like(a)) == 'death'
    assert classify_material_change((bridge,), a | b) == 'split'
    assert classify_material_change((bridge, np.zeros_like(a)), a | b) == 'split'
    assert classify_material_change((a, np.zeros_like(a)), a | b) == 'birth'
    assert classify_material_change((a, b), bridge) == 'merge'
    hole = a.copy(); hole[13:16, 8:11] = False
    assert classify_material_change((a,), hole) == 'unsupported_nested_hole'


def test_nonradial_contour_promotes_and_mixed_state_roundtrips():
    axis = np.linspace(.3, .7, 161)
    x, y = np.meshgrid(axis, axis)
    points = np.stack((x, y), axis=-1)
    # A thick C has one simple outer contour and no radial centre in its
    # material kernel. It must survive as a Cartesian periodic component.
    radius = np.linalg.norm(points - [.5, .5], axis=-1)
    mask = (radius < .09) & (radius > .047) & ~((x > .5) & (np.abs(y - .5) < .026))
    nan = np.full_like(x, np.nan)
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(mask), mask, (mask,), nan, nan, axis[1] - axis[0])
    component = fit_mask_component(mask, workspace, 'c', 5, baseline._geometry_config(128))
    assert isinstance(component, CartesianFourierCurveState)
    state = MultiRadialFourierState((component, circle_radial_fourier_state((.64, .5), .015, 'disk')))
    rebuilt = state.from_parameter_vector(state.parameter_vector())
    assert rebuilt.component_ids == state.component_ids
    np.testing.assert_array_equal(rebuilt.parameter_vector(), state.parameter_vector())
    np.testing.assert_array_equal(rebuilt.boundary(baseline._geometry_config(128)).points,
                                  state.boundary(baseline._geometry_config(128)).points)


def test_controller_compares_event_types_and_preserves_exact_rollback(monkeypatch):
    import sdf_inverse.topology_controller as controller
    from sdf_inverse.topology_controller import TopologyCandidate
    state = MultiRadialFourierState((circle_radial_fourier_state((.5, .5), .03, 'original'),))
    added = state.appended(circle_radial_fourier_state((.6, .5), .02, 'new'))
    monkeypatch.setattr(controller, 'run_multiradial_fd_inverse', lambda *a, **k:
                        type('Result', (), dict(final_state=a[0], stop_reason='no_decreasing_step'))())
    monkeypatch.setattr(controller, 'build_topology_workspace', lambda *a: None)
    monkeypatch.setattr(controller, 'generate_topology_candidates', lambda *a: ((
        TopologyCandidate('birth', added, (), ('new',), -100., 'test'),
        TopologyCandidate('death', None, ('original',), (), 0., 'test')), ()))
    def objective(current, data, geometry, solve):
        # Production would pick birth, but refinement disproves it.
        if current is added:
            return (.1 if geometry == 'production' else 1.2), 1.
        return (.4 if current is None else 1.), 1.
    monkeypatch.setattr(controller, 'topology_objective', objective)
    result = run_topology_aware_fourier_inverse(state, None, 'production', 'refined', solve_config=None,
        config=TopologyControllerConfig(maximum_cycles=1, candidate_refinement_iterations=0))
    assert result.events[0]['kind'] == 'death'
    assert result.final_state is None
    assert result.frames[0].state is state
    assert result.passes[0]['trials'][0]['reason'] == 'cross_resolution_margin_failed'
    # No improvement must return the exact original state, including IDs/chart.
    monkeypatch.setattr(controller, 'topology_objective', lambda *a: (1., 1.))
    result = run_topology_aware_fourier_inverse(state, None, 'production', 'refined', solve_config=None,
        config=TopologyControllerConfig(maximum_cycles=1, candidate_refinement_iterations=0))
    assert result.final_state is state
    assert not result.events
    assert result.stop_reason == 'topology_stationary'


def test_split_budget_retains_two_child_corridors_and_merge_tracks_all_parents():
    from sdf_inverse.topology_controller import generate_topology_candidates, component_parameterization
    from sdf_inverse.radial_topology import _inside_polygon
    axis = np.linspace(.3, .7, 81)
    x, y = np.meshgrid(axis, axis)
    points = np.stack((x, y), axis=-1)
    radial = np.hypot(x - .5, y - .5)
    angle = np.arctan2(y - .5, x - .5)
    mask = radial < .048 + .043 * np.cos(2 * angle)
    removal = np.where(mask, -100. * (1 - ((x - .5) / .08)**2), np.nan)
    addition = np.full_like(x, np.nan)
    geometry = baseline._geometry_config(64)
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(mask), mask,
                                  (mask,), addition, removal, .005)
    initial = MultiRadialFourierState((circle_radial_fourier_state((.5, .5), .07, 'parent'),))
    candidates, _ = generate_topology_candidates(initial, workspace, geometry, TopologyControllerConfig(), 1)
    assert any(c.kind == 'split' and len(c.children) == 2 for c in candidates)
    outside = circle_radial_fourier_state((.5, .75), .01, 'outside')
    offgrid_workspace = replace(workspace, component_masks=(mask, np.zeros_like(mask)))
    candidates, _ = generate_topology_candidates(initial.appended(outside), offgrid_workspace,
                                                 geometry, TopologyControllerConfig(), 1)
    two_children = [c for c in candidates if c.kind == 'split' and len(c.children) == 2]
    assert two_children
    assert all(c.state.components[0] is outside and len(c.state.components) == 3 for c in two_children)

    components = tuple(circle_radial_fourier_state((cx, .5), .021, cid)
                       for cx, cid in ((.43, 'left'), (.5, 'middle'), (.57, 'right')))
    masks = tuple(_inside_polygon(points.reshape(-1, 2), component_parameterization(c).discretize(256).points).reshape(x.shape)
                  for c in components)
    material = np.logical_or.reduce(masks)
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(mask), material,
        masks, np.where(material, np.nan, -1.), np.full_like(x, np.nan), .005)
    candidates, _ = generate_topology_candidates(MultiRadialFourierState(components), workspace,
                                               geometry, TopologyControllerConfig(), 2)
    triple = [c for c in candidates if c.kind == 'merge' and len(c.parents) == 3]
    assert triple
    assert all(len(c.children) == 1 and len(c.state.components) == 1 for c in triple)


def test_thin_neck_requests_topology_before_lm_can_pinch(monkeypatch):
    import sdf_inverse.topology_controller as controller
    from sdf_inverse.curve_updates import RadialFourierCurveState
    state = MultiRadialFourierState((RadialFourierCurveState(np.array([.5, .5]),
        np.array([.04, 0., .039]), np.zeros(3), 'thin'),))
    def forbidden_refinement(*args, **kwargs):
        pytest.fail('LM must not refine a sub-floor radial neck.')
    monkeypatch.setattr(controller, 'run_multiradial_fd_inverse', forbidden_refinement)
    monkeypatch.setattr(controller, 'topology_objective', lambda *a: (1., 1.))
    monkeypatch.setattr(controller, 'build_topology_workspace', lambda *a: None)
    monkeypatch.setattr(controller, 'generate_topology_candidates', lambda *a: ((), ()))
    result = run_topology_aware_fourier_inverse(state, None, None, None, solve_config=None)
    assert result.passes[0]['trigger'] == 'component_radius_floor'
    assert result.final_state is state


def test_fixed_birth_ladder_and_visible_demo_are_off_grid():
    from sdf_inverse.topology_controller import generate_topology_candidates
    from run_fourier_topology_controller import case_spec
    ladder = (.016, .024, .036, .048)
    config = TopologyControllerConfig(birth_radius_grid_m=ladder, candidate_refinement_iterations=0)
    axis = np.linspace(.3, .7, 81)
    x, y = np.meshgrid(axis, axis)
    points = np.stack((x, y), axis=-1)
    material = np.zeros(x.shape, bool)
    addition = np.where(np.hypot(x - .5, y - .5) < .04, -1., np.nan)
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(material), material,
        (), addition, np.full_like(x, np.nan), .005)
    candidates, _ = generate_topology_candidates(None, workspace, baseline._geometry_config(64), config, 1)
    assert {c.state.components[0].mean_radius_m for c in candidates} == set(ladder)
    _, _, targets = case_spec('repeated-birth', 'visible-refinement')
    assert min(abs(c.mean_radius_m - r) for c in targets for r in ladder) > .0018
    initial, _, targets = case_spec('split', 'visible-refinement')
    parent = initial.components[0]
    assert parent.mean_radius_m == .1
    assert np.count_nonzero(parent.radius_cosine_coefficients[1:]) == 0
    assert np.count_nonzero(parent.radius_sine_coefficients) == 0
    assert all(np.linalg.norm(c.center - parent.center) + c.mean_radius_m < parent.mean_radius_m for c in targets)
    for invalid in ((.024, .024), (.001,), (.2,), (np.nan,), ()):
        with pytest.raises(ValueError):
            TopologyControllerConfig(birth_radius_grid_m=invalid)


def test_unpolished_birth_is_visible_before_normal_refinement(monkeypatch):
    import sdf_inverse.topology_controller as controller
    from sdf_inverse.topology_controller import TopologyCandidate
    from types import SimpleNamespace
    seed = MultiRadialFourierState((circle_radial_fourier_state((.5, .5), .024, 'new'),))
    refined = MultiRadialFourierState((circle_radial_fourier_state((.5, .5), .0273, 'new'),))
    calls = []
    def optimize(current, *args, **kwargs):
        calls.append(current)
        assert current is seed
        for iteration, state, loss in ((0, seed, .2), (1, refined, 1e-8)):
            kwargs['progress_callback'](SimpleNamespace(iteration=iteration, state=state, loss=loss))
        return SimpleNamespace(final_state=refined, stop_reason='loss_tolerance')
    monkeypatch.setattr(controller, 'run_multiradial_fd_inverse', optimize)
    monkeypatch.setattr(controller, 'topology_objective', lambda state, *a:
                        (1e-8, .0001) if state is refined else ((.2, .6) if state is seed else (.5, 1.)))
    monkeypatch.setattr(controller, 'build_topology_workspace', lambda *a: None)
    monkeypatch.setattr(controller, 'generate_topology_candidates', lambda *a:
                        ((TopologyCandidate('birth', seed, (), ('new',), -1., 'fixed_ladder'),), ()))
    result = run_topology_aware_fourier_inverse(None, None, None, None, solve_config=None,
        config=TopologyControllerConfig(candidate_refinement_iterations=0))
    assert calls == [seed]
    event = result.events[0]
    assert event['raw_birth_radius_m'] == .024
    assert event['production_after'] == .2
    assert event['candidate_refinement_steps'] == 0
    birth = next(i for i, f in enumerate(result.frames) if f.label == 'BIRTH accepted')
    assert result.frames[birth].state is seed
    assert result.frames[birth + 1].state is seed
    assert result.frames[birth + 2].state is refined


def test_large_circle_split_can_seed_separated_children():
    from sdf_inverse.topology_controller import generate_topology_candidates
    axis = np.linspace(.3, .7, 81)
    x, y = np.meshgrid(axis, axis)
    points = np.stack((x, y), axis=-1)
    material = np.hypot(x - .5, y - .5) < .1
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(material), material,
        (material,), np.full_like(x, np.nan), np.where(material, -1., np.nan), .005)
    initial = MultiRadialFourierState((circle_radial_fourier_state((.5, .5), .1, 'parent'),))
    candidates, _ = generate_topology_candidates(initial, workspace, baseline._geometry_config(64),
        TopologyControllerConfig(split_seed_radius_factors=(1., .75, .5)), 1)
    separated = []
    for candidate in candidates:
        if candidate.kind != 'split' or len(candidate.children) != 2 or 'seed_scale=0.5' not in candidate.construction:
            continue
        a, b = candidate.state.components
        if np.linalg.norm(a.center - b.center) - a.mean_radius_m - b.mean_radius_m > .01:
            separated.append(candidate)
    assert separated
    assert all(max(c.mean_radius_m for c in candidate.state.components) < .04 for candidate in separated)
    for invalid in ((0.,), (1.1,), (), (.5, .5)):
        with pytest.raises(ValueError):
            TopologyControllerConfig(split_seed_radius_factors=invalid)
