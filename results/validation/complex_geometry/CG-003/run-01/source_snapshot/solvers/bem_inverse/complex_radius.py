"""Opt-in complex-geometry instrument: exact transmission disks and scalar folds.

The complex scalar is a radius, not the x+iy encoding of a real planar curve.
Only real centers/frequencies are supported. No maintained fitting defaults
use this module. Derivatives are of the complete holomorphic objective.
"""
from collections import OrderedDict
from math import comb
from time import perf_counter

import numpy as np
from scipy.special import hankel1, jv

from .mie_localize import geometric_products


class ComplexDomainError(ValueError):
    """The declared analytic chart or numerical pole margin was exceeded."""


def coefficient_jets(k, contrast, radius, cutoff, degree=3):
    """Mie coefficients and true radius derivatives, shape (...,degree+1,modes).

    Bessel derivatives use the exact integer-order recurrence. Quotient jets
    include all denominator derivatives. Nonfinite modes are never masked.
    """
    q = np.asarray(radius, complex)
    if (not np.isfinite(q).all() or np.any(q.real <= .25)
            or np.any(q.real >= 2.5) or np.any(np.abs(q.imag) >= .5)):
        raise ComplexDomainError('Radius outside Re(q) in (.25,2.5), |Im(q)|<.5')
    if degree not in (0, 1, 2, 3) or k <= 0 or contrast <= 0 or cutoff < 1:
        raise ValueError('Positive real physics, positive cutoff, degree 0..3 required')
    ki = k*np.sqrt(contrast)
    pad = degree+1
    width = 2*cutoff+1
    orders = np.arange(-cutoff-pad, cutoff+pad+1)

    def derivatives(function, wave):
        raw = function(orders, wave*q[..., None])
        return [wave**m/2**m * sum(
            (-1)**ell*comb(m, ell)*raw[..., pad-m+2*ell:pad-m+2*ell+width]
            for ell in range(m+1)) for m in range(degree+2)]

    ji, je, he = derivatives(jv, ki), derivatives(jv, k), derivatives(hankel1, k)
    numerator, denominator = [], []
    for m in range(degree+1):
        numerator.append(sum(comb(m, ell)*(ji[ell+1]*je[m-ell]
                            -ji[ell]*je[m-ell+1]) for ell in range(m+1)))
        denominator.append(sum(comb(m, ell)*(ji[ell]*he[m-ell+1]
                              -ji[ell+1]*he[m-ell]) for ell in range(m+1)))
    relative_pole = np.min(np.abs(denominator[0])/
        np.maximum(np.abs(ji[0]*he[1])+np.abs(ji[1]*he[0]), np.finfo(float).tiny), axis=-1)
    if not np.isfinite(relative_pole).all() or np.any(relative_pole < 1e-10):
        raise ComplexDomainError('Transmission denominator cancellation/pole guard')
    quotient = []
    for m in range(degree+1):
        quotient.append((numerator[m]-sum(comb(m, ell)*denominator[ell]*quotient[m-ell]
                                         for ell in range(1, m+1)))/denominator[0])
    result = .25j*np.stack(quotient, axis=-2)
    if not np.isfinite(result).all():
        raise ComplexDomainError('Nonfinite transmission coefficient/derivative')
    return result, relative_pole


class DiskHomotopy:
    """Fitting instrument accepting only measured observations and a start.

    F(q,t) = A(q)-t B(q) is the mirror extension of the real data-loss gradient.
    All frequencies carry equal relative-squared-residual weight.
    """
    def __init__(self, observations, contrast, q0=1.3, center=0j, extra_cutoff=0, work_check=None):
        self.observations = tuple(observations)
        self.contrast, self.q0, self.center = contrast, q0, center
        self.work_check = work_check
        self.cutoffs, self.products, self.scales = [], [], []
        self.frequency_evaluations = self.jet_calls = self.cache_hits = self.failures = 0
        self._cache = OrderedDict()
        for obs in self.observations:
            if complex(obs.wavenumber).imag != 0:
                raise ValueError('CG-001 fixes all frequencies to the real axis')
            cut = int(np.ceil(obs.wavenumber*np.sqrt(max(contrast, 1))*2.5+24))+extra_cutoff
            scale = np.linalg.norm(obs.scattered)*np.sqrt(len(self.observations))
            acq = obs.acquisition
            if not acq.paired:
                raise ValueError('Only observed paired channels are supported')
            products = geometric_products(obs.wavenumber, [center], acq.sources,
                                          acq.receivers, np.arange(-cut, cut+1))[0]
            self.products.append(products*acq.strength/scale)
            self.cutoffs.append(cut)
            self.scales.append(scale)
        self.data = np.concatenate([o.scattered/s for o, s in zip(self.observations, self.scales)])
        self.g0 = self.jets(q0)[0][0]
        self.delta = self.data-self.g0

    def jets(self, radius):
        if self.work_check is not None:
            self.work_check()
        q = np.asarray(radius, complex)
        key = complex(q) if q.ndim == 0 else None
        if key is not None and key in self._cache:
            self.cache_hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self.jet_calls += q.size
        pieces, margins = [], []
        try:
            for obs, cut, products in zip(self.observations, self.cutoffs, self.products):
                self.frequency_evaluations += q.size
                coeff, margin = coefficient_jets(obs.wavenumber, self.contrast, q, cut)
                pieces.append(np.einsum('...jn,pn->...jp', coeff, products))
                margins.append(margin)
        except Exception:
            self.failures += 1
            raise
        answer = np.concatenate(pieces, axis=-1), np.min(margins, axis=0)
        if key is not None:
            self._cache[key] = answer
            if len(self._cache) > 512:
                self._cache.popitem(last=False)
        return answer

    def ab(self, radius):
        g, margin = self.jets(radius)
        if np.all(np.imag(radius) == 0):
            mirror, mirror_margin = np.conj(g), margin
        else:
            reflected, mirror_margin = self.jets(np.conj(radius))
            mirror = np.conj(reflected)
        r, rs = g[..., 0, :]-self.g0, mirror[..., 0, :]-self.g0.conj()
        dot = lambda x, y: np.sum(x*y, axis=-1)
        A = .5*(dot(mirror[..., 1, :], r)+dot(g[..., 1, :], rs))
        Ap = (.5*(dot(mirror[..., 2, :], r)+dot(g[..., 2, :], rs))
              +dot(mirror[..., 1, :], g[..., 1, :]))
        App = (.5*(dot(mirror[..., 3, :], r)+dot(g[..., 3, :], rs))
               +1.5*(dot(mirror[..., 2, :], g[..., 1, :])
                     +dot(mirror[..., 1, :], g[..., 2, :])))
        B = [.5*(dot(mirror[..., j, :], self.delta)
                 +dot(g[..., j, :], self.delta.conj())) for j in (1, 2, 3)]
        return np.stack((A, Ap, App), axis=-1), np.stack(B, axis=-1), np.minimum(margin, mirror_margin)

    def state(self, q, t):
        A, B, margin = self.ab(q)
        F, Fq, Fqq = A-t*B
        return dict(F=complex(F), Fq=complex(Fq), Fqq=complex(Fqq), Ft=complex(-B[0]),
                    scale=max(1., abs(A[0])+abs(t*B[0])), margin=float(margin))

    def real_loss(self, q, t=1.):
        if abs(complex(q).imag) > 1e-8 or abs(complex(t).imag) > 1e-8:
            raise ValueError('Ordinary physical loss is reported only at real geometry/data')
        r = self.jets(float(np.real(q)))[0][0]-self.g0-float(np.real(t))*self.delta
        return float(.5*np.vdot(r, r).real)

    def counters(self):
        return dict(frequency_evaluations=self.frequency_evaluations, jet_calls=self.jet_calls,
                    cache_hits=self.cache_hits, failed_jet_calls=self.failures)


def record_state(model, q, t):
    st = model.state(q, t)
    if not all(np.isfinite(st[key]) for key in ('F', 'Fq', 'Fqq', 'Ft', 'scale', 'margin')):
        raise ComplexDomainError('Nonfinite continuation state')
    return dict(q=complex(q), t=complex(t), **st)


def track(model, q, waypoints, *, max_step=.004, min_step=1e-8, max_attempts=20000):
    """Complex tangent prediction and full-Newton correction with branch guards.

    Waypoints specify a polygonal parameter path. Failed steps are retained;
    domain failures halve the step, never project geometry onto the real axis.
    """
    started = perf_counter()
    t, q = complex(waypoints[0]), complex(q)
    rows, rejected = [record_state(model, q, t)], []
    if abs(rows[0]['F']) > 1e-8*rows[0]['scale']:
        raise ValueError('Continuation must start at a stationary root')
    attempts = 0
    status = 'COMPLETED'
    for target in map(complex, waypoints[1:]):
        step_cap = max_step
        while abs(target-t) > 2e-14:
            attempts += 1
            if attempts > max_attempts:
                status = 'ATTEMPT_BUDGET'; break
            dt = target-t
            if abs(dt) > step_cap:
                dt *= step_cap/abs(dt)
            try:
                current = model.state(q, t)
                if abs(current['Fq']) < 1e-14:
                    raise ComplexDomainError('Singular natural-parameter tangent')
                prediction = q-current['Ft']/current['Fq']*dt
                predicted_step = abs(prediction-q)
                if predicted_step > .04:
                    raise ComplexDomainError('Predictor exceeds chart step bound')
                trial = prediction
                for iteration in range(10):
                    st = model.state(trial, t+dt)
                    if abs(st['F']) <= 1e-11*st['scale']:
                        break
                    if abs(st['Fq']) < 1e-14:
                        raise ComplexDomainError('Singular corrector Jacobian')
                    trial -= st['F']/st['Fq']
                else:
                    raise ComplexDomainError('Newton did not converge in ten iterations')
                if abs(trial-prediction) > max(1e-4, .5*predicted_step):
                    raise ComplexDomainError('Corrector left predictor neighborhood')
                q, t = trial, t+dt
                rows.append(record_state(model, q, t))
                step_cap = min(max_step, step_cap*1.5)
            except (ComplexDomainError, FloatingPointError, ZeroDivisionError) as exc:
                rejected.append(dict(q=q, t=t, dt=dt, reason=str(exc)))
                step_cap = abs(dt)/2
                if step_cap < min_step:
                    status = 'MINIMUM_STEP'; break
        if status != 'COMPLETED':
            break
    return dict(status=status, states=rows, rejected=rejected, attempts=attempts,
                seconds=perf_counter()-started)


def pseudo_arclength(model, q, t, *, direction=1., steps=160, ds=.002):
    """Real augmented predictor-corrector; ds is in dimensionless (q,t) space."""
    started = perf_counter()
    x = np.array([q, t], float)
    tangent = None
    rows, rejected = [record_state(model, *x)], []
    if abs(rows[0]['F']) > 1e-8*rows[0]['scale']:
        raise ValueError('Pseudo-arclength must start at a stationary root')
    status = 'COMPLETED'
    for _ in range(steps):
        st = model.state(*x)
        new = np.array([-st['Ft'].real, st['Fq'].real])
        size = np.linalg.norm(new)
        if not np.isfinite(size) or size < 1e-14:
            status = 'SINGULAR_AUGMENTED_TANGENT'; break
        new /= size
        if (tangent is None and new[0]*direction < 0) or (tangent is not None and new@tangent < 0):
            new = -new
        tangent = new
        step = ds
        while True:
            predicted = x+step*tangent
            trial = predicted.copy()
            try:
                for iteration in range(10):
                    st = model.state(*trial)
                    residual = np.array([st['F'].real, (trial-predicted)@tangent])
                    if abs(residual[0]) <= 1e-11*st['scale'] and abs(residual[1]) <= 1e-11:
                        break
                    jac = np.array([[st['Fq'].real, st['Ft'].real], tangent])
                    trial -= np.linalg.solve(jac, residual)
                else:
                    raise ComplexDomainError('Pseudo-arclength Newton failed')
                if np.linalg.norm(trial-predicted) > step:
                    raise ComplexDomainError('Pseudo-arclength correction jumped branch')
                x = trial
                rows.append(record_state(model, *x))
                break
            except (ComplexDomainError, np.linalg.LinAlgError) as exc:
                rejected.append(dict(q=complex(x[0]), t=complex(x[1]), ds=step, reason=str(exc)))
                step /= 2
                if step < 1e-8:
                    status = 'MINIMUM_STEP'; break
        if status != 'COMPLETED':
            break
    return dict(status=status, states=rows, rejected=rejected, attempts=len(rows)-1+len(rejected),
                seconds=perf_counter()-started)


class Cubic:
    """Analytic tracker control, never an inverse-recovery result."""
    def state(self, q, t):
        return dict(F=q**3-3*q-t, Fq=3*q*q-3, Fqq=6*q, Ft=-1., scale=1., margin=1.)


def circle_path(center, radius, angle, turns=1., orientation=1., points=256):
    return center+radius*np.exp(1j*(angle+orientation*np.linspace(0, 2*np.pi*turns, points+1)))
