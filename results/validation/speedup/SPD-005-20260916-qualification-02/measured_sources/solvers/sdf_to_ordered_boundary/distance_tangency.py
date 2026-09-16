"""Opt-in signed-distance contact/tangent-jet Fourier conversion experiment.

This assumes continuous field and gradient access.  It is not sparse-sample
Reach For the Arcs: no feasibility-arc search, sphere-union algorithm or Poisson
reconstruction is implemented.  For an exact SDF, the contact formula is also
one Newton projection.  Candidate construction never accepts target geometry
or measured physical fields as inputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np
from scipy.optimize import minimize

from ordered_boundary import BoundaryValidationConfig, validate_periodic_parameterization
from .frontend import polygon_self_intersection_count, polygon_signed_area
from .parameter_aware import _design, _labels, closest_parameters
from .representations import FourierBoundary, fit_fourier_least_squares
from .results import MethodResult, ResidualDiagnostics


def _readonly(values, name, shape=None):
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real.")
    result = np.array(values, dtype=float, copy=True)
    if not np.all(np.isfinite(result)) or (shape is not None and result.shape != shape):
        raise ValueError(f"{name} has nonfinite values or an invalid shape.")
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class DistanceContactSamples:
    source_points: np.ndarray
    signed_values: np.ndarray
    contacts: np.ndarray
    normals: np.ndarray
    contact_normalized_zero_residual_m: np.ndarray
    metric_radii_assumed: bool

    def __post_init__(self):
        sources = _readonly(self.source_points, "source_points")
        if sources.ndim != 2 or sources.shape[1] != 2 or len(sources) < 3:
            raise ValueError("source_points must have shape (M,2), M>=3.")
        object.__setattr__(self, "source_points", sources)
        count = len(sources)
        for name, shape in (("signed_values", (count,)), ("contacts", (count, 2)),
                            ("normals", (count, 2)),
                            ("contact_normalized_zero_residual_m", (count,))):
            object.__setattr__(self, name, _readonly(getattr(self, name), name, shape))
        if not np.allclose(np.linalg.norm(self.normals, axis=1), 1., atol=1e-12, rtol=1e-12):
            raise ValueError("Contact normals must be unit vectors.")
        if np.any(self.contact_normalized_zero_residual_m < 0):
            raise ValueError("Contact residuals must be nonnegative.")
        if not isinstance(self.metric_radii_assumed, (bool, np.bool_)):
            raise TypeError("metric_radii_assumed must be boolean.")


@dataclass(frozen=True)
class DistanceTangencyConfig:
    bandwidth: int = 8
    max_iterations: int = 100
    tangency_weight: float = .1
    spectral_penalty: float = 0.0
    spectral_order: int = 2
    minimum_gap_fraction: float = 1e-4
    minimum_speed_ratio: float = 1e-3
    contact_zero_tolerance_m: float = 1e-5
    contact_fit_tolerance_m: float = 2e-4
    closest_contact_tolerance_m: float = 2e-4
    validation_resolution: int = 512

    def __post_init__(self):
        for name in ("bandwidth", "max_iterations", "spectral_order", "validation_resolution"):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                raise TypeError(f"{name} must be an integer.")
            if value < (32 if name == "validation_resolution" else 1):
                raise ValueError(f"{name} is too small.")
        for name in ("tangency_weight", "spectral_penalty", "minimum_gap_fraction", "minimum_speed_ratio",
                     "contact_zero_tolerance_m", "contact_fit_tolerance_m", "closest_contact_tolerance_m"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative.")
            object.__setattr__(self, name, value)
        if not 0 < self.minimum_gap_fraction < 1 or not 0 < self.minimum_speed_ratio < 1:
            raise ValueError("Gap and speed floors must be between zero and one.")
        if min(self.contact_zero_tolerance_m, self.contact_fit_tolerance_m,
               self.closest_contact_tolerance_m) <= 0:
            raise ValueError("Contact tolerances must be positive.")


def make_offsurface_queries(field, ordered_points, *, offset_m=.003, tangent_fraction=.15):
    """Use only a shared extracted loop and its queried field normals.

    Tangential jitter avoids the vacuous experiment in which every off-surface
    sample is a normal offset whose exact contact is an already-known point.
    Its size is bounded by neighboring chord gaps, and cyclic order is audited
    again after contact construction.
    """
    points = _readonly(ordered_points, "ordered_points")
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("ordered_points must have shape (M,2).")
    if not np.isfinite(offset_m) or offset_m <= 0 or not 0 <= tangent_fraction <= .25:
        raise ValueError("Invalid normal offset or tangential fraction.")
    gradients = np.asarray(field.gradient(points), dtype=float)
    norms = np.linalg.norm(gradients, axis=1)
    if np.any(norms < 1e-10):
        raise ValueError("Near-critical field at seed points.")
    normals = gradients / norms[:, None]
    tangents = np.column_stack((-normals[:, 1], normals[:, 0]))
    gaps = np.linalg.norm(np.roll(points, -1, axis=0)-points, axis=1)
    local_gap = np.minimum(gaps, np.roll(gaps, 1))
    indices = np.arange(len(points))
    signed_offset = offset_m * np.where(indices % 2, -1., 1.)
    jitter = tangent_fraction * local_gap * np.sin(indices*2.399963229728653)
    return points + signed_offset[:, None]*normals + jitter[:, None]*tangents


def sample_distance_contacts(field, source_points):
    """Query signed values/gradients once, then independently query contacts.

    A unit gradient at the interface is insufficient: the returned contact's
    zero residual is tested later before a metric-radius fit may be accepted.
    """
    sources = _readonly(source_points, "source_points")
    values = np.asarray(field.value(sources), dtype=float).reshape(-1)
    gradients = np.asarray(field.gradient(sources), dtype=float)
    norms = np.linalg.norm(gradients, axis=1)
    if np.any(norms < 1e-10):
        raise ValueError("Near-critical off-surface gradient.")
    normals = gradients / norms[:, None]
    contacts = sources-values[:, None]*normals
    residual = np.abs(np.asarray(field.value(contacts), dtype=float).reshape(-1))
    contact_gradients = np.asarray(field.gradient(contacts), dtype=float)
    contact_norms = np.linalg.norm(contact_gradients, axis=1)
    if np.any(contact_norms < 1e-10):
        raise ValueError("Near-critical contact gradient.")
    return DistanceContactSamples(sources, values, contacts, normals, residual/contact_norms, True)


def projected_contact_samples(field, source_points, projected_points):
    """A distance-free tangent-jet control from ordinary zero-set projections."""
    contacts = np.asarray(projected_points, dtype=float)
    gradients = np.asarray(field.gradient(contacts), dtype=float)
    norms = np.linalg.norm(gradients, axis=1)
    if np.any(norms < 1e-10):
        raise ValueError("Near-critical projected contact gradient.")
    residual = np.abs(np.asarray(field.value(contacts), dtype=float).reshape(-1))/norms
    return DistanceContactSamples(source_points, np.zeros(len(contacts)), contacts,
                                  gradients/norms[:, None], residual, False)


def _tangent_objective(logits, samples, config):
    labels, gaps, probabilities, free_length = _labels(logits, config.minimum_gap_fraction)
    design, derivative = _design(labels, config.bandwidth)
    modes = np.r_[0., np.repeat(np.arange(1, config.bandwidth+1), 2)]
    second = -design*modes[None, :]**2
    p = design.shape[1]
    position_rows = np.kron(design, np.eye(2))
    tangent_rows = (derivative[:, :, None]*samples.normals[:, None, :]).reshape(len(labels), 2*p)
    penalties = np.repeat(modes**config.spectral_order, 2)
    count_scale = np.sqrt(len(labels))
    matrix = np.vstack((position_rows/count_scale,
                        np.sqrt(config.tangency_weight)*tangent_rows/count_scale,
                        np.sqrt(config.spectral_penalty)*np.diag(penalties)))
    rhs = np.r_[samples.contacts.reshape(-1)/count_scale, np.zeros(len(labels)+2*p)]
    coefficients = np.linalg.lstsq(matrix, rhs, rcond=None)[0].reshape(p, 2)
    residual = design@coefficients-samples.contacts
    tangent = np.sum((derivative@coefficients)*samples.normals, axis=1)
    penalty = config.spectral_penalty*np.sum((penalties*coefficients.reshape(-1))**2)
    value = np.mean(np.sum(residual**2, axis=1)+config.tangency_weight*tangent**2)+penalty
    label_gradient = 2*np.sum(residual*(derivative@coefficients), axis=1)/len(labels)
    label_gradient += (2*config.tangency_weight*tangent
                       * np.sum((second@coefficients)*samples.normals, axis=1)/len(labels))
    increment_gradient = np.r_[np.cumsum(label_gradient[:0:-1])[::-1], 0.]
    gradient = free_length*probabilities*(increment_gradient-probabilities@increment_gradient)
    return float(value), gradient[:-1], coefficients, labels, gaps, residual, tangent


def _curve(coefficients, bandwidth):
    cosine = np.zeros((bandwidth+1, 2)); sine = np.zeros_like(cosine)
    cosine[0], cosine[1:], sine[1:] = coefficients[0], coefficients[1::2], coefficients[2::2]
    return FourierBoundary(cosine, sine, name="experimental_distance_contact_tangent_jet")


def audit_closest_contacts(samples, curve, *, assigned_parameters, localization_samples=1024):
    """Check actual nearest distances/side, not just tangent stationarity."""
    parameter, distance = closest_parameters(samples.source_points, curve,
                                               localization_samples=localization_samples, candidates=8)
    refined_parameter, refined_distance = closest_parameters(samples.source_points, curve,
        localization_samples=2*localization_samples, candidates=8)
    nearest = curve.evaluate(refined_parameter)
    speed = np.linalg.norm(nearest.first_derivatives, axis=1)
    normal = np.column_stack((nearest.first_derivatives[:, 1], -nearest.first_derivatives[:, 0]))/speed[:, None]
    side = np.sum((samples.source_points-nearest.points)*normal, axis=1)
    signed_distance = np.where(side < 0, -1., 1.)*refined_distance
    assigned = curve.evaluate(assigned_parameters).points
    assigned_distance = np.linalg.norm(samples.source_points-assigned, axis=1)
    return {"closest_point_refinement_agreement_m": float(np.max(np.abs(distance-refined_distance))),
            "assigned_contact_excess_distance_m": float(np.max(np.maximum(assigned_distance-refined_distance, 0))),
            "metric_radius_maximum_error_m": (float(np.max(np.abs(signed_distance-samples.signed_values)))
                                             if samples.metric_radii_assumed else None),
            "source_side_mismatches": (int(np.sum(np.sign(signed_distance)!=np.sign(samples.signed_values)))
                                       if samples.metric_radii_assumed else None),
            "closest_point_policy": "dense_multistart_local_refinement_agreement_not_a_global_certificate"}


def fit_distance_tangency(samples, initial_parameters, *, fallback, config=None):
    """Return (accepted MethodResult, raw candidate FourierBoundary).

    Rejected metric assumptions preserve both their raw diagnostic candidate
    and the valid baseline fallback.  All rejection thresholds come from the
    supplied fixed config; no reference geometry/field errors select a fit.
    """
    settings = DistanceTangencyConfig() if config is None else config
    if not isinstance(samples, DistanceContactSamples) or not isinstance(settings, DistanceTangencyConfig):
        raise TypeError("Expected DistanceContactSamples and DistanceTangencyConfig.")
    if not isinstance(fallback, MethodResult) or fallback.validation is None or not fallback.validation.valid:
        raise ValueError("A valid zero-projection baseline fallback is required.")
    start = perf_counter()
    # Established phase/order and sample-count checks; no sorting or dropping.
    fit_fourier_least_squares(initial_parameters, samples.contacts, bandwidth=settings.bandwidth)
    parameters = np.asarray(initial_parameters, dtype=float)
    if parameters[0] != 0.:
        raise ValueError("The declared phase gauge requires the first initial parameter to be zero.")
    increments = np.diff(np.r_[parameters, 2*np.pi])
    floor = 2*np.pi*settings.minimum_gap_fraction/len(parameters)
    if np.min(increments) <= floor:
        raise ValueError("Initial label increments violate the configured positive gap floor.")
    probabilities = (increments-floor)/(2*np.pi*(1-settings.minimum_gap_fraction))
    logits = np.log(probabilities[:-1]/probabilities[-1])
    def objective(value):
        result = _tangent_objective(value, samples, settings)
        return result[0], result[1]
    optimized = minimize(objective, logits, jac=True, method="L-BFGS-B",
                         options={"maxiter": settings.max_iterations, "ftol": 1e-15,
                                  "gtol": 1e-13, "maxcor": 20, "maxls": 30})
    value, _, coefficients, labels, gaps, residual, tangent = _tangent_objective(optimized.x, samples, settings)
    candidate = _curve(coefficients, settings.bandwidth)
    curve = candidate.to_parameterization()
    report = validate_periodic_parameterization(curve, BoundaryValidationConfig(
        num_samples_per_component=settings.validation_resolution, fourier_bandwidth=settings.bandwidth),
        raise_on_error=False)
    if not report.valid:
        # Do not discretize invalid/zero-speed geometry merely to generate
        # secondary diagnostics: preserve the raw coefficients and valid path.
        return MethodResult("experimental-distance-contact-tangent-jet", "fallback",
            fallback.representation, fallback.parameterization, fallback.validation,
            fallback.input_fit_residual, None, perf_counter()-start,
            {"config": asdict(settings), "optimizer_success": bool(optimized.success),
             "optimizer_message": str(optimized.message), "iterations": int(optimized.nit),
             "coefficient_solve_count": int(optimized.nfev)+2,
             "raw_candidate_validation": report.to_dict(),
             "rejected_candidate_available": True, "parameter_labels": labels.tolist(),
             "metric_radii_assumed": samples.metric_radii_assumed},
            failure_reason="invalid candidate: "+"; ".join(report.issues)), candidate
    issues = list(report.issues)
    if polygon_self_intersection_count(samples.contacts) or polygon_signed_area(samples.contacts) <= 0:
        issues.append("contact order/orientation is not a simple CCW loop")
    if np.max(samples.contact_normalized_zero_residual_m) > settings.contact_zero_tolerance_m:
        issues.append("distance contact is not on the queried field zero set")
    errors = np.linalg.norm(residual, axis=1)
    if np.max(errors) > settings.contact_fit_tolerance_m:
        issues.append("contact fitting fidelity tolerance exceeded")
    query = curve.discretize(settings.validation_resolution)
    if np.min(query.speeds)/np.max(query.speeds) < settings.minimum_speed_ratio:
        issues.append("minimum speed ratio failed")
    correspondence = curve.evaluate(labels)
    n = np.column_stack((correspondence.first_derivatives[:, 1], -correspondence.first_derivatives[:, 0]))
    n /= np.linalg.norm(n, axis=1)[:, None]
    minimum_normal_dot = float(np.min(np.sum(n*samples.normals, axis=1)))
    if minimum_normal_dot <= 0:
        issues.append("contact normal orientation is inconsistent")
    nearest_report = audit_closest_contacts(samples, curve, assigned_parameters=labels)
    if nearest_report["assigned_contact_excess_distance_m"] > settings.closest_contact_tolerance_m:
        issues.append("assigned tangent contact is not the closest contact")
    if samples.metric_radii_assumed:
        if nearest_report["metric_radius_maximum_error_m"] > settings.closest_contact_tolerance_m:
            issues.append("nearest signed distance disagrees with input metric radii")
        if nearest_report["source_side_mismatches"]:
            issues.append("inside/outside source sign inconsistency")
    if nearest_report["closest_point_refinement_agreement_m"] > .1*settings.closest_contact_tolerance_m:
        issues.append("closest-contact refinement did not stabilize")
    diagnostics = {"config": asdict(settings), "optimizer_success": bool(optimized.success),
        "optimizer_message": str(optimized.message), "iterations": int(optimized.nit),
        "coefficient_solve_count": int(optimized.nfev)+2, "objective_m2": value,
        "metric_radii_assumed": samples.metric_radii_assumed, "parameter_labels": labels.tolist(),
        "minimum_parameter_gap": float(np.min(gaps)),
        "maximum_contact_zero_residual_m": float(np.max(samples.contact_normalized_zero_residual_m)),
        "maximum_contact_fit_error_m": float(np.max(errors)),
        "rms_normal_dot_tangent_m": float(np.sqrt(np.mean(tangent**2))),
        "minimum_contact_normal_dot": minimum_normal_dot,
        "design_condition": float(np.linalg.cond(_design(labels, settings.bandwidth)[0])),
        "closest_contacts": nearest_report, "raw_candidate_validation": report.to_dict(),
        "phase_gauge": "first_label_zero", "penalty_depends_on_parameterization": True,
        "rejected_candidate_available": bool(issues)}
    if issues:
        return MethodResult("experimental-distance-contact-tangent-jet", "fallback",
            fallback.representation, fallback.parameterization, fallback.validation,
            fallback.input_fit_residual, None, perf_counter()-start, diagnostics,
            failure_reason="; ".join(issues)), candidate
    return MethodResult("experimental-distance-contact-tangent-jet", "success", candidate, curve,
        report, ResidualDiagnostics(float(np.max(errors)), float(np.sqrt(np.mean(errors**2)))),
        None, perf_counter()-start, diagnostics), candidate
