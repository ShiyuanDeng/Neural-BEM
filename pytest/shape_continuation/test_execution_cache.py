"""SC-030: exact geometry reuse, including negative results and fit isolation."""
from dataclasses import replace

import numpy as np
import pytest

from ordered_boundary.validation_cache import current_validation_cache, geometry_validation, validation_cache
from experiments.shape_continuation import lm_backend as lm
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.validation import self_intersections


def test_hybrid_keys_include_points_order_resolution_and_tolerance():
    points = FourierCurve.circle().nodes(32).points
    with validation_cache('cache') as cache:
        assert self_intersections(points) == self_intersections(points.copy()) == 0
        assert cache.counts['hybrid_self_intersection.hits'] == 1
        self_intersections(points, 2e-12)
        shifted = points.copy(); shifted[0, 0] = np.nextafter(shifted[0, 0], np.inf)
        self_intersections(shifted)
        self_intersections(points[::-1])
        self_intersections(FourierCurve.circle().nodes(64).points)
        assert cache.counts['hybrid_self_intersection.misses'] == 5


def test_crossing_count_is_cached_but_remains_invalid():
    points = np.array([[0., 0.], [1., 1.], [0., 1.], [1., 0.]])
    expected = self_intersections(points)
    assert expected > 0
    with validation_cache('cache') as cache:
        assert self_intersections(points) == self_intersections(points) == expected
        assert cache.counts['hybrid_self_intersection.hits'] == 1
        for tolerance in (-1., np.nan):
            with pytest.raises(ValueError):
                self_intersections(points, tolerance)
        with pytest.raises(ValueError):
            self_intersections([[np.nan, 0.]] * 3)
        assert cache.counts['hybrid_self_intersection.requests'] == 2


def test_real_fit_entry_cleans_scope_on_exception():
    curve = FourierCurve.circle()
    stage = lm.FitStage('test', (None,), (1.,), (1e-5,), 0, 2, 8, 16, 0)
    snapshots = []
    with geometry_validation('cache', on_fit=snapshots.append):
        for _ in range(2):
            with pytest.raises(ValueError, match='storage band'):
                lm.fit_stage(curve, stage, 1., None, lm.BackendConfig(), lm.Ledger())
            assert current_validation_cache() is None
    assert len(snapshots) == 2 and all(s['entries'] == 0 for s in snapshots)


def test_zero_cache_budget_preserves_result():
    points = FourierCurve.circle().nodes(32).points
    with validation_cache('cache', max_bytes=0) as cache:
        assert self_intersections(points) == self_intersections(points) == 0
        assert cache.counts['hybrid_self_intersection.hits'] == 0
        assert cache.counts['oversize_entries'] == 2
        assert cache.peak_bytes == 0
