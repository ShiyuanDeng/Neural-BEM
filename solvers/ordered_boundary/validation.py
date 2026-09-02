"""Scale-aware diagnostics for continuous parameterizations and topology."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import operator

import numpy as np

from ._array_utils import cross2d
from .boundary_parameterization import OrderedBoundaryParameterization2D
from .parameterization import PeriodicParameterization2D


@dataclass(frozen=True)
class BoundaryValidationConfig:
    """Resolution and scale-relative tolerances for geometry diagnostics."""

    num_samples_per_component: int = 512
    closure_relative_tolerance: float = 1.0e-10
    closure_absolute_tolerance: float = 1.0e-12
    minimum_speed_relative: float = 1.0e-10
    minimum_area_relative: float = 1.0e-12
    derivative_relative_tolerance: float = 1.0e-4
    intersection_relative_tolerance: float = 1.0e-12
    minimum_intercomponent_clearance: float = 0.0
    require_counterclockwise: bool = True
    allow_nested_components: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.num_samples_per_component, bool):
            raise TypeError("num_samples_per_component must be an integer, not bool.")
        try:
            sample_count = operator.index(self.num_samples_per_component)
        except TypeError as exc:
            raise TypeError("num_samples_per_component must be an integer.") from exc
        if sample_count < 16:
            raise ValueError("num_samples_per_component must be at least 16.")
        object.__setattr__(self, "num_samples_per_component", sample_count)
        for name in (
            "closure_relative_tolerance",
            "closure_absolute_tolerance",
            "minimum_speed_relative",
            "minimum_area_relative",
            "derivative_relative_tolerance",
            "intersection_relative_tolerance",
            "minimum_intercomponent_clearance",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)
        for name in ("require_counterclockwise", "allow_nested_components"):
            value = getattr(self, name)
            if not isinstance(value, (bool, np.bool_)):
                raise TypeError(f"{name} must be boolean.")
            object.__setattr__(self, name, bool(value))


@dataclass(frozen=True)
class CurveGeometryReport:
    component_id: str
    name: str
    valid: bool
    issues: tuple[str, ...]
    num_validation_nodes: int
    orientation: str
    phase_anchor: tuple[float, float]
    parameter_origin: float
    maximum_derivative_order: int
    source_kind: str
    source_identifier: str | None
    projection_residual: float | None
    fit_residual: float | None
    signed_area: float
    perimeter: float
    minimum_speed: float
    maximum_speed: float
    minimum_curvature: float | None
    maximum_curvature: float | None
    position_closure_error: float
    first_derivative_closure_error: float
    second_derivative_closure_error: float
    third_derivative_closure_error: float | None
    first_derivative_consistency_error: float
    second_derivative_consistency_error: float
    third_derivative_consistency_error: float | None
    self_intersection_count: int
    bounding_box_min: tuple[float, float]
    bounding_box_max: tuple[float, float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OrderedBoundaryReport:
    valid: bool
    issues: tuple[str, ...]
    components: tuple[CurveGeometryReport, ...]
    minimum_intercomponent_clearance: float | None
    intersecting_component_pairs: tuple[tuple[str, str], ...]
    nested_component_pairs: tuple[tuple[str, str], ...]

    @property
    def num_components(self) -> int:
        return len(self.components)

    @property
    def total_perimeter(self) -> float:
        return float(sum(component.perimeter for component in self.components))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["num_components"] = self.num_components
        payload["total_perimeter"] = self.total_perimeter
        return payload


class OrderedBoundaryValidationError(ValueError):
    """Raised when requested validation rejects a parameterized boundary."""

    def __init__(self, report: CurveGeometryReport | OrderedBoundaryReport):
        self.report = report
        super().__init__("; ".join(report.issues) if report.issues else "Ordered boundary is invalid.")


def validate_periodic_parameterization(
    curve: PeriodicParameterization2D,
    config: BoundaryValidationConfig | None = None,
    *,
    raise_on_error: bool = False,
) -> CurveGeometryReport:
    """Evaluate regularity, derivative, orientation, closure, and simplicity."""

    settings = BoundaryValidationConfig() if config is None else config
    count = int(settings.num_samples_per_component)
    step = curve.period / count
    parameters = curve.parameter_origin + step * np.arange(count, dtype=float)
    evaluation = curve.evaluate(parameters, wrap=False)
    points = evaluation.points
    first_derivatives = evaluation.first_derivatives
    second_derivatives = evaluation.second_derivatives
    third_derivatives = evaluation.third_derivatives
    speeds = np.linalg.norm(first_derivatives, axis=1)
    weights = step * speeds
    perimeter = float(np.sum(weights))
    signed_area = 0.5 * step * float(np.sum(cross2d(points, first_derivatives)))
    if signed_area > 0.0:
        orientation = "counterclockwise"
    elif signed_area < 0.0:
        orientation = "clockwise"
    else:
        orientation = "degenerate"
    scale = max(
        float(np.linalg.norm(np.max(points, axis=0) - np.min(points, axis=0))),
        perimeter / (2.0 * np.pi),
        np.finfo(float).tiny,
    )
    probe = curve.parameter_origin + curve.period * np.arange(8, dtype=float) / 8.0
    periodic_probe = curve.evaluate(
        np.concatenate((probe, probe + curve.period)),
        wrap=False,
    )
    position_closure = float(
        np.max(np.linalg.norm(periodic_probe.points[8:] - periodic_probe.points[:8], axis=1))
    )
    first_closure = float(
        np.max(
            np.linalg.norm(
                periodic_probe.first_derivatives[8:] - periodic_probe.first_derivatives[:8],
                axis=1,
            )
        )
    )
    second_closure = float(
        np.max(
            np.linalg.norm(
                periodic_probe.second_derivatives[8:] - periodic_probe.second_derivatives[:8],
                axis=1,
            )
        )
    )
    third_closure = None
    if periodic_probe.third_derivatives is not None:
        third_closure = float(
            np.max(
                np.linalg.norm(
                    periodic_probe.third_derivatives[8:] - periodic_probe.third_derivatives[:8],
                    axis=1,
                )
            )
        )
    point_first = (
        np.roll(points, 2, axis=0)
        - 8.0 * np.roll(points, 1, axis=0)
        + 8.0 * np.roll(points, -1, axis=0)
        - np.roll(points, -2, axis=0)
    ) / (12.0 * step)
    point_second = (
        -np.roll(points, 2, axis=0)
        + 16.0 * np.roll(points, 1, axis=0)
        - 30.0 * points
        + 16.0 * np.roll(points, -1, axis=0)
        - np.roll(points, -2, axis=0)
    ) / (12.0 * step**2)
    first_scale = max(float(np.max(speeds)), scale / curve.period)
    second_scale = max(
        float(np.max(np.linalg.norm(second_derivatives, axis=1))),
        scale / curve.period**2,
    )
    first_consistency = float(
        np.max(np.linalg.norm(point_first - first_derivatives, axis=1)) / first_scale
    )
    second_consistency = float(
        np.max(np.linalg.norm(point_second - second_derivatives, axis=1)) / second_scale
    )
    third_consistency = None
    third_scale = None
    if third_derivatives is not None:
        second_first = (
            np.roll(second_derivatives, 2, axis=0)
            - 8.0 * np.roll(second_derivatives, 1, axis=0)
            + 8.0 * np.roll(second_derivatives, -1, axis=0)
            - np.roll(second_derivatives, -2, axis=0)
        ) / (12.0 * step)
        third_scale = max(
            float(np.max(np.linalg.norm(third_derivatives, axis=1))),
            scale / curve.period**3,
        )
        third_consistency = float(
            np.max(np.linalg.norm(second_first - third_derivatives, axis=1)) / third_scale
        )
    cross_tolerance = settings.intersection_relative_tolerance * scale**2
    length_tolerance = settings.intersection_relative_tolerance * scale
    self_intersections = _self_intersection_count(points, cross_tolerance, length_tolerance)
    closure_tolerance = (
        settings.closure_absolute_tolerance + settings.closure_relative_tolerance * scale
    )
    issues = []
    if position_closure > closure_tolerance:
        issues.append(f"{curve.component_id}: position is not periodic at the seam")
    if (
        first_closure
        > settings.closure_absolute_tolerance + settings.closure_relative_tolerance * first_scale
    ):
        issues.append(f"{curve.component_id}: first derivative is not periodic at the seam")
    if (
        second_closure
        > settings.closure_absolute_tolerance + settings.closure_relative_tolerance * second_scale
    ):
        issues.append(f"{curve.component_id}: second derivative is not periodic at the seam")
    if (
        third_closure is not None
        and third_scale is not None
        and third_closure
        > settings.closure_absolute_tolerance + settings.closure_relative_tolerance * third_scale
    ):
        issues.append(f"{curve.component_id}: third derivative is not periodic at the seam")
    speed_threshold = settings.minimum_speed_relative * scale / curve.period
    if float(np.min(speeds)) <= speed_threshold:
        issues.append(f"{curve.component_id}: parameterisation speed is too small")
    if abs(signed_area) <= settings.minimum_area_relative * scale**2:
        issues.append(f"{curve.component_id}: enclosed signed area is degenerate")
    if settings.require_counterclockwise and signed_area <= 0.0:
        issues.append(f"{curve.component_id}: component is not counterclockwise")
    if first_consistency > settings.derivative_relative_tolerance:
        issues.append(f"{curve.component_id}: supplied first derivative is inconsistent with positions")
    if second_consistency > settings.derivative_relative_tolerance:
        issues.append(f"{curve.component_id}: supplied second derivative is inconsistent with positions")
    if third_consistency is not None and third_consistency > settings.derivative_relative_tolerance:
        issues.append(f"{curve.component_id}: supplied third derivative is inconsistent with lower derivatives")
    if self_intersections:
        issues.append(
            f"{curve.component_id}: sampled curve has {self_intersections} self-intersection(s)"
        )
    regular_mask = speeds > speed_threshold
    curvature_values = (
        cross2d(first_derivatives, second_derivatives)[regular_mask] / speeds[regular_mask] ** 3
    )
    report = CurveGeometryReport(
        component_id=curve.component_id,
        name=curve.name,
        valid=not issues,
        issues=tuple(issues),
        num_validation_nodes=count,
        orientation=orientation,
        phase_anchor=tuple(float(value) for value in points[0]),
        parameter_origin=curve.parameter_origin,
        maximum_derivative_order=3 if third_derivatives is not None else 2,
        source_kind=curve.provenance.source_kind,
        source_identifier=curve.provenance.source_identifier,
        projection_residual=curve.provenance.projection_residual,
        fit_residual=curve.provenance.fit_residual,
        signed_area=signed_area,
        perimeter=perimeter,
        minimum_speed=float(np.min(speeds)),
        maximum_speed=float(np.max(speeds)),
        minimum_curvature=float(np.min(curvature_values)) if curvature_values.size else None,
        maximum_curvature=float(np.max(curvature_values)) if curvature_values.size else None,
        position_closure_error=position_closure,
        first_derivative_closure_error=first_closure,
        second_derivative_closure_error=second_closure,
        third_derivative_closure_error=third_closure,
        first_derivative_consistency_error=first_consistency,
        second_derivative_consistency_error=second_consistency,
        third_derivative_consistency_error=third_consistency,
        self_intersection_count=self_intersections,
        bounding_box_min=tuple(float(value) for value in np.min(points, axis=0)),
        bounding_box_max=tuple(float(value) for value in np.max(points, axis=0)),
    )
    if raise_on_error and not report.valid:
        raise OrderedBoundaryValidationError(report)
    return report


def validate_ordered_parameterization(
    boundary: OrderedBoundaryParameterization2D,
    config: BoundaryValidationConfig | None = None,
    *,
    raise_on_error: bool = False,
) -> OrderedBoundaryReport:
    """Validate every continuous component plus crossings, nesting, and clearance."""

    settings = BoundaryValidationConfig() if config is None else config
    component_reports = tuple(
        validate_periodic_parameterization(component, settings) for component in boundary.components
    )
    parameter_step = tuple(
        component.period / settings.num_samples_per_component for component in boundary.components
    )
    points = tuple(
        component.evaluate(
            component.parameter_origin
            + step * np.arange(settings.num_samples_per_component, dtype=float),
            wrap=False,
        ).points
        for component, step in zip(boundary.components, parameter_step)
    )
    intersecting_pairs = []
    nested_pairs = []
    minimum_clearance: float | None = None
    for first_index in range(boundary.num_components):
        for second_index in range(first_index + 1, boundary.num_components):
            first_id = boundary.components[first_index].component_id
            second_id = boundary.components[second_index].component_id
            first_points = points[first_index]
            second_points = points[second_index]
            pair_scale = max(
                float(np.linalg.norm(np.max(first_points, axis=0) - np.min(first_points, axis=0))),
                float(np.linalg.norm(np.max(second_points, axis=0) - np.min(second_points, axis=0))),
                np.finfo(float).tiny,
            )
            tolerance = settings.intersection_relative_tolerance * pair_scale**2
            length_tolerance = settings.intersection_relative_tolerance * pair_scale
            if _polylines_intersect(first_points, second_points, tolerance, length_tolerance):
                intersecting_pairs.append((first_id, second_id))
                minimum_clearance = 0.0
                continue
            clearance = _polyline_clearance(first_points, second_points)
            minimum_clearance = (
                clearance if minimum_clearance is None else min(minimum_clearance, clearance)
            )
            if _point_in_polygon(first_points[0], second_points):
                nested_pairs.append((first_id, second_id))
            elif _point_in_polygon(second_points[0], first_points):
                nested_pairs.append((second_id, first_id))
    issues = [issue for report in component_reports for issue in report.issues]
    for first_id, second_id in intersecting_pairs:
        issues.append(f"components {first_id} and {second_id} intersect")
    if nested_pairs and not settings.allow_nested_components:
        for inner_id, outer_id in nested_pairs:
            issues.append(f"component {inner_id} is nested inside {outer_id}")
    if (
        minimum_clearance is not None
        and minimum_clearance < settings.minimum_intercomponent_clearance
    ):
        issues.append(
            "minimum intercomponent clearance "
            f"{minimum_clearance:.6g} is below {settings.minimum_intercomponent_clearance:.6g}"
        )
    report = OrderedBoundaryReport(
        valid=not issues,
        issues=tuple(issues),
        components=component_reports,
        minimum_intercomponent_clearance=minimum_clearance,
        intersecting_component_pairs=tuple(intersecting_pairs),
        nested_component_pairs=tuple(nested_pairs),
    )
    if raise_on_error and not report.valid:
        raise OrderedBoundaryValidationError(report)
    return report


def _segment_intersection_matrix(
    first_points: np.ndarray,
    second_points: np.ndarray,
    cross_tolerance: float,
    length_tolerance: float,
) -> np.ndarray:
    first_start = first_points
    first_end = np.roll(first_points, -1, axis=0)
    second_start = second_points
    second_end = np.roll(second_points, -1, axis=0)
    first_delta = first_end - first_start
    second_delta = second_end - second_start
    o1 = cross2d(first_delta[:, None, :], second_start[None, :, :] - first_start[:, None, :])
    o2 = cross2d(first_delta[:, None, :], second_end[None, :, :] - first_start[:, None, :])
    o3 = cross2d(second_delta[None, :, :], first_start[:, None, :] - second_start[None, :, :])
    o4 = cross2d(second_delta[None, :, :], first_end[:, None, :] - second_start[None, :, :])
    proper = (
        (o1 > cross_tolerance) & (o2 < -cross_tolerance)
        | (o1 < -cross_tolerance) & (o2 > cross_tolerance)
    ) & (
        (o3 > cross_tolerance) & (o4 < -cross_tolerance)
        | (o3 < -cross_tolerance) & (o4 > cross_tolerance)
    )
    touching = (
        (np.abs(o1) <= cross_tolerance)
        & _point_on_segment_matrix(second_start, first_start, first_end, length_tolerance)
        | (np.abs(o2) <= cross_tolerance)
        & _point_on_segment_matrix(second_end, first_start, first_end, length_tolerance)
        | (np.abs(o3) <= cross_tolerance)
        & _point_on_segment_matrix(first_start, second_start, second_end, length_tolerance).T
        | (np.abs(o4) <= cross_tolerance)
        & _point_on_segment_matrix(first_end, second_start, second_end, length_tolerance).T
    )
    return proper | touching


def _point_on_segment_matrix(
    points: np.ndarray,
    segment_start: np.ndarray,
    segment_end: np.ndarray,
    length_tolerance: float,
) -> np.ndarray:
    lower = np.minimum(segment_start, segment_end)[:, None, :]
    upper = np.maximum(segment_start, segment_end)[:, None, :]
    candidates = points[None, :, :]
    return np.all(
        (candidates >= lower - length_tolerance) & (candidates <= upper + length_tolerance),
        axis=-1,
    )


def _self_intersection_count(
    points: np.ndarray,
    cross_tolerance: float,
    length_tolerance: float,
) -> int:
    intersections = _segment_intersection_matrix(points, points, cross_tolerance, length_tolerance)
    count = points.shape[0]
    indices = np.arange(count)
    adjacency = (
        (indices[:, None] == indices[None, :])
        | ((indices[:, None] - indices[None, :]) % count == 1)
        | ((indices[None, :] - indices[:, None]) % count == 1)
    )
    return int(np.count_nonzero(np.triu(intersections & ~adjacency, k=1)))


def _polylines_intersect(
    first: np.ndarray,
    second: np.ndarray,
    cross_tolerance: float,
    length_tolerance: float,
) -> bool:
    return bool(np.any(_segment_intersection_matrix(first, second, cross_tolerance, length_tolerance)))


def _point_to_segments_minimum(points: np.ndarray, segment_points: np.ndarray) -> float:
    starts = segment_points
    deltas = np.roll(segment_points, -1, axis=0) - starts
    denominator = np.sum(deltas * deltas, axis=1)
    minimum = float("inf")
    chunk_size = 256
    for start in range(0, points.shape[0], chunk_size):
        candidates = points[start : start + chunk_size]
        displacement = candidates[:, None, :] - starts[None, :, :]
        fraction = np.einsum("cnd,nd->cn", displacement, deltas) / denominator[None, :]
        fraction = np.clip(fraction, 0.0, 1.0)
        closest = starts[None, :, :] + fraction[..., None] * deltas[None, :, :]
        minimum = min(minimum, float(np.min(np.linalg.norm(candidates[:, None, :] - closest, axis=-1))))
    return minimum


def _polyline_clearance(first: np.ndarray, second: np.ndarray) -> float:
    return min(_point_to_segments_minimum(first, second), _point_to_segments_minimum(second, first))


def _point_in_polygon(point: np.ndarray, polygon: np.ndarray) -> bool:
    x, y = float(point[0]), float(point[1])
    x0 = polygon[:, 0]
    y0 = polygon[:, 1]
    x1 = np.roll(x0, -1)
    y1 = np.roll(y0, -1)
    crosses = (y0 > y) != (y1 > y)
    denominator = np.where(np.abs(y1 - y0) > 0.0, y1 - y0, 1.0)
    intersection_x = x0 + (y - y0) * (x1 - x0) / denominator
    return bool(np.count_nonzero(crosses & (x < intersection_x)) % 2)
