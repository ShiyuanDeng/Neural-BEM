#!/usr/bin/env python3
"""QBX diagonal diagnostics for the kernel-differenced Muller solvers.

This is intentionally a scratchpad driver.  It does not modify the production
solver packages; the experimental bounded-diagonal QBX variant is assembled
locally so its results can be compared against the existing implementations.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from scipy.interpolate import CubicSpline
from scipy.spatial import cKDTree
from scipy.special import hankel1, jv
from scipy.signal import resample

ROOT = Path(__file__).resolve().parents[3]
SOLVERS = ROOT / "solvers"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SOLVERS) not in sys.path:
    sys.path.insert(0, str(SOLVERS))

import config.circle_config as circle_cfg  # noqa: E402
import config.ellipse_config as ellipse_cfg  # noqa: E402
import config.star_config as star_cfg  # noqa: E402
import gpr_bem_kdiff  # noqa: E402
import gpr_bem_mod  # noqa: E402
import gpr_bem_ref  # noqa: E402
import gpr_bem_kdiff.ibim_tmz_forward as kdiff_forward  # noqa: E402
from qbx_legacy_near_band import QbxSettings, _qbx_diff_row  # noqa: E402
import nystrom_ref.nystrom_tmz as nystrom_tmz  # noqa: E402
from nystrom_ref import (  # noqa: E402
    build_curve,
    circle_parameterization,
    ellipse_parameterization,
    solve_transmission,
    star_parameterization,
)

RING_STANDOFF = 0.30
NUM_RING_PAIRS = 24
GRID = (161, 161)
NYSTROM_N = 512
TWO_PI = 2.0 * np.pi
DEFAULT_FREQUENCIES_GHZ = (0.5, 1.5, 2.5)
DEFAULT_RHO_FACTORS = (0.5, 0.75, 1.0)
DEFAULT_ORDERS = (4, 6, 8, 12, 16, 20, 24, 32, 40, 64)
NOMINAL_N = {"circle": 168, "ellipse": 120, "star": 164}
BOUNDED_BLOCKS = ("single", "double", "adjoint")
BLOCK_LABELS = {
    "single": "S_diff",
    "double": "D_diff",
    "adjoint": "Kp_diff",
    "hyper": "T_diff",
}
SOLVE_NAMES = (
    "gpr_bem_mod",
    "gpr_bem_kdiff",
    "EXP_BOUNDED_DIAG_QBX",
    "EXP_T_OPERATOR_QBX",
    "EXP_ALL_DIAG_FIX",
)


@dataclass(frozen=True)
class ProbeCase:
    name: str
    cfg: object
    center: tuple[float, float]
    bounds: tuple[tuple[float, float], tuple[float, float]]
    build_boundary: Callable[[object], object]
    feature_targets: Callable[[], list[tuple[str, np.ndarray]]]
    reference_scattered: Callable[[np.ndarray, np.ndarray, np.ndarray], dict[float, np.ndarray]]
    sdf_for_kdiff: Callable[[torch.Tensor], torch.Tensor] | None = None


@dataclass
class SolverMetric:
    error: float
    residual: float
    condition_number: float
    elapsed_seconds: float
    num_samples: int


def _ring_scan(center: tuple[float, float], tx_rx_offset: float) -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0.0, 2.0 * np.pi, NUM_RING_PAIRS, endpoint=False, dtype=float)
    separation = float(tx_rx_offset) / RING_STANDOFF
    sources = np.column_stack(
        (
            center[0] + RING_STANDOFF * np.cos(angles),
            center[1] + RING_STANDOFF * np.sin(angles),
        )
    )
    receivers = np.column_stack(
        (
            center[0] + RING_STANDOFF * np.cos(angles + separation),
            center[1] + RING_STANDOFF * np.sin(angles + separation),
        )
    )
    return sources, receivers


def _materials(solver: object, cfg: object):
    exterior = solver.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = solver.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    return exterior, interior


def _wavenumbers(cfg: object, frequency_hz: float) -> tuple[complex, complex]:
    angular_frequency = 2.0 * np.pi * frequency_hz
    exterior, interior = _materials(gpr_bem_ref, cfg)
    return (
        complex(exterior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0)),
        complex(interior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0)),
    )


def _compress_boundary(solver: object, phi: Callable[[torch.Tensor], torch.Tensor], bounds) -> object:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = solver.build_implicit_boundary_band(phi, bounds, grid_shape=GRID, dtype=torch.float64)
        return solver.compress_implicit_boundary_band(band)


def _circle_case() -> ProbeCase:
    radius = float(circle_cfg.TARGET_RADIUS)
    center = (float(circle_cfg.TARGET_CENTER_X), float(circle_cfg.TARGET_CENTER_Y))
    bounds = (
        (center[0] - 3.0 * radius, center[1] - 3.0 * radius),
        (center[0] + 3.0 * radius, center[1] + 3.0 * radius),
    )

    def build_boundary(solver: object) -> object:
        def phi(points: torch.Tensor) -> torch.Tensor:
            return solver.circle_signed_distance(points, center=center, radius=radius)

        return _compress_boundary(solver, phi, bounds)

    def feature_targets() -> list[tuple[str, np.ndarray]]:
        return [("east", np.array([center[0] + radius, center[1]], dtype=float))]

    def reference_scattered(
        frequencies_hz: np.ndarray, sources: np.ndarray, receivers: np.ndarray
    ) -> dict[float, np.ndarray]:
        reference = {}
        for frequency_hz in frequencies_hz:
            k_ext, k_int = _wavenumbers(circle_cfg, float(frequency_hz))
            exact = gpr_bem_ref.penetrable_cylinder_scattered_field(
                receivers,
                sources,
                k_exterior=k_ext,
                k_interior=k_int,
                radius=radius,
                center=center,
            )
            reference[float(frequency_hz)] = exact
        return reference

    return ProbeCase("circle", circle_cfg, center, bounds, build_boundary, feature_targets, reference_scattered)


def _ellipse_level_set(points: torch.Tensor) -> torch.Tensor:
    center = torch.tensor(
        (float(ellipse_cfg.TARGET_CENTER_X), float(ellipse_cfg.TARGET_CENTER_Y)),
        device=points.device,
        dtype=points.dtype,
    )
    rel = points - center[None, :]
    semi_major = float(ellipse_cfg.TARGET_SEMI_MAJOR)
    semi_minor = float(ellipse_cfg.TARGET_SEMI_MINOR)
    radial = torch.sqrt((rel[:, 0] / semi_major) ** 2 + (rel[:, 1] / semi_minor) ** 2)
    return ((radial - 1.0) * min(semi_major, semi_minor)).reshape(-1, 1)


def _ellipse_case() -> ProbeCase:
    semi_major = float(ellipse_cfg.TARGET_SEMI_MAJOR)
    semi_minor = float(ellipse_cfg.TARGET_SEMI_MINOR)
    target_size = float(ellipse_cfg.TARGET_SIZE)
    center = (float(ellipse_cfg.TARGET_CENTER_X), float(ellipse_cfg.TARGET_CENTER_Y))
    bounds = (
        (center[0] - 3.0 * target_size, center[1] - 3.0 * target_size),
        (center[0] + 3.0 * target_size, center[1] + 3.0 * target_size),
    )

    def build_boundary(solver: object) -> object:
        return _compress_boundary(solver, _ellipse_level_set, bounds)

    def feature_targets() -> list[tuple[str, np.ndarray]]:
        return [
            ("major_tip", np.array([center[0] + semi_major, center[1]], dtype=float)),
            ("minor_tip", np.array([center[0], center[1] + semi_minor], dtype=float)),
            (
                "intermediate",
                np.array(
                    [
                        center[0] + semi_major / math.sqrt(2.0),
                        center[1] + semi_minor / math.sqrt(2.0),
                    ],
                    dtype=float,
                ),
            ),
        ]

    def reference_scattered(
        frequencies_hz: np.ndarray, sources: np.ndarray, receivers: np.ndarray
    ) -> dict[float, np.ndarray]:
        curve = build_curve(ellipse_parameterization(center, semi_major, semi_minor), NYSTROM_N, "ellipse")
        reference = {}
        for frequency_hz in frequencies_hz:
            k_ext, k_int = _wavenumbers(ellipse_cfg, float(frequency_hz))
            solution = solve_transmission(curve, sources, receivers, k_ext, k_int)
            reference[float(frequency_hz)] = np.diag(solution.scattered)
        return reference

    return ProbeCase(
        "ellipse",
        ellipse_cfg,
        center,
        bounds,
        build_boundary,
        feature_targets,
        reference_scattered,
        sdf_for_kdiff=_ellipse_level_set,
    )


def _chebyshev_t(values: torch.Tensor, order: int) -> torch.Tensor:
    if order == 0:
        return torch.ones_like(values)
    if order == 1:
        return values
    previous = torch.ones_like(values)
    current = values
    for _ in range(2, order + 1):
        previous, current = current, 2.0 * values * current - previous
    return current


def _star_level_set(points: torch.Tensor) -> torch.Tensor:
    center = torch.tensor(
        (float(star_cfg.TARGET_CENTER_X), float(star_cfg.TARGET_CENTER_Y)),
        device=points.device,
        dtype=points.dtype,
    )
    rel = points - center[None, :]
    radius = torch.sqrt(torch.sum(rel * rel, dim=1, keepdim=True) + 1.0e-30)
    cos_theta = rel[:, 0:1] / radius
    cos_lobes_theta = _chebyshev_t(cos_theta, int(star_cfg.TARGET_STAR_LOBES))
    boundary_radius = float(star_cfg.TARGET_MEAN_RADIUS) * (
        1.0 + float(star_cfg.TARGET_STAR_AMPLITUDE) * cos_lobes_theta
    )
    return radius - boundary_radius


def _star_case() -> ProbeCase:
    mean_radius = float(star_cfg.TARGET_MEAN_RADIUS)
    amplitude = float(star_cfg.TARGET_STAR_AMPLITUDE)
    lobes = int(star_cfg.TARGET_STAR_LOBES)
    target_size = float(star_cfg.TARGET_SIZE)
    center = (float(star_cfg.TARGET_CENTER_X), float(star_cfg.TARGET_CENTER_Y))
    bounds = (
        (center[0] - 3.0 * target_size, center[1] - 3.0 * target_size),
        (center[0] + 3.0 * target_size, center[1] + 3.0 * target_size),
    )

    def build_boundary(solver: object) -> object:
        return _compress_boundary(solver, _star_level_set, bounds)

    def polar_point(theta: float, radius: float) -> np.ndarray:
        return np.array([center[0] + radius * np.cos(theta), center[1] + radius * np.sin(theta)], dtype=float)

    def feature_targets() -> list[tuple[str, np.ndarray]]:
        lobe_radius = mean_radius * (1.0 + amplitude)
        valley_radius = mean_radius * (1.0 - amplitude)
        return [
            ("lobe_tip", polar_point(0.0, lobe_radius)),
            ("valley", polar_point(np.pi / lobes, valley_radius)),
            ("transition", polar_point(np.pi / (2.0 * lobes), mean_radius)),
        ]

    def reference_scattered(
        frequencies_hz: np.ndarray, sources: np.ndarray, receivers: np.ndarray
    ) -> dict[float, np.ndarray]:
        curve = build_curve(star_parameterization(center, mean_radius, amplitude, lobes), NYSTROM_N, "star")
        reference = {}
        for frequency_hz in frequencies_hz:
            k_ext, k_int = _wavenumbers(star_cfg, float(frequency_hz))
            solution = solve_transmission(curve, sources, receivers, k_ext, k_int)
            reference[float(frequency_hz)] = np.diag(solution.scattered)
        return reference

    return ProbeCase(
        "star",
        star_cfg,
        center,
        bounds,
        build_boundary,
        feature_targets,
        reference_scattered,
        sdf_for_kdiff=_star_level_set,
    )


def _all_cases() -> list[ProbeCase]:
    return [_circle_case(), _ellipse_case(), _star_case()]


def _nearest_feature_indices(case: ProbeCase, points: np.ndarray) -> list[tuple[str, int]]:
    selected = []
    seen: set[int] = set()
    for label, target in case.feature_targets():
        index = int(np.argmin(np.linalg.norm(points - target[None, :], axis=1)))
        if index not in seen:
            selected.append((label, index))
            seen.add(index)
    return selected


def _expansion_geometry(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    settings: QbxSettings,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    frames = kdiff_forward._local_frames(points, normals, weights)
    curvature = kdiff_forward._sdf_curvature(points, sdf_fn) if sdf_fn is not None else frames["curvature"]
    curvature_radius = kdiff_forward._local_radius(curvature)
    cap = settings.radius_curvature_factor * curvature_radius
    default_radius = np.minimum(settings.radius_spacing_factor * frames["step_scale"], cap)
    return frames["step_scale"], cap, np.maximum(default_radius, 1.0e-12), curvature


def _qbx_self_value(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    index: int,
    k_ext: complex,
    k_int: complex,
    rho: float,
    order: int,
) -> dict[str, complex]:
    row = _qbx_diff_row(
        points[index],
        normals[index],
        points[index : index + 1],
        normals[index : index + 1],
        k_ext,
        k_int,
        float(rho),
        int(order),
    )
    return {key: complex(row[key][0] * weights[index]) for key in BLOCK_LABELS}


def _qbx_bounded_diagonal_terms(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    k_ext: complex,
    k_int: complex,
    settings: QbxSettings,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None,
) -> dict[str, np.ndarray]:
    _, _, expansion_radius, _ = _expansion_geometry(points, normals, weights, settings, sdf_fn)
    diagonal = {key: np.empty(points.shape[0], dtype=complex) for key in BOUNDED_BLOCKS}
    for index in range(points.shape[0]):
        values = _qbx_self_value(
            points,
            normals,
            weights,
            index,
            k_ext,
            k_int,
            float(expansion_radius[index]),
            settings.expansion_order,
        )
        for key in BOUNDED_BLOCKS:
            diagonal[key][index] = values[key]
    return diagonal


def _build_exp_bounded_blocks(
    boundary: object,
    k_ext: complex,
    k_int: complex,
    settings: QbxSettings,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None,
):
    points, normals, weights = kdiff_forward.boundary_points_normals_weights(boundary)
    num_nodes = points.shape[0]
    geometry = kdiff_forward._pair_geometry(points, normals, points, normals, outer=True)
    safe_r = np.where(np.eye(num_nodes, dtype=bool), 1.0, geometry[0])
    kernels, _ = kdiff_forward._difference_kernels(safe_r, *geometry[1:], k_ext, k_int)
    old_diagonal = kdiff_forward._diagonal_terms(points, normals, weights, k_ext, k_int, sdf_fn=sdf_fn)
    qbx_diagonal = _qbx_bounded_diagonal_terms(points, normals, weights, k_ext, k_int, settings, sdf_fn)

    matrices = {}
    for key in BLOCK_LABELS:
        matrix = kernels[key] * weights[None, :]
        np.fill_diagonal(matrix, old_diagonal[key])
        if key in qbx_diagonal:
            np.fill_diagonal(matrix, qbx_diagonal[key])
        matrices[key] = matrix
    return points, normals, weights, matrices


def _qbx_operator_t_matrix(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    k_ext: complex,
    k_int: complex,
    settings: QbxSettings,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None,
) -> np.ndarray:
    """Full-row operator-level QBX matrix for the Muller ``T_diff`` block.

    Every source node, including ``j == i``, participates in the coefficient
    quadrature.  The resulting diagonal entry is an algebraic contribution to
    this quadrature approximation, not a finite pointwise kernel value.
    """

    _, _, expansion_radius, _ = _expansion_geometry(points, normals, weights, settings, sdf_fn)
    return _qbx_operator_t_rect_matrix_fast(
        points,
        normals,
        points,
        normals,
        weights,
        k_ext,
        k_int,
        expansion_radius,
        settings.expansion_order,
    )


def _qbx_center_clearance(
    points: np.ndarray,
    normals: np.ndarray,
    expansion_radius: np.ndarray,
) -> tuple[float, float, int]:
    """Return minimum nonself Graf clearance for both one-sided centers.

    The self node sits exactly at ratio 1 and is intentionally excluded.  Other
    nodes should have ``|y_j-c_i| / rho_i > 1`` for the full-row expansion to
    be geometrically admissible.
    """

    min_ratio = float("inf")
    min_margin = float("inf")
    bad_count = 0
    for side in (1.0, -1.0):
        centers = points + side * expansion_radius[:, None] * normals
        distances = np.linalg.norm(centers[:, None, :] - points[None, :, :], axis=2)
        np.fill_diagonal(distances, np.inf)
        ratio = distances / expansion_radius[:, None]
        margin = distances - expansion_radius[:, None]
        min_ratio = min(min_ratio, float(np.min(ratio)))
        min_margin = min(min_margin, float(np.min(margin)))
        bad_count += int(np.count_nonzero(ratio <= 1.0))
    return min_ratio, min_margin, bad_count


def _qbx_target_source_clearance(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    expansion_radius: np.ndarray,
    self_source_indices: np.ndarray | None = None,
) -> tuple[float, float, int]:
    min_ratio = float("inf")
    min_margin = float("inf")
    bad_count = 0
    for side in (1.0, -1.0):
        centers = target_points + side * expansion_radius[:, None] * target_normals
        distances = np.linalg.norm(centers[:, None, :] - source_points[None, :, :], axis=2)
        if self_source_indices is not None:
            distances[np.arange(target_points.shape[0]), self_source_indices] = np.inf
        ratio = distances / expansion_radius[:, None]
        margin = distances - expansion_radius[:, None]
        min_ratio = min(min_ratio, float(np.min(ratio)))
        min_margin = min(min_margin, float(np.min(margin)))
        bad_count += int(np.count_nonzero(ratio <= 1.0))
    return min_ratio, min_margin, bad_count


def _build_experiment_blocks(
    boundary: object,
    k_ext: complex,
    k_int: complex,
    settings: QbxSettings,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None,
    *,
    bounded_diagonal_qbx: bool,
    t_operator_qbx: bool,
):
    points, normals, weights = kdiff_forward.boundary_points_normals_weights(boundary)
    num_nodes = points.shape[0]
    geometry = kdiff_forward._pair_geometry(points, normals, points, normals, outer=True)
    safe_r = np.where(np.eye(num_nodes, dtype=bool), 1.0, geometry[0])
    kernels, _ = kdiff_forward._difference_kernels(safe_r, *geometry[1:], k_ext, k_int)
    old_diagonal = kdiff_forward._diagonal_terms(points, normals, weights, k_ext, k_int, sdf_fn=sdf_fn)
    qbx_diagonal = (
        _qbx_bounded_diagonal_terms(points, normals, weights, k_ext, k_int, settings, sdf_fn)
        if bounded_diagonal_qbx
        else {}
    )

    matrices = {}
    for key in BLOCK_LABELS:
        matrix = kernels[key] * weights[None, :]
        np.fill_diagonal(matrix, old_diagonal[key])
        if key in qbx_diagonal:
            np.fill_diagonal(matrix, qbx_diagonal[key])
        matrices[key] = matrix

    if t_operator_qbx:
        matrices["hyper"] = _qbx_operator_t_matrix(points, normals, weights, k_ext, k_int, settings, sdf_fn)

    return points, normals, weights, matrices


def _build_direct_blocks_from_arrays(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    k_ext: complex,
    k_int: complex,
    settings: QbxSettings,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None,
    *,
    bounded_diagonal_qbx: bool,
) -> dict[str, np.ndarray]:
    num_nodes = points.shape[0]
    geometry = kdiff_forward._pair_geometry(points, normals, points, normals, outer=True)
    safe_r = np.where(np.eye(num_nodes, dtype=bool), 1.0, geometry[0])
    kernels, _ = kdiff_forward._difference_kernels(safe_r, *geometry[1:], k_ext, k_int)
    old_diagonal = kdiff_forward._diagonal_terms(points, normals, weights, k_ext, k_int, sdf_fn=sdf_fn)
    qbx_diagonal = (
        _qbx_bounded_diagonal_terms(points, normals, weights, k_ext, k_int, settings, sdf_fn)
        if bounded_diagonal_qbx
        else {}
    )
    matrices = {}
    for key in BLOCK_LABELS:
        matrix = kernels[key] * weights[None, :]
        np.fill_diagonal(matrix, old_diagonal[key])
        if key in qbx_diagonal:
            np.fill_diagonal(matrix, qbx_diagonal[key])
        matrices[key] = matrix
    return matrices


def _solve_exp_bounded_diag_qbx(
    boundary: object,
    sources: np.ndarray,
    receivers: np.ndarray,
    frequency_hz: float,
    source_strength: float,
    case: ProbeCase,
    settings: QbxSettings,
) -> tuple[np.ndarray, float, float, int]:
    angular_frequency = 2.0 * np.pi * frequency_hz
    exterior, interior = _materials(gpr_bem_kdiff, case.cfg)
    k_ext = complex(exterior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))
    k_int = complex(interior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))
    points, normals, weights, blocks = _build_exp_bounded_blocks(
        boundary, k_ext, k_int, settings, case.sdf_for_kdiff
    )
    num_nodes = points.shape[0]
    identity = np.eye(num_nodes, dtype=complex)
    matrix = np.block(
        [
            [identity - blocks["double"], blocks["single"]],
            [-blocks["hyper"], identity + blocks["adjoint"]],
        ]
    )

    dirichlet_incident, neumann_incident = gpr_bem_kdiff.ibim_incident_trace_on_boundary(
        points,
        normals,
        sources,
        angular_frequency,
        source_strength,
        exterior=exterior,
        eps0=case.cfg.EPS0,
        mu0=case.cfg.MU0,
    )
    rhs = np.concatenate((dirichlet_incident, neumann_incident), axis=1).T
    solution = np.linalg.solve(matrix, rhs)
    residual = float(np.linalg.norm(matrix @ solution - rhs) / np.linalg.norm(rhs))

    dirichlet_total = solution[:num_nodes].T
    neumann_total = solution[num_nodes:].T
    source_receiver_distance = np.linalg.norm(receivers - sources, axis=1)
    incident_receiver = source_strength * (0.25j * hankel1(0, k_ext * source_receiver_distance))

    displacement = receivers[:, None, :] - points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    projection = np.einsum("mnd,nd->mn", displacement, normals) / distance
    green = 0.25j * hankel1(0, k_ext * distance)
    green_normal = 0.25j * k_ext * hankel1(1, k_ext * distance) * projection
    single_receiver = (green * neumann_total * weights[None, :]).sum(axis=-1)
    double_receiver = (green_normal * dirichlet_total * weights[None, :]).sum(axis=-1)
    scattered = double_receiver - single_receiver
    _ = incident_receiver  # kept to mirror the package solver evaluation path.
    return np.asarray(scattered, dtype=complex), residual, float(np.linalg.cond(matrix)), num_nodes


def _solve_experiment_variant(
    boundary: object,
    sources: np.ndarray,
    receivers: np.ndarray,
    frequency_hz: float,
    source_strength: float,
    case: ProbeCase,
    settings: QbxSettings,
    *,
    bounded_diagonal_qbx: bool,
    t_operator_qbx: bool,
) -> tuple[np.ndarray, float, float, int]:
    angular_frequency = 2.0 * np.pi * frequency_hz
    exterior, interior = _materials(gpr_bem_kdiff, case.cfg)
    k_ext = complex(exterior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))
    k_int = complex(interior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))
    points, normals, weights, blocks = _build_experiment_blocks(
        boundary,
        k_ext,
        k_int,
        settings,
        case.sdf_for_kdiff,
        bounded_diagonal_qbx=bounded_diagonal_qbx,
        t_operator_qbx=t_operator_qbx,
    )
    num_nodes = points.shape[0]
    identity = np.eye(num_nodes, dtype=complex)
    matrix = np.block(
        [
            [identity - blocks["double"], blocks["single"]],
            [-blocks["hyper"], identity + blocks["adjoint"]],
        ]
    )

    dirichlet_incident, neumann_incident = gpr_bem_kdiff.ibim_incident_trace_on_boundary(
        points,
        normals,
        sources,
        angular_frequency,
        source_strength,
        exterior=exterior,
        eps0=case.cfg.EPS0,
        mu0=case.cfg.MU0,
    )
    rhs = np.concatenate((dirichlet_incident, neumann_incident), axis=1).T
    solution = np.linalg.solve(matrix, rhs)
    residual = float(np.linalg.norm(matrix @ solution - rhs) / np.linalg.norm(rhs))

    dirichlet_total = solution[:num_nodes].T
    neumann_total = solution[num_nodes:].T
    displacement = receivers[:, None, :] - points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    projection = np.einsum("mnd,nd->mn", displacement, normals) / distance
    green = 0.25j * hankel1(0, k_ext * distance)
    green_normal = 0.25j * k_ext * hankel1(1, k_ext * distance) * projection
    single_receiver = (green * neumann_total * weights[None, :]).sum(axis=-1)
    double_receiver = (green_normal * dirichlet_total * weights[None, :]).sum(axis=-1)
    scattered = double_receiver - single_receiver
    return np.asarray(scattered, dtype=complex), residual, float(np.linalg.cond(matrix)), num_nodes


def _solve_ibim_source_t_qbx_variant(
    case: ProbeCase,
    sources: np.ndarray,
    receivers: np.ndarray,
    frequency_hz: float,
    settings: QbxSettings,
    source_factor: int,
    *,
    delta_cells: float | None,
    band_cells: float | None,
    strict_weights: bool,
    reproject_targets: bool,
    reproject_sources: bool,
    bounded_diagonal_qbx: bool,
    idw_neighbours: int,
    idw_power: float,
    source_chunk_size: int,
) -> tuple[np.ndarray, float, float, int, int, float, int, float]:
    angular_frequency = 2.0 * np.pi * frequency_hz
    exterior, interior = _materials(gpr_bem_kdiff, case.cfg)
    k_ext = complex(exterior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))
    k_int = complex(interior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))

    boundary = case.build_boundary(gpr_bem_kdiff)
    points, normals, weights = kdiff_forward.boundary_points_normals_weights(boundary)
    sdf_fn = _case_sdf_for_sampling(case) if reproject_targets else case.sdf_for_kdiff
    if reproject_targets:
        points, normals = _reproject_points_and_normals(case, points)

    source_points, source_normals, source_weights, source_count, _delta_half_width, _source_measure = (
        _ibim_raw_source_samples(
            case,
            source_factor,
            delta_cells=delta_cells,
            band_cells=band_cells,
            strict_weights=strict_weights,
            reproject_sources=reproject_sources,
        )
    )
    _, _, expansion_radius, _ = _expansion_geometry(points, normals, weights, settings, sdf_fn)
    min_ratio, _min_margin, bad_count = _qbx_target_source_clearance(
        points,
        normals,
        source_points,
        expansion_radius,
        None,
    )
    prolongation = _idw_prolongation_matrix(
        points,
        source_points,
        neighbours=idw_neighbours,
        power=idw_power,
    )

    blocks = _build_direct_blocks_from_arrays(
        points,
        normals,
        weights,
        k_ext,
        k_int,
        settings,
        sdf_fn,
        bounded_diagonal_qbx=bounded_diagonal_qbx,
    )
    blocks["hyper"] = _qbx_operator_t_matrix_with_source_prolongation(
        points,
        normals,
        source_points,
        source_normals,
        source_weights,
        prolongation,
        k_ext,
        k_int,
        expansion_radius,
        settings.expansion_order,
        source_chunk_size,
    )

    num_nodes = points.shape[0]
    identity = np.eye(num_nodes, dtype=complex)
    matrix = np.block(
        [
            [identity - blocks["double"], blocks["single"]],
            [-blocks["hyper"], identity + blocks["adjoint"]],
        ]
    )
    dirichlet_incident, neumann_incident = gpr_bem_kdiff.ibim_incident_trace_on_boundary(
        points,
        normals,
        sources,
        angular_frequency,
        1.0,
        exterior=exterior,
        eps0=case.cfg.EPS0,
        mu0=case.cfg.MU0,
    )
    rhs = np.concatenate((dirichlet_incident, neumann_incident), axis=1).T
    solution = np.linalg.solve(matrix, rhs)
    residual = float(np.linalg.norm(matrix @ solution - rhs) / np.linalg.norm(rhs))

    dirichlet_total = solution[:num_nodes].T
    neumann_total = solution[num_nodes:].T
    displacement = receivers[:, None, :] - points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    projection = np.einsum("mnd,nd->mn", displacement, normals) / distance
    green = 0.25j * hankel1(0, k_ext * distance)
    green_normal = 0.25j * k_ext * hankel1(1, k_ext * distance) * projection
    single_receiver = (green * neumann_total * weights[None, :]).sum(axis=-1)
    double_receiver = (green_normal * dirichlet_total * weights[None, :]).sum(axis=-1)
    scattered = double_receiver - single_receiver
    return (
        np.asarray(scattered, dtype=complex),
        residual,
        float(np.linalg.cond(matrix)),
        num_nodes,
        source_count,
        min_ratio,
        bad_count,
        float(np.max(np.abs(blocks["hyper"]))),
    )


def _solve_ibim_perfect_prolongation_t_qbx_variant(
    case: ProbeCase,
    sources: np.ndarray,
    receivers: np.ndarray,
    frequency_hz: float,
    settings: QbxSettings,
    source_factor: int,
    *,
    reproject_targets: bool,
    bounded_diagonal_qbx: bool,
    source_chunk_size: int,
) -> tuple[np.ndarray, float, float, int, int, float, int, float]:
    """Condition B: "perfect boundary knowledge" raw-source T-QBX solve.

    Keeps the real compressed IBIM boundary as the unknown/target grid (same
    as ``_solve_ibim_source_t_qbx_variant``), but:

    - recovers each target's curve parameter ``t`` analytically instead of by
      an unordered index or Euclidean IDW neighbourhood;
    - builds the oversampled sources directly from the analytic
      parameterization (exact by construction, no SDF band/reprojection
      needed for the sources);
    - prolongs the compressed-target Neumann density to the oversampled
      sources by periodic cubic-spline interpolation in ``t`` instead of
      local inverse-distance weighting.

    Everything else (S/D/Kp on the target grid, T assembly, the Muller
    solve, and the scattered-field evaluation) is identical to condition A.
    """

    angular_frequency = 2.0 * np.pi * frequency_hz
    exterior, interior = _materials(gpr_bem_kdiff, case.cfg)
    k_ext = complex(exterior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))
    k_int = complex(interior.wavenumber(angular_frequency, case.cfg.EPS0, case.cfg.MU0))

    boundary = case.build_boundary(gpr_bem_kdiff)
    points, normals, weights = kdiff_forward.boundary_points_normals_weights(boundary)
    sdf_fn = _case_sdf_for_sampling(case) if reproject_targets else case.sdf_for_kdiff
    if reproject_targets:
        points, normals = _reproject_points_and_normals(case, points)
    target_t = _point_parameters(case, points)

    source_points, source_normals, source_weights, source_t, source_count = (
        _analytic_oversampled_source_samples(case, source_factor, points.shape[0])
    )

    _, _, expansion_radius, _ = _expansion_geometry(points, normals, weights, settings, sdf_fn)
    min_ratio, _min_margin, bad_count = _qbx_target_source_clearance(
        points,
        normals,
        source_points,
        expansion_radius,
        None,
    )
    prolongation = _periodic_spline_prolongation_matrix(target_t, source_t)

    blocks = _build_direct_blocks_from_arrays(
        points,
        normals,
        weights,
        k_ext,
        k_int,
        settings,
        sdf_fn,
        bounded_diagonal_qbx=bounded_diagonal_qbx,
    )
    blocks["hyper"] = _qbx_operator_t_matrix_with_source_prolongation(
        points,
        normals,
        source_points,
        source_normals,
        source_weights,
        prolongation,
        k_ext,
        k_int,
        expansion_radius,
        settings.expansion_order,
        source_chunk_size,
    )

    num_nodes = points.shape[0]
    identity = np.eye(num_nodes, dtype=complex)
    matrix = np.block(
        [
            [identity - blocks["double"], blocks["single"]],
            [-blocks["hyper"], identity + blocks["adjoint"]],
        ]
    )
    dirichlet_incident, neumann_incident = gpr_bem_kdiff.ibim_incident_trace_on_boundary(
        points,
        normals,
        sources,
        angular_frequency,
        1.0,
        exterior=exterior,
        eps0=case.cfg.EPS0,
        mu0=case.cfg.MU0,
    )
    rhs = np.concatenate((dirichlet_incident, neumann_incident), axis=1).T
    solution = np.linalg.solve(matrix, rhs)
    residual = float(np.linalg.norm(matrix @ solution - rhs) / np.linalg.norm(rhs))

    dirichlet_total = solution[:num_nodes].T
    neumann_total = solution[num_nodes:].T
    displacement = receivers[:, None, :] - points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    projection = np.einsum("mnd,nd->mn", displacement, normals) / distance
    green = 0.25j * hankel1(0, k_ext * distance)
    green_normal = 0.25j * k_ext * hankel1(1, k_ext * distance) * projection
    single_receiver = (green * neumann_total * weights[None, :]).sum(axis=-1)
    double_receiver = (green_normal * dirichlet_total * weights[None, :]).sum(axis=-1)
    scattered = double_receiver - single_receiver
    return (
        np.asarray(scattered, dtype=complex),
        residual,
        float(np.linalg.cond(matrix)),
        num_nodes,
        source_count,
        min_ratio,
        bad_count,
        float(np.max(np.abs(blocks["hyper"]))),
    )


def _run_package_solver(
    name: str,
    solver: object,
    boundary: object,
    sources: np.ndarray,
    receivers: np.ndarray,
    frequency_hz: float,
    case: ProbeCase,
) -> tuple[np.ndarray, float, float, int]:
    exterior, interior = _materials(solver, case.cfg)
    kwargs = {
        "exterior": exterior,
        "interior": interior,
        "eps0": case.cfg.EPS0,
        "mu0": case.cfg.MU0,
    }
    if name == "gpr_bem_mod":
        kwargs.update({"offset_distance": None, "use_strict_quadrature": True, "backend": "numpy"})
    forward = solver.solve_ibim_tmz_total_field_batch(
        boundary,
        sources,
        receivers,
        2.0 * np.pi * frequency_hz,
        1.0,
        **kwargs,
    )
    matrix = np.asarray(forward.system.system_matrix)[0]
    return (
        np.asarray(forward.scattered_receiver, dtype=complex),
        float(forward.linear_system_relative_residual),
        float(np.linalg.cond(matrix)),
        int(forward.system.num_boundary_samples),
    )


def _relative_error(scattered: np.ndarray, reference: np.ndarray) -> float:
    return float(np.linalg.norm(scattered - reference) / np.linalg.norm(reference))


def _run_solve_table(cases: list[ProbeCase], frequencies_hz: np.ndarray, settings: QbxSettings) -> None:
    print("\nForward-solve diagnostic table")
    print("  err columns are relative scattered-field errors vs Mie (circle) or nystrom_ref N=512")
    print("  EXP_BOUNDED_DIAG_QBX replaces only S/D/Kp diagonals; T keeps the old kdiff diagonal")
    print("  EXP_T_OPERATOR_QBX keeps old S/D/Kp diagonals; T is full-row operator-level QBX")
    print("  EXP_ALL_DIAG_FIX combines bounded S/D/Kp QBX diagonals with full-row T-QBX\n")
    for case in cases:
        sources, receivers = _ring_scan(case.center, float(case.cfg.TX_RX_OFFSET))
        reference = case.reference_scattered(frequencies_hz, sources, receivers)
        boundaries = {
            "gpr_bem_mod": case.build_boundary(gpr_bem_mod),
            "gpr_bem_kdiff": case.build_boundary(gpr_bem_kdiff),
            "EXP_BOUNDED_DIAG_QBX": case.build_boundary(gpr_bem_kdiff),
            "EXP_T_OPERATOR_QBX": case.build_boundary(gpr_bem_kdiff),
            "EXP_ALL_DIAG_FIX": case.build_boundary(gpr_bem_kdiff),
        }
        exp_points, exp_normals, exp_weights = kdiff_forward.boundary_points_normals_weights(
            boundaries["EXP_T_OPERATOR_QBX"]
        )
        _, _, exp_radius, _ = _expansion_geometry(exp_points, exp_normals, exp_weights, settings, case.sdf_for_kdiff)
        min_ratio, min_margin, bad_count = _qbx_center_clearance(exp_points, exp_normals, exp_radius)
        print(
            f"{case.name}: full-row QBX nonself clearance min |y-c|/rho={min_ratio:.3f}, "
            f"min margin={min_margin:.3e}, bad nonself pairs={bad_count}"
        )
        rows: dict[str, dict[float, SolverMetric]] = {name: {} for name in SOLVE_NAMES}
        for frequency_hz in frequencies_hz:
            for name in SOLVE_NAMES:
                started = time.perf_counter()
                if name == "EXP_BOUNDED_DIAG_QBX":
                    scattered, residual, condition_number, num_samples = _solve_experiment_variant(
                        boundaries[name],
                        sources,
                        receivers,
                        float(frequency_hz),
                        1.0,
                        case,
                        settings,
                        bounded_diagonal_qbx=True,
                        t_operator_qbx=False,
                    )
                elif name == "EXP_T_OPERATOR_QBX":
                    scattered, residual, condition_number, num_samples = _solve_experiment_variant(
                        boundaries[name],
                        sources,
                        receivers,
                        float(frequency_hz),
                        1.0,
                        case,
                        settings,
                        bounded_diagonal_qbx=False,
                        t_operator_qbx=True,
                    )
                elif name == "EXP_ALL_DIAG_FIX":
                    scattered, residual, condition_number, num_samples = _solve_experiment_variant(
                        boundaries[name],
                        sources,
                        receivers,
                        float(frequency_hz),
                        1.0,
                        case,
                        settings,
                        bounded_diagonal_qbx=True,
                        t_operator_qbx=True,
                    )
                elif name == "gpr_bem_mod":
                    scattered, residual, condition_number, num_samples = _run_package_solver(
                        name, gpr_bem_mod, boundaries[name], sources, receivers, float(frequency_hz), case
                    )
                elif name == "gpr_bem_kdiff":
                    scattered, residual, condition_number, num_samples = _run_package_solver(
                        name, gpr_bem_kdiff, boundaries[name], sources, receivers, float(frequency_hz), case
                    )
                else:
                    raise AssertionError(f"Unhandled diagnostic solver {name!r}.")
                rows[name][float(frequency_hz)] = SolverMetric(
                    error=_relative_error(scattered, reference[float(frequency_hz)]),
                    residual=residual,
                    condition_number=condition_number,
                    elapsed_seconds=time.perf_counter() - started,
                    num_samples=num_samples,
                )

        header = f"{case.name:<8}{'solver':<24}{'N':>5}"
        header += "".join(f"{frequency_hz / 1.0e9:>12.1f}GHz" for frequency_hz in frequencies_hz)
        header += f"{'max resid':>12}{'max cond':>12}{'time [s]':>10}"
        print(header)
        print("-" * len(header))
        for name in SOLVE_NAMES:
            row_metrics = rows[name]
            first_frequency = float(frequencies_hz[0])
            line = f"{case.name:<8}{name:<24}{row_metrics[first_frequency].num_samples:>5}"
            line += "".join(f"{row_metrics[float(frequency_hz)].error:>12.4e}" for frequency_hz in frequencies_hz)
            line += f"{max(metric.residual for metric in row_metrics.values()):>12.1e}"
            line += f"{max(metric.condition_number for metric in row_metrics.values()):>12.2e}"
            line += f"{sum(metric.elapsed_seconds for metric in row_metrics.values()):>10.2f}"
            print(line)
        print()


def _run_ibim_source_t_solve_probe(
    cases: list[ProbeCase],
    frequencies_hz: np.ndarray,
    settings: QbxSettings,
    source_factors: tuple[int, ...],
    *,
    delta_cells: float | None,
    band_cells: float | None,
    strict_weights: bool,
    reproject_targets: bool,
    reproject_sources: bool,
    bounded_diagonal_qbx: bool,
    idw_neighbours: int,
    idw_power: float,
    source_chunk_size: int,
    perfect_prolongation: bool = False,
) -> None:
    print("\nForward solve with compressed IBIM targets and raw SDF-band T-QBX sources")
    print("  S/D/Kp are direct kdiff blocks on the target grid")
    if perfect_prolongation:
        print("  CONDITION B: 'perfect boundary knowledge' -- sources are built exactly on the analytic")
        print("  parameterization (no SDF band/reprojection needed) and the target density is prolonged to")
        print("  sources by periodic cubic-spline interpolation in the analytically recovered curve parameter t")
    else:
        print("  CONDITION A: T is full-row operator-level QBX over raw SDF-band sources, composed with local IDW density prolongation")
    if reproject_targets:
        print("  target points/normals are reprojected to the SDF zero set")
    if reproject_sources and not perfect_prolongation:
        print("  raw source points/normals are reprojected once more to the SDF zero set")
    if bounded_diagonal_qbx:
        print("  S/D/Kp diagonals use bounded QBX self replacements")
    print()

    header = (
        f"{'shape':<8}{'N':>5}{'src x':>7}{'Ms':>7}"
        + "".join(f"{frequency_hz / 1.0e9:>12.1f}GHz" for frequency_hz in frequencies_hz)
        + f"{'clear':>10}{'bad':>7}{'max resid':>12}{'max cond':>12}{'max |T|':>12}{'time [s]':>10}"
    )
    print(header)
    print("-" * len(header))
    for case in cases:
        sources, receivers = _ring_scan(case.center, float(case.cfg.TX_RX_OFFSET))
        reference = case.reference_scattered(frequencies_hz, sources, receivers)
        for factor in source_factors:
            errors = []
            residuals = []
            condition_numbers = []
            source_count = 0
            min_ratio = float("nan")
            bad_count = 0
            max_t = 0.0
            started = time.perf_counter()
            for frequency_hz in frequencies_hz:
                if perfect_prolongation:
                    scattered, residual, condition_number, num_nodes, source_count, min_ratio, bad_count, max_t = (
                        _solve_ibim_perfect_prolongation_t_qbx_variant(
                            case,
                            sources,
                            receivers,
                            float(frequency_hz),
                            settings,
                            factor,
                            reproject_targets=reproject_targets,
                            bounded_diagonal_qbx=bounded_diagonal_qbx,
                            source_chunk_size=source_chunk_size,
                        )
                    )
                else:
                    scattered, residual, condition_number, num_nodes, source_count, min_ratio, bad_count, max_t = (
                        _solve_ibim_source_t_qbx_variant(
                            case,
                            sources,
                            receivers,
                            float(frequency_hz),
                            settings,
                            factor,
                            delta_cells=delta_cells,
                            band_cells=band_cells,
                            strict_weights=strict_weights,
                            reproject_targets=reproject_targets,
                            reproject_sources=reproject_sources,
                            bounded_diagonal_qbx=bounded_diagonal_qbx,
                            idw_neighbours=idw_neighbours,
                            idw_power=idw_power,
                            source_chunk_size=source_chunk_size,
                        )
                    )
                errors.append(_relative_error(scattered, reference[float(frequency_hz)]))
                residuals.append(residual)
                condition_numbers.append(condition_number)
            clearance = f"{min_ratio:.3f}" if bad_count == 0 else f"{min_ratio:.3f}!"
            line = f"{case.name:<8}{num_nodes:>5}{factor:>7}{source_count:>7}"
            line += "".join(f"{error:>12.4e}" for error in errors)
            line += (
                f"{clearance:>10}{bad_count:>7}{max(residuals):>12.1e}"
                f"{max(condition_numbers):>12.2e}{max_t:>12.3e}{time.perf_counter() - started:>10.2f}"
            )
            print(line)
    print()


def _self_records_for_case(
    case: ProbeCase,
    frequencies_hz: np.ndarray,
    rho_factors: tuple[float, ...],
    orders: tuple[int, ...],
    settings: QbxSettings,
) -> list[dict[str, object]]:
    boundary = case.build_boundary(gpr_bem_kdiff)
    points, normals, weights = kdiff_forward.boundary_points_normals_weights(boundary)
    step_scale, curvature_cap, _, curvature = _expansion_geometry(
        points, normals, weights, settings, case.sdf_for_kdiff
    )
    feature_indices = _nearest_feature_indices(case, points)
    records: list[dict[str, object]] = []

    for frequency_hz in frequencies_hz:
        k_ext, k_int = _wavenumbers(case.cfg, float(frequency_hz))
        for node_label, index in feature_indices:
            h_local = float(step_scale[index])
            for rho_factor in rho_factors:
                requested_rho = float(rho_factor * h_local)
                rho = max(min(requested_rho, float(curvature_cap[index])), 1.0e-12)
                for order in orders:
                    try:
                        values = _qbx_self_value(points, normals, weights, index, k_ext, k_int, rho, int(order))
                    except Exception as exc:  # pragma: no cover - diagnostic visibility path.
                        values = {key: complex(np.nan, np.nan) for key in BLOCK_LABELS}
                        error = repr(exc)
                    else:
                        error = ""
                    for block, value in values.items():
                        records.append(
                            {
                                "shape": case.name,
                                "frequency_hz": float(frequency_hz),
                                "node_label": node_label,
                                "node_index": index,
                                "block": BLOCK_LABELS[block],
                                "rho_factor_requested": float(rho_factor),
                                "rho_over_h_effective": float(rho / h_local) if h_local > 0.0 else float("nan"),
                                "rho": float(rho),
                                "h_local": h_local,
                                "curvature": float(curvature[index]),
                                "P": int(order),
                                "value_real": float(np.real(value)),
                                "value_imag": float(np.imag(value)),
                                "finite": bool(np.isfinite(np.real(value)) and np.isfinite(np.imag(value))),
                                "error": error,
                            }
                        )
    return records


def _write_self_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def _point_parameter(case: ProbeCase, point: np.ndarray) -> float:
    rel = point - np.asarray(case.center, dtype=float)
    if case.name == "circle":
        return float(np.arctan2(rel[1], rel[0]))
    if case.name == "ellipse":
        return float(np.arctan2(rel[1] / float(case.cfg.TARGET_SEMI_MINOR), rel[0] / float(case.cfg.TARGET_SEMI_MAJOR)))
    if case.name == "star":
        return float(np.arctan2(rel[1], rel[0]))
    raise ValueError(f"unknown case {case.name!r}")


def _shifted_parameterization(case: ProbeCase, t0: float):
    base = _case_parameterization(case)

    def shifted(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return base(np.asarray(t, dtype=float) + t0)

    return shifted


def _case_parameterization(case: ProbeCase):
    if case.name == "circle":
        return circle_parameterization(case.center, float(case.cfg.TARGET_RADIUS))
    if case.name == "ellipse":
        return ellipse_parameterization(
            case.center, float(case.cfg.TARGET_SEMI_MAJOR), float(case.cfg.TARGET_SEMI_MINOR)
        )
    if case.name == "star":
        return star_parameterization(
            case.center,
            float(case.cfg.TARGET_MEAN_RADIUS),
            float(case.cfg.TARGET_STAR_AMPLITUDE),
            int(case.cfg.TARGET_STAR_LOBES),
        )
    raise ValueError(f"unknown case {case.name!r}")


def _case_sdf_for_sampling(case: ProbeCase) -> Callable[[torch.Tensor], torch.Tensor]:
    if case.name == "circle":
        center = torch.tensor(case.center, dtype=torch.float64)
        radius = float(case.cfg.TARGET_RADIUS)

        def phi(points: torch.Tensor) -> torch.Tensor:
            origin = center.to(device=points.device, dtype=points.dtype)
            return (torch.linalg.norm(points - origin[None, :], dim=1) - radius).reshape(-1, 1)

        return phi
    if case.sdf_for_kdiff is None:
        raise ValueError(f"no SDF available for {case.name!r}")
    return case.sdf_for_kdiff


def _scaled_grid_shape(grid_shape: tuple[int, int], factor: int) -> tuple[int, int]:
    if factor < 1:
        raise ValueError("grid factor must be positive")
    return (int(factor) * (int(grid_shape[0]) - 1) + 1, int(factor) * (int(grid_shape[1]) - 1) + 1)


def _ibim_raw_source_samples(
    case: ProbeCase,
    grid_factor: int,
    *,
    delta_cells: float | None,
    band_cells: float | None,
    strict_weights: bool,
    reproject_sources: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, float, float]:
    grid_shape = _scaled_grid_shape(GRID, grid_factor)
    dummy_grid_x, dummy_grid_y, dummy_points, spacing, dummy_area = gpr_bem_kdiff.cartesian_grid_points(
        case.bounds, grid_shape=grid_shape, dtype=torch.float64
    )
    del dummy_grid_x, dummy_grid_y, dummy_points, dummy_area
    max_spacing = max(spacing)
    delta_half_width = None if delta_cells is None else float(delta_cells) * max_spacing
    band_half_width = None if band_cells is None else float(band_cells) * max_spacing
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = gpr_bem_kdiff.build_implicit_boundary_band(
            _case_sdf_for_sampling(case),
            case.bounds,
            grid_shape=grid_shape,
            band_half_width=band_half_width,
            delta_half_width=delta_half_width,
            dtype=torch.float64,
        )
    weights_tensor = band.strict_quadrature_weights if strict_weights else band.quadrature_weights
    points = band.projected_points.detach().cpu().numpy().astype(float)
    normals = band.normals.detach().cpu().numpy().astype(float)
    weights = weights_tensor.detach().cpu().numpy().reshape(-1).astype(float)
    if reproject_sources:
        points, normals = _reproject_points_and_normals(case, points)
    return points, normals, weights, band.num_samples, float(band.delta_half_width), float(band.boundary_measure(strict=strict_weights))


def _reproject_points_and_normals(
    case: ProbeCase,
    points: np.ndarray,
    *,
    level: float = 0.0,
    gradient_epsilon: float = 1.0e-8,
) -> tuple[np.ndarray, np.ndarray]:
    tensor_points = torch.tensor(points, dtype=torch.float64, requires_grad=True)
    sdf_values = _case_sdf_for_sampling(case)(tensor_points).reshape(-1, 1)
    gradients = torch.autograd.grad(
        outputs=sdf_values,
        inputs=tensor_points,
        grad_outputs=torch.ones_like(sdf_values),
        create_graph=False,
        retain_graph=False,
        only_inputs=True,
    )[0]
    projected = gpr_bem_kdiff.project_points_to_level_set(
        tensor_points,
        sdf_values,
        gradients,
        level=level,
        epsilon=gradient_epsilon,
    )
    normals = gradients / torch.linalg.norm(gradients, dim=1, keepdim=True).clamp_min(float(gradient_epsilon))
    return (
        projected.detach().cpu().numpy().astype(float),
        normals.detach().cpu().numpy().astype(float),
    )


def _reference_pointwise_bounded_diagonal(
    case: ProbeCase, point: np.ndarray, frequency_hz: float
) -> dict[str, complex]:
    t0 = _point_parameter(case, point)
    curve = build_curve(_shifted_parameterization(case, t0), NYSTROM_N, f"{case.name}_local")
    k_ext, k_int = _wavenumbers(case.cfg, frequency_hz)
    _, second = nystrom_tmz._diagonal_limits(curve, k_ext, k_int, epsilon=1.0e-3)
    return {key: complex(second[key][0] / curve.speeds[0]) for key in BOUNDED_BLOCKS}


def _run_bounded_diagonal_compare(
    cases: list[ProbeCase], frequencies_hz: np.ndarray, settings: QbxSettings
) -> None:
    print("\nBounded diagonal comparison against parameterized nystrom_ref")
    print("  Entries are unweighted pointwise finite limits: matrix_diagonal / local_weight")
    print("  T_diff is intentionally omitted because it has no finite pointwise diagonal\n")

    header = (
        f"{'shape':<8}{'GHz':>6} {'node':<14}{'idx':>5} {'block':<8}"
        f"{'|ref|':>12}{'abs osc-ref':>14}{'abs qbx-ref':>14}{'rel osc':>12}{'rel qbx':>12}"
    )
    print(header)
    print("-" * len(header))

    for case in cases:
        boundary = case.build_boundary(gpr_bem_kdiff)
        points, normals, weights = kdiff_forward.boundary_points_normals_weights(boundary)
        _, _, expansion_radius, _ = _expansion_geometry(points, normals, weights, settings, case.sdf_for_kdiff)
        feature_indices = _nearest_feature_indices(case, points)
        for frequency_hz in frequencies_hz:
            k_ext, k_int = _wavenumbers(case.cfg, float(frequency_hz))
            old_diagonal = kdiff_forward._diagonal_terms(points, normals, weights, k_ext, k_int, sdf_fn=case.sdf_for_kdiff)
            for node_label, index in feature_indices:
                ref = _reference_pointwise_bounded_diagonal(case, points[index], float(frequency_hz))
                qbx = _qbx_self_value(
                    points,
                    normals,
                    weights,
                    index,
                    k_ext,
                    k_int,
                    float(expansion_radius[index]),
                    settings.expansion_order,
                )
                for block in BOUNDED_BLOCKS:
                    ref_value = ref[block]
                    osc_value = complex(old_diagonal[block][index] / weights[index])
                    qbx_value = complex(qbx[block] / weights[index])
                    abs_osc = abs(osc_value - ref_value)
                    abs_qbx = abs(qbx_value - ref_value)
                    ref_norm = abs(ref_value)
                    rel_osc = abs_osc / ref_norm if ref_norm > 1.0e-14 else float("nan")
                    rel_qbx = abs_qbx / ref_norm if ref_norm > 1.0e-14 else float("nan")
                    print(
                        f"{case.name:<8}{frequency_hz / 1.0e9:>6.1f} {node_label:<14}{index:>5} {BLOCK_LABELS[block]:<8}"
                        f"{ref_norm:>12.3e}{abs_osc:>14.3e}{abs_qbx:>14.3e}{rel_osc:>12.3e}{rel_qbx:>12.3e}"
                    )
    print()


def _direct_kdiff_t_matrix(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    k_ext: complex,
    k_int: complex,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
) -> np.ndarray:
    num_nodes = points.shape[0]
    geometry = kdiff_forward._pair_geometry(points, normals, points, normals, outer=True)
    safe_r = np.where(np.eye(num_nodes, dtype=bool), 1.0, geometry[0])
    kernels, _ = kdiff_forward._difference_kernels(safe_r, *geometry[1:], k_ext, k_int)
    old_diagonal = kdiff_forward._diagonal_terms(points, normals, weights, k_ext, k_int, sdf_fn=sdf_fn)
    matrix = kernels["hyper"] * weights[None, :]
    np.fill_diagonal(matrix, old_diagonal["hyper"])
    return matrix


def _test_densities(t: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "const": np.ones_like(t, dtype=complex),
        "cos1": np.cos(t).astype(complex),
        "sin1": np.sin(t).astype(complex),
        "cos2": np.cos(2.0 * t).astype(complex),
        "sin2": np.sin(2.0 * t).astype(complex),
    }


def _point_parameters(case: ProbeCase, points: np.ndarray) -> np.ndarray:
    return np.asarray([_point_parameter(case, point) for point in np.asarray(points, dtype=float)], dtype=float)


def _density_matrix_from_parameters(t: np.ndarray) -> tuple[list[str], np.ndarray]:
    densities = _test_densities(np.asarray(t, dtype=float))
    names = list(densities)
    return names, np.column_stack([densities[name] for name in names])


def _periodic_fourier_eval(values: np.ndarray, t_eval: np.ndarray) -> np.ndarray:
    samples = np.asarray(values, dtype=complex)
    num_samples = samples.shape[0]
    modes = np.fft.fftfreq(num_samples, d=1.0 / num_samples)
    coefficients = np.fft.fft(samples, axis=0) / num_samples
    phase = np.exp(1j * np.mod(t_eval, TWO_PI)[:, None] * modes[None, :])
    return phase @ coefficients


def _reference_hyper_actions_at_points(
    case: ProbeCase,
    target_points: np.ndarray,
    frequency_hz: float,
    reference_nodes: int,
) -> tuple[list[str], np.ndarray]:
    curve = build_curve(_case_parameterization(case), reference_nodes, f"{case.name}_reference")
    k_ext, k_int = _wavenumbers(case.cfg, float(frequency_hz))
    reference = nystrom_tmz._operator_matrices(curve, k_ext, k_int, epsilon=1.0e-3)["hyper"]
    names, density_matrix = _density_matrix_from_parameters(curve.t)
    uniform_actions = reference @ density_matrix
    target_t = _point_parameters(case, target_points)
    return names, _periodic_fourier_eval(uniform_actions, target_t)


def _idw_prolong_density_matrix(
    target_points: np.ndarray,
    target_density_matrix: np.ndarray,
    source_points: np.ndarray,
    *,
    neighbours: int,
    power: float,
) -> np.ndarray:
    return _idw_prolongation_matrix(
        target_points,
        source_points,
        neighbours=neighbours,
        power=power,
    ) @ target_density_matrix


def _idw_prolongation_matrix(
    target_points: np.ndarray,
    source_points: np.ndarray,
    *,
    neighbours: int,
    power: float,
) -> np.ndarray:
    num_targets = int(target_points.shape[0])
    k = max(1, min(int(neighbours), num_targets))
    distances, indices = cKDTree(target_points).query(source_points, k=k)
    distances = np.asarray(distances, dtype=float)
    indices = np.asarray(indices, dtype=int)
    if k == 1:
        distances = distances[:, None]
        indices = indices[:, None]

    exact = distances <= 1.0e-13
    weights = np.zeros_like(distances)
    exact_rows = np.any(exact, axis=1)
    if np.any(exact_rows):
        first_exact = np.argmax(exact[exact_rows], axis=1)
        weights[exact_rows, first_exact] = 1.0
    if np.any(~exact_rows):
        safe_distances = np.maximum(distances[~exact_rows], 1.0e-13)
        local = safe_distances ** (-float(power))
        weights[~exact_rows] = local / local.sum(axis=1, keepdims=True)

    prolongation = np.zeros((source_points.shape[0], target_points.shape[0]), dtype=complex)
    rows = np.repeat(np.arange(source_points.shape[0])[:, None], k, axis=1)
    np.add.at(prolongation, (rows.reshape(-1), indices.reshape(-1)), weights.reshape(-1))
    return prolongation


def _periodic_spline_prolongation_matrix(target_t: np.ndarray, source_t: np.ndarray) -> np.ndarray:
    """Linear prolongation from ``target_t``-ordered samples to ``source_t``.

    Builds a periodic cubic spline through the (sorted) target parameter
    values and evaluates it at the source parameter values.  Because cubic
    spline interpolation is linear in the sample values for fixed knot/query
    locations, the whole map can be produced as one matrix by handing
    ``CubicSpline`` a batch of one-hot "density" columns (one per target
    node) instead of looping over columns by hand.
    """

    target_t = np.asarray(target_t, dtype=float)
    source_t = np.asarray(source_t, dtype=float)
    num_target = int(target_t.shape[0])

    order = np.argsort(target_t)
    t_sorted = target_t[order].copy()
    # Guard against coincident/near-coincident parameter values, which would
    # violate CubicSpline's strict monotonicity requirement.  Real boundary
    # samples should not collide, but nudge defensively rather than crash.
    eps = 1.0e-12
    for i in range(1, num_target):
        if t_sorted[i] <= t_sorted[i - 1]:
            t_sorted[i] = t_sorted[i - 1] + eps

    one_hot_sorted = np.zeros((num_target, num_target), dtype=float)
    one_hot_sorted[np.arange(num_target), order] = 1.0

    t_ext = np.concatenate([t_sorted, [t_sorted[0] + TWO_PI]])
    y_ext = np.concatenate([one_hot_sorted, one_hot_sorted[0:1, :]], axis=0)
    spline = CubicSpline(t_ext, y_ext, axis=0, bc_type="periodic")

    source_wrapped = t_sorted[0] + np.mod(source_t - t_sorted[0], TWO_PI)
    return np.asarray(spline(source_wrapped), dtype=float)


def _analytic_oversampled_source_samples(
    case: ProbeCase,
    source_factor: int,
    num_target: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """Exact-by-construction oversampled sources from the analytic parameterization.

    Uniform in the curve parameter ``t`` (matching ``build_curve``'s
    convention), at ``source_factor * num_target`` nodes.  Points/normals sit
    exactly on the analytic curve, so no SDF reprojection is needed or
    possible to improve upon.
    """

    source_count = int(source_factor) * int(num_target)
    if source_count % 2 != 0:
        source_count += 1
    source_curve = build_curve(_case_parameterization(case), source_count, f"{case.name}_analytic_source")
    source_weights = source_curve.speeds * (TWO_PI / source_curve.num_nodes)
    return (
        source_curve.points,
        source_curve.normals,
        source_weights,
        source_curve.t,
        source_curve.num_nodes,
    )


def _operator_action_error(candidate: np.ndarray, reference: np.ndarray, density: np.ndarray) -> float:
    exact = reference @ density
    got = candidate @ density
    return float(np.linalg.norm(got - exact) / max(np.linalg.norm(exact), 1.0e-300))


def _qbx_operator_t_action(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    source_density: np.ndarray,
    k_ext: complex,
    k_int: complex,
    expansion_radius: np.ndarray,
    order: int,
) -> np.ndarray:
    action = np.empty(target_points.shape[0], dtype=complex)
    weighted_density = source_weights * source_density
    for index in range(target_points.shape[0]):
        row = _qbx_diff_row(
            target_points[index],
            target_normals[index],
            source_points,
            source_normals,
            k_ext,
            k_int,
            float(expansion_radius[index]),
            order,
        )
        action[index] = np.dot(row["hyper"], weighted_density)
    return action


def _qbx_operator_t_rect_matrix(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    k_ext: complex,
    k_int: complex,
    expansion_radius: np.ndarray,
    order: int,
) -> np.ndarray:
    matrix = np.empty((target_points.shape[0], source_points.shape[0]), dtype=complex)
    for index in range(target_points.shape[0]):
        row = _qbx_diff_row(
            target_points[index],
            target_normals[index],
            source_points,
            source_normals,
            k_ext,
            k_int,
            float(expansion_radius[index]),
            order,
        )
        matrix[index, :] = row["hyper"] * source_weights
    return matrix


def _qbx_side_hyper_rect_matrix(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    k: complex,
    expansion_radius: np.ndarray,
    side: float,
    order: int,
) -> np.ndarray:
    centers = target_points + side * expansion_radius[:, None] * target_normals
    disp = source_points[None, :, :] - centers[:, None, :]
    rho = np.linalg.norm(disp, axis=2)
    theta = np.arctan2(disp[:, :, 1], disp[:, :, 0])

    orders = np.arange(-order, order + 1, dtype=float)
    n_col = orders[:, None, None]
    z = k * rho[None, :, :]
    exp_y = np.exp(-1j * n_col * theta[None, :, :])
    hankel_n = hankel1(n_col, z)
    hankel_deriv = 0.5 * (hankel1(n_col - 1.0, z) - hankel1(n_col + 1.0, z))
    psi = hankel_n * exp_y

    rho_hat = np.stack((np.cos(theta), np.sin(theta)), axis=2)
    theta_hat = np.stack((-np.sin(theta), np.cos(theta)), axis=2)
    dpsi_drho = k * hankel_deriv * exp_y
    dpsi_dtheta_over_rho = (-1j * n_col / rho[None, :, :]) * psi
    grad_y = (
        dpsi_drho[:, :, :, None] * rho_hat[None, :, :, :]
        + dpsi_dtheta_over_rho[:, :, :, None] * theta_hat[None, :, :, :]
    )
    dpsi_dny = np.einsum("ltmd,md->ltm", grad_y, source_normals)

    theta_x = np.arctan2(-side * target_normals[:, 1], -side * target_normals[:, 0])
    rho_x = expansion_radius
    zx = k * rho_x
    bessel_n = jv(orders[:, None], zx[None, :])
    bessel_deriv = 0.5 * (jv(orders[:, None] - 1.0, zx[None, :]) - jv(orders[:, None] + 1.0, zx[None, :]))
    exp_x = np.exp(1j * orders[:, None] * theta_x[None, :])
    phi_x = bessel_n * exp_x
    dphi_x_drho = k * bessel_deriv * exp_x
    dphi_x_dtheta_over_rho = (1j * orders[:, None] / rho_x[None, :]) * phi_x
    rho_hat_x = np.stack((np.cos(theta_x), np.sin(theta_x)), axis=1)
    theta_hat_x = np.stack((-np.sin(theta_x), np.cos(theta_x)), axis=1)
    grad_x = (
        dphi_x_drho[:, :, None] * rho_hat_x[None, :, :]
        + dphi_x_dtheta_over_rho[:, :, None] * theta_hat_x[None, :, :]
    )
    dphi_x_dnx = np.einsum("ltd,td->lt", grad_x, target_normals)

    hyper = 0.25j * np.einsum("lt,ltm->tm", dphi_x_dnx, dpsi_dny)
    return hyper * source_weights[None, :]


def _qbx_operator_t_rect_matrix_fast(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    k_ext: complex,
    k_int: complex,
    expansion_radius: np.ndarray,
    order: int,
) -> np.ndarray:
    ext_plus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights, k_ext, expansion_radius, +1.0, order
    )
    ext_minus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights, k_ext, expansion_radius, -1.0, order
    )
    int_plus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights, k_int, expansion_radius, +1.0, order
    )
    int_minus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights, k_int, expansion_radius, -1.0, order
    )
    return 0.5 * (ext_plus + ext_minus - int_plus - int_minus)


def _qbx_operator_t_rect_actions_fast_chunked(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    source_density_matrix: np.ndarray,
    k_ext: complex,
    k_int: complex,
    expansion_radius: np.ndarray,
    order: int,
    source_chunk_size: int,
) -> np.ndarray:
    density_matrix = np.asarray(source_density_matrix, dtype=complex)
    if density_matrix.ndim == 1:
        density_matrix = density_matrix[:, None]
    action = np.zeros((target_points.shape[0], density_matrix.shape[1]), dtype=complex)
    chunk_size = max(1, int(source_chunk_size))
    for start in range(0, source_points.shape[0], chunk_size):
        stop = min(start + chunk_size, source_points.shape[0])
        matrix = _qbx_operator_t_rect_matrix_fast(
            target_points,
            target_normals,
            source_points[start:stop],
            source_normals[start:stop],
            source_weights[start:stop],
            k_ext,
            k_int,
            expansion_radius,
            order,
        )
        action += matrix @ density_matrix[start:stop]
    return action


def _qbx_operator_t_matrix_with_source_prolongation(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    source_prolongation: np.ndarray,
    k_ext: complex,
    k_int: complex,
    expansion_radius: np.ndarray,
    order: int,
    source_chunk_size: int,
) -> np.ndarray:
    matrix = np.zeros((target_points.shape[0], target_points.shape[0]), dtype=complex)
    chunk_size = max(1, int(source_chunk_size))
    for start in range(0, source_points.shape[0], chunk_size):
        stop = min(start + chunk_size, source_points.shape[0])
        rect = _qbx_operator_t_rect_matrix_fast(
            target_points,
            target_normals,
            source_points[start:stop],
            source_normals[start:stop],
            source_weights[start:stop],
            k_ext,
            k_int,
            expansion_radius,
            order,
        )
        matrix += rect @ source_prolongation[start:stop, :]
    return matrix


def _run_t_action_probe(
    cases: list[ProbeCase],
    frequencies_hz: np.ndarray,
    settings: QbxSettings,
    oversampling_factors: tuple[int, ...],
) -> None:
    print("\nT operator-action probe on parameterized same-N curves")
    print("  Reference is nystrom_ref Kress/Kussmaul-Martensen T_diff at the same nominal N")
    print("  Errors are max relative action errors over const, cos/sin(t), cos/sin(2t)\n")

    header = (
        f"{'shape':<8}{'GHz':>6}{'N':>5}{'src x':>7}"
        f"{'clearance':>12}{'old T max':>13}{'T-QBX max':>13}{'worst T-QBX density':>22}"
    )
    print(header)
    print("-" * len(header))
    for case in cases:
        curve = build_curve(_case_parameterization(case), NOMINAL_N[case.name], case.name)
        weights = curve.speeds * (TWO_PI / curve.num_nodes)
        _, _, expansion_radius, _ = _expansion_geometry(curve.points, curve.normals, weights, settings, None)
        densities = _test_densities(curve.t)
        for frequency_hz in frequencies_hz:
            k_ext, k_int = _wavenumbers(case.cfg, float(frequency_hz))
            reference = nystrom_tmz._operator_matrices(curve, k_ext, k_int, epsilon=1.0e-3)["hyper"]
            old_t = _direct_kdiff_t_matrix(curve.points, curve.normals, weights, k_ext, k_int)
            old_errors = {
                name: _operator_action_error(old_t, reference, density)
                for name, density in densities.items()
            }
            for factor in oversampling_factors:
                source_curve = (
                    curve
                    if factor == 1
                    else build_curve(_case_parameterization(case), factor * NOMINAL_N[case.name], case.name)
                )
                source_weights = source_curve.speeds * (TWO_PI / source_curve.num_nodes)
                source_self = np.arange(curve.num_nodes) * factor
                min_ratio, _, bad_count = _qbx_target_source_clearance(
                    curve.points,
                    curve.normals,
                    source_curve.points,
                    expansion_radius,
                    source_self,
                )
                qbx_matrix = _qbx_operator_t_rect_matrix_fast(
                    curve.points,
                    curve.normals,
                    source_curve.points,
                    source_curve.normals,
                    source_weights,
                    k_ext,
                    k_int,
                    expansion_radius,
                    settings.expansion_order,
                )
                qbx_errors = {}
                for name, density in densities.items():
                    source_density = _test_densities(source_curve.t)[name]
                    got = qbx_matrix @ source_density
                    exact = reference @ density
                    qbx_errors[name] = float(np.linalg.norm(got - exact) / max(np.linalg.norm(exact), 1.0e-300))
                worst_name = max(qbx_errors, key=qbx_errors.get)
                clearance = f"{min_ratio:.3f}" if bad_count == 0 else f"{min_ratio:.3f}!"
                old_text = f"{max(old_errors.values()):.3e}" if factor == 1 else "n/a"
                print(
                    f"{case.name:<8}{frequency_hz / 1.0e9:>6.1f}{curve.num_nodes:>5}{factor:>7}"
                    f"{clearance:>12}{old_text:>13}"
                    f"{max(qbx_errors.values()):>13.3e}{worst_name:>22}"
                )
    print()


def _max_named_relative_error(candidate: np.ndarray, reference: np.ndarray, names: list[str]) -> tuple[float, str]:
    errors = np.linalg.norm(candidate - reference, axis=0) / np.maximum(np.linalg.norm(reference, axis=0), 1.0e-300)
    worst = int(np.argmax(errors))
    return float(errors[worst]), names[worst]


def _run_ibim_source_t_action_probe(
    cases: list[ProbeCase],
    frequencies_hz: np.ndarray,
    settings: QbxSettings,
    source_factors: tuple[int, ...],
    *,
    reference_nodes: int,
    delta_cells: float | None,
    band_cells: float | None,
    strict_weights: bool,
    reproject_targets: bool,
    reproject_sources: bool,
    idw_neighbours: int,
    idw_power: float,
    source_chunk_size: int,
) -> None:
    print("\nT operator-action probe with compressed IBIM targets and raw SDF-band sources")
    print("  Reference is nystrom_ref T_diff on the analytic curve, Fourier-evaluated at target parameters")
    print("  qbx analytic uses exact smooth test densities at raw source points")
    print("  qbx IDW prolongs the same target-grid densities to raw source points by local inverse-distance weights\n")
    if reproject_targets:
        print("  target points/normals are reprojected to the SDF zero set before this diagnostic\n")
    if reproject_sources:
        print("  raw source points/normals are reprojected once more to the SDF zero set before this diagnostic\n")

    header = (
        f"{'shape':<8}{'GHz':>6}{'Nt':>5}{'src x':>7}{'Ms':>7}"
        f"{'measure':>11}{'clear':>10}{'bad':>7}{'|phi_t|max':>12}"
        f"{'old T':>12}{'qbx analytic':>14}{'qbx IDW':>12}{'worst':>11}{'time [s]':>10}"
    )
    print(header)
    print("-" * len(header))
    for case in cases:
        boundary = case.build_boundary(gpr_bem_kdiff)
        target_points, target_normals, target_weights = kdiff_forward.boundary_points_normals_weights(boundary)
        if reproject_targets:
            target_points, target_normals = _reproject_points_and_normals(case, target_points)
        _, _, expansion_radius, _ = _expansion_geometry(
            target_points,
            target_normals,
            target_weights,
            settings,
            case.sdf_for_kdiff,
        )
        target_t = _point_parameters(case, target_points)
        names, target_density = _density_matrix_from_parameters(target_t)
        phi_target = _case_sdf_for_sampling(case)(
            torch.tensor(target_points, dtype=torch.float64)
        ).detach().cpu().numpy().reshape(-1)
        target_phi_max = float(np.max(np.abs(phi_target)))

        source_cache = {
            factor: _ibim_raw_source_samples(
                case,
                factor,
                delta_cells=delta_cells,
                band_cells=band_cells,
                strict_weights=strict_weights,
                reproject_sources=reproject_sources,
            )
            for factor in source_factors
        }
        for frequency_hz in frequencies_hz:
            k_ext, k_int = _wavenumbers(case.cfg, float(frequency_hz))
            reference_names, reference_actions = _reference_hyper_actions_at_points(
                case,
                target_points,
                float(frequency_hz),
                reference_nodes,
            )
            if reference_names != names:
                raise RuntimeError("density ordering mismatch")
            old_t = _direct_kdiff_t_matrix(
                target_points,
                target_normals,
                target_weights,
                k_ext,
                k_int,
                sdf_fn=case.sdf_for_kdiff,
            )
            old_error, _old_worst = _max_named_relative_error(old_t @ target_density, reference_actions, names)
            for factor in source_factors:
                started = time.perf_counter()
                (
                    source_points,
                    source_normals,
                    source_weights,
                    source_count,
                    _delta_half_width,
                    source_measure,
                ) = source_cache[factor]
                min_ratio, _min_margin, bad_count = _qbx_target_source_clearance(
                    target_points,
                    target_normals,
                    source_points,
                    expansion_radius,
                    None,
                )
                source_t = _point_parameters(case, source_points)
                _source_names, source_density_analytic = _density_matrix_from_parameters(source_t)
                source_density_idw = _idw_prolong_density_matrix(
                    target_points,
                    target_density,
                    source_points,
                    neighbours=idw_neighbours,
                    power=idw_power,
                )
                combined_density = np.concatenate([source_density_analytic, source_density_idw], axis=1)
                qbx_actions = _qbx_operator_t_rect_actions_fast_chunked(
                    target_points,
                    target_normals,
                    source_points,
                    source_normals,
                    source_weights,
                    combined_density,
                    k_ext,
                    k_int,
                    expansion_radius,
                    settings.expansion_order,
                    source_chunk_size,
                )
                analytic_actions = qbx_actions[:, : len(names)]
                idw_actions = qbx_actions[:, len(names) :]
                analytic_error, analytic_worst = _max_named_relative_error(analytic_actions, reference_actions, names)
                idw_error, idw_worst = _max_named_relative_error(idw_actions, reference_actions, names)
                clearance = f"{min_ratio:.3f}" if bad_count == 0 else f"{min_ratio:.3f}!"
                worst = f"{analytic_worst}/{idw_worst}"
                print(
                    f"{case.name:<8}{frequency_hz / 1.0e9:>6.1f}{target_points.shape[0]:>5}{factor:>7}"
                    f"{source_count:>7}{source_measure:>11.4e}{clearance:>10}{bad_count:>7}"
                    f"{target_phi_max:>12.2e}{old_error:>12.3e}{analytic_error:>14.3e}"
                    f"{idw_error:>12.3e}{worst:>11}{time.perf_counter() - started:>10.2f}"
                )
    print()


def _fourier_resampling_matrix(num_target: int, factor: int) -> np.ndarray:
    if factor < 1:
        raise ValueError("oversampling factor must be positive")
    if factor == 1:
        return np.eye(num_target, dtype=complex)
    identity = np.eye(num_target, dtype=complex)
    return np.asarray(resample(identity, factor * num_target, axis=0), dtype=complex)


def _parameterized_t_qbx_solution(
    case: ProbeCase,
    frequency_hz: float,
    sources: np.ndarray,
    receivers: np.ndarray,
    settings: QbxSettings,
    source_oversampling: int,
) -> tuple[np.ndarray, float, float]:
    curve = build_curve(_case_parameterization(case), NOMINAL_N[case.name], case.name)
    source_curve = (
        curve
        if source_oversampling == 1
        else build_curve(_case_parameterization(case), source_oversampling * NOMINAL_N[case.name], case.name)
    )
    k_ext, k_int = _wavenumbers(case.cfg, frequency_hz)
    blocks = nystrom_tmz._operator_matrices(curve, k_ext, k_int, epsilon=1.0e-3)

    target_weights = curve.speeds * (TWO_PI / curve.num_nodes)
    source_weights = source_curve.speeds * (TWO_PI / source_curve.num_nodes)
    _, _, expansion_radius, _ = _expansion_geometry(curve.points, curve.normals, target_weights, settings, None)
    t_rect = _qbx_operator_t_rect_matrix_fast(
        curve.points,
        curve.normals,
        source_curve.points,
        source_curve.normals,
        source_weights,
        k_ext,
        k_int,
        expansion_radius,
        settings.expansion_order,
    )
    prolongation = _fourier_resampling_matrix(curve.num_nodes, source_oversampling)
    t_qbx = t_rect @ prolongation

    identity = np.eye(curve.num_nodes, dtype=complex)
    system = np.block(
        [
            [identity - blocks["double"], blocks["single"]],
            [-t_qbx, identity + blocks["adjoint"]],
        ]
    )
    rhs = np.empty((2 * curve.num_nodes, sources.shape[0]), dtype=complex)
    for column, source in enumerate(sources):
        trace, normal_trace = nystrom_tmz._incident_traces(curve.points, curve.normals, source, k_ext, 1.0)
        rhs[: curve.num_nodes, column] = trace
        rhs[curve.num_nodes :, column] = normal_trace

    solution = np.linalg.solve(system, rhs)
    residual = float(np.linalg.norm(system @ solution - rhs) / np.linalg.norm(rhs))
    scattered = np.empty((sources.shape[0], receivers.shape[0]), dtype=complex)
    for column in range(sources.shape[0]):
        scattered[column] = nystrom_tmz._exterior_representation(
            receivers,
            curve,
            solution[: curve.num_nodes, column],
            solution[curve.num_nodes :, column],
            k_ext,
        )
    return np.diag(scattered), residual, float(np.linalg.cond(system))


def _run_parameterized_t_solve(
    cases: list[ProbeCase],
    frequencies_hz: np.ndarray,
    settings: QbxSettings,
    source_oversampling: int,
) -> None:
    print("\nParameterized solve with oversampled T-QBX")
    print("  S/D/Kp come from nystrom_ref at nominal N; only T is replaced by operator-level QBX")
    print("  Oversampled source densities use global Fourier interpolation, so this is diagnostic-only\n")

    header = (
        f"{'shape':<8}{'N':>5}{'src x':>7}"
        + "".join(f"{frequency_hz / 1.0e9:>12.1f}GHz" for frequency_hz in frequencies_hz)
        + f"{'max resid':>12}{'max cond':>12}{'time [s]':>10}"
    )
    print(header)
    print("-" * len(header))
    for case in cases:
        sources, receivers = _ring_scan(case.center, float(case.cfg.TX_RX_OFFSET))
        reference = case.reference_scattered(frequencies_hz, sources, receivers)
        errors = []
        residuals = []
        condition_numbers = []
        started = time.perf_counter()
        for frequency_hz in frequencies_hz:
            scattered, residual, condition_number = _parameterized_t_qbx_solution(
                case,
                float(frequency_hz),
                sources,
                receivers,
                settings,
                source_oversampling,
            )
            errors.append(_relative_error(scattered, reference[float(frequency_hz)]))
            residuals.append(residual)
            condition_numbers.append(condition_number)
        line = f"{case.name:<8}{NOMINAL_N[case.name]:>5}{source_oversampling:>7}"
        line += "".join(f"{error:>12.4e}" for error in errors)
        line += f"{max(residuals):>12.1e}{max(condition_numbers):>12.2e}{time.perf_counter() - started:>10.2f}"
        print(line)
    print()


def _complex_from_record(record: dict[str, object]) -> complex:
    return complex(float(record["value_real"]), float(record["value_imag"]))


def _format_complex(value: complex) -> str:
    return f"{value.real:+.3e}{value.imag:+.3e}j"


def _span(values: list[complex]) -> tuple[float, float]:
    finite = np.asarray([value for value in values if np.isfinite(value.real) and np.isfinite(value.imag)])
    if finite.size == 0:
        return float("nan"), float("nan")
    center = finite.mean()
    absolute = float(np.max(np.abs(finite - center)))
    relative = float(absolute / max(abs(center), 1.0e-300))
    return absolute, relative


def _print_self_summary(records: list[dict[str, object]], orders: tuple[int, ...]) -> None:
    if not records:
        return
    print("\nQBX one-source self-series summary")
    print("  Values are weighted matrix contributions w_i * QBX_self_kernel_limit")
    print("  Detailed P/rho records are written to the CSV path shown after this table\n")
    tail_orders = tuple(order for order in orders if order >= 20) or orders[-min(3, len(orders)) :]
    group_keys = []
    for record in records:
        key = (
            str(record["shape"]),
            float(record["frequency_hz"]),
            str(record["node_label"]),
            int(record["node_index"]),
            str(record["block"]),
        )
        if key not in group_keys:
            group_keys.append(key)

    header = (
        f"{'shape':<8}{'GHz':>6} {'node':<14}{'idx':>5} {'block':<8}"
        f"{'tail abs span':>15}{'tail rel span':>15}{'Pmax/rho=0.5h':>28}{'plateau?':>10}"
    )
    print(header)
    print("-" * len(header))
    for shape, frequency_hz, node_label, node_index, block in group_keys:
        tail_values = [
            _complex_from_record(record)
            for record in records
            if str(record["shape"]) == shape
            and float(record["frequency_hz"]) == frequency_hz
            and str(record["node_label"]) == node_label
            and int(record["node_index"]) == node_index
            and str(record["block"]) == block
            and int(record["P"]) in tail_orders
        ]
        abs_span, rel_span = _span(tail_values)
        pmax = max(int(record["P"]) for record in records if str(record["block"]) == block)
        representative = [
            record
            for record in records
            if str(record["shape"]) == shape
            and float(record["frequency_hz"]) == frequency_hz
            and str(record["node_label"]) == node_label
            and int(record["node_index"]) == node_index
            and str(record["block"]) == block
            and int(record["P"]) == pmax
            and math.isclose(float(record["rho_factor_requested"]), 0.5)
        ]
        value_text = _format_complex(_complex_from_record(representative[0])) if representative else "n/a"
        plateau = "skip" if block == "T_diff" else ("yes" if abs_span <= 1.0e-10 + 1.0e-6 * max(abs(value) for value in tail_values or [0.0]) else "no")
        print(
            f"{shape:<8}{frequency_hz / 1.0e9:>6.1f} {node_label:<14}{node_index:>5} {block:<8}"
            f"{abs_span:>15.3e}{rel_span:>15.3e}{value_text:>28}{plateau:>10}"
        )
    print()


def _run_self_probe(
    cases: list[ProbeCase],
    frequencies_hz: np.ndarray,
    rho_factors: tuple[float, ...],
    orders: tuple[int, ...],
    settings: QbxSettings,
    csv_path: Path,
) -> None:
    records: list[dict[str, object]] = []
    for case in cases:
        records.extend(_self_records_for_case(case, frequencies_hz, rho_factors, orders, settings))
    _write_self_csv(csv_path, records)
    _print_self_summary(records, orders)
    print(f"Self-series CSV: {csv_path}")


def _parse_float_tuple(values: list[float] | None, default: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(default if not values else values)


def _parse_int_tuple(values: list[int] | None, default: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(default if not values else values)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shapes", nargs="*", choices=("circle", "ellipse", "star"), default=["circle", "ellipse", "star"])
    parser.add_argument("--frequencies-ghz", nargs="*", type=float, default=list(DEFAULT_FREQUENCIES_GHZ))
    parser.add_argument("--rho-factors", nargs="*", type=float, default=list(DEFAULT_RHO_FACTORS))
    parser.add_argument("--orders", nargs="*", type=int, default=list(DEFAULT_ORDERS))
    parser.add_argument("--qbx-order", type=int, default=20, help="Expansion order for EXP_BOUNDED_DIAG_QBX solves.")
    parser.add_argument("--radius-spacing-factor", type=float, default=0.5)
    parser.add_argument("--radius-curvature-factor", type=float, default=0.2)
    parser.add_argument(
        "--t-action-oversampling",
        nargs="*",
        type=int,
        default=[1],
        help="Source oversampling factors for the parameterized T action probe.",
    )
    parser.add_argument("--skip-self", action="store_true")
    parser.add_argument("--skip-diag-compare", action="store_true")
    parser.add_argument("--skip-t-action", action="store_true")
    parser.add_argument("--skip-solves", action="store_true")
    parser.add_argument(
        "--ibim-source-t-action",
        action="store_true",
        help="Run a compressed-target T-QBX action probe using raw SDF-band samples as oversampled sources.",
    )
    parser.add_argument(
        "--ibim-source-t-solve",
        action="store_true",
        help="Run a forward solve where T is raw SDF-band QBX composed with IDW density prolongation.",
    )
    parser.add_argument(
        "--ibim-source-factors",
        nargs="*",
        type=int,
        default=[1, 2, 4, 8],
        help="Cartesian grid refinement factors for raw SDF-band QBX source samples.",
    )
    parser.add_argument(
        "--ibim-source-delta-cells",
        type=float,
        default=None,
        help="Override the raw-source cosine delta half-width in fine-grid cells; default keeps build_implicit_boundary_band logic.",
    )
    parser.add_argument(
        "--ibim-source-band-cells",
        type=float,
        default=None,
        help="Override the raw-source retained band half-width in fine-grid cells; default keeps build_implicit_boundary_band logic.",
    )
    parser.add_argument("--ibim-source-strict-weights", action="store_true")
    parser.add_argument(
        "--ibim-reproject-targets",
        action="store_true",
        help="For the raw-source T-action diagnostic, reproject compressed target points/normals back to the SDF zero set.",
    )
    parser.add_argument(
        "--ibim-reproject-sources",
        action="store_true",
        help="For the raw-source T-action diagnostic, reproject raw band points/normals once more to the SDF zero set.",
    )
    parser.add_argument("--ibim-reference-n", type=int, default=NYSTROM_N)
    parser.add_argument("--ibim-idw-neighbours", type=int, default=8)
    parser.add_argument("--ibim-idw-power", type=float, default=2.0)
    parser.add_argument("--ibim-source-chunk-size", type=int, default=256)
    parser.add_argument("--ibim-source-bounded-diag-qbx", action="store_true")
    parser.add_argument(
        "--ibim-perfect-prolongation",
        action="store_true",
        help=(
            "For --ibim-source-t-solve only: condition B, 'perfect boundary knowledge'. "
            "Recovers each compressed target's curve parameter t analytically, builds the "
            "oversampled sources directly from the analytic parameterization (exact, no SDF "
            "reprojection needed), and prolongs the density by periodic cubic-spline "
            "interpolation in t instead of local IDW."
        ),
    )
    parser.add_argument(
        "--parameterized-t-solve",
        action="store_true",
        help="Also run a parameterized diagnostic solve with oversampled T-QBX and Fourier density interpolation.",
    )
    parser.add_argument("--parameterized-source-oversampling", type=int, default=8)
    parser.add_argument(
        "--self-csv",
        type=Path,
        default=Path(__file__).resolve().with_name("qbx_diagonal_probe_self_series.csv"),
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only circle, 0.5 GHz, rho/h=0.5, and P in {4, 8, 12} for a smoke test.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.quick:
        args.shapes = ["circle"]
        args.frequencies_ghz = [0.5]
        args.rho_factors = [0.5]
        args.orders = [4, 8, 12]

    cases_by_name = {case.name: case for case in _all_cases()}
    cases = [cases_by_name[name] for name in args.shapes]
    frequencies_hz = np.asarray([1.0e9 * frequency for frequency in args.frequencies_ghz], dtype=float)
    rho_factors = _parse_float_tuple(args.rho_factors, DEFAULT_RHO_FACTORS)
    orders = _parse_int_tuple(args.orders, DEFAULT_ORDERS)
    t_action_oversampling = tuple(args.t_action_oversampling or [1])
    ibim_source_factors = tuple(args.ibim_source_factors or [1])
    settings = QbxSettings(
        expansion_order=int(args.qbx_order),
        radius_spacing_factor=float(args.radius_spacing_factor),
        radius_curvature_factor=float(args.radius_curvature_factor),
    )

    print("QBX diagonal probe")
    print(f"  shapes: {', '.join(case.name for case in cases)}")
    print(f"  frequencies GHz: {', '.join(f'{frequency / 1.0e9:.1f}' for frequency in frequencies_hz)}")
    print(f"  self orders: {orders}")
    print(f"  rho/h requested: {rho_factors}")
    print(f"  T action source oversampling: {t_action_oversampling}")
    if args.ibim_source_t_action or args.ibim_source_t_solve:
        print(f"  raw SDF-band T-QBX source factors: {ibim_source_factors}")
    print(
        "  EXP_BOUNDED_DIAG_QBX radius: "
        f"min({settings.radius_spacing_factor} h, {settings.radius_curvature_factor} R_curv), "
        f"P={settings.expansion_order}"
    )

    if not args.skip_self:
        _run_self_probe(cases, frequencies_hz, rho_factors, orders, settings, args.self_csv)
    if not args.skip_diag_compare:
        _run_bounded_diagonal_compare(cases, frequencies_hz, settings)
    if not args.skip_t_action:
        _run_t_action_probe(cases, frequencies_hz, settings, t_action_oversampling)
    if args.ibim_source_t_action:
        _run_ibim_source_t_action_probe(
            cases,
            frequencies_hz,
            settings,
            ibim_source_factors,
            reference_nodes=int(args.ibim_reference_n),
            delta_cells=args.ibim_source_delta_cells,
            band_cells=args.ibim_source_band_cells,
            strict_weights=bool(args.ibim_source_strict_weights),
            reproject_targets=bool(args.ibim_reproject_targets),
            reproject_sources=bool(args.ibim_reproject_sources),
            idw_neighbours=int(args.ibim_idw_neighbours),
            idw_power=float(args.ibim_idw_power),
            source_chunk_size=int(args.ibim_source_chunk_size),
        )
    if args.ibim_source_t_solve:
        _run_ibim_source_t_solve_probe(
            cases,
            frequencies_hz,
            settings,
            ibim_source_factors,
            delta_cells=args.ibim_source_delta_cells,
            band_cells=args.ibim_source_band_cells,
            strict_weights=bool(args.ibim_source_strict_weights),
            reproject_targets=bool(args.ibim_reproject_targets),
            reproject_sources=bool(args.ibim_reproject_sources),
            bounded_diagonal_qbx=bool(args.ibim_source_bounded_diag_qbx),
            idw_neighbours=int(args.ibim_idw_neighbours),
            idw_power=float(args.ibim_idw_power),
            source_chunk_size=int(args.ibim_source_chunk_size),
            perfect_prolongation=bool(args.ibim_perfect_prolongation),
        )
    if not args.skip_solves:
        _run_solve_table(cases, frequencies_hz, settings)
    if args.parameterized_t_solve:
        _run_parameterized_t_solve(cases, frequencies_hz, settings, args.parameterized_source_oversampling)


if __name__ == "__main__":
    main()
