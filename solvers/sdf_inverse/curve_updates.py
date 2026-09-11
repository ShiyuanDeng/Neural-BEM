"""Phase-preserving normal-mode updates of an ordered inverse boundary.

The neural inverse uses :class:`~sdf_inverse.neural_optimization.SmoothNormalModeUpdate2D`
to define a small geometry search space.  Re-extracting every member of that
space from a dense implicit-field grid is unnecessary: once a validated
``PeriodicCurve2D`` is available, the same modal values can be interpreted
directly as signed outward-normal displacements of that curve.

This module deliberately contains no Torch or forward-solver dependency.  A
trial update is refitted in the existing Fourier geometry bandwidth and
checked as a continuous periodic parameterization.  Cheap probes retain the
same node phase; a selected accepted candidate can additionally be refitted on
a uniform arc-length map before it becomes the next canonical state.  The MLP
may therefore be distilled from that curve without making its extraction
error part of every finite-difference probe.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import operator

import numpy as np

from ordered_boundary import (
    BoundaryValidationConfig,
    CurveProvenance2D,
    OrderedBoundaryValidationError,
    PeriodicCurve2D,
    PeriodicParameterization2D,
    sampled_self_intersection_count,
    validate_periodic_parameterization,
)
from sdf_to_ordered_boundary import (
    ArcLengthGeometryError,
    fit_fourier_least_squares,
    reparameterize_by_arclength,
)

from .geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError


def _radial_parameter_count(maximum_mode: int) -> int:
    """Gauge-fixed radial parameters through ``maximum_mode``.

    The ordering is ``mean radius, center x, center y, cos(2t), sin(2t), ...``.
    Exact center translation replaces the nearly dependent radial first
    harmonic, so the count remains ``1 + 2 K`` just like the legacy normal
    basis.
    """

    mode = _positive_integer(maximum_mode, name="maximum_mode")
    return 1 + 2 * mode


def _positive_integer(value: object, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < 1:
        raise ValueError(f"{name} must be positive.")
    return int(result)


def _finite_points(points: object, *, name: str) -> np.ndarray:
    if np.iscomplexobj(points):
        raise ValueError(f"{name} must be real-valued.")
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError(f"{name} must have shape (N, 2).")
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{name} must contain only finite values.")
    return values


def smooth_normal_mode_values(
    points: object,
    *,
    center: tuple[float, float] | np.ndarray,
    radius_scale: float,
    maximum_mode: int,
) -> np.ndarray:
    """Evaluate the neural inverse's bounded real normal-mode basis.

    The returned columns are ``1, cos(t), sin(t), ...`` in the ordering used
    by ``SmoothNormalModeUpdate2D``, including that class's smooth radial
    envelopes.  On the reference circle the columns reduce exactly to the
    ordinary real angular harmonics.  Away from it they remain finite at the
    centre and decay at large radius.
    """

    point_values = _finite_points(points, name="points")
    if np.iscomplexobj(center):
        raise ValueError("center must be real-valued.")
    center_values = np.asarray(center, dtype=np.float64)
    if center_values.shape != (2,) or not np.all(np.isfinite(center_values)):
        raise ValueError("center must contain two finite coordinates.")
    scale = float(radius_scale)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("radius_scale must be finite and positive.")
    mode_limit = _positive_integer(maximum_mode, name="maximum_mode")

    delta = (point_values - center_values[None, :]) / scale
    x = delta[:, 0]
    y = delta[:, 1]
    radius_squared = x * x + y * y
    columns = [np.exp(-0.5 * (radius_squared - 1.0) ** 2)]
    real = np.ones_like(x)
    imaginary = np.zeros_like(x)
    for mode in range(1, mode_limit + 1):
        real, imaginary = real * x - imaginary * y, real * y + imaginary * x
        exponent = np.clip(0.5 * mode * (1.0 - radius_squared), -80.0, 40.0)
        envelope = np.exp(exponent)
        columns.extend((real * envelope, imaginary * envelope))
    values = np.column_stack(columns)
    if not np.all(np.isfinite(values)):
        raise FloatingPointError("normal-mode basis evaluation produced non-finite values.")
    values.setflags(write=False)
    return values


@dataclass(frozen=True)
class RadialFourierCurveState:
    """Authoritative state for a gauge-fixed star-shaped Fourier curve.

    ``radius_cosine_coefficients`` and ``radius_sine_coefficients`` contain
    modes ``0..K``.  The mode-zero cosine coefficient is the mean radius and
    the mode-zero sine coefficient is zero.  Both mode-one coefficients are
    fixed to zero: the corresponding two degrees of freedom are represented
    by exact Cartesian translation of ``center``.  This removes the local
    translation/first-harmonic ambiguity while retaining ``1 + 2 K`` active
    parameters.

    The state, rather than a successively refitted node curve, is advanced by
    accepted inverse steps.  Rebuilding a curve from it is therefore a true
    finite-dimensional retraction and cannot accumulate unrepresented radial
    modes across iterations.
    """

    center: np.ndarray
    radius_cosine_coefficients: np.ndarray
    radius_sine_coefficients: np.ndarray
    component_id: str
    name: str = "radial_fourier_inverse_curve"
    source_identifier: str | None = None
    initial_projection_rms_m: float = 0.0
    initial_projection_maximum_m: float = 0.0

    def __post_init__(self) -> None:
        if np.iscomplexobj(self.center):
            raise ValueError("center must be real-valued.")
        center = np.array(self.center, dtype=np.float64, copy=True)
        if center.shape != (2,) or not np.all(np.isfinite(center)):
            raise ValueError("center must contain two finite coordinates.")
        cosine = np.array(
            self.radius_cosine_coefficients, dtype=np.float64, copy=True
        )
        sine = np.array(self.radius_sine_coefficients, dtype=np.float64, copy=True)
        if cosine.ndim != 1 or cosine.size < 2:
            raise ValueError(
                "radius_cosine_coefficients must contain modes 0..K with K >= 1."
            )
        if sine.shape != cosine.shape:
            raise ValueError(
                "radius_sine_coefficients must match radius_cosine_coefficients."
            )
        if not np.all(np.isfinite(cosine)) or not np.all(np.isfinite(sine)):
            raise ValueError("radial Fourier coefficients must be finite.")
        tolerance = 64.0 * np.finfo(np.float64).eps * max(abs(cosine[0]), 1.0)
        if abs(sine[0]) > tolerance:
            raise ValueError("the mode-zero sine coefficient must be zero.")
        if abs(cosine[1]) > tolerance or abs(sine[1]) > tolerance:
            raise ValueError(
                "radial mode one is gauge-fixed to zero; use center for translation."
            )
        sine[0] = 0.0
        cosine[1] = 0.0
        sine[1] = 0.0
        lower_bound = float(
            cosine[0] - np.sum(np.hypot(cosine[2:], sine[2:]))
        )
        if not math.isfinite(lower_bound) or lower_bound <= 0.0:
            raise ValueError(
                "radial Fourier coefficients do not certify a positive radius."
            )
        for field_name in (
            "initial_projection_rms_m",
            "initial_projection_maximum_m",
        ):
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be finite and non-negative.")
            object.__setattr__(self, field_name, value)
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be a non-empty string.")
        center.setflags(write=False)
        cosine.setflags(write=False)
        sine.setflags(write=False)
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "radius_cosine_coefficients", cosine)
        object.__setattr__(self, "radius_sine_coefficients", sine)
        object.__setattr__(self, "component_id", self.component_id.strip())
        object.__setattr__(self, "name", str(self.name))
        if self.source_identifier is not None:
            object.__setattr__(self, "source_identifier", str(self.source_identifier))

    @property
    def maximum_mode(self) -> int:
        return int(self.radius_cosine_coefficients.size - 1)

    @property
    def parameter_count(self) -> int:
        return _radial_parameter_count(self.maximum_mode)

    @property
    def mean_radius_m(self) -> float:
        return float(self.radius_cosine_coefficients[0])

    @property
    def minimum_radius_lower_bound_m(self) -> float:
        """Coefficient-norm lower bound, certifying ``r(theta) > 0``."""

        return float(
            self.radius_cosine_coefficients[0]
            - np.sum(
                np.hypot(
                    self.radius_cosine_coefficients[2:],
                    self.radius_sine_coefficients[2:],
                )
            )
        )

    def incremented(
        self, coefficients: object, *, maximum_mode: int | None = None
    ) -> "RadialFourierCurveState":
        """Return the state after one additive gauge-fixed radial step."""

        active_mode = (
            self.maximum_mode
            if maximum_mode is None
            else _positive_integer(maximum_mode, name="maximum_mode")
        )
        if active_mode > self.maximum_mode:
            raise ValueError("maximum_mode cannot exceed the state's maximum mode.")
        if np.iscomplexobj(coefficients):
            raise ValueError("coefficients must be real-valued.")
        values = np.asarray(coefficients, dtype=np.float64)
        expected = _radial_parameter_count(active_mode)
        if values.shape != (expected,) or not np.all(np.isfinite(values)):
            raise ValueError(f"coefficients must contain {expected} finite values.")

        center = np.asarray(self.center).copy()
        center += values[1:3]
        cosine = np.asarray(self.radius_cosine_coefficients).copy()
        sine = np.asarray(self.radius_sine_coefficients).copy()
        cosine[0] += values[0]
        for mode in range(2, active_mode + 1):
            cosine[mode] += values[2 * mode - 1]
            sine[mode] += values[2 * mode]
        return RadialFourierCurveState(
            center=center,
            radius_cosine_coefficients=cosine,
            radius_sine_coefficients=sine,
            component_id=self.component_id,
            name=self.name,
            source_identifier=self.source_identifier,
            initial_projection_rms_m=self.initial_projection_rms_m,
            initial_projection_maximum_m=self.initial_projection_maximum_m,
        )


def radial_fourier_displacement_basis(
    parameters: object, *, maximum_mode: int
) -> np.ndarray:
    """Vector displacement basis for the gauge-fixed radial chart.

    The result has shape ``parameters.shape + (1 + 2 K, 2)``.  Contracting
    its penultimate axis with an increment gives the exact Cartesian point
    displacement at fixed polar angle, including exact center translation.
    """

    if np.iscomplexobj(parameters):
        raise ValueError("parameters must be real-valued.")
    angles = np.asarray(parameters, dtype=np.float64)
    if not np.all(np.isfinite(angles)):
        raise ValueError("parameters must contain only finite values.")
    mode_limit = _positive_integer(maximum_mode, name="maximum_mode")
    radial = np.stack((np.cos(angles), np.sin(angles)), axis=-1)
    result = np.zeros(
        angles.shape + (_radial_parameter_count(mode_limit), 2),
        dtype=np.float64,
    )
    result[..., 0, :] = radial
    result[..., 1, 0] = 1.0
    result[..., 2, 1] = 1.0
    for mode in range(2, mode_limit + 1):
        result[..., 2 * mode - 1, :] = (
            np.cos(mode * angles)[..., None] * radial
        )
        result[..., 2 * mode, :] = np.sin(mode * angles)[..., None] * radial
    result.setflags(write=False)
    return result


def fit_radial_fourier_curve_state(
    curve: PeriodicCurve2D,
    *,
    maximum_mode: int,
    center: tuple[float, float] | np.ndarray | None = None,
) -> RadialFourierCurveState:
    """Least-squares project one star-shaped curve into the radial chart.

    This is the sole allowed projection of an off-manifold initial contour.
    Subsequent accepted states must be advanced with :meth:`incremented`, not
    re-fitted from their nodes, so projection error cannot accumulate.
    """

    if not isinstance(curve, PeriodicCurve2D):
        raise TypeError("curve must be a PeriodicCurve2D.")
    mode_limit = _positive_integer(maximum_mode, name="maximum_mode")
    if center is None:
        center_values = np.mean(np.asarray(curve.points), axis=0)
    else:
        if np.iscomplexobj(center):
            raise ValueError("center must be real-valued.")
        center_values = np.asarray(center, dtype=np.float64)
        if center_values.shape != (2,) or not np.all(np.isfinite(center_values)):
            raise ValueError("center must contain two finite coordinates.")
    delta = np.asarray(curve.points) - center_values[None, :]
    radii = np.linalg.norm(delta, axis=1)
    if np.any(radii <= 64.0 * np.finfo(np.float64).eps):
        raise OrderedSDFGeometryError(
            "The supplied curve is not radial about the requested center."
        )
    angles = np.unwrap(np.arctan2(delta[:, 1], delta[:, 0]))
    angle_steps = np.diff(np.concatenate((angles, angles[:1] + 2.0 * np.pi)))
    if np.any(angle_steps <= 64.0 * np.finfo(np.float64).eps):
        raise OrderedSDFGeometryError(
            "The supplied curve is not a counterclockwise star-shaped radial graph."
        )

    columns = [np.ones(curve.num_nodes, dtype=np.float64)]
    for mode in range(2, mode_limit + 1):
        columns.extend((np.cos(mode * angles), np.sin(mode * angles)))
    design = np.column_stack(columns)
    if design.shape[0] <= design.shape[1]:
        raise ValueError(
            "curve nodes must outnumber the gauge-fixed radial coefficients."
        )
    fitted, _, rank, _ = np.linalg.lstsq(design, radii, rcond=None)
    if rank != design.shape[1]:
        raise OrderedSDFGeometryError(
            "The initial radial Fourier projection is rank deficient."
        )
    cosine = np.zeros(mode_limit + 1, dtype=np.float64)
    sine = np.zeros_like(cosine)
    cosine[0] = fitted[0]
    for mode in range(2, mode_limit + 1):
        cosine[mode] = fitted[2 * mode - 3]
        sine[mode] = fitted[2 * mode - 2]
    residual = radii - design @ fitted
    try:
        return RadialFourierCurveState(
            center=center_values,
            radius_cosine_coefficients=cosine,
            radius_sine_coefficients=sine,
            component_id=curve.component_id,
            name=curve.name,
            source_identifier=(
                curve.provenance.source_identifier
                if curve.provenance.source_identifier is not None
                else curve.component_id
            ),
            initial_projection_rms_m=float(np.sqrt(np.mean(residual * residual))),
            initial_projection_maximum_m=float(np.max(np.abs(residual))),
        )
    except ValueError as exc:
        raise OrderedSDFGeometryError(
            f"Initial radial Fourier projection is not admissible: {exc}"
        ) from exc


def _radial_parameterization(
    state: RadialFourierCurveState,
) -> PeriodicParameterization2D:
    cosine_coefficients = np.asarray(state.radius_cosine_coefficients)
    sine_coefficients = np.asarray(state.radius_sine_coefficients)
    modes = np.arange(state.maximum_mode + 1, dtype=np.float64)
    center = np.asarray(state.center)

    def evaluator(parameters: np.ndarray):
        phase = parameters[..., None] * modes
        cosine = np.cos(phase)
        sine = np.sin(phase)
        radius = np.einsum(
            "...k,k->...", cosine, cosine_coefficients
        ) + np.einsum("...k,k->...", sine, sine_coefficients)
        first = np.einsum(
            "...k,k->...", -sine * modes, cosine_coefficients
        ) + np.einsum("...k,k->...", cosine * modes, sine_coefficients)
        squared = modes * modes
        second = np.einsum(
            "...k,k->...", -cosine * squared, cosine_coefficients
        ) + np.einsum("...k,k->...", -sine * squared, sine_coefficients)
        cubed = squared * modes
        third = np.einsum(
            "...k,k->...", sine * cubed, cosine_coefficients
        ) + np.einsum("...k,k->...", -cosine * cubed, sine_coefficients)

        radial = np.stack((np.cos(parameters), np.sin(parameters)), axis=-1)
        angular = np.stack((-np.sin(parameters), np.cos(parameters)), axis=-1)
        points = center + radius[..., None] * radial
        d1 = first[..., None] * radial + radius[..., None] * angular
        d2 = (
            (second - radius)[..., None] * radial
            + 2.0 * first[..., None] * angular
        )
        d3 = (
            (third - 3.0 * first)[..., None] * radial
            + (3.0 * second - radius)[..., None] * angular
        )
        return points, d1, d2, d3

    return PeriodicParameterization2D(
        component_id=state.component_id,
        evaluator=evaluator,
        name=state.name,
        provenance=CurveProvenance2D(
            source_kind="direct_radial_fourier_retraction",
            source_identifier=state.source_identifier,
            projection_residual=state.initial_projection_rms_m,
        ),
    )


def radial_fourier_parameterization(
    state: RadialFourierCurveState,
) -> PeriodicParameterization2D:
    """Retain the state's continuous curve independently of a solver grid.

    Distance supervision, exports, and refinement audits can sample this exact
    radial Fourier representation without reconstructing an evaluator from
    the node-only ``PeriodicCurve2D`` contract.
    """

    if not isinstance(state, RadialFourierCurveState):
        raise TypeError("state must be a RadialFourierCurveState.")
    return _radial_parameterization(state)


def radial_fourier_state_curve(
    state: RadialFourierCurveState,
    *,
    geometry_config: OrderedSDFGeometryConfig,
    full_validation: bool = True,
) -> PeriodicCurve2D:
    """Build and validate the deterministic curve represented by ``state``."""

    if not isinstance(state, RadialFourierCurveState):
        raise TypeError("state must be a RadialFourierCurveState.")
    if not isinstance(geometry_config, OrderedSDFGeometryConfig):
        raise TypeError("geometry_config must be an OrderedSDFGeometryConfig.")
    if not isinstance(full_validation, (bool, np.bool_)):
        raise TypeError("full_validation must be bool.")
    # Multiplication of radius harmonics by (cos(theta), sin(theta)) raises
    # the Cartesian bandwidth from K to K+1.  The Method-B bandwidth in the
    # shared geometry config may be smaller, so its existing sampling checks
    # cannot certify this independently parameterized radial curve.
    minimum_resolution = 2 * (state.maximum_mode + 1) + 2
    for name in ("num_nodes", "validation_resolution"):
        if getattr(geometry_config, name) < minimum_resolution:
            raise ValueError(
                f"{name} must be at least {minimum_resolution} to sample the "
                "radial curve's Cartesian Fourier bandwidth without aliasing."
            )
    parameterization = _radial_parameterization(state)
    report = None
    if full_validation:
        try:
            report = validate_periodic_parameterization(
                parameterization,
                BoundaryValidationConfig(
                    num_samples_per_component=geometry_config.validation_resolution,
                    fourier_bandwidth=state.maximum_mode + 1,
                ),
                raise_on_error=True,
            )
        except OrderedBoundaryValidationError as exc:
            raise OrderedSDFGeometryError(
                f"Radial Fourier retraction produced an inadmissible contour: {exc}"
            ) from exc
    curve = parameterization.discretize(
        geometry_config.num_nodes, require_even=True
    )
    lower = np.asarray(geometry_config.bounds[0], dtype=np.float64)
    upper = np.asarray(geometry_config.bounds[1], dtype=np.float64)
    if report is None:
        audit_count = max(
            geometry_config.validation_resolution,
            64 * (state.maximum_mode + 1),
        )
        parameters = 2.0 * np.pi * np.arange(audit_count) / audit_count
        audit_points = parameterization.evaluate(parameters, wrap=False).points
        minimum = np.min(audit_points, axis=0)
        maximum = np.max(audit_points, axis=0)
    else:
        minimum = np.asarray(report.bounding_box_min, dtype=np.float64)
        maximum = np.asarray(report.bounding_box_max, dtype=np.float64)
    if np.any(minimum <= lower) or np.any(maximum >= upper):
        raise OrderedSDFGeometryError(
            "Radial Fourier retraction touches or leaves the configured geometry bounds."
        )
    if not full_validation and sampled_self_intersection_count(curve.points):
        raise OrderedSDFGeometryError(
            "Radial Fourier retraction has a solver-grid self-intersection."
        )
    return curve


@dataclass(frozen=True)
class DirectRadialFourierCurveUpdate:
    """One deterministic radial-state increment and its physical step audit."""

    state: RadialFourierCurveState
    curve: PeriodicCurve2D
    coefficients: np.ndarray
    maximum_displacement_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.state, RadialFourierCurveState):
            raise TypeError("state must be a RadialFourierCurveState.")
        if not isinstance(self.curve, PeriodicCurve2D):
            raise TypeError("curve must be a PeriodicCurve2D.")
        coefficients = np.array(self.coefficients, dtype=np.float64, copy=True)
        if coefficients.ndim != 1 or not np.all(np.isfinite(coefficients)):
            raise ValueError("coefficients must be a finite vector.")
        coefficients.setflags(write=False)
        displacement = float(self.maximum_displacement_m)
        if not math.isfinite(displacement) or displacement < 0.0:
            raise ValueError("maximum_displacement_m must be finite and non-negative.")
        object.__setattr__(self, "coefficients", coefficients)
        object.__setattr__(self, "maximum_displacement_m", displacement)

    @property
    def arclength_refit_rms_m(self) -> float:
        return 0.0

    @property
    def arclength_refit_maximum_m(self) -> float:
        return 0.0

    @property
    def arclength_speed_ratio_before(self) -> float:
        return float(np.max(self.curve.speeds) / np.min(self.curve.speeds))

    @property
    def arclength_speed_ratio_after(self) -> float:
        return self.arclength_speed_ratio_before


def apply_radial_fourier_update(
    state: RadialFourierCurveState,
    coefficients: object,
    *,
    maximum_mode: int,
    geometry_config: OrderedSDFGeometryConfig,
    full_validation: bool = True,
) -> DirectRadialFourierCurveUpdate:
    """Retract an increment in the authoritative radial Fourier state."""

    active_mode = _positive_integer(maximum_mode, name="maximum_mode")
    try:
        next_state = state.incremented(coefficients, maximum_mode=active_mode)
    except ValueError as exc:
        raise OrderedSDFGeometryError(
            f"Radial Fourier retraction is not admissible: {exc}"
        ) from exc
    curve = radial_fourier_state_curve(
        next_state,
        geometry_config=geometry_config,
        full_validation=full_validation,
    )
    values = np.asarray(coefficients, dtype=np.float64)
    audit_count = max(
        geometry_config.validation_resolution,
        64 * (active_mode + 1),
    )
    angles = 2.0 * np.pi * np.arange(audit_count, dtype=np.float64) / audit_count
    basis = radial_fourier_displacement_basis(
        angles, maximum_mode=active_mode
    )
    displacement = np.einsum("...pd,p->...d", basis, values)
    maximum_displacement = float(np.max(np.linalg.norm(displacement, axis=-1)))
    return DirectRadialFourierCurveUpdate(
        state=next_state,
        curve=curve,
        coefficients=values,
        maximum_displacement_m=maximum_displacement,
    )


@dataclass(frozen=True)
class DirectNormalModeCurveUpdate:
    """A validated direct curve update and its geometric fidelity audit."""

    curve: PeriodicCurve2D
    coefficients: np.ndarray
    mode_values: np.ndarray
    requested_normal_displacement_m: np.ndarray
    realized_normal_displacement_m: np.ndarray
    realized_tangential_displacement_m: np.ndarray
    fourier_refit_rms_m: float
    fourier_refit_maximum_m: float
    arclength_refit_rms_m: float
    arclength_refit_maximum_m: float
    arclength_speed_ratio_before: float
    arclength_speed_ratio_after: float

    def __post_init__(self) -> None:
        if not isinstance(self.curve, PeriodicCurve2D):
            raise TypeError("curve must be a PeriodicCurve2D.")
        arrays: dict[str, np.ndarray] = {}
        for name, dimension in (
            ("coefficients", 1),
            ("mode_values", 2),
            ("requested_normal_displacement_m", 1),
            ("realized_normal_displacement_m", 1),
            ("realized_tangential_displacement_m", 1),
        ):
            values = np.array(getattr(self, name), dtype=np.float64, copy=True)
            if values.ndim != dimension or not np.all(np.isfinite(values)):
                raise ValueError(f"{name} must be a finite {dimension}-D array.")
            values.setflags(write=False)
            arrays[name] = values
        node_count = arrays["requested_normal_displacement_m"].size
        if arrays["mode_values"].shape != (node_count, arrays["coefficients"].size):
            raise ValueError("mode_values shape must match the node and coefficient counts.")
        for name in (
            "realized_normal_displacement_m",
            "realized_tangential_displacement_m",
        ):
            if arrays[name].shape != (node_count,):
                raise ValueError(f"{name} must match the requested displacement shape.")
        for name, values in arrays.items():
            object.__setattr__(self, name, values)
        for name in (
            "fourier_refit_rms_m",
            "fourier_refit_maximum_m",
            "arclength_refit_rms_m",
            "arclength_refit_maximum_m",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)
        for name in (
            "arclength_speed_ratio_before",
            "arclength_speed_ratio_after",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 1.0:
                raise ValueError(f"{name} must be finite and at least one.")
            object.__setattr__(self, name, value)

    @property
    def maximum_requested_displacement_m(self) -> float:
        return float(np.max(np.abs(self.requested_normal_displacement_m)))

    @property
    def maximum_normal_displacement_error_m(self) -> float:
        return float(
            np.max(
                np.abs(
                    self.realized_normal_displacement_m
                    - self.requested_normal_displacement_m
                )
            )
        )

    @property
    def maximum_tangential_displacement_m(self) -> float:
        return float(np.max(np.abs(self.realized_tangential_displacement_m)))


def apply_normal_mode_update(
    curve: PeriodicCurve2D,
    coefficients: object,
    *,
    center: tuple[float, float] | np.ndarray,
    radius_scale: float,
    maximum_mode: int,
    geometry_config: OrderedSDFGeometryConfig,
    full_validation: bool = True,
    reparameterize_arclength: bool = False,
) -> DirectNormalModeCurveUpdate:
    """Apply modal coefficients as metres of outward normal curve motion.

    For a negative-inside signed-distance field ``phi`` the corresponding
    implicit update is ``phi_new = phi - B c``.  Linearizing its zero set gives
    ``delta_n = B c / |grad(phi)|``.  The accepted neural field is explicitly
    re-distanced, so ``|grad(phi)| ~= 1`` and a positive coefficient means an
    outward displacement.  This direct representation makes that intended
    metre scaling exact: ``delta_n := B c``.

    By default the displaced nodes are Fourier-refitted without arc-length
    reparameterization.  This phase-preserving behavior remains useful for
    finite-difference probes whose coefficients are defined on the current
    canonical node phase.  ``reparameterize_arclength=True`` performs a second
    Fourier refit on the shared numerical arc-length map.  It preserves the
    period, seam, node count, and orientation while restoring approximately
    uniform speed before an accepted curve becomes the next canonical state.

    ``full_validation=False`` is the finite-difference probe path: it checks
    the actual solver-node polygon, bounds, and regular node jets but skips the
    quadratic dense continuous self-intersection audit.  A probe selected by
    the line search must be rebuilt with the default full validation before it
    may become an accepted state.
    """

    if not isinstance(curve, PeriodicCurve2D):
        raise TypeError("curve must be a PeriodicCurve2D.")
    if not isinstance(geometry_config, OrderedSDFGeometryConfig):
        raise TypeError("geometry_config must be an OrderedSDFGeometryConfig.")
    if not isinstance(full_validation, (bool, np.bool_)):
        raise TypeError("full_validation must be bool.")
    if not isinstance(reparameterize_arclength, (bool, np.bool_)):
        raise TypeError("reparameterize_arclength must be bool.")
    if curve.num_nodes != geometry_config.num_nodes:
        raise ValueError(
            "curve.num_nodes must equal geometry_config.num_nodes so direct "
            "updates preserve the canonical solver grid."
        )
    mode_limit = _positive_integer(maximum_mode, name="maximum_mode")
    expected_count = 1 + 2 * mode_limit
    if np.iscomplexobj(coefficients):
        raise ValueError("coefficients must be real-valued.")
    coefficient_values = np.asarray(coefficients, dtype=np.float64)
    if coefficient_values.shape != (expected_count,) or not np.all(
        np.isfinite(coefficient_values)
    ):
        raise ValueError(
            f"coefficients must contain {expected_count} finite values."
        )

    basis = smooth_normal_mode_values(
        curve.points,
        center=center,
        radius_scale=radius_scale,
        maximum_mode=mode_limit,
    )
    requested = basis @ coefficient_values
    displaced_points = (
        np.asarray(curve.points, dtype=np.float64)
        + requested[:, None] * np.asarray(curve.normals, dtype=np.float64)
    )

    initial_provenance = CurveProvenance2D(
        source_kind="direct_normal_mode_update",
        source_identifier=(
            curve.provenance.source_identifier
            if curve.provenance.source_identifier is not None
            else curve.component_id
        ),
    )
    initial_fit = fit_fourier_least_squares(
        curve.parameters,
        displaced_points,
        bandwidth=geometry_config.bandwidth,
        component_id=curve.component_id,
        name=curve.name,
        period=curve.period,
        parameter_origin=curve.parameter_origin,
        provenance=initial_provenance,
    )
    final_boundary = initial_fit.boundary
    parameterization = final_boundary.to_parameterization()
    phase_curve = parameterization.discretize(curve.num_nodes, require_even=True)
    phase_speed_ratio = float(np.max(phase_curve.speeds) / np.min(phase_curve.speeds))
    arclength_refit_rms = 0.0
    arclength_refit_maximum = 0.0
    arclength_speed_ratio_before = phase_speed_ratio
    arclength_speed_ratio_after = phase_speed_ratio
    if reparameterize_arclength:
        final_fit_holder = []

        def refit_factory(
            refit_parameters: np.ndarray, refit_points: np.ndarray
        ):
            refit = fit_fourier_least_squares(
                refit_parameters,
                refit_points,
                bandwidth=geometry_config.bandwidth,
                component_id=curve.component_id,
                name=curve.name,
                period=curve.period,
                parameter_origin=curve.parameter_origin,
                provenance=initial_provenance,
            )
            final_fit_holder.append(refit)
            return refit.boundary

        try:
            arclength_result = reparameterize_by_arclength(
                parameterization,
                refit_factory,
                dense_n=geometry_config.arclength_dense_resolution,
                output_n=geometry_config.projected_samples,
                validation_n=geometry_config.validation_resolution,
            )
        except ArcLengthGeometryError as exc:
            raise OrderedSDFGeometryError(
                "Direct normal-mode update could not be reparameterized by "
                f"arc length: {exc}"
            ) from exc
        if len(final_fit_holder) != 1:
            raise RuntimeError(
                "Arc-length refit factory was expected to run exactly once."
            )
        final_boundary = arclength_result.representation
        arclength_refit_rms = arclength_result.diagnostics.rms_refit_displacement
        arclength_refit_maximum = (
            arclength_result.diagnostics.maximum_refit_displacement
        )
        arclength_speed_ratio_before = arclength_result.diagnostics.speed_ratio_before
        arclength_speed_ratio_after = arclength_result.diagnostics.speed_ratio_after

    provenance = CurveProvenance2D(
        source_kind="direct_normal_mode_update",
        source_identifier=initial_provenance.source_identifier,
        fit_residual=(
            arclength_refit_rms
            if reparameterize_arclength
            else initial_fit.residual.rms
        ),
    )
    parameterization = final_boundary.with_provenance(provenance).to_parameterization()
    report = None
    if full_validation:
        validation_config = BoundaryValidationConfig(
            num_samples_per_component=geometry_config.validation_resolution,
            fourier_bandwidth=geometry_config.bandwidth,
        )
        try:
            report = validate_periodic_parameterization(
                parameterization,
                validation_config,
                raise_on_error=True,
            )
        except OrderedBoundaryValidationError as exc:
            raise OrderedSDFGeometryError(
                f"Direct normal-mode update produced an inadmissible contour: {exc}"
            ) from exc

    updated_curve = parameterization.discretize(curve.num_nodes, require_even=True)
    if not np.array_equal(updated_curve.parameters, curve.parameters):
        raise RuntimeError("Direct curve update changed the canonical periodic node phase.")
    if updated_curve.orientation != curve.orientation:
        raise OrderedSDFGeometryError(
            "Direct normal-mode update changed the canonical curve orientation."
        )

    lower = np.asarray(geometry_config.bounds[0], dtype=np.float64)
    upper = np.asarray(geometry_config.bounds[1], dtype=np.float64)
    if report is None:
        minimum = np.min(updated_curve.points, axis=0)
        maximum = np.max(updated_curve.points, axis=0)
    else:
        minimum = np.asarray(report.bounding_box_min, dtype=np.float64)
        maximum = np.asarray(report.bounding_box_max, dtype=np.float64)
    if np.any(minimum <= lower) or np.any(maximum >= upper):
        raise OrderedSDFGeometryError(
            "Direct normal-mode update touches or leaves the configured geometry bounds."
        )
    if not full_validation:
        intersections = sampled_self_intersection_count(updated_curve.points)
        if intersections:
            raise OrderedSDFGeometryError(
                "Direct normal-mode probe has "
                f"{intersections} solver-grid self-intersection(s)."
            )

    # Audit the phase-preserving first fit at the original nodes.  Arc-length
    # redistribution deliberately changes later node correspondences, so it
    # must not contaminate the normal-mode fidelity diagnostic.
    realized_delta = np.asarray(phase_curve.points) - np.asarray(curve.points)
    realized_normal = np.sum(realized_delta * np.asarray(curve.normals), axis=1)
    realized_tangential = np.sum(realized_delta * np.asarray(curve.tangents), axis=1)
    return DirectNormalModeCurveUpdate(
        curve=updated_curve,
        coefficients=coefficient_values,
        mode_values=basis,
        requested_normal_displacement_m=requested,
        realized_normal_displacement_m=realized_normal,
        realized_tangential_displacement_m=realized_tangential,
        fourier_refit_rms_m=initial_fit.residual.rms,
        fourier_refit_maximum_m=initial_fit.residual.maximum,
        arclength_refit_rms_m=arclength_refit_rms,
        arclength_refit_maximum_m=arclength_refit_maximum,
        arclength_speed_ratio_before=arclength_speed_ratio_before,
        arclength_speed_ratio_after=arclength_speed_ratio_after,
    )


__all__ = [
    "DirectNormalModeCurveUpdate",
    "DirectRadialFourierCurveUpdate",
    "RadialFourierCurveState",
    "apply_normal_mode_update",
    "apply_radial_fourier_update",
    "fit_radial_fourier_curve_state",
    "radial_fourier_displacement_basis",
    "radial_fourier_parameterization",
    "radial_fourier_state_curve",
    "smooth_normal_mode_values",
]


# ---------------------------------------------------------------------------
# Cartesian Fourier chart
#
# The radial chart above is gauge-fixed by construction: its parameter is the
# polar angle, so it carries no reparameterization freedom.  The Cartesian
# chart does, and that freedom is deliberately retained here.  A closed curve
# is band-limited only in a particular parameter, and for the five-lobed star
# that parameter is the polar angle, in which the target occupies exactly
# modes 1, 4 and 6.  Refitting to arc length -- which Method B does -- destroys
# that property and leaves a truncation floor no bandwidth removes.  Nothing
# in this section refits.
# ---------------------------------------------------------------------------


def _cartesian_parameter_count(maximum_mode: int) -> int:
    """Stored real Cartesian coefficients through ``maximum_mode``: ``4 K + 2``."""

    mode = _positive_integer(maximum_mode, name="maximum_mode")
    return 4 * mode + 2


def cartesian_fourier_displacement_basis(
    parameters: object, *, maximum_mode: int
) -> np.ndarray:
    """Exact vector displacement basis of the Cartesian Fourier chart.

    The result has shape ``parameters.shape + (4 K + 2, 2)``.  Contracting its
    penultimate axis with a coefficient increment gives the exact Cartesian
    point displacement at fixed parameter.  Unlike the radial basis this is
    independent of the current state: the chart is affine in its coefficients.

    Ordering matches :meth:`CartesianFourierCurveState.incremented`:
    ``c_0x, c_0y, c_1x, c_1y, ..., c_Kx, c_Ky, s_1x, s_1y, ..., s_Kx, s_Ky``.
    """

    if np.iscomplexobj(parameters):
        raise ValueError("parameters must be real-valued.")
    values = np.asarray(parameters, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("parameters must contain only finite values.")
    mode_limit = _positive_integer(maximum_mode, name="maximum_mode")
    result = np.zeros(
        values.shape + (_cartesian_parameter_count(mode_limit), 2),
        dtype=np.float64,
    )
    for mode in range(mode_limit + 1):
        cosine = np.cos(mode * values)
        result[..., 2 * mode, 0] = cosine
        result[..., 2 * mode + 1, 1] = cosine
    offset = 2 * mode_limit + 2
    for mode in range(1, mode_limit + 1):
        sine = np.sin(mode * values)
        result[..., offset + 2 * (mode - 1), 0] = sine
        result[..., offset + 2 * (mode - 1) + 1, 1] = sine
    result.setflags(write=False)
    return result


def cartesian_fourier_phase_gauge_direction(
    state: object, *, maximum_mode: int | None = None
) -> np.ndarray | None:
    """Unit coefficient direction of an infinitesimal parameter shift.

    Under ``t -> t + delta`` the point set is unchanged while every mode pair
    rotates, so ``d c_k = k s_k`` and ``d s_k = -k c_k`` with ``d c_0 = 0``.
    That direction is an exact null direction of any shape objective and is
    removed from proposed steps.  ``None`` is returned when the direction
    degenerates, which happens only for a state with no active harmonics.
    """

    cosine = np.asarray(state.cosine_coefficients, dtype=np.float64)
    sine = np.asarray(state.sine_coefficients, dtype=np.float64)
    active = state.maximum_mode if maximum_mode is None else _positive_integer(
        maximum_mode, name="maximum_mode"
    )
    if active > state.maximum_mode:
        raise ValueError("maximum_mode cannot exceed the state's maximum mode.")
    direction = np.zeros(_cartesian_parameter_count(active), dtype=np.float64)
    offset = 2 * active + 2
    for mode in range(1, active + 1):
        direction[2 * mode : 2 * mode + 2] = mode * sine[mode]
        direction[offset + 2 * (mode - 1) : offset + 2 * mode] = -mode * cosine[mode]
    norm = float(np.linalg.norm(direction))
    if not math.isfinite(norm) or norm <= 0.0:
        return None
    direction /= norm
    direction.setflags(write=False)
    return direction


def project_off_phase_gauge(
    step: object, state: object, *, maximum_mode: int | None = None
) -> tuple[np.ndarray, float]:
    """Remove the exact phase direction, returning the step and what was removed."""

    values = np.asarray(step, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("step must be a finite vector.")
    direction = cartesian_fourier_phase_gauge_direction(
        state, maximum_mode=maximum_mode
    )
    if direction is None:
        return values, 0.0
    if direction.shape != values.shape:
        raise ValueError("step and gauge direction must have the same length.")
    component = float(np.dot(values, direction))
    return values - component * direction, component


def fit_cartesian_fourier_curve_state(
    curve: object,
    *,
    maximum_mode: int,
    center: object | None = None,
    component_id: str = "cartesian_fourier_inverse_curve",
    samples: int = 4096,
    source_identifier: str | None = None,
) -> object:
    """Project one star-shaped contour into the polar-angle Cartesian chart.

    The contour is resampled at uniform polar angle about ``center`` and
    truncated at ``maximum_mode``.  Polar angle, not arc length, is the
    parameter in which the analytic targets of this project are band-limited.

    This initializes the coefficient state. Later increments may optionally
    be re-gauged with :func:`regauge_cartesian_state_to_polar_angle`; those
    projections have their own reported truncation error.
    """

    from .explicit_fourier import CartesianFourierCurveState

    mode_limit = _positive_integer(maximum_mode, name="maximum_mode")
    count = _positive_integer(samples, name="samples")
    if count < 2 * (mode_limit + 1):
        raise ValueError("samples must resolve the requested bandwidth.")
    points = np.asarray(getattr(curve, "points", curve), dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 3:
        raise ValueError("curve must supply at least three planar points.")
    if not np.all(np.isfinite(points)):
        raise ValueError("curve points must be finite.")
    origin = (
        np.mean(points, axis=0)
        if center is None
        else np.asarray(center, dtype=np.float64)
    )
    if origin.shape != (2,) or not np.all(np.isfinite(origin)):
        raise ValueError("center must contain two finite coordinates.")

    delta = points - origin[None, :]
    radii = np.linalg.norm(delta, axis=1)
    if np.any(radii <= 64.0 * np.finfo(float).eps):
        raise OrderedSDFGeometryError(
            "Cartesian Fourier projection needs nonzero radii about the center."
        )
    angles = np.unwrap(np.arctan2(delta[:, 1], delta[:, 0]))
    if angles[-1] < angles[0]:
        angles = angles[::-1]
        radii = radii[::-1]
    extended_angles = np.concatenate((angles, angles[:1] + 2.0 * np.pi))
    extended_radii = np.concatenate((radii, radii[:1]))
    if np.any(np.diff(extended_angles) <= 0.0):
        raise OrderedSDFGeometryError(
            "Contour is not single-valued in polar angle about the requested "
            "center; the Cartesian polar-angle chart cannot represent it."
        )
    if extended_angles[-1] - extended_angles[0] > 2.0 * np.pi + 1.0e-9:
        raise OrderedSDFGeometryError(
            "Contour winds more than once about the requested center."
        )

    sample_angles = extended_angles[0] + 2.0 * np.pi * np.arange(count) / count
    sampled_radii = np.interp(sample_angles, extended_angles, extended_radii)
    sampled = origin[None, :] + sampled_radii[:, None] * np.stack(
        (np.cos(sample_angles), np.sin(sample_angles)), axis=-1
    )

    spectrum = np.fft.rfft(sampled, axis=0) / count
    cosine = np.zeros((mode_limit + 1, 2), dtype=np.float64)
    sine = np.zeros_like(cosine)
    cosine[0] = spectrum[0].real
    for mode in range(1, mode_limit + 1):
        cosine[mode] = 2.0 * spectrum[mode].real
        sine[mode] = -2.0 * spectrum[mode].imag

    # The transform's parameter is the sample index, whose origin is the first
    # sampled angle, so the truncation residual must be evaluated in that same
    # relative parameter.  Using the absolute angle here would report a phase
    # mismatch as a projection error.
    relative = sample_angles - sample_angles[0]
    phase = relative[:, None] * np.arange(mode_limit + 1)[None, :]
    reconstruction = np.cos(phase) @ cosine + np.sin(phase) @ sine
    residual = np.linalg.norm(reconstruction - sampled, axis=1)
    # The chart's own parameter origin is that sample origin, so rotate the
    # coefficients back to a zero origin and keep the state canonical: the
    # stored curve is then parameterized by polar angle itself.
    shift = float(sample_angles[0])
    if shift:
        rotated_cosine = np.array(cosine, copy=True)
        rotated_sine = np.array(sine, copy=True)
        # The transform's parameter is ``theta - shift``.  Expanding
        # ``cos(k(theta - shift))`` and ``sin(k(theta - shift))`` and
        # collecting terms re-expresses the same curve in absolute polar
        # angle, so the stored state's parameter *is* the polar angle.
        for mode in range(1, mode_limit + 1):
            c, s = np.cos(mode * shift), np.sin(mode * shift)
            rotated_cosine[mode] = c * cosine[mode] - s * sine[mode]
            rotated_sine[mode] = s * cosine[mode] + c * sine[mode]
        cosine, sine = rotated_cosine, rotated_sine

    try:
        return CartesianFourierCurveState(
            cosine,
            sine,
            component_id,
            source_identifier=source_identifier,
            initial_projection_rms_m=float(np.sqrt(np.mean(residual * residual))),
            initial_projection_maximum_m=float(np.max(residual)),
        )
    except ValueError as exc:
        raise OrderedSDFGeometryError(
            f"Initial Cartesian Fourier projection is not admissible: {exc}"
        ) from exc


def cartesian_fourier_state_curve(
    state: object,
    *,
    geometry_config: OrderedSDFGeometryConfig,
    full_validation: bool = True,
) -> PeriodicCurve2D:
    """Build and validate the deterministic curve represented by ``state``."""

    if not isinstance(geometry_config, OrderedSDFGeometryConfig):
        raise TypeError("geometry_config must be an OrderedSDFGeometryConfig.")
    if not isinstance(full_validation, (bool, np.bool_)):
        raise TypeError("full_validation must be bool.")
    minimum_resolution = 2 * state.maximum_mode + 2
    for name in ("num_nodes", "validation_resolution"):
        if getattr(geometry_config, name) < minimum_resolution:
            raise ValueError(
                f"{name} must be at least {minimum_resolution} to sample the "
                "Cartesian Fourier bandwidth without aliasing."
            )
    parameterization = state.parameterization()
    report = None
    if full_validation:
        try:
            report = validate_periodic_parameterization(
                parameterization,
                BoundaryValidationConfig(
                    num_samples_per_component=geometry_config.validation_resolution,
                    fourier_bandwidth=state.maximum_mode,
                ),
                raise_on_error=True,
            )
        except OrderedBoundaryValidationError as exc:
            raise OrderedSDFGeometryError(
                f"Cartesian Fourier retraction produced an inadmissible contour: {exc}"
            ) from exc
    curve = parameterization.discretize(geometry_config.num_nodes, require_even=True)
    lower = np.asarray(geometry_config.bounds[0], dtype=np.float64)
    upper = np.asarray(geometry_config.bounds[1], dtype=np.float64)
    if report is None:
        audit_count = max(
            geometry_config.validation_resolution,
            64 * (state.maximum_mode + 1),
        )
        parameters = 2.0 * np.pi * np.arange(audit_count) / audit_count
        audit_points = parameterization.evaluate(parameters, wrap=False).points
        minimum = np.min(audit_points, axis=0)
        maximum = np.max(audit_points, axis=0)
    else:
        minimum = np.asarray(report.bounding_box_min, dtype=np.float64)
        maximum = np.asarray(report.bounding_box_max, dtype=np.float64)
    if np.any(minimum <= lower) or np.any(maximum >= upper):
        raise OrderedSDFGeometryError(
            "Cartesian Fourier retraction touches or leaves the configured geometry bounds."
        )
    if not full_validation and sampled_self_intersection_count(curve.points):
        raise OrderedSDFGeometryError(
            "Cartesian Fourier retraction has a solver-grid self-intersection."
        )
    return curve


@dataclass(frozen=True)
class DirectCartesianFourierCurveUpdate:
    """One Cartesian-state increment and its physical step audit.

    ``arclength_refit_*`` are exactly zero because this chart never refits.
    The normal/tangential split is reported rather than constrained: tangential
    motion is reparameterization, which the optimizer needs in order to reach
    the gauge in which the target is band-limited.
    """

    state: object
    curve: PeriodicCurve2D
    coefficients: np.ndarray
    maximum_displacement_m: float
    regauge_rms_m: float
    regauge_maximum_m: float
    maximum_normal_displacement_m: float
    maximum_tangential_displacement_m: float
    rms_normal_displacement_m: float
    rms_tangential_displacement_m: float
    tangential_energy_ratio: float
    speed_ratio_before: float
    speed_ratio_after: float

    def __post_init__(self) -> None:
        if not isinstance(self.curve, PeriodicCurve2D):
            raise TypeError("curve must be a PeriodicCurve2D.")
        coefficients = np.array(self.coefficients, dtype=np.float64, copy=True)
        if coefficients.ndim != 1 or not np.all(np.isfinite(coefficients)):
            raise ValueError("coefficients must be a finite vector.")
        coefficients.setflags(write=False)
        object.__setattr__(self, "coefficients", coefficients)
        for name in (
            "maximum_displacement_m",
            "regauge_rms_m",
            "regauge_maximum_m",
            "maximum_normal_displacement_m",
            "maximum_tangential_displacement_m",
            "rms_normal_displacement_m",
            "rms_tangential_displacement_m",
            "tangential_energy_ratio",
            "speed_ratio_before",
            "speed_ratio_after",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)

    @property
    def arclength_refit_rms_m(self) -> float:
        """Polar-angle re-gauge truncation, not an arc-length refit.

        This chart never refits to arc length -- that is what would reinstate
        the truncation floor it exists to avoid.  The shared trajectory record
        carries the refit slots, so the polar-angle gauge projection's measured
        truncation is reported through them and labelled ``regauge_*`` wherever
        it is written out.  It is exactly zero when re-gauging is disabled.
        """

        return self.regauge_rms_m

    @property
    def arclength_refit_maximum_m(self) -> float:
        return self.regauge_maximum_m

    @property
    def arclength_speed_ratio_before(self) -> float:
        return self.speed_ratio_before

    @property
    def arclength_speed_ratio_after(self) -> float:
        return self.speed_ratio_after


def apply_cartesian_fourier_update(
    state: object,
    coefficients: object,
    *,
    maximum_mode: int,
    geometry_config: OrderedSDFGeometryConfig,
    full_validation: bool = True,
    regauge: bool = False,
) -> DirectCartesianFourierCurveUpdate:
    """Retract an increment in the authoritative Cartesian Fourier state.

    With ``regauge`` the retracted state is re-expressed in its own polar-angle
    parameter, which removes the chart's null space at the cost of a measured
    band truncation.  The exact target is a fixed point of that map.
    """

    active_mode = _positive_integer(maximum_mode, name="maximum_mode")
    try:
        next_state = state.incremented(coefficients, maximum_mode=active_mode)
    except ValueError as exc:
        raise OrderedSDFGeometryError(
            f"Cartesian Fourier retraction is not admissible: {exc}"
        ) from exc
    regauge_rms = 0.0
    regauge_maximum = 0.0
    if regauge:
        next_state, regauge_rms, regauge_maximum = (
            regauge_cartesian_state_to_polar_angle(next_state)
        )
    curve = cartesian_fourier_state_curve(
        next_state,
        geometry_config=geometry_config,
        full_validation=full_validation,
    )
    values = np.asarray(coefficients, dtype=np.float64)
    audit_count = max(
        geometry_config.validation_resolution,
        64 * (state.maximum_mode + 1),
    )
    parameters = 2.0 * np.pi * np.arange(audit_count, dtype=np.float64) / audit_count
    basis = cartesian_fourier_displacement_basis(parameters, maximum_mode=active_mode)
    displacement = np.einsum("...pd,p->...d", basis, values)
    magnitude = np.linalg.norm(displacement, axis=-1)

    before = state.parameterization().evaluate(parameters, wrap=False)
    after = next_state.parameterization().evaluate(parameters, wrap=False)
    tangents = np.asarray(before.first_derivatives, dtype=np.float64)
    speeds = np.linalg.norm(tangents, axis=-1)
    if np.any(speeds <= 0.0) or not np.all(np.isfinite(speeds)):
        raise OrderedSDFGeometryError(
            "Cartesian Fourier retraction has a vanishing parameter speed."
        )
    unit_tangent = tangents / speeds[:, None]
    unit_normal = np.stack((unit_tangent[:, 1], -unit_tangent[:, 0]), axis=-1)
    normal_motion = np.einsum("nd,nd->n", displacement, unit_normal)
    tangential_motion = np.einsum("nd,nd->n", displacement, unit_tangent)
    normal_energy = float(np.mean(normal_motion * normal_motion))
    tangential_energy = float(np.mean(tangential_motion * tangential_motion))
    total_energy = normal_energy + tangential_energy
    after_speeds = np.linalg.norm(
        np.asarray(after.first_derivatives, dtype=np.float64), axis=-1
    )
    return DirectCartesianFourierCurveUpdate(
        state=next_state,
        curve=curve,
        coefficients=values,
        maximum_displacement_m=float(np.max(magnitude)),
        regauge_rms_m=regauge_rms,
        regauge_maximum_m=regauge_maximum,
        maximum_normal_displacement_m=float(np.max(np.abs(normal_motion))),
        maximum_tangential_displacement_m=float(np.max(np.abs(tangential_motion))),
        rms_normal_displacement_m=float(np.sqrt(normal_energy)),
        rms_tangential_displacement_m=float(np.sqrt(tangential_energy)),
        tangential_energy_ratio=(
            0.0 if total_energy <= 0.0 else tangential_energy / total_energy
        ),
        speed_ratio_before=float(np.max(speeds) / np.min(speeds)),
        speed_ratio_after=float(np.max(after_speeds) / np.min(after_speeds)),
    )


def cartesian_fourier_velocity_basis(
    parameters: object, *, maximum_mode: int
) -> np.ndarray:
    """Parameter derivative of :func:`cartesian_fourier_displacement_basis`.

    Contracting this with a coefficient increment gives ``d(delta gamma)/dt``,
    which is what changes the parameter speed.  Reparameterization drift is a
    property of that derivative, not of the displacement itself: a step can be
    almost entirely normal in energy and still redistribute the parameter.
    """

    if np.iscomplexobj(parameters):
        raise ValueError("parameters must be real-valued.")
    values = np.asarray(parameters, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("parameters must contain only finite values.")
    mode_limit = _positive_integer(maximum_mode, name="maximum_mode")
    result = np.zeros(
        values.shape + (_cartesian_parameter_count(mode_limit), 2),
        dtype=np.float64,
    )
    for mode in range(1, mode_limit + 1):
        sine = -mode * np.sin(mode * values)
        result[..., 2 * mode, 0] = sine
        result[..., 2 * mode + 1, 1] = sine
    offset = 2 * mode_limit + 2
    for mode in range(1, mode_limit + 1):
        cosine = mode * np.cos(mode * values)
        result[..., offset + 2 * (mode - 1), 0] = cosine
        result[..., offset + 2 * (mode - 1) + 1, 1] = cosine
    result.setflags(write=False)
    return result


@lru_cache(maxsize=None)
def polar_angle_gauge_tangent_basis(maximum_mode: int) -> np.ndarray:
    """Orthonormal basis of the gauge-fixed set, in coefficient coordinates.

    The set of states this chart's gauge fixes is a *linear* subspace of the
    coefficient space, not a curved manifold: a curve is gauge-fixed exactly
    when it is ``m + rho(theta) e(theta)`` for a band-``K-1`` radial profile
    ``rho`` with no mode one, and that map is linear in ``(m, rho)``.  Its
    dimension is ``3`` for ``K <= 2`` and ``2K - 1`` above, against the chart's
    ``4K + 2`` coefficients.

    That is why the basis is needed.  The exact phase direction that
    :func:`project_off_phase_gauge` removes is only *one* of the ``2K + 3``
    directions the gauge annihilates; a step chosen in the full chart and
    projected afterwards spends most of itself on the others.  Measured on the
    band-six ellipse/star stage, 63 of the proposed steps were rejected as
    unprojectable against 1 in the radial chart, and eight accepted updates
    moved the objective by 7% where the radial chart moved it by 40%.  Solving
    the Levenberg system inside this subspace removes both effects at once, and
    subsumes the phase projection.

    The basis depends only on the bandwidth, so it is built once per ``K``.
    Rows are orthonormal and ordered to match
    :meth:`CartesianFourierCurveState.parameter_vector`.
    """

    modes = _positive_integer(maximum_mode, name="maximum_mode")
    count = 8 * (modes + 1)
    angles = 2.0 * np.pi * np.arange(count, dtype=np.float64) / count
    radial_direction = np.stack((np.cos(angles), np.sin(angles)), axis=-1)

    def coefficients(displacement: np.ndarray) -> np.ndarray:
        spectrum = np.fft.rfft(displacement, axis=0) / count
        cosine = np.zeros((modes + 1, 2), dtype=np.float64)
        sine = np.zeros_like(cosine)
        cosine[0] = spectrum[0].real
        for mode in range(1, modes + 1):
            cosine[mode] = 2.0 * spectrum[mode].real
            sine[mode] = -2.0 * spectrum[mode].imag
        return np.concatenate((cosine.ravel(), sine[1:].ravel()))

    rows = [
        coefficients(np.tile((1.0, 0.0), (count, 1))),   # translate x
        coefficients(np.tile((0.0, 1.0), (count, 1))),   # translate y
        coefficients(radial_direction),                  # uniform radius
    ]
    for mode in range(2, modes):
        rows.append(coefficients(np.cos(mode * angles)[:, None] * radial_direction))
        rows.append(coefficients(np.sin(mode * angles)[:, None] * radial_direction))
    orthonormal, _ = np.linalg.qr(np.transpose(rows))
    basis = np.ascontiguousarray(orthonormal.T)
    basis.setflags(write=False)
    return basis


def polar_angle_gauge_fixed_point(
    state: object,
    *,
    samples: int = 1024,
    rounds: int = 6,
    tolerance: float = 1.0e-13,
    maximum_residual_m: float = 1.0e-9,
) -> tuple[object, float]:
    """Iterate :func:`regauge_cartesian_state_to_polar_angle` to its fixed point.

    One application does *not* generally produce a gauge-fixed state.  The map's
    contraction was measured near ``1/2`` on the tested perturbations, so a
    single projection leaves some of the
    parameter's excess behind, and an optimizer that applies one per accepted
    step inherits that rate: the measured loss then fell by exactly four per
    iteration where the radial chart was quadratic.  Vector Aitken
    extrapolation over the measured ratio reaches the fixed point -- machine
    precision for a band-limited target, and a representable curve
    otherwise -- in two or three rounds.

    The returned pair is always ``(state, that state's own measured distance
    from its next gauge projection)``, never a state beside the residual of the state
    before it. Band truncation alone is insufficient: a phase-shifted circle
    has zero truncation while still being outside the optimizer's subspace.
    We also bound the displacement between input and output at the same parameter.
    Only states that have been passed through the map carry a measurement, and only
    those are eligible to be returned.  Extrapolation is a proposal, never a
    commitment: the best measured state wins, so the result cannot be worse
    gauged than plain iteration would have left it.

    A state too far from the gauge-fixed set to be projected onto it raises,
    rather than being handed back ungauged.  Silently returning the input is
    what turns one bad step into a lost run: the optimizer's Jacobian is
    measured on this map, so a projection that quietly does nothing lets the
    next step be taken in the free chart, which walks further off the set,
    which makes the projection fail again -- measured, a peanut left the
    star-shaped set entirely within two accepted updates and its split was
    never proposed.  Raising instead makes the trial infeasible and the
    optimizer backtracks; the excess is second-order in the step, so a halved
    step is projectable.
    """

    from .explicit_fourier import CartesianFourierCurveState

    count = _positive_integer(samples, name="samples")
    passes = _positive_integer(rounds, name="rounds")
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and non-negative.")
    if not math.isfinite(maximum_residual_m) or maximum_residual_m < tolerance:
        raise ValueError("maximum_residual_m must be finite and at least tolerance.")

    def rebuilt(reference: object, vector: np.ndarray) -> object:
        size = reference.cosine_coefficients.size
        return CartesianFourierCurveState(
            vector[:size].reshape(-1, 2),
            np.vstack((np.zeros(2), vector[size:].reshape(-1, 2))),
            reference.component_id,
            name=reference.name,
            source_identifier=reference.source_identifier,
            initial_projection_rms_m=reference.initial_projection_rms_m,
            initial_projection_maximum_m=reference.initial_projection_maximum_m,
        )

    current = state
    best: object | None = None
    best_truncation = math.inf

    def consider(candidate: object, measured: float) -> None:
        nonlocal best, best_truncation
        if measured < best_truncation:
            best, best_truncation = candidate, float(measured)

    def measured_projection(candidate: object) -> tuple[object, float]:
        projected, _, truncation = regauge_cartesian_state_to_polar_angle(candidate, samples=count)
        # The sum of harmonic-vector norms bounds displacement at every
        # parameter, including pure phase changes with zero band truncation.
        displacement_bound = float(
            np.linalg.norm(projected.cosine_coefficients - candidate.cosine_coefficients, axis=1).sum()
            + np.linalg.norm(projected.sine_coefficients - candidate.sine_coefficients, axis=1).sum()
        )
        return projected, max(truncation, displacement_bound)

    for _ in range(passes):
        # ``first`` measures ``current``; ``second`` measures ``once``.  A
        # projection can leave the star-shaped set even when the state it
        # started from was inside it, so each measurement is taken on its own:
        # the pass that fails is discarded, not the progress before it.  Only a
        # round that cannot measure anything at all leaves the caller with
        # nothing to accept.
        try:
            once, first = measured_projection(current)
        except (OrderedSDFGeometryError, ValueError):
            if best is None:
                raise
            break
        consider(current, first)
        if best_truncation <= tolerance:
            break
        try:
            twice, second = measured_projection(once)
        except (OrderedSDFGeometryError, ValueError):
            break
        consider(once, second)
        if best_truncation <= tolerance:
            break
        start = current.parameter_vector()
        first_difference = once.parameter_vector() - start
        second_difference = twice.parameter_vector() - once.parameter_vector()
        denominator = float(first_difference @ first_difference)
        if denominator <= 0.0:
            break
        ratio = float(first_difference @ second_difference) / denominator
        if not math.isfinite(ratio) or abs(ratio) >= 0.999:
            current = twice
            continue
        proposal = rebuilt(
            current, once.parameter_vector() + second_difference / (1.0 - ratio)
        )
        try:
            _, extrapolated = measured_projection(proposal)
        except (OrderedSDFGeometryError, ValueError):
            current = twice
            continue
        consider(proposal, extrapolated)
        current = proposal if extrapolated < second else twice
    assert best is not None
    if best_truncation > maximum_residual_m:
        raise OrderedSDFGeometryError(
            "Polar-angle gauge fixing did not converge: the state is "
            f"{best_truncation:.3e} m from the gauge-fixed set."
        )
    return best, best_truncation


def regauge_cartesian_state_to_polar_angle(
    state: object, *, maximum_mode: int | None = None, samples: int = 2048
) -> tuple[object, float, float]:
    """Re-express a Cartesian state in its own polar-angle parameter.

    This is a *gauge* projection, not an arc-length refit.  It changes the
    parameter and leaves the point set alone, up to the band truncation it
    reports.  Its purpose is to remove the chart's null space: without it the
    optimizer's step has a reparameterization component the data cannot see,
    the parameter speed ratio compounds -- measured at about 1.4 per accepted
    update, reaching 226 within fifteen -- and the Kress quadrature degrades
    while the shape stops improving.

    The parameter values are found exactly by Newton iteration on
    ``angle(gamma(t) - c) = theta``, so no interpolation error is introduced;
    the returned RMS and maximum are the genuine band-``K`` truncation of the
    re-gauged curve.  The exact target is a fixed point of this map, because it
    is band-limited in precisely this parameter.

    Newton is *started* from a monotone interpolation of a dense probe of
    ``angle(gamma(t))`` rather than from the target angles themselves.  That
    only chooses the starting point -- every returned parameter is still
    polished against a displacement tolerance -- but it is what makes the map usable near a pinch,
    where the angle sweeps almost the whole turn over a few percent of the
    parameter and the naive start does not converge in any iteration budget.
    A curve whose probe is not monotone is reported as not single-valued
    immediately, instead of after a spent budget.
    """

    from .explicit_fourier import CartesianFourierCurveState

    mode_limit = state.maximum_mode if maximum_mode is None else _positive_integer(
        maximum_mode, name="maximum_mode"
    )
    count = _positive_integer(samples, name="samples")
    if count < 4 * (mode_limit + 1):
        raise ValueError("samples must comfortably resolve the requested bandwidth.")
    center = np.asarray(state.center, dtype=np.float64)
    parameterization = state.parameterization()
    targets = 2.0 * np.pi * np.arange(count, dtype=np.float64) / count

    probe_count = max(8 * count, 4096)
    probe = 2.0 * np.pi * np.arange(probe_count, dtype=np.float64) / probe_count
    probe_offset = (
        np.asarray(parameterization.evaluate(probe, wrap=False).points, dtype=np.float64)
        - center[None, :]
    )
    if np.any(np.linalg.norm(probe_offset, axis=1) <= 0.0):
        raise OrderedSDFGeometryError(
            "Re-gauging requires a curve that does not pass through its own center."
        )
    probe_angles = np.unwrap(np.arctan2(probe_offset[:, 1], probe_offset[:, 0]))
    # A clockwise contour sweeps the angle downwards.  Negating the angle, not
    # the parameter, is what keeps the interpolation's abscissa increasing
    # while its ordinate stays the parameter the caller asked about.
    orientation = 1.0 if probe_angles[-1] > probe_angles[0] else -1.0
    ordered_angles = orientation * probe_angles
    if np.any(np.diff(ordered_angles) <= 0.0):
        raise OrderedSDFGeometryError(
            "Re-gauging requires a strictly monotone polar angle; the contour is "
            "not single-valued about its own center."
        )
    extended_angles = np.concatenate((ordered_angles, ordered_angles[:1] + 2.0 * np.pi))
    if np.any(np.diff(extended_angles) <= 0.0):
        raise OrderedSDFGeometryError("Re-gauging requires exactly one monotone turn about the center.")
    extended_parameters = np.concatenate((probe, probe[:1] + 2.0 * np.pi))
    wrapped = extended_angles[0] + np.mod(
        orientation * targets - extended_angles[0], 2.0 * np.pi
    )
    parameters = np.interp(wrapped, extended_angles, extended_parameters)
    # A geometric convergence criterion, not an angular one.  Near a pinch the
    # angle is so sensitive to the parameter that an angular tolerance of 1e-14
    # is below what double precision in the parameter can deliver, and Newton
    # stalls above it forever while the point it has already selected is
    # correct to a femtometre.  Scaling the angular residual by the local
    # radius measures exactly that displacement.
    displacement_tolerance_m = 1.0e-15
    admissible_displacement_m = 1.0e-12
    best_displacement = math.inf
    best_parameters = parameters.copy()
    for _ in range(64):
        sample = parameterization.evaluate(parameters, wrap=False)
        offset = np.asarray(sample.points, dtype=np.float64) - center[None, :]
        derivative = np.asarray(sample.first_derivatives, dtype=np.float64)
        squared = np.einsum("nd,nd->n", offset, offset)
        if np.any(squared <= 0.0):
            raise OrderedSDFGeometryError(
                "Re-gauging requires a curve that does not pass through its own center."
            )
        angles = np.arctan2(offset[:, 1], offset[:, 0])
        residual = np.arctan2(np.sin(angles - targets), np.cos(angles - targets))
        displacement = float(np.max(np.abs(residual) * np.sqrt(squared)))
        if displacement >= best_displacement:
            break
        best_displacement = displacement
        best_parameters = parameters.copy()
        if displacement <= displacement_tolerance_m:
            break
        slope = (
            offset[:, 0] * derivative[:, 1] - offset[:, 1] * derivative[:, 0]
        ) / squared
        if np.any(np.abs(slope) <= 0.0):
            raise OrderedSDFGeometryError(
                "Re-gauging requires a strictly monotone polar angle."
            )
        parameters = parameters - residual / slope
    if best_displacement > admissible_displacement_m:
        raise OrderedSDFGeometryError(
            "Re-gauging to polar angle did not converge; the contour is probably "
            "not single-valued about its own center."
        )

    points = np.asarray(
        parameterization.evaluate(best_parameters, wrap=False).points, dtype=np.float64
    )
    spectrum = np.fft.rfft(points, axis=0) / count
    cosine = np.zeros((mode_limit + 1, 2), dtype=np.float64)
    sine = np.zeros_like(cosine)
    cosine[0] = spectrum[0].real
    for mode in range(1, mode_limit + 1):
        cosine[mode] = 2.0 * spectrum[mode].real
        sine[mode] = -2.0 * spectrum[mode].imag
    phase = targets[:, None] * np.arange(mode_limit + 1)[None, :]
    residual = np.linalg.norm(
        np.cos(phase) @ cosine + np.sin(phase) @ sine - points, axis=1
    )
    regauged = CartesianFourierCurveState(
        cosine,
        sine,
        state.component_id,
        name=state.name,
        source_identifier=state.source_identifier,
        initial_projection_rms_m=state.initial_projection_rms_m,
        initial_projection_maximum_m=state.initial_projection_maximum_m,
    )
    return (
        regauged,
        float(np.sqrt(np.mean(residual * residual))),
        float(np.max(residual)),
    )
