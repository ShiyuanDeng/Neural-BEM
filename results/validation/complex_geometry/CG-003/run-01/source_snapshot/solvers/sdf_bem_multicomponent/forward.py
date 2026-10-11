"""Automatic SDF/boundary-to-Kress seams for disconnected inclusions.

The repaired curve-state neural inverse remains intentionally single-object.
This module composes the isolated automatic geometry builder with the
multi-component Kress solver, and also accepts an already-owned
``OrderedBoundary2D`` without repeating extraction.  Its paired-experiment
contract can copy any structurally compatible problem without importing
``sdf_inverse``.

Import this module explicitly when exercising the new path.  A future
topology-aware optimizer can adopt the direct-boundary function without a
geometry or operator rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np

from gpr_bem_kress.materials import Material
from gpr_bem_kress.multicomponent import (
    MultiComponentKressForwardResult,
    MultiComponentKressSolveConfig,
    solve_multicomponent_kress_tmz_total_field_batch,
)
from ordered_boundary import OrderedBoundary2D

from .geometry import (
    MultiComponentOrderedSDFGeometryBuild,
    MultiComponentOrderedSDFGeometryConfig,
    build_multicomponent_ordered_sdf_geometry,
)


def _readonly(values: Any, *, dtype: Any) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _finite_nonnegative(value: Any, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise TypeError(f"{name} must be a real number, not bool or complex.")
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


def _finite_positive(value: Any, *, name: str) -> float:
    result = _finite_nonnegative(value, name=name)
    if result == 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return result


def _paired_points(values: Any, *, name: str) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    try:
        points = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must have shape (num_pairs, 2).") from exc
    if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 1:
        raise ValueError(f"{name} must have non-empty shape (num_pairs, 2).")
    if not np.all(np.isfinite(points)):
        raise ValueError(f"{name} must contain only finite coordinates.")
    return _readonly(points, dtype=np.float64)


def _angular_frequencies(values: Any) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError("angular_frequencies must be real-valued.")
    try:
        frequencies = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "angular_frequencies must be a non-empty one-dimensional array."
        ) from exc
    if frequencies.ndim != 1 or frequencies.size < 1:
        raise ValueError(
            "angular_frequencies must be a non-empty one-dimensional array."
        )
    if not np.all(np.isfinite(frequencies)) or np.any(frequencies <= 0.0):
        raise ValueError(
            "angular_frequencies must contain only finite positive values."
        )
    return _readonly(frequencies, dtype=np.float64)


def _frequency_strengths(values: Any, frequency_count: int) -> np.ndarray:
    try:
        strengths = np.asarray(values, dtype=np.complex128)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "source_strengths must be scalar or have one value per frequency."
        ) from exc
    if strengths.ndim == 0:
        strengths = np.full(
            (frequency_count,), strengths.item(), dtype=np.complex128
        )
    elif strengths.shape == (frequency_count,):
        strengths = np.array(strengths, dtype=np.complex128, copy=True)
    else:
        raise ValueError(
            "source_strengths must be scalar or have shape (num_frequencies,)."
        )
    if not np.all(np.isfinite(strengths)):
        raise ValueError("source_strengths must contain only finite values.")
    strengths.setflags(write=False)
    return strengths


def _missing_fields(value: Any, fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in fields if not hasattr(value, name))


@dataclass(frozen=True)
class MaterialSpec:
    """Small solver-neutral material value used by the opt-in path."""

    epsr: float
    sigma: float = 0.0
    mur: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "epsr", _finite_positive(self.epsr, name="epsr"))
        object.__setattr__(
            self,
            "sigma",
            _finite_nonnegative(self.sigma, name="sigma"),
        )
        object.__setattr__(self, "mur", _finite_positive(self.mur, name="mur"))

    @classmethod
    def from_compatible(cls, value: Any) -> "MaterialSpec":
        """Own a copy of any object exposing ``epsr``, ``sigma``, and ``mur``."""

        if isinstance(value, cls):
            return value
        missing = _missing_fields(value, ("epsr", "sigma", "mur"))
        if missing:
            raise TypeError(
                "material must provide epsr, sigma, and mur; missing: "
                + ", ".join(missing)
                + "."
            )
        return cls(epsr=value.epsr, sigma=value.sigma, mur=value.mur)


@dataclass(frozen=True)
class PairedForwardProblem:
    """Immutable paired sources, receivers, frequencies, and materials.

    The class mirrors the established inverse-pipeline value contract without
    importing that pipeline.  ``from_compatible`` is the future wiring seam.
    """

    source_points: np.ndarray
    receiver_points: np.ndarray
    angular_frequencies: np.ndarray
    source_strengths: complex | np.ndarray
    exterior: MaterialSpec
    interior: MaterialSpec
    eps0: float
    mu0: float

    def __post_init__(self) -> None:
        sources = _paired_points(self.source_points, name="source_points")
        receivers = _paired_points(self.receiver_points, name="receiver_points")
        if receivers.shape != sources.shape:
            raise ValueError(
                "receiver_points must have the same (num_pairs, 2) shape as "
                "source_points."
            )
        cross_distances = np.linalg.norm(
            receivers[None, :, :] - sources[:, None, :], axis=-1
        )
        if np.any(cross_distances <= 0.0):
            raise ValueError(
                "Every source point must be distinct from every receiver point."
            )
        frequencies = _angular_frequencies(self.angular_frequencies)
        strengths = _frequency_strengths(self.source_strengths, frequencies.size)
        exterior = MaterialSpec.from_compatible(self.exterior)
        interior = MaterialSpec.from_compatible(self.interior)

        object.__setattr__(self, "source_points", sources)
        object.__setattr__(self, "receiver_points", receivers)
        object.__setattr__(self, "angular_frequencies", frequencies)
        object.__setattr__(self, "source_strengths", strengths)
        object.__setattr__(self, "exterior", exterior)
        object.__setattr__(self, "interior", interior)
        object.__setattr__(self, "eps0", _finite_positive(self.eps0, name="eps0"))
        object.__setattr__(self, "mu0", _finite_positive(self.mu0, name="mu0"))

    @classmethod
    def from_compatible(cls, value: Any) -> "PairedForwardProblem":
        """Copy a problem with the established paired-forward field names."""

        if isinstance(value, cls):
            return value
        fields = (
            "source_points",
            "receiver_points",
            "angular_frequencies",
            "source_strengths",
            "exterior",
            "interior",
            "eps0",
            "mu0",
        )
        missing = _missing_fields(value, fields)
        if missing:
            raise TypeError(
                "problem must provide the paired-forward fields; missing: "
                + ", ".join(missing)
                + "."
            )
        return cls(**{name: getattr(value, name) for name in fields})

    @property
    def num_pairs(self) -> int:
        return int(self.source_points.shape[0])

    @property
    def num_frequencies(self) -> int:
        return int(self.angular_frequencies.size)


def _kress_material(spec: Any) -> Material:
    """Copy one validated solver-neutral material into Kress ownership."""

    return Material(epsr=spec.epsr, sigma=spec.sigma, mur=spec.mur)


def _canonical_paired_solve_payload(
    *,
    boundary: OrderedBoundary2D,
    problem: PairedForwardProblem,
    solve_config: MultiComponentKressSolveConfig,
    scattered_response: Any,
    total_response: Any,
    linear_system_relative_residuals: Any,
    forwards: Any,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    tuple[MultiComponentKressForwardResult, ...],
]:
    """Validate and own the response contract shared by both entry points."""

    if not isinstance(boundary, OrderedBoundary2D):
        raise TypeError("boundary must be an OrderedBoundary2D.")
    if not isinstance(problem, PairedForwardProblem):
        raise TypeError("problem must be a PairedForwardProblem.")
    if not isinstance(solve_config, MultiComponentKressSolveConfig):
        raise TypeError("solve_config must be a MultiComponentKressSolveConfig.")

    expected_shape = (problem.num_pairs, problem.num_frequencies)
    scattered = np.asarray(scattered_response, dtype=np.complex128)
    total = np.asarray(total_response, dtype=np.complex128)
    if scattered.shape != expected_shape:
        raise ValueError(f"scattered_response must have shape {expected_shape}.")
    if total.shape != expected_shape:
        raise ValueError(f"total_response must have shape {expected_shape}.")
    if not np.all(np.isfinite(scattered)) or not np.all(np.isfinite(total)):
        raise ValueError("Forward responses must contain only finite values.")

    if np.iscomplexobj(linear_system_relative_residuals):
        raise ValueError("linear_system_relative_residuals must be real-valued.")
    residuals = np.asarray(
        linear_system_relative_residuals,
        dtype=np.float64,
    )
    if residuals.shape != (problem.num_frequencies,):
        raise ValueError(
            "linear_system_relative_residuals must have shape (num_frequencies,)."
        )
    if not np.all(np.isfinite(residuals)) or np.any(residuals < 0.0):
        raise ValueError(
            "linear_system_relative_residuals must be finite and non-negative."
        )

    retained = tuple(forwards)
    if len(retained) != problem.num_frequencies or not all(
        isinstance(item, MultiComponentKressForwardResult) for item in retained
    ):
        raise TypeError(
            "forwards must contain one MultiComponentKressForwardResult per "
            "frequency."
        )
    if any(item.system.geometry is not boundary for item in retained):
        raise ValueError("Every retained solve must use boundary.")
    for index, (item, angular_frequency, source_strength) in enumerate(
        zip(
            retained,
            problem.angular_frequencies,
            problem.source_strengths,
        )
    ):
        if item.solve_config != solve_config:
            raise ValueError(f"Retained solve {index} does not use solve_config.")
        if item.system.angular_frequency != float(angular_frequency):
            raise ValueError(
                f"Retained solve {index} has the wrong angular frequency."
            )
        if not np.array_equal(item.source_points, problem.source_points):
            raise ValueError(f"Retained solve {index} has different source points.")
        if not np.array_equal(item.receiver_points, problem.receiver_points):
            raise ValueError(
                f"Retained solve {index} has different receiver points."
            )
        expected_strengths = np.full(
            problem.num_pairs,
            source_strength,
            dtype=np.complex128,
        )
        if not np.array_equal(item.source_strengths, expected_strengths):
            raise ValueError(
                f"Retained solve {index} has different source strengths."
            )
        material_values = (
            item.exterior_material.epsr,
            item.exterior_material.sigma,
            item.exterior_material.mur,
            item.interior_material.epsr,
            item.interior_material.sigma,
            item.interior_material.mur,
        )
        expected_material_values = (
            problem.exterior.epsr,
            problem.exterior.sigma,
            problem.exterior.mur,
            problem.interior.epsr,
            problem.interior.sigma,
            problem.interior.mur,
        )
        if material_values != expected_material_values:
            raise ValueError(f"Retained solve {index} has different material values.")
        if item.eps0 != problem.eps0 or item.mu0 != problem.mu0:
            raise ValueError(
                f"Retained solve {index} has different vacuum constants."
            )

    retained_scattered = np.stack(
        [np.diag(item.scattered_receiver) for item in retained],
        axis=1,
    )
    retained_total = np.stack(
        [np.diag(item.total_receiver) for item in retained],
        axis=1,
    )
    retained_residuals = np.asarray(
        [item.linear_system_relative_residual for item in retained],
        dtype=np.float64,
    )
    if not np.array_equal(scattered, retained_scattered):
        raise ValueError("scattered_response must match the retained paired solves.")
    if not np.array_equal(total, retained_total):
        raise ValueError("total_response must match the retained paired solves.")
    if not np.array_equal(residuals, retained_residuals):
        raise ValueError(
            "linear_system_relative_residuals must match the retained solves."
        )

    return (
        _readonly(scattered, dtype=np.complex128),
        _readonly(total, dtype=np.complex128),
        _readonly(residuals, dtype=np.float64),
        retained,
    )


@dataclass(frozen=True)
class MultiComponentPairedForwardResult:
    """Paired frequency responses plus the retained multi-object solves."""

    geometry_build: MultiComponentOrderedSDFGeometryBuild
    problem: PairedForwardProblem
    solve_config: MultiComponentKressSolveConfig
    scattered_response: np.ndarray
    total_response: np.ndarray
    linear_system_relative_residuals: np.ndarray
    forwards: tuple[MultiComponentKressForwardResult, ...]
    geometry_seconds: float
    forward_seconds: float
    total_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(
            self.geometry_build,
            MultiComponentOrderedSDFGeometryBuild,
        ):
            raise TypeError(
                "geometry_build must be a MultiComponentOrderedSDFGeometryBuild."
            )
        scattered, total, residuals, forwards = _canonical_paired_solve_payload(
            boundary=self.geometry_build.boundary,
            problem=self.problem,
            solve_config=self.solve_config,
            scattered_response=self.scattered_response,
            total_response=self.total_response,
            linear_system_relative_residuals=(
                self.linear_system_relative_residuals
            ),
            forwards=self.forwards,
        )
        object.__setattr__(self, "scattered_response", scattered)
        object.__setattr__(self, "total_response", total)
        object.__setattr__(
            self,
            "linear_system_relative_residuals",
            residuals,
        )
        object.__setattr__(self, "forwards", forwards)
        for name in ("geometry_seconds", "forward_seconds", "total_seconds"):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name=name),
            )

    @property
    def num_components(self) -> int:
        return self.geometry_build.boundary.num_components

    @property
    def solver(self) -> str:
        """Compatibility label used by the current paired-result consumers."""

        return "kress"

    @property
    def component_ids(self) -> tuple[str, ...]:
        return self.geometry_build.boundary.component_ids

    @property
    def component_offsets(self) -> np.ndarray:
        return self.geometry_build.boundary.component_offsets

    @property
    def paired_scattered_response(self) -> np.ndarray:
        return self.scattered_response

    @property
    def paired_total_response(self) -> np.ndarray:
        return self.total_response

    @property
    def per_frequency_linear_residuals(self) -> np.ndarray:
        return self.linear_system_relative_residuals


@dataclass(frozen=True)
class MultiComponentBoundaryPairedForwardResult:
    """Paired Kress responses produced from an existing ordered boundary.

    This is the boundary-level counterpart of
    :class:`MultiComponentPairedForwardResult`.  It deliberately retains the
    exact input :class:`~ordered_boundary.OrderedBoundary2D` instead of
    fabricating SDF extraction diagnostics.  Response arrays, retained solves,
    timing names, and compatibility aliases follow the SDF-backed result.
    """

    boundary: OrderedBoundary2D
    problem: PairedForwardProblem
    solve_config: MultiComponentKressSolveConfig
    scattered_response: np.ndarray
    total_response: np.ndarray
    linear_system_relative_residuals: np.ndarray
    forwards: tuple[MultiComponentKressForwardResult, ...]
    forward_seconds: float
    total_seconds: float

    def __post_init__(self) -> None:
        scattered, total, residuals, forwards = _canonical_paired_solve_payload(
            boundary=self.boundary,
            problem=self.problem,
            solve_config=self.solve_config,
            scattered_response=self.scattered_response,
            total_response=self.total_response,
            linear_system_relative_residuals=(
                self.linear_system_relative_residuals
            ),
            forwards=self.forwards,
        )
        object.__setattr__(self, "scattered_response", scattered)
        object.__setattr__(self, "total_response", total)
        object.__setattr__(
            self,
            "linear_system_relative_residuals",
            residuals,
        )
        object.__setattr__(self, "forwards", forwards)
        for name in ("forward_seconds", "total_seconds"):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name=name),
            )

    @property
    def geometry_seconds(self) -> float:
        """No geometry construction is performed by the boundary seam."""

        return 0.0

    @property
    def num_components(self) -> int:
        return self.boundary.num_components

    @property
    def solver(self) -> str:
        return "kress"

    @property
    def component_ids(self) -> tuple[str, ...]:
        return self.boundary.component_ids

    @property
    def component_offsets(self) -> np.ndarray:
        return self.boundary.component_offsets

    @property
    def paired_scattered_response(self) -> np.ndarray:
        return self.scattered_response

    @property
    def paired_total_response(self) -> np.ndarray:
        return self.total_response

    @property
    def per_frequency_linear_residuals(self) -> np.ndarray:
        return self.linear_system_relative_residuals


def _solve_paired_boundary(
    boundary: OrderedBoundary2D,
    problem: PairedForwardProblem,
    solve_config: MultiComponentKressSolveConfig,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    tuple[MultiComponentKressForwardResult, ...],
    float,
]:
    """Solve every frequency on one already-owned ordered boundary."""

    exterior = _kress_material(problem.exterior)
    interior = _kress_material(problem.interior)
    forward_started = perf_counter()
    forwards = tuple(
        solve_multicomponent_kress_tmz_total_field_batch(
            boundary,
            problem.source_points,
            problem.receiver_points,
            float(angular_frequency),
            complex(source_strength),
            exterior=exterior,
            interior=interior,
            eps0=problem.eps0,
            mu0=problem.mu0,
            config=solve_config,
        )
        for angular_frequency, source_strength in zip(
            problem.angular_frequencies,
            problem.source_strengths,
        )
    )
    forward_seconds = float(perf_counter() - forward_started)
    scattered = np.stack(
        [np.diag(item.scattered_receiver) for item in forwards],
        axis=1,
    )
    total = np.stack(
        [np.diag(item.total_receiver) for item in forwards],
        axis=1,
    )
    residuals = np.asarray(
        [item.linear_system_relative_residual for item in forwards],
        dtype=np.float64,
    )
    return scattered, total, residuals, forwards, forward_seconds


def predict_multicomponent_kress_paired_boundary_response(
    boundary: OrderedBoundary2D,
    problem: Any,
    *,
    solve_config: MultiComponentKressSolveConfig | None = None,
) -> MultiComponentBoundaryPairedForwardResult:
    """Solve paired responses directly from an ``OrderedBoundary2D``.

    The component count is read from ``boundary`` at runtime, so one component
    is simply the ``M=1`` case and no upper topology arity is built into this
    adapter.  The function never evaluates an implicit field, runs marching
    squares, or fits a parameterization.  ``problem`` may be the active
    inverse package's ``PairedForwardProblem`` or any object exposing the same
    fields.
    """

    if not isinstance(boundary, OrderedBoundary2D):
        raise TypeError("boundary must be an OrderedBoundary2D.")
    resolved_problem = PairedForwardProblem.from_compatible(problem)
    settings = (
        MultiComponentKressSolveConfig()
        if solve_config is None
        else solve_config
    )
    if not isinstance(settings, MultiComponentKressSolveConfig):
        raise TypeError(
            "solve_config must be a MultiComponentKressSolveConfig."
        )

    total_started = perf_counter()
    scattered, total, residuals, forwards, forward_seconds = (
        _solve_paired_boundary(boundary, resolved_problem, settings)
    )
    return MultiComponentBoundaryPairedForwardResult(
        boundary=boundary,
        problem=resolved_problem,
        solve_config=settings,
        scattered_response=scattered,
        total_response=total,
        linear_system_relative_residuals=residuals,
        forwards=forwards,
        forward_seconds=forward_seconds,
        total_seconds=float(perf_counter() - total_started),
    )


def predict_multicomponent_kress_paired_response(
    model: Any,
    problem: Any,
    geometry_config: MultiComponentOrderedSDFGeometryConfig,
    *,
    solve_config: MultiComponentKressSolveConfig | None = None,
) -> MultiComponentPairedForwardResult:
    """Extract one fixed-topology boundary and solve every requested frequency.

    Kress produces a full source-by-receiver matrix.  This adapter deliberately
    applies the same paired-diagonal measurement convention as the established
    inverse pipeline.  Geometry is extracted once and the identical immutable
    ``OrderedBoundary2D`` is retained by every frequency solve.
    """

    resolved_problem = PairedForwardProblem.from_compatible(problem)
    if not isinstance(
        geometry_config,
        MultiComponentOrderedSDFGeometryConfig,
    ):
        raise TypeError(
            "geometry_config must be a "
            "MultiComponentOrderedSDFGeometryConfig."
        )
    settings = (
        MultiComponentKressSolveConfig()
        if solve_config is None
        else solve_config
    )
    if not isinstance(settings, MultiComponentKressSolveConfig):
        raise TypeError(
            "solve_config must be a MultiComponentKressSolveConfig."
        )

    total_started = perf_counter()
    geometry_started = perf_counter()
    geometry_build = build_multicomponent_ordered_sdf_geometry(
        model,
        geometry_config,
    )
    geometry_seconds = float(perf_counter() - geometry_started)

    scattered, total, residuals, forwards, forward_seconds = (
        _solve_paired_boundary(
            geometry_build.boundary,
            resolved_problem,
            settings,
        )
    )
    return MultiComponentPairedForwardResult(
        geometry_build=geometry_build,
        problem=resolved_problem,
        solve_config=settings,
        scattered_response=scattered,
        total_response=total,
        linear_system_relative_residuals=residuals,
        forwards=forwards,
        geometry_seconds=geometry_seconds,
        forward_seconds=forward_seconds,
        total_seconds=float(perf_counter() - total_started),
    )


__all__ = [
    "MaterialSpec",
    "MultiComponentBoundaryPairedForwardResult",
    "MultiComponentPairedForwardResult",
    "PairedForwardProblem",
    "predict_multicomponent_kress_paired_boundary_response",
    "predict_multicomponent_kress_paired_response",
]
