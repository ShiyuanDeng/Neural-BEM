"""Physical boundary-trace and receiver-field tests against the Mie oracle."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import h1vp, hankel1, jv, jvp

import config.circle_config as cfg
import gpr_bem_ref
from gpr_bem_kress import (
    ExteriorReceiverOperator,
    KressSolveConfig,
    Material,
    evaluate_exterior_representation,
    solve_kress_tmz_total_field_batch,
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
    exterior = Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = Material(
        epsr=cfg.PLASTIC_EPSR,
        sigma=cfg.PLASTIC_SIGMA,
    )
    solve_config = KressSolveConfig(compute_condition_number=False)
    cases = {}
    for frequency_hz, num_nodes in CASE_SPECS:
        curve = circle(
            tuple(CENTER),
            RADIUS,
            component_id=f"mie-circle-{num_nodes}",
        ).discretize(num_nodes, require_even=True)
        forward = solve_kress_tmz_total_field_batch(
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
        assert forward.solve_config is solve_config
        assert forward.system.assembly_config is solve_config.assembly
        assert forward.system.difference_blocks.config is solve_config.assembly
        assert forward.exterior_material is exterior
        assert forward.interior_material is interior
        assert forward.eps0 == cfg.EPS0
        assert forward.mu0 == cfg.MU0
        assert forward.receiver_operator.geometry is forward.system.geometry
        exact = gpr_bem_ref.penetrable_cylinder_scattered_field(
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
    modes = gpr_bem_ref.cylinder_series_mode_numbers(
        k_exterior,
        k_interior,
        RADIUS,
    )
    ratio = gpr_bem_ref.penetrable_cylinder_scattering_coefficient_ratio(
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


def test_receiver_operator_is_the_forward_map_and_has_exact_complex_duality(
    physical_cases,
) -> None:
    forward, _ = physical_cases[2.5e9]
    receiver = forward.receiver_operator
    expected_rows = np.concatenate(
        (receiver.double_layer_rows, -receiver.single_layer_rows),
        axis=1,
    )
    np.testing.assert_array_equal(receiver.state_rows, expected_rows)

    mapped = receiver.apply_state(forward.solution)
    np.testing.assert_allclose(
        mapped,
        forward.scattered_receiver,
        rtol=2.0e-14,
        atol=2.0e-14,
    )

    data_dual = np.vstack(
        tuple(
            np.linspace(0.3 + index, 1.1 + index, receiver.num_receivers)
            + 1j
            * np.linspace(-0.7 + 0.2 * index, 0.2 + 0.2 * index, receiver.num_receivers)
            for index in range(forward.solution.shape[1])
        )
    )
    state_dual = receiver.apply_adjoint(data_dual)
    forward_inner_product = np.vdot(mapped, data_dual)
    adjoint_inner_product = np.vdot(forward.solution, state_dual)
    np.testing.assert_allclose(
        forward_inner_product,
        adjoint_inner_product,
        rtol=2.0e-14,
        atol=2.0e-14,
    )

    # This is the complete algebraic seam needed by a later adjoint: the
    # tangent solve applies A^-1 before C, while the reverse path applies C^H
    # before A^-H.  It intentionally does not claim a geometry derivative.
    generator = np.random.default_rng(20260902)
    rhs_perturbation = (
        generator.normal(size=forward.right_hand_side.shape)
        + 1j * generator.normal(size=forward.right_hand_side.shape)
    )
    state_perturbation = np.linalg.solve(
        forward.system.system_matrix,
        rhs_perturbation,
    )
    receiver_perturbation = receiver.apply_state(state_perturbation)
    adjoint_state = np.linalg.solve(
        forward.system.system_matrix.conjugate().T,
        state_dual,
    )
    np.testing.assert_allclose(
        np.vdot(receiver_perturbation, data_dual),
        np.vdot(rhs_perturbation, adjoint_state),
        rtol=5.0e-13,
        atol=5.0e-13,
    )
    assert mapped.shape == forward.scattered_receiver.shape
    assert state_dual.shape == forward.solution.shape
    assert not mapped.flags.writeable
    assert not state_dual.flags.writeable
    for values in (
        receiver.receiver_points,
        receiver.single_layer_rows,
        receiver.double_layer_rows,
        receiver.state_rows,
    ):
        assert not values.flags.writeable


def test_receiver_operator_derives_c_and_owns_immutable_row_copies() -> None:
    curve = circle((0.0, 0.0), 0.2).discretize(16, require_even=True)
    receivers = np.asarray(((0.5, 0.0), (0.0, 0.5)))
    single = np.arange(32, dtype=np.float64).reshape(2, 16).astype(np.complex128)
    double = (2.0 - 0.3j) * single
    expected = np.concatenate((double, -single), axis=1)

    operator = ExteriorReceiverOperator(
        geometry=curve,
        receiver_points=receivers,
        k_exterior=3.0,
        single_layer_rows=single,
        double_layer_rows=double,
        build_seconds=0.0,
    )
    single[:] = 0.0
    double[:] = 0.0
    np.testing.assert_array_equal(operator.state_rows, expected)
    assert not operator.single_layer_rows.flags.writeable
    assert not operator.double_layer_rows.flags.writeable
    assert not operator.state_rows.flags.writeable

    with pytest.raises(ValueError, match="single_layer_rows must have shape"):
        ExteriorReceiverOperator(
            geometry=curve,
            receiver_points=receivers,
            k_exterior=3.0,
            single_layer_rows=np.zeros((1, 16)),
            double_layer_rows=np.zeros((2, 16)),
            build_seconds=0.0,
        )


def test_zero_contrast_reproduces_incident_traces_and_zero_scattering() -> None:
    sources, receivers = _ring_scan(num_pairs=2)
    exterior = Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    curve = circle(
        tuple(CENTER),
        RADIUS,
        component_id="zero-contrast-forward",
    ).discretize(32, require_even=True)
    forward = solve_kress_tmz_total_field_batch(
        curve,
        sources,
        receivers,
        2.0 * np.pi * 1.5e9,
        exterior=exterior,
        interior=exterior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        config=KressSolveConfig(compute_condition_number=False),
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
