"""Method B: Fourier least squares plus native arc-length refit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import operator
import time
from typing import Protocol

import numpy as np

from ordered_boundary import (
    BoundaryValidationConfig,
    CurveProvenance2D,
    validate_periodic_parameterization,
)

from .arclength import ArcLengthConfig, reparameterize_by_arclength
from .representations import FourierBoundary, fit_fourier_least_squares
from .results import MethodResult


class ProjectedLoopLike(Protocol):
    parameters: np.ndarray
    projected_points: np.ndarray


@dataclass(frozen=True)
class MethodBConfig:
    """All bandwidth, least-squares, reparameterization, and validation choices."""

    bandwidth: int = 16
    least_squares_rcond: float | None = None
    arclength: ArcLengthConfig = ArcLengthConfig()
    validation: BoundaryValidationConfig = BoundaryValidationConfig(
        num_samples_per_component=1024
    )
    def __post_init__(self) -> None:
        if isinstance(self.bandwidth, bool):
            raise TypeError("bandwidth must be an integer, not bool.")
        try:
            bandwidth = operator.index(self.bandwidth)
        except TypeError as exc:
            raise TypeError("bandwidth must be an integer.") from exc
        if bandwidth < 1:
            raise ValueError("bandwidth must be at least one.")
        object.__setattr__(self, "bandwidth", bandwidth)
        if self.least_squares_rcond is not None:
            rcond = float(self.least_squares_rcond)
            if not np.isfinite(rcond) or rcond < 0.0:
                raise ValueError(
                    "least_squares_rcond must be finite and non-negative when supplied."
                )
            object.__setattr__(self, "least_squares_rcond", rcond)
        if not isinstance(self.arclength, ArcLengthConfig):
            raise TypeError("arclength must be ArcLengthConfig.")
        if not isinstance(self.validation, BoundaryValidationConfig):
            raise TypeError("validation must be BoundaryValidationConfig.")


def fit_method_b_from_samples(
    parameters,
    projected_points,
    *,
    config: MethodBConfig | None = None,
    component_id: str = "component-0",
    source_identifier: str | None = None,
    projection_residual: float | None = None,
) -> MethodResult:
    """Fit Method B to the already shared/projected front-end samples."""

    settings = MethodBConfig() if config is None else config
    if not isinstance(settings, MethodBConfig):
        raise TypeError("config must be MethodBConfig.")
    point_values = np.asarray(projected_points, dtype=np.float64)
    parameter_values = np.asarray(parameters, dtype=np.float64)
    start = time.perf_counter()

    initial_provenance = CurveProvenance2D(
        source_kind="sdf_fourier_least_squares",
        source_identifier=source_identifier,
        projection_residual=projection_residual,
    )
    initial_fit = fit_fourier_least_squares(
        parameter_values,
        point_values,
        bandwidth=settings.bandwidth,
        component_id=component_id,
        name="method_b_fourier_least_squares",
        rcond=settings.least_squares_rcond,
        provenance=initial_provenance,
    )
    initial = initial_fit.boundary.with_provenance(
        CurveProvenance2D(
            source_kind="sdf_fourier_least_squares",
            source_identifier=source_identifier,
            projection_residual=projection_residual,
            fit_residual=initial_fit.residual.rms,
        )
    )
    initial_parameterization = initial.to_parameterization()
    initial_validation = validate_periodic_parameterization(
        initial_parameterization,
        settings.validation,
        raise_on_error=True,
    )

    refit_count = (
        int(parameter_values.size)
        if settings.arclength.refit_sample_count is None
        else settings.arclength.refit_sample_count
    )
    minimum_refit_count = 2 * settings.bandwidth + 1
    if refit_count < minimum_refit_count:
        raise ValueError(
            "Arc-length Fourier refit requires at least "
            f"2 * bandwidth + 1 = {minimum_refit_count} samples."
        )
    final_fit_holder = []

    def refit_factory(refit_parameters: np.ndarray, refit_points: np.ndarray) -> FourierBoundary:
        fitted = fit_fourier_least_squares(
            refit_parameters,
            refit_points,
            bandwidth=settings.bandwidth,
            component_id=component_id,
            name="method_b_fourier_least_squares",
            rcond=settings.least_squares_rcond,
            provenance=initial.provenance,
        )
        final_fit_holder.append(fitted)
        return fitted.boundary

    arclength_result = reparameterize_by_arclength(
        initial_parameterization,
        refit_factory,
        dense_n=settings.arclength.dense_resolution,
        output_n=refit_count,
        validation_n=settings.arclength.validation_resolution,
    )
    if len(final_fit_holder) != 1:
        raise RuntimeError("Arc-length refit factory was expected to run exactly once.")
    final_fit = final_fit_holder[0]
    final_provenance = CurveProvenance2D(
        source_kind="sdf_fourier_least_squares",
        source_identifier=source_identifier,
        projection_residual=projection_residual,
        fit_residual=arclength_result.diagnostics.maximum_refit_displacement,
    )
    final_representation = arclength_result.representation.with_provenance(final_provenance)
    final_parameterization = final_representation.to_parameterization()
    final_validation = validate_periodic_parameterization(
        final_parameterization,
        settings.validation,
        raise_on_error=True,
    )
    runtime = time.perf_counter() - start
    return MethodResult(
        method_name="B-fourier-least-squares",
        status="success",
        representation=final_representation,
        parameterization=final_parameterization,
        validation=final_validation,
        input_fit_residual=initial_fit.residual,
        arc_length=arclength_result.diagnostics,
        runtime_seconds=runtime,
        diagnostics={
            "initial_validation": initial_validation.to_dict(),
            "input_sample_count": int(parameter_values.size),
            "bandwidth": settings.bandwidth,
            "initial_least_squares": asdict(initial_fit.diagnostics),
            "final_least_squares": asdict(final_fit.diagnostics),
            "final_native_refit_residual": asdict(final_fit.residual),
            "config": {
                "bandwidth": settings.bandwidth,
                "least_squares_rcond": settings.least_squares_rcond,
                "arclength": asdict(settings.arclength),
                "validation": asdict(settings.validation),
            },
        },
    )


def fit_method_b(
    frontend: ProjectedLoopLike,
    *,
    config: MethodBConfig | None = None,
    component_id: str = "component-0",
    source_identifier: str | None = None,
    projection_residual: float | None = None,
) -> MethodResult:
    """Fit Method B from a single-component shared front-end result."""

    try:
        parameters = frontend.parameters
        points = frontend.projected_points
    except AttributeError as exc:
        raise TypeError(
            "frontend must expose parameters and projected_points for one component."
        ) from exc
    return fit_method_b_from_samples(
        parameters,
        points,
        config=config,
        component_id=component_id,
        source_identifier=source_identifier,
        projection_residual=projection_residual,
    )
