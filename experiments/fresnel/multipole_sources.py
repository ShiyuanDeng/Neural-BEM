"""Outgoing 2D Helmholtz source multipoles, with exact spatial derivatives.

This isolated incident-only model leaves the production solver unchanged.
The source singularity is outside the target region. A rotated coefficient
vector models the one physical antenna while the target is rotated.
"""
from dataclasses import dataclass

import numpy as np
from scipy.special import hankel1


def multipole_basis(points, source, wavenumber, order, *, boresight=None):
    """Return value, Cartesian gradient and Hessian bases (P,2M+1,...).

    F_m = (i/4) H_m^(1)(k |x-s|) exp[i m(arg(x-s)-boresight)].
    Hankel recurrences give exact derivatives, without finite differences.
    """
    points, source = np.asarray(points, float), np.asarray(source, float)
    if points.ndim != 2 or points.shape[1] != 2 or source.shape != (2,):
        raise ValueError('Expected points (N,2) and source (2,).')
    if not np.isfinite(points).all() or not np.isfinite(source).all():
        raise ValueError('Coordinates must be finite.')
    if int(order) != order or order < 0 or not np.isfinite(wavenumber) or wavenumber <= 0:
        raise ValueError('Nonnegative integer order and positive finite real wavenumber required.')
    order = int(order)
    displacement = points-source
    radius = np.linalg.norm(displacement, axis=1)
    if np.any(radius == 0):
        raise ValueError('The outgoing source field is singular at its source.')
    if boresight is None:
        if np.linalg.norm(source) == 0:
            raise ValueError('Specify boresight for a source at the origin.')
        boresight = np.arctan2(-source[1], -source[0])
    angle = np.arctan2(displacement[:, 1], displacement[:, 0])
    modes = np.arange(-order-2, order+3)
    f = .25j*hankel1(modes[None], wavenumber*radius[:, None])*np.exp(1j*angle[:, None]*modes)
    lower2, lower, center, upper, upper2 = (f[:, i:i+2*order+1] for i in range(5))
    phase = np.exp(-1j*np.arange(-order, order+1)*boresight)[None]
    value = center*phase
    gradient = np.stack((lower-upper, 1j*(lower+upper)), axis=-1)*(wavenumber/2)*phase[..., None]
    hessian = np.empty((*value.shape, 2, 2), complex)
    hessian[..., 0, 0] = lower2-2*center+upper2
    hessian[..., 1, 1] = -lower2-2*center-upper2
    hessian[..., 0, 1] = hessian[..., 1, 0] = 1j*(lower2-upper2)
    hessian *= (wavenumber**2/4)*phase[..., None, None]
    return value, gradient, hessian


@dataclass(frozen=True)
class MultipoleFit:
    coefficients: np.ndarray
    singular_values: np.ndarray
    rank: int
    scaled_condition: float
    relative_residual: float
    inverse_map: np.ndarray
    rcond: float


def fit_multipoles(matrix, incident, *, rcond=1e-8):
    """Column-scaled truncated SVD; no target or scattered data accepted.

    inverse_map maps complex incident samples directly to physical multipole
    coefficients and is retained for deterministic noise-amplification audits.
    """
    matrix, incident = np.asarray(matrix, complex), np.asarray(incident, complex)
    if matrix.ndim != 2 or incident.shape != (len(matrix),) or not 0 < rcond < 1:
        raise ValueError('Expected a design matrix and one incident sample per row.')
    if not np.isfinite(matrix).all() or not np.isfinite(incident).all():
        raise ValueError('Finite design and incident samples required.')
    scales = np.linalg.norm(matrix, axis=0)
    if np.any(scales == 0) or np.linalg.norm(incident) == 0:
        raise ValueError('Nonzero basis columns and incident norm required.')
    u, singular, vh = np.linalg.svd(matrix/scales, full_matrices=False)
    keep = singular > rcond*singular[0]
    inverse = ((vh[keep].conj().T/singular[keep])@u[:, keep].conj().T)/scales[:, None]
    coefficients = inverse@incident
    return MultipoleFit(coefficients, singular, int(keep.sum()), float(singular[0]/singular[-1]),
        float(np.linalg.norm(matrix@coefficients-incident)/np.linalg.norm(incident)), inverse, rcond)


def evaluate_fit(points, source, wavenumber, fit, *, boresight=None):
    value, gradient, hessian = multipole_basis(points, source, wavenumber,
        (len(fit.coefficients)-1)//2, boresight=boresight)
    return (value@fit.coefficients,
            np.einsum('pmd,m->pd', gradient, fit.coefficients),
            np.einsum('pmde,m->pde', hessian, fit.coefficients))
