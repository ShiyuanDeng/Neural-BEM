"""Automatic multi-component SDF-to-ordered-boundary construction.

Marching squares owns topology discovery: no component count is required for
the normal path.  Method B fits every discovered loop independently and
``OrderedBoundaryParameterization2D`` preserves component ownership through
discretisation.  An exact expected count remains available as an optional
debug/test assertion, not as the default operating mode.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import operator
from time import perf_counter
from typing import Any, Sequence, Union

import numpy as np

from ordered_boundary import (
    BoundaryValidationConfig,
    OrderedBoundary2D,
    OrderedBoundaryParameterization2D,
    OrderedBoundaryReport,
    OrderedBoundaryValidationError,
    PeriodicCurve2D,
    PeriodicParameterization2D,
    validate_ordered_parameterization,
)
from sdf_to_ordered_boundary import (
    ArcLengthConfig,
    ArcLengthGeometryError,
    FrontendConfig,
    MethodBConfig,
    ProjectionConfig,
    TorchImplicitField2D,
    extract_frontend_components,
    fit_method_b,
)
from sdf_to_ordered_boundary.frontend import FrontendError


Bounds2D = tuple[tuple[float, float], tuple[float, float]]
NodeCounts = Union[int, tuple[int, ...]]


class MultiComponentOrderedSDFGeometryError(FrontendError):
    """The implicit field cannot produce the configured component topology."""


def _canonical_bounds(bounds: Any) -> Bounds2D:
    if np.iscomplexobj(bounds):
        raise ValueError("bounds must be real-valued.")
    try:
        values = np.asarray(bounds, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "bounds must be ((xmin, ymin), (xmax, ymax)) with finite values."
        ) from exc
    if values.shape != (2, 2) or not np.all(np.isfinite(values)):
        raise ValueError(
            "bounds must be ((xmin, ymin), (xmax, ymax)) with finite values."
        )
    if np.any(values[1] <= values[0]):
        raise ValueError("Upper bounds must be strictly greater than lower bounds.")
    return (
        (float(values[0, 0]), float(values[0, 1])),
        (float(values[1, 0]), float(values[1, 1])),
    )


def _integer_at_least(value: Any, *, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return result


def _finite_nonnegative(value: Any, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number, not bool.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real number.") from exc
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


def _canonical_node_counts(
    values: int | Sequence[int],
    *,
    bandwidth: int,
) -> NodeCounts:
    if isinstance(values, (bool, np.bool_)):
        raise TypeError("num_nodes must be an integer or a sequence of integers.")
    try:
        scalar = operator.index(values)
    except TypeError:
        try:
            counts = tuple(values)
        except TypeError as exc:
            raise TypeError(
                "num_nodes must be an integer or a sequence of integers."
            ) from exc
        if not counts:
            raise ValueError("A num_nodes sequence must not be empty.")
        canonical: NodeCounts = tuple(
            _integer_at_least(value, name=f"num_nodes[{index}]", minimum=8)
            for index, value in enumerate(counts)
        )
        node_counts = canonical
    else:
        node_counts = _integer_at_least(scalar, name="num_nodes", minimum=8)

    resolved = (node_counts,) if isinstance(node_counts, int) else node_counts
    for index, count in enumerate(resolved):
        label = "num_nodes" if isinstance(node_counts, int) else f"num_nodes[{index}]"
        if count % 2:
            raise ValueError(f"{label} must be even for Kress quadrature.")
        if count < 2 * bandwidth + 2:
            raise ValueError(
                f"{label} must be at least 2 * bandwidth + 2 to avoid aliasing."
            )
    return node_counts


@dataclass(frozen=True)
class MultiComponentOrderedSDFGeometryConfig:
    """Resolution and topology policy for automatic multi-object builds.

    ``projected_samples`` and a scalar ``num_nodes`` apply independently to
    every component.  A sequence of node counts may be supplied when components
    need different Kress resolutions; its order follows the deterministic
    component order returned by the frontend.  Nested components are always
    rejected because the intended downstream solvers model disjoint inclusions,
    not multiply connected material regions.

    ``expected_num_components=None`` is the normal mode: every closed loop is
    retained and the scalar node count is expanded only after extraction.  A
    positive expected count is an optional exact-topology assertion useful for
    deterministic tests.  The component and node ceilings are resource guards,
    while the area/perimeter and residual/gradient limits define whether a
    discovered contour is sufficiently resolved for a downstream BEM solve.

    Production builds confirm the complete extraction, fit, topology, and
    readiness pipeline on a Cartesian grid with the opposite point-count
    parity.  The default confirmation shape adds one sample on each axis; an
    explicit opposite-parity shape can be supplied for a larger resolution
    jump.  ``minimum_grid_clearance_factor`` also rejects distinct fitted loops
    whose gap is not resolved by at least that many cells.  Both protections
    can be set to zero/false only for controlled diagnostics.  Successful
    confirmation also requires a one-to-one component match whose sampled
    symmetric Hausdorff distance is within the larger of a grid-scale floor
    and ``grid_confirmation_residual_tolerance_factor`` times that matched
    pair's normalized fit residual.  Tolerances are deliberately local: a
    rough component cannot make another component's match admissible, and the
    residual allowance is capped by
    ``grid_confirmation_geometry_tolerance_cap_factor`` grid cells.  This is a
    resolution-confidence check, not a proof of continuous topology.
    Nonzero grid-relative area, perimeter, and two-axis span floors reject
    one-cell marching-squares seeds before their projected versions can
    masquerade as well-resolved solver components.  After discretisation, the
    component gap must also exceed
    ``minimum_quadrature_clearance_in_weights`` times the largest arc-length
    weight, matching the ordinary cross-component quadrature assumption used
    by the default multi-component Kress assembly.
    """

    bounds: Bounds2D
    expected_num_components: int | None = None
    grid_shape: tuple[int, int] = (129, 129)
    projected_samples: int = 64
    bandwidth: int = 10
    num_nodes: int | tuple[int, ...] = 64
    arclength_dense_resolution: int = 512
    validation_resolution: int = 256
    minimum_intercomponent_clearance: float = 0.0
    maximum_num_components: int = 32
    maximum_total_nodes: int = 2048
    minimum_component_perimeter: float = 0.0
    minimum_component_area: float = 0.0
    minimum_grid_component_area_factor: float = 4.0
    minimum_grid_component_perimeter_factor: float = 8.0
    minimum_grid_component_span_factor: float = 2.0
    minimum_boundary_gradient_norm: float = 1.0e-8
    maximum_normalized_curve_residual: float = 1.0e-3
    minimum_grid_clearance_factor: float = 2.0
    minimum_quadrature_clearance_in_weights: float = 2.0
    confirm_grid_parity: bool = True
    confirmation_grid_shape: tuple[int, int] | None = None
    grid_confirmation_geometry_tolerance_factor: float = 0.05
    grid_confirmation_residual_tolerance_factor: float = 8.0
    grid_confirmation_geometry_tolerance_cap_factor: float = 2.0

    def __post_init__(self) -> None:
        bounds = _canonical_bounds(self.bounds)
        expected = self.expected_num_components
        if expected is not None:
            expected = _integer_at_least(
                expected,
                name="expected_num_components",
                minimum=1,
            )
        try:
            grid_count = len(self.grid_shape)
        except TypeError as exc:
            raise TypeError(
                "grid_shape must be a two-element sequence (ny, nx)."
            ) from exc
        if grid_count != 2:
            raise ValueError("grid_shape must be a two-element sequence (ny, nx).")
        grid_shape = (
            _integer_at_least(self.grid_shape[0], name="grid_shape[0]", minimum=2),
            _integer_at_least(self.grid_shape[1], name="grid_shape[1]", minimum=2),
        )
        bandwidth = _integer_at_least(self.bandwidth, name="bandwidth", minimum=1)
        projected_samples = _integer_at_least(
            self.projected_samples,
            name="projected_samples",
            minimum=8,
        )
        if projected_samples < 2 * bandwidth + 1:
            raise ValueError(
                "projected_samples must be at least 2 * bandwidth + 1 for "
                "the Method-B Fourier fit."
            )
        node_counts = _canonical_node_counts(
            self.num_nodes,
            bandwidth=bandwidth,
        )
        if (
            expected is not None
            and isinstance(node_counts, tuple)
            and len(node_counts) != expected
        ):
            raise ValueError(
                "A num_nodes sequence must contain one entry per expected component."
            )
        dense_resolution = _integer_at_least(
            self.arclength_dense_resolution,
            name="arclength_dense_resolution",
            minimum=16,
        )
        validation_resolution = _integer_at_least(
            self.validation_resolution,
            name="validation_resolution",
            minimum=16,
        )
        minimum_fourier_resolution = 2 * bandwidth + 2
        if dense_resolution < minimum_fourier_resolution:
            raise ValueError(
                "arclength_dense_resolution must be at least 2 * bandwidth + 2."
            )
        if validation_resolution < minimum_fourier_resolution:
            raise ValueError(
                "validation_resolution must be at least 2 * bandwidth + 2."
            )
        clearance = _finite_nonnegative(
            self.minimum_intercomponent_clearance,
            name="minimum_intercomponent_clearance",
        )
        maximum_num_components = _integer_at_least(
            self.maximum_num_components,
            name="maximum_num_components",
            minimum=1,
        )
        maximum_total_nodes = _integer_at_least(
            self.maximum_total_nodes,
            name="maximum_total_nodes",
            minimum=8,
        )
        if expected is not None and expected > maximum_num_components:
            raise ValueError(
                "expected_num_components must not exceed maximum_num_components."
            )
        minimum_component_perimeter = _finite_nonnegative(
            self.minimum_component_perimeter,
            name="minimum_component_perimeter",
        )
        minimum_component_area = _finite_nonnegative(
            self.minimum_component_area,
            name="minimum_component_area",
        )
        minimum_grid_component_area_factor = _finite_nonnegative(
            self.minimum_grid_component_area_factor,
            name="minimum_grid_component_area_factor",
        )
        minimum_grid_component_perimeter_factor = _finite_nonnegative(
            self.minimum_grid_component_perimeter_factor,
            name="minimum_grid_component_perimeter_factor",
        )
        minimum_grid_component_span_factor = _finite_nonnegative(
            self.minimum_grid_component_span_factor,
            name="minimum_grid_component_span_factor",
        )
        minimum_boundary_gradient_norm = _finite_nonnegative(
            self.minimum_boundary_gradient_norm,
            name="minimum_boundary_gradient_norm",
        )
        maximum_normalized_curve_residual = _finite_nonnegative(
            self.maximum_normalized_curve_residual,
            name="maximum_normalized_curve_residual",
        )
        if maximum_normalized_curve_residual == 0.0:
            raise ValueError(
                "maximum_normalized_curve_residual must be positive."
            )
        minimum_grid_clearance_factor = _finite_nonnegative(
            self.minimum_grid_clearance_factor,
            name="minimum_grid_clearance_factor",
        )
        minimum_quadrature_clearance_in_weights = _finite_nonnegative(
            self.minimum_quadrature_clearance_in_weights,
            name="minimum_quadrature_clearance_in_weights",
        )
        grid_confirmation_geometry_tolerance_factor = _finite_nonnegative(
            self.grid_confirmation_geometry_tolerance_factor,
            name="grid_confirmation_geometry_tolerance_factor",
        )
        if grid_confirmation_geometry_tolerance_factor == 0.0:
            raise ValueError(
                "grid_confirmation_geometry_tolerance_factor must be positive."
            )
        grid_confirmation_residual_tolerance_factor = _finite_nonnegative(
            self.grid_confirmation_residual_tolerance_factor,
            name="grid_confirmation_residual_tolerance_factor",
        )
        grid_confirmation_geometry_tolerance_cap_factor = _finite_nonnegative(
            self.grid_confirmation_geometry_tolerance_cap_factor,
            name="grid_confirmation_geometry_tolerance_cap_factor",
        )
        if grid_confirmation_geometry_tolerance_cap_factor == 0.0:
            raise ValueError(
                "grid_confirmation_geometry_tolerance_cap_factor must be positive."
            )
        if not isinstance(self.confirm_grid_parity, (bool, np.bool_)):
            raise TypeError("confirm_grid_parity must be boolean.")
        confirm_grid_parity = bool(self.confirm_grid_parity)
        confirmation_grid_shape = self.confirmation_grid_shape
        if confirmation_grid_shape is not None:
            try:
                confirmation_grid_count = len(confirmation_grid_shape)
            except TypeError as exc:
                raise TypeError(
                    "confirmation_grid_shape must be a two-element sequence "
                    "(ny, nx)."
                ) from exc
            if confirmation_grid_count != 2:
                raise ValueError(
                    "confirmation_grid_shape must be a two-element sequence "
                    "(ny, nx)."
                )
            confirmation_grid_shape = (
                _integer_at_least(
                    confirmation_grid_shape[0],
                    name="confirmation_grid_shape[0]",
                    minimum=2,
                ),
                _integer_at_least(
                    confirmation_grid_shape[1],
                    name="confirmation_grid_shape[1]",
                    minimum=2,
                ),
            )
            if not confirm_grid_parity:
                raise ValueError(
                    "confirmation_grid_shape requires confirm_grid_parity=True."
                )
            if any(
                confirmation <= primary
                for primary, confirmation in zip(
                    grid_shape,
                    confirmation_grid_shape,
                )
            ):
                raise ValueError(
                    "confirmation_grid_shape must be strictly finer than "
                    "grid_shape on both axes."
                )
            if any(
                (confirmation - primary) % 2 == 0
                for primary, confirmation in zip(
                    grid_shape,
                    confirmation_grid_shape,
                )
            ):
                raise ValueError(
                    "confirmation_grid_shape must reverse the point-count parity "
                    "of grid_shape on both axes."
                )
        if isinstance(node_counts, tuple) and sum(node_counts) > maximum_total_nodes:
            raise ValueError(
                "The requested num_nodes sequence exceeds maximum_total_nodes."
            )
        if (
            expected is not None
            and isinstance(node_counts, int)
            and expected * node_counts > maximum_total_nodes
        ):
            raise ValueError(
                "The expected component count and num_nodes exceed "
                "maximum_total_nodes."
            )
        object.__setattr__(self, "bounds", bounds)
        object.__setattr__(self, "expected_num_components", expected)
        object.__setattr__(self, "grid_shape", grid_shape)
        object.__setattr__(self, "projected_samples", projected_samples)
        object.__setattr__(self, "bandwidth", bandwidth)
        object.__setattr__(self, "num_nodes", node_counts)
        object.__setattr__(self, "arclength_dense_resolution", dense_resolution)
        object.__setattr__(self, "validation_resolution", validation_resolution)
        object.__setattr__(self, "minimum_intercomponent_clearance", clearance)
        object.__setattr__(self, "maximum_num_components", maximum_num_components)
        object.__setattr__(self, "maximum_total_nodes", maximum_total_nodes)
        object.__setattr__(
            self,
            "minimum_component_perimeter",
            minimum_component_perimeter,
        )
        object.__setattr__(self, "minimum_component_area", minimum_component_area)
        object.__setattr__(
            self,
            "minimum_grid_component_area_factor",
            minimum_grid_component_area_factor,
        )
        object.__setattr__(
            self,
            "minimum_grid_component_perimeter_factor",
            minimum_grid_component_perimeter_factor,
        )
        object.__setattr__(
            self,
            "minimum_grid_component_span_factor",
            minimum_grid_component_span_factor,
        )
        object.__setattr__(
            self,
            "minimum_boundary_gradient_norm",
            minimum_boundary_gradient_norm,
        )
        object.__setattr__(
            self,
            "maximum_normalized_curve_residual",
            maximum_normalized_curve_residual,
        )
        object.__setattr__(
            self,
            "minimum_grid_clearance_factor",
            minimum_grid_clearance_factor,
        )
        object.__setattr__(
            self,
            "minimum_quadrature_clearance_in_weights",
            minimum_quadrature_clearance_in_weights,
        )
        object.__setattr__(self, "confirm_grid_parity", confirm_grid_parity)
        object.__setattr__(
            self,
            "confirmation_grid_shape",
            confirmation_grid_shape,
        )
        object.__setattr__(
            self,
            "grid_confirmation_geometry_tolerance_factor",
            grid_confirmation_geometry_tolerance_factor,
        )
        object.__setattr__(
            self,
            "grid_confirmation_residual_tolerance_factor",
            grid_confirmation_residual_tolerance_factor,
        )
        object.__setattr__(
            self,
            "grid_confirmation_geometry_tolerance_cap_factor",
            grid_confirmation_geometry_tolerance_cap_factor,
        )

    @property
    def grid_spacing(self) -> tuple[float, float]:
        """Primary Cartesian-grid spacing in ``(dx, dy)`` order."""

        (xmin, ymin), (xmax, ymax) = self.bounds
        ny, nx = self.grid_shape
        return (xmax - xmin) / (nx - 1), (ymax - ymin) / (ny - 1)

    @property
    def resolved_minimum_intercomponent_clearance(self) -> float:
        """Solver-readiness clearance including the grid-resolution floor."""

        resolution_floor = self.minimum_grid_clearance_factor * max(
            self.grid_spacing
        )
        return max(self.minimum_intercomponent_clearance, resolution_floor)

    @property
    def resolved_minimum_component_area(self) -> float:
        """Absolute/grid-relative area floor for a resolved raw loop."""

        dx, dy = self.grid_spacing
        return max(
            self.minimum_component_area,
            self.minimum_grid_component_area_factor * dx * dy,
        )

    @property
    def resolved_minimum_component_perimeter(self) -> float:
        """Absolute/grid-relative perimeter floor for a resolved raw loop."""

        return max(
            self.minimum_component_perimeter,
            self.minimum_grid_component_perimeter_factor
            * max(self.grid_spacing),
        )

    @property
    def resolved_minimum_component_spans(self) -> tuple[float, float]:
        """Minimum raw bounding-box spans in physical ``(x, y)`` units."""

        dx, dy = self.grid_spacing
        factor = self.minimum_grid_component_span_factor
        return factor * dx, factor * dy

    @property
    def resolved_confirmation_grid_shape(self) -> tuple[int, int] | None:
        """Opposite-parity grid used by the independent confirmation pass."""

        if not self.confirm_grid_parity:
            return None
        if self.confirmation_grid_shape is not None:
            return self.confirmation_grid_shape
        return self.grid_shape[0] + 1, self.grid_shape[1] + 1

    @property
    def resolved_grid_confirmation_geometry_tolerance(self) -> float | None:
        """Grid-scale floor for matched boundary distance across both grids."""

        confirmation_shape = self.resolved_confirmation_grid_shape
        if confirmation_shape is None:
            return None
        (xmin, ymin), (xmax, ymax) = self.bounds
        confirmation_ny, confirmation_nx = confirmation_shape
        confirmation_spacing = (
            (xmax - xmin) / (confirmation_nx - 1),
            (ymax - ymin) / (confirmation_ny - 1),
        )
        coarser_spacing = max(*self.grid_spacing, *confirmation_spacing)
        return self.grid_confirmation_geometry_tolerance_factor * coarser_spacing

    @property
    def resolved_grid_confirmation_geometry_tolerance_cap(self) -> float | None:
        """Grid-scale ceiling for residual-inflated match tolerances."""

        if not self.confirm_grid_parity:
            return None
        coarser_spacing = max(self.grid_spacing)
        return (
            self.grid_confirmation_geometry_tolerance_cap_factor
            * coarser_spacing
        )

    @property
    def resolved_node_counts(self) -> tuple[int, ...]:
        """Pre-resolved counts when the configuration fixes their arity.

        Automatic scalar configurations cannot know this tuple until contour
        extraction.  Use :meth:`resolve_node_counts` or the build result's
        ``resolved_node_counts`` in that case.
        """

        if isinstance(self.num_nodes, int):
            if self.expected_num_components is None:
                raise ValueError(
                    "A scalar num_nodes cannot be resolved before automatic "
                    "component discovery."
                )
            return (self.num_nodes,) * self.expected_num_components
        return self.num_nodes

    def resolve_node_counts(self, num_components: int) -> tuple[int, ...]:
        """Resolve one Kress node count per discovered component."""

        count = _integer_at_least(
            num_components,
            name="num_components",
            minimum=1,
        )
        if count > self.maximum_num_components:
            raise MultiComponentOrderedSDFGeometryError(
                "Implicit-field topology exceeds maximum_num_components: "
                f"found {count}, limit {self.maximum_num_components}."
            )
        if self.expected_num_components is not None and count != self.expected_num_components:
            raise MultiComponentOrderedSDFGeometryError(
                "Implicit-field topology mismatch: expected "
                f"{self.expected_num_components} closed component(s), found {count}."
            )
        if isinstance(self.num_nodes, int):
            resolved = (self.num_nodes,) * count
        else:
            if len(self.num_nodes) != count:
                raise MultiComponentOrderedSDFGeometryError(
                    "Per-component num_nodes mismatch: configured "
                    f"{len(self.num_nodes)} entries, found {count} closed component(s)."
                )
            resolved = self.num_nodes
        total = sum(resolved)
        if total > self.maximum_total_nodes:
            raise MultiComponentOrderedSDFGeometryError(
                "Discretisation exceeds maximum_total_nodes: requested "
                f"{total}, limit {self.maximum_total_nodes}."
            )
        return resolved

    @classmethod
    def from_compatible_config(
        cls,
        config: Any,
        *,
        expected_num_components: int | None = None,
        minimum_intercomponent_clearance: float = 0.0,
        num_nodes: int | Sequence[int] | None = None,
    ) -> "MultiComponentOrderedSDFGeometryConfig":
        """Copy shared fields from a structurally compatible geometry config.

        This adapter intentionally uses a structural contract.  In particular,
        it does not import ``sdf_inverse`` merely to copy configuration values,
        so this experimental package stays independent of that package's
        neural-model imports.
        """

        required_fields = (
            "bounds",
            "grid_shape",
            "projected_samples",
            "bandwidth",
            "num_nodes",
            "arclength_dense_resolution",
            "validation_resolution",
        )
        missing = tuple(name for name in required_fields if not hasattr(config, name))
        if missing:
            joined = ", ".join(missing)
            raise TypeError(
                "config must provide the single-component geometry fields; "
                f"missing: {joined}."
            )
        resolved_nodes = config.num_nodes if num_nodes is None else num_nodes
        return cls(
            bounds=config.bounds,
            expected_num_components=expected_num_components,
            grid_shape=config.grid_shape,
            projected_samples=config.projected_samples,
            bandwidth=config.bandwidth,
            num_nodes=resolved_nodes,
            arclength_dense_resolution=config.arclength_dense_resolution,
            validation_resolution=config.validation_resolution,
            minimum_intercomponent_clearance=minimum_intercomponent_clearance,
        )


@dataclass(frozen=True)
class GridParityConfirmationDiagnostics:
    """Summary of a successful independent opposite-parity geometry build."""

    primary_grid_shape: tuple[int, int]
    confirmation_grid_shape: tuple[int, int]
    primary_num_components: int
    confirmation_num_components: int
    primary_minimum_projected_field_gradient_norm: float
    confirmation_minimum_projected_field_gradient_norm: float
    primary_minimum_field_gradient_norm: float
    confirmation_minimum_field_gradient_norm: float
    primary_maximum_normalized_curve_residual: float
    confirmation_maximum_normalized_curve_residual: float
    primary_to_confirmation_component_indices: tuple[int, ...]
    matched_component_distances: tuple[float, ...]
    primary_component_normalized_curve_residuals: tuple[float, ...]
    matched_confirmation_component_normalized_curve_residuals: tuple[float, ...]
    matched_component_tolerances: tuple[float, ...]
    confirmation_seconds: float

    def __post_init__(self) -> None:
        canonical_shapes = []
        for name in ("primary_grid_shape", "confirmation_grid_shape"):
            shape = getattr(self, name)
            try:
                shape_count = len(shape)
            except TypeError as exc:
                raise TypeError(f"{name} must be a two-element sequence.") from exc
            if shape_count != 2:
                raise ValueError(f"{name} must be a two-element sequence.")
            canonical_shapes.append(
                (
                    _integer_at_least(shape[0], name=f"{name}[0]", minimum=2),
                    _integer_at_least(shape[1], name=f"{name}[1]", minimum=2),
                )
            )
        primary_shape, confirmation_shape = canonical_shapes
        if any(
            (confirmation - primary) % 2 == 0
            for primary, confirmation in zip(primary_shape, confirmation_shape)
        ):
            raise ValueError(
                "The confirmation grid must reverse point-count parity on both axes."
            )
        primary_count = _integer_at_least(
            self.primary_num_components,
            name="primary_num_components",
            minimum=1,
        )
        confirmation_count = _integer_at_least(
            self.confirmation_num_components,
            name="confirmation_num_components",
            minimum=1,
        )
        if primary_count != confirmation_count:
            raise ValueError(
                "A successful grid-parity confirmation must preserve component count."
            )
        try:
            matched_indices = tuple(self.primary_to_confirmation_component_indices)
        except TypeError as exc:
            raise TypeError(
                "primary_to_confirmation_component_indices must be a sequence."
            ) from exc
        if len(matched_indices) != primary_count:
            raise ValueError(
                "Component-match indices must contain one entry per component."
            )
        matched_indices = tuple(
            _integer_at_least(value, name=f"matched_indices[{index}]", minimum=0)
            for index, value in enumerate(matched_indices)
        )
        if tuple(sorted(matched_indices)) != tuple(range(primary_count)):
            raise ValueError(
                "Component-match indices must be a permutation of confirmation "
                "component indices."
            )
        try:
            matched_distances = tuple(self.matched_component_distances)
        except TypeError as exc:
            raise TypeError(
                "matched_component_distances must be a sequence."
            ) from exc
        if len(matched_distances) != primary_count:
            raise ValueError(
                "Matched component distances must contain one entry per component."
            )
        matched_distances = tuple(
            _finite_nonnegative(
                value,
                name=f"matched_component_distances[{index}]",
            )
            for index, value in enumerate(matched_distances)
        )
        per_component_values = {}
        for name in (
            "primary_component_normalized_curve_residuals",
            "matched_confirmation_component_normalized_curve_residuals",
            "matched_component_tolerances",
        ):
            try:
                values = tuple(getattr(self, name))
            except TypeError as exc:
                raise TypeError(f"{name} must be a sequence.") from exc
            if len(values) != primary_count:
                raise ValueError(
                    f"{name} must contain one entry per matched component."
                )
            values = tuple(
                _finite_nonnegative(value, name=f"{name}[{index}]")
                for index, value in enumerate(values)
            )
            per_component_values[name] = values
        primary_residuals = per_component_values[
            "primary_component_normalized_curve_residuals"
        ]
        confirmation_residuals = per_component_values[
            "matched_confirmation_component_normalized_curve_residuals"
        ]
        matched_tolerances = per_component_values["matched_component_tolerances"]
        if any(tolerance == 0.0 for tolerance in matched_tolerances):
            raise ValueError("Every matched component tolerance must be positive.")
        if any(
            distance > tolerance
            for distance, tolerance in zip(
                matched_distances,
                matched_tolerances,
            )
        ):
            raise ValueError(
                "A successful confirmation cannot exceed its component-geometry "
                "tolerances."
            )
        for name in (
            "primary_minimum_projected_field_gradient_norm",
            "confirmation_minimum_projected_field_gradient_norm",
            "primary_minimum_field_gradient_norm",
            "confirmation_minimum_field_gradient_norm",
            "primary_maximum_normalized_curve_residual",
            "confirmation_maximum_normalized_curve_residual",
            "confirmation_seconds",
        ):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name=name),
            )
        object.__setattr__(self, "primary_grid_shape", primary_shape)
        object.__setattr__(self, "confirmation_grid_shape", confirmation_shape)
        object.__setattr__(self, "primary_num_components", primary_count)
        object.__setattr__(self, "confirmation_num_components", confirmation_count)
        object.__setattr__(
            self,
            "primary_to_confirmation_component_indices",
            matched_indices,
        )
        object.__setattr__(
            self,
            "matched_component_distances",
            matched_distances,
        )
        object.__setattr__(
            self,
            "primary_component_normalized_curve_residuals",
            primary_residuals,
        )
        object.__setattr__(
            self,
            "matched_confirmation_component_normalized_curve_residuals",
            confirmation_residuals,
        )
        object.__setattr__(
            self,
            "matched_component_tolerances",
            matched_tolerances,
        )

        if self.primary_maximum_normalized_curve_residual != max(
            primary_residuals
        ):
            raise ValueError(
                "Primary aggregate residual does not match component residuals."
            )
        if self.confirmation_maximum_normalized_curve_residual != max(
            confirmation_residuals
        ):
            raise ValueError(
                "Confirmation aggregate residual does not match matched component "
                "residuals."
            )

    @property
    def maximum_matched_component_distance(self) -> float:
        return max(self.matched_component_distances)

    @property
    def component_geometry_tolerance(self) -> float:
        """Compatibility summary; acceptance is checked pair by pair."""

        return max(self.matched_component_tolerances)


@dataclass(frozen=True)
class MultiComponentGeometryDiagnostics:
    """Auditable residual and geometric diagnostics for one fitted loop."""

    component_id: str
    num_nodes: int
    projected_sample_count: int
    readiness_sample_count: int
    maximum_projected_sdf_residual: float
    minimum_projected_field_gradient_norm: float
    maximum_projected_field_gradient_norm: float
    maximum_curve_sdf_residual: float
    maximum_normalized_curve_residual: float
    minimum_field_gradient_norm: float
    maximum_field_gradient_norm: float
    minimum_speed: float
    maximum_speed: float
    speed_ratio: float
    signed_area: float
    perimeter: float
    centroid: tuple[float, float]
    bounding_box_min: tuple[float, float]
    bounding_box_max: tuple[float, float]
    fit_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be a non-empty string.")
        object.__setattr__(self, "component_id", self.component_id.strip())
        object.__setattr__(
            self,
            "num_nodes",
            _integer_at_least(self.num_nodes, name="num_nodes", minimum=3),
        )
        object.__setattr__(
            self,
            "projected_sample_count",
            _integer_at_least(
                self.projected_sample_count,
                name="projected_sample_count",
                minimum=3,
            ),
        )
        object.__setattr__(
            self,
            "readiness_sample_count",
            _integer_at_least(
                self.readiness_sample_count,
                name="readiness_sample_count",
                minimum=3,
            ),
        )
        for name in (
            "maximum_projected_sdf_residual",
            "minimum_projected_field_gradient_norm",
            "maximum_projected_field_gradient_norm",
            "maximum_curve_sdf_residual",
            "maximum_normalized_curve_residual",
            "minimum_field_gradient_norm",
            "maximum_field_gradient_norm",
            "minimum_speed",
            "maximum_speed",
            "speed_ratio",
            "signed_area",
            "perimeter",
            "fit_seconds",
        ):
            value = _finite_nonnegative(getattr(self, name), name=name)
            object.__setattr__(self, name, value)
        if self.maximum_field_gradient_norm < self.minimum_field_gradient_norm:
            raise ValueError(
                "maximum_field_gradient_norm must not be below "
                "minimum_field_gradient_norm."
            )
        if (
            self.maximum_projected_field_gradient_norm
            < self.minimum_projected_field_gradient_norm
        ):
            raise ValueError(
                "maximum_projected_field_gradient_norm must not be below "
                "minimum_projected_field_gradient_norm."
            )
        if self.minimum_speed <= 0.0:
            raise ValueError("minimum_speed must be positive.")
        if self.maximum_speed < self.minimum_speed:
            raise ValueError("maximum_speed must not be below minimum_speed.")
        if self.speed_ratio < 1.0:
            raise ValueError("speed_ratio must be at least one.")
        if self.signed_area <= 0.0:
            raise ValueError("signed_area must be positive for a CCW component.")
        if self.perimeter <= 0.0:
            raise ValueError("perimeter must be positive.")
        for name in ("centroid", "bounding_box_min", "bounding_box_max"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != (2,) or not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must contain two finite coordinates.")
            object.__setattr__(self, name, tuple(float(item) for item in value))


@dataclass(frozen=True)
class MultiComponentOrderedSDFGeometryBuild:
    """A solver-neutral multi-component boundary and preprocessing audit."""

    boundary: OrderedBoundary2D
    parameterization: OrderedBoundaryParameterization2D
    topology_report: OrderedBoundaryReport
    component_diagnostics: tuple[MultiComponentGeometryDiagnostics, ...]
    frontend_seconds: float
    fit_seconds: float
    topology_validation_seconds: float
    discretize_seconds: float
    residual_validation_seconds: float
    total_seconds: float
    config: MultiComponentOrderedSDFGeometryConfig
    resolved_node_counts: tuple[int, ...]
    resolved_required_intercomponent_clearance: float | None
    grid_parity_confirmation: GridParityConfirmationDiagnostics | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.boundary, OrderedBoundary2D):
            raise TypeError("boundary must be an OrderedBoundary2D.")
        if not isinstance(
            self.parameterization,
            OrderedBoundaryParameterization2D,
        ):
            raise TypeError(
                "parameterization must be an OrderedBoundaryParameterization2D."
            )
        if not isinstance(self.topology_report, OrderedBoundaryReport):
            raise TypeError("topology_report must be an OrderedBoundaryReport.")
        if not self.topology_report.valid:
            raise ValueError("topology_report must describe a valid boundary.")
        if not isinstance(self.config, MultiComponentOrderedSDFGeometryConfig):
            raise TypeError(
                "config must be a MultiComponentOrderedSDFGeometryConfig."
            )
        components = tuple(self.component_diagnostics)
        if not all(
            isinstance(item, MultiComponentGeometryDiagnostics)
            for item in components
        ):
            raise TypeError(
                "component_diagnostics must contain "
                "MultiComponentGeometryDiagnostics objects."
            )
        expected_ids = self.boundary.component_ids
        if self.parameterization.component_ids != expected_ids:
            raise ValueError("Boundary and parameterization component IDs must agree.")
        report_ids = tuple(
            component.component_id for component in self.topology_report.components
        )
        if report_ids != expected_ids:
            raise ValueError("Topology report and boundary component IDs must agree.")
        if tuple(item.component_id for item in components) != expected_ids:
            raise ValueError("Component diagnostics must follow boundary component order.")
        if (
            self.config.expected_num_components is not None
            and len(components) != self.config.expected_num_components
        ):
            raise ValueError("Component diagnostics do not match the configured count.")
        if self.topology_report.num_components != len(components):
            raise ValueError("Topology report and boundary component counts must agree.")
        try:
            resolved_node_counts = tuple(self.resolved_node_counts)
        except TypeError as exc:
            raise TypeError(
                "resolved_node_counts must be a sequence of integers."
            ) from exc
        if len(resolved_node_counts) != len(components):
            raise ValueError(
                "resolved_node_counts must contain one entry per component."
            )
        resolved_node_counts = tuple(
            _integer_at_least(value, name=f"resolved_node_counts[{index}]", minimum=8)
            for index, value in enumerate(resolved_node_counts)
        )
        configured_node_counts = self.config.resolve_node_counts(len(components))
        if resolved_node_counts != configured_node_counts:
            raise ValueError(
                "Resolved node counts must match the geometry config."
            )
        observed_node_counts = tuple(
            component.num_nodes for component in self.boundary.components
        )
        if observed_node_counts != resolved_node_counts:
            raise ValueError(
                "Boundary component node counts must match resolved_node_counts."
            )
        required_clearance = self.resolved_required_intercomponent_clearance
        if len(components) == 1:
            if required_clearance is not None:
                raise ValueError(
                    "resolved_required_intercomponent_clearance must be None "
                    "for one component."
                )
        else:
            if required_clearance is None:
                raise ValueError(
                    "resolved_required_intercomponent_clearance is required for "
                    "multiple components."
                )
            required_clearance = _finite_nonnegative(
                required_clearance,
                name="resolved_required_intercomponent_clearance",
            )
            expected_required_clearance = max(
                self.config.resolved_minimum_intercomponent_clearance,
                self.config.minimum_quadrature_clearance_in_weights
                * float(np.max(self.boundary.arc_length_weights)),
            )
            if required_clearance != expected_required_clearance:
                raise ValueError(
                    "resolved_required_intercomponent_clearance does not match "
                    "the geometry config and boundary weights."
                )
            observed_clearance = (
                self.topology_report.minimum_intercomponent_clearance
            )
            if observed_clearance is None or observed_clearance <= required_clearance:
                raise ValueError(
                    "A successful geometry build must exceed its resolved required "
                    "intercomponent clearance."
                )
        object.__setattr__(self, "component_diagnostics", components)
        object.__setattr__(self, "resolved_node_counts", resolved_node_counts)
        object.__setattr__(
            self,
            "resolved_required_intercomponent_clearance",
            required_clearance,
        )
        confirmation = self.grid_parity_confirmation
        if self.config.confirm_grid_parity:
            if not isinstance(confirmation, GridParityConfirmationDiagnostics):
                raise ValueError(
                    "grid_parity_confirmation is required when "
                    "confirm_grid_parity is enabled."
                )
            if confirmation.primary_grid_shape != self.config.grid_shape:
                raise ValueError(
                    "Grid-confirmation diagnostics do not match the primary grid."
                )
            if (
                confirmation.confirmation_grid_shape
                != self.config.resolved_confirmation_grid_shape
            ):
                raise ValueError(
                    "Grid-confirmation diagnostics do not match the configured "
                    "confirmation grid."
                )
            grid_tolerance = (
                self.config.resolved_grid_confirmation_geometry_tolerance
            )
            if grid_tolerance is None:  # pragma: no cover - config invariant
                raise RuntimeError(
                    "The enabled grid confirmation has no geometry tolerance."
                )
            tolerance_cap = (
                self.config.resolved_grid_confirmation_geometry_tolerance_cap
            )
            if tolerance_cap is None:  # pragma: no cover - config invariant
                raise RuntimeError(
                    "The enabled grid confirmation has no geometry tolerance cap."
                )
            primary_component_residuals = tuple(
                item.maximum_normalized_curve_residual for item in components
            )
            if (
                confirmation.primary_component_normalized_curve_residuals
                != primary_component_residuals
            ):
                raise ValueError(
                    "Grid-confirmation diagnostics do not match primary component "
                    "residuals."
                )
            matched_confirmation_residuals = (
                confirmation.matched_confirmation_component_normalized_curve_residuals
            )
            expected_geometry_tolerances = tuple(
                max(
                    grid_tolerance,
                    min(
                        self.config.grid_confirmation_residual_tolerance_factor
                        * max(primary_residual, confirmation_residual),
                        tolerance_cap,
                    ),
                )
                for primary_residual, confirmation_residual in zip(
                    primary_component_residuals,
                    matched_confirmation_residuals,
                )
            )
            if (
                confirmation.matched_component_tolerances
                != expected_geometry_tolerances
            ):
                raise ValueError(
                    "Grid-confirmation diagnostics do not match the configured "
                    "per-component geometry tolerances."
                )
            if confirmation.primary_num_components != len(components):
                raise ValueError(
                    "Grid-confirmation diagnostics do not match the boundary "
                    "component count."
                )
            primary_minimum_projected_gradient = min(
                item.minimum_projected_field_gradient_norm for item in components
            )
            primary_minimum_curve_gradient = min(
                item.minimum_field_gradient_norm for item in components
            )
            primary_maximum_residual = max(
                item.maximum_normalized_curve_residual for item in components
            )
            if (
                confirmation.primary_minimum_projected_field_gradient_norm
                != primary_minimum_projected_gradient
                or confirmation.primary_minimum_field_gradient_norm
                != primary_minimum_curve_gradient
                or confirmation.primary_maximum_normalized_curve_residual
                != primary_maximum_residual
            ):
                raise ValueError(
                    "Grid-confirmation diagnostics do not match primary readiness "
                    "diagnostics."
                )
        elif confirmation is not None:
            raise ValueError(
                "grid_parity_confirmation must be None when confirmation is disabled."
            )
        for name in (
            "frontend_seconds",
            "fit_seconds",
            "topology_validation_seconds",
            "discretize_seconds",
            "residual_validation_seconds",
            "total_seconds",
        ):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name=name),
            )

    @property
    def num_components(self) -> int:
        return self.boundary.num_components

    @property
    def curve(self) -> PeriodicCurve2D:
        """Compatibility view for callers explicitly handling one component."""

        if self.num_components != 1:
            raise MultiComponentOrderedSDFGeometryError(
                "A multi-component build has no unique curve; use boundary.components."
            )
        return self.boundary.components[0]

    @property
    def maximum_projected_sdf_residual(self) -> float:
        return max(
            item.maximum_projected_sdf_residual
            for item in self.component_diagnostics
        )

    @property
    def maximum_curve_sdf_residual(self) -> float:
        return max(
            item.maximum_curve_sdf_residual for item in self.component_diagnostics
        )

    @property
    def maximum_normalized_curve_residual(self) -> float:
        return max(
            item.maximum_normalized_curve_residual
            for item in self.component_diagnostics
        )

    @property
    def minimum_field_gradient_norm(self) -> float:
        return min(
            item.minimum_field_gradient_norm
            for item in self.component_diagnostics
        )

    @property
    def minimum_projected_field_gradient_norm(self) -> float:
        return min(
            item.minimum_projected_field_gradient_norm
            for item in self.component_diagnostics
        )

    @property
    def speed_ratio(self) -> float:
        return max(item.speed_ratio for item in self.component_diagnostics)


def _torch_module():
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - Torch is a project dependency
        raise ImportError(
            "Multi-component SDF geometry requires the 'torch' dependency."
        ) from exc
    return torch


def _model_tensor_options(model: Any) -> tuple[Any, Any]:
    """Infer evaluation device and floating dtype from a module's state."""

    torch = _torch_module()
    reference = None
    for accessor_name in ("parameters", "buffers"):
        accessor = getattr(model, accessor_name, None)
        if not callable(accessor):
            continue
        try:
            reference = next(iter(accessor()))
        except StopIteration:
            continue
        if reference is not None:
            break
    if reference is None:
        return torch.device("cpu"), torch.get_default_dtype()
    if not isinstance(reference, torch.Tensor):
        raise TypeError("Model parameters and buffers must be torch.Tensor objects.")
    if not reference.is_floating_point():
        raise TypeError("The model's inferred evaluation dtype must be floating-point.")
    return reference.device, reference.dtype


def _projection_residual_tolerance(dtype: Any) -> float:
    torch = _torch_module()
    try:
        machine_epsilon = float(torch.finfo(dtype).eps)
    except TypeError as exc:
        raise TypeError(
            "The model's inferred dtype must support floating arithmetic."
        ) from exc
    return max(1.0e-10, 8.0 * machine_epsilon)


def _polygon_centroid(points: np.ndarray) -> tuple[float, float]:
    following = np.roll(points, -1, axis=0)
    cross = points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1]
    area_factor = float(np.sum(cross))
    scale = max(float(np.max(np.abs(points))), 1.0)
    if abs(area_factor) <= np.finfo(np.float64).eps * scale**2:
        centroid = np.mean(points, axis=0)
    else:
        centroid = np.sum((points + following) * cross[:, None], axis=0)
        centroid /= 3.0 * area_factor
    return float(centroid[0]), float(centroid[1])


def _minimum_projected_intercomponent_clearance(
    components: Sequence[Any],
) -> float | None:
    """Minimum sampled separation before a Fourier fit can open a small gap."""

    if len(components) < 2:
        return None
    minimum_squared = np.inf
    for first_index, first in enumerate(components[:-1]):
        first_points = np.asarray(first.projected_points, dtype=np.float64)
        for second in components[first_index + 1 :]:
            second_points = np.asarray(second.projected_points, dtype=np.float64)
            # Components are resource-capped and projected_samples is explicit;
            # evaluate one pair at a time so memory does not scale as M^2.
            for first_point in first_points:
                squared_distances = np.sum(
                    (second_points - first_point[None, :]) ** 2,
                    axis=1,
                )
                minimum_squared = min(
                    minimum_squared,
                    float(np.min(squared_distances)),
                )
    if not np.isfinite(minimum_squared):  # pragma: no cover - frontend invariant
        raise RuntimeError("Projected component clearance could not be evaluated.")
    return float(np.sqrt(max(minimum_squared, 0.0)))


def _maximum_point_to_polyline_distance(
    query_points: np.ndarray,
    polyline_points: np.ndarray,
) -> float:
    """Maximum nearest-segment distance to one closed polygonal curve."""

    query = np.asarray(query_points, dtype=np.float64)
    polyline = np.asarray(polyline_points, dtype=np.float64)
    if (
        query.ndim != 2
        or polyline.ndim != 2
        or query.shape[1:] != (2,)
        or polyline.shape[1:] != (2,)
        or query.shape[0] == 0
        or polyline.shape[0] < 3
        or not np.all(np.isfinite(query))
        or not np.all(np.isfinite(polyline))
    ):
        raise RuntimeError("Component matching received invalid boundary points.")
    segment_starts = polyline
    segment_vectors = np.roll(polyline, -1, axis=0) - polyline
    segment_length_squared = np.sum(segment_vectors**2, axis=1)
    if np.any(segment_length_squared <= np.finfo(np.float64).tiny):
        raise RuntimeError("Component matching received a degenerate polyline.")

    maximum_squared = 0.0
    # Bound the temporary (query, segment, xy) array independently of curve
    # resolution while retaining exact point-to-segment distances.
    for start in range(0, query.shape[0], 64):
        points = query[start : start + 64]
        offsets = points[:, None, :] - segment_starts[None, :, :]
        parameters = np.sum(
            offsets * segment_vectors[None, :, :],
            axis=2,
        ) / segment_length_squared[None, :]
        parameters = np.clip(parameters, 0.0, 1.0)
        nearest = (
            segment_starts[None, :, :]
            + parameters[:, :, None] * segment_vectors[None, :, :]
        )
        squared_distances = np.sum(
            (points[:, None, :] - nearest) ** 2,
            axis=2,
        )
        maximum_squared = max(
            maximum_squared,
            float(np.max(np.min(squared_distances, axis=1))),
        )
    return float(np.sqrt(maximum_squared))


def _sampled_symmetric_hausdorff_distance(
    first_points: np.ndarray,
    second_points: np.ndarray,
) -> float:
    """Symmetric dense-sample-to-polyline Hausdorff approximation."""

    return max(
        _maximum_point_to_polyline_distance(first_points, second_points),
        _maximum_point_to_polyline_distance(second_points, first_points),
    )


def _match_component_geometries(
    primary: OrderedBoundaryParameterization2D,
    confirmation: OrderedBoundaryParameterization2D,
    *,
    primary_node_counts: Sequence[int],
    confirmation_node_counts: Sequence[int],
    minimum_resolution: int,
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Globally match densely sampled continuous component fits."""

    if primary.num_components != confirmation.num_components:
        raise ValueError("Component geometry matching requires equal counts.")
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:  # pragma: no cover - SciPy is a project dependency
        raise ImportError(
            "Grid-confirmation component matching requires scipy."
        ) from exc

    count = primary.num_components
    if len(primary_node_counts) != count or len(confirmation_node_counts) != count:
        raise RuntimeError("Dense component matching received invalid node counts.")
    primary_points = tuple(
        component.discretize(
            max(minimum_resolution, 4 * int(node_count))
        ).points
        for component, node_count in zip(primary.components, primary_node_counts)
    )
    confirmation_points = tuple(
        component.discretize(
            max(minimum_resolution, 4 * int(node_count))
        ).points
        for component, node_count in zip(
            confirmation.components,
            confirmation_node_counts,
        )
    )
    costs = np.empty((count, count), dtype=np.float64)
    for primary_index, first_points in enumerate(primary_points):
        for confirmation_index, second_points in enumerate(confirmation_points):
            costs[primary_index, confirmation_index] = (
                _sampled_symmetric_hausdorff_distance(
                    first_points,
                    second_points,
                )
            )
    primary_indices, confirmation_indices = linear_sum_assignment(costs)
    if not np.array_equal(primary_indices, np.arange(count)):
        raise RuntimeError("Component assignment did not cover every primary loop.")
    matches = tuple(int(value) for value in confirmation_indices)
    distances = tuple(
        float(costs[primary_index, confirmation_index])
        for primary_index, confirmation_index in zip(
            primary_indices,
            confirmation_indices,
        )
    )
    return matches, distances


def _build_multicomponent_ordered_sdf_geometry(
    model: Any,
    config: MultiComponentOrderedSDFGeometryConfig,
) -> MultiComponentOrderedSDFGeometryBuild:
    """Extract, fit, validate, and discretize every discovered zero-set loop.

    Component IDs and order come directly from the deterministic frontend.
    Topology may vary between calls when ``expected_num_components`` is
    ``None``.  If an exact count is configured, a mismatch fails before
    fitting so callers can use it as a topology-stability assertion.
    """

    if not callable(model):
        raise TypeError("model must be callable on torch tensors of shape (n, 2).")
    if not isinstance(config, MultiComponentOrderedSDFGeometryConfig):
        raise TypeError(
            "config must be a MultiComponentOrderedSDFGeometryConfig."
        )

    device, dtype = _model_tensor_options(model)
    source_identifier = f"{type(model).__module__}.{type(model).__qualname__}"
    total_started = perf_counter()
    field = TorchImplicitField2D(
        model,
        device=device,
        dtype=dtype,
        name=source_identifier,
        sign_convention="negative_inside",
    )

    frontend_started = perf_counter()
    try:
        frontend = extract_frontend_components(
            field,
            FrontendConfig(
                bounds=config.bounds,
                grid_shape=config.grid_shape,
                projected_samples=config.projected_samples,
                maximum_num_components=config.maximum_num_components,
                projection=ProjectionConfig(
                    residual_tolerance=_projection_residual_tolerance(dtype)
                ),
            ),
        )
    except FrontendError as exc:
        raise MultiComponentOrderedSDFGeometryError(
            f"The implicit field has no admissible closed zero contours: {exc}"
        ) from exc
    frontend_seconds = perf_counter() - frontend_started
    if frontend.num_components == 0:
        raise MultiComponentOrderedSDFGeometryError(
            "The implicit field has no closed zero-set components inside bounds."
        )
    resolved_node_counts = config.resolve_node_counts(frontend.num_components)

    projected_gradient_minima: list[float] = []
    projected_gradient_maxima: list[float] = []
    for component in frontend.components:
        required_perimeter = config.resolved_minimum_component_perimeter
        required_area = config.resolved_minimum_component_area
        required_spans = np.asarray(
            config.resolved_minimum_component_spans,
            dtype=np.float64,
        )
        for stage, diagnostics in (
            ("raw", component.raw_diagnostics),
            ("projected", component.projected_diagnostics),
        ):
            perimeter = float(diagnostics.perimeter)
            area = abs(float(diagnostics.signed_area))
            spans = np.asarray(diagnostics.bounding_box_max) - np.asarray(
                diagnostics.bounding_box_min
            )
            if perimeter < required_perimeter:
                raise MultiComponentOrderedSDFGeometryError(
                    f"Frontend component {component.component_id!r} is too small "
                    f"for solver use: {stage} perimeter {perimeter:.6g} is below "
                    "the resolved minimum_component_perimeter requirement "
                    f"{required_perimeter:.6g}."
                )
            if area < required_area:
                raise MultiComponentOrderedSDFGeometryError(
                    f"Frontend component {component.component_id!r} is too small "
                    f"for solver use: {stage} area {area:.6g} is below the "
                    "resolved minimum_component_area requirement "
                    f"{required_area:.6g}."
                )
            if np.any(spans < required_spans):
                axis = "x" if spans[0] < required_spans[0] else "y"
                axis_index = 0 if axis == "x" else 1
                raise MultiComponentOrderedSDFGeometryError(
                    f"Frontend component {component.component_id!r} is too small "
                    f"for solver use: {stage} {axis}-span "
                    f"{spans[axis_index]:.6g} is below the grid-relative "
                    "minimum_component_span requirement "
                    f"{required_spans[axis_index]:.6g}."
                )
        if not component.projection_passes:
            raise RuntimeError(
                f"Frontend component {component.component_id!r} has no "
                "projection diagnostics."
            )
        projected_gradient_norms = np.asarray(
            component.projection_passes[-1].gradient_norms,
            dtype=np.float64,
        )
        if (
            projected_gradient_norms.shape
            != (component.projected_points.shape[0],)
            or not np.all(np.isfinite(projected_gradient_norms))
        ):
            raise RuntimeError(
                f"Frontend component {component.component_id!r} has invalid "
                "projected field-gradient diagnostics."
            )
        minimum_projected_gradient = float(np.min(projected_gradient_norms))
        maximum_projected_gradient = float(np.max(projected_gradient_norms))
        if minimum_projected_gradient < config.minimum_boundary_gradient_norm:
            raise MultiComponentOrderedSDFGeometryError(
                f"Frontend component {component.component_id!r} is not "
                "solver-ready: minimum projected field-gradient norm "
                f"{minimum_projected_gradient:.6g} is below "
                "minimum_boundary_gradient_norm "
                f"{config.minimum_boundary_gradient_norm:.6g}. This pre-fit "
                "regularity check prevents Fourier smoothing from hiding a "
                "pinch that a later maximum normalized curve residual could "
                "miss."
            )
        projected_gradient_minima.append(minimum_projected_gradient)
        projected_gradient_maxima.append(maximum_projected_gradient)

    projected_clearance = _minimum_projected_intercomponent_clearance(
        frontend.components
    )
    required_clearance = config.resolved_minimum_intercomponent_clearance
    if (
        projected_clearance is not None
        and projected_clearance < required_clearance
    ):
        raise MultiComponentOrderedSDFGeometryError(
            "The projected contours fail the minimum intercomponent clearance: "
            f"observed {projected_clearance:.6g}, required "
            f"{required_clearance:.6g}. The required value is the larger of "
            "minimum_intercomponent_clearance and the grid-resolution floor."
        )

    validation_config = BoundaryValidationConfig(
        num_samples_per_component=config.validation_resolution,
        minimum_intercomponent_clearance=(
            config.resolved_minimum_intercomponent_clearance
        ),
        allow_nested_components=False,
        fourier_bandwidth=config.bandwidth,
    )
    method_config = MethodBConfig(
        bandwidth=config.bandwidth,
        arclength=ArcLengthConfig(
            dense_resolution=config.arclength_dense_resolution,
            refit_sample_count=None,
            validation_resolution=config.validation_resolution,
        ),
        validation=validation_config,
    )

    fit_started = perf_counter()
    parameterizations: list[PeriodicParameterization2D] = []
    projected_residuals: list[float] = []
    component_fit_seconds: list[float] = []
    for component in frontend.components:
        if not component.projection_passes:
            raise RuntimeError(
                f"Frontend component {component.component_id!r} has no projection diagnostics."
            )
        projection_residual = float(
            component.projection_passes[-1].maximum_residual
        )
        component_started = perf_counter()
        try:
            fit = fit_method_b(
                component,
                config=method_config,
                component_id=component.component_id,
                source_identifier=source_identifier,
                projection_residual=projection_residual,
            )
        except (ArcLengthGeometryError, OrderedBoundaryValidationError) as exc:
            raise MultiComponentOrderedSDFGeometryError(
                f"Method B rejected component {component.component_id!r}: {exc}"
            ) from exc
        component_fit_seconds.append(perf_counter() - component_started)
        if fit.status != "success":
            reason = fit.failure_reason or "no failure reason was supplied"
            raise MultiComponentOrderedSDFGeometryError(
                f"Method B failed for component {component.component_id!r}: {reason}."
            )
        if fit.parameterization is None:
            raise RuntimeError(
                f"Method B returned no parameterization for {component.component_id!r}."
            )
        parameterizations.append(fit.parameterization)
        projected_residuals.append(projection_residual)
    fit_seconds = perf_counter() - fit_started

    parameterization = OrderedBoundaryParameterization2D(tuple(parameterizations))
    topology_started = perf_counter()
    try:
        topology_report = validate_ordered_parameterization(
            parameterization,
            validation_config,
            raise_on_error=True,
        )
    except OrderedBoundaryValidationError as exc:
        raise MultiComponentOrderedSDFGeometryError(
            f"The fitted component topology is inadmissible: {exc}"
        ) from exc
    topology_seconds = perf_counter() - topology_started

    discretize_started = perf_counter()
    boundary = parameterization.discretize(
        resolved_node_counts,
        require_even=True,
    )
    discretize_seconds = perf_counter() - discretize_started

    resolved_required_intercomponent_clearance = None
    if boundary.num_components > 1:
        quadrature_clearance = (
            config.minimum_quadrature_clearance_in_weights
            * float(np.max(boundary.arc_length_weights))
        )
        resolved_required_intercomponent_clearance = max(
            config.resolved_minimum_intercomponent_clearance,
            quadrature_clearance,
        )
        observed_clearance = topology_report.minimum_intercomponent_clearance
        if (
            observed_clearance is None  # pragma: no cover - topology invariant
            or observed_clearance <= resolved_required_intercomponent_clearance
        ):
            raise MultiComponentOrderedSDFGeometryError(
                "The fitted components are not solver-ready for ordinary "
                "cross-component quadrature: minimum clearance "
                f"{observed_clearance!r} must exceed the resolved requirement "
                f"{resolved_required_intercomponent_clearance:.6g}, including "
                "minimum_quadrature_clearance_in_weights times the largest "
                "boundary arc-length weight."
            )

    residual_started = perf_counter()
    readiness_node_counts = tuple(
        max(node_count, config.validation_resolution)
        for node_count in resolved_node_counts
    )
    readiness_boundary = parameterization.discretize(readiness_node_counts)
    points = np.array(readiness_boundary.points, dtype=np.float64, copy=True)
    curve_values = np.asarray(field.value(points), dtype=np.float64)
    if curve_values.shape != (readiness_boundary.num_nodes,):
        raise RuntimeError(
            "The model returned an unexpected value shape on the readiness grid: "
            f"expected {(readiness_boundary.num_nodes,)}, received "
            f"{curve_values.shape}."
        )
    if not np.all(np.isfinite(curve_values)):
        raise ValueError("The model returned non-finite readiness-grid values.")
    gradients = np.asarray(field.gradient(points), dtype=np.float64)
    if gradients.shape != (readiness_boundary.num_nodes, 2) or not np.all(
        np.isfinite(gradients)
    ):
        raise ValueError("The model returned invalid readiness-grid gradients.")
    gradient_norms = np.linalg.norm(gradients, axis=1)
    if np.any(gradient_norms <= np.finfo(np.float64).tiny):
        raise MultiComponentOrderedSDFGeometryError(
            "Every ordered zero contour needs a nonzero field gradient."
        )

    component_diagnostics = []
    for index, (frontend_component, curve, readiness_slice) in enumerate(
        zip(
            frontend.components,
            boundary.components,
            readiness_boundary.component_slices,
        )
    ):
        values = curve_values[readiness_slice]
        norms = gradient_norms[readiness_slice]
        minimum_speed = float(np.min(curve.speeds))
        maximum_speed = float(np.max(curve.speeds))
        minimum_field_gradient_norm = float(np.min(norms))
        maximum_field_gradient_norm = float(np.max(norms))
        maximum_normalized_curve_residual = float(
            np.max(np.abs(values) / norms)
        )
        if minimum_field_gradient_norm < config.minimum_boundary_gradient_norm:
            raise MultiComponentOrderedSDFGeometryError(
                f"Fitted component {curve.component_id!r} is not solver-ready: "
                f"minimum field-gradient norm {minimum_field_gradient_norm:.6g} "
                "is below minimum_boundary_gradient_norm "
                f"{config.minimum_boundary_gradient_norm:.6g}."
            )
        # Extraction canonicalizes every loop to CCW, which by itself loses
        # the field's material-side convention. A sign-reversed field has the
        # same zero set, |phi| residual, and gradient norm, but represents an
        # exterior negative domain rather than an inclusion. Check the signed
        # direction on the dense readiness grid before assigning interiors.
        normal_alignment = np.einsum(
            "nd,nd->n",
            gradients[readiness_slice] / norms[:, None],
            readiness_boundary.normals[readiness_slice],
        )
        if np.any(normal_alignment <= 0.0):
            raise MultiComponentOrderedSDFGeometryError(
                f"Fitted component {curve.component_id!r} violates the "
                "negative_inside sign convention: the field gradient must "
                "have a positive projection onto the outward boundary normal "
                "at every readiness sample."
            )
        if (
            maximum_normalized_curve_residual
            > config.maximum_normalized_curve_residual
        ):
            raise MultiComponentOrderedSDFGeometryError(
                f"Fitted component {curve.component_id!r} is not solver-ready: "
                "maximum normalized curve residual "
                f"{maximum_normalized_curve_residual:.6g} exceeds "
                "maximum_normalized_curve_residual "
                f"{config.maximum_normalized_curve_residual:.6g}."
            )
        component_diagnostics.append(
            MultiComponentGeometryDiagnostics(
                component_id=curve.component_id,
                num_nodes=curve.num_nodes,
                projected_sample_count=int(
                    frontend_component.projected_points.shape[0]
                ),
                readiness_sample_count=readiness_node_counts[index],
                maximum_projected_sdf_residual=projected_residuals[index],
                minimum_projected_field_gradient_norm=(
                    projected_gradient_minima[index]
                ),
                maximum_projected_field_gradient_norm=(
                    projected_gradient_maxima[index]
                ),
                maximum_curve_sdf_residual=float(np.max(np.abs(values))),
                maximum_normalized_curve_residual=(
                    maximum_normalized_curve_residual
                ),
                minimum_field_gradient_norm=minimum_field_gradient_norm,
                maximum_field_gradient_norm=maximum_field_gradient_norm,
                minimum_speed=minimum_speed,
                maximum_speed=maximum_speed,
                speed_ratio=maximum_speed / minimum_speed,
                signed_area=float(curve.signed_area),
                perimeter=float(curve.perimeter),
                centroid=_polygon_centroid(curve.points),
                bounding_box_min=tuple(
                    float(value) for value in np.min(curve.points, axis=0)
                ),
                bounding_box_max=tuple(
                    float(value) for value in np.max(curve.points, axis=0)
                ),
                fit_seconds=component_fit_seconds[index],
            )
        )
    residual_seconds = perf_counter() - residual_started

    grid_parity_confirmation = None
    if config.confirm_grid_parity:
        confirmation_grid_shape = config.resolved_confirmation_grid_shape
        if confirmation_grid_shape is None:  # pragma: no cover - config invariant
            raise RuntimeError("The enabled grid confirmation has no grid shape.")
        confirmation_config = replace(
            config,
            grid_shape=confirmation_grid_shape,
            confirm_grid_parity=False,
            confirmation_grid_shape=None,
        )
        confirmation_started = perf_counter()
        try:
            confirmation_build = _build_multicomponent_ordered_sdf_geometry(
                model,
                confirmation_config,
            )
        except MultiComponentOrderedSDFGeometryError as exc:
            raise MultiComponentOrderedSDFGeometryError(
                "Independent grid-parity confirmation on grid "
                f"{confirmation_grid_shape} rejected the primary geometry: {exc}"
            ) from exc
        confirmation_seconds = perf_counter() - confirmation_started
        if confirmation_build.num_components != boundary.num_components:
            raise MultiComponentOrderedSDFGeometryError(
                "Independent grid-parity confirmation found an inconsistent "
                "component count: primary grid "
                f"{config.grid_shape} found {boundary.num_components}, while "
                f"confirmation grid {confirmation_grid_shape} found "
                f"{confirmation_build.num_components}."
            )
        matched_indices, matched_distances = _match_component_geometries(
            parameterization,
            confirmation_build.parameterization,
            primary_node_counts=resolved_node_counts,
            confirmation_node_counts=confirmation_build.resolved_node_counts,
            minimum_resolution=config.validation_resolution,
        )
        grid_geometry_tolerance = (
            config.resolved_grid_confirmation_geometry_tolerance
        )
        if grid_geometry_tolerance is None:  # pragma: no cover - config invariant
            raise RuntimeError(
                "The enabled grid confirmation has no geometry tolerance."
            )
        geometry_tolerance_cap = (
            config.resolved_grid_confirmation_geometry_tolerance_cap
        )
        if geometry_tolerance_cap is None:  # pragma: no cover - config invariant
            raise RuntimeError(
                "The enabled grid confirmation has no geometry tolerance cap."
            )
        primary_component_residuals = tuple(
            item.maximum_normalized_curve_residual
            for item in component_diagnostics
        )
        matched_confirmation_component_residuals = tuple(
            confirmation_build.component_diagnostics[confirmation_index]
            .maximum_normalized_curve_residual
            for confirmation_index in matched_indices
        )
        matched_component_tolerances = tuple(
            max(
                grid_geometry_tolerance,
                min(
                    config.grid_confirmation_residual_tolerance_factor
                    * max(primary_residual, confirmation_residual),
                    geometry_tolerance_cap,
                ),
            )
            for primary_residual, confirmation_residual in zip(
                primary_component_residuals,
                matched_confirmation_component_residuals,
            )
        )
        violating_indices = tuple(
            index
            for index, (distance, tolerance) in enumerate(
                zip(matched_distances, matched_component_tolerances)
            )
            if distance > tolerance
        )
        if violating_indices:
            worst_primary_index = max(
                violating_indices,
                key=lambda index: (
                    matched_distances[index] / matched_component_tolerances[index]
                ),
            )
            worst_distance = matched_distances[worst_primary_index]
            worst_tolerance = matched_component_tolerances[worst_primary_index]
            worst_confirmation_index = matched_indices[worst_primary_index]
            raise MultiComponentOrderedSDFGeometryError(
                "Independent grid-parity confirmation found inconsistent "
                "component geometry despite an equal component count: primary "
                f"component {worst_primary_index} matched confirmation component "
                f"{worst_confirmation_index} at sampled symmetric Hausdorff "
                f"distance {worst_distance:.6g}, exceeding its pair-local "
                f"grid/residual tolerance {worst_tolerance:.6g}. This is a resolution "
                "confidence failure."
            )
        primary_normalized_residual = max(primary_component_residuals)
        confirmation_normalized_residual = max(
            matched_confirmation_component_residuals
        )
        grid_parity_confirmation = GridParityConfirmationDiagnostics(
            primary_grid_shape=config.grid_shape,
            confirmation_grid_shape=confirmation_grid_shape,
            primary_num_components=boundary.num_components,
            confirmation_num_components=confirmation_build.num_components,
            primary_minimum_projected_field_gradient_norm=min(
                item.minimum_projected_field_gradient_norm
                for item in component_diagnostics
            ),
            confirmation_minimum_projected_field_gradient_norm=(
                confirmation_build.minimum_projected_field_gradient_norm
            ),
            primary_minimum_field_gradient_norm=min(
                item.minimum_field_gradient_norm
                for item in component_diagnostics
            ),
            confirmation_minimum_field_gradient_norm=(
                confirmation_build.minimum_field_gradient_norm
            ),
            primary_maximum_normalized_curve_residual=primary_normalized_residual,
            confirmation_maximum_normalized_curve_residual=(
                confirmation_normalized_residual
            ),
            primary_to_confirmation_component_indices=matched_indices,
            matched_component_distances=matched_distances,
            primary_component_normalized_curve_residuals=(
                primary_component_residuals
            ),
            matched_confirmation_component_normalized_curve_residuals=(
                matched_confirmation_component_residuals
            ),
            matched_component_tolerances=matched_component_tolerances,
            confirmation_seconds=confirmation_seconds,
        )

    return MultiComponentOrderedSDFGeometryBuild(
        boundary=boundary,
        parameterization=parameterization,
        topology_report=topology_report,
        component_diagnostics=tuple(component_diagnostics),
        frontend_seconds=float(frontend_seconds),
        fit_seconds=float(fit_seconds),
        topology_validation_seconds=float(topology_seconds),
        discretize_seconds=float(discretize_seconds),
        residual_validation_seconds=float(residual_seconds),
        total_seconds=float(perf_counter() - total_started),
        config=config,
        resolved_node_counts=resolved_node_counts,
        resolved_required_intercomponent_clearance=(
            resolved_required_intercomponent_clearance
        ),
        grid_parity_confirmation=grid_parity_confirmation,
    )


def build_multicomponent_ordered_sdf_geometry(
    model: Any,
    config: MultiComponentOrderedSDFGeometryConfig,
) -> MultiComponentOrderedSDFGeometryBuild:
    """Build every zero-set loop and confirm it on an independent grid.

    The component count is discovered rather than configured by default.  If
    grid-parity confirmation is enabled (the production default), a second
    complete build runs with opposite Cartesian-grid point-count parity.  Both
    passes must independently satisfy extraction, regularity, topology, and
    residual readiness checks and must discover the same number of components.
    """

    return _build_multicomponent_ordered_sdf_geometry(model, config)


__all__ = [
    "GridParityConfirmationDiagnostics",
    "MultiComponentGeometryDiagnostics",
    "MultiComponentOrderedSDFGeometryBuild",
    "MultiComponentOrderedSDFGeometryConfig",
    "MultiComponentOrderedSDFGeometryError",
    "build_multicomponent_ordered_sdf_geometry",
]
