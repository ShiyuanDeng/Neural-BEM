"""C9. Gauss–Newton quantities → damped local-coordinate proposal.

J is (real measurement, update coordinate); g is (coordinate,);
H_GN and D are (coordinate, coordinate). Proposals are in metres.
"""
import numpy as np
from . import checks

def hanke_damping(matrix, residual, metric, ratio, floor=1e-12):
    """Hanke's regularizing-LM parameter in the metric R (Inverse Problems 13, 1997).

    Returns (lam, attainable) with ||r + J d(lam)|| = ratio ||r|| for
    d(lam) = -(J^T J + lam R)^{-1} J^T r. The linearized residual rises
    monotonically from its Gauss-Newton value (lam = 0) to ||r||; if the
    Gauss-Newton value already exceeds ratio ||r||, return the floor
    ``floor`` x the mean eigenvalue of the R-scaled Gauss-Newton matrix.
    """
    from scipy.optimize import brentq
    factor = np.linalg.cholesky(metric)
    scaled = np.linalg.solve(factor, np.asarray(matrix).T).T  # J C^{-T}, R = C C^T
    u, singular, _ = np.linalg.svd(scaled, full_matrices=False)
    projection = u.T @ residual
    total = float(residual @ residual)
    outside = max(total - float(projection @ projection), 0.0)
    power = singular**2
    lowest = floor * float(np.mean(power)) if power.size and np.mean(power) > 0 else floor
    target = ratio**2 * total

    def excess(log_lam):
        lam = np.exp(log_lam)
        return outside + float(np.sum((lam / (power + lam))**2 * projection**2)) - target

    if checks.hanke_floor_attains_target(excess(np.log(lowest))):
        return lowest, False
    high = max(float(np.max(power)), lowest) * 10
    while checks.hanke_below_target(excess(np.log(high))):
        high *= 10
    return float(np.exp(brentq(excess, np.log(lowest), np.log(high), xtol=1e-13, rtol=1e-15))), True



def damping_matrix(H_GN, space, update, config, smoothing):
    """Marquardt diagonal floor, or the configured physical update metric."""
    if config.metric == "marquardt":
        return np.diag(np.maximum(np.diag(H_GN), config.scaling_floor))
    return update.metric(space, config.metric, smoothing)


def solve_proposal(g, H_GN, D, lambda_trial):
    """Return a_raw; the caller retains retry handling for singular systems."""
    return np.linalg.solve(H_GN + lambda_trial * D, -g)


def damping_floor(normal, metric, relative):
    factor = np.linalg.cholesky(metric)
    scaled = np.linalg.solve(factor, normal)
    scaled = np.linalg.solve(factor, scaled.T).T
    # Infinity norm bounds the curvature spectrum without an eigensolve.
    curvature = max(float(np.linalg.norm(scaled, ord=np.inf)), np.finfo(float).eps)
    return max(relative * curvature, np.finfo(float).eps)
