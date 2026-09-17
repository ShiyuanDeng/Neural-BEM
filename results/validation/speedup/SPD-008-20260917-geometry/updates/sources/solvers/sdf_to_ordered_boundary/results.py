"""Immutable result records shared by SDF-to-boundary fitting methods."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping

import numpy as np

from ordered_boundary import (
    CurveGeometryReport,
    PeriodicParameterization2D,
)


MethodStatus = Literal["success", "failed", "fallback"]


@dataclass(frozen=True)
class ResidualDiagnostics:
    """Maximum and root-mean-square Euclidean residuals."""

    maximum: float
    rms: float

    def __post_init__(self) -> None:
        for name in ("maximum", "rms"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class LeastSquaresDiagnostics:
    """Conditioning information from a real Fourier least-squares solve."""

    num_samples: int
    num_unknowns: int
    rank: int
    condition_number: float
    singular_values: tuple[float, ...]

    def __post_init__(self) -> None:
        for name in ("num_samples", "num_unknowns", "rank"):
            value = int(getattr(self, name))
            if value < 0:
                raise ValueError(f"{name} must be non-negative.")
            object.__setattr__(self, name, value)
        condition = float(self.condition_number)
        if np.isnan(condition) or condition < 0.0:
            raise ValueError("condition_number must be non-negative and not NaN.")
        object.__setattr__(self, "condition_number", condition)
        singular_values = tuple(float(value) for value in self.singular_values)
        if any(not np.isfinite(value) or value < 0.0 for value in singular_values):
            raise ValueError("singular_values must be finite and non-negative.")
        object.__setattr__(self, "singular_values", singular_values)


@dataclass(frozen=True)
class ArcLengthDiagnostics:
    """Geometry and speed changes introduced by arc-length refitting."""

    dense_resolution: int
    refit_sample_count: int
    validation_resolution: int
    perimeter_before: float
    perimeter_after: float
    minimum_speed_before: float
    maximum_speed_before: float
    speed_ratio_before: float
    minimum_speed_after: float
    maximum_speed_after: float
    speed_ratio_after: float
    maximum_refit_displacement: float
    rms_refit_displacement: float

    def __post_init__(self) -> None:
        for name in ("dense_resolution", "refit_sample_count", "validation_resolution"):
            value = int(getattr(self, name))
            if value < 3:
                raise ValueError(f"{name} must be at least 3.")
            object.__setattr__(self, name, value)
        for name in (
            "perimeter_before",
            "perimeter_after",
            "minimum_speed_before",
            "maximum_speed_before",
            "speed_ratio_before",
            "minimum_speed_after",
            "maximum_speed_after",
            "speed_ratio_after",
            "maximum_refit_displacement",
            "rms_refit_displacement",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class ArcLengthReparameterizationResult:
    """A native representation refitted to an approximate arc-length map."""

    representation: Any
    parameterization: PeriodicParameterization2D
    diagnostics: ArcLengthDiagnostics

    def __post_init__(self) -> None:
        if not isinstance(self.parameterization, PeriodicParameterization2D):
            raise TypeError("parameterization must be a PeriodicParameterization2D.")
        if not isinstance(self.diagnostics, ArcLengthDiagnostics):
            raise TypeError("diagnostics must be ArcLengthDiagnostics.")


@dataclass(frozen=True)
class MethodResult:
    """One method outcome without coupling geometry to experiment I/O.

    ``representation`` owns the spline/Fourier coefficients.  The corresponding
    continuous ``parameterization`` is the shared ordered-boundary contract.
    Optimization histories, front-end data, and serialised arrays belong to
    higher-level experiment records rather than either geometry object.
    """

    method_name: str
    status: MethodStatus
    representation: Any | None
    parameterization: PeriodicParameterization2D | None
    validation: CurveGeometryReport | None
    input_fit_residual: ResidualDiagnostics | None
    arc_length: ArcLengthDiagnostics | None
    runtime_seconds: float
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        method_name = str(self.method_name).strip()
        if not method_name:
            raise ValueError("method_name must be a non-empty string.")
        if self.status not in ("success", "failed", "fallback"):
            raise ValueError("status must be 'success', 'failed', or 'fallback'.")
        runtime = float(self.runtime_seconds)
        if not np.isfinite(runtime) or runtime < 0.0:
            raise ValueError("runtime_seconds must be finite and non-negative.")
        if self.status == "success":
            if self.representation is None or self.parameterization is None:
                raise ValueError("Successful results require a representation and parameterization.")
            if self.validation is None or not self.validation.valid:
                raise ValueError("Successful results require a valid geometry report.")
            if self.failure_reason is not None:
                raise ValueError("Successful results cannot have a failure_reason.")
        elif self.failure_reason is None or not str(self.failure_reason).strip():
            raise ValueError("Failed or fallback results require a failure_reason.")
        if self.parameterization is not None and not isinstance(
            self.parameterization, PeriodicParameterization2D
        ):
            raise TypeError("parameterization must be a PeriodicParameterization2D.")
        if self.validation is not None and not isinstance(self.validation, CurveGeometryReport):
            raise TypeError("validation must be a CurveGeometryReport.")
        if self.input_fit_residual is not None and not isinstance(
            self.input_fit_residual, ResidualDiagnostics
        ):
            raise TypeError("input_fit_residual must be ResidualDiagnostics.")
        if self.arc_length is not None and not isinstance(self.arc_length, ArcLengthDiagnostics):
            raise TypeError("arc_length must be ArcLengthDiagnostics.")
        diagnostics = MappingProxyType(dict(self.diagnostics))
        object.__setattr__(self, "method_name", method_name)
        object.__setattr__(self, "runtime_seconds", runtime)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.failure_reason is not None:
            object.__setattr__(self, "failure_reason", str(self.failure_reason).strip())

    @property
    def succeeded(self) -> bool:
        return self.status == "success"

    def to_summary_dict(self) -> dict[str, Any]:
        """Return JSON-oriented scalar diagnostics, excluding curve objects."""

        payload: dict[str, Any] = {
            "method_name": self.method_name,
            "status": self.status,
            "runtime_seconds": self.runtime_seconds,
            "failure_reason": self.failure_reason,
            "diagnostics": dict(self.diagnostics),
        }
        if self.validation is not None:
            payload["validation"] = self.validation.to_dict()
        if self.input_fit_residual is not None:
            payload["input_fit_residual"] = asdict(self.input_fit_residual)
        if self.arc_length is not None:
            payload["arc_length"] = asdict(self.arc_length)
        return payload


# Descriptive compatibility name for callers that prefer the longer spelling.
BoundaryMethodResult = MethodResult
