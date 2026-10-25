"""Mathematical and numerical conditions, ordered by A1–C12 and endpoint.

Each check exposes its quantity, comparison and existing threshold source.
Callers retain the original invocation point and response. No check solves
physics or mutates optimizer state. Geometry-validity certificate decisions
and their records live with the optional certified spectral method.
"""
import numpy as np
from scipy.spatial import cKDTree
from ordered_boundary.validation_cache import array_key, memoized_validation
from .errors import NumericalFailure


# A1. Orientation, log-modulus interval and reciprocal certificate.

def require_positive_orientation(area):
    """A1/C10 coefficient signed area must be strictly positive."""
    if not area > 0:
        raise ValueError('Curve must be counterclockwise (positive signed area).')


def require_modulus_domain(upper, tolerance):
    """The coefficient l1 upper bound and requested log accuracy must be positive."""
    if not np.isfinite(upper) or upper <= 0 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Positive finite modulus norm and log tolerance required.')


def require_positive_modulus_sample(sampled):
    """The sampled minimum proposes the interval; it is not its certificate."""
    if not sampled > 0:
        raise ValueError(f'Inconclusive interval proposal: sampled min |W|^2 = {sampled:g}.')


def log_tail_exceeds(ratio, degree, tolerance):
    """Unchanged geometric bound for the omitted logarithm series."""
    return 2*ratio**(degree+1)/((degree+1)*(1-ratio)) > tolerance


def require_log_degree(degree, maximum, beta, upper):
    if degree > maximum:
        raise ValueError(f'log|W|^2 needs more than {maximum} Chebyshev terms '
                         f'(beta/Lambda={beta/upper:.3g}); curve is nearly self-touching.')


def require_finite_certificate(residual, norm, allowance, lower):
    """Residual evidence must be finite and the reciprocal l1 norm positive."""
    if not np.isfinite([residual, norm, allowance, lower]).all() or norm <= 0:
        raise ValueError('Non-finite reciprocal residual certificate.')


def interval_certified(lower, beta):
    return lower >= beta


def interval_needs_recompute(lower, beta):
    # Device certificate uses <, distinct from negating >= for NaNs.
    return lower < beta


def require_positive_certificate(lower, residual):
    if not lower > 0:
        raise ValueError(f'|W|^2 lower bound not certified (coefficient residual {residual:.3g}).')


def require_finite_log_coefficients(log, *, device=False):
    if device:
        import torch
        finite = bool(torch.isfinite(log).all())
    else:
        finite = np.isfinite(log).all()
    if not finite:
        raise ValueError('Non-finite log modulus coefficients.')


# A2. Material parameters, radial expansion and coefficient workspace.

def require_radial_domain(ko, ki, upper, tolerance):
    if (not np.isfinite(upper) or upper <= 0 or
            not np.isfinite(tolerance) or not 0 < tolerance < 1 or
            not np.isfinite(ko) or not np.isfinite(ki) or ko == 0 or ki == 0):
        raise ValueError('Finite nonzero wavenumbers, upper > 0 and 0 < tolerance < 1 required.')


def require_finite_radial_coefficients(coefficients):
    if not np.all(np.isfinite(coefficients)):
        raise ValueError('Non-finite analytic radial Chebyshev coefficients.')


def radial_series_converged(small, count, ko, ki, tail, tolerance, size):
    """Every retained function's decay and omitted Neumann bound must pass."""
    return np.all(small[:, count//2]) and (ko == ki or np.all(tail <= tolerance*size))


def require_trace_workspace(cutoff, band):
    if cutoff > band:
        raise ValueError('Trace cutoff must fit inside the coefficient window.')


def require_geometry_workspace(window, cutoff, geometry_band):
    if window < max(cutoff, geometry_band):
        raise ValueError('Coefficient workspace must contain trace and geometry bands.')


def require_material_frequency(k, contrast):
    if not (np.isfinite(k) and np.real(k) > 0 and np.imag(k) >= 0 and np.isfinite(contrast) and contrast > 0):
        raise ValueError('Wavenumber and contrast must be finite and positive.')


def radial_decay(coefficients, tolerance, size):
    """Suffix coefficient maxima determine the existing truncation decision."""
    later = np.maximum.accumulate(np.abs(coefficients)[:, ::-1], axis=1)[:, ::-1]
    return later <= tolerance*size[:, None]


def bessel_requires_rescaling(value):
    """Protect the unchanged Miller recurrence from intermediate overflow."""
    return abs(value) > 1e200


def neumann_tail_unbounded(ratio):
    return ratio >= 1


# A3. Graf expansion, source separation and cancellation.

def require_graf_separation(distance, radius):
    if np.any(distance <= radius):
        raise ValueError('Graf expansion requires every source and receiver outside the '
                         'coefficient bounding circle of the curve.')


def require_wave_cancellation(loss, series_loss, x):
    if loss > series_loss:
        raise ValueError(f'Regular-wave series cancellation {loss:.2g} exceeds {series_loss:g} (|k| rho={x:.3g}).')


def graf_tail_orders(tail, tolerance):
    """Indices whose finite omitted-tail bound passes for every point."""
    return np.flatnonzero(np.all(np.isfinite(tail) & (tail <= tolerance), axis=1))


def graf_tail_is_bounded(increasing, ratio):
    return increasing and np.all(ratio < 1)


def graf_hankel_increasing(scaled, a, order):
    return np.all(scaled[-2]*a/order <= scaled[-1])


def regular_wave_term_count(x, tolerance):
    """First omitted n=0 regular-wave term below the requested accuracy."""
    from scipy.special import gammaln
    p = np.arange(2, 400)
    omitted = 2*p*np.log(max(x, 1e-300)/2)-2*gammaln(p+1)
    return int(p[np.argmax(omitted <= np.log(tolerance))])


# A4. Predicted measurements.

def require_finite_prediction(prediction):
    if not np.isfinite(prediction).all():
        raise FloatingPointError('Nonfinite modal prediction')


# B6. Complete-trial geometry differentiation.

def require_derivative_step(step):
    if not np.isfinite(step) or step <= 0:
        raise ValueError('Positive finite derivative step required.')


def require_arclength_monotone(gaps):
    """Works on the existing NumPy or device differences without transfer."""
    if bool((gaps <= 0).any()):
        raise ValueError('Non-monotone arclength map.')


# B7–B8. Data Jacobian and gradient.

def require_finite_data_jacobian(J_data):
    if not np.isfinite(J_data).all():
        raise FloatingPointError('Nonfinite modal shape Jacobian.')


def require_gradient(g, coordinate_count):
    if g.shape != (coordinate_count,) or not np.isfinite(g).all():
        raise FloatingPointError('Invalid objective gradient')


# C9. Damping discrepancy root.

def hanke_floor_attains_target(excess):
    return excess >= 0


def hanke_below_target(excess):
    return excess < 0


# Geometry construction and direct validity checks.

def inside_box(curve, box):
    if box is None:
        return True
    from .continuation.geometry import grid_size
    z = curve.values(grid_size(curve.band))
    (x0, y0), (x1, y1) = box
    return bool(np.all(z.real > x0) and np.all(z.real < x1) and np.all(z.imag > y0) and np.all(z.imag < y1))


def check_area(coefficients):
    """Require positive finite continuous signed area."""
    from .continuation.geometry import signed_area
    from .errors import UpdateRefused
    area = signed_area(coefficients)
    if not np.isfinite(area) or area <= 0:
        raise UpdateRefused('irregular_parameterization', 'Curve area must be positive.')


def check_speed(speeds):
    """Require the existing minimum-speed fraction on the supplied grid."""
    from .errors import UpdateRefused
    if not np.isfinite(speeds).all() or np.min(speeds) < 1e-6*np.mean(speeds) or np.min(speeds) <= 0:
        raise UpdateRefused('irregular_parameterization', 'Curve speed is too small.')


def check_intersection(points):
    """Reject crossing or touching nonadjacent sampled segments."""
    from .errors import UpdateRefused
    if self_intersections(points):
        raise UpdateRefused('self_intersection', 'Curve self-intersects.')


def require_sampled_moved_curve(nodes):
    """Run before refitting each moved curve, preserving refusal precedence."""
    from .errors import UpdateRefused
    if nodes.signed_area <= 0 or np.min(nodes.speeds) < 1e-6*np.mean(nodes.speeds):
        raise UpdateRefused('irregular_parameterization', 'Invalid displaced curve.')
    if self_intersections(nodes.points):
        raise UpdateRefused('self_intersection', 'Displaced curve self-intersects.')


def require_sampled_stored_curve(nodes):
    """Final stored-curve sampled test; messages differ from moved-curve checks."""
    if nodes.signed_area <= 0 or np.min(nodes.speeds) < 1e-6*np.mean(nodes.speeds):
        raise ValueError('Curve must be regular and counterclockwise.')
    if self_intersections(nodes.points):
        raise ValueError('Curve self-intersects.')


def require_refit_curve(nodes):
    if nodes.signed_area <= 0 or np.min(nodes.speeds) < 1e-6 * np.mean(nodes.speeds):
        raise ValueError("Invalid displaced curve.")
    if self_intersections(nodes.points):
        raise ValueError("Displaced curve self-intersects.")


def require_projection_agreement(error, radius, tolerance):
    """Grid/doubled-grid position discrepancy, scaled by perimeter radius."""
    from .errors import UpdateRefused
    if error/radius > tolerance:
        raise UpdateRefused('unresolved_projection', f'geometry grid refinement {error/radius:g}')


def require_spline_projection(error, tolerance, perimeter):
    if error > tolerance * perimeter / (2 * np.pi):
        raise ValueError(f"Arclength projection unresolved: {error / (perimeter / (2*np.pi)):.3g} relative.")


def step_too_small(a, scale, tolerance):
    return np.linalg.norm(a) / scale <= tolerance


def require_geometry_proposal_allowance(proposals, cap):
    from .errors import GeometryProposalCap
    if proposals >= cap:
        raise GeometryProposalCap('stage geometry proposal cap reached')


def self_intersections(points, relative_tolerance=1e-12):
    """Count nonadjacent crossing/touching segments without all-pairs arrays.

    Intersecting segments have centers at most half the sum of their lengths
    apart. The largest segment length therefore gives a conservative search
    radius. Padding also includes the reference predicate's tolerated touches.
    This prunes comparisons, not geometry samples or admissibility conditions.
    """
    points = np.asarray(points, float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError("Expected at least three finite planar points.")
    if not np.isfinite(relative_tolerance) or relative_tolerance < 0:
        raise ValueError("Tolerance must be finite and nonnegative.")
    return memoized_validation("hybrid_self_intersection",
        lambda: (array_key(points), array_key(np.asarray(relative_tolerance))),
        lambda: _self_intersections(points, relative_tolerance))


def _self_intersections(points, relative_tolerance):
    """Unchanged predicate; called only after public input validation."""
    scale = max(np.linalg.norm(np.ptp(points, axis=0)), np.finfo(float).tiny)
    length_tolerance = relative_tolerance * scale
    cross_tolerance = relative_tolerance * scale ** 2
    end = np.roll(points, -1, axis=0)
    delta = end - points
    radius = np.max(np.linalg.norm(delta, axis=1)) + np.sqrt(2) * length_tolerance
    # Include roundoff in center construction for translated coordinate systems.
    radius += 16 * np.finfo(float).eps * max(scale, float(np.max(np.abs(points))))
    pairs = cKDTree(points + delta / 2).query_pairs(radius, output_type="ndarray")
    if not len(pairs):
        return 0
    gap = pairs[:, 1] - pairs[:, 0]
    i, j = pairs[(gap > 1) & (gap < len(points) - 1)].T
    a, b, c, d = points[i], end[i], points[j], end[j]

    def cross(first, second):
        return first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]

    def on_segment(point, start, stop):
        return np.all((point >= np.minimum(start, stop) - length_tolerance)
                      & (point <= np.maximum(start, stop) + length_tolerance), axis=1)

    o1, o2 = cross(b - a, c - a), cross(b - a, d - a)
    o3, o4 = cross(d - c, a - c), cross(d - c, b - c)
    proper = (((o1 > cross_tolerance) & (o2 < -cross_tolerance)
              | (o1 < -cross_tolerance) & (o2 > cross_tolerance))
              & ((o3 > cross_tolerance) & (o4 < -cross_tolerance)
              | (o3 < -cross_tolerance) & (o4 > cross_tolerance)))
    touching = ((np.abs(o1) <= cross_tolerance) & on_segment(c, a, b)
                | (np.abs(o2) <= cross_tolerance) & on_segment(d, a, b)
                | (np.abs(o3) <= cross_tolerance) & on_segment(a, c, d)
                | (np.abs(o4) <= cross_tolerance) & on_segment(b, c, d))
    return int(np.count_nonzero(proper | touching))


# C11. Production/refined agreement and acceptance.

def relative_columns(a, b):
    return np.linalg.norm(a - b, axis=0) / np.linalg.norm(b, axis=0)


def require_finite_trial(candidate):
    if not np.isfinite(candidate.loss) or not np.isfinite(candidate.prediction).all():
        raise NumericalFailure('non-finite production evaluation at candidate state')


def production_nondecreasing(candidate_loss, current_loss):
    # Retain >=, including its original NaN behavior; finiteness is checked first.
    return candidate_loss >= current_loss


def fields_agree(discrepancy, tolerances):
    return bool(np.all(np.isfinite(discrepancy)) and np.all(discrepancy <= tolerances))


def fields_unresolved(discrepancy, tolerances):
    return not np.all(np.isfinite(discrepancy)) or np.any(discrepancy > tolerances)


def acceptance(base, candidate, refined_base, refined_candidate, config):
    dp, dr = base - candidate, refined_base - refined_candidate
    margin = max(config.acceptance_absolute_margin + config.acceptance_relative_margin * base,
                 config.acceptance_absolute_margin + config.acceptance_relative_margin * refined_base)
    uncertainty = config.cross_resolution_factor * abs(dp - dr)
    return dict(production_gain=dp, refined_gain=dr, margin=margin,
                disagreement_allowance=uncertainty, accepted=bool(min(dp, dr) > margin + uncertainty))


def resolution_check(base, candidate, refined_base, refined_candidate, stage, config):
    """Gain decision and field qualification, retaining the pre-gate decision."""
    states = (base, candidate, refined_base, refined_candidate)
    if any(s is None for s in states):
        raise NumericalFailure("production or refined evaluation failed")
    if any(not np.isfinite(s.loss) or not np.isfinite(s.prediction).all() for s in states):
        raise NumericalFailure("non-finite production or refined evaluation")
    discrepancy = relative_columns(candidate.prediction, refined_candidate.prediction)
    if not np.isfinite(discrepancy).all():
        raise NumericalFailure("non-finite prediction discrepancy")
    row = dict(acceptance(*(s.loss for s in states), config),
               prediction_discrepancy=discrepancy.tolist(),
               refined_base_loss=refined_base.loss, refined_candidate_loss=refined_candidate.loss,
               gate=config.resolution_gate,
               prediction_discrepancy_ratios=(discrepancy/np.asarray(stage.discrepancy_tolerances)).tolist())
    accurate = bool(np.all(discrepancy <= stage.discrepancy_tolerances))
    if not accurate:
        row['numerical_obstruction'] = True
        if config.resolution_gate == 'absolute':
            row['accepted'] = False
    return row, accurate


# C12. Damping feedback, stopping and continuation.

def loss_converged(loss, tolerance):
    return loss <= tolerance


def gradient_converged(g, tolerance):
    return np.linalg.norm(g, ord=np.inf) <= tolerance


def severely_shortened(fraction):
    return fraction <= .25


def poor_model_agreement(gain_ratio):
    return gain_ratio is None or not np.isfinite(gain_ratio) or gain_ratio < .25


def shortened_or_marginal(fraction, gain_ratio):
    return fraction < .75 or gain_ratio < .75


def shortened_stagnation(history, window, minimum_progress):
    if len(history) <= window:
        return False
    start, end = history[-window-1]['loss'], history[-1]['loss']
    shortened = sum(row.get('accepted_fraction', 1.) <= .25 for row in history[-window:])
    return (shortened >= (window+1)//2 and
            (start-end)/max(abs(start), np.finfo(float).tiny) < minimum_progress)


def insufficient_progress(history, window, minimum_progress):
    """Plain accepted-loss progress exit, without a shortened-step condition."""
    if len(history) <= window:
        return False
    start, end = history[-window-1]['loss'], history[-1]['loss']
    return (start-end)/max(abs(start), np.finfo(float).tiny) < minimum_progress


def require_observable_frontier(paired):
    if not np.isfinite(paired).all() or paired.max() <= 0:
        raise FloatingPointError('No finite nonzero observable frontier')


# Optional A4/B6/C10–C12 paths. Same comparisons and thresholds as their
# original implementations; each caller retains its own exception and response.

def invalid_nodal_material(k, contrast):
    return k.real <= 0 or k.imag < 0 or not np.isfinite(k) or contrast <= 0 or not np.isfinite(contrast)


def nonfinite_prediction(prediction):
    return not np.isfinite(prediction).all()


def unobservable_frontier(paired):
    return not np.isfinite(paired).all() or paired.max() <= 0


def irregular_projection_derivative(sigma):
    return not np.all(np.isfinite(sigma)) or np.min(sigma) <= 0


def nonfinite_projection_derivative(out):
    return not np.isfinite(out).all()


def nonpositive_gaussian_width(width):
    return not width > 0


def ill_conditioned_gaussian_interpolation(condition):
    return not condition <= 1e12


def inaccurate_gaussian_coordinates(relative):
    return max(relative) > 1e-4


def gaussian_norm_kink(nonzero, dw):
    return np.any(~nonzero & (abs(dw) > 0))


def gaussian_clipping_kink(C):
    return abs(C-.8) <= 1e-12


def inaccurate_gaussian_direction(error):
    return error > 1e-4


def unresolved_gaussian_projection(refinement, radius, tolerance):
    return refinement/radius > tolerance


def invalid_similarity_radius(radius):
    return not np.isfinite(radius) or radius <= 0


def invalid_similarity_factor(factor):
    return not np.isfinite(factor) or factor <= 0


# Optional C11. Stage-entry nodal qualification.
def nodal_profile_passed(fields, derivatives, tolerances):
    return bool(np.all(np.isfinite(fields)) and np.all(np.isfinite(derivatives)) and
                np.all(fields <= tolerances) and np.all(derivatives <= 1e-3))


# Endpoint. Independent field, Jacobian and complete-trial checks.

def endpoint_passed(fields, field_tolerances, derivative, full_trial_error):
    """Existing all-frequency field, per-column Jacobian and directional FD tests."""
    return bool(np.all(fields <= field_tolerances) and
                max(derivative) <= 1e-3 and full_trial_error <= 1e-3)


def endpoint_reference_passed(passed, fields, field_tolerances, derivative):
    return bool(passed and np.all(fields <= field_tolerances) and np.all(derivative <= 1e-3))
