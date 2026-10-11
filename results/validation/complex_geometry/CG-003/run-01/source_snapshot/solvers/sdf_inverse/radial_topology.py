"""Explicit Fourier objective, material sensitivities and fixed-topology LM.

The automatic birth/death/split/merge controller lives in topology_controller.
Iteration-01 entry points retain their original numerical policies.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter
from typing import Any, Callable

import numpy as np
from scipy import ndimage
from gpr_bem_kress.execution import hankel1

from gpr_bem_kress.materials import Material
from gpr_bem_kress.multicomponent import (
    MultiComponentAssemblyConfig,
    MultiComponentKressGeometryError,
    MultiComponentKressSolveConfig,
    adapt_multicomponent_boundary,
    validate_multicomponent_admissibility,
    build_multicomponent_exterior_receiver_operator,
    build_multicomponent_kress_tmz_frequency_system,
    multicomponent_incident_trace_on_boundary,
    evaluate_multicomponent_interior_total_field,
)
from ordered_boundary import OrderedBoundary2D
from ordered_boundary.validation_cache import (
    current_validation_cache, fit_geometry_validation, validation_timed,
)
from sdf_bem_multicomponent import (
    PairedForwardProblem,
    predict_multicomponent_kress_paired_boundary_response,
)

from .curve_updates import (
    RadialFourierCurveState,
    polar_angle_gauge_fixed_point,
    polar_angle_gauge_tangent_basis,
    radial_fourier_state_curve,
)
from .explicit_fourier import CartesianFourierCurveState, circle_cartesian_fourier_state
from .geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from .runtime import current_runtime, inverse_execution, jacobian_selection
from .optimization import (
    ComplexScatteredData,
    ParameterFDConfig,
    normalized_complex_residual,
)


DEFAULT_TD_CHUNK_SIZE = 4096
FROZEN_BIRTH_RADIUS_FACTORS = (1.0, 0.75, 0.5, 0.35)


def component_radius_floor(component) -> float:
    """Conservative feature radius of one explicit component.

    Keeping the certificate resolved prevents LM approaching a singular pinch
    while the topology controller prepares a discrete cut.  Both charts bound
    the same quantity -- the minimum distance from the component's own centre
    to its boundary -- whenever that quantity is a feature radius at all.  A
    Cartesian fallback contour that is *not* star-shaped about its centre has
    no such interpretation, so it falls back to the equivalent-area radius it
    used before the polar-angle gauge existed.
    """
    if isinstance(component, CartesianFourierCurveState):
        return float(component.minimum_radius_lower_bound_m
                     if component.is_star_shaped_about_center else component.mean_radius_m)
    return float(component.minimum_radius_lower_bound_m)


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
    """Immutable explicit components, retaining the iteration-01 API name.

    Radial and Cartesian Fourier charts share the vector/rebuild/Kress seam.
    ``None`` denotes an empty domain in the topology controller.
    """

    components: tuple[RadialFourierCurveState | CartesianFourierCurveState, ...]

    def __post_init__(self) -> None:
        components = tuple(self.components)
        if not components:
            raise ValueError("At least one radial component is required.")
        if not all(isinstance(item, (RadialFourierCurveState, CartesianFourierCurveState)) for item in components):
            raise TypeError("components must contain explicit Fourier curve states.")
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
            if isinstance(component, CartesianFourierCurveState):
                result.extend(component.parameter_names)
                continue
            prefix = component.component_id
            result.extend((f"{prefix}.radius_m", f"{prefix}.center_x_m", f"{prefix}.center_y_m"))
            for mode in range(2, component.maximum_mode + 1):
                result.extend((f"{prefix}.radius_cos_{mode}_m", f"{prefix}.radius_sin_{mode}_m"))
        return tuple(result)

    def parameter_vector(self) -> np.ndarray:
        """Flatten absolute parameters without introducing an ID registry."""

        values: list[float] = []
        for component in self.components:
            if isinstance(component, CartesianFourierCurveState):
                values.extend(component.parameter_vector())
                continue
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
        rebuilt: list[RadialFourierCurveState | CartesianFourierCurveState] = []
        for component, component_slice in zip(self.components, self.parameter_slices):
            local = vector[component_slice]
            if isinstance(component, CartesianFourierCurveState):
                rebuilt.append(component.from_parameter_vector(local))
                continue
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

    def polar_angle_gauge_fixed(self) -> tuple["MultiRadialFourierState", float]:
        """Re-express every Cartesian component in its own polar-angle parameter.

        Radial components are already gauge-fixed and are returned untouched.
        Every Cartesian component must be projectable, or this raises: there is
        no skip.  An un-projectable component is one that has left the
        star-shaped set, and passing it through would let the next step be
        taken in the free chart, which is the drift the gauge exists to stop.
        Callers reach this only under the Cartesian chart, whose contour fits
        already refuse anything the gauge cannot hold, so a failure here is a
        step to reject rather than a state to tolerate.

        The second value combines band truncation with a displacement bound
        between the state and its next gauge projection. Band truncation alone
        cannot detect a phase-shifted circle. The residual is zero to roundoff
        for a canonical circle or an exact radial embedding one band lower.
        """
        rebuilt: list[RadialFourierCurveState | CartesianFourierCurveState] = []
        truncation = 0.0
        for component in self.components:
            if not isinstance(component, CartesianFourierCurveState):
                rebuilt.append(component)
                continue
            regauged, maximum = polar_angle_gauge_fixed_point(component)
            rebuilt.append(regauged)
            truncation = max(truncation, float(maximum))
        return MultiRadialFourierState(tuple(rebuilt)), truncation

    def gauge_tangent_basis(self) -> np.ndarray:
        """Orthonormal basis of the directions a gauge-fixed step may take.

        A radial component contributes its own coordinates unchanged; a
        Cartesian one contributes the linear subspace its gauge fixes, which is
        much smaller than its coefficient count.  Components occupy disjoint
        parameter slices, so the block-diagonal assembly is orthonormal.  A
        purely radial state gets the identity and is unaffected.
        """
        rows: list[np.ndarray] = []
        for component, component_slice in zip(self.components, self.parameter_slices):
            width = component_slice.stop - component_slice.start
            local = (polar_angle_gauge_tangent_basis(component.maximum_mode)
                     if isinstance(component, CartesianFourierCurveState) else np.eye(width))
            block = np.zeros((len(local), self.parameter_count), dtype=np.float64)
            block[:, component_slice] = local
            rows.append(block)
        return np.vstack(rows) if rows else np.zeros((0, self.parameter_count))

    def incremented(self, step: Any) -> "MultiRadialFourierState":
        delta = np.asarray(step, dtype=np.float64)
        if delta.shape != (self.parameter_count,) or not np.all(np.isfinite(delta)):
            raise ValueError(f"step must contain {self.parameter_count} finite values.")
        return self.from_parameter_vector(self.parameter_vector() + delta)

    def appended(self, component: RadialFourierCurveState | CartesianFourierCurveState) -> "MultiRadialFourierState":
        if not isinstance(component, (RadialFourierCurveState, CartesianFourierCurveState)):
            raise TypeError("component must be an explicit Fourier curve state.")
        return MultiRadialFourierState(self.components + (component,))

    def boundary(self, geometry_config: OrderedSDFGeometryConfig) -> OrderedBoundary2D:
        """Build every component with full validation in stored order."""

        if not isinstance(geometry_config, OrderedSDFGeometryConfig):
            raise TypeError("geometry_config must be an OrderedSDFGeometryConfig.")
        return OrderedBoundary2D(
            tuple(
                component.boundary_curve(geometry_config) if isinstance(component, CartesianFourierCurveState) else radial_fourier_state_curve(
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


@inverse_execution
def evaluate_current_domain_topological_derivative(
    state: MultiRadialFourierState | None,
    data: ComplexScatteredData,
    points: Any,
    *,
    geometry_config: OrderedSDFGeometryConfig | None = None,
    solve_config: MultiComponentKressSolveConfig | None = None,
    chunk_size: int = DEFAULT_TD_CHUNK_SIZE,
    material_change: str = "addition",
) -> TopologicalDerivativeResult:
    """Evaluate the exact project-convention TD, solving one RHS batch/frequency.

    Physical source row ``s`` is paired only with reciprocal receiver-source
    row ``s``.  Receiver-point evaluation is chunked after the boundary system
    has been solved; no inspection-point solve is performed.

    ``material_change='removal'`` evaluates interior total fields and reverses
    the squared-wavenumber contrast. For this nonmagnetic scalar convention,
    D_minus = Re[(k_e^2-k_i^2) sum(conj(residual) u_i u_i_recip)] with exactly
    the same column scales and frequency weights as the addition derivative.
    Removal points must lie strictly in one current inclusion.
    """

    from .work_accounting import record_work
    record_work(td_evaluation_count=1)
    if material_change not in ("addition", "removal"):
        raise ValueError("material_change must be addition or removal.")
    if material_change == "removal" and state is None:
        raise ValueError("Material removal requires a nonempty current domain.")
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
            record_work(td_frequency_solve_count=1)
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
            elif material_change == "removal":
                assert total_traces is not None
                total = evaluate_multicomponent_interior_total_field(
                    boundary, local_points, k_interior, *total_traces
                )
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
            if material_change == "removal":
                contrast = -contrast
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


@validation_timed('admissible')
def multiradial_geometry_admissible(
    state: MultiRadialFourierState | None,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    solve_config: MultiComponentKressSolveConfig | None = None,
) -> bool:
    """Whether one state's boundary is Kress-admissible at this discretisation.

    Geometry only: it builds the boundary and runs the same component-grid,
    topology and clearance checks the assembly runs, without a forward solve.
    The distinction matters because those checks are discretisation-dependent.
    An inscribed polygon overstates the gap between two components, and it
    overstates it more at 64 nodes than at 128, so a state the production
    resolution accepts can be refused by the refined one.  Asking the question
    directly costs a curve evaluation instead of a BIE solve.
    """

    if state is None:
        return True
    try:
        cache = current_validation_cache()
        validator = (validate_multicomponent_admissibility
                     if cache is not None and cache.mode == 'certified'
                     else adapt_multicomponent_boundary)
        validator(
            state.boundary(geometry_config),
            config=None if solve_config is None else solve_config.assembly,
        )
    except (OrderedSDFGeometryError, MultiComponentKressGeometryError):
        return False
    return True


@inverse_execution
def evaluate_multiradial_objective(
    state: MultiRadialFourierState,
    data: ComplexScatteredData,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    solve_config: MultiComponentKressSolveConfig | None = None,
    compiled_evaluator: Any = None,
) -> MultiRadialObjectiveEvaluation:
    """Evaluate Kress; an explicit fit-local evaluator may reduce the system."""

    from .work_accounting import record_work
    record_work(evaluation_count=1)
    started = perf_counter()
    compiled = None if compiled_evaluator is None else compiled_evaluator.evaluate(state)
    if compiled is None:
        boundary = state.boundary(geometry_config)
        forward = predict_multicomponent_kress_paired_boundary_response(
            boundary, data.forward_problem, solve_config=solve_config)
        prediction = forward.scattered_response
        maximum_system_residual = float(np.max(forward.linear_system_relative_residuals))
        record_work(forward_frequency_solve_count=len(forward.linear_system_relative_residuals))
    else:
        prediction = compiled['prediction']
        maximum_system_residual = compiled['maximum_system_residual']
    record_work(forward_evaluation_count=1)
    residual, relative = normalized_complex_residual(
        prediction,
        data.observed_scattered_response,
        data.frequency_weights,
    )
    return MultiRadialObjectiveEvaluation(
        state=state,
        loss=0.5 * float(np.dot(residual, residual)),
        relative_l2_error=relative,
        residual=_readonly(residual, dtype=np.float64),
        prediction=_readonly(prediction, dtype=np.complex128),
        maximum_system_residual=maximum_system_residual,
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
    chart: str = "radial",
) -> BirthResult:
    """Score the frozen finite-radius ladder at both Kress resolutions.

    ``chart`` selects only which exact circle the newborn is expressed in.  A
    circle is mode one alone in either chart, so the ladder's geometry, its
    acceptance rule and its recorded radii are identical.
    """

    if chart not in ("radial", "cartesian"):
        raise ValueError("chart must be 'radial' or 'cartesian'.")
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
        newborn = (circle_cartesian_fourier_state(center, radius, component_id)
                   if chart == "cartesian" else
                   circle_radial_fourier_state(center, radius, component_id))
        candidate = state.appended(newborn)
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
    # Legacy field name: includes the gauge-displacement bound as well as truncation.
    gauge_truncation_maximum_m: float = 0.0


@dataclass(frozen=True)
class MultiRadialFDResult:
    iterations: tuple[MultiRadialFDIteration, ...]
    final_state: MultiRadialFourierState
    converged: bool
    stop_reason: str
    evaluation_count: int
    infeasible_trial_count: int
    total_seconds: float
    # Trials refused only because a *finer* discretisation than the one being
    # optimized at calls them inadmissible. Zero means the guard never bit.
    feasibility_rejected_trial_count: int = 0
    # Jacobian columns, summed over every assembly, that were measured on one
    # feasible side because the other side was refused.
    one_sided_jacobian_column_count: int = 0
    # Columns no admissible probe reached on either side. These are the only
    # genuinely unknown derivatives; they are zero because nothing measured them.
    unresolved_jacobian_column_count: int = 0


@dataclass(frozen=True)
class StepSafeguards:
    """Opt-in step controls of the legacy single-object inverse.

    This LM was written for topology work and never carried the four controls
    that `neural_optimization.AlternatingNeuralInverseConfig` added against a
    measured failure: a growing ripple at the highest available mode, because
    undamped Gauss--Newton inverts the near-null column of an unresolvable
    harmonic, a clipped or rescaled oversized step keeps that direction, and
    an any-decrease test accepts the result.  The defaults are the legacy
    values.  They apply to Cartesian components under the polar-angle gauge,
    whose reduced directions are translation, uniform radius and unit radial
    harmonics 2..K-1 (``polar_angle_gauge_tangent_basis``).

    * ``curvature_penalty_weight``: a ``w * max(diag G) * m**4`` ridge on
      radial harmonic ``m``, outside the damping multiplier, so an
      unresolvable mode is bought at its bending cost.  It prices the step,
      not the state, and leaves stationary points unchanged.
    * ``minimum_damping``: floor on the carried damping.
    * ``maximum_normal_displacement_m``: largest normal boundary move of a
      proposed step.  The damping is raised (and then refined in log lambda)
      until the step fits; rescaling is the fallback once the search is spent.
    * ``armijo_coefficient``: accept only a realized decrease of at least this
      fraction of the linear model's predicted decrease ``g . d``.
    """

    curvature_penalty_weight: float = 1.0e-4
    minimum_damping: float = 1.0e-6
    maximum_normal_displacement_m: float | None = 2.0e-3
    armijo_coefficient: float = 1.0e-4
    max_trust_region_solves: int = 8
    trust_region_refinement_steps: int = 8
    minimum_displacement_samples: int = 512

    def __post_init__(self) -> None:
        for name in ("curvature_penalty_weight", "minimum_damping", "armijo_coefficient"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative.")
            object.__setattr__(self, name, value)
        if self.armijo_coefficient >= 1.0:
            raise ValueError("armijo_coefficient must be smaller than one.")
        bound = self.maximum_normal_displacement_m
        if bound is not None:
            bound = float(bound)
            if not math.isfinite(bound) or bound <= 0.0:
                raise ValueError("maximum_normal_displacement_m must be positive or None.")
            object.__setattr__(self, "maximum_normal_displacement_m", bound)
        for name in ("max_trust_region_solves", "trust_region_refinement_steps"):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or int(value) != value or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer.")
            object.__setattr__(self, name, int(value))
        object.__setattr__(self, "minimum_displacement_samples", _positive_integer(
            self.minimum_displacement_samples, name="minimum_displacement_samples"))


def gauge_radial_orders(state: MultiRadialFourierState) -> np.ndarray:
    """Radial harmonic order of each polar-gauge direction; 0 for rigid/size."""
    orders: list[float] = []
    for component in state.components:
        if not isinstance(component, CartesianFourierCurveState):
            raise ValueError("step safeguards require Cartesian components.")
        orders += [0.0, 0.0, 0.0] + [float(m) for m in range(2, component.maximum_mode) for _ in range(2)]
    return np.asarray(orders, dtype=np.float64)


def gauge_normal_displacement_operator(
    state: MultiRadialFourierState, basis: np.ndarray, minimum_samples: int = 512
) -> np.ndarray:
    """Linear map from a reduced step to normal boundary moves at sample points.

    The Cartesian chart is affine in its coefficients, so the displacement at
    fixed parameter is exact; its normal component is the shape change.  Rows
    stack every component's uniform parameter samples.
    """
    from .curve_updates import cartesian_fourier_displacement_basis

    blocks: list[np.ndarray] = []
    for component, component_slice in zip(state.components, state.parameter_slices):
        if not isinstance(component, CartesianFourierCurveState):
            raise ValueError("step safeguards require Cartesian components.")
        modes = component.maximum_mode
        count = max(int(minimum_samples), 64 * (modes + 1))
        angles = 2.0 * np.pi * np.arange(count, dtype=np.float64) / count
        orders = np.arange(modes + 1, dtype=np.float64)
        phase = np.outer(angles, orders)
        tangent = (-(np.sin(phase) * orders) @ component.cosine_coefficients
                   + (np.cos(phase) * orders) @ component.sine_coefficients)
        speed = np.linalg.norm(tangent, axis=1)
        if not np.all(speed > 0.0):
            raise ValueError("current curve has a vanishing parameter speed.")
        normals = np.column_stack((tangent[:, 1], -tangent[:, 0])) / speed[:, None]
        local = np.einsum("npd,nd->np", cartesian_fourier_displacement_basis(
            angles, maximum_mode=modes), normals)
        block = np.zeros((count, state.parameter_count), dtype=np.float64)
        block[:, component_slice] = local
        blocks.append(block)
    return np.vstack(blocks) @ np.asarray(basis, dtype=np.float64).T


@inverse_execution
@fit_geometry_validation
def run_multiradial_fd_inverse(
    initial_state: MultiRadialFourierState,
    data: ComplexScatteredData,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    solve_config: MultiComponentKressSolveConfig,
    config: ParameterFDConfig,
    progress_callback: Callable[[MultiRadialFDIteration], None] | None = None,
    minimum_component_radius_m: float = 0.0,
    cartesian_gauge: bool = False,
    feasibility_geometry_configs: tuple[OrderedSDFGeometryConfig, ...] = (),
    feasible_fd_jacobian: bool = False,
    loss_change_stopping: bool = True,
    candidate_acceptance_callback: Callable[[MultiRadialObjectiveEvaluation, MultiRadialObjectiveEvaluation], bool] | None = None,
    jacobian_batch_callback: Callable[[int], None] | None = None,
    accepted_state_callback: Callable[[int, MultiRadialObjectiveEvaluation], None] | None = None,
    evaluation_event_callback: Callable[[str], None] | None = None,
    diagnostic_callback: Callable[[str, dict], None] | None = None,
    jacobian_mode: str | None = None,
    analytic_constraint_policy: str | None = None,
    step_safeguards: StepSafeguards | None = None,
) -> MultiRadialFDResult:
    """Bounded LM optimizer for one fixed Fourier topology.

    ``step_safeguards`` (default ``None``: the historical path, unchanged)
    enables the legacy single-object step controls; see
    :class:`StepSafeguards`. It requires ``cartesian_gauge``.

    The shared compiled runtime defaults to guarded reciprocal Cartesian
    Jacobians and reduced multi-object solves at >=256 nodes, with full-Kress
    fallbacks, FD-compatible stencils, and real-argument CPU kernels. Radial
    coefficients use FD. ``jacobian_mode`` overrides derivative selection;
    ``inverse_runtime('reference')`` restores FD/reference CPU throughout a call.

    Optional callbacks allow experiment-owned candidate validation, batch
    reservations and accepted-state checkpoints. Exceptions propagate to the
    owner so it can preserve partial evidence. ``loss_change_stopping=False``
    disables only accepted-loss-change stopping, retaining the configured
    objective target and all other convergence tests.
    ``diagnostic_callback`` receives Jacobian completion and candidate/feasibility
    events. It may interrupt before a step; it does not change the default math.

    With ``cartesian_gauge`` the retraction is gauge-fixing: every retracted
    state, in the Jacobian as well as on the accepted step, is re-expressed in
    its own polar-angle parameter. Jacobians and steps use the subspace that
    preserves this gauge, including removal of the phase null direction. The Cartesian chart
    needs this.  Left free, its parameter drifts along directions the data
    cannot see, the quadrature degrades and the shape stops improving; the
    softer controls that were measured instead all failed.  Radial components
    are unaffected either way, so a purely radial state takes the identical
    code path at ``cartesian_gauge=True``.

    ``feasibility_geometry_configs`` names *additional* discretisations at
    which every trial state must be geometrically admissible.  The objective
    is still evaluated only at ``geometry_config``; the extra resolutions cost
    curve evaluations, not solves.  Left empty, the optimizer searches exactly
    the feasible set its own resolution defines -- and a caller that evaluates
    the result at a finer one can then be handed a state that resolution
    refuses.

    ``feasible_fd_jacobian`` keeps the derivative information that survives an
    active constraint.  A refused probe says a step is inadmissible; it does not
    say the derivative is zero, and writing a zero there feeds a number nothing
    measured into the normal equations.  With the flag on, each side of every
    difference quotient is attempted independently: both sides give the central
    difference as before, one side gives the one-sided quotient at that same
    step, and only a direction blocked on *both* sides stays an unresolved zero.
    A small gradient then certifies stationarity only when no column is
    unresolved. In the reference FD profile, leaving this flag off reproduces
    the historical stencil behavior. Analytic mode applies the selected
    ``analytic_constraint_policy`` to infeasible stencils.
    """

    # All existing topology/continuation callers inherit the shared runtime.
    # Unsupported radial coefficient bridges retain FD under the auto policy.
    selected = current_runtime()
    jacobian_mode = jacobian_selection(initial_state, jacobian_mode)
    analytic_constraint_policy = (selected.analytic_constraint_policy
        if analytic_constraint_policy is None else analytic_constraint_policy)
    if jacobian_mode not in ("fd", "analytic"):
        raise ValueError("jacobian_mode must be 'auto', 'fd' or 'analytic'.")
    if analytic_constraint_policy not in ("true", "fd_compatible"):
        raise ValueError("analytic_constraint_policy must be 'true' or 'fd_compatible'.")
    # TOP-016 opt-in orchestration hooks. Defaults retain every legacy step.
    # Candidate acceptance supplements the existing strict production decrease;
    # the callback may enforce refined loss agreement or external work limits.
    # Checkpoints precede Jacobians so a budget interruption retains the newest
    # accepted state, without claiming an uncomputed terminal gradient.
    if not isinstance(loss_change_stopping, bool):
        raise TypeError("loss_change_stopping must be boolean.")
    for callback in (candidate_acceptance_callback, jacobian_batch_callback, accepted_state_callback,
                     evaluation_event_callback, diagnostic_callback):
        if callback is not None and not callable(callback):
            raise TypeError("optimizer hooks must be callable or None.")

    if not isinstance(initial_state, MultiRadialFourierState):
        raise TypeError("initial_state must be MultiRadialFourierState.")
    if not np.isfinite(minimum_component_radius_m) or minimum_component_radius_m < 0:
        raise ValueError("minimum_component_radius_m must be finite and nonnegative.")
    if not isinstance(config, ParameterFDConfig):
        raise TypeError("config must be ParameterFDConfig.")
    if config.infeasible_trial_policy != "reject":
        raise ValueError("the topology experiment requires infeasible_trial_policy='reject'.")
    if step_safeguards is not None:
        if not isinstance(step_safeguards, StepSafeguards):
            raise TypeError("step_safeguards must be StepSafeguards or None.")
        if not cartesian_gauge:
            raise ValueError("step_safeguards require cartesian_gauge=True.")
        gauge_radial_orders(initial_state)  # Cartesian components only.
    feasibility_configs = tuple(feasibility_geometry_configs)
    if not all(isinstance(item, OrderedSDFGeometryConfig) for item in feasibility_configs):
        raise TypeError("feasibility_geometry_configs must contain OrderedSDFGeometryConfig objects.")
    parameter_count = initial_state.parameter_count
    if parameter_count > config.max_parameters:
        raise ValueError("state exceeds config.max_parameters.")
    fd_steps = config.resolved_finite_difference_steps(parameter_count)
    max_steps = config.resolved_max_steps(parameter_count)
    accepted_state = initial_state
    cache: dict[bytes, MultiRadialObjectiveEvaluation | None] = {}
    evaluation_count = 0
    infeasible_count = 0
    feasibility_rejected = 0
    started = perf_counter()

    compiled_evaluator = None
    if (selected.continuation_backend == "compiled" and geometry_config.num_nodes >= 256
            and jacobian_mode == "analytic"):
        from .compiled_jacobian import CompiledEvaluator
        directions = initial_state.gauge_tangent_basis() if cartesian_gauge else np.eye(parameter_count)
        compiled_evaluator = CompiledEvaluator(data, geometry_config, solve_config, directions)

    def evaluate(state: MultiRadialFourierState) -> MultiRadialObjectiveEvaluation | None:
        nonlocal evaluation_count, infeasible_count, feasibility_rejected
        key = np.asarray(state.parameter_vector()).tobytes()
        if key in cache:
            if evaluation_event_callback is not None:
                evaluation_event_callback("cache_hit")
            return cache[key]
        if evaluation_event_callback is not None:
            evaluation_event_callback("cache_miss")
        evaluation_count += 1
        try:
            if any(component_radius_floor(c) < minimum_component_radius_m for c in state.components):
                raise OrderedSDFGeometryError("Component is below the topology feature-radius floor.")
            if any(not multiradial_geometry_admissible(state, extra, solve_config=solve_config)
                   for extra in feasibility_configs):
                feasibility_rejected += 1
                raise OrderedSDFGeometryError(
                    "State is inadmissible at a required finer discretisation."
                )
            result = evaluate_multiradial_objective(
                state, data, geometry_config, solve_config=solve_config,
                **({} if compiled_evaluator is None else {'compiled_evaluator':compiled_evaluator})
            )
            if compiled_evaluator is not None and diagnostic_callback is not None:
                diagnostic_callback('compiled_backend', compiled_evaluator.snapshot())
        except (OrderedSDFGeometryError, MultiComponentKressGeometryError) as exc:
            infeasible_count += 1
            if diagnostic_callback is not None:
                diagnostic_callback("feasibility_refusal", dict(state=state, reason=str(exc)))
            result = None
        cache[key] = result
        return result

    def retract(state: MultiRadialFourierState, step: np.ndarray) -> tuple[MultiRadialFourierState, float]:
        candidate = state.incremented(step)
        if not cartesian_gauge:
            return candidate, 0.0
        return candidate.polar_angle_gauge_fixed()

    def probe(
        state: MultiRadialFourierState, step: np.ndarray
    ) -> MultiRadialObjectiveEvaluation | None:
        """One side of a difference quotient, or None if that side is refused."""
        try:
            trial = retract(state, step)[0]
        except (ValueError, OrderedSDFGeometryError) as exc:
            if diagnostic_callback is not None:
                diagnostic_callback("feasibility_refusal", dict(state=state, step=step, reason=str(exc)))
            return None
        return evaluate(trial)

    def jacobian(
        state: MultiRadialFourierState,
    ) -> tuple[np.ndarray, np.ndarray | None, int, int]:
        """Central differences along the directions the step may actually take.

        Under the Cartesian gauge those are the gauge-fixed subspace's basis
        directions, not the raw coefficients.  Probing a raw coefficient would
        be probing mostly off the subspace, where the retraction has to project
        the perturbation back and can refuse it outright -- and a refused probe
        freezes its column to zero, which corrupts every reachable direction
        that coefficient contributes to.  It also costs: band six has 26
        coefficients and 11 reachable directions.
        """
        basis = state.gauge_tangent_basis() if cartesian_gauge else None
        directions = np.eye(parameter_count) if basis is None else basis
        if jacobian_batch_callback is not None:
            # FD-compatible analytic mode may additionally evaluate one feasible
            # side per column. This is a conservative assembly-equivalent bound.
            jacobian_batch_callback(2 * len(directions) if jacobian_mode == "fd" else
                1 + len(directions) * (2 if analytic_constraint_policy == "fd_compatible" else 1))
        # A unit direction gets the configured step; a spread-out one gets the
        # same step in a norm-weighted sense, so the difference quotient is
        # measured at one scale across the basis.
        sizes = (fd_steps if basis is None
                 else np.sqrt((directions * directions) @ (fd_steps * fd_steps)))
        if jacobian_mode == "analytic":
            from .analytic_jacobian import cartesian_residual_jacobian
            base_evaluation = evaluate(state)
            if base_evaluation is None:
                raise ValueError("Analytic Jacobian base must be feasible.")
            matrix, prediction = cartesian_residual_jacobian(
                state, data, geometry_config, solve_config=solve_config, directions=directions,
                **({} if compiled_evaluator is None else {'compiled_evaluator':compiled_evaluator}))
            discrepancy = np.linalg.norm(prediction-base_evaluation.prediction)/max(
                np.linalg.norm(base_evaluation.prediction), np.finfo(float).tiny)
            if not np.isfinite(discrepancy) or discrepancy > 2e-11:
                raise FloatingPointError("Analytic base does not reproduce the objective prediction.")
            unresolved = one_sided = 0
            if analytic_constraint_policy == "fd_compatible":
                @validation_timed('stencil')
                def allowed(delta):
                    try:
                        trial = retract(state, delta)[0]
                        if any(component_radius_floor(c) < minimum_component_radius_m for c in trial.components):
                            return False
                        return all(multiradial_geometry_admissible(trial, g, solve_config=solve_config)
                                   for g in (geometry_config, *feasibility_configs))
                    except (ValueError, OrderedSDFGeometryError, MultiComponentKressGeometryError):
                        return False
                for index, (direction, size) in enumerate(zip(directions, sizes)):
                    step = size * direction
                    plus, minus = allowed(step), allowed(-step)
                    if plus and minus:
                        continue
                    if not feasible_fd_jacobian or not (plus or minus):
                        matrix[:, index] = 0.0
                        unresolved += 1
                    else:
                        sign = 1 if plus else -1
                        side = probe(state, sign*step)
                        if side is None:
                            matrix[:, index] = 0.0
                            unresolved += 1
                        else:
                            matrix[:, index] = (side.residual-base_evaluation.residual)/(sign*size)
                            one_sided += 1
            if diagnostic_callback is not None:
                diagnostic_callback("jacobian_complete", dict(state=state,
                    unresolved_columns=unresolved, one_sided_columns=one_sided,
                    directions=len(directions), matrix=_readonly(matrix, dtype=np.float64)))
            return matrix, basis, unresolved, one_sided
        # Cached, so the base residual a one-sided quotient needs is the one the
        # optimizer already holds at this state and costs no extra solve. It has
        # to come through evaluate() rather than be formed separately, or the
        # gauge it was fixed in could differ from the probes'.
        base = evaluate(state) if feasible_fd_jacobian else None
        columns: list[np.ndarray] = []
        unresolved = 0
        one_sided = 0
        for direction, step_size in zip(directions, sizes):
            step = step_size * direction
            if not feasible_fd_jacobian:
                try:
                    plus_state = retract(state, step)[0]
                    minus_state = retract(state, -step)[0]
                except (ValueError, OrderedSDFGeometryError):
                    unresolved += 1
                    columns.append(np.zeros_like(current.residual))
                    continue
                plus = evaluate(plus_state)
                minus = evaluate(minus_state)
                if plus is None or minus is None:
                    unresolved += 1
                    columns.append(np.zeros_like(current.residual))
                else:
                    columns.append((plus.residual - minus.residual) / (2.0 * step_size))
                continue
            # Independently: the shared try above abandons both sides when only
            # one of the two retractions fails.
            plus = probe(state, step)
            minus = probe(state, -step)
            if plus is not None and minus is not None:
                columns.append((plus.residual - minus.residual) / (2.0 * step_size))
            elif plus is not None and base is not None:
                # Forward and backward both estimate +Jd; the base residual is
                # the near end of the forward quotient and the far end of the
                # backward one.
                one_sided += 1
                columns.append((plus.residual - base.residual) / step_size)
            elif minus is not None and base is not None:
                one_sided += 1
                columns.append((base.residual - minus.residual) / step_size)
            else:
                unresolved += 1
                columns.append(np.zeros_like(current.residual))
        matrix = np.column_stack(columns)
        if diagnostic_callback is not None:
            diagnostic_callback("jacobian_complete", dict(state=state,
                unresolved_columns=unresolved, one_sided_columns=one_sided,
                directions=len(directions), matrix=_readonly(matrix, dtype=np.float64)))
        return matrix, basis, unresolved, one_sided

    gauge_truncation = 0.0
    if cartesian_gauge:
        # The first accepted state must satisfy the same gauge as every later
        # one, or iteration one measures a projection the trajectory then keeps.
        accepted_state, gauge_truncation = accepted_state.polar_angle_gauge_fixed()
    current = evaluate(accepted_state)
    if current is None:
        raise ValueError("initial_state is not solver-ready.")
    if accepted_state_callback is not None:
        accepted_state_callback(0, current)
    matrix, basis, unresolved_columns, one_sided_new = jacobian(accepted_state)
    one_sided_columns = one_sided_new
    unresolved_total = unresolved_columns
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
            gradient=_readonly(gradient if basis is None else basis.T @ gradient,
                               dtype=np.float64),
            step=_readonly(step, dtype=np.float64),
            damping=float(used_damping),
            evaluation_count=evaluation_count,
            maximum_system_residual=current.maximum_system_residual,
            gauge_truncation_maximum_m=float(gauge_truncation),
        )
        records.append(item)
        if progress_callback is not None:
            progress_callback(item)

    def gradient_stop() -> tuple[bool, str]:
        """A small gradient is stationarity only if every column was measured.

        The other two tolerance branches already refuse to certify a run with
        unresolved columns; this one did not, so a gradient whose norm came from
        zeros nothing measured could report convergence. The legacy path keeps
        that historical answer so arms recorded before the correction replay
        unchanged.
        """
        if feasible_fd_jacobian and unresolved_columns:
            return False, "infeasible_jacobian"
        return True, "gradient_tolerance"

    record(0, np.zeros(parameter_count), damping)
    converged = False
    stop_reason = "maximum_iterations"
    if current.loss <= config.loss_tolerance:
        converged, stop_reason = True, "loss_tolerance"
    elif np.linalg.norm(gradient, ord=np.inf) <= config.gradient_tolerance:
        converged, stop_reason = gradient_stop()

    for iteration in range(1, config.max_iterations + 1):
        if converged:
            break
        normal = matrix.T @ matrix
        scaling = np.maximum(np.diag(normal), 1.0)
        reduced_max_steps = (
            None if basis is None
            else np.min(np.where(np.abs(basis) > 1.0e-12,
                                 max_steps / np.maximum(np.abs(basis), 1.0e-12), np.inf), axis=1)
        )
        penalty = motion_map = None
        if step_safeguards is not None:
            # Referred to the best-determined column, so the ridge is invariant
            # to residual units and scale, as in the legacy inverse.
            reference = float(np.max(np.diag(normal)))
            if not math.isfinite(reference) or reference <= 0.0:
                reference = 1.0
            penalty = np.diag(step_safeguards.curvature_penalty_weight * reference
                              * gauge_radial_orders(accepted_state) ** 4)
            if step_safeguards.maximum_normal_displacement_m is not None:
                motion_map = gauge_normal_displacement_operator(
                    accepted_state, basis, step_safeguards.minimum_displacement_samples)

        def safeguarded_step(start: float) -> tuple[np.ndarray, float, float]:
            """Raise the damping until the normal move fits (legacy trust region).

            Raising the damping shortens the step and rotates it toward steepest
            descent; a clip or rescale would keep an unresolvable mode's
            direction. The decade search brackets the damping, a log-lambda
            bisection keeps the least over-damped feasible step, and rescaling
            is the fallback once the search is spent.
            """
            def solve(value: float) -> np.ndarray:
                result = np.linalg.solve(normal + value * np.diag(scaling) + penalty, -gradient)
                if not np.all(np.isfinite(result)):
                    raise np.linalg.LinAlgError("nonfinite safeguarded step")
                return result

            bound = step_safeguards.maximum_normal_displacement_m
            trial, infeasible = float(start), None
            attempted, step, maximum = trial, None, math.inf
            for _ in range(step_safeguards.max_trust_region_solves + 1):
                step = solve(trial)
                if motion_map is None:
                    return step, trial, math.nan
                maximum = float(np.max(np.abs(motion_map @ step)))
                if maximum <= bound:
                    if infeasible is None:
                        return step, trial, maximum
                    feasible, feasible_step, feasible_maximum = trial, step, maximum
                    for _ in range(step_safeguards.trust_region_refinement_steps):
                        midpoint = math.sqrt(infeasible * feasible)
                        try:
                            midpoint_step = solve(midpoint)
                        except np.linalg.LinAlgError:
                            break
                        value = float(np.max(np.abs(motion_map @ midpoint_step)))
                        if value <= bound:
                            feasible, feasible_step, feasible_maximum = midpoint, midpoint_step, value
                        else:
                            infeasible = midpoint
                    return feasible_step, feasible, feasible_maximum
                infeasible = attempted = trial
                trial *= config.damping_increase
            return step * (bound / maximum), attempted, bound

        def sufficient_decrease(candidate_loss: float, predicted: float | None) -> bool:
            """Armijo against the linear model; plain decrease without safeguards."""
            if predicted is None or not math.isfinite(predicted) or predicted >= 0.0:
                return True
            return candidate_loss <= current.loss + step_safeguards.armijo_coefficient * predicted

        accepted_evaluation = None
        accepted_candidate = None
        accepted_step = None
        accepted_truncation = 0.0
        used_damping = damping
        trial_damping = damping
        for _ in range(config.max_damping_trials):
            try:
                if step_safeguards is None:
                    proposed = np.linalg.solve(
                        normal + trial_damping * np.diag(scaling), -gradient
                    )
                else:
                    proposed, trial_damping, proposed_motion = safeguarded_step(trial_damping)
                    if diagnostic_callback is not None:
                        diagnostic_callback("step_safeguards", dict(kind="proposal",
                            damping=trial_damping, maximum_normal_displacement_m=proposed_motion))
            except np.linalg.LinAlgError:
                trial_damping *= config.damping_increase
                continue
            if basis is None:
                proposed = np.clip(proposed, -max_steps, max_steps)
            else:
                # Clip in the subspace's own coordinates. Clipping the rebuilt
                # coefficient vector instead would push the step out of the
                # gauge-fixed subspace, and the retraction would then have to
                # recover a step the clip had bent. The per-direction bound is
                # the tightest coefficient bound that direction can violate.
                reduced = np.clip(proposed, -reduced_max_steps, reduced_max_steps)
                proposed = basis.T @ reduced
            for backtrack in range(config.max_backtracks + 1):
                step = (0.5**backtrack) * proposed
                predicted = (None if step_safeguards is None
                             else float(gradient @ ((0.5**backtrack) * reduced)))
                relative_step = float(
                    np.linalg.norm(step)
                    / max(np.linalg.norm(accepted_state.parameter_vector()), 1.0)
                )
                if relative_step <= config.relative_step_tolerance:
                    continue
                if diagnostic_callback is not None:
                    diagnostic_callback("candidate_attempt", dict(state=accepted_state, step=step))
                try:
                    candidate, candidate_truncation = retract(accepted_state, step)
                except (ValueError, OrderedSDFGeometryError) as exc:
                    infeasible_count += 1
                    if diagnostic_callback is not None:
                        diagnostic_callback("feasibility_refusal", dict(state=accepted_state,
                            step=step, reason=str(exc)))
                    continue
                candidate_evaluation = evaluate(candidate)
                if diagnostic_callback is not None:
                    diagnostic_callback("candidate_evaluated", dict(base=current,
                        candidate=candidate_evaluation))
                if (step_safeguards is not None and diagnostic_callback is not None
                        and candidate_evaluation is not None):
                    diagnostic_callback("step_safeguards", dict(kind="candidate", backtrack=backtrack,
                        predicted_change=predicted, realized_change=candidate_evaluation.loss-current.loss,
                        sufficient_decrease=sufficient_decrease(candidate_evaluation.loss, predicted)))
                if (candidate_evaluation is not None and candidate_evaluation.loss < current.loss
                        and sufficient_decrease(candidate_evaluation.loss, predicted)
                        and (candidate_acceptance_callback is None
                             or candidate_acceptance_callback(current, candidate_evaluation))):
                    accepted_evaluation = candidate_evaluation
                    accepted_candidate = candidate
                    accepted_step = step
                    accepted_truncation = candidate_truncation
                    used_damping = trial_damping
                    break
            if accepted_evaluation is not None:
                break
            trial_damping *= config.damping_increase
        if accepted_evaluation is None or accepted_candidate is None or accepted_step is None:
            stop_reason = "infeasible_jacobian" if unresolved_columns else "no_decreasing_step"
            break
        previous_loss = current.loss
        accepted_state = accepted_candidate
        gauge_truncation = accepted_truncation
        current = accepted_evaluation
        damping = max(used_damping * config.damping_decrease, np.finfo(float).tiny
                      if step_safeguards is None else max(step_safeguards.minimum_damping, np.finfo(float).tiny))
        if accepted_state_callback is not None:
            accepted_state_callback(iteration, current)
        matrix, basis, unresolved_columns, one_sided_new = jacobian(accepted_state)
        one_sided_columns += one_sided_new
        unresolved_total += unresolved_columns
        gradient = matrix.T @ current.residual
        record(iteration, accepted_step, used_damping)
        if current.loss <= config.loss_tolerance:
            converged, stop_reason = True, "loss_tolerance"
        elif loss_change_stopping and previous_loss - current.loss <= config.loss_tolerance:
            converged, stop_reason = unresolved_columns == 0, (
                "loss_change_tolerance" if unresolved_columns == 0 else "infeasible_jacobian"
            )
        elif np.linalg.norm(gradient, ord=np.inf) <= config.gradient_tolerance:
            converged, stop_reason = gradient_stop()
        elif float(np.linalg.norm(accepted_step)) / max(
            np.linalg.norm(accepted_state.parameter_vector()), 1.0
        ) <= config.relative_step_tolerance:
            converged, stop_reason = unresolved_columns == 0, (
                "relative_step_tolerance" if unresolved_columns == 0 else "infeasible_jacobian"
            )

    return MultiRadialFDResult(
        iterations=tuple(records),
        final_state=accepted_state,
        converged=converged,
        stop_reason=stop_reason,
        evaluation_count=evaluation_count,
        infeasible_trial_count=infeasible_count,
        total_seconds=float(perf_counter() - started),
        feasibility_rejected_trial_count=feasibility_rejected,
        one_sided_jacobian_column_count=one_sided_columns,
        unresolved_jacobian_column_count=unresolved_total,
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
    "multiradial_geometry_admissible",
    "run_multiradial_fd_inverse",
]
