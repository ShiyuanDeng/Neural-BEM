from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config.simulation_config as cfg
from gpr_bem import (
    Material,
    build_ibim_tmz_frequency_system,
    build_implicit_boundary_band,
    compress_implicit_boundary_band,
    ibim_incident_trace_on_boundary,
    solve_ibim_tmz_frequency_response,
    solve_ibim_tmz_total_field_batch,
)
from gpr_bem.neural_sdf import circle_signed_distance


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


def test_ibim_incident_trace_on_boundary_returns_expected_shapes() -> None:
    boundary = _compressed_circle_boundary()
    exterior, _interior = _materials()
    source_points = np.array(
        [
            [cfg.SCAN_START, cfg.ANTENNA_Y],
            [cfg.SCAN_START + 0.05, cfg.ANTENNA_Y],
        ],
        dtype=float,
    )
    angular_frequency = 2.0 * np.pi * 1.0e9
    source_strength = 1.0 + 0.25j

    dirichlet, neumann = ibim_incident_trace_on_boundary(
        boundary,
        source_points,
        angular_frequency,
        source_strength,
        exterior=exterior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
    )

    assert np.asarray(dirichlet).shape == (source_points.shape[0], boundary.num_samples)
    assert np.asarray(neumann).shape == (source_points.shape[0], boundary.num_samples)
    assert np.isfinite(np.asarray(dirichlet)).all()
    assert np.isfinite(np.asarray(neumann)).all()


def test_ibim_tmz_frequency_system_has_expected_block_size() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequency = 2.0 * np.pi * 1.0e9

    system = build_ibim_tmz_frequency_system(
        boundary,
        angular_frequency,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="numpy",
    )

    n = boundary.num_samples
    assert system.num_boundary_samples == n
    assert np.asarray(system.system_matrix).shape == (1, 2 * n, 2 * n)
    assert np.asarray(system.system_matrix_squared).shape == (1, 2 * n, 2 * n)
    assert np.isfinite(np.asarray(system.system_matrix)).all()


def test_ibim_tmz_frequency_response_has_expected_shape_and_finite_values() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    angular_frequencies = 2.0 * np.pi * np.array([0.8e9, 1.0e9, 1.2e9], dtype=float)
    source_points = np.array(
        [
            [0.18, cfg.ANTENNA_Y],
            [0.26, cfg.ANTENNA_Y],
        ],
        dtype=float,
    )
    receiver_points = source_points + np.array([cfg.TX_RX_OFFSET, 0.0], dtype=float)
    source_strength = 1.0 + 0.25j

    implicit_result = solve_ibim_tmz_frequency_response(
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
    assert implicit_result.frequency_response.shape == (source_points.shape[0], angular_frequencies.size)
    assert len(implicit_result.forwards) == angular_frequencies.size
    assert np.isfinite(implicit_result.frequency_response).all()


def test_ibim_tmz_direct_solve_strategy_matches_squared_strategy_with_smaller_residual() -> None:
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

    direct = solve_ibim_tmz_total_field_batch(
        boundary,
        source_points,
        receiver_points,
        angular_frequency,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        solve_strategy="direct",
        backend="numpy",
    )
    squared = solve_ibim_tmz_total_field_batch(
        boundary,
        source_points,
        receiver_points,
        angular_frequency,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        solve_strategy="squared",
        backend="numpy",
    )

    assert direct.solve_strategy == "direct"
    assert squared.solve_strategy == "squared"
    assert direct.linear_system_relative_residual < squared.linear_system_relative_residual
    assert direct.linear_system_relative_residual < 1.0e-10
    np.testing.assert_allclose(direct.total_receiver, squared.total_receiver, rtol=1.0e-5, atol=1.0e-8)


def test_ibim_tmz_solve_strategy_rejects_unknown_value() -> None:
    boundary = _compressed_circle_boundary()
    exterior, interior = _materials()
    with pytest.raises(ValueError, match="solve_strategy"):
        solve_ibim_tmz_total_field_batch(
            boundary,
            np.array([[0.18, cfg.ANTENNA_Y]], dtype=float),
            np.array([[0.18 + cfg.TX_RX_OFFSET, cfg.ANTENNA_Y]], dtype=float),
            2.0 * np.pi * 1.0e9,
            1.0,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            solve_strategy="normal-equations",
            backend="numpy",
        )


def test_ibim_tmz_total_field_batch_cupy_matches_numpy_when_available() -> None:
    pytest.importorskip("cupy")

    exterior, interior = _materials()
    band = build_implicit_boundary_band(
        lambda points: circle_signed_distance(
            points,
            center=(cfg.TARGET_CENTER_X, cfg.TARGET_CENTER_Y),
            radius=cfg.TARGET_RADIUS,
        ),
        ((0.0, 0.0), (cfg.DOMAIN_WIDTH, cfg.DOMAIN_HEIGHT)),
        grid_shape=(193, 193),
        dtype=torch.float64,
    )
    boundary = compress_implicit_boundary_band(band)
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

    numpy_result = solve_ibim_tmz_total_field_batch(
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
    cupy_result = solve_ibim_tmz_total_field_batch(
        boundary,
        source_points,
        receiver_points,
        angular_frequency,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
        backend="cupy",
    )

    np.testing.assert_allclose(
        cupy_result.total_receiver,
        numpy_result.total_receiver,
        rtol=1.0e-11,
        atol=1.0e-12,
    )
