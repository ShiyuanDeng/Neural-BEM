"""Opt-in topology birth and fixed-topology optimization for radial curves.

This module is deliberately separate from the established single-component
implicit inverse.  It owns an ordered tuple of explicit radial-Fourier states,
uses the direct multi-component Kress seam, and implements exactly one kind of
topology event: appending a circular component proposed by a current-domain
topological derivative.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter
from typing import Any, Callable

import numpy as np
from scipy import ndimage
from scipy.special import hankel1

from gpr_bem_kress.materials import Material
from gpr_bem_kress.multicomponent import (
    MultiComponentAssemblyConfig,
    MultiComponentKressGeometryError,
    MultiComponentKressSolveConfig,
    build_multicomponent_exterior_receiver_operator,
    build_multicomponent_kress_tmz_frequency_system,
    multicomponent_incident_trace_on_boundary,
)
from ordered_boundary import OrderedBoundary2D
from sdf_bem_multicomponent import (
    PairedForwardProblem,
    predict_multicomponent_kress_paired_boundary_response,
)

from .curve_updates import RadialFourierCurveState, radial_fourier_state_curve
from .geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from .optimization import (
    ComplexScatteredData,
    ParameterFDConfig,
    normalized_complex_residual,
)


DEFAULT_TD_CHUNK_SIZE = 4096
FROZEN_BIRTH_RADIUS_FACTORS = (1.0, 0.75, 0.5, 0.35)


def _readonly(values: Any, *, dtype: Any) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _finite_points(values: Any, *, name: str) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[1] != 2 or result.shape[0] < 1:
        raise ValueError(f"{name} must have non-empty shape (N, 2).")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values.")
    return result


def _positive_integer(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    result = int(value)
    if result != value or result < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return result


def circle_radial_fourier_state(
    center: Any,
    radius_m: float,
    component_id: str,
) -> RadialFourierCurveState:
    """Construct the gauge-fixed ``K=1`` representation of a circle."""

    radius = float(radius_m)
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("radius_m must be finite and positive.")
    return RadialFourierCurveState(
        center=np.asarray(center, dtype=np.float64),
        radius_cosine_coefficients=np.asarray((radius, 0.0)),
        radius_sine_coefficients=np.zeros(2, dtype=np.float64),
        component_id=component_id,
        name=f"radial_fourier_{component_id}",
        source_identifier=component_id,
    )


@dataclass(frozen=True)
class MultiRadialFourierState:
    """Immutable, authoritatively ordered collection of radial components."""

    components: tuple[RadialFourierCurveState, ...]

    def __post_init__(self) -> None:
        components = tuple(self.components)
        if not components:
            raise ValueError("At least one radial component is required.")
        if not all(isinstance(item, RadialFourierCurveState) for item in components):
            raise TypeError("components must contain RadialFourierCurveState objects.")
        identifiers = tuple(item.component_id for item in components)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("component_id values must be unique.")
        object.__setattr__(self, "components", components)

    @property
    def component_ids(self) -> tuple[str, ...]:
        return tuple(item.component_id for item in self.components)

    @property
    def parameter_slices(self) -> tuple[slice, ...]:
        slices: list[slice] = []
        offset = 0
        for component in self.components:
            slices.append(slice(offset, offset + component.parameter_count))
            offset += component.parameter_count
        return tuple(slices)

    @property
    def parameter_count(self) -> int:
        return sum(item.parameter_count for item in self.components)

    @property
    def parameter_names(self) -> tuple[str, ...]:
        result: list[str] = []
        for component in self.components:
            prefix = component.component_id
            result.extend((f"{prefix}.radius_m", f"{prefix}.center_x_m", f"{prefix}.center_y_m"))
            for mode in range(2, component.maximum_mode + 1):
                result.extend((f"{prefix}.radius_cos_{mode}_m", f"{prefix}.radius_sin_{mode}_m"))
        return tuple(result)

    def parameter_vector(self) -> np.ndarray:
        """Flatten absolute parameters without introducing an ID registry."""

        values: list[float] = []
        for component in self.components:
            values.extend((component.mean_radius_m, *np.asarray(component.center)))
            for mode in range(2, component.maximum_mode + 1):
                values.extend(
                    (
                        float(component.radius_cosine_coefficients[mode]),
                        float(component.radius_sine_coefficients[mode]),
                    )
                )
        return _readonly(values, dtype=np.float64)

    def from_parameter_vector(self, values: Any) -> "MultiRadialFourierState":
        """Unflatten absolute values while preserving order, IDs and metadata."""

        vector = np.asarray(values, dtype=np.float64)
        if vector.shape != (self.parameter_count,) or not np.all(np.isfinite(vector)):
            raise ValueError(
                f"values must contain {self.parameter_count} finite parameters."
            )
        rebuilt: list[RadialFourierCurveState] = []
        for component, component_slice in zip(self.components, self.parameter_slices):
            local = vector[component_slice]
            cosine = np.asarray(component.radius_cosine_coefficients).copy()
            sine = np.asarray(component.radius_sine_coefficients).copy()
            cosine[0] = local[0]
            cursor = 3
            for mode in range(2, component.maximum_mode + 1):
                cosine[mode], sine[mode] = local[cursor : cursor + 2]
                cursor += 2
            rebuilt.append(
                RadialFourierCurveState(
                    center=local[1:3],
                    radius_cosine_coefficients=cosine,
                    radius_sine_coefficients=sine,
                    component_id=component.component_id,
                    name=component.name,
                    source_identifier=component.source_identifier,
                    initial_projection_rms_m=component.initial_projection_rms_m,
                    initial_projection_maximum_m=component.initial_projection_maximum_m,
                )
            )
        return MultiRadialFourierState(tuple(rebuilt))

    def incremented(self, step: Any) -> "MultiRadialFourierState":
        delta = np.asarray(step, dtype=np.float64)
        if delta.shape != (self.parameter_count,) or not np.all(np.isfinite(delta)):
            raise ValueError(f"step must contain {self.parameter_count} finite values.")
        return self.from_parameter_vector(self.parameter_vector() + delta)

    def appended(self, component: RadialFourierCurveState) -> "MultiRadialFourierState":
        if not isinstance(component, RadialFourierCurveState):
            raise TypeError("component must be a RadialFourierCurveState.")
        return MultiRadialFourierState(self.components + (component,))

    def boundary(self, geometry_config: OrderedSDFGeometryConfig) -> OrderedBoundary2D:
        """Build every component with full validation in stored order."""

        if not isinstance(geometry_config, OrderedSDFGeometryConfig):
            raise TypeError("geometry_config must be an OrderedSDFGeometryConfig.")
        return OrderedBoundary2D(
            tuple(
                radial_fourier_state_curve(
                    component,
                    geometry_config=geometry_config,
                    full_validation=True,
                )
                for component in self.components
            )
        )


@dataclass(frozen=True)
class TopologicalDerivativeResult:
    """Raw multi-frequency current-domain derivative at requested points."""

    points: np.ndarray
    values: np.ndarray
    per_frequency_values: np.ndarray
    predicted_scattered_response: np.ndarray
    complex_residual: np.ndarray
    observed_column_scales: np.ndarray
    frequency_weights: np.ndarray
    linear_system_relative_residuals: np.ndarray
    empty_domain: bool

    def __post_init__(self) -> None:
        points = _finite_points(self.points, name="points")
        count = points.shape[0]
        values = np.asarray(self.values, dtype=np.float64)
        per_frequency = np.asarray(self.per_frequency_values, dtype=np.float64)
        predicted = np.asarray(self.predicted_scattered_response, dtype=np.complex128)
        residual = np.asarray(self.complex_residual, dtype=np.complex128)
        scales = np.asarray(self.observed_column_scales, dtype=np.float64)
        weights = np.asarray(self.frequency_weights, dtype=np.float64)
        linear = np.asarray(self.linear_system_relative_residuals, dtype=np.float64)
        if values.shape != (count,) or not np.all(np.isfinite(values)):
            raise ValueError("values must be a finite vector matching points.")
        if predicted.ndim != 2 or residual.shape != predicted.shape:
            raise ValueError("predicted_scattered_response and complex_residual must match.")
        frequency_count = predicted.shape[1]
        if per_frequency.shape != (count, frequency_count):
            raise ValueError("per_frequency_values has an inconsistent shape.")
        if scales.shape != (frequency_count,) or weights.shape != (frequency_count,):
            raise ValueError("scale and weight vectors have an inconsistent shape.")
        if linear.shape != (frequency_count,):
            raise ValueError("linear_system_relative_residuals has an inconsistent shape.")
        for name, array in (
            ("per_frequency_values", per_frequency),
            ("predicted_scattered_response", predicted),
            ("complex_residual", residual),
            ("observed_column_scales", scales),
            ("frequency_weights", weights),
            ("linear_system_relative_residuals", linear),
        ):
            if not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must be finite.")
        object.__setattr__(self, "points", _readonly(points, dtype=np.float64))
        object.__setattr__(self, "values", _readonly(values, dtype=np.float64))
        object.__setattr__(self, "per_frequency_values", _readonly(per_frequency, dtype=np.float64))
        object.__setattr__(self, "predicted_scattered_response", _readonly(predicted, dtype=np.complex128))
        object.__setattr__(self, "complex_residual", _readonly(residual, dtype=np.complex128))
        object.__setattr__(self, "observed_column_scales", _readonly(scales, dtype=np.float64))
        object.__setattr__(self, "frequency_weights", _readonly(weights, dtype=np.float64))
        object.__setattr__(self, "linear_system_relative_residuals", _readonly(linear, dtype=np.float64))
        object.__setattr__(self, "empty_domain", bool(self.empty_domain))


def _objective_column_scales(observed: np.ndarray, relative_floor: float = 1.0e-12) -> np.ndarray:
    norms = np.linalg.norm(observed, axis=0)
    reference = max(
        float(np.max(norms)),
        float(np.linalg.norm(observed)) / math.sqrt(observed.shape[1]),
        1.0,
    )
    return np.maximum(norms, max(relative_floor * reference, np.finfo(float).tiny))


def _free_space_field(
    evaluation_points: np.ndarray,
    source_points: np.ndarray,
    k_exterior: complex,
    source_strengths: np.ndarray,
) -> np.ndarray:
    distances = np.linalg.norm(
        source_points[:, None, :] - evaluation_points[None, :, :], axis=-1
    )
    if np.any(distances <= 0.0):
        raise ValueError("evaluation points must not coincide with source points.")
    return source_strengths[:, None] * 0.25j * hankel1(0, k_exterior * distances)


def _material(spec: Any) -> Material:
    return Material(epsr=spec.epsr, sigma=spec.sigma, mur=spec.mur)


def evaluate_current_domain_topological_derivative(
    state: MultiRadialFourierState | None,
    data: ComplexScatteredData,
    points: Any,
    *,
    geometry_config: OrderedSDFGeometryConfig | None = None,
    solve_config: MultiComponentKressSolveConfig | None = None,
    chunk_size: int = DEFAULT_TD_CHUNK_SIZE,
) -> TopologicalDerivativeResult:
    """Evaluate the exact project-convention TD, solving one RHS batch/frequency.

    Physical source row ``s`` is paired only with reciprocal receiver-source
    row ``s``.  Receiver-point evaluation is chunked after the boundary system
    has been solved; no inspection-point solve is performed.
    """

    if not isinstance(data, ComplexScatteredData):
        raise TypeError("data must be ComplexScatteredData.")
    evaluation_points = _finite_points(points, name="points")
    chunk = _positive_integer(chunk_size, name="chunk_size")
    problem = PairedForwardProblem.from_compatible(data.forward_problem)
    observed = np.asarray(data.observed_scattered_response)
    if observed.shape != (problem.num_pairs, problem.num_frequencies):
        raise ValueError("observed response and paired problem shapes do not match.")
    if state is not None and not isinstance(state, MultiRadialFourierState):
        raise TypeError("state must be MultiRadialFourierState or None.")
    if state is not None and not isinstance(geometry_config, OrderedSDFGeometryConfig):
        raise TypeError("geometry_config is required for a non-empty state.")
    settings = MultiComponentKressSolveConfig() if solve_config is None else solve_config
    if not isinstance(settings, MultiComponentKressSolveConfig):
        raise TypeError("solve_config must be MultiComponentKressSolveConfig.")

    scales = _objective_column_scales(observed)
    weights = np.asarray(data.frequency_weights)
    per_frequency = np.empty((evaluation_points.shape[0], problem.num_frequencies))
    predicted = np.empty_like(observed)
    linear_residuals = np.zeros(problem.num_frequencies, dtype=np.float64)
    boundary = None if state is None else state.boundary(geometry_config)
    exterior = _material(problem.exterior)
    interior = _material(problem.interior)

    if boundary is None:
        predicted.fill(0.0)
    complex_residual = np.empty_like(observed)

    for frequency_index, (omega, physical_strength) in enumerate(
        zip(problem.angular_frequencies, problem.source_strengths)
    ):
        k_exterior = complex(exterior.wavenumber(float(omega), problem.eps0, problem.mu0))
        k_interior = complex(interior.wavenumber(float(omega), problem.eps0, problem.mu0))
        paired_count = problem.num_pairs
        combined_sources = np.vstack((problem.source_points, problem.receiver_points))
        combined_strengths = np.concatenate(
            (
                np.full(paired_count, physical_strength, dtype=np.complex128),
                np.ones(paired_count, dtype=np.complex128),
            )
        )
        total_traces: tuple[np.ndarray, np.ndarray] | None = None
        if boundary is not None:
            system = build_multicomponent_kress_tmz_frequency_system(
                boundary,
                float(omega),
                exterior=exterior,
                interior=interior,
                eps0=problem.eps0,
                mu0=problem.mu0,
                config=settings.assembly,
                compute_condition_number=settings.compute_condition_number,
            )
            incident_dirichlet, incident_neumann = multicomponent_incident_trace_on_boundary(
                boundary, combined_sources, system.k_exterior, combined_strengths
            )
            rhs = np.concatenate((incident_dirichlet, incident_neumann), axis=1).T
            solution = np.linalg.solve(system.system_matrix, rhs)
            equation_residual = system.system_matrix @ solution - rhs
            relative = float(np.linalg.norm(equation_residual) / np.linalg.norm(rhs))
            linear_residuals[frequency_index] = max(
                linear_residuals[frequency_index], relative
            )
            total_traces = (
                solution[: boundary.num_nodes].T,
                solution[boundary.num_nodes :].T,
            )

            # The same combined solve supplies the current paired prediction.
            # Only physical-source rows participate in the objective; the
            # reciprocal receiver-source rows remain unit-strength TD fields.
            paired_operator = build_multicomponent_exterior_receiver_operator(
                boundary, problem.receiver_points, k_exterior, minimum_clearance=0.0
            )
            paired_representation = paired_operator.evaluate(*total_traces)
            predicted[:, frequency_index] = np.diag(
                paired_representation.scattered[:paired_count]
            )
        complex_residual[:, frequency_index] = (
            predicted[:, frequency_index] - observed[:, frequency_index]
        )

        for start in range(0, evaluation_points.shape[0], chunk):
            stop = min(start + chunk, evaluation_points.shape[0])
            local_points = evaluation_points[start:stop]
            incident = _free_space_field(
                local_points, combined_sources, k_exterior, combined_strengths
            )
            if boundary is None:
                total = incident
            else:
                assert total_traces is not None
                operator = build_multicomponent_exterior_receiver_operator(
                    boundary, local_points, k_exterior, minimum_clearance=0.0
                )
                representation = operator.evaluate(*total_traces)
                total = incident + representation.scattered
            physical = total[:paired_count]
            reciprocal = total[paired_count:]
            accumulated = np.sum(
                np.conjugate(complex_residual[:, frequency_index])[:, None]
                * physical
                * reciprocal,
                axis=0,
            )
            contrast = k_interior * k_interior - k_exterior * k_exterior
            per_frequency[start:stop, frequency_index] = (
                weights[frequency_index]
                / scales[frequency_index] ** 2
                * np.real(contrast * accumulated)
            )

    return TopologicalDerivativeResult(
        points=evaluation_points,
        values=np.sum(per_frequency, axis=1),
        per_frequency_values=per_frequency,
        predicted_scattered_response=predicted,
        complex_residual=complex_residual,
        observed_column_scales=scales,
        frequency_weights=weights,
        linear_system_relative_residuals=linear_residuals,
        empty_domain=state is None,
    )


def _inside_polygon(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    result = np.zeros(points.shape[0], dtype=bool)
    x = points[:, 0]
    y = points[:, 1]
    first = polygon[-1]
    for second in polygon:
        crosses = (first[1] > y) != (second[1] > y)
        denominator = second[1] - first[1]
        x_intersection = (second[0] - first[0]) * (y - first[1]) / (
            denominator + np.where(denominator >= 0.0, 1.0, -1.0) * np.finfo(float).tiny
        ) + first[0]
        result ^= crosses & (x < x_intersection)
        first = second
    return result


def _minimum_polygon_distance(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    result = np.full(points.shape[0], np.inf)
    first = polygon[-1]
    for second in polygon:
        edge = second - first
        squared = float(np.dot(edge, edge))
        relative = points - first[None, :]
        fraction = np.clip(relative @ edge / squared, 0.0, 1.0)
        projection = first[None, :] + fraction[:, None] * edge[None, :]
        result = np.minimum(result, np.linalg.norm(points - projection, axis=1))
        first = second
    return result


@dataclass(frozen=True)
class TDRasterResult:
    """Node-grid TD field plus deterministic 4-connected proposal region."""

    axis_x: np.ndarray
    axis_y: np.ndarray
    points: np.ndarray
    valid_mask: np.ndarray
    values: np.ndarray
    threshold_mask: np.ndarray
    labels: np.ndarray
    selected_region: np.ndarray
    minimum_point: np.ndarray
    minimum_value: float
    region_count: int
    selected_centroid: np.ndarray
    selected_area_m2: float
    equivalent_radius_m: float
    selected_touches_inspection_boundary: bool
    minimum_station_distance_m: float

    def __post_init__(self) -> None:
        shape = np.asarray(self.values).shape
        if len(shape) != 2 or shape != (len(self.axis_y), len(self.axis_x)):
            raise ValueError("values shape must equal (len(axis_y), len(axis_x)).")
        for name in ("valid_mask", "threshold_mask", "labels", "selected_region"):
            if np.asarray(getattr(self, name)).shape != shape:
                raise ValueError(f"{name} must match the raster shape.")


def build_td_raster(
    state: MultiRadialFourierState | None,
    data: ComplexScatteredData,
    *,
    num_points: int,
    inspection_center: tuple[float, float] = (0.5, 0.5),
    inspection_radius_m: float = 0.2,
    boundary_buffer_m: float = 0.01,
    threshold_c0: float = 0.15,
    geometry_config: OrderedSDFGeometryConfig | None = None,
    solve_config: MultiComponentKressSolveConfig | None = None,
    chunk_size: int = DEFAULT_TD_CHUNK_SIZE,
) -> tuple[TDRasterResult, TopologicalDerivativeResult]:
    """Evaluate and label the frozen node-grid topology proposal."""

    count = _positive_integer(num_points, name="num_points")
    if count < 3:
        raise ValueError("num_points must be at least three.")
    center = np.asarray(inspection_center, dtype=np.float64)
    radius = float(inspection_radius_m)
    buffer = float(boundary_buffer_m)
    c0 = float(threshold_c0)
    if center.shape != (2,) or not np.all(np.isfinite(center)):
        raise ValueError("inspection_center must contain two finite coordinates.")
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("inspection_radius_m must be finite and positive.")
    if not math.isfinite(buffer) or buffer < 0.0:
        raise ValueError("boundary_buffer_m must be finite and non-negative.")
    if not math.isfinite(c0) or not 0.0 < c0 < 1.0:
        raise ValueError("threshold_c0 must lie strictly between zero and one.")

    axis_x = np.linspace(center[0] - radius, center[0] + radius, count)
    axis_y = np.linspace(center[1] - radius, center[1] + radius, count)
    grid_x, grid_y = np.meshgrid(axis_x, axis_y, indexing="xy")
    flat_points = np.column_stack((grid_x.ravel(), grid_y.ravel()))
    disk = np.linalg.norm(flat_points - center[None, :], axis=1) <= radius + 8.0 * np.finfo(float).eps
    valid = disk.copy()
    if state is not None:
        if geometry_config is None:
            raise TypeError("geometry_config is required for a non-empty state.")
        boundary = state.boundary(geometry_config)
        for component in boundary.components:
            polygon = np.asarray(component.points)
            valid &= ~_inside_polygon(flat_points, polygon)
            valid &= _minimum_polygon_distance(flat_points, polygon) > buffer
    problem = PairedForwardProblem.from_compatible(data.forward_problem)
    stations = np.vstack((problem.source_points, problem.receiver_points))
    station_distance = np.min(
        np.linalg.norm(flat_points[valid, None, :] - stations[None, :, :], axis=-1)
    )
    derivative = evaluate_current_domain_topological_derivative(
        state,
        data,
        flat_points[valid],
        geometry_config=geometry_config,
        solve_config=solve_config,
        chunk_size=chunk_size,
    )
    flat_values = np.full(flat_points.shape[0], np.nan)
    flat_values[valid] = derivative.values
    values = flat_values.reshape(count, count)
    minimum_flat_index = int(np.nanargmin(flat_values))
    minimum_value = float(flat_values[minimum_flat_index])
    if minimum_value >= 0.0:
        raise ValueError("The inspection raster contains no favourable negative TD value.")
    threshold_mask = np.isfinite(values) & (values < (1.0 - c0) * minimum_value)
    labels, region_count = ndimage.label(
        threshold_mask, structure=np.asarray(((0, 1, 0), (1, 1, 1), (0, 1, 0)))
    )
    minimum_index = np.unravel_index(minimum_flat_index, values.shape)
    selected_label = int(labels[minimum_index])
    if selected_label == 0:
        raise RuntimeError("The favourable global minimum was not labelled.")
    selected = labels == selected_label
    dx = float(axis_x[1] - axis_x[0])
    dy = float(axis_y[1] - axis_y[0])
    area = float(np.count_nonzero(selected) * dx * dy)
    centroid = np.asarray((np.mean(grid_x[selected]), np.mean(grid_y[selected])))
    equivalent_radius = math.sqrt(area / math.pi)
    disk_mask = disk.reshape(count, count)
    outside_neighbour = ndimage.binary_dilation(selected, structure=np.asarray(((0, 1, 0), (1, 1, 1), (0, 1, 0)))) & ~disk_mask
    touches = bool(np.any(outside_neighbour))
    raster = TDRasterResult(
        axis_x=_readonly(axis_x, dtype=np.float64),
        axis_y=_readonly(axis_y, dtype=np.float64),
        points=_readonly(flat_points.reshape(count, count, 2), dtype=np.float64),
        valid_mask=_readonly(valid.reshape(count, count), dtype=bool),
        values=_readonly(values, dtype=np.float64),
        threshold_mask=_readonly(threshold_mask, dtype=bool),
        labels=_readonly(labels, dtype=np.int64),
        selected_region=_readonly(selected, dtype=bool),
        minimum_point=_readonly(flat_points[minimum_flat_index], dtype=np.float64),
        minimum_value=minimum_value,
        region_count=int(region_count),
        selected_centroid=_readonly(centroid, dtype=np.float64),
        selected_area_m2=area,
        equivalent_radius_m=equivalent_radius,
        selected_touches_inspection_boundary=touches,
        minimum_station_distance_m=float(station_distance),
    )
    return raster, derivative


@dataclass(frozen=True)
class MultiRadialObjectiveEvaluation:
    state: MultiRadialFourierState
    loss: float
    relative_l2_error: float
    residual: np.ndarray
    prediction: np.ndarray
    maximum_system_residual: float
    forward_seconds: float


def evaluate_multiradial_objective(
    state: MultiRadialFourierState,
    data: ComplexScatteredData,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    solve_config: MultiComponentKressSolveConfig | None = None,
) -> MultiRadialObjectiveEvaluation:
    """Evaluate the actual direct-boundary Kress objective."""

    started = perf_counter()
    boundary = state.boundary(geometry_config)
    forward = predict_multicomponent_kress_paired_boundary_response(
        boundary,
        data.forward_problem,
        solve_config=solve_config,
    )
    residual, relative = normalized_complex_residual(
        forward.scattered_response,
        data.observed_scattered_response,
        data.frequency_weights,
    )
    return MultiRadialObjectiveEvaluation(
        state=state,
        loss=0.5 * float(np.dot(residual, residual)),
        relative_l2_error=relative,
        residual=_readonly(residual, dtype=np.float64),
        prediction=_readonly(forward.scattered_response, dtype=np.complex128),
        maximum_system_residual=float(np.max(forward.linear_system_relative_residuals)),
        forward_seconds=float(perf_counter() - started),
    )


@dataclass(frozen=True)
class BirthTrial:
    factor: float
    radius_m: float
    production_loss: float | None
    refined_loss: float | None
    production_delta: float | None
    refined_delta: float | None
    accepted: bool
    rejection_reason: str | None
    state: MultiRadialFourierState | None


@dataclass(frozen=True)
class BirthResult:
    initial_state: MultiRadialFourierState
    selected_state: MultiRadialFourierState | None
    trials: tuple[BirthTrial, ...]
    production_base_loss: float
    refined_base_loss: float
    stop_reason: str


def evaluate_birth_ladder(
    state: MultiRadialFourierState,
    data: ComplexScatteredData,
    *,
    seed_center: Any,
    equivalent_radius_m: float,
    production_geometry_config: OrderedSDFGeometryConfig,
    refined_geometry_config: OrderedSDFGeometryConfig,
    solve_config: MultiComponentKressSolveConfig,
    component_id: str = "td_birth_001",
    radius_factors: tuple[float, ...] = FROZEN_BIRTH_RADIUS_FACTORS,
    minimum_radius_m: float = 0.005,
) -> BirthResult:
    """Score the frozen finite-radius ladder at both Kress resolutions."""

    if tuple(radius_factors) != FROZEN_BIRTH_RADIUS_FACTORS:
        raise ValueError("iteration 01 requires the frozen birth-radius ladder.")
    center = np.asarray(seed_center, dtype=np.float64)
    if center.shape != (2,) or not np.all(np.isfinite(center)):
        raise ValueError("seed_center must contain two finite coordinates.")
    equivalent = float(equivalent_radius_m)
    if not math.isfinite(equivalent) or equivalent <= 0.0:
        raise ValueError("equivalent_radius_m must be finite and positive.")
    production_base = evaluate_multiradial_objective(
        state, data, production_geometry_config, solve_config=solve_config
    )
    refined_base = evaluate_multiradial_objective(
        state, data, refined_geometry_config, solve_config=solve_config
    )
    trials: list[BirthTrial] = []
    accepted: list[BirthTrial] = []
    for factor in radius_factors:
        radius = float(factor * equivalent)
        if radius < minimum_radius_m:
            trial = BirthTrial(factor, radius, None, None, None, None, False, "below_minimum_radius", None)
            trials.append(trial)
            continue
        candidate = state.appended(circle_radial_fourier_state(center, radius, component_id))
        try:
            production = evaluate_multiradial_objective(
                candidate, data, production_geometry_config, solve_config=solve_config
            )
        except (OrderedSDFGeometryError, MultiComponentKressGeometryError) as exc:
            trial = BirthTrial(factor, radius, None, None, None, None, False, f"invalid_geometry: {exc}", candidate)
            trials.append(trial)
            continue
        production_delta = production.loss - production_base.loss
        if production_delta >= 0.0:
            trial = BirthTrial(factor, radius, production.loss, None, production_delta, None, False, "production_objective_not_decreased", candidate)
            trials.append(trial)
            continue
        try:
            refined = evaluate_multiradial_objective(
                candidate, data, refined_geometry_config, solve_config=solve_config
            )
        except (OrderedSDFGeometryError, MultiComponentKressGeometryError) as exc:
            trial = BirthTrial(factor, radius, production.loss, None, production_delta, None, False, f"refined_invalid_geometry: {exc}", candidate)
            trials.append(trial)
            continue
        refined_delta = refined.loss - refined_base.loss
        reason = None
        if refined_delta >= 0.0:
            reason = "refined_objective_not_decreased"
        elif min(-production_delta, -refined_delta) <= 5.0 * abs(production_delta - refined_delta) + 1.0e-12:
            reason = "cross_resolution_margin_failed"
        trial = BirthTrial(
            factor,
            radius,
            production.loss,
            refined.loss,
            production_delta,
            refined_delta,
            reason is None,
            reason,
            candidate,
        )
        trials.append(trial)
        if trial.accepted:
            accepted.append(trial)
    selected = min(accepted, key=lambda item: float(item.production_loss)) if accepted else None
    return BirthResult(
        initial_state=state,
        selected_state=None if selected is None else selected.state,
        trials=tuple(trials),
        production_base_loss=production_base.loss,
        refined_base_loss=refined_base.loss,
        stop_reason="accepted" if selected is not None else "no_acceptable_birth",
    )


@dataclass(frozen=True)
class MultiRadialFDIteration:
    iteration: int
    state: MultiRadialFourierState
    parameter_names: tuple[str, ...]
    parameter_vector: np.ndarray
    loss: float
    relative_l2_error: float
    gradient: np.ndarray
    step: np.ndarray
    damping: float
    evaluation_count: int
    maximum_system_residual: float


@dataclass(frozen=True)
class MultiRadialFDResult:
    iterations: tuple[MultiRadialFDIteration, ...]
    final_state: MultiRadialFourierState
    converged: bool
    stop_reason: str
    evaluation_count: int
    infeasible_trial_count: int
    total_seconds: float


def run_multiradial_fd_inverse(
    initial_state: MultiRadialFourierState,
    data: ComplexScatteredData,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    solve_config: MultiComponentKressSolveConfig,
    config: ParameterFDConfig,
    progress_callback: Callable[[MultiRadialFDIteration], None] | None = None,
) -> MultiRadialFDResult:
    """Bounded central-FD LM optimizer for one fixed multi-radial topology."""

    if not isinstance(initial_state, MultiRadialFourierState):
        raise TypeError("initial_state must be MultiRadialFourierState.")
    if not isinstance(config, ParameterFDConfig):
        raise TypeError("config must be ParameterFDConfig.")
    if config.infeasible_trial_policy != "reject":
        raise ValueError("the topology experiment requires infeasible_trial_policy='reject'.")
    parameter_count = initial_state.parameter_count
    if parameter_count > config.max_parameters:
        raise ValueError("state exceeds config.max_parameters.")
    fd_steps = config.resolved_finite_difference_steps(parameter_count)
    max_steps = config.resolved_max_steps(parameter_count)
    accepted_state = initial_state
    cache: dict[bytes, MultiRadialObjectiveEvaluation | None] = {}
    evaluation_count = 0
    infeasible_count = 0
    started = perf_counter()

    def evaluate(state: MultiRadialFourierState) -> MultiRadialObjectiveEvaluation | None:
        nonlocal evaluation_count, infeasible_count
        key = np.asarray(state.parameter_vector()).tobytes()
        if key in cache:
            return cache[key]
        evaluation_count += 1
        try:
            result = evaluate_multiradial_objective(
                state, data, geometry_config, solve_config=solve_config
            )
        except (OrderedSDFGeometryError, MultiComponentKressGeometryError):
            infeasible_count += 1
            result = None
        cache[key] = result
        return result

    def jacobian(state: MultiRadialFourierState) -> tuple[np.ndarray, int]:
        columns: list[np.ndarray] = []
        frozen = 0
        for index, step_size in enumerate(fd_steps):
            step = np.zeros(parameter_count)
            step[index] = step_size
            try:
                plus_state = state.incremented(step)
                minus_state = state.incremented(-step)
            except ValueError:
                frozen += 1
                columns.append(np.zeros_like(current.residual))
                continue
            plus = evaluate(plus_state)
            minus = evaluate(minus_state)
            if plus is None or minus is None:
                frozen += 1
                columns.append(np.zeros_like(current.residual))
            else:
                columns.append((plus.residual - minus.residual) / (2.0 * step_size))
        return np.column_stack(columns), frozen

    current = evaluate(accepted_state)
    if current is None:
        raise ValueError("initial_state is not solver-ready.")
    matrix, frozen_columns = jacobian(accepted_state)
    gradient = matrix.T @ current.residual
    records: list[MultiRadialFDIteration] = []
    damping = config.initial_damping

    def record(iteration: int, step: np.ndarray, used_damping: float) -> None:
        item = MultiRadialFDIteration(
            iteration=iteration,
            state=accepted_state,
            parameter_names=accepted_state.parameter_names,
            parameter_vector=accepted_state.parameter_vector(),
            loss=current.loss,
            relative_l2_error=current.relative_l2_error,
            gradient=_readonly(gradient, dtype=np.float64),
            step=_readonly(step, dtype=np.float64),
            damping=float(used_damping),
            evaluation_count=evaluation_count,
            maximum_system_residual=current.maximum_system_residual,
        )
        records.append(item)
        if progress_callback is not None:
            progress_callback(item)

    record(0, np.zeros(parameter_count), damping)
    converged = False
    stop_reason = "maximum_iterations"
    if current.loss <= config.loss_tolerance:
        converged, stop_reason = True, "loss_tolerance"
    elif np.linalg.norm(gradient, ord=np.inf) <= config.gradient_tolerance:
        converged, stop_reason = True, "gradient_tolerance"

    for iteration in range(1, config.max_iterations + 1):
        if converged:
            break
        normal = matrix.T @ matrix
        scaling = np.maximum(np.diag(normal), 1.0)
        accepted_evaluation = None
        accepted_candidate = None
        accepted_step = None
        used_damping = damping
        trial_damping = damping
        for _ in range(config.max_damping_trials):
            try:
                proposed = np.linalg.solve(
                    normal + trial_damping * np.diag(scaling), -gradient
                )
            except np.linalg.LinAlgError:
                trial_damping *= config.damping_increase
                continue
            proposed = np.clip(proposed, -max_steps, max_steps)
            for backtrack in range(config.max_backtracks + 1):
                step = (0.5**backtrack) * proposed
                relative_step = float(
                    np.linalg.norm(step)
                    / max(np.linalg.norm(accepted_state.parameter_vector()), 1.0)
                )
                if relative_step <= config.relative_step_tolerance:
                    continue
                try:
                    candidate = accepted_state.incremented(step)
                except ValueError:
                    infeasible_count += 1
                    continue
                candidate_evaluation = evaluate(candidate)
                if candidate_evaluation is not None and candidate_evaluation.loss < current.loss:
                    accepted_evaluation = candidate_evaluation
                    accepted_candidate = candidate
                    accepted_step = step
                    used_damping = trial_damping
                    break
            if accepted_evaluation is not None:
                break
            trial_damping *= config.damping_increase
        if accepted_evaluation is None or accepted_candidate is None or accepted_step is None:
            stop_reason = "infeasible_jacobian" if frozen_columns else "no_decreasing_step"
            break
        previous_loss = current.loss
        accepted_state = accepted_candidate
        current = accepted_evaluation
        damping = max(used_damping * config.damping_decrease, np.finfo(float).tiny)
        matrix, frozen_columns = jacobian(accepted_state)
        gradient = matrix.T @ current.residual
        record(iteration, accepted_step, used_damping)
        if current.loss <= config.loss_tolerance:
            converged, stop_reason = True, "loss_tolerance"
        elif previous_loss - current.loss <= config.loss_tolerance:
            converged, stop_reason = frozen_columns == 0, (
                "loss_change_tolerance" if frozen_columns == 0 else "infeasible_jacobian"
            )
        elif np.linalg.norm(gradient, ord=np.inf) <= config.gradient_tolerance:
            converged, stop_reason = True, "gradient_tolerance"
        elif float(np.linalg.norm(accepted_step)) / max(
            np.linalg.norm(accepted_state.parameter_vector()), 1.0
        ) <= config.relative_step_tolerance:
            converged, stop_reason = frozen_columns == 0, (
                "relative_step_tolerance" if frozen_columns == 0 else "infeasible_jacobian"
            )

    return MultiRadialFDResult(
        iterations=tuple(records),
        final_state=accepted_state,
        converged=converged,
        stop_reason=stop_reason,
        evaluation_count=evaluation_count,
        infeasible_trial_count=infeasible_count,
        total_seconds=float(perf_counter() - started),
    )


def iteration01_solve_config() -> MultiComponentKressSolveConfig:
    """The frozen physical-clearance Kress configuration."""

    return MultiComponentKressSolveConfig(
        assembly=MultiComponentAssemblyConfig(minimum_absolute_clearance=0.010)
    )


def iteration01_optimizer_config() -> ParameterFDConfig:
    """The frozen iteration-01 six/three-variable LM policy."""

    return ParameterFDConfig(
        max_iterations=15,
        finite_difference_steps=1.0e-4,
        max_steps=2.0e-2,
        initial_damping=1.0e-3,
        damping_increase=10.0,
        damping_decrease=0.3,
        max_damping_trials=6,
        max_backtracks=8,
        gradient_tolerance=1.0e-8,
        loss_tolerance=1.0e-12,
        relative_step_tolerance=1.0e-8,
        infeasible_trial_policy="reject",
    )


__all__ = [
    "BirthResult",
    "BirthTrial",
    "DEFAULT_TD_CHUNK_SIZE",
    "FROZEN_BIRTH_RADIUS_FACTORS",
    "MultiRadialFDIteration",
    "MultiRadialFDResult",
    "MultiRadialFourierState",
    "MultiRadialObjectiveEvaluation",
    "TDRasterResult",
    "TopologicalDerivativeResult",
    "build_td_raster",
    "circle_radial_fourier_state",
    "evaluate_birth_ladder",
    "evaluate_current_domain_topological_derivative",
    "evaluate_multiradial_objective",
    "iteration01_optimizer_config",
    "iteration01_solve_config",
    "run_multiradial_fd_inverse",
]
