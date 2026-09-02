"""Shared Cartesian-contour and zero-set-projection front end.

Every fitted representation in the comparison must consume the same ordered,
projected points.  This module owns that common preprocessing and deliberately
has no dependency on an active BIE solver or on any representation-specific
fitting code.
"""

from __future__ import annotations

from dataclasses import dataclass
import operator
from typing import Any

import numpy as np

from .fields import CountedImplicitField2D, FieldEvaluationCounts, ImplicitField2D


Array = np.ndarray


class FrontendError(ValueError):
    """Base class for explicit front-end failures."""


class ContourExtractionError(FrontendError):
    """Raised when marching-squares output cannot be interpreted safely."""


class OpenContourError(ContourExtractionError):
    """Raised when marching squares reports a non-cyclic contour."""


class BoundaryTouchingContourError(ContourExtractionError):
    """Raised when a contour reaches the caller-supplied bounding box."""


class PolygonValidationError(FrontendError):
    """Raised when an ordered polygon is degenerate or self-intersecting."""


class ComponentCountError(FrontendError):
    """Raised when a single-component entry point sees zero or many loops."""

    def __init__(self, actual: int, expected: int = 1):
        self.actual = int(actual)
        self.expected = int(expected)
        super().__init__(
            f"Expected exactly {self.expected} closed zero-set component(s); "
            f"detected {self.actual}."
        )


class ProjectionError(FrontendError):
    """Raised when safeguarded Newton projection leaves failed points."""

    def __init__(self, message: str, result: "ProjectionResult | None" = None):
        self.result = result
        super().__init__(message)


def _readonly(values: Any, *, dtype: Any = np.float64) -> Array:
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _positive_integer(value: Any, *, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        integer = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if integer < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return integer


@dataclass(frozen=True)
class ProjectionConfig:
    """Scale-explicit controls for safeguarded Newton correction."""

    residual_tolerance: float = 1.0e-10
    max_iterations: int = 20
    gradient_tolerance: float = 1.0e-12
    denominator_epsilon: float = 1.0e-30
    max_step_grid_fraction: float = 0.75
    raise_on_failure: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_iterations",
            _positive_integer(self.max_iterations, name="max_iterations", minimum=1),
        )
        for name in (
            "residual_tolerance",
            "gradient_tolerance",
            "denominator_epsilon",
            "max_step_grid_fraction",
        ):
            value = float(getattr(self, name))
            lower_ok = value >= 0.0
            if name in {"gradient_tolerance", "max_step_grid_fraction"}:
                lower_ok = value > 0.0
            if not np.isfinite(value) or not lower_ok:
                relation = "positive" if name in {"gradient_tolerance", "max_step_grid_fraction"} else "non-negative"
                raise ValueError(f"{name} must be finite and {relation}.")
            object.__setattr__(self, name, value)
        if not isinstance(self.raise_on_failure, (bool, np.bool_)):
            raise TypeError("raise_on_failure must be boolean.")
        object.__setattr__(self, "raise_on_failure", bool(self.raise_on_failure))


@dataclass(frozen=True)
class FrontendConfig:
    """Configuration shared unchanged by every representation method.

    ``bounds`` follows the repository convention
    ``((xmin, ymin), (xmax, ymax))`` and ``grid_shape`` is ``(ny, nx)``.
    """

    bounds: tuple[tuple[float, float], tuple[float, float]]
    grid_shape: tuple[int, int] = (129, 129)
    projected_samples: int = 256
    level: float = 0.0
    boundary_tolerance: float | None = None
    contour_closure_tolerance: float = 1.0e-7
    intersection_relative_tolerance: float = 1.0e-12
    minimum_area_relative: float = 1.0e-12
    second_resample_and_project: bool = True
    projection: ProjectionConfig = ProjectionConfig()

    def __post_init__(self) -> None:
        bounds = np.asarray(self.bounds, dtype=np.float64)
        if bounds.shape != (2, 2) or not np.all(np.isfinite(bounds)):
            raise ValueError("bounds must be ((xmin, ymin), (xmax, ymax)) with finite values.")
        if np.any(bounds[1] <= bounds[0]):
            raise ValueError("Upper bounds must be strictly greater than lower bounds.")
        canonical_bounds = (
            (float(bounds[0, 0]), float(bounds[0, 1])),
            (float(bounds[1, 0]), float(bounds[1, 1])),
        )
        if len(self.grid_shape) != 2:
            raise ValueError("grid_shape must be (ny, nx).")
        ny = _positive_integer(self.grid_shape[0], name="grid_shape[0]", minimum=2)
        nx = _positive_integer(self.grid_shape[1], name="grid_shape[1]", minimum=2)
        projected_samples = _positive_integer(
            self.projected_samples, name="projected_samples", minimum=8
        )
        level = float(self.level)
        if not np.isfinite(level):
            raise ValueError("level must be finite.")
        boundary_tolerance = self.boundary_tolerance
        if boundary_tolerance is not None:
            boundary_tolerance = float(boundary_tolerance)
            if not np.isfinite(boundary_tolerance) or boundary_tolerance < 0.0:
                raise ValueError("boundary_tolerance must be finite and non-negative.")
        for name in (
            "contour_closure_tolerance",
            "intersection_relative_tolerance",
            "minimum_area_relative",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)
        if not isinstance(self.second_resample_and_project, (bool, np.bool_)):
            raise TypeError("second_resample_and_project must be boolean.")
        if not isinstance(self.projection, ProjectionConfig):
            raise TypeError("projection must be a ProjectionConfig object.")
        object.__setattr__(self, "bounds", canonical_bounds)
        object.__setattr__(self, "grid_shape", (ny, nx))
        object.__setattr__(self, "projected_samples", projected_samples)
        object.__setattr__(self, "level", level)
        object.__setattr__(self, "boundary_tolerance", boundary_tolerance)
        object.__setattr__(
            self, "second_resample_and_project", bool(self.second_resample_and_project)
        )

    @property
    def grid_spacing(self) -> tuple[float, float]:
        (xmin, ymin), (xmax, ymax) = self.bounds
        ny, nx = self.grid_shape
        return (xmax - xmin) / (nx - 1), (ymax - ymin) / (ny - 1)

    @property
    def resolved_boundary_tolerance(self) -> float:
        if self.boundary_tolerance is not None:
            return self.boundary_tolerance
        lower = np.asarray(self.bounds[0])
        upper = np.asarray(self.bounds[1])
        scale = max(float(np.linalg.norm(upper - lower)), 1.0)
        return 128.0 * np.finfo(np.float64).eps * scale


@dataclass(frozen=True)
class CartesianGridSample:
    x_coordinates: Array
    y_coordinates: Array
    values: Array

    def __post_init__(self) -> None:
        x = _readonly(self.x_coordinates)
        y = _readonly(self.y_coordinates)
        values = _readonly(self.values)
        if x.ndim != 1 or y.ndim != 1:
            raise ValueError("Grid coordinates must be one-dimensional.")
        if values.shape != (y.size, x.size):
            raise ValueError("Grid values must have shape (len(y), len(x)).")
        if x.size < 2 or y.size < 2:
            raise ValueError("A Cartesian grid needs at least two coordinates per axis.")
        if not np.all(np.diff(x) > 0.0) or not np.all(np.diff(y) > 0.0):
            raise ValueError("Grid coordinates must be strictly increasing.")
        object.__setattr__(self, "x_coordinates", x)
        object.__setattr__(self, "y_coordinates", y)
        object.__setattr__(self, "values", values)


@dataclass(frozen=True)
class PolygonDiagnostics:
    num_points: int
    perimeter: float
    signed_area: float
    orientation: str
    self_intersection_count: int
    bounding_box_min: tuple[float, float]
    bounding_box_max: tuple[float, float]


@dataclass(frozen=True)
class ProjectionResult:
    points: Array
    converged: Array
    gradient_failed: Array
    iteration_counts: Array
    clipped_step_counts: Array
    residuals: Array
    gradient_norms: Array

    def __post_init__(self) -> None:
        points = _readonly(self.points)
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("Projection points must have shape (num_points, 2).")
        count = points.shape[0]
        arrays = {
            "converged": _readonly(self.converged, dtype=np.bool_),
            "gradient_failed": _readonly(self.gradient_failed, dtype=np.bool_),
            "iteration_counts": _readonly(self.iteration_counts, dtype=np.int64),
            "clipped_step_counts": _readonly(self.clipped_step_counts, dtype=np.int64),
            "residuals": _readonly(self.residuals),
            "gradient_norms": _readonly(self.gradient_norms),
        }
        if any(array.shape != (count,) for array in arrays.values()):
            raise ValueError("Per-point projection diagnostics must have shape (num_points,).")
        object.__setattr__(self, "points", points)
        for name, array in arrays.items():
            object.__setattr__(self, name, array)

    @property
    def all_converged(self) -> bool:
        return bool(np.all(self.converged))

    @property
    def maximum_residual(self) -> float:
        return float(np.max(self.residuals)) if self.residuals.size else 0.0

    @property
    def total_iterations(self) -> int:
        return int(np.sum(self.iteration_counts))


@dataclass(frozen=True)
class FrontendComponent:
    component_id: str
    raw_contour: Array
    initial_points: Array
    projected_points: Array
    parameters: Array
    raw_diagnostics: PolygonDiagnostics
    projected_diagnostics: PolygonDiagnostics
    projection_passes: tuple[ProjectionResult, ...]

    def __post_init__(self) -> None:
        raw = _readonly(self.raw_contour)
        initial = _readonly(self.initial_points)
        projected = _readonly(self.projected_points)
        parameters = _readonly(self.parameters)
        for name, points in (
            ("raw_contour", raw),
            ("initial_points", initial),
            ("projected_points", projected),
        ):
            if points.ndim != 2 or points.shape[1] != 2:
                raise ValueError(f"{name} must have shape (num_points, 2).")
        if projected.shape[0] != parameters.size or parameters.ndim != 1:
            raise ValueError("parameters must contain one value per projected point.")
        if not self.projection_passes:
            raise ValueError("At least one projection pass is required.")
        if self.projection_passes[-1].points.shape != projected.shape:
            raise ValueError("The last projection pass must describe projected_points.")
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be a non-empty string.")
        object.__setattr__(self, "component_id", self.component_id.strip())
        object.__setattr__(self, "raw_contour", raw)
        object.__setattr__(self, "initial_points", initial)
        object.__setattr__(self, "projected_points", projected)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "projection_passes", tuple(self.projection_passes))


@dataclass(frozen=True)
class FrontendResult:
    config: FrontendConfig
    grid: CartesianGridSample
    components: tuple[FrontendComponent, ...]
    field_counts: FieldEvaluationCounts | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.config, FrontendConfig):
            raise TypeError("config must be a FrontendConfig object.")
        if not isinstance(self.grid, CartesianGridSample):
            raise TypeError("grid must be a CartesianGridSample object.")
        object.__setattr__(self, "components", tuple(self.components))

    @property
    def num_components(self) -> int:
        return len(self.components)

    @property
    def single_component(self) -> FrontendComponent:
        if self.num_components != 1:
            raise ComponentCountError(self.num_components)
        return self.components[0]

    @property
    def parameters(self) -> Array:
        return self.single_component.parameters

    @property
    def projected_points(self) -> Array:
        return self.single_component.projected_points


def _coerce_values(values: Any, point_shape: tuple[int, ...]) -> Array:
    result = np.asarray(values, dtype=np.float64)
    if result.shape == point_shape + (1,):
        result = result[..., 0]
    if result.shape != point_shape:
        raise ValueError(
            f"field.value must return shape {point_shape}; received {result.shape}."
        )
    if not np.all(np.isfinite(result)):
        raise ValueError("field.value returned non-finite data.")
    return result


def _coerce_gradients(values: Any, point_shape: tuple[int, ...]) -> Array:
    result = np.asarray(values, dtype=np.float64)
    expected = point_shape + (2,)
    if result.shape != expected:
        raise ValueError(
            f"field.gradient must return shape {expected}; received {result.shape}."
        )
    if not np.all(np.isfinite(result)):
        raise ValueError("field.gradient returned non-finite data.")
    return result


def evaluate_cartesian_grid(
    field: ImplicitField2D,
    config: FrontendConfig,
) -> CartesianGridSample:
    """Evaluate a field once on the configured physical Cartesian grid."""

    (xmin, ymin), (xmax, ymax) = config.bounds
    ny, nx = config.grid_shape
    x = np.linspace(xmin, xmax, nx, dtype=np.float64)
    y = np.linspace(ymin, ymax, ny, dtype=np.float64)
    grid_x, grid_y = np.meshgrid(x, y, indexing="xy")
    points = np.stack((grid_x, grid_y), axis=-1)
    values = _coerce_values(field.value(points.reshape(-1, 2)), (ny * nx,)).reshape(ny, nx)
    return CartesianGridSample(x, y, values)


def polygon_signed_area(points: Array) -> float:
    values = np.asarray(points, dtype=np.float64)
    return 0.5 * float(
        np.sum(values[:, 0] * np.roll(values[:, 1], -1) - values[:, 1] * np.roll(values[:, 0], -1))
    )


def polygon_perimeter(points: Array) -> float:
    values = np.asarray(points, dtype=np.float64)
    return float(np.sum(np.linalg.norm(np.roll(values, -1, axis=0) - values, axis=1)))


def _cross(first: Array, second: Array) -> float:
    return float(first[0] * second[1] - first[1] * second[0])


def _point_on_segment(
    point: Array,
    start: Array,
    end: Array,
    *,
    cross_tolerance: float,
    length_tolerance: float,
) -> bool:
    if abs(_cross(end - start, point - start)) > cross_tolerance:
        return False
    return bool(
        np.all(point >= np.minimum(start, end) - length_tolerance)
        and np.all(point <= np.maximum(start, end) + length_tolerance)
    )


def _segments_intersect(
    first_start: Array,
    first_end: Array,
    second_start: Array,
    second_end: Array,
    *,
    cross_tolerance: float,
    length_tolerance: float,
) -> bool:
    first_direction = first_end - first_start
    second_direction = second_end - second_start
    first_side_start = _cross(first_direction, second_start - first_start)
    first_side_end = _cross(first_direction, second_end - first_start)
    second_side_start = _cross(second_direction, first_start - second_start)
    second_side_end = _cross(second_direction, first_end - second_start)
    if (
        first_side_start * first_side_end < -(cross_tolerance**2)
        and second_side_start * second_side_end < -(cross_tolerance**2)
    ):
        return True
    return any(
        (
            (
            abs(first_side_start) <= cross_tolerance
            and _point_on_segment(
                second_start,
                first_start,
                first_end,
                cross_tolerance=cross_tolerance,
                length_tolerance=length_tolerance,
            )
            ),
            (
            abs(first_side_end) <= cross_tolerance
            and _point_on_segment(
                second_end,
                first_start,
                first_end,
                cross_tolerance=cross_tolerance,
                length_tolerance=length_tolerance,
            )
            ),
            (
            abs(second_side_start) <= cross_tolerance
            and _point_on_segment(
                first_start,
                second_start,
                second_end,
                cross_tolerance=cross_tolerance,
                length_tolerance=length_tolerance,
            )
            ),
            (
            abs(second_side_end) <= cross_tolerance
            and _point_on_segment(
                first_end,
                second_start,
                second_end,
                cross_tolerance=cross_tolerance,
                length_tolerance=length_tolerance,
            )
            ),
        ),
    )


def polygon_self_intersection_count(
    points: Array,
    *,
    relative_tolerance: float = 1.0e-12,
) -> int:
    """Count intersecting nonadjacent segment pairs in a cyclic polygon."""

    values = np.asarray(points, dtype=np.float64)
    count = values.shape[0]
    if values.ndim != 2 or values.shape[1] != 2 or count < 3:
        raise ValueError("points must have shape (num_points, 2), with at least 3 points.")
    extent = np.ptp(values, axis=0)
    scale = max(float(np.linalg.norm(extent)), np.finfo(np.float64).tiny)
    cross_tolerance = float(relative_tolerance) * scale**2
    length_tolerance = float(relative_tolerance) * scale
    intersections = 0
    for first in range(count):
        first_next = (first + 1) % count
        for second in range(first + 1, count):
            second_next = (second + 1) % count
            if first == second or first_next == second or second_next == first:
                continue
            if _segments_intersect(
                values[first],
                values[first_next],
                values[second],
                values[second_next],
                cross_tolerance=cross_tolerance,
                length_tolerance=length_tolerance,
            ):
                intersections += 1
    return intersections


def polygon_diagnostics(
    points: Array,
    *,
    intersection_relative_tolerance: float = 1.0e-12,
    minimum_area_relative: float = 1.0e-12,
    require_counterclockwise: bool = True,
) -> PolygonDiagnostics:
    """Validate and summarize one cyclic polygon without a duplicated endpoint."""

    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] < 3:
        raise PolygonValidationError(
            "A cyclic polygon must have shape (num_points, 2) with at least three points."
        )
    if not np.all(np.isfinite(values)):
        raise PolygonValidationError("Polygon coordinates must be finite.")
    extent = np.ptp(values, axis=0)
    scale = max(float(np.linalg.norm(extent)), np.finfo(np.float64).tiny)
    segment_lengths = np.linalg.norm(np.roll(values, -1, axis=0) - values, axis=1)
    if np.any(segment_lengths <= intersection_relative_tolerance * scale):
        raise PolygonValidationError("Polygon contains a zero-length or duplicate cyclic edge.")
    perimeter = float(np.sum(segment_lengths))
    signed_area = polygon_signed_area(values)
    if abs(signed_area) <= minimum_area_relative * scale**2:
        raise PolygonValidationError("Polygon has numerically degenerate signed area.")
    orientation = "counterclockwise" if signed_area > 0.0 else "clockwise"
    if require_counterclockwise and signed_area <= 0.0:
        raise PolygonValidationError("Polygon orientation is not counterclockwise.")
    intersections = polygon_self_intersection_count(
        values, relative_tolerance=intersection_relative_tolerance
    )
    if intersections:
        raise PolygonValidationError(
            f"Polygon has {intersections} nonadjacent segment intersection(s)."
        )
    return PolygonDiagnostics(
        num_points=values.shape[0],
        perimeter=perimeter,
        signed_area=signed_area,
        orientation=orientation,
        self_intersection_count=intersections,
        bounding_box_min=tuple(float(value) for value in np.min(values, axis=0)),
        bounding_box_max=tuple(float(value) for value in np.max(values, axis=0)),
    )


def _canonicalize_counterclockwise_polygon(points: Array, config: FrontendConfig) -> Array:
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] < 3:
        raise PolygonValidationError("Extracted contour has fewer than three cyclic vertices.")
    if polygon_signed_area(values) < 0.0:
        values = values[::-1]
    # Deterministic phase: rightmost vertex, then lower y for an exact x tie.
    anchor = int(np.lexsort((values[:, 1], -values[:, 0]))[0])
    values = np.roll(values, -anchor, axis=0)
    polygon_diagnostics(
        values,
        intersection_relative_tolerance=config.intersection_relative_tolerance,
        minimum_area_relative=config.minimum_area_relative,
    )
    return np.array(values, dtype=np.float64, copy=True)


def _remove_consecutive_marching_squares_duplicates(
    points: Array,
    *,
    relative_tolerance: float,
) -> Array:
    """Remove only adjacent near-duplicates emitted at exact grid zeros.

    ``skimage.measure.find_contours`` may repeat a grid vertex when the level
    set is exactly zero there.  Those zero-length steps carry no contour
    information and otherwise make a valid closed curve fail polygon
    validation.  Non-adjacent duplicates remain untouched so genuine contour
    degeneracies are still rejected by :func:`polygon_diagnostics`.
    """

    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] < 3:
        raise PolygonValidationError("Extracted contour has invalid point coordinates.")
    extent = np.ptp(values, axis=0)
    scale = max(float(np.linalg.norm(extent)), np.finfo(np.float64).tiny)
    tolerance = float(relative_tolerance) * scale
    kept = [values[0]]
    for point in values[1:]:
        if float(np.linalg.norm(point - kept[-1])) > tolerance:
            kept.append(point)
    if len(kept) > 1 and float(np.linalg.norm(kept[-1] - kept[0])) <= tolerance:
        kept.pop()
    if len(kept) < 3:
        raise PolygonValidationError(
            "Extracted contour has fewer than three vertices after removing "
            "consecutive marching-squares duplicates."
        )
    return np.asarray(kept, dtype=np.float64)


def _physical_contours(
    grid: CartesianGridSample,
    config: FrontendConfig,
) -> tuple[Array, ...]:
    try:
        from skimage import measure
    except ImportError as exc:  # pragma: no cover - dependency is present in the project environment
        raise ImportError("The shared contour front end requires scikit-image.") from exc

    index_contours = measure.find_contours(
        grid.values,
        level=config.level,
        fully_connected="low",
        positive_orientation="low",
    )
    polygons: list[Array] = []
    for contour_index, contour in enumerate(index_contours):
        contour = np.asarray(contour, dtype=np.float64)
        if contour.ndim != 2 or contour.shape[1] != 2 or contour.shape[0] < 2:
            raise ContourExtractionError(
                f"Marching-squares contour {contour_index} has an invalid array shape."
            )
        closure_error = float(np.linalg.norm(contour[0] - contour[-1]))
        if closure_error > config.contour_closure_tolerance:
            raise OpenContourError(
                f"Marching-squares contour {contour_index} is open "
                f"(index-space closure error {closure_error:.3e})."
            )
        contour = contour[:-1]
        if contour.shape[0] < 3:
            raise ContourExtractionError(
                f"Marching-squares contour {contour_index} has fewer than three vertices."
            )
        rows = contour[:, 0]
        columns = contour[:, 1]
        x = np.interp(columns, np.arange(grid.x_coordinates.size), grid.x_coordinates)
        y = np.interp(rows, np.arange(grid.y_coordinates.size), grid.y_coordinates)
        physical = np.column_stack((x, y))
        physical = _remove_consecutive_marching_squares_duplicates(
            physical,
            relative_tolerance=config.intersection_relative_tolerance,
        )
        tolerance = config.resolved_boundary_tolerance
        (xmin, ymin), (xmax, ymax) = config.bounds
        if bool(
            np.any(physical[:, 0] <= xmin + tolerance)
            or np.any(physical[:, 0] >= xmax - tolerance)
            or np.any(physical[:, 1] <= ymin + tolerance)
            or np.any(physical[:, 1] >= ymax - tolerance)
        ):
            raise BoundaryTouchingContourError(
                f"Marching-squares contour {contour_index} touches the physical bounding box."
            )
        polygons.append(_canonicalize_counterclockwise_polygon(physical, config))

    # Stable component IDs are spatial, not size-ranked: no largest-component selection.
    polygons.sort(
        key=lambda polygon: tuple(float(value) for value in np.mean(polygon, axis=0))
    )
    return tuple(polygons)


def resample_closed_polygon(points: Array, num_samples: int) -> Array:
    """Resample a cyclic polygon uniformly in cumulative chord length."""

    count = _positive_integer(num_samples, name="num_samples", minimum=3)
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] < 3:
        raise ValueError("points must have shape (num_points, 2), with at least 3 points.")
    extended = np.vstack((values, values[0]))
    lengths = np.linalg.norm(np.diff(extended, axis=0), axis=1)
    if np.any(lengths <= 0.0):
        raise PolygonValidationError("Cannot resample a polygon with a zero-length edge.")
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    perimeter = float(cumulative[-1])
    targets = perimeter * np.arange(count, dtype=np.float64) / count
    x = np.interp(targets, cumulative, extended[:, 0])
    y = np.interp(targets, cumulative, extended[:, 1])
    return np.column_stack((x, y))


def _chord_parameters(points: Array) -> Array:
    values = np.asarray(points, dtype=np.float64)
    lengths = np.linalg.norm(np.roll(values, -1, axis=0) - values, axis=1)
    perimeter = float(np.sum(lengths))
    if not np.isfinite(perimeter) or perimeter <= 0.0:
        raise PolygonValidationError("Projected polygon has no positive perimeter.")
    cumulative = np.concatenate(([0.0], np.cumsum(lengths[:-1])))
    return 2.0 * np.pi * cumulative / perimeter


def project_to_zero_set(
    field: ImplicitField2D,
    points: Array,
    *,
    grid_spacing: tuple[float, float] | float,
    level: float = 0.0,
    config: ProjectionConfig | None = None,
) -> ProjectionResult:
    """Safeguarded vectorized Newton/closest-point correction to ``F=level``."""

    settings = ProjectionConfig() if config is None else config
    if not isinstance(settings, ProjectionConfig):
        raise TypeError("config must be a ProjectionConfig object.")
    projected = np.asarray(points, dtype=np.float64)
    if projected.ndim != 2 or projected.shape[1] != 2 or projected.shape[0] == 0:
        raise ValueError("points must have shape (num_points, 2), with at least one point.")
    if not np.all(np.isfinite(projected)):
        raise ValueError("points must be finite.")
    projected = projected.copy()
    spacing_values = np.asarray(grid_spacing, dtype=np.float64)
    if spacing_values.ndim == 0:
        spacing_values = np.repeat(spacing_values, 2)
    if spacing_values.shape != (2,) or not np.all(np.isfinite(spacing_values)) or np.any(spacing_values <= 0.0):
        raise ValueError("grid_spacing must contain one or two finite positive values.")
    level_value = float(level)
    if not np.isfinite(level_value):
        raise ValueError("level must be finite.")
    max_step = settings.max_step_grid_fraction * float(np.min(spacing_values))
    count = projected.shape[0]
    converged = np.zeros(count, dtype=bool)
    gradient_failed = np.zeros(count, dtype=bool)
    iterations = np.zeros(count, dtype=np.int64)
    clipped_steps = np.zeros(count, dtype=np.int64)

    for _ in range(settings.max_iterations):
        active = ~(converged | gradient_failed)
        if not np.any(active):
            break
        indices = np.flatnonzero(active)
        values = _coerce_values(field.value(projected[indices]), (indices.size,)) - level_value
        newly_converged = np.abs(values) <= settings.residual_tolerance
        converged[indices[newly_converged]] = True
        indices = indices[~newly_converged]
        values = values[~newly_converged]
        if indices.size == 0:
            continue
        iterations[indices] += 1
        gradients = _coerce_gradients(field.gradient(projected[indices]), (indices.size,))
        gradient_norms = np.linalg.norm(gradients, axis=1)
        bad_gradient = gradient_norms < settings.gradient_tolerance
        gradient_failed[indices[bad_gradient]] = True
        valid_indices = indices[~bad_gradient]
        if valid_indices.size == 0:
            continue
        valid_values = values[~bad_gradient]
        valid_gradients = gradients[~bad_gradient]
        valid_norms = gradient_norms[~bad_gradient]
        corrections = (
            valid_values[:, None]
            * valid_gradients
            / (valid_norms[:, None] ** 2 + settings.denominator_epsilon)
        )
        correction_norms = np.linalg.norm(corrections, axis=1)
        clipped = correction_norms > max_step
        if np.any(clipped):
            corrections[clipped] *= (max_step / correction_norms[clipped])[:, None]
            clipped_steps[valid_indices[clipped]] += 1
        projected[valid_indices] -= corrections

    final_values = _coerce_values(field.value(projected), (count,)) - level_value
    final_residuals = np.abs(final_values)
    converged |= final_residuals <= settings.residual_tolerance
    final_gradients = _coerce_gradients(field.gradient(projected), (count,))
    final_gradient_norms = np.linalg.norm(final_gradients, axis=1)
    gradient_failed |= (~converged) & (final_gradient_norms < settings.gradient_tolerance)
    result = ProjectionResult(
        points=projected,
        converged=converged,
        gradient_failed=gradient_failed,
        iteration_counts=iterations,
        clipped_step_counts=clipped_steps,
        residuals=final_residuals,
        gradient_norms=final_gradient_norms,
    )
    if settings.raise_on_failure and not result.all_converged:
        failed = int(np.count_nonzero(~result.converged))
        near_critical = int(np.count_nonzero(result.gradient_failed))
        raise ProjectionError(
            f"Zero-set projection failed for {failed}/{count} point(s); "
            f"{near_critical} encountered gradients below the configured threshold.",
            result,
        )
    return result


def _prepare_component(
    field: ImplicitField2D,
    raw_contour: Array,
    component_id: str,
    config: FrontendConfig,
) -> FrontendComponent:
    raw_diagnostics = polygon_diagnostics(
        raw_contour,
        intersection_relative_tolerance=config.intersection_relative_tolerance,
        minimum_area_relative=config.minimum_area_relative,
    )
    initial = resample_closed_polygon(raw_contour, config.projected_samples)
    polygon_diagnostics(
        initial,
        intersection_relative_tolerance=config.intersection_relative_tolerance,
        minimum_area_relative=config.minimum_area_relative,
    )
    first_projection = project_to_zero_set(
        field,
        initial,
        grid_spacing=config.grid_spacing,
        level=config.level,
        config=config.projection,
    )
    polygon_diagnostics(
        first_projection.points,
        intersection_relative_tolerance=config.intersection_relative_tolerance,
        minimum_area_relative=config.minimum_area_relative,
    )
    projection_passes = [first_projection]
    if config.second_resample_and_project:
        second_initial = resample_closed_polygon(first_projection.points, config.projected_samples)
        second_projection = project_to_zero_set(
            field,
            second_initial,
            grid_spacing=config.grid_spacing,
            level=config.level,
            config=config.projection,
        )
        projection_passes.append(second_projection)
    projected = projection_passes[-1].points
    projected_diagnostics = polygon_diagnostics(
        projected,
        intersection_relative_tolerance=config.intersection_relative_tolerance,
        minimum_area_relative=config.minimum_area_relative,
    )
    return FrontendComponent(
        component_id=component_id,
        raw_contour=raw_contour,
        initial_points=initial,
        projected_points=projected,
        parameters=_chord_parameters(projected),
        raw_diagnostics=raw_diagnostics,
        projected_diagnostics=projected_diagnostics,
        projection_passes=tuple(projection_passes),
    )


def _run_frontend(
    field: ImplicitField2D,
    config: FrontendConfig,
    *,
    require_single_component: bool,
) -> FrontendResult:
    if not isinstance(config, FrontendConfig):
        raise TypeError("config must be a FrontendConfig object.")
    if not isinstance(require_single_component, bool):
        raise TypeError("require_single_component must be boolean.")
    grid = evaluate_cartesian_grid(field, config)
    raw_contours = _physical_contours(grid, config)
    if require_single_component and len(raw_contours) != 1:
        raise ComponentCountError(len(raw_contours))
    components = tuple(
        _prepare_component(field, contour, f"component_{index:03d}", config)
        for index, contour in enumerate(raw_contours)
    )
    counts = field.counts if isinstance(field, CountedImplicitField2D) else None
    return FrontendResult(config=config, grid=grid, components=components, field_counts=counts)


def extract_frontend_components(
    field: ImplicitField2D,
    config: FrontendConfig,
) -> FrontendResult:
    """Extract and prepare every closed component without size-based selection."""

    return _run_frontend(field, config, require_single_component=False)


def prepare_single_component(
    field: ImplicitField2D,
    config: FrontendConfig,
) -> FrontendResult:
    """Run the Phase-1 front end and fail unless exactly one component exists."""

    return _run_frontend(field, config, require_single_component=True)


__all__ = [
    "BoundaryTouchingContourError",
    "CartesianGridSample",
    "ComponentCountError",
    "ContourExtractionError",
    "FrontendComponent",
    "FrontendConfig",
    "FrontendError",
    "FrontendResult",
    "OpenContourError",
    "PolygonDiagnostics",
    "PolygonValidationError",
    "ProjectionConfig",
    "ProjectionError",
    "ProjectionResult",
    "evaluate_cartesian_grid",
    "extract_frontend_components",
    "polygon_diagnostics",
    "polygon_perimeter",
    "polygon_self_intersection_count",
    "polygon_signed_area",
    "prepare_single_component",
    "project_to_zero_set",
    "resample_closed_polygon",
]
