"""Focused checks for the optional marching-squares component ceiling."""

from __future__ import annotations

import numpy as np
import pytest

from sdf_to_ordered_boundary import ComponentLimitError
from sdf_to_ordered_boundary.fields import CallableImplicitField2D
from sdf_to_ordered_boundary.frontend import FrontendConfig, extract_frontend_components


def _two_circle_field(*, gradient_calls: list[int] | None = None) -> CallableImplicitField2D:
    centers = np.asarray(((-0.65, 0.0), (0.65, 0.0)), dtype=np.float64)
    radius = 0.31

    def value(points: np.ndarray) -> np.ndarray:
        offsets = points[..., None, :] - centers
        return np.min(np.linalg.norm(offsets, axis=-1) - radius, axis=-1)

    def gradient(points: np.ndarray) -> np.ndarray:
        if gradient_calls is not None:
            gradient_calls[0] += 1
        offsets = points[..., None, :] - centers
        distances = np.linalg.norm(offsets, axis=-1)
        selected = np.argmin(distances, axis=-1)
        flat_offsets = offsets.reshape(-1, 2, 2)
        flat_distances = distances.reshape(-1, 2)
        flat_selected = selected.reshape(-1)
        rows = np.arange(flat_selected.size)
        result = (
            flat_offsets[rows, flat_selected]
            / flat_distances[rows, flat_selected, None]
        )
        return result.reshape(points.shape)

    return CallableImplicitField2D(
        value,
        gradient,
        name="two_circles_component_limit_fixture",
        is_signed_distance=True,
    )


def _config(**changes: object) -> FrontendConfig:
    arguments: dict[str, object] = {
        "bounds": ((-1.2, -0.7), (1.2, 0.7)),
        "grid_shape": (65, 109),
        "projected_samples": 32,
        "second_resample_and_project": False,
    }
    arguments.update(changes)
    return FrontendConfig(**arguments)


def test_component_limit_rejects_immediately_after_contour_discovery() -> None:
    gradient_calls = [0]

    with pytest.raises(ComponentLimitError) as captured:
        extract_frontend_components(
            _two_circle_field(gradient_calls=gradient_calls),
            _config(maximum_num_components=1),
        )

    assert captured.value.actual == 2
    assert captured.value.maximum == 1
    assert "exceeds maximum_num_components" in str(captured.value)
    assert gradient_calls == [0]


def test_none_default_preserves_results_and_equal_limit_allows_preparation() -> None:
    default_config = _config()
    assert default_config.maximum_num_components is None
    baseline = extract_frontend_components(_two_circle_field(), default_config)

    gradient_calls = [0]
    bounded = extract_frontend_components(
        _two_circle_field(gradient_calls=gradient_calls),
        _config(maximum_num_components=2),
    )

    assert bounded.num_components == baseline.num_components == 2
    assert gradient_calls[0] > 0
    for baseline_component, bounded_component in zip(
        baseline.components,
        bounded.components,
    ):
        assert bounded_component.component_id == baseline_component.component_id
        np.testing.assert_array_equal(
            bounded_component.projected_points,
            baseline_component.projected_points,
        )


@pytest.mark.parametrize("value", (0, -1))
def test_component_limit_requires_a_positive_value(value: int) -> None:
    with pytest.raises(ValueError, match="maximum_num_components"):
        _config(maximum_num_components=value)


@pytest.mark.parametrize("value", (True, 1.5))
def test_component_limit_rejects_non_integer_values(value: object) -> None:
    with pytest.raises(TypeError, match="maximum_num_components"):
        _config(maximum_num_components=value)
