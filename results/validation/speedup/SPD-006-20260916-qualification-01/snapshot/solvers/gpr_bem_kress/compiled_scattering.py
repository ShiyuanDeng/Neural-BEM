"""Nodal Kress regular-to-outgoing maps and reduced multiple scattering.

Port of BIE-005's nodal elimination, with retained regular-wave Dirichlet
traces for reciprocal derivatives. No experimental solver imports. Geometry,
material, separation and angular-convergence policy belong to the caller.
All cylindrical normalizations use one fixed physical radius (0.1 m), so no
geometry-dependent normalization derivative enters the shape identity.
"""
from dataclasses import dataclass
import numpy as np
from scipy.linalg import block_diag
from scipy.special import gammaln
from .execution import Factorization, hankel1, jv
from .system import build_muller_system


class CompiledScatteringFailure(FloatingPointError):
    """An explicit numerical failure for which full Kress may be used."""


def checked_solve(matrix, rhs):
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(rhs)):
        raise CompiledScatteringFailure('nonfinite compiled system')
    try:
        value = Factorization(matrix).solve(rhs)
    except np.linalg.LinAlgError as exc:
        raise CompiledScatteringFailure('singular compiled system') from exc
    relative = float(np.linalg.norm(matrix @ value-rhs) /
                     max(np.linalg.norm(rhs), np.finfo(float).tiny))
    if not np.all(np.isfinite(value)) or not np.isfinite(relative) or relative > 1e-10:
        raise CompiledScatteringFailure('compiled linear residual exceeds 1e-10')
    return value, relative


def cylindrical(orders, delta, wave, *, regular=False, sign=1, derivatives=False):
    """Evaluate distinct cylindrical orders once, then gather repeated entries."""
    orders, delta = np.asarray(orders), np.asarray(delta)
    first, last = int(orders.min())-1, int(orders.max())+1
    ladder = np.arange(first, last+1)[:, None]
    flat = delta.reshape(-1)
    function = jv if regular else hankel1
    table = function(ladder, wave*np.abs(flat)[None, :]) * np.exp(sign*1j*ladder*np.angle(flat)[None, :])
    indices = np.arange(delta.size).reshape(delta.shape)
    value = table[orders-first, indices]
    if not derivatives:
        return value
    lower, upper = table[orders-first-1, indices], table[orders-first+1, indices]
    return value, wave/2*(lower-upper), sign*1j*wave/2*(lower+upper)


@dataclass(frozen=True)
class LocalScattering:
    modes: np.ndarray
    normalization: np.ndarray
    matrix: np.ndarray
    trace: np.ndarray
    relative_residual: float

    def truncated(self, order):
        selected = np.flatnonzero(abs(self.modes) <= order)
        return LocalScattering(self.modes[selected], self.normalization[selected],
            self.matrix[np.ix_(selected, selected)], self.trace[:, selected], self.relative_residual)


def compile_local(curve, center, ko, ki, *, order, assembly):
    """One self Kress factorization solves every regular-wave illumination."""
    modes = np.arange(-order, order+1)
    normalization = np.exp(abs(modes)*np.log(ko*.1/2)-gammaln(abs(modes)+1))
    system = build_muller_system(curve, ko, ki, config=assembly).system_matrix
    z = curve.points[:, 0]+1j*curve.points[:, 1]-center
    value, dx, dy = cylindrical(modes[None, :], z[:, None], ko, regular=True, derivatives=True)
    normal = dx*curve.normals[:, 0, None]+dy*curve.normals[:, 1, None]
    rhs = np.concatenate((value, normal))/normalization[None, :]
    state, residual = checked_solve(system, rhs)
    projection = np.concatenate(((normal*curve.arc_length_weights[:, None]).T,
                                  -(value*curve.arc_length_weights[:, None]).T), axis=1)
    projection = .25j*(-1.)**modes[:, None]*projection[::-1]/normalization[:, None]
    return LocalScattering(modes, normalization, projection @ state,
                           state[:curve.num_nodes], residual)


def reduced_paired_response(templates, centers, sources, receivers, strength, ko, ki, weights):
    """Full coupled paired prediction and reciprocal directional derivatives.

    Unit receiver illuminations and physical source illuminations share one
    reduced solve. The local traces reconstruct both illuminations; no adjoint
    conjugation appears in their bilinear shape product.
    """
    widths = [len(t.modes) for t in templates]
    stops = np.r_[0, np.cumsum(widths)]
    slices = [slice(a, b) for a, b in zip(stops[:-1], stops[1:])]
    scattering = block_diag(*[t.matrix for t in templates])
    translation = np.zeros_like(scattering)
    for i, (target, rs) in enumerate(zip(templates, slices)):
        for j, (source, cs) in enumerate(zip(templates, slices)):
            if i != j:
                translation[rs, cs] = cylindrical(source.modes[None, :]-target.modes[:, None],
                    centers[i]-centers[j], ko)*target.normalization[:, None]*source.normalization[None, :]
    points = np.vstack((sources, receivers))
    z = points[:, 0]+1j*points[:, 1]
    count = len(sources)
    strengths = np.r_[np.full(count, strength, complex), np.ones(len(receivers))]
    incident = np.concatenate([.25j*t.normalization[:, None]*strengths[None, :]
        *cylindrical(t.modes[:, None], z[None, :]-center, ko, sign=-1)
        for t, center in zip(templates, centers)])
    rz = receivers[:, 0]+1j*receivers[:, 1]
    receiver = np.concatenate([t.normalization[None, :]
        *cylindrical(t.modes[None, :], rz[:, None]-center, ko)
        for t, center in zip(templates, centers)], axis=1)
    matrix = np.eye(len(scattering))-scattering @ translation
    outgoing, residual = checked_solve(matrix, scattering @ incident)
    prediction = np.diag(receiver @ outgoing[:, :count])
    local_incident = incident+translation @ outgoing
    derivatives = np.zeros((len(weights[0]), count), complex)
    for template, sl, weight in zip(templates, slices, weights):
        trace = template.trace @ local_incident[sl]
        derivatives += (ki*ki-ko*ko)*(weight @ (trace[:, :count]*trace[:, count:]))
    if not np.all(np.isfinite(prediction)) or not np.all(np.isfinite(derivatives)):
        raise CompiledScatteringFailure('nonfinite compiled prediction or derivative')
    return prediction, derivatives, max(residual, *(t.relative_residual for t in templates))
