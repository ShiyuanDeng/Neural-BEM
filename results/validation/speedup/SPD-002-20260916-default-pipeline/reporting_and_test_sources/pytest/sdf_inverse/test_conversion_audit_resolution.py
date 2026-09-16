"""Audit density can vary independently without changing production defaults."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from sdf_inverse.geometry import OrderedSDFGeometryConfig, _conversion_audit_levels


def test_explicit_audit_resolution_is_independent_of_production(monkeypatch):
    import sdf_inverse.geometry as geometry
    seen = []
    points = np.zeros((3, 2))
    def prepare(field, config):
        seen.append((config.grid_shape, config.projected_samples))
        return SimpleNamespace(projected_points=points)
    monkeypatch.setattr(geometry, "prepare_single_component", prepare)
    config = OrderedSDFGeometryConfig(bounds=((0., 0.), (1., 1.)),
        conversion_audit_grid_shape=(65, 81), conversion_audit_samples=192)
    field = SimpleNamespace(dtype=torch.float64)
    parameterization = SimpleNamespace(discretize=lambda n: SimpleNamespace(points=points))
    for production in (config, replace(config, grid_shape=(513, 513), bandwidth=20)):
        list(_conversion_audit_levels(field, parameterization, production))
    assert seen == [((65, 81), 192), ((129, 161), 384)] * 2


@pytest.mark.parametrize("kwargs", [
    {"conversion_audit_samples": 7}, {"conversion_audit_samples": True},
    {"conversion_audit_grid_shape": (1, 65)}, {"conversion_audit_grid_shape": (65,)},
])
def test_invalid_explicit_audit_resolution(kwargs):
    with pytest.raises((TypeError, ValueError)):
        OrderedSDFGeometryConfig(bounds=((0., 0.), (1., 1.)), **kwargs)


def test_measurement_reports_both_directions_without_relaxing_failed_limits(monkeypatch):
    import sdf_inverse.geometry as geometry
    raw = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
    converted = 0.9 * raw + 0.05
    component = SimpleNamespace(component_id="component_000",
        raw_diagnostics=SimpleNamespace(self_intersection_count=0),
        projected_diagnostics=SimpleNamespace(self_intersection_count=0),
        projection_passes=(SimpleNamespace(maximum_residual=0.),))
    reference = SimpleNamespace(projected_points=raw, num_components=1, single_component=component)
    monkeypatch.setattr(geometry, "_conversion_audit_levels", lambda *args: iter([
        (32, (65, 65), reference, converted), (64, (129, 129), reference, converted)]))
    config = OrderedSDFGeometryConfig(bounds=((0., 0.), (1., 1.)), conversion_tolerance_m=.0002)
    report = geometry.measure_conversion_fidelity(None, None, config)
    assert report["levels"][0]["raw_to_converted_m"] == pytest.approx(np.sqrt(2.) * .05)
    assert report["levels"][0]["converted_to_raw_m"] == pytest.approx(.05)
    assert report["fidelity_pass"] is False
    assert report["rejection_reasons"] == ["conversion_distance"]
    assert report["refinement_tolerance_m"] == pytest.approx(.00001)
    assert report["topology_pass"] is True
