"""Local action predictions, using the complete trial Jacobian and physical metric.

This is an opt-in diagnostic, not an inverse optimizer or a convergence claim.
The caller owns the actual trial construction, data weighting and admissibility.
Unlike componentwise QR caps, one quadratic constraint bounds the whole step.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq


@dataclass(frozen=True)
class ActionPrediction:
    step: np.ndarray
    singular_values: np.ndarray
    predicted_decrease: float
    initial_loss: float
    linear_loss: float
    physical_norm: float
    radius: float
    constraint_active: bool
    numerical_rank: int

    def record(self):
        return dict(predicted_decrease=self.predicted_decrease,
                    decrease_fraction=self.predicted_decrease / self.initial_loss if self.initial_loss else 0.,
                    initial_loss=self.initial_loss, linear_loss=self.linear_loss,
                    physical_norm=self.physical_norm, radius=self.radius,
                    constraint_active=self.constraint_active, numerical_rank=self.numerical_rank)


def predict(jacobian, residual, metric, radius, *, rcond=1e-12):
    """Minimise .5 ||r + J p||² subject to p.T metric p <= radius².

    The metric must be positive definite on the supplied parameter space. Rank
    truncation applies in physical coordinates, not arbitrarily scaled parameter
    coordinates. Returned singular values are per unit physical displacement.
    Parameter changes J -> J B, metric -> B.T metric B preserve the problem.
    """
    J, r, G = (np.asarray(x, dtype=float) for x in (jacobian, residual, metric))
    if J.ndim != 2 or r.shape != (J.shape[0],) or G.shape != (J.shape[1], J.shape[1]) or not J.shape[1]:
        raise ValueError('Incompatible Jacobian, residual or metric dimensions.')
    if not all(np.all(np.isfinite(x)) for x in (J, r, G)):
        raise ValueError('Finite inputs are required.')
    if not np.isfinite(radius) or radius <= 0 or not 0 < rcond < 1:
        raise ValueError('Positive finite radius and 0 < rcond < 1 required.')
    if np.linalg.norm(G-G.T, ord=np.inf) > 1e-12*np.linalg.norm(G, ord=np.inf):
        raise ValueError('The physical metric must be symmetric.')
    C = np.linalg.cholesky(.5*(G+G.T))
    physical_J = np.linalg.solve(C, J.T).T  # J C^{-T}; p = C^{-T} x
    U, s, Vt = np.linalg.svd(physical_J * radius, full_matrices=False)
    keep = s > (rcond * s[0] if s.size else 0.)
    spectrum = s / radius
    s, q, Vt = s[keep], (U.T @ r)[keep], Vt[keep]
    active = False
    if not s.size:
        x = np.zeros(J.shape[1])
    else:
        # Scale the secular equation to avoid absolute root tolerances tied to
        # the physical units or the overall data normalization.
        scale = s[0]
        sn, qn = s / scale, q / scale

        def coefficients(lam):
            return -sn * qn / (sn * sn + lam)

        z = coefficients(0.)
        active = bool(np.linalg.norm(z) > 1.)
        if active:
            high = max(1., float(np.linalg.norm(sn * qn)))
            lam = brentq(lambda v: np.linalg.norm(coefficients(v)) - 1., 0., high,
                         xtol=np.finfo(float).tiny, rtol=1e-14)
            z = coefficients(lam)
        x = radius * (Vt.T @ z)
    p = np.linalg.solve(C.T, x)
    move = J @ p
    # Avoid cancellation when the attainable decrease is tiny.
    decrease = float(-r @ move - .5 * move @ move)
    initial, linear = .5 * float(r @ r), .5 * float((r + move) @ (r + move))
    return ActionPrediction(p, spectrum, decrease, initial, linear,
                            float(np.linalg.norm(C.T @ p)), float(radius), active, int(keep.sum()))


def descent_lower_bound(predicted_decrease, linear_residual_norm, remainder_bound):
    """Conditional bound from expanding .5||r + Jp + e||², ||e|| <= epsilon.

    Using a measured remainder yields an a-posteriori check, not a certificate
    for an unevaluated step. The caller must establish any prospective bound.
    """
    if not all(np.isfinite(v) for v in (predicted_decrease, linear_residual_norm, remainder_bound)):
        raise ValueError('Finite values required.')
    if linear_residual_norm < 0 or remainder_bound < 0:
        raise ValueError('Norms and remainder bounds must be nonnegative.')
    return float(predicted_decrease - linear_residual_norm * remainder_bound - .5 * remainder_bound**2)
