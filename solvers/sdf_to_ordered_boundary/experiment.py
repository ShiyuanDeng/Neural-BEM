"""Controlled A/B/C experiments for implicit-to-parametric boundaries.

This module is an isolated research orchestrator.  It imports no active BIE
solver and never feeds its outputs into a forward, adjoint, or inverse path.
For each ``(shape, grid_shape, projected_sample_count)`` case it constructs one
shared front-end result, fits Method A once, and fits Methods B and C once per
configured Fourier bandwidth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field as dataclass_field, replace
import operator
from pathlib import Path
import re
import time
from typing import Any, Mapping, Sequence

import numpy as np

from ordered_boundary import (
    BoundaryValidationConfig,
    PeriodicParameterization2D,
)

from .arclength import ArcLengthConfig
from .artifacts import (
    plot_boundary_diagnostics,
    write_metrics_csv,
    write_npz,
    write_strict_json,
)
from .fields import (
    CircleSDF,
    CountedImplicitField2D,
    EllipseLevelSet,
    FieldEvaluationCounts,
    ImplicitField2D,
    RadialFourierLevelSet,
)
from .frontend import (
    FrontendConfig,
    FrontendResult,
    ProjectionConfig,
    prepare_single_component,
)
from .method_a import MethodAConfig, fit_method_a
from .method_b import MethodBConfig, fit_method_b
from .method_c import (
    MethodCConfig,
    RefinementStage,
    RefinementWeights,
    fit_method_c,
)
from .metrics import (
    BoundaryMetricConfig,
    BoundaryMetrics,
    coordinate_spectrum,
    evaluate_field_gradients,
    evaluate_field_values,
    sample_parameterization,
    compute_boundary_metrics,
)
from .representations import FourierBoundary, PeriodicSplineBoundary
from .results import MethodResult


_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _positive_integer(value: Any, *, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return result


def _counts_dict(counts: FieldEvaluationCounts | None) -> dict[str, int] | None:
    return None if counts is None else asdict(counts)


@dataclass(frozen=True)
class ComparisonShape:
    """One analytic field/reference pair and its explicit physical box."""

    name: str
    field: ImplicitField2D
    reference: PeriodicParameterization2D
    bounds: tuple[tuple[float, float], tuple[float, float]]
    winding_test_points: tuple[tuple[float, float], ...]
    description: str
    parameters: Mapping[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        if not _SAFE_NAME.match(name):
            raise ValueError("shape name must use only letters, digits, underscores, and hyphens.")
        if not isinstance(self.field, ImplicitField2D):
            raise TypeError("field must implement ImplicitField2D.")
        if not isinstance(self.reference, PeriodicParameterization2D):
            raise TypeError("reference must be PeriodicParameterization2D.")
        bounds = np.asarray(self.bounds, dtype=np.float64)
        if bounds.shape != (2, 2) or not np.all(np.isfinite(bounds)):
            raise ValueError("bounds must be finite ((xmin, ymin), (xmax, ymax)).")
        if np.any(bounds[1] <= bounds[0]):
            raise ValueError("shape upper bounds must exceed lower bounds.")
        test_points = tuple(tuple(float(value) for value in point) for point in self.winding_test_points)
        if any(len(point) != 2 or not np.all(np.isfinite(point)) for point in test_points):
            raise ValueError("winding_test_points must contain finite 2D points.")
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "bounds",
            (
                (float(bounds[0, 0]), float(bounds[0, 1])),
                (float(bounds[1, 0]), float(bounds[1, 1])),
            ),
        )
        object.__setattr__(self, "winding_test_points", test_points)
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "parameters", dict(self.parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "field_name": str(getattr(self.field, "name", type(self.field).__name__)),
            "is_signed_distance": bool(getattr(self.field, "is_signed_distance", False)),
            "sign_convention": str(getattr(self.field, "sign_convention", "unspecified")),
            "bounds": self.bounds,
            "winding_test_points": self.winding_test_points,
            "description": self.description,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class ComparisonProfile:
    """Complete controlled sweep definition, excluding shape-specific bounds."""

    name: str
    grid_shapes: tuple[tuple[int, int], ...]
    projected_sample_counts: tuple[int, ...]
    bandwidths: tuple[int, ...]
    projection: ProjectionConfig
    second_resample_and_project: bool
    method_a: MethodAConfig
    method_b_template: MethodBConfig
    method_c: MethodCConfig
    metrics: BoundaryMetricConfig

    def __post_init__(self) -> None:
        name = str(self.name).strip().lower()
        if not _SAFE_NAME.match(name):
            raise ValueError("profile name must be filesystem-safe.")
        grid_shapes = []
        for index, shape in enumerate(self.grid_shapes):
            if len(shape) != 2:
                raise ValueError("Each grid shape must be (ny, nx).")
            grid_shapes.append(
                (
                    _positive_integer(shape[0], name=f"grid_shapes[{index}][0]", minimum=2),
                    _positive_integer(shape[1], name=f"grid_shapes[{index}][1]", minimum=2),
                )
            )
        sample_counts = tuple(
            _positive_integer(value, name="projected_sample_counts", minimum=8)
            for value in self.projected_sample_counts
        )
        bandwidths = tuple(
            _positive_integer(value, name="bandwidths", minimum=1)
            for value in self.bandwidths
        )
        if not grid_shapes or not sample_counts or not bandwidths:
            raise ValueError("Profile sweep axes cannot be empty.")
        if len(set(grid_shapes)) != len(grid_shapes):
            raise ValueError("grid_shapes must not contain duplicates.")
        if len(set(sample_counts)) != len(sample_counts):
            raise ValueError("projected_sample_counts must not contain duplicates.")
        if len(set(bandwidths)) != len(bandwidths):
            raise ValueError("bandwidths must not contain duplicates.")
        for expected_type, value, label in (
            (ProjectionConfig, self.projection, "projection"),
            (MethodAConfig, self.method_a, "method_a"),
            (MethodBConfig, self.method_b_template, "method_b_template"),
            (MethodCConfig, self.method_c, "method_c"),
            (BoundaryMetricConfig, self.metrics, "metrics"),
        ):
            if not isinstance(value, expected_type):
                raise TypeError(f"{label} must be {expected_type.__name__}.")
        if not isinstance(self.second_resample_and_project, (bool, np.bool_)):
            raise TypeError("second_resample_and_project must be boolean.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "grid_shapes", tuple(grid_shapes))
        object.__setattr__(self, "projected_sample_counts", sample_counts)
        object.__setattr__(self, "bandwidths", bandwidths)
        object.__setattr__(
            self,
            "second_resample_and_project",
            bool(self.second_resample_and_project),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentRunRecord:
    """One persisted method row, with continuous geometry retained in memory."""

    run_id: str
    profile_name: str
    frontend_id: str
    shape_name: str
    grid_shape: tuple[int, int]
    projected_sample_count: int
    method_label: str
    bandwidth: int | None
    method_result: MethodResult
    metrics: BoundaryMetrics | None
    metrics_failure_reason: str | None
    frontend_runtime_seconds: float
    initializer_runtime_seconds: float
    frontend_field_counts: FieldEvaluationCounts | None
    initializer_field_counts: FieldEvaluationCounts | None
    method_field_counts: FieldEvaluationCounts | None
    metrics_field_counts: FieldEvaluationCounts | None
    artifact_paths: Mapping[str, str]

    @property
    def parameterization(self) -> PeriodicParameterization2D | None:
        return self.method_result.parameterization

    @property
    def status(self) -> str:
        return self.method_result.status

    @property
    def failure_reason(self) -> str | None:
        return self.method_result.failure_reason

    @property
    def total_converter_runtime_seconds(self) -> float:
        return (
            self.frontend_runtime_seconds
            + self.initializer_runtime_seconds
            + self.method_result.runtime_seconds
        )

    def scalar_metric_aliases(self) -> dict[str, Any]:
        """Return the compact comparison columns requested by the study.

        The complete metric hierarchy remains authoritative and is retained in
        ``metrics``.  These aliases make the primary comparison table usable
        without embedding choices such as which reference-set norm represents
        the requested single discrepancy column in notebook code.
        """

        metrics = self.metrics
        if metrics is None:
            return {
                "max_sdf_residual": None,
                "rms_sdf_residual": None,
                "minimum_speed": None,
                "speed_ratio": None,
                "self_intersections": None,
                "area": None,
                "perimeter": None,
                "reference_contour_discrepancy": None,
                "normal_discrepancy": None,
                "coefficient_tail": None,
                "coefficient_tail_order_1": None,
                "coefficient_tail_order_2": None,
            }
        return {
            "max_sdf_residual": (
                None
                if metrics.sdf_residual is None
                else metrics.sdf_residual.maximum_absolute
            ),
            "rms_sdf_residual": (
                None if metrics.sdf_residual is None else metrics.sdf_residual.rms
            ),
            "minimum_speed": metrics.speed.minimum,
            "speed_ratio": metrics.speed.ratio,
            "self_intersections": metrics.topology.sampled_self_intersection_count,
            "area": metrics.integral_geometry.signed_area,
            "perimeter": metrics.integral_geometry.perimeter,
            "reference_contour_discrepancy": (
                None
                if metrics.reference_set is None
                else metrics.reference_set.symmetric_hausdorff
            ),
            "normal_discrepancy": (
                None
                if metrics.reference_set is None
                else metrics.reference_set.normal_angle_maximum_radians
            ),
            "coefficient_tail": metrics.spectral_tail.order_0,
            "coefficient_tail_order_1": metrics.spectral_tail.order_1,
            "coefficient_tail_order_2": metrics.spectral_tail.order_2,
        }

    def _identity_and_accounting_aliases(self) -> dict[str, Any]:
        counts = self.frontend_field_counts
        converter_counts = tuple(
            item
            for item in (
                self.frontend_field_counts,
                self.initializer_field_counts,
                self.method_field_counts,
            )
            if item is not None
        )

        def total(name: str) -> int | None:
            return (
                sum(int(getattr(item, name)) for item in converter_counts)
                if converter_counts
                else None
            )

        return {
            "shape": self.shape_name,
            "grid_resolution": f"{self.grid_shape[0]}x{self.grid_shape[1]}",
            "projected_samples": self.projected_sample_count,
            "method": self.method_label,
            "shared_frontend_id": self.frontend_id,
            "runtime_seconds": self.total_converter_runtime_seconds,
            "frontend_value_calls": None if counts is None else counts.value_calls,
            "frontend_value_points": None if counts is None else counts.value_points,
            "frontend_gradient_calls": None if counts is None else counts.gradient_calls,
            "frontend_gradient_points": None if counts is None else counts.gradient_points,
            "converter_value_calls": total("value_calls"),
            "converter_value_points": total("value_points"),
            "converter_gradient_calls": total("gradient_calls"),
            "converter_gradient_points": total("gradient_points"),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "profile_name": self.profile_name,
            "frontend_id": self.frontend_id,
            "shape_name": self.shape_name,
            "grid_shape": self.grid_shape,
            "projected_sample_count": self.projected_sample_count,
            "method_label": self.method_label,
            "bandwidth": self.bandwidth,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "metrics_failure_reason": self.metrics_failure_reason,
            "frontend_runtime_seconds": self.frontend_runtime_seconds,
            "initializer_runtime_seconds": self.initializer_runtime_seconds,
            "method_runtime_seconds": self.method_result.runtime_seconds,
            "total_converter_runtime_seconds": self.total_converter_runtime_seconds,
            "frontend_field_counts": _counts_dict(self.frontend_field_counts),
            "initializer_field_counts": _counts_dict(self.initializer_field_counts),
            "method_field_counts": _counts_dict(self.method_field_counts),
            "metrics_field_counts": _counts_dict(self.metrics_field_counts),
            "method_result": self.method_result.to_summary_dict(),
            "metrics": None if self.metrics is None else self.metrics.to_dict(),
            "artifacts": dict(self.artifact_paths),
        }
        payload.update(self._identity_and_accounting_aliases())
        payload.update(self.scalar_metric_aliases())
        return payload

    def to_csv_dict(self) -> dict[str, Any]:
        """Return the metrics table row without optimizer histories."""

        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "profile_name": self.profile_name,
            "frontend_id": self.frontend_id,
            "shape_name": self.shape_name,
            "grid_shape": self.grid_shape,
            "grid_ny": self.grid_shape[0],
            "grid_nx": self.grid_shape[1],
            "projected_sample_count": self.projected_sample_count,
            "method_label": self.method_label,
            "method_name": self.method_result.method_name,
            "bandwidth": self.bandwidth,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "metrics_failure_reason": self.metrics_failure_reason,
            "runtime": {
                "frontend_seconds": self.frontend_runtime_seconds,
                "initializer_seconds": self.initializer_runtime_seconds,
                "method_seconds": self.method_result.runtime_seconds,
                "total_converter_seconds": self.total_converter_runtime_seconds,
            },
            "field_counts": {
                "frontend": _counts_dict(self.frontend_field_counts),
                "initializer": _counts_dict(self.initializer_field_counts),
                "method": _counts_dict(self.method_field_counts),
                "metrics": _counts_dict(self.metrics_field_counts),
            },
            "input_fit_residual": (
                None
                if self.method_result.input_fit_residual is None
                else asdict(self.method_result.input_fit_residual)
            ),
            "arc_length": (
                None
                if self.method_result.arc_length is None
                else asdict(self.method_result.arc_length)
            ),
            "metrics": None if self.metrics is None else self.metrics.to_dict(),
        }
        payload.update(self._identity_and_accounting_aliases())
        payload.update(self.scalar_metric_aliases())
        return payload


@dataclass(frozen=True)
class ComparisonExperimentResult:
    output_directory: Path
    profile: ComparisonProfile
    shapes: tuple[ComparisonShape, ...]
    records: tuple[ExperimentRunRecord, ...]
    frontend_count: int
    manifest_path: Path
    metrics_json_path: Path
    metrics_csv_path: Path

    @property
    def status_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for record in self.records:
            result[record.status] = result.get(record.status, 0) + 1
        return result


def analytic_comparison_shapes() -> tuple[ComparisonShape, ...]:
    """Return circle, rotated ellipse, and radial-Fourier star benchmarks."""

    circle_field = CircleSDF(center=(0.12, -0.08), radius=0.72, name="analytic_circle_sdf")
    ellipse_field = EllipseLevelSet(
        center=(-0.08, 0.06),
        semi_major=0.92,
        semi_minor=0.51,
        rotation=0.37,
        name="analytic_rotated_ellipse_level_set",
    )
    star_field = RadialFourierLevelSet.star(
        center=(0.08, 0.04),
        mean_radius=0.72,
        amplitude=0.18,
        lobes=5,
        rotation=0.21,
        name="analytic_radial_fourier_star",
    )
    return (
        ComparisonShape(
            name="circle",
            field=circle_field,
            reference=circle_field.reference_parameterization(component_id="circle-reference"),
            bounds=((-0.90, -1.10), (1.15, 0.95)),
            winding_test_points=(circle_field.center,),
            description="Exact Euclidean signed-distance circle.",
            parameters={"center": circle_field.center, "radius": circle_field.radius},
        ),
        ComparisonShape(
            name="rotated_ellipse",
            field=ellipse_field,
            reference=ellipse_field.reference_parameterization(
                component_id="rotated-ellipse-reference"
            ),
            bounds=((-1.35, -1.15), (1.20, 1.25)),
            winding_test_points=(ellipse_field.center,),
            description="Rotated ellipse represented by a generic level-set field.",
            parameters={
                "center": ellipse_field.center,
                "semi_major": ellipse_field.semi_major,
                "semi_minor": ellipse_field.semi_minor,
                "rotation": ellipse_field.rotation,
            },
        ),
        ComparisonShape(
            name="radial_fourier_star",
            field=star_field,
            reference=star_field.reference_parameterization(component_id="star-reference"),
            bounds=((-1.05, -1.10), (1.20, 1.18)),
            winding_test_points=(star_field.center,),
            description="Smooth five-mode radial-Fourier star level set.",
            parameters={
                "center": star_field.center,
                "mean_radius": star_field.mean_radius,
                "amplitude": 0.18,
                "lobes": 5,
                "rotation": star_field.rotation,
            },
        ),
    )


def comparison_profile(name: str) -> ComparisonProfile:
    """Resolve the reproducible ``smoke`` or ``study`` profile."""

    normalized = str(name).strip().lower()
    projection = ProjectionConfig(
        residual_tolerance=1.0e-11,
        max_iterations=20,
        gradient_tolerance=1.0e-12,
        max_step_grid_fraction=0.75,
    )
    if normalized == "smoke":
        arc = ArcLengthConfig(
            dense_resolution=512,
            refit_sample_count=None,
            validation_resolution=256,
        )
        method_a = MethodAConfig(
            arclength=arc,
            validation=BoundaryValidationConfig(
                # Cubic-spline second derivatives are continuous but their
                # third derivatives jump at knots.  Resolve the finite-
                # difference probe more finely and use the calibrated
                # method-specific tolerance rather than rejecting the star at
                # stencils that straddle a knot.
                num_samples_per_component=512,
                derivative_relative_tolerance=3.0e-2,
            ),
        )
        method_b = MethodBConfig(
            bandwidth=4,
            arclength=arc,
            validation=BoundaryValidationConfig(num_samples_per_component=256),
        )
        method_c = MethodCConfig(
            dense_sample_count=64,
            # Resolve the highest smoke bandwidth with enough points for the
            # independent five-point derivative checks; N=128 can spuriously
            # reject a valid K=8 Fourier curve on third-derivative consistency.
            validation_sample_count=256,
            checkpoint_interval=2,
            stages=(
                RefinementStage(
                    "smoke_attach",
                    6,
                    1.5e-3,
                    RefinementWeights(fidelity=1.0, anchor=5.0e-2, spectral=1.0e-8),
                ),
                RefinementStage(
                    "smoke_regularize",
                    4,
                    6.0e-4,
                    RefinementWeights(
                        fidelity=1.0,
                        anchor=1.0e-2,
                        spectral=1.0e-8,
                        speed=1.0e-2,
                        regularity=5.0e-2,
                    ),
                ),
            ),
            final_stage=RefinementStage(
                "smoke_final",
                3,
                2.0e-4,
                RefinementWeights(fidelity=1.0, spectral=1.0e-8, regularity=1.0e-2),
            ),
            arc_length=arc,
        )
        metrics = BoundaryMetricConfig(
            dense_resolution=256,
            reference_resolution=1024,
            topology_resolution=128,
            fft_resolution=256,
            fft_tail_start_mode=8,
            kress_resolution=64,
            kress_sample_counts=(32, 64, 128),
        )
        return ComparisonProfile(
            name="smoke",
            grid_shapes=((65, 65),),
            projected_sample_counts=(64,),
            bandwidths=(4, 8),
            projection=projection,
            second_resample_and_project=True,
            method_a=method_a,
            method_b_template=method_b,
            method_c=method_c,
            metrics=metrics,
        )
    if normalized == "study":
        return ComparisonProfile(
            name="study",
            grid_shapes=((65, 65), (129, 129), (257, 257)),
            projected_sample_counts=(128, 256),
            bandwidths=(4, 8, 16, 32),
            projection=projection,
            second_resample_and_project=True,
            method_a=MethodAConfig(
                validation=BoundaryValidationConfig(
                    num_samples_per_component=1024,
                    derivative_relative_tolerance=2.0e-2,
                )
            ),
            method_b_template=MethodBConfig(bandwidth=4),
            # The study reaches K=32.  Keep the validation stencil independent
            # and substantially finer than the highest represented mode.
            method_c=MethodCConfig(validation_sample_count=1024),
            metrics=BoundaryMetricConfig(
                # Continue past the largest spline knot count so frozen-node
                # perimeter convergence cannot be hidden by knot-grid aliasing.
                kress_sample_counts=(64, 128, 256, 512, 1024),
            ),
        )
    raise ValueError("Unknown profile; expected 'smoke' or 'study'.")


def _failed_method(method_name: str, reason: str, runtime: float = 0.0) -> MethodResult:
    return MethodResult(
        method_name=method_name,
        status="failed",
        representation=None,
        parameterization=None,
        validation=None,
        input_fit_residual=None,
        arc_length=None,
        runtime_seconds=runtime,
        diagnostics={},
        failure_reason=reason,
    )


def _frontend_id(shape: ComparisonShape, grid_shape: tuple[int, int], samples: int) -> str:
    return f"{shape.name}__g{grid_shape[0]}x{grid_shape[1]}__m{samples}"


def _run_id(frontend_id: str, method_label: str, bandwidth: int | None) -> str:
    suffix = method_label.lower() if bandwidth is None else f"{method_label.lower()}__k{bandwidth:03d}"
    return f"{frontend_id}__{suffix}"


def _write_frontend_artifacts(
    output: Path,
    frontend_id: str,
    frontend: FrontendResult,
    *,
    runtime_seconds: float,
) -> dict[str, str]:
    component = frontend.single_component
    arrays: dict[str, Any] = {
        "grid_x": frontend.grid.x_coordinates,
        "grid_y": frontend.grid.y_coordinates,
        "grid_values": frontend.grid.values,
        "raw_contour": component.raw_contour,
        "initial_points": component.initial_points,
        "projected_points": component.projected_points,
        "parameters": component.parameters,
    }
    for index, projection_pass in enumerate(component.projection_passes):
        prefix = f"projection_{index}"
        arrays[f"{prefix}_points"] = projection_pass.points
        arrays[f"{prefix}_converged"] = projection_pass.converged
        arrays[f"{prefix}_iteration_counts"] = projection_pass.iteration_counts
        arrays[f"{prefix}_clipped_step_counts"] = projection_pass.clipped_step_counts
        arrays[f"{prefix}_residuals"] = projection_pass.residuals
        arrays[f"{prefix}_gradient_norms"] = projection_pass.gradient_norms
    npz_path = write_npz(output / "frontends" / f"{frontend_id}.npz", arrays)
    json_path = write_strict_json(
        output / "frontends" / f"{frontend_id}.json",
        {
            "frontend_id": frontend_id,
            "config": asdict(frontend.config),
            "runtime_seconds": runtime_seconds,
            "field_counts": _counts_dict(frontend.field_counts),
            "component_id": component.component_id,
            "raw_diagnostics": asdict(component.raw_diagnostics),
            "projected_diagnostics": asdict(component.projected_diagnostics),
            "projection_passes": [
                {
                    "all_converged": item.all_converged,
                    "maximum_residual": item.maximum_residual,
                    "total_iterations": item.total_iterations,
                    "maximum_iteration_count": int(np.max(item.iteration_counts)),
                    "total_clipped_steps": int(np.sum(item.clipped_step_counts)),
                }
                for item in component.projection_passes
            ],
        },
    )
    return {"frontend_npz": str(npz_path), "frontend_json": str(json_path)}


def _curve_npz_arrays(
    result: MethodResult,
    *,
    shape: ComparisonShape,
    frontend: FrontendResult,
    metric_config: BoundaryMetricConfig,
) -> dict[str, Any]:
    curve = result.parameterization
    if curve is None:
        raise ValueError("A failed method has no curve arrays to persist.")
    samples = sample_parameterization(curve, metric_config.dense_resolution)
    reference = sample_parameterization(shape.reference, metric_config.reference_resolution)
    field_values = evaluate_field_values(shape.field, samples.points)
    field_gradients = evaluate_field_gradients(shape.field, samples.points)
    gradient_norms = np.linalg.norm(field_gradients, axis=1)
    spectrum_samples = sample_parameterization(curve, metric_config.fft_resolution)
    modes, spectrum = coordinate_spectrum(
        spectrum_samples.points,
        center_coordinates=metric_config.center_fft_coordinates,
    )
    component = frontend.single_component
    arrays: dict[str, Any] = {
        "parameters": samples.parameters,
        "points": samples.points,
        "first_derivatives": samples.first_derivatives,
        "second_derivatives": samples.second_derivatives,
        "speeds": samples.speeds,
        "tangents": samples.tangents,
        "outward_normals": samples.outward_normals,
        "curvatures": samples.curvatures,
        "field_values": field_values,
        "field_gradient_norms": gradient_norms,
        "normalized_field_residual": np.abs(field_values)
        / (gradient_norms + metric_config.gradient_epsilon),
        "spectrum_modes": modes,
        "spectrum_amplitudes": spectrum,
        "reference_parameters": reference.parameters,
        "reference_points": reference.points,
        "reference_normals": reference.outward_normals,
        "raw_contour": component.raw_contour,
        "projected_points": component.projected_points,
        "projected_parameters": component.parameters,
        # Stable semantic aliases for consumers that do not use the internal
        # sampling vocabulary.  The native coefficients below, not these
        # sampled points, remain the fitted representation authority.
        "dense_parameters": samples.parameters,
        "gamma": samples.points,
        "d1": samples.first_derivatives,
        "d2": samples.second_derivatives,
        "speed": samples.speeds,
        "normal": samples.outward_normals,
        "curvature": samples.curvatures,
        "shared_raw_contour": component.raw_contour,
        "shared_projected_contour": component.projected_points,
        "shared_projected_parameters": component.parameters,
    }
    if isinstance(result.representation, FourierBoundary):
        arrays["cosine_coefficients"] = result.representation.cosine_coefficients
        arrays["sine_coefficients"] = result.representation.sine_coefficients
        arrays["native_mode_amplitudes"] = result.representation.mode_amplitudes()
    elif isinstance(result.representation, PeriodicSplineBoundary):
        arrays["spline_knots"] = result.representation.knots
        arrays["spline_coefficients"] = result.representation.coefficients
    return arrays


def _measure_method(
    field: CountedImplicitField2D,
    callback,
    *,
    failure_name: str,
) -> tuple[MethodResult, FieldEvaluationCounts]:
    field.reset_counts()
    started = time.perf_counter()
    try:
        result = callback()
        if not isinstance(result, MethodResult):
            raise TypeError("Method callback did not return MethodResult.")
    except Exception as exc:
        result = _failed_method(
            failure_name,
            f"{type(exc).__name__}: {exc}",
            runtime=time.perf_counter() - started,
        )
    return result, field.counts


def _measure_metrics(
    field: CountedImplicitField2D,
    result: MethodResult,
    *,
    shape: ComparisonShape,
    config: BoundaryMetricConfig,
) -> tuple[BoundaryMetrics | None, str | None, FieldEvaluationCounts]:
    field.reset_counts()
    if result.parameterization is None:
        return None, "method did not produce a parameterization", field.counts
    try:
        metrics = compute_boundary_metrics(
            result.parameterization,
            field=field,
            reference=shape.reference,
            config=config,
            winding_test_points=shape.winding_test_points,
        )
        return metrics, None, field.counts
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", field.counts


def _persist_run(
    output: Path,
    *,
    profile: ComparisonProfile,
    shape: ComparisonShape,
    frontend: FrontendResult | None,
    frontend_id: str,
    grid_shape: tuple[int, int],
    projected_samples: int,
    method_label: str,
    bandwidth: int | None,
    method_result: MethodResult,
    metrics: BoundaryMetrics | None,
    metrics_failure_reason: str | None,
    frontend_runtime: float,
    initializer_runtime: float,
    frontend_counts: FieldEvaluationCounts | None,
    initializer_counts: FieldEvaluationCounts | None,
    method_counts: FieldEvaluationCounts | None,
    metrics_counts: FieldEvaluationCounts | None,
    make_plots: bool,
) -> ExperimentRunRecord:
    run_id = _run_id(frontend_id, method_label, bandwidth)
    artifact_paths: dict[str, str] = {
        "run_json": str(output / "runs" / f"{run_id}.json"),
    }
    if method_result.parameterization is not None and frontend is not None:
        npz_path = write_npz(
            output / "curves" / f"{run_id}.npz",
            _curve_npz_arrays(
                method_result,
                shape=shape,
                frontend=frontend,
                metric_config=profile.metrics,
            ),
        )
        artifact_paths["curve_npz"] = str(npz_path)
        if make_plots:
            plot_path = plot_boundary_diagnostics(
                output / "plots" / f"{run_id}.png",
                method_result.parameterization,
                field=shape.field,
                reference=shape.reference,
                raw_contour=frontend.single_component.raw_contour,
                projected_contour=frontend.single_component.projected_points,
                config=profile.metrics,
                title=(
                    f"{shape.name}: Method {method_label}"
                    + ("" if bandwidth is None else f", K={bandwidth}")
                ),
            )
            artifact_paths["plot"] = str(plot_path)
    record = ExperimentRunRecord(
        run_id=run_id,
        profile_name=profile.name,
        frontend_id=frontend_id,
        shape_name=shape.name,
        grid_shape=grid_shape,
        projected_sample_count=projected_samples,
        method_label=method_label,
        bandwidth=bandwidth,
        method_result=method_result,
        metrics=metrics,
        metrics_failure_reason=metrics_failure_reason,
        frontend_runtime_seconds=frontend_runtime,
        initializer_runtime_seconds=initializer_runtime,
        frontend_field_counts=frontend_counts,
        initializer_field_counts=initializer_counts,
        method_field_counts=method_counts,
        metrics_field_counts=metrics_counts,
        artifact_paths=artifact_paths,
    )
    write_strict_json(artifact_paths["run_json"], record.to_dict())
    return record


def _frontend_failure_records(
    output: Path,
    *,
    profile: ComparisonProfile,
    shape: ComparisonShape,
    frontend_id: str,
    grid_shape: tuple[int, int],
    projected_samples: int,
    reason: str,
    frontend_runtime: float,
    frontend_counts: FieldEvaluationCounts,
    make_plots: bool,
) -> list[ExperimentRunRecord]:
    del make_plots
    axes = [("A", None)] + [
        (label, bandwidth)
        for bandwidth in profile.bandwidths
        for label in ("B", "C")
    ]
    records = []
    for label, bandwidth in axes:
        result = _failed_method(
            f"method_{label.lower()}_not_run",
            f"shared front end failed: {reason}",
        )
        records.append(
            _persist_run(
                output,
                profile=profile,
                shape=shape,
                frontend=None,
                frontend_id=frontend_id,
                grid_shape=grid_shape,
                projected_samples=projected_samples,
                method_label=label,
                bandwidth=bandwidth,
                method_result=result,
                metrics=None,
                metrics_failure_reason="shared front end failed",
                frontend_runtime=frontend_runtime,
                initializer_runtime=0.0,
                frontend_counts=frontend_counts,
                initializer_counts=FieldEvaluationCounts(0, 0, 0, 0),
                method_counts=FieldEvaluationCounts(0, 0, 0, 0),
                metrics_counts=FieldEvaluationCounts(0, 0, 0, 0),
                make_plots=False,
            )
        )
    return records


def run_comparison_experiment(
    output_directory: str | Path,
    *,
    profile: str | ComparisonProfile = "smoke",
    shapes: Sequence[ComparisonShape] | None = None,
    make_plots: bool = True,
) -> ComparisonExperimentResult:
    """Run the configured isolated comparison and persist every result/failure."""

    settings = comparison_profile(profile) if isinstance(profile, str) else profile
    if not isinstance(settings, ComparisonProfile):
        raise TypeError("profile must be a profile name or ComparisonProfile.")
    selected_shapes = tuple(analytic_comparison_shapes() if shapes is None else shapes)
    if not selected_shapes or not all(isinstance(shape, ComparisonShape) for shape in selected_shapes):
        raise TypeError("shapes must contain at least one ComparisonShape.")
    if not isinstance(make_plots, (bool, np.bool_)):
        raise TypeError("make_plots must be boolean.")
    output = Path(output_directory)
    if output.exists():
        if not output.is_dir():
            raise NotADirectoryError(f"Experiment output is not a directory: {output}")
        if any(output.iterdir()):
            raise FileExistsError(
                "Experiment output directory must be empty so artifacts from "
                f"different sweeps cannot be mixed: {output}"
            )
    records: list[ExperimentRunRecord] = []
    frontend_count = 0

    for shape in selected_shapes:
        for grid_shape in settings.grid_shapes:
            for projected_samples in settings.projected_sample_counts:
                frontend_count += 1
                frontend_id = _frontend_id(shape, grid_shape, projected_samples)
                counted_field = CountedImplicitField2D(shape.field)
                frontend_config = FrontendConfig(
                    bounds=shape.bounds,
                    grid_shape=grid_shape,
                    projected_samples=projected_samples,
                    second_resample_and_project=settings.second_resample_and_project,
                    projection=settings.projection,
                )
                counted_field.reset_counts()
                frontend_started = time.perf_counter()
                try:
                    frontend = prepare_single_component(counted_field, frontend_config)
                    frontend_runtime = time.perf_counter() - frontend_started
                    frontend_counts = frontend.field_counts or counted_field.counts
                    _write_frontend_artifacts(
                        output,
                        frontend_id,
                        frontend,
                        runtime_seconds=frontend_runtime,
                    )
                except Exception as exc:
                    frontend_runtime = time.perf_counter() - frontend_started
                    reason = f"{type(exc).__name__}: {exc}"
                    records.extend(
                        _frontend_failure_records(
                            output,
                            profile=settings,
                            shape=shape,
                            frontend_id=frontend_id,
                            grid_shape=grid_shape,
                            projected_samples=projected_samples,
                            reason=reason,
                            frontend_runtime=frontend_runtime,
                            frontend_counts=counted_field.counts,
                            make_plots=bool(make_plots),
                        )
                    )
                    continue

                component = frontend.single_component
                projection_residual = component.projection_passes[-1].maximum_residual
                common_keywords = {
                    "component_id": component.component_id,
                    "source_identifier": shape.name,
                    "projection_residual": projection_residual,
                }

                method_a_result, method_a_counts = _measure_method(
                    counted_field,
                    lambda: fit_method_a(
                        frontend,
                        config=settings.method_a,
                        **common_keywords,
                    ),
                    failure_name="method_a_periodic_cubic_spline",
                )
                method_a_metrics, method_a_metric_failure, method_a_metric_counts = (
                    _measure_metrics(
                        counted_field,
                        method_a_result,
                        shape=shape,
                        config=settings.metrics,
                    )
                )
                records.append(
                    _persist_run(
                        output,
                        profile=settings,
                        shape=shape,
                        frontend=frontend,
                        frontend_id=frontend_id,
                        grid_shape=grid_shape,
                        projected_samples=projected_samples,
                        method_label="A",
                        bandwidth=None,
                        method_result=method_a_result,
                        metrics=method_a_metrics,
                        metrics_failure_reason=method_a_metric_failure,
                        frontend_runtime=frontend_runtime,
                        initializer_runtime=0.0,
                        frontend_counts=frontend_counts,
                        initializer_counts=FieldEvaluationCounts(0, 0, 0, 0),
                        method_counts=method_a_counts,
                        metrics_counts=method_a_metric_counts,
                        make_plots=bool(make_plots),
                    )
                )

                for bandwidth in settings.bandwidths:
                    method_b_config = replace(
                        settings.method_b_template,
                        bandwidth=bandwidth,
                    )
                    method_b_result, method_b_counts = _measure_method(
                        counted_field,
                        lambda method_b_config=method_b_config: fit_method_b(
                            frontend,
                            config=method_b_config,
                            **common_keywords,
                        ),
                        failure_name="method_b_fourier_least_squares",
                    )
                    method_b_metrics, method_b_metric_failure, method_b_metric_counts = (
                        _measure_metrics(
                            counted_field,
                            method_b_result,
                            shape=shape,
                            config=settings.metrics,
                        )
                    )
                    records.append(
                        _persist_run(
                            output,
                            profile=settings,
                            shape=shape,
                            frontend=frontend,
                            frontend_id=frontend_id,
                            grid_shape=grid_shape,
                            projected_samples=projected_samples,
                            method_label="B",
                            bandwidth=bandwidth,
                            method_result=method_b_result,
                            metrics=method_b_metrics,
                            metrics_failure_reason=method_b_metric_failure,
                            frontend_runtime=frontend_runtime,
                            initializer_runtime=0.0,
                            frontend_counts=frontend_counts,
                            initializer_counts=FieldEvaluationCounts(0, 0, 0, 0),
                            method_counts=method_b_counts,
                            metrics_counts=method_b_metric_counts,
                            make_plots=bool(make_plots),
                        )
                    )

                    if method_b_result.status == "success":
                        method_c_result, method_c_counts = _measure_method(
                            counted_field,
                            lambda: fit_method_c(
                                counted_field,
                                frontend,
                                method_b_result,
                                config=settings.method_c,
                            ),
                            failure_name="method_c_sdf_refined_fourier",
                        )
                    else:
                        method_c_result = _failed_method(
                            "method_c_sdf_refined_fourier",
                            "Method C was not run because its Method B initializer failed.",
                        )
                        method_c_counts = FieldEvaluationCounts(0, 0, 0, 0)
                    method_c_metrics, method_c_metric_failure, method_c_metric_counts = (
                        _measure_metrics(
                            counted_field,
                            method_c_result,
                            shape=shape,
                            config=settings.metrics,
                        )
                    )
                    records.append(
                        _persist_run(
                            output,
                            profile=settings,
                            shape=shape,
                            frontend=frontend,
                            frontend_id=frontend_id,
                            grid_shape=grid_shape,
                            projected_samples=projected_samples,
                            method_label="C",
                            bandwidth=bandwidth,
                            method_result=method_c_result,
                            metrics=method_c_metrics,
                            metrics_failure_reason=method_c_metric_failure,
                            frontend_runtime=frontend_runtime,
                            initializer_runtime=method_b_result.runtime_seconds,
                            frontend_counts=frontend_counts,
                            initializer_counts=method_b_counts,
                            method_counts=method_c_counts,
                            metrics_counts=method_c_metric_counts,
                            make_plots=bool(make_plots),
                        )
                    )

    metrics_json_path = write_strict_json(
        output / "metrics.json",
        [record.to_dict() for record in records],
    )
    metrics_csv_path = write_metrics_csv(
        output / "metrics.csv",
        [record.to_csv_dict() for record in records],
    )
    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
    manifest_path = write_strict_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "profile": settings.to_dict(),
            "shapes": [shape.to_dict() for shape in selected_shapes],
            "frontend_count": frontend_count,
            "run_count": len(records),
            "status_counts": status_counts,
            "metrics_json": str(metrics_json_path),
            "metrics_csv": str(metrics_csv_path),
            "plots_enabled": bool(make_plots),
            "active_solver_pipeline_modified": False,
        },
    )
    return ComparisonExperimentResult(
        output_directory=output,
        profile=settings,
        shapes=selected_shapes,
        records=tuple(records),
        frontend_count=frontend_count,
        manifest_path=manifest_path,
        metrics_json_path=metrics_json_path,
        metrics_csv_path=metrics_csv_path,
    )


__all__ = [
    "ComparisonExperimentResult",
    "ComparisonProfile",
    "ComparisonShape",
    "ExperimentRunRecord",
    "analytic_comparison_shapes",
    "comparison_profile",
    "run_comparison_experiment",
]
