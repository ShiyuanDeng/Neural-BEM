"""Exact geometry reuse must preserve ownership, refusals and fit isolation."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

import run_fourier_topology_controller as driver
from ordered_boundary import OrderedBoundary2D, circle
from ordered_boundary.validation import _self_intersection_count
from ordered_boundary.validation_cache import (
    array_key, current_validation_cache, fit_geometry_validation,
    geometry_validation, validation_cache,
)
from gpr_bem_kress.geometry import adapt_periodic_curve
from gpr_bem_kress.multicomponent import (
    MultiComponentAssemblyConfig, MultiComponentKressGeometryError,
    adapt_multicomponent_boundary, validate_multicomponent_admissibility,
    _axis_separation_certificate, _component_pair_clearance,
)
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.geometry import OrderedSDFGeometryError
from sdf_inverse.radial_topology import multiradial_geometry_admissible

ROOT = Path(__file__).resolve().parents[2]


def boundary(gap=.035, nodes=32):
    radius = .04
    return OrderedBoundary2D(tuple(circle((x, .5), radius, component_id=str(i)).discretize(nodes)
        for i, x in enumerate((.5-radius-gap/2, .5+radius+gap/2))))


def test_component_reports_share_validation_but_not_solver_grid_or_bounds():
    state = circle_cartesian_fourier_state((.5, .5), .03, 'one', maximum_mode=4)
    low = driver.baseline._geometry_config(64)
    with validation_cache('cache') as cache:
        a = state.boundary_curve(low)
        b = state.boundary_curve(replace(low, num_nodes=128))
        assert (a.num_nodes, b.num_nodes) == (64, 128)
        assert cache.counts['component_report.misses'] == 1
        assert cache.counts['component_report.hits'] == 1
        with pytest.raises(OrderedSDFGeometryError, match='bounds'):
            state.boundary_curve(replace(low, bounds=((.48, .48), (.52, .52))))
        with pytest.raises(OrderedSDFGeometryError, match='undersampled'):
            state.boundary_curve(replace(low, num_nodes=8))
        shifted = state.parameter_vector().copy()
        shifted[0] = np.nextafter(shifted[0], np.inf)
        state.from_parameter_vector(shifted).boundary_curve(low)
        assert cache.counts['component_report.misses'] == 3
        state.boundary_curve(replace(low, validation_resolution=128))
        assert cache.counts['component_report.misses'] == 4


def test_sample_audit_keys_order_and_resolved_tolerances():
    points = circle((.5, .5), .04).discretize(16).points
    with validation_cache('cache') as cache:
        assert _self_intersection_count(points, 1e-15, 1e-14) == 0
        assert _self_intersection_count(points.copy(), 1e-15, 1e-14) == 0
        assert cache.counts['self_intersection.hits'] == 1
        _self_intersection_count(points, 2e-15, 1e-14)
        crossing = points[np.array([0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15])]
        count = _self_intersection_count(crossing, 1e-15, 1e-14)
        assert count > 0
        assert _self_intersection_count(crossing, 1e-15, 1e-14) == count
        assert cache.counts['self_intersection.misses'] == 3
        assert cache.counts['self_intersection.hits'] == 2
    assert array_key(np.array([0.])) != array_key(np.array([-0.]))


def test_adapter_hits_preserve_caller_identity_and_validate_changed_weights():
    curves = [circle((.5, .5), .04, component_id='same').discretize(16) for _ in range(2)]
    with validation_cache('cache') as cache:
        for curve in curves:
            adapter = adapt_periodic_curve(curve)
            assert adapter.curve is curve
            assert adapter.arc_length_weights is curve.arc_length_weights
        assert cache.counts['self_intersection.hits'] == 1
        object.__setattr__(curves[1], 'arc_length_weights', curves[1].arc_length_weights * 1.5)
        with pytest.raises(ValueError, match='arc-length weights'):
            adapt_periodic_curve(curves[1])


def test_component_failure_is_cached_without_turning_into_success():
    state = circle_cartesian_fourier_state((.5, .5), .03, 'one')
    cosine = state.cosine_coefficients.copy(); cosine[1] *= -1
    bad = replace(state, cosine_coefficients=cosine)
    config = driver.baseline._geometry_config(32)
    with validation_cache('cache') as cache:
        for _ in range(2):
            with pytest.raises(OrderedSDFGeometryError) as caught:
                bad.boundary_curve(config)
            assert caught.value.__cause__ is not None
        assert cache.counts['component_report.hits'] == 1


def test_bounded_cache_eviction_nested_contexts_and_exception_cleanup():
    with validation_cache('cache', max_bytes=1000) as outer:
        for i in range(20):
            outer.memoize('test', lambda i=i: (i, bytes(200)), lambda: 1)
        assert outer.peak_bytes <= 1000 and outer.counts['evictions'] > 0
        with pytest.raises(RuntimeError):
            with validation_cache('certified') as inner:
                assert inner is current_validation_cache() and inner is not outer
                raise RuntimeError('fixture')
        assert current_validation_cache() is outer
    assert current_validation_cache() is None
    assert outer.retained_bytes == 0


def test_selection_is_opt_in_and_each_fit_has_its_own_cache():
    observed = []
    @fit_geometry_validation
    def fit():
        cache = current_validation_cache()
        if cache is not None:
            cache.memoize('test', lambda: ('value',), lambda: 1)
        return cache
    assert fit() is None
    with geometry_validation('cache', on_fit=observed.append):
        assert current_validation_cache() is None
        first, second = fit(), fit()
        assert current_validation_cache() is None  # independent endpoint scope
    assert first is not second
    assert len(observed) == 2
    assert all(x['counts']['test.misses'] == 1 for x in observed)
    assert first.retained_bytes == second.retained_bytes == 0


@pytest.mark.parametrize('mode', ['reference', 'cache', 'certified'])
@pytest.mark.parametrize('gap', [-.015, 0., .005, .01, .01000000000001, .035])
def test_pair_predicates_match_full_report_and_keep_strict_threshold(mode, gap):
    geometry = boundary(gap)
    settings = MultiComponentAssemblyConfig(minimum_absolute_clearance=.01, minimum_clearance_in_weights=0.)
    try:
        reference = adapt_multicomponent_boundary(geometry, config=settings)
        accepted = True
    except MultiComponentKressGeometryError:
        accepted = False
    with validation_cache(mode) as cache:
        for _ in range(2):
            if accepted:
                validate_multicomponent_admissibility(geometry, config=settings)
                detailed = adapt_multicomponent_boundary(geometry, config=settings)
                assert detailed.component_pair_reports == reference.component_pair_reports
            else:
                with pytest.raises(MultiComponentKressGeometryError):
                    validate_multicomponent_admissibility(geometry, config=settings)
        if mode == 'certified' and gap == .035:
            assert cache.counts['pair.certified'] == 2
        if mode == 'certified' and gap <= .01000000000001:
            assert cache.counts['pair.fallback'] == 2


def test_nested_components_and_changed_clearance_settings_never_reuse_acceptance():
    nested = OrderedBoundary2D((circle((.5,.5),.08,component_id='outer').discretize(32),
                               circle((.5,.5),.03,component_id='inner').discretize(32)))
    with validation_cache('certified'):
        with pytest.raises(MultiComponentKressGeometryError, match='nested'):
            validate_multicomponent_admissibility(nested)
        validate_multicomponent_admissibility(boundary(), config=MultiComponentAssemblyConfig(minimum_clearance_in_weights=0.))
        with pytest.raises(MultiComponentKressGeometryError, match='too close'):
            validate_multicomponent_admissibility(boundary(), config=MultiComponentAssemblyConfig(minimum_absolute_clearance=.1))


def test_certificate_bounds_match_reference_across_poses_scales_and_gaps():
    rng = np.random.default_rng(802)
    certified = 0
    for scale in (1e-6, 1., 1e6):
        settings = MultiComponentAssemblyConfig(minimum_absolute_clearance=.01*scale,
                                                minimum_clearance_in_weights=0.)
        for _ in range(20):
            angle = rng.uniform(0, 2*np.pi)
            offset = rng.uniform(.075,.16)*np.array([np.cos(angle), np.sin(angle)])
            first = circle((.5*scale,.5*scale), .04*scale, component_id='a').discretize(24)
            second = circle((np.array([.5,.5])+offset)*scale, .04*scale, component_id='b').discretize(32)
            bound = _axis_separation_certificate(first,second,settings)
            clearance, intersects, nested = _component_pair_clearance(first,second)
            if bound is not None:
                certified += 1
                assert not intersects and not nested
                assert clearance > settings.minimum_absolute_clearance
                assert bound <= clearance + 1e-14*scale
    assert certified > 15


def test_diagonal_overlapping_boxes_and_unsupported_scale_use_exact_fallback():
    first = circle((.5,.5),.04,component_id='a').discretize(32)
    second = circle((.56,.56),.04,component_id='b').discretize(32)
    settings = MultiComponentAssemblyConfig(minimum_absolute_clearance=0., minimum_clearance_in_weights=0.)
    assert _axis_separation_certificate(first,second,settings) is None
    geometry = OrderedBoundary2D((first,second))
    with validation_cache('certified') as cache:
        validate_multicomponent_admissibility(geometry,config=settings)
        assert cache.counts['pair.fallback'] == 1
    far = circle((100.,100.),.04,component_id='far').discretize(32)
    assert _axis_separation_certificate(first,far,settings) is None


def test_warm_adapter_does_not_bypass_canonical_grid_or_speed_checks():
    curve = circle((.5,.5),.04).discretize(16)
    with validation_cache('cache'):
        adapt_periodic_curve(curve)
        object.__setattr__(curve, 'parameters', curve.parameters+.01)
        with pytest.raises(ValueError, match='canonical'):
            adapt_periodic_curve(curve)


@pytest.mark.parametrize('nodes', [(64,128,256), (256,128,64)])
def test_saved_resolution_sensitive_failure_with_warm_cache(nodes):
    path = ROOT/'results/validation/topology/TOP-006-20260911-scenes-v1/runs/A/far-ellipse-star/checkpoint.json'
    state = driver.deserialize_state(json.loads(path.read_text())['state'])
    solve = driver.baseline.iteration01_solve_config()
    with validation_cache('certified'):
        for n in nodes:
            assert multiradial_geometry_admissible(state, driver.baseline._geometry_config(n),
                                                  solve_config=solve) == (n == 64)
