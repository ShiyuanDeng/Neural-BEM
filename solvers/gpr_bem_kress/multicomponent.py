"""Opt-in Kress/Muller support for disconnected, same-material inclusions.

This module is deliberately separate from the established single-component
API.  It consumes :class:`ordered_boundary.OrderedBoundary2D` directly and
keeps every component's periodic grid independent.  Singular self
interactions are delegated unchanged to :func:`build_muller_difference_blocks`;
interactions between distinct components are smooth exterior Helmholtz
operators evaluated with ordinary periodic trapezoidal weights.

The supported topology is a collection of disjoint, non-nested components in
one homogeneous exterior.  Every component has the same homogeneous interior
material.  Close-evaluation quadrature is not implemented, so a configurable
clearance guard rejects insufficiently separated components and field points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import numpy as np
from scipy.special import hankel1

from ordered_boundary import OrderedBoundary2D, PeriodicCurve2D

from ._kernels import pair_geometry, validate_wavenumber
from .conventions import PROJECT_MULLER_CONVENTION
from .geometry import PeriodicCurveAdapter, adapt_periodic_curve
from .materials import Material
from .operators import (
    MullerAssemblyConfig,
    MullerDifferenceBlocks,
    build_muller_difference_blocks,
)


class MultiComponentKressGeometryError(ValueError):
    """Base class for geometry rejected by the multi-component Kress path."""


class MultiComponentCurveGeometryError(MultiComponentKressGeometryError):
    """Raised when one component is not an admissible periodic Kress grid."""


class MultiComponentTopologyError(MultiComponentKressGeometryError):
    """Raised when components do not form supported disjoint inclusions."""


class MultiComponentFieldPointError(MultiComponentKressGeometryError):
    """Raised when a source or receiver is inadmissible for exterior evaluation."""


def _readonly(values: np.ndarray, *, dtype) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True, order="C")
    result.setflags(write=False)
    return result


def _finite_readonly_array(
    values,
    *,
    dtype,
    name: str,
    shape: tuple[int, ...] | None = None,
    ndim: int | None = None,
    real_valued: bool = False,
) -> np.ndarray:
    """Validate and defensively freeze one public result array.

    Builder-owned arrays that are already C-contiguous, read-only, and own
    their storage are reused.  Public callers otherwise receive a private
    copy, so freezing a view cannot leave a mutable base array behind it.
    """

    if real_valued and np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    result = np.asarray(values, dtype=dtype)
    if shape is not None and result.shape != shape:
        raise ValueError(f"{name} must have shape {shape}.")
    if ndim is not None and result.ndim != ndim:
        raise ValueError(f"{name} must be {ndim}-dimensional.")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values.")
    expected_dtype = np.dtype(dtype)
    if (
        result.dtype == expected_dtype
        and result.flags.c_contiguous
        and result.flags.owndata
        and not result.flags.writeable
    ):
        return result
    return _readonly(result, dtype=expected_dtype)


def _freeze_metadata(value):
    """Recursively detach mutable containers used by public diagnostics."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_metadata(item) for key, item in value.items()}
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_metadata(item) for item in value)
    if isinstance(value, np.ndarray):
        result = np.array(value, copy=True, order="C")
        result.setflags(write=False)
        return result
    return value


def _frozen_mapping(values, *, name: str) -> Mapping[str, object]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    return _freeze_metadata(values)


def _real_points(values, *, name: str) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    result = np.atleast_2d(np.asarray(values, dtype=np.float64))
    if result.ndim != 2 or result.shape[1] != 2 or result.shape[0] == 0:
        raise ValueError(f"{name} must have shape (count, 2).")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values.")
    return result


def _source_strengths(values, count: int) -> np.ndarray:
    result = np.atleast_1d(np.asarray(values, dtype=np.complex128))
    if result.ndim != 1:
        raise ValueError("source_strength must be scalar or one-dimensional.")
    if result.size == 1 and count > 1:
        result = np.full(count, result[0], dtype=np.complex128)
    if result.shape != (count,):
        raise ValueError("source_strength must be scalar or have one value per source.")
    if not np.all(np.isfinite(result)):
        raise ValueError("source_strength must contain only finite values.")
    return result


def _trace_matrix(values, num_nodes: int, *, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.complex128)
    if result.ndim == 1:
        result = result[None, :]
    if result.ndim != 2 or result.shape[0] == 0 or result.shape[1] != num_nodes:
        raise ValueError(f"{name} must have shape (num_rhs, {num_nodes}).")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values.")
    return result


def _nonnegative_finite(value: float, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number, not bool.")
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


def _positive_finite(value: float, *, name: str) -> float:
    result = _nonnegative_finite(value, name=name)
    if result == 0.0:
        raise ValueError(f"{name} must be positive.")
    return result


def _positive_integer(value: int, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result != value:
        raise TypeError(f"{name} must be an integer.")
    if result < 1:
        raise ValueError(f"{name} must be positive.")
    return result


def _component_adapter(
    component: PeriodicCurve2D,
    *,
    context: str,
) -> PeriodicCurveAdapter:
    """Translate the single-curve adapter contract into this API's hierarchy."""

    try:
        return adapt_periodic_curve(component)
    except (TypeError, ValueError) as exc:
        component_id = getattr(component, "component_id", "<unknown>")
        raise MultiComponentCurveGeometryError(
            f"{context} {component_id!r} is not an admissible Kress component: {exc}"
        ) from exc


def _cross2d(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return first[..., 0] * second[..., 1] - first[..., 1] * second[..., 0]


def _point_to_segment_distances(
    points: np.ndarray,
    segment_starts: np.ndarray,
) -> np.ndarray:
    """Return all point-to-closed-polygon-segment distances."""

    segment_vectors = np.roll(segment_starts, -1, axis=0) - segment_starts
    segment_squared = np.einsum("sd,sd->s", segment_vectors, segment_vectors)
    displacement = points[:, None, :] - segment_starts[None, :, :]
    numerator = np.einsum("psd,sd->ps", displacement, segment_vectors)
    fraction = np.divide(
        numerator,
        segment_squared[None, :],
        out=np.zeros_like(numerator),
        where=segment_squared[None, :] > 0.0,
    )
    fraction = np.clip(fraction, 0.0, 1.0)
    closest = (
        segment_starts[None, :, :]
        + fraction[..., None] * segment_vectors[None, :, :]
    )
    return np.linalg.norm(points[:, None, :] - closest, axis=-1)


def _segment_intersection_matrix(
    first_points: np.ndarray,
    second_points: np.ndarray,
    *,
    length_tolerance: float,
) -> np.ndarray:
    first_start = first_points
    first_end = np.roll(first_points, -1, axis=0)
    second_start = second_points
    second_end = np.roll(second_points, -1, axis=0)
    first_delta = first_end - first_start
    second_delta = second_end - second_start
    o1 = _cross2d(
        first_delta[:, None, :],
        second_start[None, :, :] - first_start[:, None, :],
    )
    o2 = _cross2d(
        first_delta[:, None, :],
        second_end[None, :, :] - first_start[:, None, :],
    )
    o3 = _cross2d(
        second_delta[None, :, :],
        first_start[:, None, :] - second_start[None, :, :],
    )
    o4 = _cross2d(
        second_delta[None, :, :],
        first_end[:, None, :] - second_start[None, :, :],
    )
    scale = max(
        float(np.max(np.linalg.norm(first_delta, axis=1))),
        float(np.max(np.linalg.norm(second_delta, axis=1))),
        np.finfo(float).tiny,
    )
    cross_tolerance = length_tolerance * scale
    proper = (
        ((o1 > cross_tolerance) & (o2 < -cross_tolerance))
        | ((o1 < -cross_tolerance) & (o2 > cross_tolerance))
    ) & (
        ((o3 > cross_tolerance) & (o4 < -cross_tolerance))
        | ((o3 < -cross_tolerance) & (o4 > cross_tolerance))
    )

    def within(
        candidates: np.ndarray,
        starts: np.ndarray,
        ends: np.ndarray,
    ) -> np.ndarray:
        lower = np.minimum(starts, ends)[:, None, :] - length_tolerance
        upper = np.maximum(starts, ends)[:, None, :] + length_tolerance
        return np.all(
            (candidates[None, :, :] >= lower)
            & (candidates[None, :, :] <= upper),
            axis=-1,
        )

    touching = (
        (np.abs(o1) <= cross_tolerance)
        & within(second_start, first_start, first_end)
        | (np.abs(o2) <= cross_tolerance)
        & within(second_end, first_start, first_end)
        | (np.abs(o3) <= cross_tolerance)
        & within(first_start, second_start, second_end).T
        | (np.abs(o4) <= cross_tolerance)
        & within(first_end, second_start, second_end).T
    )
    return proper | touching


def _inside_closed_polygon(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    x = points[:, 0, None]
    y = points[:, 1, None]
    x0 = polygon[:, 0][None, :]
    y0 = polygon[:, 1][None, :]
    x1 = np.roll(polygon[:, 0], -1)[None, :]
    y1 = np.roll(polygon[:, 1], -1)[None, :]
    crosses = (y0 > y) != (y1 > y)
    denominator = np.where(np.abs(y1 - y0) > 0.0, y1 - y0, 1.0)
    intersection_x = x0 + (y - y0) * (x1 - x0) / denominator
    return np.count_nonzero(crosses & (x < intersection_x), axis=1) % 2 == 1


def _component_pair_clearance(
    first: PeriodicCurve2D,
    second: PeriodicCurve2D,
) -> tuple[float, bool, bool]:
    first_points = first.points
    second_points = second.points
    scale = max(
        float(np.linalg.norm(np.ptp(first_points, axis=0))),
        float(np.linalg.norm(np.ptp(second_points, axis=0))),
        np.finfo(float).tiny,
    )
    length_tolerance = 64.0 * np.finfo(float).eps * scale
    intersects = bool(
        np.any(
            _segment_intersection_matrix(
                first_points,
                second_points,
                length_tolerance=length_tolerance,
            )
        )
    )
    if intersects:
        return 0.0, True, False
    clearance = min(
        float(np.min(_point_to_segment_distances(first_points, second_points))),
        float(np.min(_point_to_segment_distances(second_points, first_points))),
    )
    nested = bool(
        _inside_closed_polygon(first_points[:1], second_points)[0]
        or _inside_closed_polygon(second_points[:1], first_points)[0]
    )
    return clearance, False, nested


def _validate_component_pair(
    first: PeriodicCurve2D,
    second: PeriodicCurve2D,
    settings: "MultiComponentAssemblyConfig",
) -> "ComponentPairReport":
    if first.component_id == second.component_id:
        raise MultiComponentTopologyError(
            "distinct components must have distinct component_id values."
        )
    clearance, intersects, nested = _component_pair_clearance(first, second)
    required = max(
        settings.minimum_absolute_clearance,
        settings.minimum_clearance_in_weights
        * max(
            float(np.max(first.arc_length_weights)),
            float(np.max(second.arc_length_weights)),
        ),
    )
    if intersects:
        raise MultiComponentTopologyError(
            f"components {first.component_id!r} and {second.component_id!r} "
            "intersect or touch."
        )
    if nested:
        raise MultiComponentTopologyError(
            f"components {first.component_id!r} and {second.component_id!r} "
            "are nested; this module supports disjoint inclusions only."
        )
    if clearance <= required:
        raise MultiComponentTopologyError(
            f"components {first.component_id!r} and {second.component_id!r} "
            "are too close for ordinary cross-component quadrature: "
            f"minimum {clearance:.6e}, required > {required:.6e}."
        )
    return ComponentPairReport(
        first_component_id=first.component_id,
        second_component_id=second.component_id,
        clearance=clearance,
        required_clearance=required,
        first_num_nodes=first.num_nodes,
        second_num_nodes=second.num_nodes,
    )


def _minimum_curve_distance(points: np.ndarray, curve: PeriodicCurve2D) -> float:
    minimum = float("inf")
    for first in range(0, points.shape[0], 256):
        distances = _point_to_segment_distances(
            points[first : first + 256],
            curve.points,
        )
        minimum = min(minimum, float(np.min(distances)))
    return minimum


def _validate_exterior_points(
    points: np.ndarray,
    boundary: OrderedBoundary2D,
    *,
    name: str,
    minimum_clearance: float,
) -> float:
    minimum_distance = float("inf")
    for component in boundary.components:
        if np.any(_inside_closed_polygon(points, component.points)):
            raise MultiComponentFieldPointError(
                f"{name} must lie in the homogeneous exterior."
            )
        minimum_distance = min(
            minimum_distance,
            _minimum_curve_distance(points, component),
        )
    if minimum_distance <= minimum_clearance:
        raise MultiComponentFieldPointError(
            f"{name} are too close to the boundary for ordinary quadrature: "
            f"minimum {minimum_distance:.6e}, required > {minimum_clearance:.6e}."
        )
    return minimum_distance


def _validate_supported_materials(exterior: Material, interior: Material) -> None:
    if not isinstance(exterior, Material) or not isinstance(interior, Material):
        raise TypeError("exterior and interior must be gpr_bem_kress.Material objects.")
    if not np.isclose(exterior.mur, 1.0, rtol=0.0, atol=1.0e-14) or not np.isclose(
        interior.mur,
        1.0,
        rtol=0.0,
        atol=1.0e-14,
    ):
        raise ValueError("Multi-component Kress currently supports nonmagnetic media only.")
    if exterior.sigma != 0.0 or interior.sigma != 0.0:
        raise ValueError(
            "The high-level multi-component pipeline currently supports lossless "
            "materials only; use the lower-level complex-wavenumber builder for tests."
        )


@dataclass(frozen=True)
class MultiComponentAssemblyConfig:
    """Controls self quadrature and the admissible component separation."""

    self_assembly: MullerAssemblyConfig = field(default_factory=MullerAssemblyConfig)
    minimum_clearance_in_weights: float = 2.0
    minimum_absolute_clearance: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.self_assembly, MullerAssemblyConfig):
            raise TypeError("self_assembly must be a MullerAssemblyConfig object.")
        object.__setattr__(
            self,
            "minimum_clearance_in_weights",
            _nonnegative_finite(
                self.minimum_clearance_in_weights,
                name="minimum_clearance_in_weights",
            ),
        )
        object.__setattr__(
            self,
            "minimum_absolute_clearance",
            _nonnegative_finite(
                self.minimum_absolute_clearance,
                name="minimum_absolute_clearance",
            ),
        )


@dataclass(frozen=True)
class ComponentPairReport:
    """Topology and quadrature information for one unordered component pair."""

    first_component_id: str
    second_component_id: str
    clearance: float
    required_clearance: float
    first_num_nodes: int
    second_num_nodes: int

    def __post_init__(self) -> None:
        first_id = str(self.first_component_id).strip()
        second_id = str(self.second_component_id).strip()
        if not first_id or not second_id:
            raise ValueError("component identifiers must be non-empty strings.")
        if first_id == second_id:
            raise ValueError("a component-pair report requires distinct identifiers.")
        clearance = _positive_finite(self.clearance, name="clearance")
        required = _nonnegative_finite(
            self.required_clearance,
            name="required_clearance",
        )
        if clearance <= required:
            raise ValueError("clearance must be greater than required_clearance.")
        first_count = _positive_integer(self.first_num_nodes, name="first_num_nodes")
        second_count = _positive_integer(self.second_num_nodes, name="second_num_nodes")
        object.__setattr__(self, "first_component_id", first_id)
        object.__setattr__(self, "second_component_id", second_id)
        object.__setattr__(self, "clearance", clearance)
        object.__setattr__(self, "required_clearance", required)
        object.__setattr__(self, "first_num_nodes", first_count)
        object.__setattr__(self, "second_num_nodes", second_count)


@dataclass(frozen=True)
class MultiComponentBoundaryAdapter:
    """Validated component-local Kress views of an ordered boundary."""

    boundary: OrderedBoundary2D
    component_adapters: tuple[PeriodicCurveAdapter, ...]
    component_pair_reports: tuple[ComponentPairReport, ...]
    minimum_intercomponent_clearance: float | None
    geometry_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.boundary, OrderedBoundary2D):
            raise TypeError("boundary must be an OrderedBoundary2D object.")
        adapters = tuple(self.component_adapters)
        if len(adapters) != self.boundary.num_components or not all(
            isinstance(adapter, PeriodicCurveAdapter) for adapter in adapters
        ):
            raise ValueError(
                "component_adapters must contain one PeriodicCurveAdapter per component."
            )
        if any(
            adapter.curve is not component
            for adapter, component in zip(adapters, self.boundary.components)
        ):
            raise ValueError(
                "component_adapters must preserve the boundary component order."
            )
        reports = tuple(self.component_pair_reports)
        expected_reports = self.boundary.num_components * (
            self.boundary.num_components - 1
        ) // 2
        if len(reports) != expected_reports or not all(
            isinstance(report, ComponentPairReport) for report in reports
        ):
            raise ValueError(
                "component_pair_reports must contain one report per unordered pair."
            )
        if reports:
            minimum = _positive_finite(
                self.minimum_intercomponent_clearance,
                name="minimum_intercomponent_clearance",
            )
            expected_minimum = min(report.clearance for report in reports)
            if minimum != expected_minimum:
                raise ValueError(
                    "minimum_intercomponent_clearance must equal the minimum pair clearance."
                )
        elif self.minimum_intercomponent_clearance is not None:
            raise ValueError(
                "minimum_intercomponent_clearance must be None for one component."
            )
        else:
            minimum = None
        geometry_id = str(self.geometry_id).strip()
        if not geometry_id:
            raise ValueError("geometry_id must be a non-empty string.")
        object.__setattr__(self, "component_adapters", adapters)
        object.__setattr__(self, "component_pair_reports", reports)
        object.__setattr__(self, "minimum_intercomponent_clearance", minimum)
        object.__setattr__(self, "geometry_id", geometry_id)

    @property
    def num_components(self) -> int:
        return self.boundary.num_components

    @property
    def num_nodes(self) -> int:
        return self.boundary.num_nodes

    @property
    def component_slices(self) -> tuple[slice, ...]:
        return self.boundary.component_slices


def adapt_multicomponent_boundary(
    boundary: OrderedBoundary2D,
    *,
    config: MultiComponentAssemblyConfig | None = None,
) -> MultiComponentBoundaryAdapter:
    """Validate component-local grids, topology, and separation.

    A one-component ``OrderedBoundary2D`` is accepted as a useful compatibility
    case, but this function never accepts a bare ``PeriodicCurve2D``.  Calling
    code must make the topology-preserving conversion explicit.
    """

    settings = MultiComponentAssemblyConfig() if config is None else config
    if not isinstance(settings, MultiComponentAssemblyConfig):
        raise TypeError("config must be a MultiComponentAssemblyConfig object.")
    if not isinstance(boundary, OrderedBoundary2D):
        raise TypeError("boundary must be an ordered_boundary.OrderedBoundary2D object.")
    adapters = tuple(
        _component_adapter(
            component,
            context=f"boundary component at index {component_index}",
        )
        for component_index, component in enumerate(boundary.components)
    )
    reports: list[ComponentPairReport] = []
    minimum_clearance: float | None = None
    for first_index, first in enumerate(boundary.components):
        for second_index in range(first_index + 1, boundary.num_components):
            second = boundary.components[second_index]
            report = _validate_component_pair(first, second, settings)
            reports.append(report)
            minimum_clearance = (
                report.clearance
                if minimum_clearance is None
                else min(minimum_clearance, report.clearance)
            )
    digest = hashlib.sha256()
    for adapter in adapters:
        digest.update(adapter.geometry_id.encode("utf-8"))
        digest.update(b"\0")
    geometry_id = f"ordered-boundary:{digest.hexdigest()[:16]}"
    return MultiComponentBoundaryAdapter(
        boundary=boundary,
        component_adapters=adapters,
        component_pair_reports=tuple(reports),
        minimum_intercomponent_clearance=minimum_clearance,
        geometry_id=geometry_id,
    )


@dataclass(frozen=True)
class ExteriorCrossBlocks:
    """Weighted exterior-only operators for one target/source component pair."""

    target_component_id: str
    source_component_id: str
    k_exterior: complex
    v: np.ndarray
    k: np.ndarray
    kp: np.ndarray
    t: np.ndarray
    minimum_pair_distance: float
    build_seconds: float

    def __post_init__(self) -> None:
        target_id = str(self.target_component_id).strip()
        source_id = str(self.source_component_id).strip()
        if not target_id or not source_id:
            raise ValueError("component identifiers must be non-empty strings.")
        if target_id == source_id:
            raise ValueError("cross blocks require distinct component identifiers.")
        wave = validate_wavenumber(self.k_exterior, name="k_exterior")
        arrays: dict[str, np.ndarray] = {}
        expected_shape: tuple[int, int] | None = None
        for name in ("v", "k", "kp", "t"):
            values = _finite_readonly_array(
                getattr(self, name),
                dtype=np.complex128,
                name=name,
                ndim=2,
            )
            if values.shape[0] == 0 or values.shape[1] == 0:
                raise ValueError(f"{name} must have a non-empty matrix shape.")
            if expected_shape is None:
                expected_shape = values.shape
            elif values.shape != expected_shape:
                raise ValueError("v, k, kp, and t must have the same shape.")
            arrays[name] = values
        distance = _positive_finite(
            self.minimum_pair_distance,
            name="minimum_pair_distance",
        )
        elapsed = _nonnegative_finite(self.build_seconds, name="build_seconds")
        object.__setattr__(self, "target_component_id", target_id)
        object.__setattr__(self, "source_component_id", source_id)
        object.__setattr__(self, "k_exterior", wave)
        for name, values in arrays.items():
            object.__setattr__(self, name, values)
        object.__setattr__(self, "minimum_pair_distance", distance)
        object.__setattr__(self, "build_seconds", elapsed)


def _exterior_cross_blocks_from_adapters(
    target: PeriodicCurveAdapter,
    source: PeriodicCurveAdapter,
    wave: complex,
) -> ExteriorCrossBlocks:
    started = perf_counter()
    geometry = pair_geometry(
        target.points,
        target.normals,
        source.points,
        source.normals,
    )
    radius = geometry.distance
    if np.any(radius <= 0.0):
        raise MultiComponentTopologyError(
            "cross-component kernel evaluation requires positive distances."
        )
    argument = wave * radius
    green = 0.25j * hankel1(0, argument)
    radial_first = -0.25j * wave * hankel1(1, argument) / radius
    radial_anisotropy = 0.25j * wave**2 * hankel1(2, argument)
    projection_product = (
        geometry.displacement_dot_target_normal
        * geometry.displacement_dot_source_normal
        / radius**2
    )
    weights = source.arc_length_weights[None, :]
    arrays = (
        green * weights,
        -radial_first * geometry.displacement_dot_source_normal * weights,
        radial_first * geometry.displacement_dot_target_normal * weights,
        (
            -radial_first * geometry.normal_dot
            - radial_anisotropy * projection_product
        )
        * weights,
    )
    if not all(np.all(np.isfinite(values)) for values in arrays):
        raise FloatingPointError("exterior cross-component kernels produced non-finite values.")
    return ExteriorCrossBlocks(
        target_component_id=target.curve.component_id,
        source_component_id=source.curve.component_id,
        k_exterior=wave,
        v=_readonly(arrays[0], dtype=np.complex128),
        k=_readonly(arrays[1], dtype=np.complex128),
        kp=_readonly(arrays[2], dtype=np.complex128),
        t=_readonly(arrays[3], dtype=np.complex128),
        minimum_pair_distance=float(np.min(radius)),
        build_seconds=float(perf_counter() - started),
    )


def build_exterior_cross_blocks(
    target: PeriodicCurve2D,
    source: PeriodicCurve2D,
    k_exterior: complex,
    *,
    config: MultiComponentAssemblyConfig | None = None,
) -> ExteriorCrossBlocks:
    """Build one validated smooth exterior target/source operator family.

    The same topology and clearance policy used by the global assembler is
    applied here, so this lower-level public function cannot bypass the
    ordinary-quadrature separation guard.
    """

    if not isinstance(target, PeriodicCurve2D) or not isinstance(source, PeriodicCurve2D):
        raise TypeError("target and source must be PeriodicCurve2D objects.")
    if target is source:
        raise ValueError("self interactions require build_muller_difference_blocks.")
    settings = MultiComponentAssemblyConfig() if config is None else config
    if not isinstance(settings, MultiComponentAssemblyConfig):
        raise TypeError("config must be a MultiComponentAssemblyConfig object.")
    target_adapter = _component_adapter(target, context="target component")
    source_adapter = _component_adapter(source, context="source component")
    _validate_component_pair(target, source, settings)
    wave = validate_wavenumber(k_exterior, name="k_exterior")
    return _exterior_cross_blocks_from_adapters(
        target_adapter,
        source_adapter,
        wave,
    )


@dataclass(frozen=True)
class MultiComponentMullerBlocks:
    """Global weighted Muller operators with component-correct interiors."""

    geometry: OrderedBoundary2D
    geometry_adapter: MultiComponentBoundaryAdapter
    config: MultiComponentAssemblyConfig
    k_exterior: complex
    k_interior: complex
    delta_v: np.ndarray
    delta_k: np.ndarray
    delta_kp: np.ndarray
    delta_t: np.ndarray
    self_blocks: tuple[MullerDifferenceBlocks, ...]
    diagnostics: Mapping[str, object]
    build_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.geometry, OrderedBoundary2D):
            raise TypeError("geometry must be an OrderedBoundary2D object.")
        if not isinstance(self.geometry_adapter, MultiComponentBoundaryAdapter):
            raise TypeError(
                "geometry_adapter must be a MultiComponentBoundaryAdapter object."
            )
        if self.geometry_adapter.boundary is not self.geometry:
            raise ValueError("geometry_adapter must describe geometry.")
        if not isinstance(self.config, MultiComponentAssemblyConfig):
            raise TypeError("config must be a MultiComponentAssemblyConfig object.")
        exterior = validate_wavenumber(self.k_exterior, name="k_exterior")
        interior = validate_wavenumber(self.k_interior, name="k_interior")
        expected = (self.geometry.num_nodes, self.geometry.num_nodes)
        arrays = {
            name: _finite_readonly_array(
                getattr(self, name),
                dtype=np.complex128,
                name=name,
                shape=expected,
            )
            for name in ("delta_v", "delta_k", "delta_kp", "delta_t")
        }
        self_blocks = tuple(self.self_blocks)
        if len(self_blocks) != self.geometry.num_components or not all(
            isinstance(block, MullerDifferenceBlocks) for block in self_blocks
        ):
            raise ValueError(
                "self_blocks must contain one MullerDifferenceBlocks per component."
            )
        if any(
            block.geometry is not component
            for block, component in zip(self_blocks, self.geometry.components)
        ):
            raise ValueError("self_blocks must preserve the geometry component order.")
        diagnostics = _frozen_mapping(self.diagnostics, name="diagnostics")
        elapsed = _nonnegative_finite(self.build_seconds, name="build_seconds")
        object.__setattr__(self, "k_exterior", exterior)
        object.__setattr__(self, "k_interior", interior)
        for name, values in arrays.items():
            object.__setattr__(self, name, values)
        object.__setattr__(self, "self_blocks", self_blocks)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "build_seconds", elapsed)

    @property
    def num_nodes(self) -> int:
        return self.geometry.num_nodes


def build_multicomponent_muller_blocks(
    boundary: OrderedBoundary2D,
    k_exterior: complex,
    k_interior: complex,
    *,
    config: MultiComponentAssemblyConfig | None = None,
) -> MultiComponentMullerBlocks:
    """Assemble global ``X_e - blockdiag(X_i)`` weighted operators."""

    started = perf_counter()
    settings = MultiComponentAssemblyConfig() if config is None else config
    if not isinstance(settings, MultiComponentAssemblyConfig):
        raise TypeError("config must be a MultiComponentAssemblyConfig object.")
    adapter = adapt_multicomponent_boundary(boundary, config=settings)
    exterior = validate_wavenumber(k_exterior, name="k_exterior")
    interior = validate_wavenumber(k_interior, name="k_interior")
    names = ("V", "K", "Kp", "T")
    matrices = {
        name: np.zeros((boundary.num_nodes, boundary.num_nodes), dtype=np.complex128)
        for name in names
    }
    self_blocks: list[MullerDifferenceBlocks] = []
    self_seconds = 0.0
    cross_seconds = 0.0
    interaction_records: list[Mapping[str, object]] = []

    for component_index, (component, component_slice) in enumerate(
        zip(boundary.components, boundary.component_slices)
    ):
        self_block = build_muller_difference_blocks(
            component,
            exterior,
            interior,
            config=settings.self_assembly,
        )
        self_blocks.append(self_block)
        self_seconds += self_block.build_seconds
        for name, field_name in (
            ("V", "delta_v"),
            ("K", "delta_k"),
            ("Kp", "delta_kp"),
            ("T", "delta_t"),
        ):
            matrices[name][component_slice, component_slice] = getattr(
                self_block,
                field_name,
            )
        interaction_records.append(
            MappingProxyType(
                {
                    "target_component": component.component_id,
                    "source_component": component.component_id,
                    "target_index": component_index,
                    "source_index": component_index,
                    "kind": "self_kress_exterior_minus_interior",
                    "shape": (component.num_nodes, component.num_nodes),
                    "build_seconds": self_block.build_seconds,
                }
            )
        )

    for target_index, (target_adapter, target_slice) in enumerate(
        zip(adapter.component_adapters, boundary.component_slices)
    ):
        for source_index, (source_adapter, source_slice) in enumerate(
            zip(adapter.component_adapters, boundary.component_slices)
        ):
            if target_index == source_index:
                continue
            cross = _exterior_cross_blocks_from_adapters(
                target_adapter,
                source_adapter,
                exterior,
            )
            cross_seconds += cross.build_seconds
            for name, values in (
                ("V", cross.v),
                ("K", cross.k),
                ("Kp", cross.kp),
                ("T", cross.t),
            ):
                matrices[name][target_slice, source_slice] = values
            interaction_records.append(
                MappingProxyType(
                    {
                        "target_component": cross.target_component_id,
                        "source_component": cross.source_component_id,
                        "target_index": target_index,
                        "source_index": source_index,
                        "kind": "cross_exterior_trapezoid",
                        "shape": cross.v.shape,
                        "minimum_node_distance": cross.minimum_pair_distance,
                        "build_seconds": cross.build_seconds,
                    }
                )
            )

    for name, matrix in matrices.items():
        if not np.all(np.isfinite(matrix)):
            raise FloatingPointError(f"multi-component Delta {name} is non-finite.")
        matrix.setflags(write=False)
    block_norms = MappingProxyType(
        {name: float(np.linalg.norm(matrix, ord=np.inf)) for name, matrix in matrices.items()}
    )
    global_block_bytes = int(sum(matrix.nbytes for matrix in matrices.values()))
    retained_self_arrays: dict[int, np.ndarray] = {}
    for self_block in self_blocks:
        arrays = (
            self_block.delta_v,
            self_block.delta_k,
            self_block.delta_kp,
            self_block.delta_t,
            *self_block.diagonal_log_coefficients.values(),
            *self_block.diagonal_smooth_remainders.values(),
        )
        retained_self_arrays.update((id(array), array) for array in arrays)
    self_block_bytes = int(
        sum(array.nbytes for array in retained_self_arrays.values())
    )
    elapsed = float(perf_counter() - started)
    diagnostics = MappingProxyType(
        {
            "geometry_id": adapter.geometry_id,
            "num_components": boundary.num_components,
            "num_nodes": boundary.num_nodes,
            "component_ids": boundary.component_ids,
            "component_offsets": tuple(int(value) for value in boundary.component_offsets),
            "component_node_counts": tuple(
                component.num_nodes for component in boundary.components
            ),
            "component_orientations": MappingProxyType(
                {
                    component.component_id: component.orientation
                    for component in boundary.components
                }
            ),
            "normal_convention": "outward_from_each_inclusion",
            "topology": "disjoint_non_nested_components",
            "minimum_intercomponent_clearance": adapter.minimum_intercomponent_clearance,
            "pair_reports": adapter.component_pair_reports,
            "interactions": tuple(interaction_records),
            "operator_formula": "X_exterior_global - blockdiag(X_interior_components)",
            "self_quadrature": "kress_exterior_minus_interior",
            "cross_quadrature": "ordinary_exterior_trapezoid",
            "source_jacobian_included": True,
            "unknowns_are_weighted": False,
            "zero_contrast_self_shortcut": exterior == interior,
            "block_infinity_norms": block_norms,
            "retained_global_block_bytes": global_block_bytes,
            "retained_self_block_bytes": self_block_bytes,
            "retained_block_bytes": global_block_bytes + self_block_bytes,
            "timings_seconds": MappingProxyType(
                {
                    "self_components": float(self_seconds),
                    "cross_components": float(cross_seconds),
                    "total": elapsed,
                }
            ),
        }
    )
    return MultiComponentMullerBlocks(
        geometry=boundary,
        geometry_adapter=adapter,
        config=settings,
        k_exterior=exterior,
        k_interior=interior,
        delta_v=matrices["V"],
        delta_k=matrices["K"],
        delta_kp=matrices["Kp"],
        delta_t=matrices["T"],
        self_blocks=tuple(self_blocks),
        diagnostics=diagnostics,
        build_seconds=elapsed,
    )


@dataclass(frozen=True)
class MultiComponentKressTMzFrequencySystem:
    """One global ``2N x 2N`` Muller system over explicit component slices."""

    geometry: OrderedBoundary2D
    angular_frequency: float | None
    k_exterior: complex
    k_interior: complex
    assembly_config: MultiComponentAssemblyConfig
    difference_blocks: MultiComponentMullerBlocks
    system_matrix: np.ndarray
    condition_number: float
    assembly_seconds: float
    diagnostics: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.geometry, OrderedBoundary2D):
            raise TypeError("geometry must be an OrderedBoundary2D object.")
        frequency = (
            None
            if self.angular_frequency is None
            else _positive_finite(
                self.angular_frequency,
                name="angular_frequency",
            )
        )
        exterior = validate_wavenumber(self.k_exterior, name="k_exterior")
        interior = validate_wavenumber(self.k_interior, name="k_interior")
        if not isinstance(self.assembly_config, MultiComponentAssemblyConfig):
            raise TypeError(
                "assembly_config must be a MultiComponentAssemblyConfig object."
            )
        if not isinstance(self.difference_blocks, MultiComponentMullerBlocks):
            raise TypeError(
                "difference_blocks must be a MultiComponentMullerBlocks object."
            )
        if self.difference_blocks.geometry is not self.geometry:
            raise ValueError("difference_blocks must describe geometry.")
        if (
            self.difference_blocks.k_exterior != exterior
            or self.difference_blocks.k_interior != interior
        ):
            raise ValueError(
                "system and difference-block wavenumbers must be identical."
            )
        expected = (2 * self.geometry.num_nodes, 2 * self.geometry.num_nodes)
        matrix = _finite_readonly_array(
            self.system_matrix,
            dtype=np.complex128,
            name="system_matrix",
            shape=expected,
        )
        if isinstance(self.condition_number, (bool, np.bool_)):
            raise TypeError("condition_number must be a real number, not bool.")
        condition = float(self.condition_number)
        if condition < 0.0 or np.isneginf(condition):
            raise ValueError("condition_number must be non-negative or NaN.")
        elapsed = _nonnegative_finite(
            self.assembly_seconds,
            name="assembly_seconds",
        )
        diagnostics = _frozen_mapping(self.diagnostics, name="diagnostics")
        object.__setattr__(self, "angular_frequency", frequency)
        object.__setattr__(self, "k_exterior", exterior)
        object.__setattr__(self, "k_interior", interior)
        object.__setattr__(self, "system_matrix", matrix)
        object.__setattr__(self, "condition_number", condition)
        object.__setattr__(self, "assembly_seconds", elapsed)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def num_nodes(self) -> int:
        return self.geometry.num_nodes

    @property
    def a11(self) -> np.ndarray:
        return self.system_matrix[: self.num_nodes, : self.num_nodes]

    @property
    def a12(self) -> np.ndarray:
        return self.system_matrix[: self.num_nodes, self.num_nodes :]

    @property
    def a21(self) -> np.ndarray:
        return self.system_matrix[self.num_nodes :, : self.num_nodes]

    @property
    def a22(self) -> np.ndarray:
        return self.system_matrix[self.num_nodes :, self.num_nodes :]


def build_multicomponent_muller_system(
    boundary: OrderedBoundary2D,
    k_exterior: complex,
    k_interior: complex,
    *,
    angular_frequency: float | None = None,
    config: MultiComponentAssemblyConfig | None = None,
    compute_condition_number: bool = False,
) -> MultiComponentKressTMzFrequencySystem:
    """Compose ``[[I-dK,dV],[-dT,I+dKp]]`` on all boundary nodes."""

    started = perf_counter()
    if not isinstance(compute_condition_number, (bool, np.bool_)):
        raise TypeError("compute_condition_number must be boolean.")
    frequency = (
        None
        if angular_frequency is None
        else _positive_finite(angular_frequency, name="angular_frequency")
    )
    blocks = build_multicomponent_muller_blocks(
        boundary,
        k_exterior,
        k_interior,
        config=config,
    )
    count = blocks.num_nodes
    matrix = np.empty((2 * count, 2 * count), dtype=np.complex128)
    matrix[:count, :count] = -blocks.delta_k
    matrix[:count, count:] = blocks.delta_v
    matrix[count:, :count] = -blocks.delta_t
    matrix[count:, count:] = blocks.delta_kp
    diagonal = np.arange(count)
    matrix[diagonal, diagonal] += 1.0
    matrix[count + diagonal, count + diagonal] += 1.0
    if not np.all(np.isfinite(matrix)):
        raise FloatingPointError("multi-component Muller system is non-finite.")
    matrix.setflags(write=False)
    condition = (
        float(np.linalg.cond(matrix)) if compute_condition_number else float("nan")
    )
    elapsed = float(perf_counter() - started)
    diagnostics = MappingProxyType(
        {
            "geometry_id": blocks.geometry_adapter.geometry_id,
            "num_components": boundary.num_components,
            "num_nodes": count,
            "component_ids": boundary.component_ids,
            "component_offsets": tuple(int(value) for value in boundary.component_offsets),
            "component_orientations": MappingProxyType(
                {
                    component.component_id: component.orientation
                    for component in boundary.components
                }
            ),
            "normal_convention": "outward_from_each_inclusion",
            "topology": "disjoint_non_nested_components",
            "unknown_order": ("u_D_all_components", "u_N_all_components"),
            "system_formula": "[[I-DeltaK, DeltaV], [-DeltaT, I+DeltaKp]]",
            "jump_terms_added": "identity_once_per_node_in_A11_and_A22",
            "solve_form": "direct_unsquared",
            "condition_number_computed": bool(compute_condition_number),
            "condition_number_kind": "raw_mixed_unit_nodal_2_norm",
            "conventions": PROJECT_MULLER_CONVENTION.as_mapping(),
        }
    )
    return MultiComponentKressTMzFrequencySystem(
        geometry=boundary,
        angular_frequency=frequency,
        k_exterior=blocks.k_exterior,
        k_interior=blocks.k_interior,
        assembly_config=blocks.config,
        difference_blocks=blocks,
        system_matrix=matrix,
        condition_number=condition,
        assembly_seconds=elapsed,
        diagnostics=diagnostics,
    )


def build_multicomponent_kress_tmz_frequency_system(
    boundary: OrderedBoundary2D,
    angular_frequency: float,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    config: MultiComponentAssemblyConfig | None = None,
    compute_condition_number: bool = False,
) -> MultiComponentKressTMzFrequencySystem:
    """Build a same-interior-material, nonmagnetic TMz frequency system."""

    _validate_supported_materials(exterior, interior)
    omega = _positive_finite(angular_frequency, name="angular_frequency")
    epsilon_zero = _positive_finite(eps0, name="eps0")
    mu_zero = _positive_finite(mu0, name="mu0")
    return build_multicomponent_muller_system(
        boundary,
        complex(exterior.wavenumber(omega, epsilon_zero, mu_zero)),
        complex(interior.wavenumber(omega, epsilon_zero, mu_zero)),
        angular_frequency=omega,
        config=config,
        compute_condition_number=compute_condition_number,
    )


def multicomponent_incident_trace_on_boundary(
    boundary: OrderedBoundary2D,
    source_points,
    k_exterior: complex,
    source_strength=1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate unweighted line-source traces on all component nodes."""

    if not isinstance(boundary, OrderedBoundary2D):
        raise TypeError("boundary must be an OrderedBoundary2D object.")
    sources = _real_points(source_points, name="source_points")
    strengths = _source_strengths(source_strength, sources.shape[0])
    wave = validate_wavenumber(k_exterior, name="k_exterior")
    displacement = boundary.points[None, :, :] - sources[:, None, :]
    distance = np.linalg.norm(displacement, axis=-1)
    if np.any(distance <= 0.0):
        raise MultiComponentFieldPointError(
            "source_points must not lie on a boundary node."
        )
    projection = np.einsum("snd,nd->sn", displacement, boundary.normals) / distance
    dirichlet = strengths[:, None] * 0.25j * hankel1(0, wave * distance)
    neumann = (
        -strengths[:, None]
        * 0.25j
        * wave
        * hankel1(1, wave * distance)
        * projection
    )
    return (
        _readonly(dirichlet, dtype=np.complex128),
        _readonly(neumann, dtype=np.complex128),
    )


@dataclass(frozen=True)
class MultiComponentExteriorRepresentationResult:
    single_layer: np.ndarray
    double_layer: np.ndarray
    scattered: np.ndarray
    minimum_receiver_distance: float
    evaluation_seconds: float

    def __post_init__(self) -> None:
        arrays: dict[str, np.ndarray] = {}
        expected_shape: tuple[int, int] | None = None
        for name in ("single_layer", "double_layer", "scattered"):
            values = _finite_readonly_array(
                getattr(self, name),
                dtype=np.complex128,
                name=name,
                ndim=2,
            )
            if values.shape[0] == 0 or values.shape[1] == 0:
                raise ValueError(f"{name} must have a non-empty matrix shape.")
            if expected_shape is None:
                expected_shape = values.shape
            elif values.shape != expected_shape:
                raise ValueError(
                    "single_layer, double_layer, and scattered must have the same shape."
                )
            arrays[name] = values
        distance = _positive_finite(
            self.minimum_receiver_distance,
            name="minimum_receiver_distance",
        )
        elapsed = _nonnegative_finite(
            self.evaluation_seconds,
            name="evaluation_seconds",
        )
        for name, values in arrays.items():
            object.__setattr__(self, name, values)
        object.__setattr__(self, "minimum_receiver_distance", distance)
        object.__setattr__(self, "evaluation_seconds", elapsed)


@dataclass(frozen=True)
class MultiComponentExteriorReceiverOperator:
    """Weighted global exterior measurement map ``C=[D,-S]``."""

    geometry: OrderedBoundary2D
    receiver_points: np.ndarray
    k_exterior: complex
    single_layer_rows: np.ndarray
    double_layer_rows: np.ndarray
    build_seconds: float
    state_rows: np.ndarray = field(init=False)
    minimum_receiver_distance: float = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.geometry, OrderedBoundary2D):
            raise TypeError("geometry must be an OrderedBoundary2D object.")
        receivers = _real_points(self.receiver_points, name="receiver_points")
        minimum_distance = _validate_exterior_points(
            receivers,
            self.geometry,
            name="receiver_points",
            minimum_clearance=0.0,
        )
        expected = (receivers.shape[0], self.geometry.num_nodes)
        single = np.asarray(self.single_layer_rows, dtype=np.complex128)
        double = np.asarray(self.double_layer_rows, dtype=np.complex128)
        if single.shape != expected or double.shape != expected:
            raise ValueError(f"receiver rows must both have shape {expected}.")
        if not np.all(np.isfinite(single)) or not np.all(np.isfinite(double)):
            raise ValueError("receiver rows must contain only finite values.")
        wave = validate_wavenumber(self.k_exterior, name="k_exterior")
        elapsed = _nonnegative_finite(self.build_seconds, name="build_seconds")
        readonly_single = _readonly(single, dtype=np.complex128)
        readonly_double = _readonly(double, dtype=np.complex128)
        object.__setattr__(self, "receiver_points", _readonly(receivers, dtype=np.float64))
        object.__setattr__(self, "k_exterior", wave)
        object.__setattr__(self, "single_layer_rows", readonly_single)
        object.__setattr__(self, "double_layer_rows", readonly_double)
        object.__setattr__(
            self,
            "state_rows",
            _readonly(
                np.concatenate((readonly_double, -readonly_single), axis=1),
                dtype=np.complex128,
            ),
        )
        object.__setattr__(self, "minimum_receiver_distance", minimum_distance)
        object.__setattr__(self, "build_seconds", elapsed)

    @property
    def num_nodes(self) -> int:
        return self.geometry.num_nodes

    @property
    def num_receivers(self) -> int:
        return int(self.receiver_points.shape[0])

    def apply_state(self, state) -> np.ndarray:
        values = np.asarray(state, dtype=np.complex128)
        if values.ndim == 1:
            values = values[:, None]
        expected_rows = 2 * self.num_nodes
        if values.ndim != 2 or values.shape[0] != expected_rows or values.shape[1] == 0:
            raise ValueError(f"state must have shape ({expected_rows}, num_rhs).")
        if not np.all(np.isfinite(values)):
            raise ValueError("state must contain only finite values.")
        return _readonly((self.state_rows @ values).T, dtype=np.complex128)

    def apply_adjoint(self, receiver_dual) -> np.ndarray:
        values = np.asarray(receiver_dual, dtype=np.complex128)
        if values.ndim == 1:
            values = values[None, :]
        if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] != self.num_receivers:
            raise ValueError(
                "receiver_dual must have shape (num_rhs, num_receivers)."
            )
        if not np.all(np.isfinite(values)):
            raise ValueError("receiver_dual must contain only finite values.")
        return _readonly(self.state_rows.conj().T @ values.T, dtype=np.complex128)

    def evaluate(
        self,
        dirichlet_trace,
        neumann_trace,
    ) -> MultiComponentExteriorRepresentationResult:
        started = perf_counter()
        dirichlet = _trace_matrix(
            dirichlet_trace,
            self.num_nodes,
            name="dirichlet_trace",
        )
        neumann = _trace_matrix(
            neumann_trace,
            self.num_nodes,
            name="neumann_trace",
        )
        if dirichlet.shape != neumann.shape:
            raise ValueError("dirichlet_trace and neumann_trace must have the same shape.")
        single = (self.single_layer_rows @ neumann.T).T
        double = (self.double_layer_rows @ dirichlet.T).T
        state = np.concatenate((dirichlet, neumann), axis=1).T
        return MultiComponentExteriorRepresentationResult(
            single_layer=_readonly(single, dtype=np.complex128),
            double_layer=_readonly(double, dtype=np.complex128),
            scattered=self.apply_state(state),
            minimum_receiver_distance=self.minimum_receiver_distance,
            evaluation_seconds=float(perf_counter() - started),
        )


def build_multicomponent_exterior_receiver_operator(
    boundary: OrderedBoundary2D,
    receiver_points,
    k_exterior: complex,
    *,
    minimum_clearance: float = 0.0,
) -> MultiComponentExteriorReceiverOperator:
    """Build global exterior ``C=[D,-S]`` rows without losing topology."""

    started = perf_counter()
    if not isinstance(boundary, OrderedBoundary2D):
        raise TypeError("boundary must be an OrderedBoundary2D object.")
    receivers = _real_points(receiver_points, name="receiver_points")
    clearance = _nonnegative_finite(minimum_clearance, name="minimum_clearance")
    _validate_exterior_points(
        receivers,
        boundary,
        name="receiver_points",
        minimum_clearance=clearance,
    )
    wave = validate_wavenumber(k_exterior, name="k_exterior")
    single, double = _receiver_layer_rows(boundary, receivers, wave)
    operator = MultiComponentExteriorReceiverOperator(
        geometry=boundary,
        receiver_points=receivers,
        k_exterior=wave,
        single_layer_rows=single,
        double_layer_rows=double,
        build_seconds=float(perf_counter() - started),
    )
    return operator


def _receiver_layer_rows(boundary, receivers, wave):
    """Shared smooth Helmholtz layer quadrature for either material side."""
    displacement = receivers[:, None, :] - boundary.points[None, :, :]
    distance = np.linalg.norm(displacement, axis=-1)
    projection = np.einsum("rnd,nd->rn", displacement, boundary.normals) / distance
    green = 0.25j * hankel1(0, wave * distance)
    green_normal = 0.25j * wave * hankel1(1, wave * distance) * projection
    return (green * boundary.arc_length_weights[None, :],
            green_normal * boundary.arc_length_weights[None, :])


def evaluate_multicomponent_interior_total_field(
    boundary: OrderedBoundary2D, points, k_interior: complex,
    dirichlet_total, neumann_total, *, minimum_clearance: float = 0.0,
) -> np.ndarray:
    """Evaluate ``S_i q - D_i u`` using only the containing component.

    The traces use the normal pointing out of the inclusion. No incident
    field is added to this interior Green representation. Points in the
    exterior, on a boundary, or in overlapping interiors are rejected.
    Ordinary smooth quadrature requires callers to keep a resolved clearance.
    """
    receivers = _real_points(points, name="points")
    wave = validate_wavenumber(k_interior, name="k_interior")
    clearance = _nonnegative_finite(minimum_clearance, name="minimum_clearance")
    u = _trace_matrix(dirichlet_total, boundary.num_nodes, name="dirichlet_total")
    q = _trace_matrix(neumann_total, boundary.num_nodes, name="neumann_total")
    if u.shape != q.shape:
        raise ValueError("Dirichlet and Neumann trace batches must match.")
    result = np.zeros((u.shape[0], len(receivers)), dtype=np.complex128)
    membership = np.zeros(len(receivers), dtype=int)
    offset = 0
    for component in boundary.components:
        selected = _inside_closed_polygon(receivers, component.points)
        membership += selected
        if np.any(selected):
            local = receivers[selected]
            if _minimum_curve_distance(local, component) <= clearance:
                raise MultiComponentFieldPointError("Interior points violate boundary clearance.")
            single, double = _receiver_layer_rows(component, local, wave)
            section = slice(offset, offset + component.num_nodes)
            result[:, selected] = q[:, section] @ single.T - u[:, section] @ double.T
        offset += component.num_nodes
    if np.any(membership != 1):
        raise MultiComponentFieldPointError("Each interior point must belong to exactly one component.")
    return result


@dataclass(frozen=True)
class MultiComponentKressSolveConfig:
    """Direct-solve and off-surface controls for the opt-in pipeline.

    ``minimum_field_point_clearance_in_weights`` controls only sources and
    receivers.  Inter-component clearance remains an assembly setting.
    """

    assembly: MultiComponentAssemblyConfig = field(
        default_factory=MultiComponentAssemblyConfig
    )
    compute_condition_number: bool = False
    minimum_field_point_clearance_in_weights: float = 2.0

    def __post_init__(self) -> None:
        if not isinstance(self.assembly, MultiComponentAssemblyConfig):
            raise TypeError("assembly must be a MultiComponentAssemblyConfig object.")
        if not isinstance(self.compute_condition_number, (bool, np.bool_)):
            raise TypeError("compute_condition_number must be boolean.")
        object.__setattr__(
            self,
            "compute_condition_number",
            bool(self.compute_condition_number),
        )
        object.__setattr__(
            self,
            "minimum_field_point_clearance_in_weights",
            _nonnegative_finite(
                self.minimum_field_point_clearance_in_weights,
                name="minimum_field_point_clearance_in_weights",
            ),
        )


@dataclass(frozen=True)
class MultiComponentKressForwardResult:
    """Auditable batched total-field solve for a disconnected boundary."""

    system: MultiComponentKressTMzFrequencySystem
    solve_config: MultiComponentKressSolveConfig
    exterior_material: Material
    interior_material: Material
    eps0: float
    mu0: float
    receiver_operator: MultiComponentExteriorReceiverOperator
    source_points: np.ndarray
    receiver_points: np.ndarray
    source_strengths: np.ndarray
    right_hand_side: np.ndarray
    solution: np.ndarray
    dirichlet_incident: np.ndarray
    neumann_incident: np.ndarray
    dirichlet_total: np.ndarray
    neumann_total: np.ndarray
    incident_receiver: np.ndarray
    single_receiver: np.ndarray
    double_receiver: np.ndarray
    scattered_receiver: np.ndarray
    total_receiver: np.ndarray
    linear_system_relative_residual: float
    per_source_relative_residual: np.ndarray
    incident_representation_leak: float
    solve_seconds: float
    receiver_evaluation_seconds: float
    total_seconds: float
    diagnostics: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.system, MultiComponentKressTMzFrequencySystem):
            raise TypeError(
                "system must be a MultiComponentKressTMzFrequencySystem object."
            )
        if not isinstance(self.solve_config, MultiComponentKressSolveConfig):
            raise TypeError("solve_config must be a MultiComponentKressSolveConfig object.")
        if not isinstance(self.exterior_material, Material) or not isinstance(
            self.interior_material,
            Material,
        ):
            raise TypeError(
                "exterior_material and interior_material must be Material objects."
            )
        epsilon_zero = _positive_finite(self.eps0, name="eps0")
        mu_zero = _positive_finite(self.mu0, name="mu0")
        if not isinstance(
            self.receiver_operator,
            MultiComponentExteriorReceiverOperator,
        ):
            raise TypeError(
                "receiver_operator must be a MultiComponentExteriorReceiverOperator object."
            )
        if self.receiver_operator.geometry is not self.system.geometry:
            raise ValueError("receiver_operator and system must use the same geometry.")

        sources = _real_points(self.source_points, name="source_points")
        receivers = _real_points(self.receiver_points, name="receiver_points")
        if not np.array_equal(receivers, self.receiver_operator.receiver_points):
            raise ValueError(
                "receiver_points must equal receiver_operator.receiver_points."
            )
        source_count = int(sources.shape[0])
        receiver_count = int(receivers.shape[0])
        node_count = self.system.num_nodes
        strengths = _source_strengths(self.source_strengths, source_count)

        array_shapes = {
            "right_hand_side": (2 * node_count, source_count),
            "solution": (2 * node_count, source_count),
            "dirichlet_incident": (source_count, node_count),
            "neumann_incident": (source_count, node_count),
            "dirichlet_total": (source_count, node_count),
            "neumann_total": (source_count, node_count),
            "incident_receiver": (source_count, receiver_count),
            "single_receiver": (source_count, receiver_count),
            "double_receiver": (source_count, receiver_count),
            "scattered_receiver": (source_count, receiver_count),
            "total_receiver": (source_count, receiver_count),
        }
        arrays = {
            name: _finite_readonly_array(
                getattr(self, name),
                dtype=np.complex128,
                name=name,
                shape=shape,
            )
            for name, shape in array_shapes.items()
        }
        aggregate_residual = _nonnegative_finite(
            self.linear_system_relative_residual,
            name="linear_system_relative_residual",
        )
        per_source = _finite_readonly_array(
            self.per_source_relative_residual,
            dtype=np.float64,
            name="per_source_relative_residual",
            shape=(source_count,),
            real_valued=True,
        )
        if np.any(per_source < 0.0):
            raise ValueError(
                "per_source_relative_residual must be non-negative."
            )
        incident_leak = _nonnegative_finite(
            self.incident_representation_leak,
            name="incident_representation_leak",
        )
        solve_seconds = _nonnegative_finite(
            self.solve_seconds,
            name="solve_seconds",
        )
        receiver_seconds = _nonnegative_finite(
            self.receiver_evaluation_seconds,
            name="receiver_evaluation_seconds",
        )
        total_seconds = _nonnegative_finite(
            self.total_seconds,
            name="total_seconds",
        )
        diagnostics = _frozen_mapping(self.diagnostics, name="diagnostics")

        object.__setattr__(self, "eps0", epsilon_zero)
        object.__setattr__(self, "mu0", mu_zero)
        object.__setattr__(
            self,
            "source_points",
            _finite_readonly_array(
                sources,
                dtype=np.float64,
                name="source_points",
                shape=(source_count, 2),
                real_valued=True,
            ),
        )
        object.__setattr__(
            self,
            "receiver_points",
            _finite_readonly_array(
                receivers,
                dtype=np.float64,
                name="receiver_points",
                shape=(receiver_count, 2),
                real_valued=True,
            ),
        )
        object.__setattr__(
            self,
            "source_strengths",
            _finite_readonly_array(
                strengths,
                dtype=np.complex128,
                name="source_strengths",
                shape=(source_count,),
            ),
        )
        for name, values in arrays.items():
            object.__setattr__(self, name, values)
        object.__setattr__(
            self,
            "linear_system_relative_residual",
            aggregate_residual,
        )
        object.__setattr__(self, "per_source_relative_residual", per_source)
        object.__setattr__(self, "incident_representation_leak", incident_leak)
        object.__setattr__(self, "solve_seconds", solve_seconds)
        object.__setattr__(
            self,
            "receiver_evaluation_seconds",
            receiver_seconds,
        )
        object.__setattr__(self, "total_seconds", total_seconds)
        object.__setattr__(self, "diagnostics", diagnostics)


def solve_multicomponent_kress_tmz_total_field_batch(
    boundary: OrderedBoundary2D,
    source_points,
    receiver_points,
    angular_frequency: float,
    source_strength=1.0,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    config: MultiComponentKressSolveConfig | None = None,
) -> MultiComponentKressForwardResult:
    """Build and solve the fixed-topology, same-material multi-object system."""

    total_started = perf_counter()
    settings = MultiComponentKressSolveConfig() if config is None else config
    if not isinstance(settings, MultiComponentKressSolveConfig):
        raise TypeError("config must be a MultiComponentKressSolveConfig object.")
    if not isinstance(boundary, OrderedBoundary2D):
        raise TypeError("boundary must be an OrderedBoundary2D object.")
    sources = _real_points(source_points, name="source_points")
    receivers = _real_points(receiver_points, name="receiver_points")
    strengths = _source_strengths(source_strength, sources.shape[0])
    clearance = settings.minimum_field_point_clearance_in_weights * float(
        np.max(boundary.arc_length_weights)
    )
    minimum_source_distance = _validate_exterior_points(
        sources,
        boundary,
        name="source_points",
        minimum_clearance=clearance,
    )
    _validate_exterior_points(
        receivers,
        boundary,
        name="receiver_points",
        minimum_clearance=clearance,
    )
    source_receiver_distance = np.linalg.norm(
        receivers[None, :, :] - sources[:, None, :],
        axis=-1,
    )
    if np.any(source_receiver_distance <= 0.0):
        raise MultiComponentFieldPointError(
            "source_points and receiver_points must be distinct."
        )
    system = build_multicomponent_kress_tmz_frequency_system(
        boundary,
        angular_frequency,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
        config=settings.assembly,
        compute_condition_number=settings.compute_condition_number,
    )
    dirichlet_incident, neumann_incident = multicomponent_incident_trace_on_boundary(
        boundary,
        sources,
        system.k_exterior,
        strengths,
    )
    right_hand_side = np.concatenate(
        (dirichlet_incident, neumann_incident),
        axis=1,
    ).T
    if not np.all(np.isfinite(right_hand_side)):
        raise FloatingPointError(
            "multi-component incident traces produced a non-finite right-hand side."
        )
    solve_started = perf_counter()
    solution = np.linalg.solve(system.system_matrix, right_hand_side)
    solve_seconds = float(perf_counter() - solve_started)
    if not np.all(np.isfinite(solution)):
        raise FloatingPointError(
            "multi-component direct solve produced a non-finite solution."
        )
    residual = system.system_matrix @ solution - right_hand_side
    if not np.all(np.isfinite(residual)):
        raise FloatingPointError(
            "multi-component direct solve produced a non-finite residual."
        )
    right_norms = np.linalg.norm(right_hand_side, axis=0)
    residual_norms = np.linalg.norm(residual, axis=0)
    per_source = np.divide(
        residual_norms,
        right_norms,
        out=np.where(residual_norms == 0.0, 0.0, np.inf),
        where=right_norms > 0.0,
    )
    aggregate_denominator = float(np.linalg.norm(right_hand_side))
    aggregate_residual = float(np.linalg.norm(residual))
    relative_residual = (
        aggregate_residual / aggregate_denominator
        if aggregate_denominator > 0.0
        else (0.0 if aggregate_residual == 0.0 else float("inf"))
    )
    if not np.all(np.isfinite(per_source)) or not np.isfinite(relative_residual):
        raise FloatingPointError(
            "multi-component direct solve produced non-finite residual diagnostics."
        )
    count = boundary.num_nodes
    dirichlet_total = solution[:count].T
    neumann_total = solution[count:].T

    receiver_started = perf_counter()
    receiver_operator = build_multicomponent_exterior_receiver_operator(
        boundary,
        receivers,
        system.k_exterior,
        minimum_clearance=clearance,
    )
    representation = receiver_operator.evaluate(dirichlet_total, neumann_total)
    incident_leak_result = receiver_operator.evaluate(
        dirichlet_incident,
        neumann_incident,
    )
    incident_receiver = (
        strengths[:, None]
        * 0.25j
        * hankel1(0, system.k_exterior * source_receiver_distance)
    )
    total_receiver = incident_receiver + representation.scattered
    for name, values in (
        ("incident receiver field", incident_receiver),
        ("single-layer receiver field", representation.single_layer),
        ("double-layer receiver field", representation.double_layer),
        ("scattered receiver field", representation.scattered),
        ("total receiver field", total_receiver),
        ("incident representation", incident_leak_result.scattered),
    ):
        if not np.all(np.isfinite(values)):
            raise FloatingPointError(
                f"multi-component solve produced a non-finite {name}."
            )
    receiver_seconds = float(perf_counter() - receiver_started)
    leak_scale = max(float(np.max(np.abs(incident_receiver))), np.finfo(float).tiny)
    incident_leak = float(
        np.max(np.abs(incident_leak_result.scattered)) / leak_scale
    )
    if not np.isfinite(incident_leak):
        raise FloatingPointError(
            "multi-component solve produced a non-finite incident-representation leak."
        )
    total_seconds = float(perf_counter() - total_started)
    diagnostics = MappingProxyType(
        {
            "solve_form": "direct_unsquared",
            "num_components": boundary.num_components,
            "component_ids": boundary.component_ids,
            "component_offsets": tuple(int(value) for value in boundary.component_offsets),
            "component_orientations": MappingProxyType(
                {
                    component.component_id: component.orientation
                    for component in boundary.components
                }
            ),
            "normal_convention": "outward_from_each_inclusion",
            "num_sources": int(sources.shape[0]),
            "num_receivers": int(receivers.shape[0]),
            "minimum_source_distance": minimum_source_distance,
            "minimum_receiver_distance": representation.minimum_receiver_distance,
            "minimum_field_point_clearance_required": clearance,
            "receiver_quadrature": "ordinary_periodic_trapezoid_per_component",
            "receiver_operator": "C=[D,-S]",
            "close_evaluation": False,
        }
    )
    return MultiComponentKressForwardResult(
        system=system,
        solve_config=settings,
        exterior_material=exterior,
        interior_material=interior,
        eps0=float(eps0),
        mu0=float(mu0),
        receiver_operator=receiver_operator,
        source_points=_readonly(sources, dtype=np.float64),
        receiver_points=_readonly(receivers, dtype=np.float64),
        source_strengths=_readonly(strengths, dtype=np.complex128),
        right_hand_side=_readonly(right_hand_side, dtype=np.complex128),
        solution=_readonly(solution, dtype=np.complex128),
        dirichlet_incident=dirichlet_incident,
        neumann_incident=neumann_incident,
        dirichlet_total=_readonly(dirichlet_total, dtype=np.complex128),
        neumann_total=_readonly(neumann_total, dtype=np.complex128),
        incident_receiver=_readonly(incident_receiver, dtype=np.complex128),
        single_receiver=representation.single_layer,
        double_receiver=representation.double_layer,
        scattered_receiver=representation.scattered,
        total_receiver=_readonly(total_receiver, dtype=np.complex128),
        linear_system_relative_residual=relative_residual,
        per_source_relative_residual=_readonly(per_source, dtype=np.float64),
        incident_representation_leak=incident_leak,
        solve_seconds=solve_seconds,
        receiver_evaluation_seconds=receiver_seconds,
        total_seconds=total_seconds,
        diagnostics=diagnostics,
    )


__all__ = [
    "ComponentPairReport",
    "ExteriorCrossBlocks",
    "MultiComponentAssemblyConfig",
    "MultiComponentBoundaryAdapter",
    "MultiComponentCurveGeometryError",
    "MultiComponentExteriorReceiverOperator",
    "MultiComponentExteriorRepresentationResult",
    "MultiComponentFieldPointError",
    "MultiComponentKressForwardResult",
    "MultiComponentKressGeometryError",
    "MultiComponentKressSolveConfig",
    "MultiComponentKressTMzFrequencySystem",
    "MultiComponentMullerBlocks",
    "MultiComponentTopologyError",
    "adapt_multicomponent_boundary",
    "build_exterior_cross_blocks",
    "build_multicomponent_exterior_receiver_operator",
    "build_multicomponent_kress_tmz_frequency_system",
    "build_multicomponent_muller_blocks",
    "build_multicomponent_muller_system",
    "multicomponent_incident_trace_on_boundary",
    "solve_multicomponent_kress_tmz_total_field_batch",
]
