from __future__ import annotations

import numpy as np
import pytest
from scipy.special import h1vp, hankel1, jv, jvp

torch = pytest.importorskip("torch")

import config.simulation_config as cfg
from gpr_bem import (
    Material,
    build_implicit_boundary_samples,
    circle_signed_distance,
    cylinder_series_mode_numbers,
    penetrable_cylinder_scattered_field,
    penetrable_cylinder_scattering_coefficient_ratio,
    solve_ibim_tmz_total_field_batch,
)


def test_penetrable_cylinder_reference_satisfies_basic_identities() -> None:
    exterior = Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    angular_frequency = 2.0 * np.pi * 0.5e9
    radius = float(cfg.TARGET_RADIUS)
    k_exterior = exterior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0)
    k_interior = interior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0)
    n = cylinder_series_mode_numbers(k_exterior, k_interior, radius)

    zero_contrast = penetrable_cylinder_scattering_coefficient_ratio(n, k_exterior, k_exterior, radius)
    assert np.max(np.abs(zero_contrast)) < 1.0e-14

    source_radius = 0.30
    coefficients = hankel1(n, k_exterior * source_radius) * penetrable_cylinder_scattering_coefficient_ratio(
        n,
        k_exterior,
        k_interior,
        radius,
    )
    interior_coefficients = (
        hankel1(n, k_exterior * source_radius) * jv(n, k_exterior * radius)
        + coefficients * hankel1(n, k_exterior * radius)
    ) / jv(n, k_interior * radius)

    for theta in (0.0, 0.7, 1.4):
        phase = np.exp(1j * n * theta)
        exterior_trace = np.sum(
            (
                hankel1(n, k_exterior * source_radius) * jv(n, k_exterior * radius)
                + coefficients * hankel1(n, k_exterior * radius)
            )
            * phase
        )
        interior_trace = np.sum(interior_coefficients * jv(n, k_interior * radius) * phase)
        exterior_normal = np.sum(
            k_exterior
            * (
                hankel1(n, k_exterior * source_radius) * jvp(n, k_exterior * radius)
                + coefficients * h1vp(n, k_exterior * radius)
            )
            * phase
        )
        interior_normal = np.sum(
            k_interior * interior_coefficients * jvp(n, k_interior * radius) * phase
        )

        assert abs(exterior_trace - interior_trace) < 1.0e-13
        assert abs(exterior_normal - interior_normal) < 1.0e-12


def test_ibim_tmz_forward_matches_penetrable_cylinder_series_at_working_frequencies() -> None:
    center = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))
    radius = float(cfg.TARGET_RADIUS)
    with pytest.warns(RuntimeWarning, match="reduced merge_distance"):
        boundary = build_implicit_boundary_samples(
            lambda points: circle_signed_distance(points, center=center, radius=radius),
            ((0.0, 0.0), (float(cfg.DOMAIN_WIDTH), float(cfg.DOMAIN_HEIGHT))),
            grid_shape=(257, 257),
            band_half_width=0.06,
            delta_half_width=0.03,
            merge_distance=0.01,
            dtype=torch.float64,
        )

    angles = np.linspace(0.0, 2.0 * np.pi, 12, endpoint=False, dtype=float)
    source_radius = 0.27
    angular_separation = 0.12
    source_points = np.column_stack(
        (
            center[0] + source_radius * np.cos(angles - 0.5 * angular_separation),
            center[1] + source_radius * np.sin(angles - 0.5 * angular_separation),
        )
    )
    receiver_points = np.column_stack(
        (
            center[0] + source_radius * np.cos(angles + 0.5 * angular_separation),
            center[1] + source_radius * np.sin(angles + 0.5 * angular_separation),
        )
    )
    exterior = Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    observed_errors: dict[float, float] = {}
    thresholds = {0.5e9: 0.18, 1.5e9: 0.35, 2.5e9: 0.30}
    for frequency_hz, threshold in thresholds.items():
        angular_frequency = 2.0 * np.pi * frequency_hz
        forward = solve_ibim_tmz_total_field_batch(
            boundary,
            source_points,
            receiver_points,
            angular_frequency,
            1.0,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            offset_distance=None,
            use_strict_quadrature=True,
            backend="numpy",
        )
        exact_scattered = penetrable_cylinder_scattered_field(
            receiver_points,
            source_points,
            k_exterior=forward.system.k_exterior,
            k_interior=forward.system.k_interior,
            radius=radius,
            center=center,
        )
        relative_error = float(
            np.linalg.norm(forward.scattered_receiver - exact_scattered) / np.linalg.norm(exact_scattered)
        )
        observed_errors[frequency_hz / 1.0e9] = relative_error
        assert relative_error < threshold, observed_errors
        formulation = getattr(forward.system, "formulation", "difference")
        if formulation == "muller":
            assert getattr(forward.system, "normal_derivative_scheme") == "analytic_extrapolated"
            assert forward.system.offset_distance == pytest.approx(0.275 * boundary.merge_distance)
        else:
            assert forward.system.offset_distance == pytest.approx(2.0 * boundary.merge_distance)
