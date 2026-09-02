"""Kernel-identity checks for the Phase 1 shape-derivative building blocks.

Per ``docs/legacy/adjoint_inverse_rebuild_plan.md`` Phase 1 and
``docs/ibim_shape_derivative.md`` S11 item 2: these new kernels must be
checked against central differences of the already-trusted forward potential
functions *before* anything in ``ibim_tmz_adjoint.py`` is wired to depend on
them. No solver, no SDF, no boundary compression involved -- a synthetic,
deliberately irregular point cloud is enough, since these are pointwise
kernel identities, not geometry checks.

``gpr_bem_mod``-specific: these functions do not exist in ``gpr_bem_ref`` or
``gpr_bem_kdiff``, so this file imports the real package name directly
(the ``test_circle_comparison.py`` convention), not the bare ``gpr_bem``
alias ``--solver`` resolves.
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import gpr_bem_mod
from gpr_bem_mod.ibim_geometry import ImplicitBoundarySamples2D
from gpr_bem_mod.ibim_tmz_forward import (
    implicit_double_layer_normal_derivative_potential_from_band,
    implicit_greens_function_mixed_directional_hessian_potential_from_band,
    implicit_greens_function_pure_source_hessian_potential_from_band,
    implicit_greens_function_pure_target_hessian_potential_from_band,
    implicit_greens_function_third_derivative_one_target_two_source_potential_from_band,
    implicit_greens_function_third_derivative_two_target_one_source_potential_from_band,
    implicit_single_layer_normal_derivative_potential_from_band,
    implicit_single_layer_potential_from_band,
    implicit_single_layer_source_directional_derivative_potential_from_band,
)

_WAVENUMBER = np.array([12.3 + 0.7j], dtype=np.complex128)
_EPS = 1.0e-4


def _synthetic_boundary(rng: np.random.Generator, *, num_samples: int = 6) -> ImplicitBoundarySamples2D:
    # Deliberately irregular, not a circle -- these are pointwise kernel
    # identities and must hold for any point cloud, not just a nice one.
    points = torch.tensor(
        rng.normal(size=(num_samples, 2)) * 0.15 + np.array([-0.2, 0.4]),
        dtype=torch.float64,
    )
    raw_normals = rng.normal(size=(num_samples, 2))
    normals = torch.tensor(
        raw_normals / np.linalg.norm(raw_normals, axis=1, keepdims=True),
        dtype=torch.float64,
    )
    weights = torch.tensor(0.05 + rng.random(num_samples) * 0.05, dtype=torch.float64).reshape(-1, 1)
    return ImplicitBoundarySamples2D(
        points=points,
        normals=normals,
        quadrature_weights=weights,
        strict_quadrature_weights=weights,
        merge_distance=0.05,
        source_num_samples=num_samples,
        bounds=((-1.0, -1.0), (1.0, 1.0)),
        level=0.0,
    )


def _with_shifted_points(band: ImplicitBoundarySamples2D, delta: np.ndarray) -> ImplicitBoundarySamples2D:
    shifted = band.points + torch.tensor(delta, dtype=band.points.dtype)
    return ImplicitBoundarySamples2D(
        points=shifted,
        normals=band.normals,
        quadrature_weights=band.quadrature_weights,
        strict_quadrature_weights=band.strict_quadrature_weights,
        merge_distance=band.merge_distance,
        source_num_samples=band.source_num_samples,
        bounds=band.bounds,
        level=band.level,
    )


def _identity_density(num_samples: int) -> np.ndarray:
    return np.eye(num_samples, dtype=np.complex128)


def test_source_directional_derivative_reproduces_existing_double_layer_kernel() -> None:
    """Regression check: passing band.normals as source_direction must
    reproduce the existing, already-validated double-layer kernel exactly --
    the new function is a strict generalization, not a re-derivation."""

    rng = np.random.default_rng(0)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)

    generalized = implicit_single_layer_source_directional_derivative_potential_from_band(
        receivers, band, band.normals.detach().cpu().numpy(), density, _WAVENUMBER
    )
    from gpr_bem_mod.ibim_tmz_forward import implicit_double_layer_potential_from_band

    existing = implicit_double_layer_potential_from_band(receivers, band, density, _WAVENUMBER).potentials
    np.testing.assert_allclose(generalized, existing, rtol=1e-12, atol=1e-14)


def test_source_directional_derivative_matches_finite_difference() -> None:
    """grad_y G . v, v varying per source column, against central differences
    of implicit_single_layer_potential_from_band with the whole point cloud
    shifted by tau*v (only column n's own point affects column n's kernel
    entry, so this isolates each column correctly -- see the derivation
    doc's S11 item 2 rationale)."""

    rng = np.random.default_rng(1)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)
    direction = rng.normal(size=(band.num_samples, 2))

    closed_form = implicit_single_layer_source_directional_derivative_potential_from_band(
        receivers, band, direction, density, _WAVENUMBER
    )

    band_plus = _with_shifted_points(band, _EPS * direction)
    band_minus = _with_shifted_points(band, -_EPS * direction)
    potentials_plus = implicit_single_layer_potential_from_band(receivers, band_plus, density, _WAVENUMBER).potentials
    potentials_minus = implicit_single_layer_potential_from_band(receivers, band_minus, density, _WAVENUMBER).potentials
    finite_difference = (potentials_plus - potentials_minus) / (2.0 * _EPS)

    np.testing.assert_allclose(closed_form, finite_difference, rtol=2e-3, atol=1e-6)


def test_mixed_hessian_reproduces_existing_hypersingular_kernel() -> None:
    """Regression check against the existing hypersingular normal-derivative
    kernel when source_direction = band.normals."""

    rng = np.random.default_rng(2)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)
    target_direction = rng.normal(size=(4, 2))

    generalized = implicit_greens_function_mixed_directional_hessian_potential_from_band(
        receivers, target_direction, band, band.normals.detach().cpu().numpy(), density, _WAVENUMBER
    )
    existing = implicit_double_layer_normal_derivative_potential_from_band(
        receivers, target_direction, band, density, _WAVENUMBER
    )
    np.testing.assert_allclose(generalized, existing, rtol=1e-12, atol=1e-14)


def test_mixed_hessian_matches_finite_difference() -> None:
    """d^2G/dn_x dn_y for two explicit directions, against a central
    difference of the existing grad_x G . target_direction kernel as the
    source points move."""

    rng = np.random.default_rng(3)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)
    target_direction = rng.normal(size=(4, 2))
    source_direction = rng.normal(size=(band.num_samples, 2))

    closed_form = implicit_greens_function_mixed_directional_hessian_potential_from_band(
        receivers, target_direction, band, source_direction, density, _WAVENUMBER
    )

    band_plus = _with_shifted_points(band, _EPS * source_direction)
    band_minus = _with_shifted_points(band, -_EPS * source_direction)
    grad_plus = implicit_single_layer_normal_derivative_potential_from_band(
        receivers, target_direction, band_plus, density, _WAVENUMBER
    )
    grad_minus = implicit_single_layer_normal_derivative_potential_from_band(
        receivers, target_direction, band_minus, density, _WAVENUMBER
    )
    finite_difference = (grad_plus - grad_minus) / (2.0 * _EPS)

    np.testing.assert_allclose(closed_form, finite_difference, rtol=2e-3, atol=1e-6)


def test_pure_target_hessian_matches_finite_difference() -> None:
    """v_a^T Hess_x(G) v_b, both row-indexed, against a central difference of
    the existing grad_x G . direction_a kernel as the *receiver* points move
    in direction direction_b."""

    rng = np.random.default_rng(4)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)
    direction_a = rng.normal(size=(4, 2))
    direction_b = rng.normal(size=(4, 2))

    closed_form = implicit_greens_function_pure_target_hessian_potential_from_band(
        receivers, direction_a, direction_b, band, density, _WAVENUMBER
    )

    grad_plus = implicit_single_layer_normal_derivative_potential_from_band(
        receivers + _EPS * direction_b, direction_a, band, density, _WAVENUMBER
    )
    grad_minus = implicit_single_layer_normal_derivative_potential_from_band(
        receivers - _EPS * direction_b, direction_a, band, density, _WAVENUMBER
    )
    finite_difference = (grad_plus - grad_minus) / (2.0 * _EPS)

    np.testing.assert_allclose(closed_form, finite_difference, rtol=2e-3, atol=1e-6)


def test_pure_source_hessian_matches_nested_finite_difference() -> None:
    """v_a^T Hess_y(G) v_b, both column-indexed, against a mixed central
    difference of the raw single-layer potential as the source points move
    in two independent directions -- the most direct test, grounded only in
    implicit_single_layer_potential_from_band, no dependency on any other
    new function in this file."""

    rng = np.random.default_rng(5)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)
    direction_a = rng.normal(size=(band.num_samples, 2))
    direction_b = rng.normal(size=(band.num_samples, 2))

    closed_form = implicit_greens_function_pure_source_hessian_potential_from_band(
        receivers, band, direction_a, direction_b, density, _WAVENUMBER
    )

    def potentials_at(delta: np.ndarray) -> np.ndarray:
        shifted = _with_shifted_points(band, delta)
        return implicit_single_layer_potential_from_band(receivers, shifted, density, _WAVENUMBER).potentials

    pp = potentials_at(_EPS * direction_a + _EPS * direction_b)
    pm = potentials_at(_EPS * direction_a - _EPS * direction_b)
    mp = potentials_at(-_EPS * direction_a + _EPS * direction_b)
    mm = potentials_at(-_EPS * direction_a - _EPS * direction_b)
    finite_difference = (pp - pm - mp + mm) / (4.0 * _EPS * _EPS)

    np.testing.assert_allclose(closed_form, finite_difference, rtol=1e-2, atol=1e-5)


def test_third_derivative_two_target_one_source_matches_finite_difference() -> None:
    """D_x^2 D_y^1 G contracted (a, b row-indexed; c column-indexed) against a
    central difference of the existing mixed-Hessian kernel as the
    *receiver* points move in direction b -- T's own-point-motion term."""

    rng = np.random.default_rng(6)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)
    direction_a = rng.normal(size=(4, 2))
    direction_b = rng.normal(size=(4, 2))
    direction_c = rng.normal(size=(band.num_samples, 2))

    closed_form = implicit_greens_function_third_derivative_two_target_one_source_potential_from_band(
        receivers, direction_a, direction_b, band, direction_c, density, _WAVENUMBER
    )

    plus = implicit_greens_function_mixed_directional_hessian_potential_from_band(
        receivers + _EPS * direction_b, direction_a, band, direction_c, density, _WAVENUMBER
    )
    minus = implicit_greens_function_mixed_directional_hessian_potential_from_band(
        receivers - _EPS * direction_b, direction_a, band, direction_c, density, _WAVENUMBER
    )
    finite_difference = (plus - minus) / (2.0 * _EPS)

    np.testing.assert_allclose(closed_form, finite_difference, rtol=2e-3, atol=1e-6)


def test_third_derivative_one_target_two_source_matches_finite_difference() -> None:
    """D_x^1 D_y^2 G contracted (a row-indexed; b, c column-indexed) against a
    central difference of the existing mixed-Hessian kernel as the *source*
    points move in direction c -- T's source-point-motion term."""

    rng = np.random.default_rng(8)
    band = _synthetic_boundary(rng)
    receivers = rng.normal(size=(4, 2)) * 0.2 + np.array([0.3, -0.1])
    density = _identity_density(band.num_samples)
    direction_a = rng.normal(size=(4, 2))
    direction_b = rng.normal(size=(band.num_samples, 2))
    direction_c = rng.normal(size=(band.num_samples, 2))

    closed_form = implicit_greens_function_third_derivative_one_target_two_source_potential_from_band(
        receivers, direction_a, band, direction_b, direction_c, density, _WAVENUMBER
    )

    band_plus = _with_shifted_points(band, _EPS * direction_c)
    band_minus = _with_shifted_points(band, -_EPS * direction_c)
    plus = implicit_greens_function_mixed_directional_hessian_potential_from_band(
        receivers, direction_a, band_plus, direction_b, density, _WAVENUMBER
    )
    minus = implicit_greens_function_mixed_directional_hessian_potential_from_band(
        receivers, direction_a, band_minus, direction_b, density, _WAVENUMBER
    )
    finite_difference = (plus - minus) / (2.0 * _EPS)

    np.testing.assert_allclose(closed_form, finite_difference, rtol=2e-3, atol=1e-6)
