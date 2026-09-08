"""Exact scalar/vectorized replay, including cyclic and degenerate contacts."""

import numpy as np
import pytest

from sdf_to_ordered_boundary.frontend import (
    _polygon_self_intersection_count_legacy,
    polygon_diagnostics,
    polygon_self_intersection_count,
    PolygonValidationError,
)


@pytest.mark.parametrize("points", [
    [[0., 0.], [1., 0.], [0., 1.]],
    [[0., 0.], [1., 1.], [0., 1.], [1., 0.]],
    [[0., 0.], [2., 0.], [1., 0.], [3., 0.], [0., 1.]],
    [[0., 0.], [1., 0.], [1., 0.], [1., 1.], [0., 1.]],
    [[0., 0.], [2., 0.], [2., 2.], [1., 0.], [0., 2.]],
    [[0., 0.]] * 5,
])
@pytest.mark.parametrize("scale", [1.e-9, 1., 1.e9])
@pytest.mark.parametrize("tolerance", [0., 1.e-12, 1.e-4])
def test_degenerate_contacts_match_legacy(points, scale, tolerance):
    polygon = np.asarray(points) * scale
    expected = _polygon_self_intersection_count_legacy(polygon, relative_tolerance=tolerance)
    for variant in (polygon, polygon[::-1], np.roll(polygon, 2, axis=0)):
        assert polygon_self_intersection_count(variant, relative_tolerance=tolerance) == expected


@pytest.mark.parametrize("count", [7, 127, 128, 129, 257])
def test_cross_tile_pairs_match_scalar_oracle(count):
    random = np.random.default_rng(count)
    polygon = random.normal(size=(count, 2))
    assert polygon_self_intersection_count(polygon) == _polygon_self_intersection_count_legacy(polygon)


@pytest.mark.parametrize("gap", [-2.e-12, -1.e-14, 0., 1.e-14, 2.e-12])
def test_near_self_contact_at_tolerance_boundary(gap):
    polygon = np.array([[0., 0.], [2., 0.], [2., 1.], [1., gap], [0., 1.]])
    assert polygon_self_intersection_count(polygon) == _polygon_self_intersection_count_legacy(polygon)


def test_topology_rejection_message_and_orientation_match_legacy(monkeypatch):
    import sdf_to_ordered_boundary.frontend as frontend
    polygons = [np.array([[0., 0.], [2., 0.], [2., 2.], [1., 0.], [0., 2.]]),
                np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])]
    for polygon in polygons:
        outcomes = []
        for counter in (_polygon_self_intersection_count_legacy, polygon_self_intersection_count):
            monkeypatch.setattr(frontend, "polygon_self_intersection_count", counter)
            try:
                outcomes.append(polygon_diagnostics(polygon))
            except PolygonValidationError as exc:
                outcomes.append((type(exc), str(exc)))
        assert outcomes[0] == outcomes[1]
