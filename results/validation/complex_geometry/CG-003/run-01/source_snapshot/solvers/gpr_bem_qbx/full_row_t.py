"""Archived full-row QBX diagnostic for the Müller ``dT`` block.

The target unknowns remain on the compressed kdiff boundary.  An oversampled
source quadrature produces a rectangular QBX operator, and a linear density
prolongation maps it back to the square system layout::

    T = T_rect(targets, oversampled_sources) @ P

Only ``T`` is returned; ``S``, ``D`` and ``K'`` stay owned by
``gpr_bem_kdiff.build_kdiff_operator_blocks``.

This module is retained to reproduce the investigation closed in
``docs/qbx_closure.md``. It is not a validated production discretization.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Union

import numpy as np
import torch
from scipy.spatial import cKDTree
from scipy.special import hankel1, jv

from gpr_bem_kdiff.t_assembly import TAssemblyContext, TAssemblyReport, TAssemblyResult

TWO_PI = 2.0 * np.pi
Parameterization = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]


@dataclass(frozen=True)
class SameNodeSources:
    """Use the existing target nodes as the QBX source quadrature.

    This is the plain, no-oversampling negative control: the rectangular
    operator is square and the density prolongation is the identity. Each
    coincident self source lies on the boundary of Graf-series convergence,
    so this mode must not be treated as a convergent QBX construction.
    """


@dataclass(frozen=True)
class ParameterizedFourierSources:
    """Analytic periodic source curve with Fourier density prolongation.

    ``target_parameters`` identifies each existing target node in the supplied
    parameterization.  If omitted, targets are assumed to be in uniform
    parameter order ``2*pi*i/N``.  Supplying the values explicitly also allows
    nonuniform target parameters via a Fourier collocation solve.
    """

    parameterization: Parameterization
    oversampling_factor: int = 8
    target_parameters: np.ndarray | None = None


@dataclass(frozen=True)
class FourierComponent:
    """One closed component in a component-wise Fourier prolongation."""

    parameterization: Parameterization
    target_indices: np.ndarray
    target_parameters: np.ndarray


@dataclass(frozen=True)
class ComponentParameterizedFourierSources:
    """Independent Fourier source grids and prolongations per component."""

    components: tuple[FourierComponent, ...]
    oversampling_factor: int = 8


@dataclass(frozen=True)
class IDWProlongation:
    neighbours: int = 8
    power: float = 2.0


@dataclass(frozen=True)
class RawSDFBandSources:
    """Fine raw IBIM-band sources with local IDW density prolongation."""

    grid_refinement_factor: int = 8
    base_grid_shape: tuple[int, int] = (161, 161)
    delta_cells: float = 2.5
    band_cells: float | None = None
    strict_weights: bool = False
    reproject_sources: bool = True
    prolongation: IDWProlongation = field(default_factory=IDWProlongation)


QbxSourceConfiguration = Union[
    SameNodeSources,
    ParameterizedFourierSources,
    ComponentParameterizedFourierSources,
    RawSDFBandSources,
]


@dataclass(frozen=True)
class FullRowQBX:
    """Diagnostic QBX T assembler selected by ``gpr_bem_kdiff``'s solve API.

    Invalid expansion clearance raises by default before matrix assembly.
    ``allow_invalid_clearance=True`` exists only to reproduce archived rows;
    it does not make those rows admissible.
    """

    source: QbxSourceConfiguration
    expansion_order: int = 16
    radius_spacing_factor: float = 1.0
    radius_curvature_factor: float = 0.2
    source_chunk_size: int = 128
    source_workers: int = 1
    allow_invalid_clearance: bool = False
    name: str = "full_row_qbx"
    _source_cache: dict[tuple[object, ...], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.expansion_order < 1:
            raise ValueError("expansion_order must be positive.")
        if self.radius_spacing_factor <= 0.0 or self.radius_curvature_factor <= 0.0:
            raise ValueError("QBX radius factors must be positive.")
        if self.source_chunk_size < 1:
            raise ValueError("source_chunk_size must be positive.")
        if self.source_workers < 1:
            raise ValueError("source_workers must be positive.")

    def assemble(self, context: TAssemblyContext) -> TAssemblyResult:
        started = time.perf_counter()
        expansion_radius = _expansion_radius(
            context,
            spacing_factor=self.radius_spacing_factor,
            curvature_factor=self.radius_curvature_factor,
        )
        source_key = _source_cache_key(context)
        prepared = self._source_cache.get(source_key)
        source_cache_hit = prepared is not None
        if prepared is None:
            prepared = _build_sources(context, self.source)
            self._source_cache[source_key] = prepared
        source_points, source_normals, source_weights, prolongation, source_parameters = prepared
        min_clearance, invalid_count, marginal_count = _clearance_diagnostics(
            context.points,
            context.normals,
            source_points,
            expansion_radius,
            self.source_chunk_size,
        )
        if invalid_count and not self.allow_invalid_clearance:
            raise ValueError(
                "QBX expansion geometry is inadmissible: "
                f"{invalid_count} source/center pairs have clearance ratio < 1 "
                f"(minimum {min_clearance:.6g}). Set allow_invalid_clearance=True "
                "only to reproduce an archived diagnostic."
            )
        matrix = _qbx_t_matrix_with_prolongation(
            context.points,
            context.normals,
            source_points,
            source_normals,
            source_weights,
            prolongation,
            context.k_exterior,
            context.k_interior,
            expansion_radius,
            self.expansion_order,
            self.source_chunk_size,
            self.source_workers,
        )
        constant_error = float(
            np.max(np.abs(prolongation @ np.ones(context.points.shape[0]) - 1.0))
        )
        diagnostics: dict[str, object] = {
            "num_targets": int(context.points.shape[0]),
            "num_sources": int(source_points.shape[0]),
            "actual_source_ratio": float(source_points.shape[0] / context.points.shape[0]),
            "min_clearance_ratio": min_clearance,
            "invalid_clearance_count": invalid_count,
            "marginal_clearance_count": marginal_count,
            "constant_prolongation_error": constant_error,
            "source_cache_hit": source_cache_hit,
            "assembly_seconds": float(time.perf_counter() - started),
        }
        diagnostics.update(source_parameters)
        parameters = {
            "expansion_order": int(self.expansion_order),
            "radius_spacing_factor": float(self.radius_spacing_factor),
            "radius_curvature_factor": float(self.radius_curvature_factor),
            "source_chunk_size": int(self.source_chunk_size),
            "source_workers": int(self.source_workers),
            "source_mode": _source_mode(self.source),
            "allow_invalid_clearance": bool(self.allow_invalid_clearance),
        }
        return TAssemblyResult(
            matrix=matrix,
            report=TAssemblyReport(method=self.name, parameters=parameters, diagnostics=diagnostics),
        )


def _source_mode(source: QbxSourceConfiguration) -> str:
    if isinstance(source, SameNodeSources):
        return "same_node"
    if isinstance(source, ParameterizedFourierSources):
        return "parameterized_fourier"
    if isinstance(source, ComponentParameterizedFourierSources):
        return "component_parameterized_fourier"
    if isinstance(source, RawSDFBandSources):
        return "raw_sdf_band_idw"
    raise TypeError(f"Unsupported QBX source configuration: {type(source).__name__}.")


def _build_sources(
    context: TAssemblyContext,
    source: QbxSourceConfiguration,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    if isinstance(source, SameNodeSources):
        num_targets = context.points.shape[0]
        return (
            context.points,
            context.normals,
            context.weights,
            np.eye(num_targets, dtype=complex),
            {"requested_oversampling_factor": 1},
        )
    if isinstance(source, ParameterizedFourierSources):
        return _parameterized_sources(context, source)
    if isinstance(source, ComponentParameterizedFourierSources):
        return _component_parameterized_sources(context, source)
    if isinstance(source, RawSDFBandSources):
        return _raw_sdf_sources(context, source)
    raise TypeError(f"Unsupported QBX source configuration: {type(source).__name__}.")


def _source_cache_key(context: TAssemblyContext) -> tuple[object, ...]:
    """Fingerprint the frequency-independent geometry prepared by a strategy."""

    return (
        context.points.shape,
        context.points.tobytes(),
        context.normals.tobytes(),
        context.weights.tobytes(),
        context.bounds,
        float(context.level),
        id(context.sdf_fn),
    )


def _parameterized_sources(
    context: TAssemblyContext,
    settings: ParameterizedFourierSources,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    factor = int(settings.oversampling_factor)
    if factor < 1:
        raise ValueError("oversampling_factor must be positive.")
    num_targets = context.points.shape[0]
    num_sources = factor * num_targets
    if num_sources % 2:
        num_sources += 1
    target_t = (
        TWO_PI * np.arange(num_targets, dtype=float) / num_targets
        if settings.target_parameters is None
        else np.asarray(settings.target_parameters, dtype=float).reshape(-1)
    )
    if target_t.shape != (num_targets,):
        raise ValueError(f"target_parameters must have shape ({num_targets},).")
    source_t = TWO_PI * np.arange(num_sources, dtype=float) / num_sources
    source_points, source_tangents = settings.parameterization(source_t)
    source_points = np.asarray(source_points, dtype=float)
    source_tangents = np.asarray(source_tangents, dtype=float)
    if source_points.shape != (num_sources, 2) or source_tangents.shape != (num_sources, 2):
        raise ValueError("parameterization must return point and tangent arrays with shape (M, 2).")
    source_speeds = np.linalg.norm(source_tangents, axis=1)
    if np.any(source_speeds <= 0.0):
        raise ValueError("parameterization returned a zero tangent.")
    source_normals = np.stack((source_tangents[:, 1], -source_tangents[:, 0]), axis=1) / source_speeds[:, None]
    source_weights = source_speeds * (TWO_PI / num_sources)
    prolongation = _fourier_prolongation_matrix(target_t, source_t)
    parameterized_targets, _ = settings.parameterization(target_t)
    geometry_mismatch = float(
        np.max(np.linalg.norm(np.asarray(parameterized_targets, dtype=float) - context.points, axis=1))
    )
    return (
        source_points,
        source_normals,
        source_weights,
        prolongation,
        {
            "requested_oversampling_factor": factor,
            "target_parameterization_mismatch": geometry_mismatch,
            "fourier_collocation_condition": _fourier_collocation_condition(target_t),
        },
    )


def _fourier_prolongation_matrix(target_t: np.ndarray, source_t: np.ndarray) -> np.ndarray:
    num_targets = int(target_t.size)
    modes = np.fft.fftfreq(num_targets, d=1.0 / num_targets)
    target_basis = np.exp(1j * np.mod(target_t, TWO_PI)[:, None] * modes[None, :])
    source_basis = np.exp(1j * np.mod(source_t, TWO_PI)[:, None] * modes[None, :])
    try:
        return np.linalg.solve(target_basis.T, source_basis.T).T
    except np.linalg.LinAlgError as exc:
        raise ValueError("target_parameters do not define an invertible Fourier collocation grid.") from exc


def _fourier_collocation_condition(target_t: np.ndarray) -> float:
    num_targets = int(target_t.size)
    modes = np.fft.fftfreq(num_targets, d=1.0 / num_targets)
    basis = np.exp(1j * np.mod(target_t, TWO_PI)[:, None] * modes[None, :])
    return float(np.linalg.cond(basis))


def _component_parameterized_sources(
    context: TAssemblyContext,
    settings: ComponentParameterizedFourierSources,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    factor = int(settings.oversampling_factor)
    if factor < 1:
        raise ValueError("oversampling_factor must be positive.")
    if not settings.components:
        raise ValueError("components must not be empty.")

    num_targets = context.points.shape[0]
    assigned = np.zeros(num_targets, dtype=bool)
    point_parts: list[np.ndarray] = []
    normal_parts: list[np.ndarray] = []
    weight_parts: list[np.ndarray] = []
    prolongation_parts: list[np.ndarray] = []
    mismatches: list[float] = []
    target_counts: list[int] = []
    source_counts: list[int] = []
    collocation_conditions: list[float] = []
    for component in settings.components:
        indices = np.asarray(component.target_indices, dtype=int).reshape(-1)
        target_t = np.asarray(component.target_parameters, dtype=float).reshape(-1)
        if indices.size == 0 or target_t.shape != indices.shape:
            raise ValueError("Each Fourier component needs matching non-empty target indices and parameters.")
        if np.unique(indices).size != indices.size:
            raise ValueError("Target indices may not repeat within a Fourier component.")
        if np.any(indices < 0) or np.any(indices >= num_targets) or np.any(assigned[indices]):
            raise ValueError("Fourier component target indices must be unique and in range.")
        assigned[indices] = True

        num_sources = factor * indices.size
        if num_sources % 2:
            num_sources += 1
        source_t = TWO_PI * np.arange(num_sources, dtype=float) / num_sources
        source_points, source_tangents = component.parameterization(source_t)
        source_points = np.asarray(source_points, dtype=float)
        source_tangents = np.asarray(source_tangents, dtype=float)
        if source_points.shape != (num_sources, 2) or source_tangents.shape != (num_sources, 2):
            raise ValueError("Each component parameterization must return arrays with shape (M, 2).")
        speeds = np.linalg.norm(source_tangents, axis=1)
        if np.any(speeds <= 0.0):
            raise ValueError("A component parameterization returned a zero tangent.")
        point_parts.append(source_points)
        normal_parts.append(np.stack((source_tangents[:, 1], -source_tangents[:, 0]), axis=1) / speeds[:, None])
        weight_parts.append(speeds * (TWO_PI / num_sources))
        local_prolongation = _fourier_prolongation_matrix(target_t, source_t)
        global_prolongation = np.zeros((num_sources, num_targets), dtype=complex)
        global_prolongation[:, indices] = local_prolongation
        prolongation_parts.append(global_prolongation)
        parameterized_targets, _ = component.parameterization(target_t)
        mismatches.append(
            float(
                np.max(
                    np.linalg.norm(
                        np.asarray(parameterized_targets, dtype=float) - context.points[indices],
                        axis=1,
                    )
                )
            )
        )
        target_counts.append(int(indices.size))
        source_counts.append(int(num_sources))
        collocation_conditions.append(_fourier_collocation_condition(target_t))

    if not np.all(assigned):
        raise ValueError("Fourier components must assign every target node exactly once.")
    return (
        np.concatenate(point_parts, axis=0),
        np.concatenate(normal_parts, axis=0),
        np.concatenate(weight_parts, axis=0),
        np.concatenate(prolongation_parts, axis=0),
        {
            "requested_oversampling_factor": factor,
            "num_components": len(settings.components),
            "component_target_counts": target_counts,
            "component_source_counts": source_counts,
            "component_fourier_collocation_conditions": collocation_conditions,
            "fourier_collocation_condition": max(collocation_conditions),
            "target_parameterization_mismatch": max(mismatches),
        },
    )


def _raw_sdf_sources(
    context: TAssemblyContext,
    settings: RawSDFBandSources,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    if context.sdf_fn is None:
        raise ValueError("RawSDFBandSources requires sdf_fn to be passed to the kdiff solve.")
    factor = int(settings.grid_refinement_factor)
    if factor < 1:
        raise ValueError("grid_refinement_factor must be positive.")
    ny = factor * (int(settings.base_grid_shape[0]) - 1) + 1
    nx = factor * (int(settings.base_grid_shape[1]) - 1) + 1

    from gpr_bem_kdiff.ibim_geometry import build_implicit_boundary_band, cartesian_grid_points, project_points_to_level_set

    _, _, _, spacing, _ = cartesian_grid_points(context.bounds, grid_shape=(ny, nx), dtype=torch.float64)
    cell_scale = max(spacing)
    delta_half_width = float(settings.delta_cells) * cell_scale
    band_cells = settings.delta_cells if settings.band_cells is None else settings.band_cells
    band = build_implicit_boundary_band(
        context.sdf_fn,
        context.bounds,
        grid_shape=(ny, nx),
        level=context.level,
        delta_half_width=delta_half_width,
        band_half_width=float(band_cells) * cell_scale,
        dtype=torch.float64,
    )
    source_points_tensor = band.projected_points
    source_normals_tensor = band.normals
    if settings.reproject_sources:
        points_for_grad = source_points_tensor.detach().clone().requires_grad_(True)
        sdf_values = context.sdf_fn(points_for_grad).reshape(-1, 1)
        gradients = torch.autograd.grad(
            outputs=sdf_values,
            inputs=points_for_grad,
            grad_outputs=torch.ones_like(sdf_values),
            create_graph=False,
            retain_graph=False,
            only_inputs=True,
        )[0]
        source_points_tensor = project_points_to_level_set(
            points_for_grad,
            sdf_values,
            gradients,
            level=context.level,
        )
        source_normals_tensor = gradients / torch.linalg.norm(gradients, dim=1, keepdim=True).clamp_min(1.0e-8)
    source_points = source_points_tensor.detach().cpu().numpy().astype(float)
    source_normals = source_normals_tensor.detach().cpu().numpy().astype(float)
    weight_tensor = band.strict_quadrature_weights if settings.strict_weights else band.quadrature_weights
    source_weights = weight_tensor.detach().cpu().numpy().reshape(-1).astype(float)
    prolongation = _idw_prolongation_matrix(context.points, source_points, settings.prolongation)
    return (
        source_points,
        source_normals,
        source_weights,
        prolongation,
        {
            "requested_grid_refinement_factor": factor,
            "source_grid_shape": [ny, nx],
            "idw_neighbours": int(settings.prolongation.neighbours),
            "idw_power": float(settings.prolongation.power),
            "reproject_sources": bool(settings.reproject_sources),
            "source_boundary_measure": float(np.sum(source_weights)),
        },
    )


def _idw_prolongation_matrix(
    target_points: np.ndarray,
    source_points: np.ndarray,
    settings: IDWProlongation,
) -> np.ndarray:
    neighbours = max(1, min(int(settings.neighbours), target_points.shape[0]))
    if settings.power <= 0.0:
        raise ValueError("IDW power must be positive.")
    distances, indices = cKDTree(target_points).query(source_points, k=neighbours)
    distances = np.asarray(distances, dtype=float)
    indices = np.asarray(indices, dtype=int)
    if neighbours == 1:
        distances = distances[:, None]
        indices = indices[:, None]
    exact = distances <= 1.0e-13
    coefficients = np.zeros_like(distances)
    exact_rows = np.any(exact, axis=1)
    if np.any(exact_rows):
        coefficients[exact_rows, np.argmax(exact[exact_rows], axis=1)] = 1.0
    if np.any(~exact_rows):
        local = np.maximum(distances[~exact_rows], 1.0e-13) ** (-float(settings.power))
        coefficients[~exact_rows] = local / local.sum(axis=1, keepdims=True)
    prolongation = np.zeros((source_points.shape[0], target_points.shape[0]), dtype=complex)
    rows = np.repeat(np.arange(source_points.shape[0])[:, None], neighbours, axis=1)
    np.add.at(prolongation, (rows.ravel(), indices.ravel()), coefficients.ravel())
    return prolongation


def _expansion_radius(
    context: TAssemblyContext,
    *,
    spacing_factor: float,
    curvature_factor: float,
) -> np.ndarray:
    from gpr_bem_kdiff.ibim_tmz_forward import _local_frames, _local_radius, _sdf_curvature

    frames = _local_frames(context.points, context.normals, context.weights)
    curvature = (
        _sdf_curvature(context.points, context.sdf_fn)
        if context.sdf_fn is not None
        else frames["curvature"]
    )
    curvature_radius = _local_radius(curvature)
    radius = np.minimum(
        float(spacing_factor) * frames["step_scale"],
        float(curvature_factor) * curvature_radius,
    )
    return np.maximum(radius, 1.0e-12)


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
    displacement = source_points[None, :, :] - centers[:, None, :]
    rho = np.linalg.norm(displacement, axis=2)
    theta = np.arctan2(displacement[:, :, 1], displacement[:, :, 0])
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
    bessel_deriv = 0.5 * (
        jv(orders[:, None] - 1.0, zx[None, :]) - jv(orders[:, None] + 1.0, zx[None, :])
    )
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


def _qbx_t_rect_matrix(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    expansion_radius: np.ndarray,
    order: int,
) -> np.ndarray:
    exterior_plus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights,
        k_exterior, expansion_radius, +1.0, order,
    )
    exterior_minus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights,
        k_exterior, expansion_radius, -1.0, order,
    )
    interior_plus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights,
        k_interior, expansion_radius, +1.0, order,
    )
    interior_minus = _qbx_side_hyper_rect_matrix(
        target_points, target_normals, source_points, source_normals, source_weights,
        k_interior, expansion_radius, -1.0, order,
    )
    return 0.5 * (exterior_plus + exterior_minus - interior_plus - interior_minus)


def _qbx_t_matrix_with_prolongation(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    prolongation: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    expansion_radius: np.ndarray,
    order: int,
    source_chunk_size: int,
    source_workers: int = 1,
) -> np.ndarray:
    def contribution(bounds: tuple[int, int]) -> np.ndarray:
        start, stop = bounds
        rectangular = _qbx_t_rect_matrix(
            target_points,
            target_normals,
            source_points[start:stop],
            source_normals[start:stop],
            source_weights[start:stop],
            k_exterior,
            k_interior,
            expansion_radius,
            order,
        )
        return rectangular @ prolongation[start:stop, :]

    chunks = []
    for start in range(0, source_points.shape[0], source_chunk_size):
        stop = min(start + source_chunk_size, source_points.shape[0])
        chunks.append((start, stop))
    if source_workers == 1:
        contributions = map(contribution, chunks)
    else:
        executor = ThreadPoolExecutor(max_workers=source_workers)
        contributions = executor.map(contribution, chunks)
    matrix = np.zeros((target_points.shape[0], target_points.shape[0]), dtype=complex)
    try:
        for chunk_matrix in contributions:
            matrix += chunk_matrix
    finally:
        if source_workers != 1:
            executor.shutdown(wait=True)
    return matrix


def _clearance_diagnostics(
    target_points: np.ndarray,
    target_normals: np.ndarray,
    source_points: np.ndarray,
    expansion_radius: np.ndarray,
    source_chunk_size: int,
) -> tuple[float, int, int]:
    min_ratio = float("inf")
    invalid = 0
    marginal = 0
    for side in (+1.0, -1.0):
        centers = target_points + side * expansion_radius[:, None] * target_normals
        for start in range(0, source_points.shape[0], source_chunk_size):
            stop = min(start + source_chunk_size, source_points.shape[0])
            distance = np.linalg.norm(centers[:, None, :] - source_points[None, start:stop, :], axis=2)
            ratio = distance / expansion_radius[:, None]
            min_ratio = min(min_ratio, float(np.min(ratio)))
            invalid += int(np.count_nonzero(ratio < 1.0 - 1.0e-8))
            marginal += int(np.count_nonzero((ratio >= 1.0 - 1.0e-8) & (ratio <= 1.0 + 1.0e-8)))
    return min_ratio, invalid, marginal


__all__ = [
    "ComponentParameterizedFourierSources",
    "FourierComponent",
    "FullRowQBX",
    "IDWProlongation",
    "ParameterizedFourierSources",
    "RawSDFBandSources",
    "SameNodeSources",
]
