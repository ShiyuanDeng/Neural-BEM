"""Regressions for topology events carried in the Cartesian Fourier chart.

The chart study's own gates live in ``test_cartesian_fourier_chart``.  These
cover what changes when topology is added: the seeds and contour fits the
controller constructs, the feature radius a discrete cut is prepared against,
and the gauge the multi-component optimizer has to maintain for the chart to
converge at all.
"""
import numpy as np
import pytest

import run_radial_fourier_topology_inverse as baseline
from ordered_boundary import ellipse
from sdf_inverse import (
    ComplexScatteredData, MultiRadialFourierState, circle_cartesian_fourier_state,
    circle_radial_fourier_state,
)
from sdf_inverse.curve_updates import (
    RadialFourierCurveState, cartesian_fourier_phase_gauge_direction,
    fit_cartesian_fourier_curve_state,
    polar_angle_gauge_fixed_point, radial_fourier_parameterization,
    regauge_cartesian_state_to_polar_angle,
)
from sdf_inverse.explicit_fourier import CartesianFourierCurveState
from sdf_inverse.geometry import OrderedSDFGeometryError
from sdf_inverse.radial_topology import (
    _inside_polygon, component_radius_floor, run_multiradial_fd_inverse,
)
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, TopologyWorkspace, cartesian_component, chart_contour_modes,
    fit_mask_component, generate_topology_candidates, state_in_chart,
)

TWO_CIRCLES = (((.44, .50), .033), ((.56, .50), .033))


def _points(component, count=2048):
    if isinstance(component, CartesianFourierCurveState):
        return component.parameterization().discretize(count).points
    return radial_fourier_parameterization(component).discretize(count).points


def _peanut(component_id='parent'):
    return RadialFourierCurveState(np.array([.5, .5]), np.array([.067, 0., .035]),
                                   np.zeros(3), component_id)


def test_a_circle_is_mode_one_alone_and_an_exact_gauge_fixed_point():
    """Every birth and split seed must cost the gauge nothing at any band."""
    for band in (1, 2, 6, 9):
        seed = circle_cartesian_fourier_state((.47, .52), .031, 'seed', maximum_mode=band)
        assert seed.mean_radius_m == pytest.approx(.031, rel=1e-14)
        assert seed.center == pytest.approx(np.array([.47, .52]))
        assert seed.is_star_shaped_about_center
        # A 128-gon understates a circle by 2e-4 relative; the exact Fourier
        # area must not, because the inversions resolve far below that.
        assert abs(seed.mean_radius_m - .031) < 1e-15
        assert seed.minimum_radius_lower_bound_m == pytest.approx(.031, rel=1e-12)
        assert polar_angle_gauge_fixed_point(seed)[1] < 1e-15
        assert np.count_nonzero(seed.cosine_coefficients[2:]) == 0
        assert np.count_nonzero(seed.sine_coefficients[2:]) == 0


@pytest.mark.parametrize('phase,orientation', [(0.7, 1.), (np.pi / 2, 1.), (0.7, -1.)])
def test_gauge_fixing_removes_phase_even_when_band_truncation_is_zero(phase, orientation):
    seed = circle_cartesian_fourier_state((.47, .52), .031, 'seed', maximum_mode=3)
    cosine, sine = seed.cosine_coefficients.copy(), seed.sine_coefficients.copy()
    cosine[1] = .031 * np.array([np.cos(phase), np.sin(phase)])
    sine[1] = orientation * .031 * np.array([-np.sin(phase), np.cos(phase)])
    shifted = seed._replaced(cosine, sine)
    # Reparameterization is exact, but the input is not in the optimizer's gauge.
    assert regauge_cartesian_state_to_polar_angle(shifted)[2] < 1e-14
    fixed, residual = polar_angle_gauge_fixed_point(shifted)
    np.testing.assert_allclose(fixed.parameter_vector(), seed.parameter_vector(), atol=1e-13)
    assert residual < 1e-13


def test_gauge_rejects_a_multiply_traversed_circle():
    seed = circle_cartesian_fourier_state((.5, .5), .03, 'double', maximum_mode=2)
    cosine, sine = seed.cosine_coefficients.copy(), seed.sine_coefficients.copy()
    cosine[2], sine[2] = cosine[1], sine[1]
    cosine[1], sine[1] = 0., 0.
    with pytest.raises(OrderedSDFGeometryError, match='one|monotone'):
        regauge_cartesian_state_to_polar_angle(seed._replaced(cosine, sine))


def test_ungauged_ellipse_radius_bound_does_not_overstate_its_minor_radius():
    seed = circle_cartesian_fourier_state((.5, .5), .09, 'ellipse')
    sine = seed.sine_coefficients.copy()
    sine[1, 1] = .01
    component = seed._replaced(seed.cosine_coefficients, sine)
    assert component.is_star_shaped_about_center
    assert 0.009 < component.minimum_radius_lower_bound_m <= .01
    assert component_radius_floor(component) <= .01


def test_controller_api_honors_cartesian_chart_for_radial_initial_geometry():
    from sdf_inverse.topology_controller import run_topology_aware_fourier_inverse
    state = MultiRadialFourierState(tuple(circle_radial_fourier_state(center, radius, cid)
        for (center, radius), cid in zip(TWO_CIRCLES, ('A', 'B'))))
    result = run_topology_aware_fourier_inverse(
        state, _two_circle_data(), baseline._geometry_config(64), baseline._geometry_config(128),
        solve_config=baseline.iteration01_solve_config(),
        config=TopologyControllerConfig(chart='cartesian', maximum_cycles=1, fixed_iterations=1))
    assert result.stop_reason == 'recovered'
    assert result.final_state.component_ids == state.component_ids
    assert all(isinstance(component, CartesianFourierCurveState)
               for frame in result.frames for component in frame.state.components)


def test_contour_fit_checks_geometry_after_gauge_convergence(monkeypatch):
    import sdf_inverse.topology_controller as controller
    axis = np.linspace(.3, .7, 161)
    x, y = np.meshgrid(axis, axis)
    points = np.stack((x, y), axis=-1)
    mask = np.linalg.norm(points - [.5, .5], axis=-1) < .05
    nan = np.full_like(x, np.nan)
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(mask), mask, (mask,),
                                 nan, nan, axis[1] - axis[0])
    gauge = controller.polar_angle_gauge_fixed_point

    def converged_but_displaced(component):
        fixed, residual = gauge(component)
        cosine = fixed.cosine_coefficients.copy()
        cosine[0, 0] += .025
        return fixed._replaced(cosine, fixed.sine_coefficients), residual

    monkeypatch.setattr(controller, 'polar_angle_gauge_fixed_point', converged_but_displaced)
    with pytest.raises(ValueError, match='No gauge-fixed'):
        fit_mask_component(mask, workspace, 'circle', 6, baseline._geometry_config(64), 'cartesian')


def test_the_radial_chart_embeds_exactly_one_band_higher():
    """Both charts must start a matched run from identical geometry."""
    for component in (circle_radial_fourier_state((.5, .5), .033, 'c'), _peanut(),
                      RadialFourierCurveState(np.array([.48, .52]), np.array([.05, 0, .008, -.004]),
                                              np.array([0., 0., .005, .002]), 'lopsided')):
        promoted = cartesian_component(component)
        assert isinstance(promoted, CartesianFourierCurveState)
        assert promoted.maximum_mode == component.maximum_mode + 1
        assert np.max(np.linalg.norm(_points(promoted) - _points(component), axis=1)) < 1e-14
        # The radial chart zeroes its own mode one, which is exactly what puts
        # the Cartesian mean on the radial centre -- the point the gauge
        # measures its angle about. So the embedding is already gauge-fixed.
        assert np.linalg.norm(promoted.center - component.center) < 1e-15
        assert polar_angle_gauge_fixed_point(promoted)[1] < 1e-14
    assert chart_contour_modes(TopologyControllerConfig(contour_modes=8, chart='cartesian')) == 9
    assert chart_contour_modes(TopologyControllerConfig(contour_modes=8)) == 8


def test_one_re_gauge_halves_the_excess_and_the_fixed_point_removes_it():
    """The rate-1/2 contraction is why a single projection is not enough.

    An optimizer applying one re-gauge per accepted step inherits this rate:
    the measured loss fell by exactly four per iteration where the radial chart
    was quadratic. The fixed-point routine is what removes that ceiling.
    """
    seed = circle_cartesian_fourier_state((.5, .5), .033, 'a', maximum_mode=3)
    cosine = np.array(seed.cosine_coefficients, copy=True)
    sine = np.array(seed.sine_coefficients, copy=True)
    cosine[2, 0] += 1e-3
    sine[3, 1] += 1e-3
    perturbed = CartesianFourierCurveState(cosine, sine, 'a')
    current, truncations = perturbed, []
    for _ in range(6):
        current, _, maximum = regauge_cartesian_state_to_polar_angle(current)
        truncations.append(maximum)
    ratios = [later / earlier for earlier, later in zip(truncations, truncations[1:])]
    assert all(.48 < ratio < .52 for ratio in ratios), truncations
    fixed, residual = polar_angle_gauge_fixed_point(perturbed)
    assert residual < 1e-10
    assert polar_angle_gauge_fixed_point(fixed)[1] <= max(residual, 1e-14)
    # A gauge projection moves the parameter, not the object: the enclosed area
    # is what must survive it.
    assert fixed.mean_radius_m == pytest.approx(perturbed.mean_radius_m, rel=2e-3)


def test_polar_angle_beats_arclength_for_a_topology_contour_at_the_same_band():
    """The chart's founding measurement, made on a contour the controller fits.

    ``fit_mask_component`` fits in arc length under the radial chart because
    that contour is a fallback for shapes no radial component can hold. Under
    the Cartesian chart the same contour is the authoritative state, and arc
    length is the parameter in which these targets are not band-limited.
    """
    angles = np.linspace(0., 2 * np.pi, 4096, endpoint=False)
    radii = .05 * (1. + .25 * np.cos(5 * angles))
    points = np.stack((.5 + radii * np.cos(angles), .5 + radii * np.sin(angles)), axis=-1)
    polar = fit_cartesian_fourier_curve_state(points, maximum_mode=6, center=(.5, .5),
                                              component_id='star')
    closed = np.vstack((points, points[:1]))
    distance = np.concatenate(([0.], np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))))
    sample = np.linspace(0., distance[-1], 4096, endpoint=False)
    uniform = np.column_stack([np.interp(sample, distance, closed[:, axis]) for axis in range(2)])
    spectrum = np.fft.rfft(uniform, axis=0)
    spectrum[7:] = 0.
    arclength_error = float(np.max(np.linalg.norm(
        np.fft.irfft(spectrum, n=len(uniform), axis=0) - uniform, axis=1)))
    assert polar.initial_projection_maximum_m < 1e-15
    assert arclength_error > 1e-4


def test_the_two_charts_certify_the_same_feature_radius():
    """The floor a discrete cut is prepared against must not depend on chart.

    It is deliberately the radial chart's conservative coefficient-norm
    certificate rather than a tighter sampled bound. A tighter bound lets a
    component approach a shape whose boundary nearly reaches its own centre,
    which the radial chart refuses to represent at all; measured on the
    ellipse/star challenge that cost the whole mode continuation.
    """
    for amplitude, expected in ((0., .067), (.035, .032), (.0645, .0025)):
        radial = RadialFourierCurveState(np.array([.5, .5]), np.array([.067, 0., amplitude]),
                                         np.zeros(3), 'neck')
        component = cartesian_component(radial)
        assert component.minimum_radius_lower_bound_m == pytest.approx(expected, rel=1e-9)
        assert component.minimum_radius_lower_bound_m == pytest.approx(
            radial.minimum_radius_lower_bound_m, rel=1e-9)
        assert component_radius_floor(component) == component.minimum_radius_lower_bound_m
    # The equivalent-area radius is blind to the pinch: it barely moves while
    # the neck closes by a factor of twenty-six.
    pinched = cartesian_component(RadialFourierCurveState(
        np.array([.5, .5]), np.array([.067, 0., .0645]), np.zeros(3), 'neck'))
    assert pinched.mean_radius_m > .08
    # A shape whose modes outrun its mean radius is certified negative even
    # though its radius stays positive -- 0.66 mm here. That is the point of a
    # conservative certificate, and the whole point of sharing it: the radial
    # chart's constructor refuses these coefficients outright, and the
    # Cartesian chart has no constructor guard to inherit.
    cosine = np.array([.03, 0., 0., 0., .009, .009, .009, .009])
    sine = np.zeros_like(cosine)
    with pytest.raises(ValueError):
        RadialFourierCurveState(np.array([.5, .5]), cosine, sine, 'wiggly')
    angles = np.linspace(0., 2 * np.pi, 4096, endpoint=False)
    phase = angles[:, None] * np.arange(len(cosine))[None, :]
    profile = np.cos(phase) @ cosine + np.sin(phase) @ sine
    points = np.array([.5, .5]) + profile[:, None] * np.stack(
        (np.cos(angles), np.sin(angles)), axis=-1)
    degenerate = fit_cartesian_fourier_curve_state(points, maximum_mode=8, center=(.5, .5),
                                                   component_id='wiggly')
    assert degenerate.minimum_radius_lower_bound_m < 0.
    assert component_radius_floor(degenerate) < 0.


def test_a_nonstar_contour_is_promoted_by_one_chart_and_refused_by_the_other():
    """A thick C has no centre in its material and so no polar-angle gauge.

    The radial chart promotes it: an arc-length Cartesian contour holds a shape
    no radial component can, and its feature radius falls back to the
    equivalent-area value. The Cartesian *topology* chart refuses it instead,
    because it would have to carry it ungauged -- the free parameter drift the
    whole gauge exists to prevent. That refusal is the cost of the chart, and
    it is recorded rather than hidden.
    """
    axis = np.linspace(.3, .7, 161)
    x, y = np.meshgrid(axis, axis)
    points = np.stack((x, y), axis=-1)
    radius = np.linalg.norm(points - [.5, .5], axis=-1)
    mask = (radius < .09) & (radius > .047) & ~((x > .5) & (np.abs(y - .5) < .026))
    nan = np.full_like(x, np.nan)
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(mask), mask, (mask,),
                                 nan, nan, axis[1] - axis[0])
    geometry = baseline._geometry_config(128)
    component = fit_mask_component(mask, workspace, 'c', 5, geometry, 'radial')
    assert isinstance(component, CartesianFourierCurveState)
    assert not component.is_star_shaped_about_center
    assert component_radius_floor(component) == component.mean_radius_m
    with pytest.raises(Exception):
        polar_angle_gauge_fixed_point(component)
    # A state holding it cannot be gauge-fixed at all, which is why the
    # Cartesian chart must never accept one: there is no skip that would let
    # such a component ride along ungauged inside a gauged state.
    mixed = MultiRadialFourierState((component, circle_cartesian_fourier_state((.5, .5), .01, 'd')))
    with pytest.raises(OrderedSDFGeometryError):
        mixed.polar_angle_gauge_fixed()
    with pytest.raises(ValueError):
        fit_mask_component(mask, workspace, 'c', 5, geometry, 'cartesian')


def test_every_candidate_of_a_cartesian_pass_is_a_gauge_fixed_cartesian_state():
    """Births, deaths, splits and merges must not leak the other chart in."""
    axis = np.linspace(.35, .65, 61)
    x, y = np.meshgrid(axis, axis)
    points = np.stack((x, y), axis=-1)
    parent = cartesian_component(_peanut())
    polygon = parent.parameterization().discretize(512).points
    material = _inside_polygon(points.reshape(-1, 2), polygon).reshape(x.shape)
    state = MultiRadialFourierState((parent,))
    workspace = TopologyWorkspace(points, axis, axis, np.ones_like(material), material,
        (material,), np.where(material, np.nan, -1.), np.where(material, -1., np.nan),
        float(axis[1] - axis[0]))
    config = TopologyControllerConfig(chart='cartesian', contour_modes=8,
                                      minimum_component_radius_m=.004)
    candidates, _ = generate_topology_candidates(state, workspace, baseline._geometry_config(64),
                                                 config, 1)
    kinds = {candidate.kind for candidate in candidates}
    assert {'death', 'split'} <= kinds, kinds
    fitted = 0
    for candidate in candidates:
        if candidate.state is None:
            continue
        for component in candidate.state.components:
            assert isinstance(component, CartesianFourierCurveState), candidate.construction
            if component.maximum_mode > 1:
                fitted += 1
                assert component.maximum_mode == 9
                assert polar_angle_gauge_fixed_point(component)[1] < 1e-8
    assert fitted, 'no contour-fitted child was generated'
    with pytest.raises(ValueError):
        TopologyControllerConfig(chart='polar')


def _two_circle_data():
    frequencies = np.array([.5e9])
    problem = baseline._problem(frequencies)
    observed = baseline._oracle_response(
        np.array([center for center, _ in TWO_CIRCLES]),
        np.array([radius for _, radius in TWO_CIRCLES]), frequencies,
        component_ids=('A', 'B'))
    return ComplexScatteredData(problem, observed)


def _fd_config(state, iterations):
    from sdf_inverse.optimization import ParameterFDConfig
    steps = [(.012 if name.endswith('radius_m') or '.cos_1_' in name or '.sin_1_' in name
              else .018 if '.center_' in name or '.cos_0_' in name else .006)
             for name in state.parameter_names]
    return ParameterFDConfig(max_iterations=iterations, finite_difference_steps=1.e-4,
        max_steps=np.asarray(steps), initial_damping=1.e-3, max_damping_trials=5,
        max_backtracks=7, gradient_tolerance=1.e-7, loss_tolerance=1.e-16,
        relative_step_tolerance=1.e-7, max_parameters=max(64, state.parameter_count),
        infeasible_trial_policy='reject')


def test_the_gauged_chart_matches_the_radial_chart_update_for_update():
    """The parity claim, at the smallest scale that can carry it.

    Four accepted updates in either chart, from the same wrong pair of circles
    to the same two-circle data, for the same number of forward solves. The
    cost matched only once the Jacobian was measured along the gauge-fixed
    subspace: probing all ``4K + 2`` coefficients of a chart whose gauge leaves
    ``2K - 1`` reachable directions is what made the earlier Cartesian run cost
    twice the radial one.
    """
    data = _two_circle_data()
    geometry = baseline._geometry_config(64)
    solve = baseline.iteration01_solve_config()
    results = {}
    for chart, seed in (('radial', circle_radial_fourier_state),
                        ('cartesian', circle_cartesian_fourier_state)):
        state = MultiRadialFourierState((seed((.43, .49), .030, 'A'), seed((.57, .51), .036, 'B')))
        results[chart] = run_multiradial_fd_inverse(
            state, data, geometry, solve_config=solve, config=_fd_config(state, 4),
            minimum_component_radius_m=.008, cartesian_gauge=chart == 'cartesian')
    radial, cartesian = results['radial'], results['cartesian']
    assert len(cartesian.iterations) == len(radial.iterations) == 5
    final = cartesian.iterations[-1]
    assert final.relative_l2_error < 2.5 * radial.iterations[-1].relative_l2_error
    assert final.relative_l2_error < 1e-8
    # Both circles recovered, and the gauge cost nothing at the fixed point.
    for component in cartesian.final_state.components:
        assert component.mean_radius_m == pytest.approx(.033, abs=1e-7)
    assert final.gauge_truncation_maximum_m < 1e-10
    assert cartesian.evaluation_count == radial.evaluation_count


def test_the_gauge_flag_is_inert_for_a_purely_radial_state():
    """A radial run must take the identical path at either setting."""
    data = _two_circle_data()
    geometry = baseline._geometry_config(64)
    solve = baseline.iteration01_solve_config()
    trajectories = []
    for gauge in (False, True):
        state = MultiRadialFourierState((circle_radial_fourier_state((.43, .49), .030, 'A'),
                                         circle_radial_fourier_state((.57, .51), .036, 'B')))
        result = run_multiradial_fd_inverse(state, data, geometry, solve_config=solve,
            config=_fd_config(state, 3), minimum_component_radius_m=.008, cartesian_gauge=gauge)
        trajectories.append([(item.loss, item.parameter_vector.tolist()) for item in result.iterations])
        assert all(item.gauge_truncation_maximum_m == 0. for item in result.iterations)
    assert trajectories[0] == trajectories[1]


def test_the_gauge_tangent_basis_spans_the_reachable_directions_of_a_mixed_state():
    """What the optimizer is allowed to step along, and what it must not.

    The gauge-fixed set is a linear subspace of the coefficient space, so a
    step inside it leaves a gauge-fixed state gauge-fixed exactly, at any size.
    The exact phase direction -- the one an earlier projection removed on its
    own -- is only one of the many directions this excludes.
    """
    state = MultiRadialFourierState((cartesian_component(_peanut('a')),
                                     circle_radial_fourier_state((.62, .5), .02, 'b'),
                                     circle_cartesian_fourier_state((.38, .5), .02, 'c', maximum_mode=4)))
    basis = state.gauge_tangent_basis()
    # Cartesian band 4 contributes 7 of its 18 coefficients, band 4 again 7 of
    # 18, and the radial circle all 3 of its 3.
    assert basis.shape == (3 + 5 + 7, state.parameter_count)
    np.testing.assert_allclose(basis @ basis.T, np.eye(len(basis)), atol=1e-12)

    generator = np.random.default_rng(20260910)
    for scale in (1e-4, 1e-3, 5e-3):
        step = basis.T @ (scale * generator.standard_normal(len(basis)))
        moved = state.from_parameter_vector(state.parameter_vector() + step)
        assert moved.polar_angle_gauge_fixed()[1] < 1e-13
    # A radial-only state keeps every direction it had.
    radial = MultiRadialFourierState((circle_radial_fourier_state((.5, .5), .03, 'r'),))
    np.testing.assert_array_equal(radial.gauge_tangent_basis(), np.eye(radial.parameter_count))
    # A pure phase shift changes no point, so it cannot lie inside a subspace
    # every direction of which changes the shape: each Cartesian component's
    # phase direction keeps a large component normal to the basis. It need not
    # be orthogonal to it, and is not -- the peanut's is not.
    for component, component_slice in zip(state.components, state.parameter_slices):
        if not isinstance(component, CartesianFourierCurveState):
            continue
        direction = np.zeros(state.parameter_count)
        direction[component_slice] = cartesian_fourier_phase_gauge_direction(component)
        assert np.linalg.norm(direction - basis.T @ (basis @ direction)) > .5


def test_state_in_chart_is_identity_for_radial_and_exact_for_cartesian():
    state = MultiRadialFourierState((_peanut(), circle_radial_fourier_state((.62, .5), .02, 'b')))
    assert state_in_chart(state, 'radial') is state
    assert state_in_chart(None, 'cartesian') is None
    converted = state_in_chart(state, 'cartesian')
    assert all(isinstance(c, CartesianFourierCurveState) for c in converted.components)
    assert converted.component_ids == state.component_ids
    geometry = baseline._geometry_config(128)
    np.testing.assert_allclose(converted.boundary(geometry).points,
                               state.boundary(geometry).points, atol=1e-13)


def test_the_challenge_driver_promotes_both_charts_to_the_same_shape_space():
    """A declared radial-mode schedule must not hand the charts different bands.

    The schedule is written in radial modes. The Cartesian chart carries the
    same shape content one band higher, so promoting it to the schedule entry
    itself would leave it a mode behind at every stage of a continuation and
    make the comparison meaningless.
    """
    import run_radial_fourier_topology_challenges as driver
    radial = driver._case_spec('ellipse-star').initial_state
    cartesian = driver._case_spec('ellipse-star', 'cartesian').initial_state
    for mode in driver._case_spec('ellipse-star').mode_schedule:
        promoted_radial = driver._promote(radial, mode)
        promoted_cartesian = driver._promote(cartesian, mode)
        assert promoted_radial.components[0].maximum_mode == mode
        assert promoted_cartesian.components[0].maximum_mode == mode + 1
        # Promotion opens coefficients; it must not move a single point.
        np.testing.assert_allclose(driver._sample_component(promoted_cartesian.components[0]),
                                   driver._sample_component(cartesian.components[0]), atol=1e-15)
        np.testing.assert_allclose(driver._sample_component(promoted_radial.components[0]),
                                   driver._sample_component(promoted_cartesian.components[0]), atol=1e-14)
    # Never lower an existing component in either chart.
    assert driver._promote(driver._promote(cartesian, 5), 2).components[0].maximum_mode == 6


def test_the_gauge_treats_both_traversal_directions_alike():
    """Handedness is a labelling of the parameter, not of the point set.

    A clockwise state is refused further downstream as solver geometry, so this
    is a property of the projection rather than an inversion path -- but the
    projection reads the angle's direction to build its own starting guess, and
    reading it wrongly would silently mis-seed Newton on half the inputs.
    """
    from scipy.spatial import cKDTree

    def sample(state, count=4096):
        parameters = 2. * np.pi * np.arange(count) / count
        phase = parameters[:, None] * np.arange(state.maximum_mode + 1)[None, :]
        return np.cos(phase) @ state.cosine_coefficients + np.sin(phase) @ state.sine_coefficients

    moved = []
    for handedness in (1., -1.):
        cosine, sine = np.zeros((4, 2)), np.zeros((4, 2))
        cosine[0] = (.5, .5)
        cosine[1, 0], sine[1, 1] = .033, handedness * .033
        cosine[3, 0], sine[3, 1] = .002, handedness * .0015
        state = CartesianFourierCurveState(cosine, sine, 'a')
        gauged, residual = polar_angle_gauge_fixed_point(state)
        assert residual < 1e-13
        before, after = sample(state), sample(gauged)
        # An order-free comparison: reversing the traversal permutes the
        # samples, so only the point sets can be compared.
        moved.append(max(cKDTree(after).query(before)[0].max(),
                         cKDTree(before).query(after)[0].max()))
    # The two states are mirror images, so the projection must move them by the
    # same distance. Reading the angle's direction wrongly makes one of them
    # start from a guess a whole turn away.
    # Nearest-neighbour maxima over a finite sample, so equal to the
    # sampling and not to machine precision.
    assert moved[0] == pytest.approx(moved[1], rel=1e-4)
    assert moved[0] > 1e-5
