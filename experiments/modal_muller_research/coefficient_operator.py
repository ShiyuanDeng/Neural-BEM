"""Node-free Fourier-Galerkin Müller assembly from Laurent geometry.

Inputs are z(theta)=center+scale*sum_j z_j exp(ij theta), not curve samples.
All products below are linear convolutions of coefficients. fftconvolve is
only a polynomial multiplication algorithm; no physical boundary grid exists.

For R=|z(w)-z(v)|^2 in normalized coordinates and W=(z(w)-z(v))/(w-v),
log R = log(4 sin^2((theta-phi)/2)) + 2 Re log W.
The first term has exact coefficients L_l=-1/|l| (l != 0), L_0=0.
J0's entire power series gives G_k=P_k(R)*log R+Q_k(R). Thus every layer
matrix entry is an explicit coefficient contraction, including singular ones.
"""
from dataclasses import dataclass
from time import perf_counter
import math

import numpy as np
from scipy.signal import fftconvolve


def conjugate(poly):
    return {tuple(-j for j in key): value.conjugate() for key, value in poly.items()}


def add(first, second, factor=1):
    result = dict(first)
    for key, value in second.items():
        result[key] = result.get(key, 0) + factor*value
    return {key: value for key, value in result.items() if abs(value) > 1e-30}


def multiply(first, second):
    result = {}
    for a, av in first.items():
        for b, bv in second.items():
            key = tuple(x+y for x, y in zip(a, b))
            result[key] = result.get(key, 0) + av*bv
    return {key: value for key, value in result.items() if abs(value) > 1e-30}


def times(poly, scalar):
    return {key: value*scalar for key, value in poly.items()}


def embed(poly, bandwidth):
    result = np.zeros((2*bandwidth+1,)*2, complex)
    for (a, b), value in poly.items():
        if abs(a) <= bandwidth and abs(b) <= bandwidth:
            result[a+bandwidth, b+bandwidth] += value
    return result


def sparse_product(array, poly):
    """Truncated linear convolution; never circular wraparound."""
    result = np.zeros_like(array)
    size = array.shape[0]
    for (a, b), value in poly.items():
        if abs(a) >= size or abs(b) >= size:
            continue
        dst = (slice(max(a, 0), min(size, size+a)), slice(max(b, 0), min(size, size+b)))
        src = (slice(max(-a, 0), min(size, size-a)), slice(max(-b, 0), min(size, size-b)))
        result[dst] += value*array[src]
    return result


def dense_product(first, second):
    bandwidth = (first.shape[0]-1)//2
    full = fftconvolve(first, second, mode='full')
    return full[bandwidth:3*bandwidth+1, bandwidth:3*bandwidth+1]


def kernel_matrix_reference(log_coefficients, smooth_coefficients, cutoff):
    """Literal exact-log contraction retained as an independent algebra check."""
    bandwidth = (log_coefficients.shape[0]-1)//2
    modes = np.arange(-cutoff, cutoff+1)
    mm, nn = np.meshgrid(modes, modes, indexing='ij')
    result = smooth_coefficients[mm+bandwidth, -nn+bandwidth].copy()
    for ell in range(-bandwidth-cutoff, bandwidth+cutoff+1):
        if ell == 0:
            continue
        a, b = mm-ell, ell-nn
        valid = (np.abs(a) <= bandwidth) & (np.abs(b) <= bandwidth)
        result[valid] -= log_coefficients[a[valid]+bandwidth, b[valid]+bandwidth]/abs(ell)
    return 2*np.pi*result


def kernel_matrix(log_coefficients, smooth_coefficients, cutoff):
    """Exact log-symbol contraction by linear convolution along coefficient diagonals.

    For d=m-n, convolve P_(a,d-a) with L_(m-a). This FFT multiplies
    coefficient sequences; it introduces no boundary collocation grid.
    """
    bandwidth = (log_coefficients.shape[0]-1)//2
    modes = np.arange(-cutoff, cutoff+1)
    mm, nn = np.meshgrid(modes, modes, indexing='ij')
    a = np.arange(-bandwidth, bandwidth+1)[None, :]
    d = np.arange(-2*cutoff, 2*cutoff+1)[:, None]
    b = d-a
    valid = np.abs(b) <= bandwidth
    diagonals = np.where(valid, log_coefficients[a+bandwidth,
                         np.clip(b+bandwidth, 0, 2*bandwidth)], 0)
    ell = np.arange(-bandwidth-cutoff, bandwidth+cutoff+1)
    symbol = -1/np.maximum(np.abs(ell), 1).astype(float)
    symbol[ell == 0] = 0
    product = fftconvolve(diagonals, symbol[None, :], axes=1)
    return 2*np.pi*(smooth_coefficients[mm+bandwidth, -nn+bandwidth]
                   + product[mm-nn+2*cutoff, mm+2*bandwidth+cutoff])


@dataclass
class LaurentGeometry:
    coefficients: dict[int, complex]
    center: complex
    scale: float

    @classmethod
    def from_coefficients(cls, coefficients):
        values = {int(j): complex(v) for j, v in coefficients.items() if abs(v) > 1e-30}
        center = values.pop(0, 0j)
        scale = abs(values.get(1, 0j))
        if scale == 0:
            raise ValueError('This prototype requires a nonzero positive fundamental mode.')
        return cls({j: v/scale for j, v in values.items()}, center, scale)

    @classmethod
    def circle(cls, center=0j, radius=.05):
        return cls.from_coefficients({0: center, 1: radius})

    @classmethod
    def ellipse(cls, center=0j, major=.045, minor=.026, rotation=.55):
        phase = np.exp(1j*rotation)
        return cls.from_coefficients({0: center, 1: phase*(major+minor)/2,
                                     -1: phase*(major-minor)/2})

    @classmethod
    def star(cls, center=0j, radius=.036, amplitude=.24, lobes=5, rotation=.2):
        phase = np.exp(1j*rotation)
        return cls.from_coefficients({0: center, 1: phase*radius,
                                     1+lobes: phase*radius*amplitude/2,
                                     1-lobes: phase*radius*amplitude/2})


class CoefficientGeometry:
    """Frequency-independent polynomial geometry and analytic log quotient.

    The log series is certified only when W/z_1 lies in a rectangle wholly
    in the right half-plane. The series bound does not certify the finite
    coefficient window: double bandwidth separately to assess that error.
    """
    def __init__(self, geometry, bandwidth=96, log_tolerance=1e-14):
        started = perf_counter()
        self.geometry, self.bandwidth = geometry, bandwidth
        z = geometry.coefficients
        target = {(j, 0): v for j, v in z.items()}
        source = {(0, j): v for j, v in z.items()}
        delta = add(target, source, -1)
        delta_bar = conjugate(delta)
        self.radius_squared = multiply(delta, delta_bar)
        # Normal times canonical speed: N=-i z', already a finite polynomial.
        nt = {(j, 0): j*v for j, v in z.items()}
        ns = {(0, j): j*v for j, v in z.items()}
        self.normal_dot = times(add(multiply(nt, conjugate(ns)), multiply(conjugate(nt), ns)), .5)
        self.target_dot = times(add(multiply(delta, conjugate(nt)), multiply(delta_bar, nt)), .5)
        self.source_dot = times(add(multiply(delta, conjugate(ns)), multiply(delta_bar, ns)), .5)
        quotient = {}
        for j, value in z.items():
            if j > 0:
                for r in range(j):
                    key = (j-1-r, r)
                    quotient[key] = quotient.get(key, 0) + value
            elif j < 0:
                for r in range(-j):
                    key = (-1-r, j+r)
                    quotient[key] = quotient.get(key, 0) - value
        fundamental = z[1]
        self.quotient = quotient
        normalized = times(quotient, 1/fundamental)
        real_part = times(add(normalized, conjugate(normalized)), .5)
        imag_part = times(add(normalized, conjugate(normalized), -1), -.5j)
        real_center = float(real_part.get((0, 0), 0).real)
        real_radius = sum(abs(v) for key, v in real_part.items() if key != (0, 0))
        imag_radius = sum(abs(v) for v in imag_part.values())
        lower, upper = real_center-real_radius, real_center+real_radius
        if lower <= 0:
            raise ValueError(f'Log-quotient certificate unavailable: Re(W/z1) >= {lower}.')
        alpha = max(upper, (lower**2+imag_radius**2)/lower)
        rho = math.hypot(1-lower/alpha, imag_radius/alpha)
        self.log_rectangle = dict(real_lower=lower, real_upper=upper, imag_bound=imag_radius,
                                  alpha=alpha, contraction=rho)
        e = add({(0, 0): 1}, times(normalized, -1/alpha))
        one = embed({(0, 0): 1}, bandwidth)
        log_w = one*np.log(alpha)
        power = one
        inverse = one.copy()
        for order in range(1, 2001):
            power = sparse_product(power, e)
            log_w -= power/order
            inverse += power
            # L2 bound for the projected coefficient recurrence: multiplication
            # by E has norm <= rho, and projection cannot increase that norm.
            # Window error remains a separate bandwidth-refinement check.
            bound = min(rho**(order+1),np.linalg.norm(power)*rho)/((order+1)*(1-rho))
            if bound < log_tolerance:
                break
        else:
            raise ValueError('Log quotient did not converge in 2000 powers.')
        self.log_quotient = log_w + log_w[::-1, ::-1].conj() + one*np.log(abs(fundamental)**2)
        self.inverse_quotient = inverse/(alpha*fundamental)
        self.log_order, self.log_series_bound = order, 2*bound
        self.seconds = perf_counter()-started

    def radial(self, ko, ki, terms):
        """P,Q,P',Q'+P/R, and k^2-weighted P,Q, with dimensionless k."""
        b = self.bandwidth
        arrays = [np.zeros((2*b+1, 2*b+1), complex) for _ in range(6)]
        power = embed({(0, 0): 1}, b)
        previous = None
        ao = ai = 1.0
        harmonic = 0.0
        for p in range(terms):
            if p:
                ao *= -(ko*ko/4)/(p*p)
                ai *= -(ki*ki/4)/(p*p)
                harmonic += 1/p
            po, pi = -ao/(4*np.pi), -ai/(4*np.pi)
            qo = ao*(.25j+(harmonic-np.euler_gamma-np.log(ko/2))/(2*np.pi))
            qi = ai*(.25j+(harmonic-np.euler_gamma-np.log(ki/2))/(2*np.pi))
            arrays[0] += (po-pi)*power
            arrays[1] += (qo-qi)*power
            if p:
                arrays[2] += p*(po-pi)*previous
                arrays[3] += (po-pi+p*(qo-qi))*previous
            arrays[4] += (ko*ko*po-ki*ki*pi)*power
            arrays[5] += (ko*ko*qo-ki*ki*qi)*power
            previous, power = power, sparse_product(power, self.radius_squared)
        return arrays

    def assemble(self, k_exterior, k_interior, cutoff, terms=28):
        started = perf_counter()
        if cutoff > self.bandwidth:
            raise ValueError('Trace cutoff must fit the coefficient bandwidth.')
        ko, ki = k_exterior*self.geometry.scale, k_interior*self.geometry.scale
        p, q, dp, dq, hp, hq = self.radial(ko, ki, terms)
        q += dense_product(p, self.log_quotient)
        dq += dense_product(dp, self.log_quotient)
        hq += dense_product(hp, self.log_quotient)
        v = kernel_matrix(p, q, cutoff)
        k = kernel_matrix(sparse_product(dp, times(self.source_dot, -2)),
                          sparse_product(dq, times(self.source_dot, -2)), cutoff)
        kp = kernel_matrix(sparse_product(dp, times(self.target_dot, 2)),
                           sparse_product(dq, times(self.target_dot, 2)), cutoff)
        modes = np.arange(-cutoff, cutoff+1)
        # Maue identity, applied to differences before truncation.
        t = -modes[:, None]*modes[None, :]*v + kernel_matrix(
            sparse_product(hp, self.normal_dot), sparse_product(hq, self.normal_dot), cutoff)
        identity = np.eye(len(modes))
        matrix = np.block([[identity-k, v], [-t, identity+kp]])
        return matrix, dict(assembly_seconds=perf_counter()-started,
                            geometry_seconds=self.seconds, log_order=self.log_order,
                            log_series_bound=self.log_series_bound,
                            log_bound_scope='coefficient L2, projected recurrence; excludes window error',
                            log_rectangle=self.log_rectangle,
                            coefficient_bandwidth=self.bandwidth, bessel_terms=terms,
                            trace_cutoff=cutoff, boundary_nodes=0, point_pair_kernel_calls=0)


class ModalMomentFamily:
    """Compile geometry once; frequencies only combine stored modal matrices.

    Stored moments are R^p, R^p log R and their source-normal and two-normal
    polynomial products. Frequency dependence is scalar Bessel-series weights.
    Compilation cost and memory must be included in amortization claims.
    """
    def __init__(self, prepared, cutoff=40, terms=28):
        started = perf_counter()
        self.prepared, self.cutoff, self.terms = prepared, cutoff, terms
        b = prepared.bandwidth
        modes = np.arange(-cutoff, cutoff+1)
        test, trial = np.meshgrid(modes+b, -modes+b, indexing='ij')
        shape = (terms, 2*cutoff+1, 2*cutoff+1)
        self.moments = {key: np.zeros(shape, complex) for key in
                        ('v_log', 'v_smooth', 'k_log', 'k_smooth', 'nn_log', 'nn_smooth')}
        power = embed({(0, 0): 1}, b)
        for p in range(terms):
            log_smooth = dense_product(power, prepared.log_quotient)
            for prefix, poly in [('v', {(0, 0): 1}), ('k', prepared.source_dot),
                                 ('nn', prepared.normal_dot)]:
                coeff = sparse_product(power, poly)
                smooth = sparse_product(log_smooth, poly)
                self.moments[prefix+'_log'][p] = kernel_matrix(coeff, smooth, cutoff)
                self.moments[prefix+'_smooth'][p] = 2*np.pi*coeff[test, trial]
            power = sparse_product(power, prepared.radius_squared)
        self.seconds = perf_counter()-started
        self.bytes = sum(value.nbytes for value in self.moments.values())

    def assemble(self, k_exterior, k_interior, cutoff=None, terms=None):
        started = perf_counter()
        if cutoff is not None and cutoff != self.cutoff:
            raise ValueError('Compiled trace cutoff is fixed.')
        if terms is not None and terms != self.terms:
            raise ValueError('Compiled expansion length is fixed.')
        ko = k_exterior*self.prepared.geometry.scale
        ki = k_interior*self.prepared.geometry.scale
        order = np.arange(self.terms)
        harmonic = np.r_[0, np.cumsum(1/np.arange(1, self.terms))]
        ao = np.ones(self.terms, complex)
        ai = ao.copy()
        for p in range(1, self.terms):
            ao[p] = ao[p-1]*(-ko*ko/(4*p*p))
            ai[p] = ai[p-1]*(-ki*ki/(4*p*p))
        po, pi = -ao/(4*np.pi), -ai/(4*np.pi)
        qo = ao*(.25j+(harmonic-np.euler_gamma-np.log(ko/2))/(2*np.pi))
        qi = ai*(.25j+(harmonic-np.euler_gamma-np.log(ki/2))/(2*np.pi))
        dp, dq = po-pi, qo-qi
        def combination(weights, name):
            return np.einsum('p,pmn->mn', weights, self.moments[name], optimize=False)
        v = combination(dp, 'v_log') + combination(dq, 'v_smooth')
        k = -2*(combination(np.r_[order[1:]*dp[1:], 0], 'k_log')
                + combination(np.r_[dp[1:]+order[1:]*dq[1:], 0], 'k_smooth'))
        kp = k[::-1, ::-1].T
        modes = np.arange(-self.cutoff, self.cutoff+1)
        t = (-modes[:, None]*modes[None, :]*v
             + combination(ko*ko*po-ki*ki*pi, 'nn_log')
             + combination(ko*ko*qo-ki*ki*qi, 'nn_smooth'))
        identity = np.eye(len(modes))
        return np.block([[identity-k, v], [-t, identity+kp]]), dict(
            assembly_seconds=perf_counter()-started, compile_seconds=self.seconds,
            compile_bytes=self.bytes, trace_cutoff=self.cutoff,
            bessel_terms=self.terms, boundary_nodes=0, point_pair_kernel_calls=0)
