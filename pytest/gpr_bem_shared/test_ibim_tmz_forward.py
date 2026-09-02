from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.special import hankel1

torch = pytest.importorskip("torch")

from gpr_bem.ibim_geometry import build_implicit_boundary_band, compress_implicit_boundary_band
from gpr_bem.ibim_tmz_forward import (
    apply_implicit_adjoint_double_layer_boundary_operator,
    apply_implicit_double_layer_boundary_operator,
    apply_implicit_hypersingular_boundary_operator,
    apply_implicit_single_layer_boundary_operator,
    build_implicit_adjoint_double_layer_boundary_matrix,
    build_implicit_boundary_operator_family,
    build_implicit_double_layer_boundary_matrix,
    build_implicit_hypersingular_boundary_matrix,
    build_implicit_single_layer_boundary_matrix,
    implicit_double_layer_normal_derivative_trace_from_band,
    implicit_double_layer_trace_from_band,
    implicit_double_layer_potential_from_band,
    implicit_single_layer_normal_derivative_trace_from_band,
    implicit_single_layer_trace_from_band,
    implicit_single_layer_potential_from_band,
)
from gpr_bem.neural_sdf import circle_signed_distance


def _circle_density(points: np.ndarray) -> np.ndarray:
    return 1.0 + 0.2 * points[:, 0] - 0.15 * points[:, 1]


def _reference_circle_layer_potential(
    receiver_points: np.ndarray,
    *,
    center: tuple[float, float],
    radius: float,
    wavenumber: complex,
    density_fn,
    kind: str,
    num_points: int = 8192,
) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, num_points, endpoint=False)
    circle_points = np.column_stack(
        (
            center[0] + radius * np.cos(theta),
            center[1] + radius * np.sin(theta),
        )
    )
    normals = np.column_stack((np.cos(theta), np.sin(theta)))
    ds = radius * (2.0 * np.pi / num_points)
    density = density_fn(circle_points)

    displacement = receiver_points[:, None, :] - circle_points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    if kind == "single":
        kernel = 0.25j * hankel1(0, wavenumber * distance)
    elif kind == "double":
        source_factor = np.einsum("mnd,nd->mn", displacement, normals, optimize=True) / distance
        kernel = 0.25j * wavenumber * hankel1(1, wavenumber * distance) * source_factor
    else:
        raise ValueError(f"Unsupported layer kind: {kind!r}")
    return np.einsum("mn,n->m", kernel, density * ds, optimize=True)


def test_implicit_single_layer_potential_matches_circle_reference() -> None:
    center = (0.1, -0.05)
    radius = 0.32
    wavenumber = 15.0
    receivers = np.array([[0.82, 0.22], [-0.6, 0.35]], dtype=float)
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(385, 385),
        dtype=torch.float64,
    )

    density = _circle_density(band.projected_points.detach().cpu().numpy())
    result = implicit_single_layer_potential_from_band(receivers, band, density, wavenumber)
    reference = _reference_circle_layer_potential(
        receivers,
        center=center,
        radius=radius,
        wavenumber=wavenumber,
        density_fn=_circle_density,
        kind="single",
    )

    np.testing.assert_allclose(np.asarray(result.potentials)[0], reference, rtol=2.0e-2, atol=2.0e-3)


def test_implicit_double_layer_potential_matches_circle_reference() -> None:
    center = (-0.12, 0.08)
    radius = 0.28
    wavenumber = 11.5
    receivers = np.array([[0.78, 0.18], [-0.72, -0.33]], dtype=float)
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(385, 385),
        dtype=torch.float64,
    )

    density = _circle_density(band.projected_points.detach().cpu().numpy())
    result = implicit_double_layer_potential_from_band(receivers, band, density, wavenumber)
    reference = _reference_circle_layer_potential(
        receivers,
        center=center,
        radius=radius,
        wavenumber=wavenumber,
        density_fn=_circle_density,
        kind="double",
    )

    np.testing.assert_allclose(np.asarray(result.potentials)[0], reference, rtol=2.0e-2, atol=2.0e-3)


def test_implicit_single_layer_potential_cupy_matches_numpy_when_available() -> None:
    cp = pytest.importorskip("cupy")

    center = (0.0, 0.0)
    radius = 0.25
    wavenumber = 9.0
    receivers = np.array([[0.73, -0.12], [-0.65, 0.28]], dtype=float)
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    density = _circle_density(band.projected_points.detach().cpu().numpy())

    numpy_result = implicit_single_layer_potential_from_band(receivers, band, density, wavenumber, backend="numpy")
    cupy_result = implicit_single_layer_potential_from_band(receivers, band, density, wavenumber, backend="cupy")

    np.testing.assert_allclose(cp.asnumpy(cupy_result.potentials)[0], np.asarray(numpy_result.potentials)[0], rtol=5.0e-6, atol=5.0e-8)


def test_compressed_boundary_samples_match_band_potential_evaluation() -> None:
    center = (0.0, 0.0)
    radius = 0.25
    wavenumber = 9.0
    receivers = np.array([[0.73, -0.12], [-0.65, 0.28]], dtype=float)
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    compressed = compress_implicit_boundary_band(band)
    band_density = _circle_density(band.projected_points.detach().cpu().numpy())
    compressed_density = _circle_density(compressed.points.detach().cpu().numpy())

    band_result = implicit_single_layer_potential_from_band(receivers, band, band_density, wavenumber)
    compressed_result = implicit_single_layer_potential_from_band(receivers, compressed, compressed_density, wavenumber)

    np.testing.assert_allclose(
        np.asarray(compressed_result.potentials)[0],
        np.asarray(band_result.potentials)[0],
        rtol=2.0e-2,
        atol=2.0e-3,
    )


def test_implicit_single_layer_trace_is_continuous_across_boundary() -> None:
    center = (0.0, 0.0)
    radius = 0.31
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    density = _circle_density(band.projected_points.detach().cpu().numpy())
    trace = implicit_single_layer_trace_from_band(band, density, 7.5)

    outside = np.asarray(trace.outside_potentials)[0]
    inside = np.asarray(trace.inside_potentials)[0]
    jump = np.asarray(trace.jump_potentials)[0]

    assert np.mean(np.abs(outside - inside)) < 3.0e-3
    assert np.max(np.abs(outside - inside)) < 3.0e-3
    assert np.mean(np.abs(jump)) < 3.0e-3


def test_implicit_double_layer_trace_has_expected_jump_for_constant_density() -> None:
    center = (0.0, 0.0)
    radius = 0.4
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(385, 385),
        dtype=torch.float64,
    )
    density = np.ones(band.num_samples, dtype=np.complex128)
    trace = implicit_double_layer_trace_from_band(band, density, 8.0, offset_distance=2.0e-3)

    jump = np.asarray(trace.jump_potentials)[0]
    average = np.asarray(trace.average_potentials)[0]

    assert abs(np.mean(jump.real) - 1.0) < 3.5e-2
    assert np.std(jump.real) < 8.0e-2
    assert np.mean(np.abs(jump.imag)) < 2.0e-2
    assert np.isfinite(average).all()


def test_boundary_operator_apply_wrappers_match_trace_averages() -> None:
    center = (0.0, 0.0)
    radius = 0.29
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    density = _circle_density(band.projected_points.detach().cpu().numpy())

    single_trace = implicit_single_layer_trace_from_band(band, density, 6.5, offset_distance=1.0e-3)
    double_trace = implicit_double_layer_trace_from_band(band, density, 6.5, offset_distance=1.0e-3)
    single_apply = apply_implicit_single_layer_boundary_operator(band, density, 6.5, offset_distance=1.0e-3)
    double_apply = apply_implicit_double_layer_boundary_operator(band, density, 6.5, offset_distance=1.0e-3)

    np.testing.assert_allclose(
        np.asarray(single_apply),
        np.asarray(single_trace.average_potentials),
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        np.asarray(double_apply),
        np.asarray(double_trace.average_potentials),
        rtol=1.0e-12,
        atol=1.0e-12,
    )


def test_boundary_operator_matrices_match_apply_wrappers_on_compressed_samples() -> None:
    center = (0.0, 0.0)
    radius = 0.29
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    compressed = compress_implicit_boundary_band(band)
    density = _circle_density(compressed.points.detach().cpu().numpy()).astype(np.complex128)
    offset = 1.0e-3

    single_matrix = build_implicit_single_layer_boundary_matrix(compressed, 6.5, offset_distance=offset)
    double_matrix = build_implicit_double_layer_boundary_matrix(compressed, 6.5, offset_distance=offset)
    single_apply = apply_implicit_single_layer_boundary_operator(compressed, density, 6.5, offset_distance=offset)
    double_apply = apply_implicit_double_layer_boundary_operator(compressed, density, 6.5, offset_distance=offset)

    np.testing.assert_allclose(
        np.asarray(single_matrix.matrix)[0] @ density,
        np.asarray(single_apply)[0],
        rtol=2.0e-10,
        atol=2.0e-10,
    )
    np.testing.assert_allclose(
        np.asarray(double_matrix.matrix)[0] @ density,
        np.asarray(double_apply)[0],
        rtol=2.0e-10,
        atol=2.0e-10,
    )

    adjoint_double_matrix = build_implicit_adjoint_double_layer_boundary_matrix(
        compressed,
        6.5,
        offset_distance=offset,
    )
    hypersingular_matrix = build_implicit_hypersingular_boundary_matrix(
        compressed,
        6.5,
        offset_distance=offset,
    )
    adjoint_double_apply = apply_implicit_adjoint_double_layer_boundary_operator(
        compressed,
        density,
        6.5,
        offset_distance=offset,
    )
    hypersingular_apply = apply_implicit_hypersingular_boundary_operator(
        compressed,
        density,
        6.5,
        offset_distance=offset,
    )

    np.testing.assert_allclose(
        np.asarray(adjoint_double_matrix.matrix)[0] @ density,
        np.asarray(adjoint_double_apply)[0],
        rtol=2.0e-10,
        atol=2.0e-10,
    )
    np.testing.assert_allclose(
        np.asarray(hypersingular_matrix.matrix)[0] @ density,
        np.asarray(hypersingular_apply)[0],
        rtol=2.0e-10,
        atol=2.0e-10,
    )


def test_boundary_operator_family_matches_individual_matrix_builders() -> None:
    center = (0.0, 0.0)
    radius = 0.31
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    compressed = compress_implicit_boundary_band(band)
    wavenumbers = np.array([5.0, 8.5], dtype=np.complex128)
    offset = 1.0e-3

    family = build_implicit_boundary_operator_family(compressed, wavenumbers, offset_distance=offset)
    single = build_implicit_single_layer_boundary_matrix(compressed, wavenumbers, offset_distance=offset)
    double = build_implicit_double_layer_boundary_matrix(compressed, wavenumbers, offset_distance=offset)
    adjoint_double = build_implicit_adjoint_double_layer_boundary_matrix(compressed, wavenumbers, offset_distance=offset)
    hypersingular = build_implicit_hypersingular_boundary_matrix(compressed, wavenumbers, offset_distance=offset)

    assert family.num_boundary_samples == compressed.num_samples
    np.testing.assert_allclose(np.asarray(family.wavenumbers), wavenumbers)
    np.testing.assert_allclose(np.asarray(family.single_layer_matrix), np.asarray(single.matrix), rtol=0.0, atol=0.0)
    np.testing.assert_allclose(np.asarray(family.double_layer_matrix), np.asarray(double.matrix), rtol=0.0, atol=0.0)
    np.testing.assert_allclose(
        np.asarray(family.adjoint_double_layer_matrix),
        np.asarray(adjoint_double.matrix),
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        np.asarray(family.hypersingular_matrix),
        np.asarray(hypersingular.matrix),
        rtol=0.0,
        atol=0.0,
    )


def test_normal_derivative_trace_wrappers_are_finite_on_compressed_samples() -> None:
    center = (0.0, 0.0)
    radius = 0.3
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(points, center=center, radius=radius),
        ((-1.0, -1.0), (1.0, 1.0)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    compressed = compress_implicit_boundary_band(band)
    density = _circle_density(compressed.points.detach().cpu().numpy())
    offset = 1.0e-3

    single_derivative_trace = implicit_single_layer_normal_derivative_trace_from_band(
        compressed,
        density,
        7.0,
        offset_distance=offset,
    )
    double_derivative_trace = implicit_double_layer_normal_derivative_trace_from_band(
        compressed,
        density,
        7.0,
        offset_distance=offset,
    )

    assert np.isfinite(np.asarray(single_derivative_trace.average_normal_derivative)).all()
    assert np.isfinite(np.asarray(double_derivative_trace.average_normal_derivative)).all()
