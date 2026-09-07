"""Narrow integration checks against the repaired MLP package."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sdf_bem_multicomponent import (
    MultiComponentOrderedSDFGeometryConfig,
    build_multicomponent_ordered_sdf_geometry,
)
from sdf_inverse import OrderedSDFGeometryConfig, SmoothMLPSDF2D


def test_fixed_mlp_model_enters_automatic_boundary_seam_as_M1() -> None:
    """The new path accepts the real MLP type without changing its optimizer."""

    active_config = OrderedSDFGeometryConfig(
        bounds=((0.20, 0.20), (0.80, 0.80)),
        grid_shape=(97, 97),
        projected_samples=32,
        bandwidth=4,
        num_nodes=32,
        arclength_dense_resolution=64,
        validation_resolution=64,
    )
    automatic_config = MultiComponentOrderedSDFGeometryConfig.from_compatible_config(
        active_config
    )
    model = SmoothMLPSDF2D(
        bounds=active_config.bounds,
        hidden_features=8,
        hidden_layers=1,
        fourier_frequencies=(1.0,),
        geometric_center=(0.5, 0.5),
        geometric_radius=0.08,
        seed=17,
        dtype=torch.float64,
    )

    build = build_multicomponent_ordered_sdf_geometry(model, automatic_config)

    assert automatic_config.expected_num_components is None
    assert build.num_components == 1
    assert build.boundary.num_components == 1
    assert build.resolved_node_counts == (32,)
    np.testing.assert_allclose(
        build.component_diagnostics[0].centroid,
        (0.5, 0.5),
        atol=2.0e-7,
    )
    assert build.maximum_normalized_curve_residual < 1.0e-9
