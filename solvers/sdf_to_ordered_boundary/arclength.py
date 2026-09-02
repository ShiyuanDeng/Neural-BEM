"""Shared numerical arc-length map, inversion, and native-representation refit."""

from __future__ import annotations

from dataclasses import dataclass
import operator
from typing import Any, Callable, Protocol, TypeVar

import numpy as np

from ordered_boundary import PeriodicParameterization2D

from .results import (
    ArcLengthDiagnostics,
    ArcLengthReparameterizationResult,
)


class NativeBoundaryRepresentation(Protocol):
    def to_parameterization(self) -> PeriodicParameterization2D: ...


RepresentationT = TypeVar("RepresentationT", bound=NativeBoundaryRepresentation)
RefitFactory = Callable[[np.ndarray, np.ndarray], RepresentationT]


@dataclass(frozen=True)
class ArcLengthConfig:
    """Numerical resolutions for one arc-length inversion and native refit."""

    dense_resolution: int = 4096
    refit_sample_count: int | None = None
    validation_resolution: int = 2048

    def __post_init__(self) -> None:
        for name in ("dense_resolution", "validation_resolution"):
            value = _integer_at_least(getattr(self, name), name=name, minimum=16)
            object.__setattr__(self, name, value)
        if self.refit_sample_count is not None:
            object.__setattr__(
                self,
                "refit_sample_count",
                _integer_at_least(
                    self.refit_sample_count,
                    name="refit_sample_count",
                    minimum=3,
                ),
            )


def _integer_at_least(value, *, name: str, minimum: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return result


def _as_parameterization(curve: Any) -> PeriodicParameterization2D:
    if isinstance(curve, PeriodicParameterization2D):
        return curve
    conversion = getattr(curve, "to_parameterization", None)
    if not callable(conversion):
        raise TypeError(
            "curve must be a PeriodicParameterization2D or expose to_parameterization()."
        )
    parameterization = conversion()
    if not isinstance(parameterization, PeriodicParameterization2D):
        raise TypeError("to_parameterization() must return PeriodicParameterization2D.")
    return parameterization


def _integrated_arclength_map(
    curve: PeriodicParameterization2D,
    resolution: int,
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    """Return endpoint-inclusive ``t``, cumulative length, perimeter, and speed."""

    origin = curve.parameter_origin
    period = curve.period
    parameters = origin + period * np.arange(resolution + 1, dtype=np.float64) / resolution
    evaluation = curve.evaluate(parameters, wrap=False)
    speeds = np.linalg.norm(evaluation.first_derivatives, axis=-1)
    if not np.all(np.isfinite(speeds)) or np.any(speeds <= 0.0):
        raise ValueError("Arc-length reparameterization requires finite positive speed.")
    step = period / resolution
    increments = 0.5 * step * (speeds[:-1] + speeds[1:])
    cumulative = np.concatenate(([0.0], np.cumsum(increments)))
    perimeter = float(cumulative[-1])
    if not np.isfinite(perimeter) or perimeter <= 0.0:
        raise ValueError("The numerically integrated perimeter must be finite and positive.")
    if np.any(np.diff(cumulative) <= 0.0):
        raise ValueError("The sampled arc-length map is not strictly monotone.")
    return parameters, cumulative, perimeter, speeds


def _inverse_parameters(
    target_parameters: np.ndarray,
    *,
    source_parameters: np.ndarray,
    cumulative_length: np.ndarray,
    perimeter: float,
    parameter_origin: float,
    period: float,
) -> np.ndarray:
    target_length = (
        (target_parameters - parameter_origin) / period * perimeter
    )
    return np.interp(target_length, cumulative_length, source_parameters)


def _speed_summary(speeds: np.ndarray) -> tuple[float, float, float]:
    minimum = float(np.min(speeds))
    maximum = float(np.max(speeds))
    if minimum <= 0.0:
        raise ValueError("Speed must remain positive.")
    return minimum, maximum, maximum / minimum


def reparameterize_by_arclength(
    curve: PeriodicParameterization2D | NativeBoundaryRepresentation,
    refit_factory: RefitFactory[RepresentationT],
    *,
    dense_n: int,
    output_n: int,
    validation_n: int | None = None,
) -> ArcLengthReparameterizationResult:
    """Approximate arc length, invert it, and refit in the caller's native basis.

    The refit factory receives uniform parameters on the original period and
    positions on the original geometric image at the corresponding inverse
    arc-length parameters.  Its returned representation is the authoritative
    output.  Displacement diagnostics compare that refit with the intended
    reparameterized source curve, not with equal source parameter values.
    """

    dense_resolution = _integer_at_least(dense_n, name="dense_n", minimum=16)
    refit_count = _integer_at_least(output_n, name="output_n", minimum=3)
    validation_resolution = _integer_at_least(
        dense_resolution if validation_n is None else validation_n,
        name="validation_n",
        minimum=16,
    )
    source = _as_parameterization(curve)
    source_parameters, cumulative, perimeter_before, source_speeds = (
        _integrated_arclength_map(source, dense_resolution)
    )
    origin = source.parameter_origin
    period = source.period

    uniform_refit_parameters = (
        origin + period * np.arange(refit_count, dtype=np.float64) / refit_count
    )
    inverse_refit_parameters = _inverse_parameters(
        uniform_refit_parameters,
        source_parameters=source_parameters,
        cumulative_length=cumulative,
        perimeter=perimeter_before,
        parameter_origin=origin,
        period=period,
    )
    refit_points = source.evaluate(inverse_refit_parameters, wrap=False).points
    representation = refit_factory(uniform_refit_parameters, refit_points)
    parameterization = _as_parameterization(representation)
    if not np.isclose(parameterization.period, period, rtol=0.0, atol=1.0e-13 * period):
        raise ValueError("The refitted representation changed the curve period.")
    if not np.isclose(
        parameterization.parameter_origin,
        origin,
        rtol=0.0,
        atol=1.0e-13 * period,
    ):
        raise ValueError("The refitted representation changed parameter_origin.")

    uniform_validation_parameters = (
        origin
        + period * np.arange(validation_resolution, dtype=np.float64) / validation_resolution
    )
    inverse_validation_parameters = _inverse_parameters(
        uniform_validation_parameters,
        source_parameters=source_parameters,
        cumulative_length=cumulative,
        perimeter=perimeter_before,
        parameter_origin=origin,
        period=period,
    )
    intended_points = source.evaluate(inverse_validation_parameters, wrap=False).points
    final_evaluation = parameterization.evaluate(uniform_validation_parameters, wrap=False)
    displacement = np.linalg.norm(final_evaluation.points - intended_points, axis=-1)
    final_speeds = np.linalg.norm(final_evaluation.first_derivatives, axis=-1)

    _, _, perimeter_after, _ = _integrated_arclength_map(
        parameterization,
        validation_resolution,
    )
    minimum_before, maximum_before, ratio_before = _speed_summary(source_speeds[:-1])
    minimum_after, maximum_after, ratio_after = _speed_summary(final_speeds)
    diagnostics = ArcLengthDiagnostics(
        dense_resolution=dense_resolution,
        refit_sample_count=refit_count,
        validation_resolution=validation_resolution,
        perimeter_before=perimeter_before,
        perimeter_after=perimeter_after,
        minimum_speed_before=minimum_before,
        maximum_speed_before=maximum_before,
        speed_ratio_before=ratio_before,
        minimum_speed_after=minimum_after,
        maximum_speed_after=maximum_after,
        speed_ratio_after=ratio_after,
        maximum_refit_displacement=float(np.max(displacement)),
        rms_refit_displacement=float(np.sqrt(np.mean(displacement**2))),
    )
    return ArcLengthReparameterizationResult(
        representation=representation,
        parameterization=parameterization,
        diagnostics=diagnostics,
    )
