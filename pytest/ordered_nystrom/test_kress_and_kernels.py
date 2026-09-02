"""Kress normalization and cancellation-safe kernel stability tests."""

from __future__ import annotations

import numpy as np
import pytest

from gpr_bem_mod.ordered_nystrom import (
    PairGeometry,
    evaluate_muller_kernel_differences,
)
from periodic_kress import kress_log_weight_matrix, kress_log_weights


TWO_PI = 2.0 * np.pi
K_EXTERIOR = 12.0 - 0.1j
K_INTERIOR = 20.0 - 0.2j


@pytest.mark.parametrize("num_nodes", [16, 32, 64])
@pytest.mark.parametrize("mode", [1, 3, 7])
def test_kress_weights_integrate_resolved_fourier_modes(
    num_nodes: int,
    mode: int,
) -> None:
    if mode >= num_nodes // 2:
        pytest.skip("mode must lie below the Nyquist term")
    parameters = TWO_PI * np.arange(num_nodes, dtype=np.float64) / num_nodes
    matrix = kress_log_weight_matrix(num_nodes)
    expected_scale = -TWO_PI / mode

    cosine = matrix @ np.cos(mode * parameters)
    sine = matrix @ np.sin(mode * parameters)

    np.testing.assert_allclose(
        cosine,
        expected_scale * np.cos(mode * parameters),
        rtol=0.0,
        atol=8.0e-14,
    )
    np.testing.assert_allclose(
        sine,
        expected_scale * np.sin(mode * parameters),
        rtol=0.0,
        atol=8.0e-14,
    )


@pytest.mark.parametrize("num_nodes", [16, 32, 64])
def test_kress_weights_include_the_special_nyquist_mode(num_nodes: int) -> None:
    parameters = TWO_PI * np.arange(num_nodes, dtype=np.float64) / num_nodes
    mode = num_nodes // 2
    density = np.cos(mode * parameters)
    expected = -(TWO_PI / mode) * density
    np.testing.assert_allclose(
        kress_log_weight_matrix(num_nodes) @ density,
        expected,
        rtol=0.0,
        atol=8.0e-14,
    )


def test_kress_weight_inputs_and_ownership_are_explicit() -> None:
    weights = kress_log_weights(16)
    matrix = kress_log_weight_matrix(16)
    assert weights.shape == (16,)
    assert matrix.shape == (16, 16)
    assert not weights.flags.writeable
    assert not matrix.flags.writeable
    with pytest.raises(ValueError, match="even integer"):
        kress_log_weights(15)
    with pytest.raises(TypeError, match="not bool"):
        kress_log_weights(True)


def _circle_pair_geometry(separations: np.ndarray, radius: float = 0.05) -> PairGeometry:
    target = np.asarray((radius, 0.0))
    target_normal = np.asarray((1.0, 0.0))
    sources = radius * np.column_stack((np.cos(separations), np.sin(separations)))
    source_normals = np.column_stack((np.cos(separations), np.sin(separations)))
    displacement = target[None, :] - sources
    return PairGeometry(
        distance=np.linalg.norm(displacement, axis=1),
        displacement_dot_target_normal=displacement @ target_normal,
        displacement_dot_source_normal=np.einsum(
            "nd,nd->n",
            displacement,
            source_normals,
        ),
        normal_dot=source_normals @ target_normal,
    )


def test_power_log_series_and_direct_hankel_branches_agree_in_their_overlap() -> None:
    geometry = _circle_pair_geometry(np.asarray((0.2, 0.45, 0.8, 1.1)))
    series = evaluate_muller_kernel_differences(
        geometry,
        K_EXTERIOR,
        K_INTERIOR,
        near_argument=100.0,
        series_terms=24,
    )
    direct = evaluate_muller_kernel_differences(
        geometry,
        K_EXTERIOR,
        K_INTERIOR,
        near_argument=1.0e-12,
        series_terms=24,
    )
    assert series.near_pair_count == geometry.distance.size
    assert direct.direct_pair_count == geometry.distance.size

    for field in (
        "delta_v",
        "delta_k",
        "delta_kp",
        "delta_t",
        "log_v",
        "log_k",
        "log_kp",
        "log_t",
    ):
        first = getattr(series, field)
        second = getattr(direct, field)
        scale = max(float(np.max(np.abs(first))), float(np.max(np.abs(second))), 1.0e-300)
        assert np.max(np.abs(first - second)) / scale < 2.0e-11, field


def test_near_series_remains_finite_and_has_the_hypersingular_difference_limit() -> None:
    distances = np.asarray((1.0e-12, 1.0e-9, 1.0e-6))
    zeros = np.zeros_like(distances)
    geometry = PairGeometry(
        distance=distances,
        displacement_dot_target_normal=zeros,
        displacement_dot_source_normal=zeros,
        normal_dot=np.ones_like(distances),
    )
    evaluation = evaluate_muller_kernel_differences(
        geometry,
        K_EXTERIOR,
        K_INTERIOR,
    )

    assert evaluation.near_pair_count == distances.size
    for field in (
        "delta_v",
        "delta_k",
        "delta_kp",
        "delta_t",
        "log_v",
        "log_k",
        "log_kp",
        "log_t",
    ):
        values = getattr(evaluation, field)
        assert np.all(np.isfinite(values)), field
        assert not values.flags.writeable

    expected_log_t = -(K_EXTERIOR**2 - K_INTERIOR**2) / (4.0 * np.pi)
    np.testing.assert_allclose(
        evaluation.log_t[0],
        expected_log_t,
        rtol=2.0e-13,
        atol=2.0e-13,
    )


def test_pair_geometry_shape_and_finiteness_are_checked_before_broadcasting() -> None:
    malformed_shape = PairGeometry(
        distance=np.ones(2),
        displacement_dot_target_normal=np.ones(1),
        displacement_dot_source_normal=np.ones(2),
        normal_dot=np.ones(2),
    )
    with pytest.raises(ValueError, match="common shape"):
        evaluate_muller_kernel_differences(
            malformed_shape,
            K_EXTERIOR,
            K_INTERIOR,
        )

    nonfinite_projection = PairGeometry(
        distance=np.ones(2),
        displacement_dot_target_normal=np.asarray((0.0, np.nan)),
        displacement_dot_source_normal=np.ones(2),
        normal_dot=np.ones(2),
    )
    with pytest.raises(ValueError, match="finite"):
        evaluate_muller_kernel_differences(
            nonfinite_projection,
            K_EXTERIOR,
            K_INTERIOR,
        )
