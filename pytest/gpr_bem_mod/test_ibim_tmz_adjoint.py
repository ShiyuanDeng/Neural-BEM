from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config.simulation_config as cfg
import gpr_bem_mod.ibim_tmz_adjoint as ibim_adj
from gpr_bem_mod import (
    ImplicitBoundarySamples2D,
    Material,
    bscan_from_frequency_response,
    build_ibim_receiver_operator_rows,
    build_implicit_boundary_band,
    compress_implicit_boundary_band,
    ibim_adjoint_context_from_receiver_dual,
    ibim_bscan_leading_order_normal_shape_gradient,
    ibim_bscan_leading_order_point_directional_gradient,
    ibim_leading_order_normal_shape_gradient,
    ibim_leading_order_point_directional_gradient,
    ibim_multifrequency_leading_order_normal_shape_gradient,
    ibim_multifrequency_leading_order_point_directional_gradient,
    ibim_shape_gradient_surrogate_loss,
    prepare_ibim_adjoint_context,
    prepare_ibim_bscan_adjoint_context,
    prepare_ibim_multifrequency_adjoint_context,
    solve_ibim_tmz_total_field_batch,
    solve_ibim_tmz_frequency_response,
)
from gpr_bem_mod.neural_sdf import circle_signed_distance


def _materials() -> tuple[Material, Material]:
    exterior = Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    return exterior, interior


def _compressed_circle_boundary():
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(
            points,
            center=(cfg.TARGET_CENTER_X, cfg.TARGET_CENTER_Y),
            radius=cfg.TARGET_RADIUS,
        ),
        ((0.0, 0.0), (cfg.DOMAIN_WIDTH, cfg.DOMAIN_HEIGHT)),
        grid_shape=(257, 257),
        dtype=torch.float64,
    )
    return compress_implicit_boundary_band(band)


def _displaced_boundary_samples(
    boundary: ImplicitBoundarySamples2D,
    point_directional: np.ndarray,
    step: float,
) -> ImplicitBoundarySamples2D:
    direction = torch.as_tensor(point_directional, dtype=boundary.points.dtype, device=boundary.points.device)
    displaced_points = boundary.points + float(step) * direction
    return ImplicitBoundarySamples2D(
        points=displaced_points,
        normals=boundary.normals,
        quadrature_weights=boundary.quadrature_weights,
        strict_quadrature_weights=boundary.strict_quadrature_weights,
        merge_distance=boundary.merge_distance,
        source_num_samples=boundary.source_num_samples,
        bounds=boundary.bounds,
        level=boundary.level,
    )


def _forward_case():
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequency = 2.0 * np.pi * 1.0e9
    source_points = np.array(
        [
            [0.18, cfg.ANTENNA_Y],
            [0.26, cfg.ANTENNA_Y],
        ],
        dtype=float,
    )
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    forward = solve_ibim_tmz_total_field_batch(
        boundary,
        source_points,
        receiver_points,
        angular_frequency,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    return boundary, exterior, interior, angular_frequency, source_points, receiver_points, source_strength, forward


def test_ibim_receiver_operator_rows_reproduce_forward_receiver_terms() -> None:
    boundary, _exterior, _interior, _omega, _src, receiver_points, _strength, forward = _forward_case()
    single_rows, double_rows = build_ibim_receiver_operator_rows(
        boundary,
        receiver_points,
        forward.system.k_exterior,
    )

    reconstructed_single = np.sum(single_rows * forward.neumann_total, axis=1)
    reconstructed_double = np.sum(double_rows * forward.dirichlet_total, axis=1)

    np.testing.assert_allclose(reconstructed_single, forward.single_receiver, rtol=2.0e-12, atol=2.0e-12)
    np.testing.assert_allclose(reconstructed_double, forward.double_receiver, rtol=2.0e-12, atol=2.0e-12)


def test_ibim_adjoint_context_solves_conjugate_transpose_system() -> None:
    boundary, exterior, interior, angular_frequency, source_points, receiver_points, source_strength, forward = _forward_case()
    observed = forward.total_receiver + np.array([0.03 - 0.01j, -0.02 + 0.015j], dtype=np.complex128)
    context = prepare_ibim_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequency,
        source_strength,
        observed,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )

    residual = context.adjoint_vector @ context.system_matrix.conjugate() - context.adjoint_rhs
    assert np.max(np.abs(residual)) < 1.0e-10


def test_ibim_adjoint_matches_explicit_rhs_directional_sensitivity() -> None:
    boundary, _exterior, _interior, _angular_frequency, _source_points, receiver_points, _strength, forward = _forward_case()
    single_rows, double_rows = build_ibim_receiver_operator_rows(
        boundary,
        receiver_points,
        forward.system.k_exterior,
    )
    receiver_dual = np.array([0.4 - 0.15j, -0.2 + 0.3j], dtype=np.complex128)
    context = ibim_adjoint_context_from_receiver_dual(
        forward,
        single_rows,
        double_rows,
        receiver_dual=receiver_dual,
        loss=0.0,
        residual=np.zeros_like(receiver_dual),
    )

    rng = np.random.default_rng(7)
    rhs_directional = rng.standard_normal(context.state_vector.shape) + 1j * rng.standard_normal(context.state_vector.shape)
    delta_state = np.linalg.solve(context.system_matrix, rhs_directional.T).T
    receiver_directional = (
        np.sum(context.double_layer_rows * delta_state[:, : boundary.num_samples], axis=1)
        - np.sum(context.single_layer_rows * delta_state[:, boundary.num_samples :], axis=1)
    )

    adjoint_value = np.real(np.vdot(context.adjoint_vector, rhs_directional))
    direct_value = np.real(np.vdot(context.receiver_dual, receiver_directional))
    assert abs(adjoint_value - direct_value) < 1.0e-10


def test_prepare_ibim_multifrequency_adjoint_context_matches_weighted_loss_sum() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array([[0.18, cfg.ANTENNA_Y], [0.26, cfg.ANTENNA_Y]], dtype=float)
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    reference = solve_ibim_tmz_frequency_response(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    observed = reference.frequency_response.T + np.array(
        [
            [0.02 - 0.01j, -0.01 + 0.005j, 0.015 + 0.01j],
            [-0.012 + 0.008j, 0.01 - 0.015j, -0.006 - 0.004j],
        ],
        dtype=np.complex128,
    ).T
    weights = np.array([1.0, 0.5, 2.0], dtype=float)

    result = prepare_ibim_multifrequency_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        observed,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        frequency_weights=weights,
        backend="numpy",
    )

    manual_losses = 0.5 * np.mean(np.abs(reference.frequency_response.T - observed) ** 2, axis=1)
    np.testing.assert_allclose(result.loss_by_frequency, manual_losses, rtol=1.0e-12, atol=1.0e-12)
    np.testing.assert_allclose(result.loss, float(weights @ manual_losses), rtol=1.0e-12, atol=1.0e-12)
    assert len(result.per_frequency_contexts) == angular_frequencies.size


def test_ibim_multifrequency_leading_order_point_directional_gradient_matches_weighted_sum() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array([[0.18, cfg.ANTENNA_Y], [0.26, cfg.ANTENNA_Y]], dtype=float)
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    reference = solve_ibim_tmz_frequency_response(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    observed = reference.frequency_response.T + np.array(
        [
            [0.02 - 0.01j, -0.01 + 0.005j, 0.015 + 0.01j],
            [-0.012 + 0.008j, 0.01 - 0.015j, -0.006 - 0.004j],
        ],
        dtype=np.complex128,
    ).T
    weights = np.array([1.0, 0.5, 2.0], dtype=float)
    result = prepare_ibim_multifrequency_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        observed,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        frequency_weights=weights,
        backend="numpy",
    )
    point_directional = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    directional = ibim_multifrequency_leading_order_point_directional_gradient(
        result,
        boundary,
        point_directional,
    )

    manual = 0.0
    for weight, context in zip(weights, result.per_frequency_contexts):
        manual += weight * ibim_leading_order_point_directional_gradient(
            context,
            boundary,
            point_directional,
        ).directional_gradient
    assert abs(directional.directional_gradient - manual) < 1.0e-12


def test_ibim_multifrequency_point_directional_gradient_matches_frozen_geometry_finite_difference() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array([[0.18, cfg.ANTENNA_Y], [0.26, cfg.ANTENNA_Y]], dtype=float)
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    reference = solve_ibim_tmz_frequency_response(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    observed = reference.frequency_response.T + np.array(
        [
            [0.02 - 0.01j, -0.01 + 0.005j, 0.015 + 0.01j],
            [-0.012 + 0.008j, 0.01 - 0.015j, -0.006 - 0.004j],
        ],
        dtype=np.complex128,
    ).T
    weights = np.array([1.0, 0.5, 2.0], dtype=float)
    result = prepare_ibim_multifrequency_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        observed,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        frequency_weights=weights,
        backend="numpy",
    )
    point_directional = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    directional = ibim_multifrequency_leading_order_point_directional_gradient(
        result,
        boundary,
        point_directional,
    )

    def objective(displaced_boundary: ImplicitBoundarySamples2D) -> float:
        displaced = solve_ibim_tmz_frequency_response(
            displaced_boundary,
            source_points,
            receiver_points,
            angular_frequencies,
            source_strength,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            backend="numpy",
        )
        losses = 0.5 * np.mean(np.abs(displaced.frequency_response.T - observed) ** 2, axis=1)
        return float(weights @ losses)

    step = 2.0e-5
    fd = (
        objective(_displaced_boundary_samples(boundary, point_directional, +step))
        - objective(_displaced_boundary_samples(boundary, point_directional, -step))
    ) / (2.0 * step)
    relative_error = abs(directional.directional_gradient - fd) / max(abs(fd), 1.0)
    assert relative_error < 2.0e-4


def test_prepare_ibim_bscan_adjoint_context_matches_frequency_directional_derivative() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array([[0.18, cfg.ANTENNA_Y], [0.26, cfg.ANTENNA_Y]], dtype=float)
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    reference = solve_ibim_tmz_frequency_response(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    time_vector = np.linspace(0.0, 12.0e-9, 96)
    frequency_window = np.array([1.0, 0.8, 0.6], dtype=float)
    predicted_bscan = bscan_from_frequency_response(
        reference.frequency_response,
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    observed_bscan = predicted_bscan + np.array([[0.2, -0.1, 0.05], [-0.15, 0.1, -0.08]], dtype=float) @ np.array(
        [
            np.exp(-((time_vector - 3.0e-9) / 0.7e-9) ** 2),
            np.exp(-((time_vector - 6.0e-9) / 0.9e-9) ** 2),
            np.exp(-((time_vector - 9.0e-9) / 1.1e-9) ** 2),
        ]
    )
    sample_weights = np.linspace(1.0, 2.0, time_vector.size)

    result = prepare_ibim_bscan_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        observed_bscan,
        time_vector=time_vector,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        frequency_window=frequency_window,
        time_gate_start=2.0e-9,
        sample_weights=sample_weights,
        backend="numpy",
    )

    rng = np.random.default_rng(11)
    direction = rng.standard_normal(result.frequency_response.shape) + 1j * rng.standard_normal(result.frequency_response.shape)
    bscan_direction = bscan_from_frequency_response(
        direction,
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    active_weights = np.where(result.time_gate_mask[None, :], result.time_sample_weights, 0.0)
    directional_transform = float(np.sum(result.residual * bscan_direction) / float(np.sum(active_weights)))
    directional_adjoint = float(np.real(np.vdot(result.frequency_response_dual, direction)))

    relative_error = abs(directional_adjoint - directional_transform) / max(abs(directional_transform), 1.0)
    assert relative_error < 1.0e-12


def test_ibim_bscan_leading_order_point_directional_gradient_matches_manual_frequency_sum() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array([[0.18, cfg.ANTENNA_Y], [0.26, cfg.ANTENNA_Y]], dtype=float)
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    reference = solve_ibim_tmz_frequency_response(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    time_vector = np.linspace(0.0, 12.0e-9, 96)
    frequency_window = np.array([1.0, 0.8, 0.6], dtype=float)
    predicted_bscan = bscan_from_frequency_response(
        reference.frequency_response,
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    observed_bscan = predicted_bscan + np.array([[0.2, -0.1, 0.05], [-0.15, 0.1, -0.08]], dtype=float) @ np.array(
        [
            np.exp(-((time_vector - 3.0e-9) / 0.7e-9) ** 2),
            np.exp(-((time_vector - 6.0e-9) / 0.9e-9) ** 2),
            np.exp(-((time_vector - 9.0e-9) / 1.1e-9) ** 2),
        ]
    )
    sample_weights = np.linspace(1.0, 2.0, time_vector.size)
    result = prepare_ibim_bscan_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        observed_bscan,
        time_vector=time_vector,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        frequency_window=frequency_window,
        time_gate_start=2.0e-9,
        sample_weights=sample_weights,
        backend="numpy",
    )
    point_directional = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    directional = ibim_bscan_leading_order_point_directional_gradient(
        result,
        boundary,
        point_directional,
    )

    manual = sum(
        ibim_leading_order_point_directional_gradient(
            context,
            boundary,
            point_directional,
        ).directional_gradient
        for context in result.per_frequency_contexts
    )
    assert abs(directional.directional_gradient - manual) < 1.0e-12


def test_ibim_bscan_point_directional_gradient_matches_frozen_geometry_finite_difference() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array([[0.18, cfg.ANTENNA_Y], [0.26, cfg.ANTENNA_Y]], dtype=float)
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    reference = solve_ibim_tmz_frequency_response(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    time_vector = np.linspace(0.0, 12.0e-9, 96)
    frequency_window = np.array([1.0, 0.8, 0.6], dtype=float)
    predicted_bscan = bscan_from_frequency_response(
        reference.frequency_response,
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    observed_bscan = predicted_bscan + np.array([[0.2, -0.1, 0.05], [-0.15, 0.1, -0.08]], dtype=float) @ np.array(
        [
            np.exp(-((time_vector - 3.0e-9) / 0.7e-9) ** 2),
            np.exp(-((time_vector - 6.0e-9) / 0.9e-9) ** 2),
            np.exp(-((time_vector - 9.0e-9) / 1.1e-9) ** 2),
        ]
    )
    sample_weights = np.linspace(1.0, 2.0, time_vector.size)
    result = prepare_ibim_bscan_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        observed_bscan,
        time_vector=time_vector,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        frequency_window=frequency_window,
        time_gate_start=2.0e-9,
        sample_weights=sample_weights,
        backend="numpy",
    )
    point_directional = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    directional = ibim_bscan_leading_order_point_directional_gradient(
        result,
        boundary,
        point_directional,
    )

    def objective(displaced_boundary: ImplicitBoundarySamples2D) -> float:
        displaced = prepare_ibim_bscan_adjoint_context(
            displaced_boundary,
            source_points,
            receiver_points,
            angular_frequencies,
            source_strength,
            observed_bscan,
            time_vector=time_vector,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            frequency_window=frequency_window,
            time_gate_start=2.0e-9,
            sample_weights=sample_weights,
            backend="numpy",
        )
        return float(displaced.loss)

    step = 5.0e-9
    fd = (
        objective(_displaced_boundary_samples(boundary, point_directional, +step))
        - objective(_displaced_boundary_samples(boundary, point_directional, -step))
    ) / (2.0 * step)
    relative_error = abs(directional.directional_gradient - fd) / max(abs(fd), 1.0)
    assert relative_error < 2.0e-4


def test_ibim_shape_gradient_surrogate_loss_matches_circle_radius_gradient() -> None:
    radius = torch.tensor(0.05, dtype=torch.float64, requires_grad=True)
    center = torch.tensor([cfg.TARGET_CENTER_X, cfg.TARGET_CENTER_Y], dtype=torch.float64)

    def sdf_fn(points: torch.Tensor) -> torch.Tensor:
        return torch.linalg.norm(points - center[None, :], dim=1, keepdim=True) - radius

    band = build_implicit_boundary_band(
        sdf_fn,
        ((0.0, 0.0), (cfg.DOMAIN_WIDTH, cfg.DOMAIN_HEIGHT)),
        grid_shape=(257, 257),
        dtype=torch.float64,
        create_graph=False,
    )
    shape_gradient = torch.ones((band.num_samples,), dtype=torch.float64)
    surrogate = ibim_shape_gradient_surrogate_loss(
        sdf_fn,
        band,
        shape_gradient,
        detach_boundary_points=True,
        detach_quadrature=True,
    )
    surrogate.backward()

    expected = 2.0 * np.pi * float(radius.detach())
    assert radius.grad is not None
    assert abs(float(radius.grad) - expected) / expected < 5.0e-2


def test_ibim_leading_order_point_directional_gradient_matches_frozen_geometry_finite_difference() -> None:
    boundary, exterior, interior, angular_frequency, source_points, receiver_points, source_strength, forward = _forward_case()
    single_rows, double_rows = build_ibim_receiver_operator_rows(
        boundary,
        receiver_points,
        forward.system.k_exterior,
    )
    receiver_dual = np.array([0.35 - 0.2j, -0.15 + 0.25j], dtype=np.complex128)
    context = ibim_adjoint_context_from_receiver_dual(
        forward,
        single_rows,
        double_rows,
        receiver_dual=receiver_dual,
        loss=0.0,
        residual=np.zeros_like(receiver_dual),
    )
    point_directional = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    directional = ibim_leading_order_point_directional_gradient(
        context,
        boundary,
        point_directional,
    )

    def linear_objective(displaced_boundary: ImplicitBoundarySamples2D) -> float:
        displaced_forward = solve_ibim_tmz_total_field_batch(
            displaced_boundary,
            source_points,
            receiver_points,
            angular_frequency,
            source_strength,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            backend="numpy",
        )
        return float(np.real(np.vdot(receiver_dual, displaced_forward.total_receiver)))

    step = 2.0e-5
    loss_plus = linear_objective(_displaced_boundary_samples(boundary, point_directional, +step))
    loss_minus = linear_objective(_displaced_boundary_samples(boundary, point_directional, -step))
    directional_fd = (loss_plus - loss_minus) / (2.0 * step)

    relative_error = abs(directional.directional_gradient - directional_fd) / max(abs(directional_fd), 1.0)
    assert relative_error < 2.0e-4


def test_ibim_leading_order_normal_shape_gradient_matches_basis_directional_gradients() -> None:
    boundary, _exterior, _interior, _angular_frequency, _source_points, receiver_points, _strength, forward = _forward_case()
    single_rows, double_rows = build_ibim_receiver_operator_rows(
        boundary,
        receiver_points,
        forward.system.k_exterior,
    )
    receiver_dual = np.array([0.35 - 0.2j, -0.15 + 0.25j], dtype=np.complex128)
    context = ibim_adjoint_context_from_receiver_dual(
        forward,
        single_rows,
        double_rows,
        receiver_dual=receiver_dual,
        loss=0.0,
        residual=np.zeros_like(receiver_dual),
    )
    normals = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    weights = np.asarray(boundary.quadrature_weights.detach().cpu(), dtype=float).reshape(-1)
    shape_gradient = ibim_leading_order_normal_shape_gradient(context, boundary)
    assert shape_gradient.shape == (boundary.num_samples,)

    sample_indices = [0, boundary.num_samples // 2, boundary.num_samples - 1]
    for sample_index in sample_indices:
        point_directional = np.zeros((boundary.num_samples, 2), dtype=float)
        point_directional[sample_index] = normals[sample_index]
        directional = ibim_leading_order_point_directional_gradient(
            context,
            boundary,
            point_directional,
        )
        node_directional = shape_gradient[sample_index] * weights[sample_index]
        assert abs(node_directional - directional.directional_gradient) < 1.0e-12


def test_ibim_normal_shape_gradient_surrogate_matches_fixed_sample_radius_fd() -> None:
    boundary, _exterior, _interior, angular_frequency, source_points, receiver_points, source_strength, forward = _forward_case()
    single_rows, double_rows = build_ibim_receiver_operator_rows(
        boundary,
        receiver_points,
        forward.system.k_exterior,
    )
    receiver_dual = np.array([0.35 - 0.2j, -0.15 + 0.25j], dtype=np.complex128)
    context = ibim_adjoint_context_from_receiver_dual(
        forward,
        single_rows,
        double_rows,
        receiver_dual=receiver_dual,
        loss=0.0,
        residual=np.zeros_like(receiver_dual),
    )
    shape_gradient = ibim_leading_order_normal_shape_gradient(context, boundary)

    radius = torch.tensor(float(cfg.TARGET_RADIUS), dtype=torch.float64, requires_grad=True)
    center = torch.tensor([cfg.TARGET_CENTER_X, cfg.TARGET_CENTER_Y], dtype=torch.float64)

    def sdf_fn(points: torch.Tensor) -> torch.Tensor:
        return torch.linalg.norm(points - center[None, :], dim=1, keepdim=True) - radius

    surrogate = ibim_shape_gradient_surrogate_loss(
        sdf_fn,
        boundary,
        torch.tensor(shape_gradient, dtype=torch.float64),
        quadrature_weights=boundary.quadrature_weights,
    )
    surrogate.backward()

    point_directional = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    directional = ibim_leading_order_point_directional_gradient(
        context,
        boundary,
        point_directional,
    )
    assert radius.grad is not None
    assert abs(float(radius.grad) - directional.directional_gradient) < 1.0e-9


def test_ibim_leading_order_normal_shape_gradient_cached_matches_uncached_loop() -> None:
    boundary, _exterior, _interior, _angular_frequency, _source_points, _receiver_points, _strength, forward = _forward_case()
    single_rows, double_rows = build_ibim_receiver_operator_rows(
        boundary,
        _receiver_points,
        forward.system.k_exterior,
    )
    receiver_dual = np.array([0.35 - 0.2j, -0.15 + 0.25j], dtype=np.complex128)
    context = ibim_adjoint_context_from_receiver_dual(
        forward,
        single_rows,
        double_rows,
        receiver_dual=receiver_dual,
        loss=0.0,
        residual=np.zeros_like(receiver_dual),
    )

    strict_quadrature = context.forward.system.use_strict_quadrature
    boundary_points, normals, weights = ibim_adj._boundary_point_normal_weight_arrays(
        boundary,
        use_strict_quadrature=strict_quadrature,
    )
    node_directional = np.array(
        [
            ibim_adj._ibim_leading_order_single_sample_normal_gradient(
                context=context,
                boundary_points=boundary_points,
                normals=normals,
                weights=weights,
                sample_index=sample_index,
            )
            for sample_index in range(boundary_points.shape[0])
        ],
        dtype=float,
    )
    uncached = ibim_adj._node_directional_to_shape_gradient_density(node_directional, weights)
    cached = ibim_leading_order_normal_shape_gradient(context, boundary)
    np.testing.assert_allclose(cached, uncached, rtol=1.0e-12, atol=1.0e-12)


def test_ibim_bscan_leading_order_normal_shape_gradient_matches_frequency_sum() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array([[0.18, cfg.ANTENNA_Y], [0.26, cfg.ANTENNA_Y]], dtype=float)
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j
    reference = solve_ibim_tmz_frequency_response(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )
    time_vector = np.linspace(0.0, 12.0e-9, 96)
    frequency_window = np.array([1.0, 0.8, 0.6], dtype=float)
    predicted_bscan = bscan_from_frequency_response(
        reference.frequency_response,
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    observed_bscan = predicted_bscan + np.array([[0.2, -0.1, 0.05], [-0.15, 0.1, -0.08]], dtype=float) @ np.array(
        [
            np.exp(-((time_vector - 3.0e-9) / 0.7e-9) ** 2),
            np.exp(-((time_vector - 6.0e-9) / 0.9e-9) ** 2),
            np.exp(-((time_vector - 9.0e-9) / 1.1e-9) ** 2),
        ]
    )
    sample_weights = np.linspace(1.0, 2.0, time_vector.size)
    result = prepare_ibim_bscan_adjoint_context(
        boundary,
        source_points,
        receiver_points,
        angular_frequencies,
        source_strength,
        observed_bscan,
        time_vector=time_vector,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        frequency_window=frequency_window,
        time_gate_start=2.0e-9,
        sample_weights=sample_weights,
        backend="numpy",
    )

    cached = ibim_bscan_leading_order_normal_shape_gradient(result, boundary)
    node_directional = np.zeros_like(cached)
    weights = None
    for context in result.per_frequency_contexts:
        strict_quadrature = context.forward.system.use_strict_quadrature
        boundary_points, normals, weights = ibim_adj._boundary_point_normal_weight_arrays(
            boundary,
            use_strict_quadrature=strict_quadrature,
        )
        node_directional += np.array(
            [
                ibim_adj._ibim_leading_order_single_sample_normal_gradient(
                    context=context,
                    boundary_points=boundary_points,
                    normals=normals,
                    weights=weights,
                    sample_index=sample_index,
                )
                for sample_index in range(boundary_points.shape[0])
            ],
            dtype=float,
        )
    assert weights is not None
    uncached = ibim_adj._node_directional_to_shape_gradient_density(node_directional, weights)
    np.testing.assert_allclose(cached, uncached, rtol=1.0e-12, atol=1.0e-12)
