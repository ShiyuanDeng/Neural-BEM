"""NG-001 isolated centred geometry engine without curve quadrature.

Finite Laurent products use padded linear convolution. Nonlinear polynomial
proposals are cropped; complete residuals include the discarded product modes.
Forward tangents differentiate the actual finite polynomial algorithm. Range
cells bound whole intervals, rather than accepting a sampled minimum.

Construction error receipts use float64 arithmetic, not directed intervals.
The independent admissibility verifier lives in ``interval_geometry``.
No defaults, physics, benchmark inputs or saved results are imported here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np
from scipy.signal import fftconvolve


class CoefficientUnresolved(ValueError):
    def __init__(self, reason, receipt):
        self.reason, self.receipt = reason, receipt
        super().__init__(f'{reason}: {receipt}')


def crop(a, band):
    old = len(a)//2
    if old >= band:
        return a[old-band:old+band+1].copy()
    return np.pad(a, [(band-old, band-old)]+[(0, 0)]*(a.ndim-1))


def product(a, b, band=None):
    if a.ndim < b.ndim:
        a = a[:, None]
    if b.ndim < a.ndim:
        b = b[:, None]
    out = fftconvolve(a, b, axes=0)
    return out if band is None else crop(out, band)


def conjugate(a):
    return a[::-1].conj()


def real(a):
    return (a+conjugate(a))/2


def derivative(a, order=1):
    k = np.arange(-(len(a)//2), len(a)//2+1)
    return a*(1j*k.reshape((-1,)+(1,)*(a.ndim-1)))**order


def norm(a):
    return float(np.sum(np.abs(a)))


def nu(a, order=1):
    k = np.arange(-(len(a)//2), len(a)//2+1)
    return float(np.sum(np.abs(a)*np.abs(k)**order))


def constant(value, band):
    a = np.zeros(2*band+1, complex)
    a[band] = value
    return a


def shift(a, order, band):
    full = np.zeros((len(a)+2*abs(order),)+a.shape[1:], complex)
    start = abs(order)+order
    full[start:start+len(a)] = a
    return crop(full, band)


def range_enclosure(a, *, positive=False, max_cells=2048):
    """Float coefficient Taylor enclosures; full cells, no point-only verdict.

    This construction proposer has a heuristic arithmetic guard. It must not
    be used as an interval-verified admissibility certificate.
    """
    a = real(a)
    k = np.arange(-(len(a)//2), len(a)//2+1)
    mean = float(a[len(a)//2].real)
    radius = norm(a)-abs(a[len(a)//2])
    guard = 128*np.finfo(float).eps*max(1., norm(a))
    lo, hi = mean-radius-guard, mean+radius+guard
    if lo > 0 or not positive:
        return lo, hi, dict(cells=0, method='coefficient triangle', arithmetic_verified=False)
    second = nu(a, 2)
    cells = 16
    while cells <= max_cells:
        # Centres are anchors of whole-interval Taylor proofs, not quadrature.
        centres = (np.arange(cells)+.5)*(2*np.pi/cells)
        phase = np.exp(1j*centres[:, None]*k)
        value = (phase@a).real
        first = np.abs((phase@(1j*k*a)).real)
        h = np.pi/cells
        radii = first*h+.5*second*h*h+guard
        lo, hi = float(np.min(value-radii)), float(np.max(value+radii))
        if lo > 0:
            return lo, hi, dict(cells=cells, method='coefficient Taylor cell enclosure',
                                arithmetic_verified=False)
        cells *= 2
    raise CoefficientUnresolved('positive_range_budget', dict(lower=lo, upper=hi, cells=cells//2))


@dataclass
class Speed:
    q: np.ndarray
    u: np.ndarray
    dq: np.ndarray | None
    eta: np.ndarray
    deta: np.ndarray | None
    mean: float
    dmean: np.ndarray | None
    receipt: dict


def _binomial_speed(p, band, dp=None, *, tolerance=1e-10, max_degree=512):
    """Finite binomial polynomials for sqrt(S), inverse sqrt(S), and tangents."""
    first = derivative(p)
    S = real(product(first, conjugate(first)))
    dS = None if dp is None else 2*real(product(derivative(dp), conjugate(first)))
    lower, upper, ranges = range_enclosure(S, positive=True)
    c = float(S[len(S)//2].real)
    ratio = max(abs(lower/c-1), abs(upper/c-1))
    if not 0 <= ratio < 1:
        raise CoefficientUnresolved('binomial_interval', dict(lower=lower, upper=upper, centre=c, ratio=ratio))
    degree = 8
    while ratio**(degree+1)/(1-ratio) > 1e-13:
        degree += 1
        if degree > max_degree:
            raise CoefficientUnresolved('scalar_degree_budget', dict(ratio=ratio, degree=degree, limit=max_degree))
    x = crop(S/c, band)
    x[band] -= 1
    dc = None if dp is None else dS[len(dS)//2].real
    dx = None if dp is None else crop(dS/c-S[:, None]*(dc/c**2), band)
    power = constant(1., band)
    dpower = None if dp is None else np.zeros_like(dp)
    q, u = power.copy(), power.copy()
    dq = None if dp is None else dpower.copy()
    du = None if dp is None else dpower.copy()
    aq = au = 1.
    for n in range(1, degree+1):
        if dp is not None:
            dpower = product(dpower, x, band)+product(power, dx, band)
        power = product(power, x, band)
        aq *= (.5-n+1)/n
        au *= (-.5-n+1)/n
        q += aq*power
        u += au*power
        if dp is not None:
            dq += aq*dpower
            du += au*dpower
    q, u = real(q*np.sqrt(c)), real(u/np.sqrt(c))
    if dp is not None:
        dq = real(dq*np.sqrt(c)+q[:, None]*(.5*dc/c))
        du = real(du/np.sqrt(c)-u[:, None]*(.5*dc/c))
    sqrt_residual = product(q, q)-crop(S, 2*band)
    inverse_residual = -product(S, product(u, u))
    inverse_residual[len(inverse_residual)//2] += 1
    rs, ru = norm(sqrt_residual), norm(inverse_residual)
    mq, _, qrange = range_enclosure(q, positive=True)
    eps_speed = rs/(mq+np.sqrt(lower))
    if rs/max(c, 1e-30) > tolerance or ru > tolerance:
        raise CoefficientUnresolved('full_speed_residual', dict(sqrt_relative=rs/c, inverse=ru,
                                                               band=band, degree=degree))
    mean = float(q[band].real)
    k = np.arange(-band, band+1)
    eta = np.zeros_like(q)
    nz = k != 0
    eta[nz] = q[nz]/(1j*k[nz]*mean)
    eta[band] = -sum(eta[nz])
    eta = real(eta)
    dmean = None if dp is None else dq[band].real
    deta = None
    if dp is not None:
        deta = np.zeros_like(dp)
        deta[nz] = (dq[nz]/mean-q[nz, None]*dmean/mean**2)/(1j*k[nz, None])
        deta[band] = -np.sum(deta[nz], axis=0)
        deta = real(deta)
    eps_alpha = 2*np.pi*eps_speed/max(mean-eps_speed, 1e-30)*(1+norm(q)/mean)
    return Speed(q, u, dq, eta, deta, mean, dmean,
        dict(scalar_degree=degree, sqrt_residual_relative=rs/c, inverse_residual=ru,
             speed_error_bound=eps_speed, alpha_error_bound=eps_alpha,
             ranges=ranges, q_range=qrange, speed_interval=[np.sqrt(lower), np.sqrt(upper)],
             arithmetic_verified=False))


def _newton_speed(p, band, dp=None, *, tolerance=1e-10, max_iterations=64):
    """A fixed finite inverse-root iteration, checked with full residuals.

    The integer scaling/count branches are locally fixed for the tangent.
    Inner squares are full products; only v, u and q are cropped.
    """
    first=derivative(p)
    S=real(product(first,conjugate(first)))
    dS=None if dp is None else 2*real(product(derivative(dp),conjugate(first)))
    lower,upper,ranges=range_enclosure(S,positive=True)
    mean_S=float(S[len(S)//2].real)
    gamma=2.**max(1,math.ceil(math.log2(upper/mean_S))+1)
    c=gamma*mean_S
    scalar_error=1-lower/c
    iterations=0
    while scalar_error>1e-14 or iterations<8:
        scalar_error=scalar_error**2*(3+scalar_error)/4
        iterations+=1
        if iterations>max_iterations:
            raise CoefficientUnresolved('inverse_root_iteration_budget',dict(iterations=iterations,limit=max_iterations))
    u=constant(1/np.sqrt(c),band)
    dc=None if dp is None else gamma*dS[len(dS)//2].real
    du=None if dp is None else np.zeros_like(dp)
    if du is not None:
        du[band]=-.5*dc/c**1.5
    for _ in range(iterations):
        square=product(u,u)
        v=product(S,square,band)
        g=constant(3.,band)-v
        if du is not None:
            dv=product(dS,square,band)+2*product(S,product(u,du),band)
            du=real((product(du,g,band)-product(u,dv,band))/2)
        u=real(product(u,g,band)/2)
    q=real(product(S,u,band))
    dq=None if dp is None else real(product(dS,u,band)+product(S,du,band))
    sqrt_residual=product(q,q)-crop(S,2*band)
    inverse_residual=-product(S,product(u,u))
    inverse_residual[len(inverse_residual)//2]+=1
    rs,ru=norm(sqrt_residual),norm(inverse_residual)
    if not np.isfinite([rs,ru]).all() or rs/mean_S>tolerance or ru>tolerance:
        raise CoefficientUnresolved('full_speed_residual',dict(sqrt_relative=rs/mean_S,
            inverse=ru,band=band,iterations=iterations,method='newton'))
    # With S>0 and residual <1, a continuous real u has constant sign.
    # Its positive mean selects the positive branch without point tests.
    if not u[band].real>0:
        raise CoefficientUnresolved('inverse_root_branch',dict(mean=float(u[band].real)))
    mq,_,qrange=range_enclosure(q,positive=True)
    eps_speed=rs/(mq+np.sqrt(lower))
    mean=float(q[band].real)
    k=np.arange(-band,band+1)
    nz=k!=0
    eta=np.zeros_like(q)
    eta[nz]=q[nz]/(1j*k[nz]*mean)
    eta[band]=-sum(eta[nz])
    eta=real(eta)
    dmean=None if dp is None else dq[band].real
    deta=None
    if dp is not None:
        deta=np.zeros_like(dp)
        deta[nz]=(dq[nz]/mean-q[nz,None]*dmean/mean**2)/(1j*k[nz,None])
        deta[band]=-np.sum(deta[nz],axis=0)
        deta=real(deta)
    eps_alpha=2*np.pi*eps_speed/max(mean-eps_speed,1e-30)*(1+norm(q)/mean)
    return Speed(q,u,dq,eta,deta,mean,dmean,dict(scalar_method='newton',scalar_degree=None,
        inverse_root_iterations=iterations,scale_gamma=gamma,sqrt_residual_relative=rs/mean_S,
        inverse_residual=ru,speed_error_bound=eps_speed,alpha_error_bound=eps_alpha,
        ranges=ranges,q_range=qrange,speed_interval=[np.sqrt(lower),np.sqrt(upper)],arithmetic_verified=False))


def speed(p,band,dp=None,*,method='binomial',**kwargs):
    if method=='binomial':
        return _binomial_speed(p,band,dp,**kwargs)
    if method=='newton':
        return _newton_speed(p,band,dp,**kwargs)
    raise ValueError(f'Unknown speed method {method!r}')


def phase_seed(s, band):
    """Cropped Taylor composition of exp(i eta), with actual forward tangent."""
    x = 1j*s.eta.copy()
    anchor = x[band]
    x[band] = 0
    dx = None if s.deta is None else 1j*s.deta.copy()
    danchor = None if dx is None else dx[band].copy()
    if dx is not None:
        dx[band] = 0
    A = norm(x)
    degree = 8
    while (degree+1)*np.log(max(A, 1e-300))-math.lgamma(degree+2) > np.log(1e-13):
        degree += 1
        if degree > 512:
            raise CoefficientUnresolved('phase_degree_budget', dict(amplitude=A, degree=degree))
    power = constant(1., band)
    out = power.copy()
    dout = None if dx is None else np.zeros_like(dx)
    dpower = None if dx is None else np.zeros_like(dx)
    for n in range(1, degree+1):
        if dx is not None:
            dpower = (product(dpower, x, band)+product(power, dx, band))/n
        power = product(power, x, band)/n
        out += power
        if dx is not None:
            dout += dpower
    if dx is not None:
        dout = np.exp(anchor)*(dout+out[:, None]*danchor)
    out *= np.exp(anchor)
    return shift(out, 1, band), None if dx is None else shift(dout, 1, band), degree


def projection(p, output_band, band, dp=None, *, phase_tolerance=1e-8, keep_phases=False, speed_method='binomial'):
    started = time.perf_counter()
    p = crop(p, band)
    dp = None if dp is None else crop(dp, band)
    s = speed(p, band, dp, method=speed_method)
    seed, dseed, degree = phase_seed(s, band)
    P = constant(1., band)
    dP = None if dp is None else np.zeros_like(dp)
    phases = [P.copy()] if keep_phases else None
    out = np.zeros(2*output_band+1, complex)
    dout = None if dp is None else np.zeros((len(out), dp.shape[1]), complex)
    out[output_band] = np.dot(p, s.q[::-1])/s.mean
    if dp is not None:
        dout[output_band] = (dp.T@s.q[::-1]+p@s.dq[::-1])/s.mean-out[output_band]*s.dmean/s.mean
    first = derivative(p)
    dfirst = None if dp is None else derivative(dp)
    alpha_prime = s.q/s.mean
    largest, errors = 0., []
    for m in range(1, output_band+1):
        if dp is not None:
            dP = product(dP, seed, band)+product(P, dseed, band)
        P = product(P, seed, band)
        residual = crop(derivative(P), 2*band)-1j*m*product(alpha_prime, P)
        error = abs(sum(P)-1)+2*np.pi*norm(residual)
        largest = max(largest, error)
        errors.append(error+m*s.receipt['alpha_error_bound'])
        if not np.isfinite(error) or error > phase_tolerance:
            raise CoefficientUnresolved('full_phase_residual', dict(mode=m, error=error, band=band,
                                                                  tolerance=phase_tolerance))
        negative = conjugate(P)
        out[output_band+m] = np.dot(first, negative[::-1])/(1j*m)
        out[output_band-m] = np.dot(first, P[::-1])/(-1j*m)
        if dp is not None:
            dout[output_band+m] = (dfirst.T@negative[::-1]+first@conjugate(dP)[::-1])/(1j*m)
            dout[output_band-m] = (dfirst.T@P[::-1]+first@dP[::-1])/(-1j*m)
        if keep_phases:
            phases.append(P.copy())
    return out, dout, s, phases, dict(**s.receipt, phase_degree=degree,
        maximum_phase_residual_bound=largest, maximum_phase_total_bound=max(errors, default=0.),
        coefficient_error_bound_nonzero=2*nu(p)*sum(e/m for m,e in enumerate(errors, 1)),
        seconds=time.perf_counter()-started, working_band=band, curve_quadrature=False)


class CoefficientGeometry:
    """Reusable base and finite update; no solver registration or sampled methods."""
    def __init__(self, curve, update_modes, *, band=None, length_unit_m=.05, speed_method='binomial'):
        self.curve, self.M = curve, update_modes
        self.K = curve.band
        self.B = band or max(256, 4*self.K)
        if self.B < max(self.K, self.M):
            raise ValueError('Working band must cover storage and update bands.')
        self.unit = length_unit_m
        self.speed_method=speed_method
        z = crop(curve.coefficients, self.B)
        self.base, _, self.speed, phases, self.receipt = projection(z, max(self.K, self.M), self.B,
                                                                  keep_phases=True,speed_method=speed_method)
        self.base = crop(self.base, self.K)
        self.phases = np.array(phases[:self.M+1])
        self.normal = product(-1j*derivative(z), self.speed.u, self.B)

    def displacement(self, a):
        a = np.asarray(a, float)
        if a.shape != (2*self.M+1,) or not np.isfinite(a).all():
            raise ValueError('Expected finite real update coefficients.')
        h = constant(a[0], self.B)
        for m in range(1, self.M+1):
            phase = self.phases[m]
            h += a[m]*real(phase)+a[self.M+m]*(phase-conjugate(phase))/(2j)
        return product(h, self.normal, self.B)/self.unit

    def trial(self, a):
        if not np.any(a):
            return self.curve.coefficients.copy(), crop(self.curve.coefficients, self.B), dict(identity=True)
        moved = crop(self.curve.coefficients, self.B)+self.displacement(a)
        projected, _, _, _, receipt = projection(moved, self.K, self.B,speed_method=self.speed_method)
        return self.curve.coefficients+projected-self.base, moved, receipt

    def tangent(self, directions):
        directions = np.atleast_2d(directions)
        dp = np.stack([self.displacement(a) for a in directions], axis=1)
        _, dot, _, _, receipt = projection(crop(self.curve.coefficients, self.B), self.K, self.B, dp,
                                           speed_method=self.speed_method)
        return dot, receipt
