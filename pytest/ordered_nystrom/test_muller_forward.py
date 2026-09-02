"""Physical boundary-trace and receiver-field tests against the Mie oracle."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import h1vp, hankel1, jv, jvp

import config.circle_config as cfg
import gpr_bem_mod
from gpr_bem_mod.ordered_nystrom import (
    OrderedSolveConfig,
    evaluate_exterior_representation,
    solve_ordered_tmz_total_field_batch,
)
from ordered_boundary import circle


CENTER = np.asarray(
    (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y)),
    dtype=np.float64,
)
RADIUS = float(cfg.TARGET_RADIUS)
CASE_SPECS = ((0.5e9, 64), (2.5e9, 64), (8.0e9, 128))


def _ring_scan(num_pairs: int = 4) -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0.0, 2.0 * np.pi, num_pairs, endpoint=False)
    source_angles = angles - 0.06
    receiver_angles = angles + 0.06
    sources = CENTER + 0.27 * np.column_stack(
        (np.cos(source_angles), np.sin(source_angles))
    )
    receivers = CENTER + 0.27 * np.column_stack(
        (np.cos(receiver_angles), np.sin(receiver_angles))
    )
    return sources, receivers


@pytest.fixture(scope="module")
def physical_cases():
    sources, receivers = _ring_scan()
    exterior = gpr_bem_mod.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_mod.Material(
        epsr=cfg.PLASTIC_EPSR,
        sigma=cfg.PLASTIC_SIGMA,
    )
    solve_config = OrderedSolveConfig(compute_condition_number=False)
    cases = {}
    for frequency_hz, num_nodes in CASE_SPECS:
        curve = circle(
            tuple(CENTER),
            RADIUS,
            component_id=f"mie-circle-{num_nodes}",
        ).discretize(num_nodes, require_even=True)
        forward = solve_ordered_tmz_total_field_batch(
            curve,
            sources,
            receivers,
            2.0 * np.pi * frequency_hz,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            config=solve_config,
        )
        exact = gpr_bem_mod.penetrable_cylinder_scattered_field(
            receivers,
            sources,
            k_exterior=forward.system.k_exterior,
            k_interior=forward.system.k_interior,
            radius=RADIUS,
            center=tuple(CENTER),
        )
        cases[frequency_hz] = (forward, exact)
    return cases


def _exact_line_source_boundary_traces(forward, source_index: int) -> tuple[np.ndarray, np.ndarray]:
    source = forward.source_points[source_index]
    source_delta = source - CENTER
    source_radius = float(np.linalg.norm(source_delta))
    source_angle = float(np.arctan2(source_delta[1], source_delta[0]))
    k_exterior = forward.system.k_exterior
    k_interior = forward.system.k_interior
    modes = gpr_bem_mod.cylinder_series_mode_numbers(
        k_exterior,
        k_interior,
        RADIUS,
    )
    ratio = gpr_bem_mod.penetrable_cylinder_scattering_coefficient_ratio(
        modes,
        k_exterior,
        k_interior,
        RADIUS,
    )
    exterior_argument = k_exterior * RADIUS
    incident_modes = hankel1(modes, k_exterior * source_radius)
    phase = np.exp(
        1j
        * np.outer(
            forward.system.geometry.parameters - source_angle,
            modes,
        )
    )
    strength = forward.source_strengths[source_index]
    dirichlet_modes = incident_modes * (
        jv(modes, exterior_argument)
        + ratio * hankel1(modes, exterior_argument)
    )
    neumann_modes = incident_modes * k_exterior * (
        jvp(modes, exterior_argument)
        + ratio * h1vp(modes, exterior_argument)
    )
    return (
        strength * 0.25j * (phase @ dirichlet_modes),
        strength * 0.25j * (phase @ neumann_modes),
    )


def test_circle_receiver_fields_match_mie_through_resolved_8_ghz(
    physical_cases,
) -> None:
    for frequency_hz, num_nodes in CASE_SPECS:
        forward, exact = physical_cases[frequency_hz]
        paired_scattered = np.diag(forward.scattered_receiver)
        absolute_error = float(np.linalg.norm(paired_scattered - exact))
        relative_error = absolute_error / float(np.linalg.norm(exact))

        assert forward.system.num_nodes == num_nodes
        assert forward.scattered_receiver.shape == (4, 4)
        assert absolute_error < 1.0e-8, (frequency_hz, absolute_error)
        assert relative_error < 1.0e-6, (frequency_hz, relative_error)
        assert forward.linear_system_relative_residual < 1.0e-10
        assert np.max(forward.per_source_relative_residual) < 1.0e-10
        assert forward.incident_representation_leak < 1.0e-10
        assert np.isfinite(forward.total_seconds)
        assert forward.total_seconds >= 0.0
        assert forward.system.diagnostics["solve_form"] == "direct_unsquared"
        assert forward.diagnostics["close_evaluation"] is False


@pytest.mark.parametrize("frequency_hz", [2.5e9, 8.0e9])
def test_circle_boundary_traces_match_fourier_bessel_solution(
    physical_cases,
    frequency_hz: float,
) -> None:
    forward, _ = physical_cases[frequency_hz]
    exact_dirichlet, exact_neumann = _exact_line_source_boundary_traces(
        forward,
        source_index=0,
    )
    dirichlet_error = np.linalg.norm(
        forward.dirichlet_total[0] - exact_dirichlet
    ) / np.linalg.norm(exact_dirichlet)
    neumann_error = np.linalg.norm(
        forward.neumann_total[0] - exact_neumann
    ) / np.linalg.norm(exact_neumann)
    assert dirichlet_error < 1.0e-6, (frequency_hz, dirichlet_error)
    assert neumann_error < 1.0e-6, (frequency_hz, neumann_error)


def test_zero_contrast_reproduces_incident_traces_and_zero_scattering() -> None:
    sources, receivers = _ring_scan(num_pairs=2)
    exterior = gpr_bem_mod.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    curve = circle(
        tuple(CENTER),
        RADIUS,
        component_id="zero-contrast-forward",
    ).discretize(32, require_even=True)
    forward = solve_ordered_tmz_total_field_batch(
        curve,
        sources,
        receivers,
        2.0 * np.pi * 1.5e9,
        exterior=exterior,
        interior=exterior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        config=OrderedSolveConfig(compute_condition_number=False),
    )

    np.testing.assert_allclose(
        forward.dirichlet_total,
        forward.dirichlet_incident,
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    np.testing.assert_allclose(
        forward.neumann_total,
        forward.neumann_incident,
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    scattered_scale = float(np.linalg.norm(forward.scattered_receiver))
    incident_scale = float(np.linalg.norm(forward.incident_receiver))
    assert scattered_scale / incident_scale < 1.0e-11
    assert forward.linear_system_relative_residual < 1.0e-12


def test_receiver_guard_measures_distance_to_sampled_segments_not_only_nodes() -> None:
    curve = circle((0.0, 0.0), 1.0).discretize(8, require_even=True)
    edge_midpoint = 0.5 * (curve.points[0] + curve.points[1])
    zeros = np.zeros(curve.num_nodes, dtype=np.complex128)

    with pytest.raises(ValueError, match="exterior|too close"):
        evaluate_exterior_representation(
            curve,
            edge_midpoint,
            zeros,
            zeros,
            2.0,
            minimum_clearance=0.0,
        )
