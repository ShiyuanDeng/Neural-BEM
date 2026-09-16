"""Geometry, implicit-field, topology, and Kress-readiness diagnostics.

The functions in this module evaluate an already constructed continuous
``PeriodicParameterization2D``.  They do not extract a contour, alter a fit,
or couple the result to any active solver.  Dense pointwise measurements and
the lower-resolution sampled topology checks intentionally have independent
resolutions: the latter are quadratic in the number of probe segments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import operator
from typing import Any, Sequence

import numpy as np
from scipy.spatial import cKDTree

from ordered_boundary import PeriodicParameterization2D

from .fields import ImplicitField2D


Array = np.ndarray
_TWO_PI = 2.0 * np.pi


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


def _validated_even_sample_counts(
    values: Sequence[int],
    *,
    name: str,
) -> tuple[int, ...]:
    """Return a non-empty, duplicate-free sequence of even node counts."""

    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of even integers.")
    try:
        raw_counts = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a sequence of even integers.") from exc
    if not raw_counts:
        raise ValueError(f"{name} must contain at least one node count.")
    counts = tuple(
        _positive_integer(value, name=f"{name}[{index}]", minimum=4)
        for index, value in enumerate(raw_counts)
    )
    odd = tuple(value for value in counts if value % 2)
    if odd:
        raise ValueError(f"Every {name} value must be even; received {odd}.")
    if len(set(counts)) != len(counts):
        raise ValueError(f"{name} must not contain duplicates.")
    return counts


@dataclass(frozen=True)
class BoundaryMetricConfig:
    """Resolutions and tolerances used by :func:`compute_boundary_metrics`."""

    dense_resolution: int = 2048
    reference_resolution: int = 8192
    topology_resolution: int = 512
    fft_resolution: int = 2048
    fft_tail_start_mode: int = 16
    kress_resolution: int = 256
    kress_sample_counts: tuple[int, ...] = (64, 128, 256)
    kress_offsets: tuple[float, ...] = (
        _TWO_PI / 32.0,
        _TWO_PI / 64.0,
        _TWO_PI / 128.0,
        _TWO_PI / 256.0,
    )
    gradient_epsilon: float = 1.0e-14
    intersection_relative_tolerance: float = 1.0e-12
    nonlocal_exclusion_fraction: float = 0.02
    center_fft_coordinates: bool = True

    def __post_init__(self) -> None:
        for name, minimum in (
            ("dense_resolution", 16),
            ("reference_resolution", 16),
            ("topology_resolution", 16),
            ("fft_resolution", 16),
            ("kress_resolution", 8),
        ):
            object.__setattr__(
                self,
                name,
                _positive_integer(getattr(self, name), name=name, minimum=minimum),
            )
        if self.fft_resolution % 2:
            raise ValueError("fft_resolution must be even.")
        tail_start = _positive_integer(
            self.fft_tail_start_mode,
            name="fft_tail_start_mode",
            minimum=1,
        )
        if tail_start > self.fft_resolution // 2:
            raise ValueError("fft_tail_start_mode cannot exceed the FFT Nyquist mode.")
        object.__setattr__(self, "fft_tail_start_mode", tail_start)
        sample_counts = _validated_even_sample_counts(
            self.kress_sample_counts,
            name="kress_sample_counts",
        )
        object.__setattr__(self, "kress_sample_counts", sample_counts)
        for name in ("gradient_epsilon", "intersection_relative_tolerance"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive.")
            object.__setattr__(self, name, value)
        exclusion = float(self.nonlocal_exclusion_fraction)
        if not np.isfinite(exclusion) or not 0.0 < exclusion < 0.5:
            raise ValueError("nonlocal_exclusion_fraction must lie strictly between 0 and 0.5.")
        object.__setattr__(self, "nonlocal_exclusion_fraction", exclusion)
        if not isinstance(self.center_fft_coordinates, (bool, np.bool_)):
            raise TypeError("center_fft_coordinates must be boolean.")
        object.__setattr__(self, "center_fft_coordinates", bool(self.center_fft_coordinates))
        offsets = tuple(float(value) for value in self.kress_offsets)
        if not offsets:
            raise ValueError("kress_offsets must contain at least one offset.")
        if any(not np.isfinite(value) or value <= 0.0 or value >= np.pi for value in offsets):
            raise ValueError("Every Kress offset must be finite and lie in (0, pi).")
        object.__setattr__(self, "kress_offsets", offsets)


@dataclass(frozen=True)
class CurveSampleData:
    """Dense uniform samples used by metrics and plotting."""

    parameters: Array
    points: Array
    first_derivatives: Array
    second_derivatives: Array
    speeds: Array
    tangents: Array
    outward_normals: Array
    curvatures: Array


@dataclass(frozen=True)
class SDFResidualMetrics:
    maximum_absolute: float
    rms: float
    normalized_maximum: float
    normalized_rms: float
    minimum_gradient_norm: float
    maximum_gradient_norm: float


@dataclass(frozen=True)
class IntegralGeometryMetrics:
    signed_area: float
    perimeter: float
    reference_signed_area: float | None
    reference_perimeter: float | None
    absolute_area_error: float | None
    relative_area_error: float | None
    absolute_perimeter_error: float | None
    relative_perimeter_error: float | None


@dataclass(frozen=True)
class ReferenceSetMetrics:
    candidate_to_reference_maximum: float
    candidate_to_reference_rms: float
    reference_to_candidate_maximum: float
    reference_to_candidate_rms: float
    symmetric_hausdorff: float
    symmetric_rms: float
    symmetric_chamfer_mean: float
    normal_angle_maximum_radians: float | None
    normal_angle_rms_radians: float | None
    curvature_absolute_maximum: float | None
    curvature_absolute_rms: float | None


@dataclass(frozen=True)
class SeamMetrics:
    position_error: float
    first_derivative_error: float
    second_derivative_error: float


@dataclass(frozen=True)
class SpeedMetrics:
    minimum: float
    maximum: float
    mean: float
    ratio: float | None
    minimum_over_mean: float | None
    coefficient_of_variation: float | None


@dataclass(frozen=True)
class WindingMetric:
    point: tuple[float, float]
    winding_number: float


@dataclass(frozen=True)
class TopologyMetrics:
    sampled_self_intersection_count: int
    minimum_nonlocal_distance: float | None
    nonlocal_exclusion_nodes: int
    winding: tuple[WindingMetric, ...]


@dataclass(frozen=True)
class SpectralTailMetrics:
    fft_resolution: int
    tail_start_mode: int
    coordinates_centered: bool
    order_0: float | None
    order_1: float | None
    order_2: float | None


@dataclass(frozen=True)
class KressDiagonalError:
    offset: float
    maximum_absolute: float | None
    rms: float | None


@dataclass(frozen=True)
class FrozenCurveSamplingMetrics:
    """Kress-node readiness diagnostics for one frozen continuous curve.

    Each record comes from a fresh uniform discretization of the same
    :class:`PeriodicParameterization2D`; no spline/Fourier refit occurs while
    changing ``num_nodes``.  ``dense_reference_perimeter`` is the common dense
    periodic-trapezoid perimeter already used by the surrounding metric record.
    """

    num_nodes: int
    parameter_step: float
    maximum_parameter_grid_error: float
    includes_repeated_endpoint: bool
    all_finite: bool
    positive_speed: bool
    counterclockwise: bool
    minimum_speed: float
    maximum_speed: float
    speed_ratio: float
    minimum_log_speed: float
    maximum_log_speed: float
    minimum_ds_weight: float
    maximum_ds_weight: float
    ds_weight_perimeter: float
    dense_reference_perimeter: float
    perimeter_absolute_error: float
    perimeter_relative_error: float
    signed_area: float


@dataclass(frozen=True)
class BoundaryMetrics:
    """Complete metric record for one continuous fitted component."""

    component_id: str
    dense_resolution: int
    sdf_residual: SDFResidualMetrics | None
    integral_geometry: IntegralGeometryMetrics
    reference_set: ReferenceSetMetrics | None
    seam: SeamMetrics
    speed: SpeedMetrics
    topology: TopologyMetrics
    spectral_tail: SpectralTailMetrics
    frozen_curve_sampling: tuple[FrozenCurveSamplingMetrics, ...]
    kress_diagonal: tuple[KressDiagonalError, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sample_parameterization(
    curve: PeriodicParameterization2D,
    resolution: int,
) -> CurveSampleData:
    """Sample positions and curve-derived differential geometry uniformly."""

    if not isinstance(curve, PeriodicParameterization2D):
        raise TypeError("curve must be a PeriodicParameterization2D.")
    count = _positive_integer(resolution, name="resolution", minimum=3)
    parameters = curve.parameter_origin + curve.period * np.arange(count, dtype=np.float64) / count
    evaluation = curve.evaluate(parameters, wrap=False)
    speeds = np.linalg.norm(evaluation.first_derivatives, axis=1)
    tangents = np.full_like(evaluation.first_derivatives, np.nan)
    regular = speeds > 0.0
    np.divide(
        evaluation.first_derivatives,
        speeds[:, None],
        out=tangents,
        where=regular[:, None],
    )
    normals = np.column_stack((tangents[:, 1], -tangents[:, 0]))
    cross = (
        evaluation.first_derivatives[:, 0] * evaluation.second_derivatives[:, 1]
        - evaluation.first_derivatives[:, 1] * evaluation.second_derivatives[:, 0]
    )
    curvatures = np.full(count, np.nan, dtype=np.float64)
    np.divide(cross, speeds**3, out=curvatures, where=regular)
    return CurveSampleData(
        parameters=parameters,
        points=evaluation.points,
        first_derivatives=evaluation.first_derivatives,
        second_derivatives=evaluation.second_derivatives,
        speeds=speeds,
        tangents=tangents,
        outward_normals=normals,
        curvatures=curvatures,
    )


def evaluate_field_values(field: ImplicitField2D, points: Array) -> Array:
    """Evaluate and shape-check one implicit field on ``(N, 2)`` points."""

    values = np.asarray(field.value(points), dtype=np.float64)
    if values.shape == (points.shape[0], 1):
        values = values[:, 0]
    if values.shape != (points.shape[0],):
        raise ValueError("field.value(points) must return shape (N,) or (N, 1).")
    if not np.all(np.isfinite(values)):
        raise ValueError("field.value(points) returned nonfinite values.")
    return values


def evaluate_field_gradients(field: ImplicitField2D, points: Array) -> Array:
    """Evaluate and shape-check field gradients on ``(N, 2)`` points."""

    gradients = np.asarray(field.gradient(points), dtype=np.float64)
    if gradients.shape != points.shape:
        raise ValueError("field.gradient(points) must return shape (N, 2).")
    if not np.all(np.isfinite(gradients)):
        raise ValueError("field.gradient(points) returned nonfinite values.")
    return gradients


def sdf_residual_metrics(
    field: ImplicitField2D,
    points: Array,
    *,
    gradient_epsilon: float = 1.0e-14,
) -> SDFResidualMetrics:
    values = evaluate_field_values(field, points)
    gradients = evaluate_field_gradients(field, points)
    gradient_norms = np.linalg.norm(gradients, axis=1)
    absolute = np.abs(values)
    normalized = absolute / (gradient_norms + float(gradient_epsilon))
    return SDFResidualMetrics(
        maximum_absolute=float(np.max(absolute)),
        rms=float(np.sqrt(np.mean(values**2))),
        normalized_maximum=float(np.max(normalized)),
        normalized_rms=float(np.sqrt(np.mean(normalized**2))),
        minimum_gradient_norm=float(np.min(gradient_norms)),
        maximum_gradient_norm=float(np.max(gradient_norms)),
    )


def _integral_geometry(samples: CurveSampleData, period: float) -> tuple[float, float]:
    step = float(period) / samples.parameters.size
    cross = (
        samples.points[:, 0] * samples.first_derivatives[:, 1]
        - samples.points[:, 1] * samples.first_derivatives[:, 0]
    )
    return 0.5 * step * float(np.sum(cross)), step * float(np.sum(samples.speeds))


def _optional_error(value: float, reference: float) -> tuple[float, float | None]:
    absolute = abs(float(value) - float(reference))
    relative = absolute / abs(reference) if reference != 0.0 else None
    return absolute, relative


def integral_geometry_metrics(
    candidate: CurveSampleData,
    candidate_period: float,
    reference: CurveSampleData | None = None,
    reference_period: float | None = None,
) -> IntegralGeometryMetrics:
    area, perimeter = _integral_geometry(candidate, candidate_period)
    if reference is None:
        return IntegralGeometryMetrics(area, perimeter, None, None, None, None, None, None)
    if reference_period is None:
        raise ValueError("reference_period is required when reference samples are supplied.")
    reference_area, reference_perimeter = _integral_geometry(reference, reference_period)
    area_absolute, area_relative = _optional_error(area, reference_area)
    perimeter_absolute, perimeter_relative = _optional_error(perimeter, reference_perimeter)
    return IntegralGeometryMetrics(
        signed_area=area,
        perimeter=perimeter,
        reference_signed_area=reference_area,
        reference_perimeter=reference_perimeter,
        absolute_area_error=area_absolute,
        relative_area_error=area_relative,
        absolute_perimeter_error=perimeter_absolute,
        relative_perimeter_error=perimeter_relative,
    )


def reference_set_metrics(
    candidate: CurveSampleData,
    reference: CurveSampleData,
) -> ReferenceSetMetrics:
    """Compare sampled geometric sets without assuming phase correspondence."""

    reference_tree = cKDTree(reference.points)
    candidate_to_reference, nearest_reference = reference_tree.query(candidate.points, k=1)
    candidate_tree = cKDTree(candidate.points)
    reference_to_candidate, _ = candidate_tree.query(reference.points, k=1)
    first_mean_square = float(np.mean(candidate_to_reference**2))
    second_mean_square = float(np.mean(reference_to_candidate**2))

    matched_normals = reference.outward_normals[np.asarray(nearest_reference, dtype=np.int64)]
    normal_dot = np.sum(candidate.outward_normals * matched_normals, axis=1)
    finite_normal = np.isfinite(normal_dot)
    normal_maximum: float | None = None
    normal_rms: float | None = None
    if np.any(finite_normal):
        angles = np.arccos(np.clip(normal_dot[finite_normal], -1.0, 1.0))
        normal_maximum = float(np.max(angles))
        normal_rms = float(np.sqrt(np.mean(angles**2)))

    matched_curvatures = reference.curvatures[np.asarray(nearest_reference, dtype=np.int64)]
    curvature_difference = np.abs(candidate.curvatures - matched_curvatures)
    finite_curvature = np.isfinite(curvature_difference)
    curvature_maximum: float | None = None
    curvature_rms: float | None = None
    if np.any(finite_curvature):
        curvature_maximum = float(np.max(curvature_difference[finite_curvature]))
        curvature_rms = float(
            np.sqrt(np.mean(curvature_difference[finite_curvature] ** 2))
        )

    return ReferenceSetMetrics(
        candidate_to_reference_maximum=float(np.max(candidate_to_reference)),
        candidate_to_reference_rms=float(np.sqrt(first_mean_square)),
        reference_to_candidate_maximum=float(np.max(reference_to_candidate)),
        reference_to_candidate_rms=float(np.sqrt(second_mean_square)),
        symmetric_hausdorff=float(
            max(np.max(candidate_to_reference), np.max(reference_to_candidate))
        ),
        symmetric_rms=float(np.sqrt(0.5 * (first_mean_square + second_mean_square))),
        symmetric_chamfer_mean=float(
            0.5 * (np.mean(candidate_to_reference) + np.mean(reference_to_candidate))
        ),
        normal_angle_maximum_radians=normal_maximum,
        normal_angle_rms_radians=normal_rms,
        curvature_absolute_maximum=curvature_maximum,
        curvature_absolute_rms=curvature_rms,
    )


def seam_metrics(curve: PeriodicParameterization2D) -> SeamMetrics:
    parameters = np.asarray(
        [curve.parameter_origin, curve.parameter_origin + curve.period],
        dtype=np.float64,
    )
    evaluation = curve.evaluate(parameters, wrap=False)
    return SeamMetrics(
        position_error=float(np.linalg.norm(evaluation.points[1] - evaluation.points[0])),
        first_derivative_error=float(
            np.linalg.norm(evaluation.first_derivatives[1] - evaluation.first_derivatives[0])
        ),
        second_derivative_error=float(
            np.linalg.norm(evaluation.second_derivatives[1] - evaluation.second_derivatives[0])
        ),
    )


def speed_metrics(speeds: Array) -> SpeedMetrics:
    values = np.asarray(speeds, dtype=np.float64)
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    mean = float(np.mean(values))
    ratio = maximum / minimum if minimum > 0.0 else None
    minimum_over_mean = minimum / mean if mean > 0.0 else None
    coefficient_of_variation = float(np.std(values) / mean) if mean > 0.0 else None
    return SpeedMetrics(
        minimum=minimum,
        maximum=maximum,
        mean=mean,
        ratio=ratio,
        minimum_over_mean=minimum_over_mean,
        coefficient_of_variation=coefficient_of_variation,
    )


def _cross2d(first: Array, second: Array) -> Array:
    return first[..., 0] * second[..., 1] - first[..., 1] * second[..., 0]


def _points_on_segments(
    points: Array,
    starts: Array,
    ends: Array,
    length_tolerance: float,
) -> Array:
    lower = np.minimum(starts, ends) - length_tolerance
    upper = np.maximum(starts, ends) + length_tolerance
    return np.all((points >= lower) & (points <= upper), axis=-1)


def _segment_intersections(
    first_start: Array,
    first_end: Array,
    second_start: Array,
    second_end: Array,
    *,
    cross_tolerance: float,
    length_tolerance: float,
) -> Array:
    first_delta = first_end - first_start
    second_delta = second_end - second_start
    o1 = _cross2d(first_delta, second_start - first_start)
    o2 = _cross2d(first_delta, second_end - first_start)
    o3 = _cross2d(second_delta, first_start - second_start)
    o4 = _cross2d(second_delta, first_end - second_start)
    proper = (
        (((o1 > cross_tolerance) & (o2 < -cross_tolerance))
         | ((o1 < -cross_tolerance) & (o2 > cross_tolerance)))
        & (((o3 > cross_tolerance) & (o4 < -cross_tolerance))
           | ((o3 < -cross_tolerance) & (o4 > cross_tolerance)))
    )
    touching = (
        ((np.abs(o1) <= cross_tolerance)
         & _points_on_segments(second_start, first_start, first_end, length_tolerance))
        | ((np.abs(o2) <= cross_tolerance)
           & _points_on_segments(second_end, first_start, first_end, length_tolerance))
        | ((np.abs(o3) <= cross_tolerance)
           & _points_on_segments(first_start, second_start, second_end, length_tolerance))
        | ((np.abs(o4) <= cross_tolerance)
           & _points_on_segments(first_end, second_start, second_end, length_tolerance))
    )
    return proper | touching


def _point_to_segments_distance(point: Array, starts: Array, ends: Array) -> Array:
    delta = ends - starts
    denominator = np.sum(delta * delta, axis=1)
    displacement = point - starts
    fraction = np.zeros(starts.shape[0], dtype=np.float64)
    np.divide(
        np.sum(displacement * delta, axis=1),
        denominator,
        out=fraction,
        where=denominator > 0.0,
    )
    fraction = np.clip(fraction, 0.0, 1.0)
    closest = starts + fraction[:, None] * delta
    return np.linalg.norm(point - closest, axis=1)


def _points_to_segment_distance(points: Array, start: Array, end: Array) -> Array:
    delta = end - start
    denominator = float(np.dot(delta, delta))
    if denominator <= 0.0:
        return np.linalg.norm(points - start, axis=1)
    fraction = np.sum((points - start) * delta, axis=1) / denominator
    fraction = np.clip(fraction, 0.0, 1.0)
    closest = start + fraction[:, None] * delta
    return np.linalg.norm(points - closest, axis=1)


def sampled_topology_metrics(
    points: Array,
    *,
    intersection_relative_tolerance: float = 1.0e-12,
    nonlocal_exclusion_fraction: float = 0.02,
    winding_test_points: Sequence[Sequence[float]] | Array | None = None,
) -> TopologyMetrics:
    """Count sampled segment crossings and estimate nonlocal clearance."""

    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] < 4:
        raise ValueError("points must have shape (N, 2) with N at least 4.")
    count = values.shape[0]
    span = np.max(values, axis=0) - np.min(values, axis=0)
    scale = max(float(np.linalg.norm(span)), np.finfo(np.float64).tiny)
    length_tolerance = float(intersection_relative_tolerance) * scale
    cross_tolerance = float(intersection_relative_tolerance) * scale**2
    exclusion = max(1, int(math.ceil(count * float(nonlocal_exclusion_fraction))))
    if exclusion >= count // 2:
        raise ValueError("The nonlocal exclusion leaves no nonlocal segment pairs.")

    ends = np.roll(values, -1, axis=0)
    intersections = 0
    minimum_distance = float("inf")
    found_nonlocal_pair = False
    for first_index in range(count):
        candidate_indices = np.arange(first_index + 1, count, dtype=np.int64)
        if candidate_indices.size == 0:
            continue
        separation = candidate_indices - first_index
        cyclic_separation = np.minimum(separation, count - separation)

        nonadjacent = cyclic_separation > 1
        if np.any(nonadjacent):
            indices = candidate_indices[nonadjacent]
            hit = _segment_intersections(
                np.broadcast_to(values[first_index], (indices.size, 2)),
                np.broadcast_to(ends[first_index], (indices.size, 2)),
                values[indices],
                ends[indices],
                cross_tolerance=cross_tolerance,
                length_tolerance=length_tolerance,
            )
            intersections += int(np.count_nonzero(hit))

        nonlocal_mask = cyclic_separation > exclusion
        if not np.any(nonlocal_mask):
            continue
        found_nonlocal_pair = True
        indices = candidate_indices[nonlocal_mask]
        first_start = values[first_index]
        first_end = ends[first_index]
        second_start = values[indices]
        second_end = ends[indices]
        hit = _segment_intersections(
            np.broadcast_to(first_start, (indices.size, 2)),
            np.broadcast_to(first_end, (indices.size, 2)),
            second_start,
            second_end,
            cross_tolerance=cross_tolerance,
            length_tolerance=length_tolerance,
        )
        pair_distance = np.minimum.reduce(
            (
                _point_to_segments_distance(first_start, second_start, second_end),
                _point_to_segments_distance(first_end, second_start, second_end),
                _points_to_segment_distance(second_start, first_start, first_end),
                _points_to_segment_distance(second_end, first_start, first_end),
            )
        )
        pair_distance[hit] = 0.0
        minimum_distance = min(minimum_distance, float(np.min(pair_distance)))

    if winding_test_points is None:
        test_points = np.mean(values, axis=0, keepdims=True)
    else:
        test_points = np.asarray(winding_test_points, dtype=np.float64)
        if test_points.ndim == 1:
            test_points = test_points[None, :]
        if test_points.ndim != 2 or test_points.shape[1] != 2:
            raise ValueError("winding_test_points must have shape (P, 2).")
        if not np.all(np.isfinite(test_points)):
            raise ValueError("winding_test_points must be finite.")
    winding = tuple(
        WindingMetric(
            point=(float(point[0]), float(point[1])),
            winding_number=winding_number(values, point),
        )
        for point in test_points
    )
    return TopologyMetrics(
        sampled_self_intersection_count=intersections,
        minimum_nonlocal_distance=minimum_distance if found_nonlocal_pair else None,
        nonlocal_exclusion_nodes=exclusion,
        winding=winding,
    )


def winding_number(points: Array, point: Sequence[float] | Array) -> float:
    """Return the sampled polygon winding number around one physical point."""

    polygon = np.asarray(points, dtype=np.float64)
    target = np.asarray(point, dtype=np.float64)
    if target.shape != (2,):
        raise ValueError("point must contain two coordinates.")
    relative = polygon - target
    if np.any(np.linalg.norm(relative, axis=1) <= np.finfo(np.float64).eps):
        raise ValueError("The winding test point lies on a sampled contour vertex.")
    following = np.roll(relative, -1, axis=0)
    angle = np.arctan2(_cross2d(relative, following), np.sum(relative * following, axis=1))
    return float(np.sum(angle) / _TWO_PI)


def spectral_tail_metrics(
    points: Array,
    *,
    tail_start_mode: int,
    center_coordinates: bool = True,
) -> SpectralTailMetrics:
    """Compute common coordinate FFT tails weighted through derivative order two."""

    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("points must have shape (N, 2).")
    if values.shape[0] % 2:
        raise ValueError("FFT samples must have even length.")
    start = _positive_integer(tail_start_mode, name="tail_start_mode", minimum=1)
    if start > values.shape[0] // 2:
        raise ValueError("tail_start_mode cannot exceed the Nyquist mode.")
    transformed_values = values - np.mean(values, axis=0) if center_coordinates else values
    coefficients = np.fft.fft(transformed_values, axis=0) / values.shape[0]
    power = np.sum(np.abs(coefficients) ** 2, axis=1)
    modes = np.abs(np.fft.fftfreq(values.shape[0], d=1.0 / values.shape[0]))
    tail = modes >= start
    results: list[float | None] = []
    for order in range(3):
        weights = modes ** (2 * order)
        weighted_power = weights * power
        denominator = float(np.sum(weighted_power))
        results.append(float(np.sum(weighted_power[tail]) / denominator) if denominator > 0.0 else None)
    return SpectralTailMetrics(
        fft_resolution=values.shape[0],
        tail_start_mode=start,
        coordinates_centered=bool(center_coordinates),
        order_0=results[0],
        order_1=results[1],
        order_2=results[2],
    )


def coordinate_spectrum(points: Array, *, center_coordinates: bool = True) -> tuple[Array, Array]:
    """Return nonnegative integer modes and combined x/y coordinate amplitudes."""

    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("points must have shape (N, 2).")
    transformed_values = values - np.mean(values, axis=0) if center_coordinates else values
    coefficients = np.fft.rfft(transformed_values, axis=0) / values.shape[0]
    amplitudes = np.linalg.norm(coefficients, axis=1)
    if amplitudes.size > 2:
        amplitudes[1:-1] *= 2.0
    return np.arange(amplitudes.size, dtype=np.int64), amplitudes


def kress_diagonal_metrics(
    curve: PeriodicParameterization2D,
    *,
    resolution: int,
    offsets: Sequence[float],
) -> tuple[KressDiagonalError, ...]:
    """Measure convergence to the removable Kress diagonal ``log|gamma'|``."""

    if not np.isclose(curve.period, _TWO_PI, rtol=0.0, atol=1.0e-13):
        raise ValueError("Kress diagonal metrics require a 2*pi-periodic parameterization.")
    samples = sample_parameterization(curve, resolution)
    finite_speed = samples.speeds > 0.0
    log_speed = np.full_like(samples.speeds, np.nan)
    log_speed[finite_speed] = np.log(samples.speeds[finite_speed])
    errors = []
    for offset_value in offsets:
        offset = float(offset_value)
        denominator = 2.0 * abs(np.sin(0.5 * offset))
        plus = curve.evaluate(samples.parameters + offset, wrap=True).points
        minus = curve.evaluate(samples.parameters - offset, wrap=True).points
        plus_distance = np.linalg.norm(plus - samples.points, axis=1)
        minus_distance = np.linalg.norm(minus - samples.points, axis=1)
        valid = finite_speed & (plus_distance > 0.0) & (minus_distance > 0.0)
        if not np.any(valid):
            errors.append(KressDiagonalError(offset, None, None))
            continue
        plus_remainder = np.log(plus_distance[valid] / denominator)
        minus_remainder = np.log(minus_distance[valid] / denominator)
        difference = 0.5 * (plus_remainder + minus_remainder) - log_speed[valid]
        errors.append(
            KressDiagonalError(
                offset=offset,
                maximum_absolute=float(np.max(np.abs(difference))),
                rms=float(np.sqrt(np.mean(difference**2))),
            )
        )
    return tuple(errors)


def frozen_curve_sampling_metrics(
    curve: PeriodicParameterization2D,
    *,
    sample_counts: Sequence[int],
    dense_reference_perimeter: float,
) -> tuple[FrozenCurveSamplingMetrics, ...]:
    """Sample one unchanged curve at several even node counts.

    The returned perimeter is ``sum(dt * |gamma'|)`` from the immutable
    :class:`~ordered_boundary.PeriodicCurve2D` at each requested count.  Its
    error is measured against a dense periodic-trapezoid perimeter of this same
    continuous curve, not against a separately fitted or analytic reference
    boundary.
    """

    if not isinstance(curve, PeriodicParameterization2D):
        raise TypeError("curve must be a PeriodicParameterization2D.")
    counts = _validated_even_sample_counts(sample_counts, name="sample_counts")
    reference_perimeter = float(dense_reference_perimeter)
    if not np.isfinite(reference_perimeter) or reference_perimeter <= 0.0:
        raise ValueError("dense_reference_perimeter must be finite and positive.")

    records = []
    for count in counts:
        nodes = curve.discretize(count, require_even=True)
        expected_parameters = (
            curve.parameter_origin
            + curve.period * np.arange(count, dtype=np.float64) / count
        )
        parameter_error = float(
            np.max(np.abs(nodes.parameters - expected_parameters))
        )
        endpoint = curve.parameter_origin + curve.period
        endpoint_tolerance = (
            32.0
            * np.finfo(np.float64).eps
            * max(abs(curve.parameter_origin), curve.period, 1.0)
        )
        includes_endpoint = bool(
            np.any(np.abs(nodes.parameters - endpoint) <= endpoint_tolerance)
        )
        speeds = nodes.speeds
        log_speeds = np.log(speeds)
        ds_weights = nodes.arc_length_weights
        perimeter = float(np.sum(ds_weights))
        absolute_error = abs(perimeter - reference_perimeter)
        finite_arrays = (
            nodes.parameters,
            nodes.points,
            nodes.first_derivatives,
            nodes.second_derivatives,
            nodes.speeds,
            nodes.tangents,
            nodes.normals,
            nodes.curvatures,
            nodes.arc_length_weights,
            log_speeds,
        )
        if nodes.third_derivatives is not None:
            finite_arrays += (nodes.third_derivatives,)
        records.append(
            FrozenCurveSamplingMetrics(
                num_nodes=count,
                parameter_step=float(nodes.parameter_step),
                maximum_parameter_grid_error=parameter_error,
                includes_repeated_endpoint=includes_endpoint,
                all_finite=all(np.all(np.isfinite(values)) for values in finite_arrays),
                positive_speed=bool(np.all(speeds > 0.0)),
                counterclockwise=nodes.orientation == "counterclockwise",
                minimum_speed=float(np.min(speeds)),
                maximum_speed=float(np.max(speeds)),
                speed_ratio=float(np.max(speeds) / np.min(speeds)),
                minimum_log_speed=float(np.min(log_speeds)),
                maximum_log_speed=float(np.max(log_speeds)),
                minimum_ds_weight=float(np.min(ds_weights)),
                maximum_ds_weight=float(np.max(ds_weights)),
                ds_weight_perimeter=perimeter,
                dense_reference_perimeter=reference_perimeter,
                perimeter_absolute_error=absolute_error,
                perimeter_relative_error=absolute_error / reference_perimeter,
                signed_area=float(nodes.signed_area),
            )
        )
    return tuple(records)


def compute_boundary_metrics(
    curve: PeriodicParameterization2D,
    *,
    field: ImplicitField2D | None = None,
    reference: PeriodicParameterization2D | None = None,
    config: BoundaryMetricConfig | None = None,
    winding_test_points: Sequence[Sequence[float]] | Array | None = None,
) -> BoundaryMetrics:
    """Compute all configured metrics for one continuous component."""

    if not isinstance(curve, PeriodicParameterization2D):
        raise TypeError("curve must be a PeriodicParameterization2D.")
    if reference is not None and not isinstance(reference, PeriodicParameterization2D):
        raise TypeError("reference must be a PeriodicParameterization2D when supplied.")
    settings = BoundaryMetricConfig() if config is None else config
    if not isinstance(settings, BoundaryMetricConfig):
        raise TypeError("config must be a BoundaryMetricConfig.")

    dense = sample_parameterization(curve, settings.dense_resolution)
    reference_dense = (
        sample_parameterization(reference, settings.reference_resolution)
        if reference is not None
        else None
    )
    # Reference-set discrepancy has its own configured resolution.  Reusing
    # the usually coarser field-metric samples would impose an artificial
    # O(perimeter / dense_resolution) Hausdorff floor even for an exact curve.
    candidate_reference_dense = (
        sample_parameterization(curve, settings.reference_resolution)
        if reference is not None
        else None
    )
    sdf = (
        sdf_residual_metrics(
            field,
            dense.points,
            gradient_epsilon=settings.gradient_epsilon,
        )
        if field is not None
        else None
    )
    integral = integral_geometry_metrics(
        dense,
        curve.period,
        reference_dense,
        reference.period if reference is not None else None,
    )
    reference_comparison = (
        reference_set_metrics(candidate_reference_dense, reference_dense)
        if reference_dense is not None and candidate_reference_dense is not None
        else None
    )
    topology_samples = sample_parameterization(curve, settings.topology_resolution)
    topology = sampled_topology_metrics(
        topology_samples.points,
        intersection_relative_tolerance=settings.intersection_relative_tolerance,
        nonlocal_exclusion_fraction=settings.nonlocal_exclusion_fraction,
        winding_test_points=winding_test_points,
    )
    fft_samples = sample_parameterization(curve, settings.fft_resolution)
    spectral = spectral_tail_metrics(
        fft_samples.points,
        tail_start_mode=settings.fft_tail_start_mode,
        center_coordinates=settings.center_fft_coordinates,
    )
    return BoundaryMetrics(
        component_id=curve.component_id,
        dense_resolution=settings.dense_resolution,
        sdf_residual=sdf,
        integral_geometry=integral,
        reference_set=reference_comparison,
        seam=seam_metrics(curve),
        speed=speed_metrics(dense.speeds),
        topology=topology,
        spectral_tail=spectral,
        frozen_curve_sampling=frozen_curve_sampling_metrics(
            curve,
            sample_counts=settings.kress_sample_counts,
            dense_reference_perimeter=integral.perimeter,
        ),
        kress_diagonal=kress_diagonal_metrics(
            curve,
            resolution=settings.kress_resolution,
            offsets=settings.kress_offsets,
        ),
    )


__all__ = [
    "BoundaryMetricConfig",
    "BoundaryMetrics",
    "CurveSampleData",
    "FrozenCurveSamplingMetrics",
    "IntegralGeometryMetrics",
    "KressDiagonalError",
    "ReferenceSetMetrics",
    "SDFResidualMetrics",
    "SeamMetrics",
    "SpectralTailMetrics",
    "SpeedMetrics",
    "TopologyMetrics",
    "WindingMetric",
    "compute_boundary_metrics",
    "coordinate_spectrum",
    "evaluate_field_gradients",
    "evaluate_field_values",
    "frozen_curve_sampling_metrics",
    "integral_geometry_metrics",
    "kress_diagonal_metrics",
    "reference_set_metrics",
    "sample_parameterization",
    "sampled_topology_metrics",
    "sdf_residual_metrics",
    "seam_metrics",
    "spectral_tail_metrics",
    "speed_metrics",
    "winding_number",
]
