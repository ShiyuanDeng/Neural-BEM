"""The ordered inverse must preserve the field's material-side convention."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sdf_inverse.geometry import (
    OrderedSDFGeometryConfig,
    OrderedSDFGeometryError,
    build_ordered_sdf_geometry,
)
from sdf_inverse.models import CircleSDF2D


@pytest.mark.parametrize("scale", (-1.0, 1.0, 2.0))
def test_ordering_cannot_turn_a_negative_exterior_into_an_inclusion(scale):
    class ScaledCircle(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.circle = CircleSDF2D(center=(0.5, 0.5), radius=0.05)

        def forward(self, points):
            return scale * self.circle(points)

    model = ScaledCircle()
    config = OrderedSDFGeometryConfig(
        bounds=((0.35, 0.35), (0.65, 0.65)), grid_shape=(65, 65),
        projected_samples=32, bandwidth=4, num_nodes=32,
        arclength_dense_resolution=64, validation_resolution=64,
    )
    if scale < 0.0:
        with pytest.raises(OrderedSDFGeometryError, match="negative_inside"):
            build_ordered_sdf_geometry(model, config)
    else:
        geometry = build_ordered_sdf_geometry(model, config)
        np.testing.assert_allclose(
            np.linalg.norm(geometry.curve.points - 0.5, axis=1), 0.05,
            atol=1.0e-8, rtol=0.0,
        )
