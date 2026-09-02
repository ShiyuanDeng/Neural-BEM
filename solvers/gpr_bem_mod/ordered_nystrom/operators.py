"""All-block Kress assembly for one ordered periodic Müller interface."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import numpy as np

from ordered_boundary import PeriodicCurve2D
from periodic_kress import kress_log_weights

from ._kernels import (
    EULER_GAMMA,
    PairGeometry,
    _evaluate_radial_differences,
    evaluate_muller_kernel_differences,
    pair_geometry,
    validate_wavenumber,
)
from .geometry import PeriodicCurveAdapter, adapt_periodic_curve


def _readonly_complex(values: np.ndarray) -> np.ndarray:
    result = np.array(values, dtype=np.complex128, copy=True, order="C")
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class MullerAssemblyConfig:
    """Numerical controls for the dense single-component candidate."""

    near_argument: float = 0.75
    series_terms: int = 24
    measure_overlap: bool = True
    maximum_overlap_pairs: int = 256
    target_chunk_size: int = 64

    def __post_init__(self) -> None:
        if isinstance(self.near_argument, (bool, np.bool_)):
            raise TypeError("near_argument must be a real number, not bool.")
        near = float(self.near_argument)
        if not np.isfinite(near) or near <= 0.0:
            raise ValueError("near_argument must be finite and positive.")
        if isinstance(self.series_terms, bool) or int(self.series_terms) != self.series_terms:
            raise TypeError("series_terms must be an integer.")
        if int(self.series_terms) < 6:
            raise ValueError("series_terms must be at least 6.")
        if not isinstance(self.measure_overlap, (bool, np.bool_)):
            raise TypeError("measure_overlap must be boolean.")
        if (
            isinstance(self.maximum_overlap_pairs, bool)
            or int(self.maximum_overlap_pairs) != self.maximum_overlap_pairs
        ):
            raise TypeError("maximum_overlap_pairs must be an integer.")
        if int(self.maximum_overlap_pairs) < 1:
            raise ValueError("maximum_overlap_pairs must be positive.")
        if (
            isinstance(self.target_chunk_size, bool)
            or int(self.target_chunk_size) != self.target_chunk_size
        ):
            raise TypeError("target_chunk_size must be an integer.")
        if int(self.target_chunk_size) < 1:
            raise ValueError("target_chunk_size must be positive.")
        object.__setattr__(self, "near_argument", near)
        object.__setattr__(self, "series_terms", int(self.series_terms))
        object.__setattr__(self, "measure_overlap", bool(self.measure_overlap))
        object.__setattr__(
            self,
            "maximum_overlap_pairs",
            int(self.maximum_overlap_pairs),
        )
        object.__setattr__(self, "target_chunk_size", int(self.target_chunk_size))


@dataclass(frozen=True)
class MullerDifferenceBlocks:
    """Four fully weighted exterior-minus-interior principal operators."""

    geometry: PeriodicCurve2D
    geometry_adapter: PeriodicCurveAdapter
    k_exterior: complex
    k_interior: complex
    delta_v: np.ndarray
    delta_k: np.ndarray
    delta_kp: np.ndarray
    delta_t: np.ndarray
    diagonal_log_coefficients: Mapping[str, np.ndarray]
    diagonal_smooth_remainders: Mapping[str, np.ndarray]
    diagnostics: Mapping[str, object]
    build_seconds: float

    @property
    def num_nodes(self) -> int:
        return self.geometry.num_nodes


def _diagonal_split_limits(
    adapter: PeriodicCurveAdapter,
    k_exterior: complex,
    k_interior: complex,
) -> tuple[Mapping[str, np.ndarray], Mapping[str, np.ndarray]]:
    """Closed diagonal limits for ``kernel*speed = A*L+B``.

    ``L=log(4 sin(theta/2)**2)`` and speed is with respect to canonical
    ``theta``.  No off-node evaluator, singular function call, or numerical
    extrapolation is used.
    """

    speed = adapter.theta_speeds
    delta_squared = k_exterior**2 - k_interior**2
    log_coefficient = -delta_squared / (4.0 * np.pi)
    zero = np.zeros(adapter.num_nodes, dtype=np.complex128)
    diagonal_log = {
        "V": _readonly_complex(zero),
        "K": _readonly_complex(zero),
        "Kp": _readonly_complex(zero),
        "T": _readonly_complex(0.5 * log_coefficient * speed),
    }

    if k_exterior == k_interior:
        diagonal_remainder = {
            name: _readonly_complex(zero) for name in ("V", "K", "Kp", "T")
        }
        return MappingProxyType(diagonal_log), MappingProxyType(diagonal_remainder)

    v_remainder = speed * (
        np.log(k_interior) - np.log(k_exterior)
    ) / (2.0 * np.pi)
    constant_t = 0.125j * delta_squared - (
        delta_squared * (EULER_GAMMA - 0.5 - np.log(2.0))
        + k_exterior**2 * np.log(k_exterior)
        - k_interior**2 * np.log(k_interior)
    ) / (4.0 * np.pi)
    t_remainder = speed * (
        constant_t + log_coefficient * np.log(speed)
    )
    diagonal_remainder = {
        "V": _readonly_complex(v_remainder),
        "K": _readonly_complex(zero),
        "Kp": _readonly_complex(zero),
        "T": _readonly_complex(t_remainder),
    }
    return MappingProxyType(diagonal_log), MappingProxyType(diagonal_remainder)


def _selected_pair_geometry(
    geometry: PairGeometry,
    indices: np.ndarray,
) -> PairGeometry:
    return PairGeometry(
        distance=np.asarray(geometry.distance).reshape(-1)[indices],
        displacement_dot_target_normal=np.asarray(
            geometry.displacement_dot_target_normal
        ).reshape(-1)[indices],
        displacement_dot_source_normal=np.asarray(
            geometry.displacement_dot_source_normal
        ).reshape(-1)[indices],
        normal_dot=np.asarray(geometry.normal_dot).reshape(-1)[indices],
    )


def _concatenate_pair_geometry(parts: list[PairGeometry]) -> PairGeometry | None:
    if not parts:
        return None
    return PairGeometry(
        distance=np.concatenate([part.distance for part in parts]),
        displacement_dot_target_normal=np.concatenate(
            [part.displacement_dot_target_normal for part in parts]
        ),
        displacement_dot_source_normal=np.concatenate(
            [part.displacement_dot_source_normal for part in parts]
        ),
        normal_dot=np.concatenate([part.normal_dot for part in parts]),
    )


def _mixed_relative_error(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(
        float(np.max(np.abs(first))),
        float(np.max(np.abs(second))),
        np.finfo(float).tiny,
    )
    return float(np.max(np.abs(first - second)) / scale)


def _overlap_diagnostics(
    geometry: PairGeometry | None,
    candidate_pair_count: int,
    k_exterior: complex,
    k_interior: complex,
    config: MullerAssemblyConfig,
) -> Mapping[str, object]:
    if not config.measure_overlap or k_exterior == k_interior or geometry is None:
        return MappingProxyType(
            {
                "candidate_pair_count": int(candidate_pair_count),
                "pair_count": 0,
                "errors": MappingProxyType({}),
                "log_coefficient_errors": MappingProxyType({}),
            }
        )

    subset_scaled = max(abs(k_exterior), abs(k_interior)) * geometry.distance
    series = evaluate_muller_kernel_differences(
        geometry,
        k_exterior,
        k_interior,
        near_argument=float(np.max(subset_scaled)) * (1.0 + 1.0e-12),
        series_terms=config.series_terms,
    )
    direct = evaluate_muller_kernel_differences(
        geometry,
        k_exterior,
        k_interior,
        near_argument=float(np.min(subset_scaled)) * 0.5,
        series_terms=config.series_terms,
    )
    errors = {
        name: _mixed_relative_error(getattr(series, field), getattr(direct, field))
        for name, field in (
            ("V", "delta_v"),
            ("K", "delta_k"),
            ("Kp", "delta_kp"),
            ("T", "delta_t"),
        )
    }
    log_coefficient_errors = {
        name: _mixed_relative_error(getattr(series, field), getattr(direct, field))
        for name, field in (
            ("V", "log_v"),
            ("K", "log_k"),
            ("Kp", "log_kp"),
            ("T", "log_t"),
        )
    }
    return MappingProxyType(
        {
            "candidate_pair_count": int(candidate_pair_count),
            "pair_count": int(geometry.distance.size),
            "scaled_argument_min": float(np.min(subset_scaled)),
            "scaled_argument_max": float(np.max(subset_scaled)),
            "errors": MappingProxyType(errors),
            "log_coefficient_errors": MappingProxyType(log_coefficient_errors),
        }
    )


def _physical_kernel_pair(
    name: str,
    geometry: PairGeometry,
    radial_values: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Form one physical kernel and its exact ``log(r)`` coefficient."""

    (
        green,
        radial_first,
        radial_anisotropy,
        green_log,
        radial_first_log,
        radial_anisotropy_log,
    ) = radial_values
    if name == "V":
        return green, green_log
    if name == "K":
        return (
            -radial_first * geometry.displacement_dot_source_normal,
            -radial_first_log * geometry.displacement_dot_source_normal,
        )
    if name == "Kp":
        return (
            radial_first * geometry.displacement_dot_target_normal,
            radial_first_log * geometry.displacement_dot_target_normal,
        )
    if name == "T":
        projection_product = (
            geometry.displacement_dot_target_normal
            * geometry.displacement_dot_source_normal
            / geometry.distance**2
        )
        return (
            -radial_first * geometry.normal_dot
            - radial_anisotropy * projection_product,
            -radial_first_log * geometry.normal_dot
            - radial_anisotropy_log * projection_product,
        )
    raise ValueError(f"Unknown Müller block {name!r}.")


def build_muller_difference_blocks(
    curve: PeriodicCurve2D,
    k_exterior: complex,
    k_interior: complex,
    *,
    config: MullerAssemblyConfig | None = None,
) -> MullerDifferenceBlocks:
    """Build coherent Kress matrices for ``Delta V/K/Kp/T``.

    Each returned matrix already contains the source Jacobian and quadrature
    weights.  Its action is directly ``matrix @ nodal_density``; multiplying
    by ``curve.arc_length_weights`` again would be an error.
    """

    started = perf_counter()
    settings = MullerAssemblyConfig() if config is None else config
    if not isinstance(settings, MullerAssemblyConfig):
        raise TypeError("config must be a MullerAssemblyConfig object.")
    adapter = adapt_periodic_curve(curve)
    exterior = validate_wavenumber(k_exterior, name="k_exterior")
    interior = validate_wavenumber(k_interior, name="k_interior")
    count = adapter.num_nodes

    diagonal_log, diagonal_remainder = _diagonal_split_limits(
        adapter, exterior, interior
    )

    names = ("V", "K", "Kp", "T")
    matrices = {
        name: np.zeros((count, count), dtype=np.complex128) for name in names
    }
    near_pair_count = 0
    direct_pair_count = 0
    overlap_candidate_count = 0
    overlap_parts: list[PairGeometry] = []
    pair_geometry_seconds = 0.0
    kernel_seconds = 0.0
    block_seconds = {name: 0.0 for name in names}

    if exterior != interior:
        offsets = np.arange(count, dtype=np.int64)
        kress_by_offset = kress_log_weights(count)
        log_by_offset = np.zeros(count, dtype=np.float64)
        log_by_offset[1:] = np.log(
            4.0 * np.sin(np.pi * offsets[1:] / count) ** 2
        )
        source_speed = adapter.theta_speeds[None, :]
        maximum_wave = max(abs(exterior), abs(interior))
        chunk_count = (
            count + settings.target_chunk_size - 1
        ) // settings.target_chunk_size
        overlap_chunk_quota = max(
            1,
            int(np.ceil(settings.maximum_overlap_pairs / chunk_count)),
        )

        for first_target in range(0, count, settings.target_chunk_size):
            past_target = min(first_target + settings.target_chunk_size, count)
            target_indices = np.arange(first_target, past_target, dtype=np.int64)
            local_count = int(target_indices.size)

            pair_started = perf_counter()
            chunk_geometry = pair_geometry(
                adapter.points[first_target:past_target],
                adapter.normals[first_target:past_target],
                adapter.points,
                adapter.normals,
            )
            off_diagonal = np.ones((local_count, count), dtype=bool)
            off_diagonal[np.arange(local_count), target_indices] = False
            off_geometry = PairGeometry(
                distance=chunk_geometry.distance[off_diagonal],
                displacement_dot_target_normal=(
                    chunk_geometry.displacement_dot_target_normal[off_diagonal]
                ),
                displacement_dot_source_normal=(
                    chunk_geometry.displacement_dot_source_normal[off_diagonal]
                ),
                normal_dot=chunk_geometry.normal_dot[off_diagonal],
            )
            pair_geometry_seconds += perf_counter() - pair_started

            if settings.measure_overlap:
                scaled_distance = maximum_wave * off_geometry.distance
                candidate_indices = np.flatnonzero(
                    (scaled_distance >= 0.5 * settings.near_argument)
                    & (scaled_distance <= 1.5 * settings.near_argument)
                )
                overlap_candidate_count += int(candidate_indices.size)
                if candidate_indices.size:
                    if candidate_indices.size > overlap_chunk_quota:
                        selection = np.linspace(
                            0,
                            candidate_indices.size - 1,
                            overlap_chunk_quota,
                            dtype=np.int64,
                        )
                        candidate_indices = candidate_indices[selection]
                    overlap_parts.append(
                        _selected_pair_geometry(
                            off_geometry,
                            candidate_indices,
                        )
                    )

            kernel_started = perf_counter()
            radial_values, near_count, direct_count = _evaluate_radial_differences(
                off_geometry.distance,
                exterior,
                interior,
                near_argument=settings.near_argument,
                series_terms=settings.series_terms,
            )
            kernel_seconds += perf_counter() - kernel_started
            near_pair_count += near_count
            direct_pair_count += direct_count

            offset_indices = (
                target_indices[:, None] - offsets[None, :]
            ) % count
            weight_rows = kress_by_offset[offset_indices]
            log_rows = log_by_offset[offset_indices]
            local_diagonal = np.arange(local_count)
            for name in names:
                block_started = perf_counter()
                kernel, logarithmic_coefficient = _physical_kernel_pair(
                    name,
                    off_geometry,
                    radial_values,
                )
                kernel_grid = np.zeros(
                    (local_count, count), dtype=np.complex128
                )
                logarithmic_grid = np.zeros_like(kernel_grid)
                kernel_grid[off_diagonal] = kernel
                logarithmic_grid[off_diagonal] = logarithmic_coefficient
                matrix_rows = source_speed * (
                    adapter.theta_step * kernel_grid
                    + 0.5
                    * logarithmic_grid
                    * (weight_rows - adapter.theta_step * log_rows)
                )
                matrix_rows[local_diagonal, target_indices] = (
                    kress_by_offset[0] * diagonal_log[name][target_indices]
                    + adapter.theta_step
                    * diagonal_remainder[name][target_indices]
                )
                matrices[name][first_target:past_target] = matrix_rows
                block_seconds[name] += perf_counter() - block_started

    overlap_geometry = _concatenate_pair_geometry(overlap_parts)
    if (
        overlap_geometry is not None
        and overlap_geometry.distance.size > settings.maximum_overlap_pairs
    ):
        selection = np.linspace(
            0,
            overlap_geometry.distance.size - 1,
            settings.maximum_overlap_pairs,
            dtype=np.int64,
        )
        overlap_geometry = _selected_pair_geometry(overlap_geometry, selection)
    overlap_started = perf_counter()
    overlap = _overlap_diagnostics(
        overlap_geometry,
        overlap_candidate_count,
        exterior,
        interior,
        settings,
    )
    overlap_seconds = perf_counter() - overlap_started
    for name, matrix in matrices.items():
        if not np.all(np.isfinite(matrix)):
            raise FloatingPointError(f"Delta {name} assembly produced non-finite entries.")
        matrix.setflags(write=False)

    block_norms = MappingProxyType(
        {name: float(np.linalg.norm(matrix, ord=np.inf)) for name, matrix in matrices.items()}
    )
    diagnostics = MappingProxyType(
        {
            "geometry_id": adapter.geometry_id,
            "num_nodes": count,
            "component_count": 1,
            "orientation": curve.orientation,
            "normal_convention": "outward_from_inclusion",
            "kress_logarithm": "log(4 sin(theta/2)^2)",
            "source_jacobian_included": True,
            "parameter_step_included": True,
            "unknowns_are_weighted": False,
            "diagonal_strategy": "closed_form_power_log_limits",
            "near_strategy": "combined_green_power_log_series",
            "near_argument": settings.near_argument,
            "series_terms": settings.series_terms,
            "target_chunk_size": settings.target_chunk_size,
            "zero_contrast_shortcut": exterior == interior,
            "near_pair_count": near_pair_count,
            "direct_pair_count": direct_pair_count,
            "overlap": overlap,
            "block_infinity_norms": block_norms,
            "retained_block_bytes": int(
                sum(matrix.nbytes for matrix in matrices.values())
            ),
            "timings_seconds": MappingProxyType(
                {
                    "pair_geometry": float(pair_geometry_seconds),
                    "shared_kernel_evaluation": float(kernel_seconds),
                    **{
                        f"assemble_delta_{name}": float(block_seconds[name])
                        for name in names
                    },
                    "overlap_diagnostic": float(overlap_seconds),
                }
            ),
        }
    )
    return MullerDifferenceBlocks(
        geometry=curve,
        geometry_adapter=adapter,
        k_exterior=exterior,
        k_interior=interior,
        delta_v=matrices["V"],
        delta_k=matrices["K"],
        delta_kp=matrices["Kp"],
        delta_t=matrices["T"],
        diagonal_log_coefficients=diagonal_log,
        diagonal_smooth_remainders=diagonal_remainder,
        diagnostics=diagnostics,
        build_seconds=float(perf_counter() - started),
    )


__all__ = [
    "MullerAssemblyConfig",
    "MullerDifferenceBlocks",
    "build_muller_difference_blocks",
]
