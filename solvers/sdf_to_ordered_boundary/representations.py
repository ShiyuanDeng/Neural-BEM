"""Coefficient-owning periodic spline and Fourier boundary representations."""

from __future__ import annotations

from dataclasses import dataclass, replace
import operator

import numpy as np
from scipy.interpolate import CubicSpline, PPoly

from ordered_boundary import (
    CurveEvaluation2D,
    CurveProvenance2D,
    PeriodicParameterization2D,
    fourier_curve,
)

from .results import LeastSquaresDiagnostics, ResidualDiagnostics


def _readonly_float_array(values, *, name: str, ndim: int) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    array = np.array(values, dtype=np.float64, copy=True)
    if array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")
    array.setflags(write=False)
    return array


def _validate_period_and_origin(period: float, parameter_origin: float) -> tuple[float, float]:
    period_value = float(period)
    origin_value = float(parameter_origin)
    if not np.isfinite(period_value) or period_value <= 0.0:
        raise ValueError("period must be finite and positive.")
    if not np.isfinite(origin_value):
        raise ValueError("parameter_origin must be finite.")
    return period_value, origin_value


def _validate_samples(
    parameters,
    points,
    *,
    period: float,
    parameter_origin: float,
    minimum_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    parameter_values = _readonly_float_array(parameters, name="parameters", ndim=1)
    point_values = _readonly_float_array(points, name="points", ndim=2)
    if point_values.shape != (parameter_values.size, 2):
        raise ValueError("points must have shape (parameters.size, 2).")
    if parameter_values.size < minimum_count:
        raise ValueError(f"At least {minimum_count} samples are required.")
    if np.any(np.diff(parameter_values) <= 0.0):
        raise ValueError("parameters must be strictly increasing.")
    scale = max(abs(parameter_origin), period, 1.0)
    tolerance = 64.0 * np.finfo(float).eps * scale
    if abs(float(parameter_values[0]) - parameter_origin) > tolerance:
        raise ValueError("parameters must begin at parameter_origin.")
    if float(parameter_values[-1]) >= parameter_origin + period - tolerance:
        raise ValueError("parameters must omit the repeated periodic endpoint.")
    return parameter_values, point_values


def _residual_diagnostics(actual: np.ndarray, expected: np.ndarray) -> ResidualDiagnostics:
    distances = np.linalg.norm(np.asarray(actual) - np.asarray(expected), axis=-1)
    return ResidualDiagnostics(
        maximum=float(np.max(distances)),
        rms=float(np.sqrt(np.mean(distances**2))),
    )


@dataclass(frozen=True)
class PeriodicSplineBoundary:
    """Periodic cubic vector spline whose knots and coefficients are authoritative.

    ``coefficients`` use SciPy's local power-basis convention with shape
    ``(4, num_intervals, 2)``.  No point cloud is retained as a competing
    representation.  The public conversion method returns the repository's
    existing continuous geometry contract.
    """

    knots: np.ndarray
    coefficients: np.ndarray
    component_id: str = "component-0"
    name: str = "periodic_cubic_spline"
    period: float = 2.0 * np.pi
    parameter_origin: float = 0.0
    provenance: CurveProvenance2D = CurveProvenance2D(source_kind="periodic_spline")

    def __post_init__(self) -> None:
        knots = _readonly_float_array(self.knots, name="knots", ndim=1)
        coefficients = _readonly_float_array(
            self.coefficients,
            name="coefficients",
            ndim=3,
        )
        period, origin = _validate_period_and_origin(self.period, self.parameter_origin)
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be a non-empty string.")
        if not isinstance(self.provenance, CurveProvenance2D):
            raise TypeError("provenance must be a CurveProvenance2D.")
        if knots.size < 3 or np.any(np.diff(knots) <= 0.0):
            raise ValueError("knots must be a strictly increasing periodic knot sequence.")
        if coefficients.shape != (4, knots.size - 1, 2):
            raise ValueError("coefficients must have shape (4, knots.size - 1, 2).")
        tolerance = 64.0 * np.finfo(float).eps * max(abs(origin), period, 1.0)
        if abs(float(knots[0]) - origin) > tolerance:
            raise ValueError("knots must begin at parameter_origin.")
        if abs(float(knots[-1]) - (origin + period)) > tolerance:
            raise ValueError("knots must end at parameter_origin + period.")

        raw = PPoly(coefficients, knots, extrapolate=False)
        geometry_scale = max(float(np.max(np.abs(raw(knots)))), 1.0)
        for order in (0, 1, 2):
            left = np.asarray(raw(origin, nu=order), dtype=float)
            right = np.asarray(raw(origin + period, nu=order), dtype=float)
            derivative_scale = max(
                geometry_scale / period**order,
                float(np.max(np.abs(left))),
                float(np.max(np.abs(right))),
                1.0,
            )
            if not np.allclose(left, right, rtol=2.0e-11, atol=2.0e-12 * derivative_scale):
                raise ValueError(
                    f"Spline coefficients are not periodic through derivative order {order}."
                )

        object.__setattr__(self, "knots", knots)
        object.__setattr__(self, "coefficients", coefficients)
        object.__setattr__(self, "component_id", self.component_id.strip())
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "parameter_origin", origin)

    @classmethod
    def interpolate(
        cls,
        parameters,
        points,
        *,
        component_id: str = "component-0",
        name: str = "periodic_cubic_spline",
        period: float = 2.0 * np.pi,
        parameter_origin: float = 0.0,
        provenance: CurveProvenance2D | None = None,
    ) -> "PeriodicSplineBoundary":
        """Interpolate cyclic samples with a true periodic cubic boundary condition."""

        period_value, origin_value = _validate_period_and_origin(period, parameter_origin)
        parameter_values, point_values = _validate_samples(
            parameters,
            points,
            period=period_value,
            parameter_origin=origin_value,
            minimum_count=3,
        )
        extended_parameters = np.concatenate(
            (parameter_values, np.asarray([origin_value + period_value]))
        )
        extended_points = np.vstack((point_values, point_values[0]))
        spline = CubicSpline(
            extended_parameters,
            extended_points,
            axis=0,
            bc_type="periodic",
            extrapolate="periodic",
        )
        metadata = (
            CurveProvenance2D(source_kind="periodic_spline")
            if provenance is None
            else provenance
        )
        return cls(
            knots=spline.x,
            coefficients=spline.c,
            component_id=component_id,
            name=name,
            period=period_value,
            parameter_origin=origin_value,
            provenance=metadata,
        )

    @property
    def degree(self) -> int:
        return 3

    @property
    def num_intervals(self) -> int:
        return int(self.knots.size - 1)

    def with_provenance(self, provenance: CurveProvenance2D) -> "PeriodicSplineBoundary":
        return replace(self, provenance=provenance)

    def to_parameterization(self) -> PeriodicParameterization2D:
        """Build the shared continuous curve from the retained coefficients."""

        polynomial = PPoly(self.coefficients, self.knots, extrapolate="periodic")

        def evaluator(parameters: np.ndarray) -> tuple[np.ndarray, ...]:
            return (
                np.asarray(polynomial(parameters, nu=0), dtype=np.float64),
                np.asarray(polynomial(parameters, nu=1), dtype=np.float64),
                np.asarray(polynomial(parameters, nu=2), dtype=np.float64),
            )

        return PeriodicParameterization2D(
            component_id=self.component_id,
            evaluator=evaluator,
            name=self.name,
            period=self.period,
            parameter_origin=self.parameter_origin,
            provenance=self.provenance,
        )

    def evaluate(self, parameters, *, wrap: bool = True) -> CurveEvaluation2D:
        return self.to_parameterization().evaluate(parameters, wrap=wrap)

    def position(self, parameters) -> np.ndarray:
        return self.evaluate(parameters).points

    def derivative(self, parameters, order: int = 1) -> np.ndarray:
        derivative_order = operator.index(order)
        evaluation = self.evaluate(parameters)
        if derivative_order == 0:
            return evaluation.points
        if derivative_order == 1:
            return evaluation.first_derivatives
        if derivative_order == 2:
            return evaluation.second_derivatives
        raise ValueError("PeriodicSplineBoundary exposes derivative orders 0, 1, and 2.")


@dataclass(frozen=True)
class FourierBoundary:
    """Real bandlimited vector Fourier curve with retained public coefficients."""

    cosine_coefficients: np.ndarray
    sine_coefficients: np.ndarray
    component_id: str = "component-0"
    name: str = "fourier_boundary"
    period: float = 2.0 * np.pi
    parameter_origin: float = 0.0
    provenance: CurveProvenance2D = CurveProvenance2D(source_kind="fourier_fit")

    def __post_init__(self) -> None:
        cosine = _readonly_float_array(
            self.cosine_coefficients,
            name="cosine_coefficients",
            ndim=2,
        )
        sine = _readonly_float_array(
            self.sine_coefficients,
            name="sine_coefficients",
            ndim=2,
        )
        period, origin = _validate_period_and_origin(self.period, self.parameter_origin)
        if cosine.shape != sine.shape or cosine.ndim != 2 or cosine.shape[1] != 2:
            raise ValueError("Fourier coefficient arrays must share shape (bandwidth + 1, 2).")
        if cosine.shape[0] < 2:
            raise ValueError("FourierBoundary requires at least mode one.")
        if not np.allclose(sine[0], 0.0, rtol=0.0, atol=1.0e-15):
            raise ValueError("The mode-zero sine coefficient must be zero.")
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be a non-empty string.")
        if not isinstance(self.provenance, CurveProvenance2D):
            raise TypeError("provenance must be a CurveProvenance2D.")
        object.__setattr__(self, "cosine_coefficients", cosine)
        object.__setattr__(self, "sine_coefficients", sine)
        object.__setattr__(self, "component_id", self.component_id.strip())
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "parameter_origin", origin)

    @property
    def bandwidth(self) -> int:
        return int(self.cosine_coefficients.shape[0] - 1)

    def with_coefficients(
        self,
        cosine_coefficients,
        sine_coefficients,
        *,
        provenance: CurveProvenance2D | None = None,
    ) -> "FourierBoundary":
        """Return a rebuilt immutable curve after coefficient optimization."""

        return FourierBoundary(
            cosine_coefficients=cosine_coefficients,
            sine_coefficients=sine_coefficients,
            component_id=self.component_id,
            name=self.name,
            period=self.period,
            parameter_origin=self.parameter_origin,
            provenance=self.provenance if provenance is None else provenance,
        )

    def with_provenance(self, provenance: CurveProvenance2D) -> "FourierBoundary":
        return replace(self, provenance=provenance)

    def to_parameterization(self) -> PeriodicParameterization2D:
        """Build the shared continuous curve from the retained coefficients."""

        curve = fourier_curve(
            self.cosine_coefficients,
            self.sine_coefficients,
            component_id=self.component_id,
            name=self.name,
            period=self.period,
            parameter_origin=self.parameter_origin,
        )
        return replace(curve, provenance=self.provenance)

    def evaluate(self, parameters, *, wrap: bool = True) -> CurveEvaluation2D:
        return self.to_parameterization().evaluate(parameters, wrap=wrap)

    def position(self, parameters) -> np.ndarray:
        return self.evaluate(parameters).points

    def derivative(self, parameters, order: int = 1) -> np.ndarray:
        derivative_order = operator.index(order)
        evaluation = self.evaluate(parameters)
        if derivative_order == 0:
            return evaluation.points
        if derivative_order == 1:
            return evaluation.first_derivatives
        if derivative_order == 2:
            return evaluation.second_derivatives
        if derivative_order == 3:
            assert evaluation.third_derivatives is not None
            return evaluation.third_derivatives
        raise ValueError("FourierBoundary exposes derivative orders 0 through 3.")

    def mode_amplitudes(self) -> np.ndarray:
        """Return Euclidean coefficient energy amplitudes for modes ``0..K``."""

        amplitudes = np.sqrt(
            np.sum(self.cosine_coefficients**2 + self.sine_coefficients**2, axis=1)
        )
        amplitudes.setflags(write=False)
        return amplitudes


@dataclass(frozen=True)
class FourierLeastSquaresResult:
    boundary: FourierBoundary
    residual: ResidualDiagnostics
    diagnostics: LeastSquaresDiagnostics


def fit_fourier_least_squares(
    parameters,
    points,
    *,
    bandwidth: int,
    component_id: str = "component-0",
    name: str = "fourier_least_squares",
    period: float = 2.0 * np.pi,
    parameter_origin: float = 0.0,
    rcond: float | None = None,
    provenance: CurveProvenance2D | None = None,
) -> FourierLeastSquaresResult:
    """Fit independent coordinate systems in one real trigonometric basis."""

    if isinstance(bandwidth, bool):
        raise TypeError("bandwidth must be an integer, not bool.")
    try:
        mode_count = operator.index(bandwidth)
    except TypeError as exc:
        raise TypeError("bandwidth must be an integer.") from exc
    if mode_count < 1:
        raise ValueError("bandwidth must be at least one.")
    period_value, origin_value = _validate_period_and_origin(period, parameter_origin)
    num_unknowns = 2 * mode_count + 1
    parameter_values, point_values = _validate_samples(
        parameters,
        points,
        period=period_value,
        parameter_origin=origin_value,
        minimum_count=num_unknowns,
    )
    if rcond is not None:
        rcond_value = float(rcond)
        if not np.isfinite(rcond_value) or rcond_value < 0.0:
            raise ValueError("rcond must be finite and non-negative when supplied.")
    else:
        rcond_value = None

    angle = 2.0 * np.pi * (parameter_values - origin_value) / period_value
    design = np.empty((parameter_values.size, num_unknowns), dtype=np.float64)
    design[:, 0] = 1.0
    for mode in range(1, mode_count + 1):
        design[:, 2 * mode - 1] = np.cos(mode * angle)
        design[:, 2 * mode] = np.sin(mode * angle)
    solution, _, rank, singular_values = np.linalg.lstsq(design, point_values, rcond=rcond_value)
    cosine = np.zeros((mode_count + 1, 2), dtype=np.float64)
    sine = np.zeros_like(cosine)
    cosine[0] = solution[0]
    for mode in range(1, mode_count + 1):
        cosine[mode] = solution[2 * mode - 1]
        sine[mode] = solution[2 * mode]

    fitted_points = design @ solution
    residual = _residual_diagnostics(fitted_points, point_values)
    metadata = (
        CurveProvenance2D(source_kind="fourier_fit", fit_residual=residual.rms)
        if provenance is None
        else provenance
    )
    boundary = FourierBoundary(
        cosine_coefficients=cosine,
        sine_coefficients=sine,
        component_id=component_id,
        name=name,
        period=period_value,
        parameter_origin=origin_value,
        provenance=metadata,
    )
    condition_number = (
        float("inf")
        if singular_values.size == 0 or singular_values[-1] == 0.0
        else float(singular_values[0] / singular_values[-1])
    )
    diagnostics = LeastSquaresDiagnostics(
        num_samples=int(parameter_values.size),
        num_unknowns=num_unknowns,
        rank=int(rank),
        condition_number=condition_number,
        singular_values=tuple(float(value) for value in singular_values),
    )
    if diagnostics.rank != num_unknowns:
        raise np.linalg.LinAlgError(
            f"Fourier least-squares design is rank deficient ({diagnostics.rank}/{num_unknowns})."
        )
    return FourierLeastSquaresResult(boundary, residual, diagnostics)


def spline_interpolation_residual(
    boundary: PeriodicSplineBoundary,
    parameters,
    points,
) -> ResidualDiagnostics:
    """Evaluate interpolation residual without retaining input samples."""

    point_values = np.asarray(points, dtype=np.float64)
    evaluated = boundary.evaluate(parameters).points
    if evaluated.shape != point_values.shape:
        raise ValueError("points must match the evaluated spline shape.")
    return _residual_diagnostics(evaluated, point_values)
