"""SPD-014 preserves exact sampled counts, cache ownership and refusals."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

import numpy as np
import pytest

from ordered_boundary import sampled_self_intersection_count
from ordered_boundary import spatial_validation as spatial
from ordered_boundary.validation import _self_intersection_count
from ordered_boundary.validation_cache import (
    current_intersection_backend, current_validation_cache,
    intersection_validation, validation_cache,
)
from experiments.spd014_geometry.runtime import cache_diagnostic, geometry_acceleration


def count(points, backend, tolerance=1e-12):
    with intersection_validation(backend):
        return sampled_self_intersection_count(points, relative_tolerance=tolerance)


def fixtures():
    rng = np.random.default_rng(14014)
    polygons = [rng.normal(size=(n, 2)) for n in (3, 4, 8, 31, 64, 129) for _ in range(5)]
    polygons += [np.array(p, float) for p in (
        [[0, 0], [1, 1], [0, 1], [1, 0]],
        [[0, 0], [2, 0], [1, 0], [1, 1]],
        [[0, 0], [1, 0], [1, 0], [1, 1], [0, 1]],
        [[0, 0], [0, 0], [0, 0]],
        [[0, 0], [1, 0], [.5, 1e-13], [.5, 1]],
        [[0, 0], [1, 0], [.5, 1e-10], [.5, 1]],
        [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
    )]
    theta = np.linspace(0, 2*np.pi, 257, endpoint=False)
    polygons += [np.column_stack((np.cos(theta), np.sin(theta))),
                 np.column_stack((np.cos(theta**2/(2*np.pi)), np.sin(theta**2/(2*np.pi))))]
    return polygons


@pytest.mark.parametrize("scale,offset", [(1., 0.), (1e-6, 0.), (2., 1e6), (1e3, -1e9)])
@pytest.mark.parametrize("tolerance", [0., 1e-12, 1e-6])
def test_spatial_counts_match_reference_on_adversarial_polygons(scale, offset, tolerance):
    for polygon in fixtures():
        points = polygon*scale + offset
        assert count(points, 'spatial', tolerance) == count(points, 'reference', tolerance)


def test_resolved_absolute_tolerances_keep_dense_predicate_semantics():
    # Continuous parameterization validation supplies already-resolved tolerances.
    for polygon in fixtures()[-9:]:
        for cross, length in ((0., 0.), (1e-4, 0.), (0., 1e-4), (1e-12, 1e-5)):
            with intersection_validation('reference'):
                expected = _self_intersection_count(polygon, cross, length)
            with intersection_validation('spatial'):
                assert _self_intersection_count(polygon, cross, length) == expected


@pytest.mark.parametrize('vertices,stride', [(5, 2), (9, 4)])
@pytest.mark.parametrize('tolerance', [0., 1e-20])
def test_subdivided_stars_below_orientation_roundoff_use_reference(
        monkeypatch, vertices, stride, tolerance):
    corners = np.exp(2j*np.pi*stride*np.arange(vertices)/vertices)
    t = np.linspace(0, 1, 40, endpoint=False)
    samples = np.concatenate([a+(b-a)*t for a, b in zip(corners, np.roll(corners, -1))])
    points = np.column_stack((samples.real, samples.imag))
    def unexpected_tree(*args):
        raise AssertionError('Sub-roundoff orientations require dense fallback')
    monkeypatch.setattr(spatial, '_make_tree', unexpected_tree)
    expected = count(points, 'reference', tolerance)
    assert expected > 0
    assert count(points, 'spatial', tolerance) == expected


def test_production_tolerance_still_uses_spatial_pruning(monkeypatch):
    theta = np.linspace(0, 2*np.pi, 512, endpoint=False)
    points = np.column_stack((np.cos(theta), np.sin(theta)))
    def unexpected_fallback(*args):
        raise AssertionError('Production tolerance should permit pruning')
    assert spatial.spatial_self_intersection_count(
        points, 1e-12, 1e-12, fallback=unexpected_fallback) == 0


def test_dense_candidates_fall_back_before_materializing_pairs(monkeypatch):
    rng = np.random.default_rng(14)
    polygon = rng.normal(size=(512, 2))
    real_tree = spatial._make_tree

    class CountOnlyTree:
        def __init__(self, values):
            self.tree = real_tree(values)

        def count_neighbors(self, other, radius):
            return self.tree.count_neighbors(other.tree, radius)

        def query_pairs(self, *args, **kwargs):
            raise AssertionError('Dense candidate sets must not be materialized')

    monkeypatch.setattr(spatial, '_make_tree', CountOnlyTree)
    assert spatial._candidate_pairs(polygon, 1e-12) is None
    assert count(polygon, 'spatial') == count(polygon, 'reference')


def test_local_candidates_and_nonuniform_segments():
    t = np.linspace(0, 2*np.pi, 1024, endpoint=False)
    circle = np.column_stack((np.cos(t), np.sin(t)))
    pairs = spatial._candidate_pairs(circle, 1e-12)
    assert pairs is not None and len(pairs) < len(circle)
    # One long chord makes pruning poor; dense fallback still preserves counts.
    circle[400] = [20., -20.]
    assert spatial._candidate_pairs(circle, 1e-12) is None
    assert count(circle, 'spatial') == count(circle, 'reference')


def test_extreme_coordinates_take_the_dense_fallback():
    polygon = np.array([[1e200, 0.], [0., 1e200], [-1e200, 0.], [0., -1e200]])
    calls = []
    def fallback(*args):
        calls.append(args)
        return 17
    assert spatial.spatial_self_intersection_count(polygon, 0., 0., fallback=fallback) == 17
    assert len(calls) == 1


@pytest.mark.parametrize('bad,tolerance', [
    (np.zeros((2, 2)), 1e-12), (np.zeros((3, 3)), 1e-12),
    (np.array([[0., 0.], [1., 0.], [np.nan, 1.]]), 1e-12),
    (np.zeros((3, 2)), -1.), (np.zeros((3, 2)), np.inf),
])
def test_public_errors_are_identical(bad, tolerance):
    errors = []
    for backend in ('reference', 'spatial'):
        with pytest.raises(ValueError) as error:
            count(bad, backend, tolerance)
        errors.append(str(error.value))
    assert errors[0] == errors[1]


def test_mode_scopes_restore_and_cache_keys_do_not_hide_ab_comparisons():
    polygon = np.array([[0., 0.], [1., 1.], [0., 1.], [1., 0.]])
    assert current_intersection_backend() == 'reference'
    with validation_cache('cache') as cache:
        for backend in ('reference', 'spatial'):
            with intersection_validation(backend):
                assert count(polygon, backend) == 1
                assert count(polygon.copy(), backend) == 1
        assert cache.counts['self_intersection.misses'] == 2
        assert cache.counts['self_intersection.hits'] == 2
    with pytest.raises(RuntimeError):
        with intersection_validation('spatial'):
            assert current_intersection_backend() == 'spatial'
            raise RuntimeError
    assert current_intersection_backend() == 'reference'
    with pytest.raises(ValueError):
        with intersection_validation('typo'):
            pass


def test_threads_share_selected_algorithm_and_exact_cache():
    polygon = fixtures()[-1]
    def work():
        assert current_intersection_backend() == 'spatial'
        return sampled_self_intersection_count(polygon)
    with intersection_validation('spatial'), validation_cache('cache') as cache:
        with ThreadPoolExecutor(4) as pool:
            futures = [pool.submit(copy_context().run, work) for _ in range(19)]
            assert [f.result() for f in futures] == [0]*19
        assert cache.counts['self_intersection.misses'] == 1
        assert cache.counts['self_intersection.hits'] == 18


def test_diagnostic_scope_uses_fresh_cache_and_preserves_existing_reference_mode():
    polygon = fixtures()[-1]
    snapshots = []
    @cache_diagnostic
    def diagnostic():
        assert current_validation_cache() is not None
        for _ in range(19):
            sampled_self_intersection_count(polygon)
        snapshots.append(current_validation_cache().snapshot())
        return 'value'
    with geometry_acceleration('both'):
        assert diagnostic() == diagnostic() == 'value'
        assert current_validation_cache() is None
        assert all(s['counts']['self_intersection.misses'] == 1 for s in snapshots)
        with validation_cache('reference') as existing:
            diagnostic()
            assert current_validation_cache() is existing
            assert existing.counts['self_intersection.misses'] == 19
    assert current_validation_cache() is None


def test_diagnostic_exception_cleans_up_and_no_cache_arm_is_unchanged():
    @cache_diagnostic
    def failure():
        raise ValueError('original error')
    with geometry_acceleration('cache'), pytest.raises(ValueError, match='original error'):
        failure()
    assert current_validation_cache() is None
    @cache_diagnostic
    def uncached():
        return current_validation_cache()
    with geometry_acceleration('reference'):
        assert uncached() is None


@pytest.mark.parametrize('gap', [-.015, 0., .005, .04])
def test_kress_multicomponent_clearance_and_refusals_are_preserved(gap):
    from ordered_boundary import circle, OrderedBoundary2D
    from gpr_bem_kress.multicomponent import (
        adapt_multicomponent_boundary, MultiComponentAssemblyConfig,
        MultiComponentKressGeometryError,
    )
    boundary = OrderedBoundary2D(tuple(
        circle((x, .5), .04, component_id=str(i)).discretize(32)
        for i, x in enumerate((.46-gap/2, .54+gap/2))))
    config = MultiComponentAssemblyConfig(minimum_absolute_clearance=.01,
                                          minimum_clearance_in_weights=0.)
    results = []
    for backend in ('reference', 'spatial'):
        with intersection_validation(backend):
            try:
                report = adapt_multicomponent_boundary(boundary, config=config)
                result = (True, report.component_pair_reports, report.minimum_intercomponent_clearance)
            except MultiComponentKressGeometryError as error:
                result = (False, type(error), str(error))
        results.append(result)
    assert results[0] == results[1]
