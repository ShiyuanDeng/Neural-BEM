"""Opt-in ordered-label Cartesian Fourier experiment, separate from A/B/C.

This is variable-projection least squares over positive cyclic label increments,
not Zhao--Serkh's speed/tangent-angle filtering algorithm.  No solver or active
inverse imports this module.  Geometry validity and fallback are explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from scipy.special import ellipe, ellipeinc, softmax

from ordered_boundary import (
    BoundaryValidationConfig,
    CurveProvenance2D,
    PeriodicParameterization2D,
    validate_periodic_parameterization,
)
from .representations import FourierBoundary, fit_fourier_least_squares
from .results import MethodResult, ResidualDiagnostics


def exact_arclength_ellipse(
    center=(0.5, 0.5), semi_major=0.07, semi_minor=0.035, rotation=0.4,
    *, component_id="ellipse", inverse_tolerance=2.0e-14,
) -> PeriodicParameterization2D:
    """The analytic ellipse with an inverted elliptic-integral arc map.

    Positions remain on the exact ellipse; no finite Fourier refit is involved.
    Jets differentiate the inverse map analytically through order three.
    """

    center = np.asarray(center, dtype=float)
    a, b = float(semi_major), float(semi_minor)
    tolerance = float(inverse_tolerance)
    if center.shape != (2,) or not np.all(np.isfinite(center)):
        raise ValueError("center must contain two finite coordinates.")
    if not np.isfinite(a + b + rotation) or not a >= b > 0:
        raise ValueError("Require finite semi_major >= semi_minor > 0 and rotation.")
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("inverse_tolerance must be finite and positive.")
    m = 1.0 - (b / a) ** 2
    integral_quarter = ellipe(m)
    perimeter = 4.0 * a * integral_quarter
    arc_scale = perimeter / (2.0 * np.pi)
    rotation_matrix = np.array([[np.cos(rotation), -np.sin(rotation)],
                                [np.sin(rotation), np.cos(rotation)]])

    def evaluator(parameters):
        parameter = np.mod(np.asarray(parameters), 2.0 * np.pi)
        desired_arc = parameter * arc_scale
        angle = np.array(parameter, copy=True)
        lower = np.zeros_like(angle)
        upper = np.full_like(angle, 2.0 * np.pi)
        for _ in range(60):
            arc = a * (ellipeinc(angle + np.pi / 2.0, m) - integral_quarter)
            residual = arc - desired_arc
            if np.max(np.abs(residual), initial=0.0) <= tolerance * perimeter:
                break
            lower = np.where(residual < 0.0, angle, lower)
            upper = np.where(residual > 0.0, angle, upper)
            speed = np.hypot(a * np.sin(angle), b * np.cos(angle))
            trial = angle - residual / speed
            angle = np.where((trial >= lower) & (trial <= upper),
                             trial, 0.5 * (lower + upper))
        else:
            raise ValueError("Elliptic-integral arclength inversion did not converge.")
        sine, cosine = np.sin(angle), np.cos(angle)
        native_first = np.stack((-a * sine, b * cosine), axis=-1)
        native_second = np.stack((-a * cosine, -b * sine), axis=-1)
        speed = np.linalg.norm(native_first, axis=-1)
        speed_first = (a * a - b * b) * sine * cosine / speed
        speed_second = ((a * a - b * b) * np.cos(2 * angle) / speed
                        - speed_first**2 / speed)
        inverse_first = arc_scale / speed
        inverse_second = -arc_scale**2 * speed_first / speed**3
        inverse_third = arc_scale**3 * (
            3.0 * speed_first**2 / speed**5 - speed_second / speed**4
        )
        points = np.stack((a * cosine, b * sine), axis=-1)
        first = native_first * inverse_first[..., None]
        second = (native_second * inverse_first[..., None]**2
                  + native_first * inverse_second[..., None])
        third = (-native_first * inverse_first[..., None]**3
                 + 3 * native_second * (inverse_first * inverse_second)[..., None]
                 + native_first * inverse_third[..., None])
        return (points @ rotation_matrix.T + center, first @ rotation_matrix.T,
                second @ rotation_matrix.T, third @ rotation_matrix.T)

    return PeriodicParameterization2D(
        component_id, evaluator, name="exact_ellipse_arclength",
        provenance=CurveProvenance2D(source_kind="analytic_elliptic_integral_inverse"),
    )


def closest_parameters(points, curve, *, localization_samples=1024, candidates=4):
    """Dense multistart localization and safeguarded local closest-point Newton.

    Returns numerical minima, not a continuous global certificate.  Callers
    tighten localization independently and report agreement.  Steps remain
    within two localization cells of each seed to prevent branch jumps.
    """

    points = np.asarray(points, dtype=float)
    count = int(localization_samples)
    if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
        raise ValueError("points must be a finite (M, 2) array.")
    if count < 32 or not 1 <= candidates <= count:
        raise ValueError("Invalid closest-point localization resolution.")
    grid = 2.0 * np.pi * np.arange(count) / count
    tree = cKDTree(curve.evaluate(grid).points)
    _, indices = tree.query(points, k=list(range(1, candidates + 1)))
    seeds = grid[indices]
    parameter = seeds.copy()
    half_width = 4.0 * np.pi / count
    for _ in range(24):
        evaluation = curve.evaluate(parameter)
        residual = evaluation.points - points[:, None, :]
        gradient = np.sum(residual * evaluation.first_derivatives, axis=-1)
        hessian = np.sum(evaluation.first_derivatives**2
                         + residual * evaluation.second_derivatives, axis=-1)
        step = gradient / np.maximum(hessian, 1.0e-20)
        step = np.clip(step, -half_width / 2.0, half_width / 2.0)
        old_squared = np.sum(residual**2, axis=-1)
        candidate_parameter = parameter.copy()
        for backtrack in range(8):
            trial = np.clip(parameter - step * 0.5**backtrack,
                            seeds - half_width, seeds + half_width)
            squared = np.sum((curve.evaluate(trial).points - points[:, None, :])**2,
                             axis=-1)
            improve = squared < old_squared
            candidate_parameter = np.where(improve, trial, candidate_parameter)
            old_squared = np.minimum(squared, old_squared)
        if np.max(np.abs(candidate_parameter - parameter), initial=0.0) < 1.0e-13:
            parameter = candidate_parameter
            break
        parameter = candidate_parameter
    distances = np.linalg.norm(curve.evaluate(parameter).points - points[:, None, :], axis=-1)
    best = np.argmin(distances, axis=1)
    return parameter[np.arange(points.shape[0]), best], distances[np.arange(points.shape[0]), best]


@dataclass(frozen=True)
class ParameterAwareConfig:
    bandwidth: int = 8
    max_iterations: int = 100
    spectral_penalty: float = 0.0
    spectral_order: int = 2
    minimum_gap_fraction: float = 1.0e-4
    minimum_speed_ratio: float = 1.0e-4
    maximum_design_condition: float = 1.0e8
    validation_resolution: int = 512

    def __post_init__(self):
        for name in ("bandwidth", "max_iterations", "spectral_order", "validation_resolution"):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                raise TypeError(f"{name} must be an integer.")
            if value < (32 if name == "validation_resolution" else 1):
                raise ValueError(f"{name} is too small.")
        for name in ("spectral_penalty", "minimum_gap_fraction", "minimum_speed_ratio",
                     "maximum_design_condition"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative.")
        if not 0 < self.minimum_gap_fraction < 1:
            raise ValueError("minimum_gap_fraction must lie strictly between zero and one.")
        if not 0 < self.minimum_speed_ratio < 1 or self.maximum_design_condition < 1:
            raise ValueError("Invalid speed/conditioning limits.")


def _design(parameters, bandwidth):
    modes = np.arange(1, bandwidth + 1)
    phase = parameters[:, None] * modes
    design = np.ones((len(parameters), 2 * bandwidth + 1))
    design[:, 1::2], design[:, 2::2] = np.cos(phase), np.sin(phase)
    derivative = np.zeros_like(design)
    derivative[:, 1::2] = -np.sin(phase) * modes
    derivative[:, 2::2] = np.cos(phase) * modes
    return design, derivative


def _labels(logits, minimum_gap_fraction):
    weights = softmax(np.r_[logits, 0.0])
    count = weights.size
    free_length = 2 * np.pi * (1.0 - minimum_gap_fraction)
    increments = 2 * np.pi * minimum_gap_fraction / count + free_length * weights
    return np.r_[0.0, np.cumsum(increments[:-1])], increments, weights, free_length


def _variable_projection(logits, points, settings):
    labels, increments, probabilities, free_length = _labels(
        logits, settings.minimum_gap_fraction
    )
    design, derivative = _design(labels, settings.bandwidth)
    scale = np.sqrt(len(points))
    diagonal = np.r_[0.0, np.repeat(np.arange(1, settings.bandwidth + 1)
                                  ** settings.spectral_order, 2)]
    matrix = np.vstack((design / scale,
                        np.sqrt(settings.spectral_penalty) * np.diag(diagonal)))
    rhs = np.vstack((points / scale, np.zeros((diagonal.size, 2))))
    coefficients = np.linalg.lstsq(matrix, rhs, rcond=None)[0]
    residual = design @ coefficients - points
    penalty = settings.spectral_penalty * np.sum((diagonal[:, None] * coefficients)**2)
    value = np.mean(np.sum(residual**2, axis=1)) + penalty
    label_gradient = 2.0 * np.sum(residual * (derivative @ coefficients), axis=1) / len(points)
    increment_gradient = np.r_[np.cumsum(label_gradient[:0:-1])[::-1], 0.0]
    gradient = free_length * probabilities * (
        increment_gradient - probabilities @ increment_gradient
    )
    return float(value), gradient[:-1], coefficients, labels, increments, residual, float(penalty)


def _boundary(coefficients, settings):
    cosine = np.zeros((settings.bandwidth + 1, 2))
    sine = np.zeros_like(cosine)
    cosine[0], cosine[1:], sine[1:] = coefficients[0], coefficients[1::2], coefficients[2::2]
    return FourierBoundary(cosine, sine, name="experimental_ordered_label_fourier",
                           provenance=CurveProvenance2D(source_kind="ordered_label_variable_projection"))


def _point_to_polygon_distances(query, polygon):
    edges = np.roll(polygon, -1, axis=0) - polygon
    offsets = query[:, None, :] - polygon[None, :, :]
    fractions = np.clip(np.sum(offsets * edges[None, :, :], axis=-1)
                        / np.sum(edges**2, axis=-1), 0.0, 1.0)
    return np.min(np.linalg.norm(offsets - fractions[..., None] * edges, axis=-1), axis=1)


def fit_without_arclength(parameters, points, *, bandwidth, validation_resolution=512):
    """The unregularized initial chord-label Fourier fit; not optimal labels."""

    start = perf_counter()
    fitted = fit_fourier_least_squares(parameters, points, bandwidth=bandwidth)
    curve = fitted.boundary.to_parameterization()
    report = validate_periodic_parameterization(curve, BoundaryValidationConfig(
        num_samples_per_component=validation_resolution, fourier_bandwidth=bandwidth
    ), raise_on_error=True)
    return MethodResult("skip-arclength-chord-labels", "success", fitted.boundary,
                        curve, report, fitted.residual, None, perf_counter() - start,
                        diagnostics={"condition_number": fitted.diagnostics.condition_number,
                                     "spectral_penalty": 0.0,
                                     "parameter_labels": "frozen_chord_length"})


def fit_parameter_aware(parameters, points, *, config=None, fallback: MethodResult):
    """Fit coefficients and cyclic labels with a fixed first-label phase gauge.

    All fitting weights are 1/M and remain fixed.  The optional k**(2q)
    coefficient penalty depends on parameter labels; it is not an invariant
    shape prior.  Failing final order, speed, topology, conditioning or fidelity
    gates returns the supplied valid baseline explicitly as a fallback.
    """

    settings = ParameterAwareConfig() if config is None else config
    if not isinstance(settings, ParameterAwareConfig):
        raise TypeError("config must be ParameterAwareConfig.")
    if fallback.status not in ("success", "fallback") or fallback.validation is None or not fallback.validation.valid:
        raise ValueError("A valid baseline fallback is required.")
    # Reuse the established immutable-sample validation, including phase/order.
    initial = fit_fourier_least_squares(parameters, points, bandwidth=settings.bandwidth)
    parameters = np.asarray(parameters, dtype=float)
    points = np.asarray(points, dtype=float)
    increments = np.diff(np.r_[parameters, 2 * np.pi])
    floor = 2 * np.pi * settings.minimum_gap_fraction / len(points)
    if np.min(increments) <= floor:
        raise ValueError("Input label increments are below the declared positive gap floor.")
    initial_weights = (increments - floor) / (2 * np.pi * (1 - settings.minimum_gap_fraction))
    logits = np.log(initial_weights[:-1] / initial_weights[-1])
    start = perf_counter()
    history = []
    def objective(values):
        result = _variable_projection(values, points, settings)
        return result[0], result[1]
    def callback(values):
        result = _variable_projection(values, points, settings)
        history.append({"objective_m2": result[0], "minimum_label_gap": float(np.min(result[4]))})
    optimized = minimize(objective, logits, jac=True, method="L-BFGS-B", callback=callback,
                         options={"maxiter": settings.max_iterations, "ftol": 1e-15,
                                  "gtol": 1e-13, "maxls": 30, "maxcor": 20})
    value, _, coefficients, labels, gaps, residual, penalty = _variable_projection(optimized.x, points, settings)
    boundary = _boundary(coefficients, settings)
    curve = boundary.to_parameterization()
    validation = BoundaryValidationConfig(num_samples_per_component=settings.validation_resolution,
                                          fourier_bandwidth=settings.bandwidth)
    report = validate_periodic_parameterization(curve, validation, raise_on_error=False)
    condition = float(np.linalg.cond(_design(labels, settings.bandwidth)[0]))
    residual_distances = np.linalg.norm(residual, axis=1)
    probe_t = 2 * np.pi * np.arange(settings.validation_resolution) / settings.validation_resolution
    speed = np.linalg.norm(curve.evaluate(probe_t).first_derivatives, axis=-1)
    # Setwise comparison against the same frozen input polygon, with no target
    # truth used for selection.  Local closest-point searches are refined on
    # both curves; their maxima are bounded by the baseline envelope plus a
    # sample-gap accuracy allowance.
    _, candidate_to_data = closest_parameters(points, curve,
                                               localization_samples=max(1024, 64 * settings.bandwidth))
    _, baseline_to_data = closest_parameters(points, fallback.parameterization,
                                             localization_samples=max(1024, 64 * settings.bandwidth))
    candidate_setwise = max(float(np.max(candidate_to_data)), float(np.max(
        _point_to_polygon_distances(curve.evaluate(probe_t).points, points))))
    baseline_setwise = max(float(np.max(baseline_to_data)), float(np.max(
        _point_to_polygon_distances(fallback.parameterization.evaluate(probe_t).points, points))))
    max_gap = float(np.max(np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=-1)))
    allowed = 1.1 * baseline_setwise + 0.05 * max_gap
    issues = list(report.issues)
    if np.min(speed) / np.max(speed) < settings.minimum_speed_ratio:
        issues.append("speed ratio below experiment floor")
    if condition > settings.maximum_design_condition:
        issues.append("Fourier design conditioning limit exceeded")
    if candidate_setwise > allowed:
        issues.append("frozen-point setwise fidelity worse than baseline envelope")
    if np.min(gaps) <= 0 or labels[0] != 0 or labels[-1] >= 2 * np.pi:
        issues.append("cyclic order or fixed first-label phase failed")
    diagnostics = {"config": asdict(settings), "optimizer_success": bool(optimized.success),
                   "optimizer_message": str(optimized.message), "iterations": int(optimized.nit),
                   "objective_evaluations": int(optimized.nfev), "objective_m2": value,
                   "coefficient_least_squares_solves": int(optimized.nfev) + len(history) + 2,
                   "spectral_penalty_m2": penalty, "condition_number": condition,
                   "initial_condition_number": initial.diagnostics.condition_number,
                   "minimum_label_gap": float(np.min(gaps)),
                   "parameter_labels": labels.tolist(), "history": history,
                   "fitting_weights": "fixed_uniform_1_over_M",
                   "phase_gauge": "first_label_zero_last_increment_reference_logit_zero",
                   "candidate_maximum_point_to_curve_m": float(np.max(candidate_to_data)),
                   "baseline_maximum_point_to_curve_m": float(np.max(baseline_to_data)),
                   "candidate_sampled_symmetric_polygon_distance_m": candidate_setwise,
                   "baseline_sampled_symmetric_polygon_distance_m": baseline_setwise,
                   "setwise_acceptance_allowance_m": allowed,
                   "candidate_validation": report.to_dict(),
                   "regularizer_is_parameterization_dependent": True}
    if issues:
        return MethodResult("experimental-ordered-label-fourier", "fallback",
                            fallback.representation, fallback.parameterization,
                            fallback.validation, fallback.input_fit_residual, None,
                            perf_counter() - start, diagnostics=diagnostics,
                            failure_reason="; ".join(issues))
    return MethodResult("experimental-ordered-label-fourier", "success", boundary, curve,
                        report, ResidualDiagnostics(float(np.max(residual_distances)),
                        float(np.sqrt(np.mean(residual_distances**2)))), None,
                        perf_counter() - start, diagnostics=diagnostics)
