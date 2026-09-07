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
