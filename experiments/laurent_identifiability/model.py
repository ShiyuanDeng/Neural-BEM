"""A continuous Gaussian log-gain prior, shared by the Fisher analysis and the inverse.

The neighbour study treated antenna calibration as either exactly known or
completely free. Those are the two endpoints of one family: a Gaussian prior on
the log-gain coordinates whose scale is `tau` times the study's own truth gain
scale. `tau = 0` is exact calibration, `tau -> inf` is the free-gain arm.

Nothing here edits the neighbour, calibration or solver packages; they are
imported read-only so their recorded source hashes keep validating.
"""
from time import perf_counter

import numpy as np
from scipy.optimize import brentq, least_squares

from experiments.laurent_calibration.design import project_out
from experiments.laurent_calibration.model import TARGET, incidence, realify
from experiments.laurent_neighbour.model import Evaluator, JointObjective

# The neighbour study's truth gain scale: log-amplitude nepers, phase radians.
GAIN_SD = (.15, .25)
# Readings of tau in instrument units, for one standard deviation.
DECIBELS_PER_TAU = 20/np.log(10)*GAIN_SD[0]
DEGREES_PER_TAU = np.rad2deg(GAIN_SD[1])


def gain_scale(tau):
    """Prior standard deviation of each log-amplitude and phase coordinate."""
    return tau*GAIN_SD[0], tau*GAIN_SD[1]


def design_blocks(y, jac, mask, sigma):
    """Noise-whitened real physical and log-gain Jacobian blocks, stacked over frequency.

    Gain coordinates are ordered exactly as the joint inverse orders them:
    per frequency, `k` log-amplitudes then `k` phases, with transmitter 0 the
    reference. The columns are the derivatives of `exp(B g) * y`.
    """
    b = incidence(np.argwhere(mask), len(mask))
    k, nf = b.shape[1], len(y)
    physical, gains = [], []
    for f in range(nf):
        block = y[f][mask, None]*b/sigma[f]
        wide = np.zeros((len(block), 2*k*nf), complex)
        wide[:, 2*k*f:2*k*f+k] = block
        wide[:, 2*k*f+k:2*k*(f+1)] = 1j*block
        physical.append(realify(jac[f][mask]/sigma[f]))
        gains.append(realify(wide))
    return np.concatenate(physical), np.concatenate(gains), k, nf


def prior_precision(k, nf, tau):
    """Diagonal prior precision on the gain coordinates, in their own ordering."""
    sa, sb = gain_scale(tau)
    return np.tile(np.r_[np.full(k, sa**-2), np.full(k, sb**-2)], nf)


def marginal_gram(y, jac, mask, sigma, tau, neighbour_unknown=True):
    """Target-harmonic Fisher information after marginalising gains and flat nuisance.

    The flat nuisance (position, radius, material, and every neighbour
    coordinate when it is unknown) keeps the neighbour study's rank-truncated
    projection. Gains are eliminated by a Schur complement carrying the prior,
    which is the same operation with a finite penalty. Eliminating disjoint
    blocks commutes, so the two steps may be taken in either order.
    """
    physical, gains, k, nf = design_blocks(y, jac, mask, sigma)
    flat = [0, 1, 2, 7]+(list(range(8, jac.shape[-1])) if neighbour_unknown else [])
    reduced, rank = project_out(np.c_[physical[:, TARGET], gains], physical[:, flat])
    target, gains = reduced[:, :len(TARGET)], reduced[:, len(TARGET):]
    if tau == 0.:
        gram = target.T@target
    elif np.isinf(tau):
        # The free-gain endpoint: an unpenalised projection, as in the study.
        projected, _ = project_out(target, gains)
        gram = projected.T@projected
    else:
        cross = gains.T@target
        normal = gains.T@gains+np.diag(prior_precision(k, nf, tau))
        gram = target.T@target-cross.T@np.linalg.solve(normal, cross)
    return gram, rank


def radial_rms_crlb_mm(gram):
    """Same target-harmonic summary the neighbour study reports."""
    eig = np.linalg.eigvalsh(gram)
    if eig[0] <= 0:
        raise ValueError("Shape information is not positive definite at this fixture")
    return float(np.sqrt(2*np.trace(np.linalg.inv(gram))))


def curve(y, jac, mask, sigma, taus, neighbour_unknown=True):
    return [radial_rms_crlb_mm(marginal_gram(y, jac, mask, sigma, t, neighbour_unknown)[0])
            for t in taus]


def crossover_tau(bound, low=1e-4, high=1e3):
    """Smallest calibration scale at which coupling stops paying for itself.

    `bound(tau)` returns (coupled_crlb, additive_crlb); the crossover solves
    coupled == additive. Returns None when the sign does not change on the
    bracket, which is itself a reportable outcome.
    """
    def excess(exponent):
        coupled, additive = bound(10.**exponent)
        return np.log(additive/coupled)
    lo, hi = np.log10(low), np.log10(high)
    a, b = excess(lo), excess(hi)
    if not np.isfinite(a) or not np.isfinite(b) or a*b > 0:
        return None
    return float(10.**brentq(excess, lo, hi, xtol=1e-6, rtol=1e-10))


class CalibratedObjective(JointObjective):
    """The neighbour study's joint inverse with a finite, fixed or absent gain prior.

    `gain_prior=None` reproduces the study exactly (free gains, no penalty).
    `gain_prior=0.` fixes every gain at unity and removes the parameters.
    `gain_prior=tau>0` penalises the gain coordinates by their prior standard
    deviation, which is maximum-a-posteriori estimation for the same model that
    generated the data.
    """
    def __init__(self, evaluator, mask, observed, sigma, physical_initial,
                 neighbour_known=False, gain_prior=None):
        super().__init__(evaluator, mask, observed, sigma, physical_initial, neighbour_known)
        self.gain_prior = gain_prior
        self.free_gains = gain_prior is None or gain_prior > 0.
        self.gain_count = self.nf*2*self.k if self.free_gains else 0
        self.weights = (prior_precision(self.k, self.nf, gain_prior)**.5
                        if self.free_gains and gain_prior is not None else None)

    def predict(self, x):
        physical = self.physical(x)
        gains = (x[self.p:].reshape(self.nf, 2, self.k) if self.free_gains
                 else np.zeros((self.nf, 2, self.k)))
        mult = np.exp((gains[:, 0]+1j*gains[:, 1]) @ self.b.T)
        return mult*self.evaluator.forward(physical)[:, self.mask], mult, physical

    def residual(self, x):
        y, _, _ = self.predict(x)
        data = realify(((y-self.observed)/self.sigma).ravel())
        if self.weights is None:
            return data
        return np.r_[data, self.weights*x[self.p:]]

    def jacobian(self, x):
        y, mult, physical = self.predict(x)
        j = self.evaluator.jacobian(physical)[:, self.mask][:, :, self.active]
        j = (j*mult[..., None]/self.sigma[..., None]).reshape(-1, self.p)
        if not self.free_gains:
            return realify(j)
        n = np.zeros((y.size, self.gain_count), complex)
        e = y.shape[1]
        for f in range(self.nf):
            block = y[f, :, None]*self.b/self.sigma[f]
            n[f*e:(f+1)*e, f*2*self.k:(f+1)*2*self.k] = np.c_[block, 1j*block]
        data = realify(np.c_[j, n])
        if self.weights is None:
            return data
        penalty = np.c_[np.zeros((self.gain_count, self.p)), np.diag(self.weights)]
        return np.r_[data, penalty]


def fit(bodies, mask, observed, sigma, initial, interactions=True, neighbour_known=False,
        gain_prior=None, max_nfev=180):
    """Same optimiser, bounds and tolerances as the neighbour study's `fit`."""
    tick = perf_counter()
    ev = Evaluator(bodies, interactions=interactions)
    objective = CalibratedObjective(ev, mask, observed, sigma, initial, neighbour_known, gain_prior)
    ng = objective.gain_count
    start = np.r_[np.array(initial)[objective.active], np.zeros(ng)]
    lo, hi = zip(*(b.chart.bounds() for b in bodies))
    lo, hi = np.concatenate(lo)[objective.active], np.concatenate(hi)[objective.active]
    result = least_squares(objective.residual, start, jac=objective.jacobian,
        bounds=(np.r_[lo, np.full(ng, -3.)], np.r_[hi, np.full(ng, 3.)]), x_scale="jac",
        ftol=1e-9, xtol=1e-9, gtol=1e-7, max_nfev=max_nfev)
    gains = (result.x[objective.p:] if objective.free_gains else np.zeros(objective.nf*2*objective.k))
    return dict(parameters=objective.physical(result.x).tolist(), gains=np.asarray(gains).tolist(),
                success=bool(result.success), nfev=result.nfev, njev=result.njev,
                cost=float(result.cost), optimality=float(result.optimality),
                seconds=perf_counter()-tick, free_gains=objective.free_gains,
                active_bounds=np.flatnonzero(result.active_mask).tolist(), message=result.message,
                active_physical_count=objective.p)
