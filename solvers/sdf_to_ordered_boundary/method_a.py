"""Method A: projected periodic cubic spline plus arc-length refit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Protocol

import numpy as np

from ordered_boundary import (
    BoundaryValidationConfig,
    CurveProvenance2D,
    validate_periodic_parameterization,
)

from .arclength import ArcLengthConfig, reparameterize_by_arclength
from .representations import (
    PeriodicSplineBoundary,
    spline_interpolation_residual,
)
from .results import MethodResult


class ProjectedLoopLike(Protocol):
    parameters: np.ndarray
    projected_points: np.ndarray


@dataclass(frozen=True)
class MethodAConfig:
    """All representation and validation choices for the spline baseline."""

    arclength: ArcLengthConfig = ArcLengthConfig()
    validation: BoundaryValidationConfig = BoundaryValidationConfig(
        num_samples_per_component=1024,
        # A periodic cubic is C2, not globally analytic.  The validator's
        # independent five-point second derivative crosses knots and therefore
        # converges only linearly at those probes; keep this method-specific and
        # configurable rather than weakening the shared geometry default.
        derivative_relative_tolerance=5.0e-3,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.arclength, ArcLengthConfig):
            raise TypeError("arclength must be ArcLengthConfig.")
        if not isinstance(self.validation, BoundaryValidationConfig):
            raise TypeError("validation must be BoundaryValidationConfig.")


def fit_method_a_from_samples(
    parameters,
    projected_points,
    *,
    config: MethodAConfig | None = None,
    component_id: str = "component-0",
    source_identifier: str | None = None,
    projection_residual: float | None = None,
) -> MethodResult:
    """Fit Method A to the already shared/projected front-end samples."""

    settings = MethodAConfig() if config is None else config
    if not isinstance(settings, MethodAConfig):
        raise TypeError("config must be MethodAConfig.")
    point_values = np.asarray(projected_points, dtype=np.float64)
    parameter_values = np.asarray(parameters, dtype=np.float64)
    start = time.perf_counter()

    initial_provenance = CurveProvenance2D(
        source_kind="sdf_periodic_spline",
        source_identifier=source_identifier,
        projection_residual=projection_residual,
    )
    initial = PeriodicSplineBoundary.interpolate(
        parameter_values,
        point_values,
        component_id=component_id,
        name="method_a_periodic_spline",
        provenance=initial_provenance,
    )
    input_residual = spline_interpolation_residual(
        initial,
        parameter_values,
        point_values,
    )
    initial = initial.with_provenance(
        CurveProvenance2D(
            source_kind="sdf_periodic_spline",
            source_identifier=source_identifier,
            projection_residual=projection_residual,
            fit_residual=input_residual.rms,
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

    def refit_factory(refit_parameters: np.ndarray, refit_points: np.ndarray):
        return PeriodicSplineBoundary.interpolate(
            refit_parameters,
            refit_points,
            component_id=component_id,
            name="method_a_periodic_spline",
            provenance=initial.provenance,
        )

    arclength_result = reparameterize_by_arclength(
        initial_parameterization,
        refit_factory,
        dense_n=settings.arclength.dense_resolution,
        output_n=refit_count,
        validation_n=settings.arclength.validation_resolution,
    )
    final_provenance = CurveProvenance2D(
        source_kind="sdf_periodic_spline",
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
        method_name="A-periodic-cubic-spline",
        status="success",
        representation=final_representation,
        parameterization=final_parameterization,
        validation=final_validation,
        input_fit_residual=input_residual,
        arc_length=arclength_result.diagnostics,
        runtime_seconds=runtime,
        diagnostics={
            "initial_validation": initial_validation.to_dict(),
            "input_sample_count": int(parameter_values.size),
            "final_interval_count": final_representation.num_intervals,
            "config": {
                "arclength": asdict(settings.arclength),
                "validation": asdict(settings.validation),
            },
        },
    )


def fit_method_a(
    frontend: ProjectedLoopLike,
    *,
    config: MethodAConfig | None = None,
    component_id: str = "component-0",
    source_identifier: str | None = None,
    projection_residual: float | None = None,
) -> MethodResult:
    """Fit Method A from a single-component shared front-end result."""

    try:
        parameters = frontend.parameters
        points = frontend.projected_points
    except AttributeError as exc:
        raise TypeError(
            "frontend must expose parameters and projected_points for one component."
        ) from exc
    return fit_method_a_from_samples(
        parameters,
        points,
        config=config,
        component_id=component_id,
        source_identifier=source_identifier,
        projection_residual=projection_residual,
    )
