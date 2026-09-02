"""Solver-neutral paired forward-response seam for SDF inversion."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np

from .geometry import (
    OrderedSDFGeometryBuild,
    OrderedSDFGeometryConfig,
    build_ordered_sdf_geometry,
    ordered_curve_to_mod_boundary,
)


def _real_scalar(value: Any, *, name: str, positive: bool) -> float:
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise TypeError(f"{name} must be a real number, not bool or complex.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real number.") from exc
    relation_holds = result > 0.0 if positive else result >= 0.0
    if not np.isfinite(result) or not relation_holds:
        relation = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be finite and {relation}.")
    return result


def _readonly_array(values: Any, *, dtype: Any) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
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
    return _readonly_array(points, dtype=np.float64)


def _angular_frequencies(values: Any) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError("angular_frequencies must be real-valued.")
    try:
        frequencies = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("angular_frequencies must be a non-empty one-dimensional array.") from exc
    if frequencies.ndim != 1 or frequencies.size < 1:
        raise ValueError("angular_frequencies must be a non-empty one-dimensional array.")
    if not np.all(np.isfinite(frequencies)) or np.any(frequencies <= 0.0):
        raise ValueError("angular_frequencies must contain only finite positive values.")
    return _readonly_array(frequencies, dtype=np.float64)


def _frequency_strengths(values: Any, frequency_count: int) -> np.ndarray:
    try:
        strengths = np.asarray(values, dtype=np.complex128)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "source_strengths must be scalar or have one value per frequency."
        ) from exc
    if strengths.ndim == 0:
        strengths = np.full((frequency_count,), strengths.item(), dtype=np.complex128)
    elif strengths.ndim == 1 and strengths.shape == (frequency_count,):
        strengths = np.array(strengths, dtype=np.complex128, copy=True)
    else:
        raise ValueError(
            "source_strengths must be scalar or have shape (num_frequencies,)."
        )
    if not np.all(np.isfinite(strengths)):
        raise ValueError("source_strengths must contain only finite values.")
    strengths.setflags(write=False)
    return strengths


def _finite_timing(value: Any, *, name: str) -> float:
    return _real_scalar(value, name=name, positive=False)


@dataclass(frozen=True)
class MaterialSpec:
    """Solver-neutral homogeneous isotropic material parameters."""

    epsr: float
    sigma: float = 0.0
    mur: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "epsr", _real_scalar(self.epsr, name="epsr", positive=True)
        )
        object.__setattr__(
            self, "sigma", _real_scalar(self.sigma, name="sigma", positive=False)
        )
        object.__setattr__(
            self, "mur", _real_scalar(self.mur, name="mur", positive=True)
        )


@dataclass(frozen=True)
class PairedForwardProblem:
    """A paired source/receiver experiment shared by both forward solvers.

    Source row ``i`` is observed only at receiver row ``i``.  A scalar source
    strength is broadcast over frequency; otherwise exactly one complex
    strength must be supplied per angular frequency.  That frequency strength
    is shared by all source/receiver pairs.
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
        # Kress evaluates the full Cartesian source/receiver matrix before the
        # paired diagonal is selected, so every cross combination must avoid
        # the line-source singularity for a problem usable by both solvers.
        cross_distances = np.linalg.norm(
            receivers[None, :, :] - sources[:, None, :], axis=-1
        )
        if np.any(cross_distances <= 0.0):
            raise ValueError(
                "Every source point must be distinct from every receiver point."
            )
        frequencies = _angular_frequencies(self.angular_frequencies)
        strengths = _frequency_strengths(self.source_strengths, frequencies.size)
        if not isinstance(self.exterior, MaterialSpec):
            raise TypeError("exterior must be a MaterialSpec.")
        if not isinstance(self.interior, MaterialSpec):
            raise TypeError("interior must be a MaterialSpec.")
        eps0 = _real_scalar(self.eps0, name="eps0", positive=True)
        mu0 = _real_scalar(self.mu0, name="mu0", positive=True)

        object.__setattr__(self, "source_points", sources)
        object.__setattr__(self, "receiver_points", receivers)
        object.__setattr__(self, "angular_frequencies", frequencies)
        object.__setattr__(self, "source_strengths", strengths)
        object.__setattr__(self, "eps0", eps0)
        object.__setattr__(self, "mu0", mu0)

    @property
    def num_pairs(self) -> int:
        """Number of paired source/receiver observations."""

        return int(self.source_points.shape[0])

    @property
    def num_frequencies(self) -> int:
        """Number of angular frequencies."""

        return int(self.angular_frequencies.size)


@dataclass(frozen=True)
class PairedForwardResult:
    """Paired complex responses and timings from one selected solver."""

    solver: str
    geometry_build: OrderedSDFGeometryBuild
    scattered_response: np.ndarray
    total_response: np.ndarray
    linear_system_relative_residuals: np.ndarray
    geometry_seconds: float
    forward_seconds: float
    total_seconds: float

    def __post_init__(self) -> None:
        if self.solver not in {"mod", "kress"}:
            raise ValueError("solver must be exactly 'mod' or 'kress'.")
        if not isinstance(self.geometry_build, OrderedSDFGeometryBuild):
            raise TypeError("geometry_build must be an OrderedSDFGeometryBuild.")

        scattered = np.asarray(self.scattered_response, dtype=np.complex128)
        total = np.asarray(self.total_response, dtype=np.complex128)
        if scattered.ndim != 2 or scattered.shape[0] < 1 or scattered.shape[1] < 1:
            raise ValueError(
                "scattered_response must have non-empty shape "
                "(num_pairs, num_frequencies)."
            )
        if total.shape != scattered.shape:
            raise ValueError("total_response must have the same shape as scattered_response.")
        if not np.all(np.isfinite(scattered)) or not np.all(np.isfinite(total)):
            raise ValueError("Forward responses must contain only finite values.")

        if np.iscomplexobj(self.linear_system_relative_residuals):
            raise ValueError("linear_system_relative_residuals must be real-valued.")
        residuals = np.asarray(
            self.linear_system_relative_residuals, dtype=np.float64
        )
        if residuals.shape != (scattered.shape[1],):
            raise ValueError(
                "linear_system_relative_residuals must have shape "
                "(num_frequencies,)."
            )
        if not np.all(np.isfinite(residuals)) or np.any(residuals < 0.0):
            raise ValueError(
                "linear_system_relative_residuals must be finite and non-negative."
            )

        object.__setattr__(
            self, "scattered_response", _readonly_array(scattered, dtype=np.complex128)
        )
        object.__setattr__(
            self, "total_response", _readonly_array(total, dtype=np.complex128)
        )
        object.__setattr__(
            self,
            "linear_system_relative_residuals",
            _readonly_array(residuals, dtype=np.float64),
        )
        for name in ("geometry_seconds", "forward_seconds", "total_seconds"):
            object.__setattr__(
                self, name, _finite_timing(getattr(self, name), name=name)
            )

    @property
    def paired_scattered_response(self) -> np.ndarray:
        """Explicit alias documenting the pairing convention."""

        return self.scattered_response

    @property
    def paired_total_response(self) -> np.ndarray:
        """Explicit alias documenting the pairing convention."""

        return self.total_response

    @property
    def per_frequency_linear_residuals(self) -> np.ndarray:
        """Explicit alias documenting the residual axis."""

        return self.linear_system_relative_residuals


def _material_kwargs(spec: MaterialSpec) -> dict[str, float]:
    return {"epsr": spec.epsr, "sigma": spec.sigma, "mur": spec.mur}


def _validate_vector_response(
    values: Any,
    *,
    name: str,
    num_pairs: int,
) -> np.ndarray:
    result = np.asarray(values, dtype=np.complex128)
    if result.shape != (num_pairs,):
        raise RuntimeError(
            f"{name} must have shape ({num_pairs},); received {result.shape}."
        )
    if not np.all(np.isfinite(result)):
        raise FloatingPointError(f"{name} contains non-finite values.")
    return result


def _validate_matrix_response(
    values: Any,
    *,
    name: str,
    num_pairs: int,
) -> np.ndarray:
    result = np.asarray(values, dtype=np.complex128)
    expected = (num_pairs, num_pairs)
    if result.shape != expected:
        raise RuntimeError(f"{name} must have shape {expected}; received {result.shape}.")
    if not np.all(np.isfinite(result)):
        raise FloatingPointError(f"{name} contains non-finite values.")
    return result


def _validate_solver_residual(value: Any, *, solver: str) -> float:
    residual = _real_scalar(
        value,
        name=f"{solver} linear_system_relative_residual",
        positive=False,
    )
    return residual


def predict_paired_response(
    model: Any,
    problem: PairedForwardProblem,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    solver: str,
) -> PairedForwardResult:
    """Build one ordered geometry and predict paired responses with MOD or Kress.

    ``solver`` accepts exactly the lowercase labels ``"mod"`` and ``"kress"``.
    Geometry extraction is performed once per call.  Kress computes its native
    full source-by-receiver matrices and this seam selects only their paired
    diagonals; MOD already returns paired vectors.  No backend or formulation
    fallback is attempted.
    """

    if not isinstance(problem, PairedForwardProblem):
        raise TypeError("problem must be a PairedForwardProblem.")
    if not isinstance(geometry_config, OrderedSDFGeometryConfig):
        raise TypeError("geometry_config must be an OrderedSDFGeometryConfig.")
    if not isinstance(solver, str) or solver not in {"mod", "kress"}:
        raise ValueError("solver must be exactly 'mod' or 'kress'.")

    total_started = perf_counter()
    geometry_started = perf_counter()
    geometry_build = build_ordered_sdf_geometry(model, geometry_config)
    geometry_seconds = float(perf_counter() - geometry_started)

    scattered_by_frequency: list[np.ndarray] = []
    total_by_frequency: list[np.ndarray] = []
    residuals: list[float] = []
    forward_started = perf_counter()

    if solver == "mod":
        from gpr_bem_mod import (
            Material as ModMaterial,
            solve_ibim_tmz_total_field_batch,
        )

        boundary = ordered_curve_to_mod_boundary(
            geometry_build.curve, geometry_config.bounds
        )
        exterior = ModMaterial(**_material_kwargs(problem.exterior))
        interior = ModMaterial(**_material_kwargs(problem.interior))
        for angular_frequency, source_strength in zip(
            problem.angular_frequencies, problem.source_strengths
        ):
            forward = solve_ibim_tmz_total_field_batch(
                boundary,
                problem.source_points,
                problem.receiver_points,
                float(angular_frequency),
                complex(source_strength),
                exterior=exterior,
                interior=interior,
                eps0=problem.eps0,
                mu0=problem.mu0,
                use_strict_quadrature=True,
                solve_strategy="direct",
                formulation="muller",
                normal_derivative_scheme="analytic_extrapolated",
                backend="numpy",
                complex_precision="complex128",
            )
            scattered_by_frequency.append(
                _validate_vector_response(
                    forward.scattered_receiver,
                    name="MOD scattered_receiver",
                    num_pairs=problem.num_pairs,
                )
            )
            total_by_frequency.append(
                _validate_vector_response(
                    forward.total_receiver,
                    name="MOD total_receiver",
                    num_pairs=problem.num_pairs,
                )
            )
            residuals.append(
                _validate_solver_residual(
                    forward.linear_system_relative_residual, solver="MOD"
                )
            )
    else:
        from gpr_bem_kress import (
            KressSolveConfig,
            Material as KressMaterial,
            solve_kress_tmz_total_field_batch,
        )

        exterior = KressMaterial(**_material_kwargs(problem.exterior))
        interior = KressMaterial(**_material_kwargs(problem.interior))
        solve_config = KressSolveConfig(compute_condition_number=False)
        for angular_frequency, source_strength in zip(
            problem.angular_frequencies, problem.source_strengths
        ):
            forward = solve_kress_tmz_total_field_batch(
                geometry_build.curve,
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
            scattered_matrix = _validate_matrix_response(
                forward.scattered_receiver,
                name="Kress scattered_receiver",
                num_pairs=problem.num_pairs,
            )
            total_matrix = _validate_matrix_response(
                forward.total_receiver,
                name="Kress total_receiver",
                num_pairs=problem.num_pairs,
            )
            scattered_by_frequency.append(np.diag(scattered_matrix))
            total_by_frequency.append(np.diag(total_matrix))
            residuals.append(
                _validate_solver_residual(
                    forward.linear_system_relative_residual, solver="Kress"
                )
            )

    forward_seconds = float(perf_counter() - forward_started)
    scattered_response = np.stack(scattered_by_frequency, axis=1)
    total_response = np.stack(total_by_frequency, axis=1)
    return PairedForwardResult(
        solver=solver,
        geometry_build=geometry_build,
        scattered_response=scattered_response,
        total_response=total_response,
        linear_system_relative_residuals=np.asarray(residuals, dtype=np.float64),
        geometry_seconds=geometry_seconds,
        forward_seconds=forward_seconds,
        total_seconds=float(perf_counter() - total_started),
    )


__all__ = [
    "MaterialSpec",
    "PairedForwardProblem",
    "PairedForwardResult",
    "predict_paired_response",
]
