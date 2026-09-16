"""Sources, receivers, and disconnected interactions without boundary nodes.

Regular cylindrical waves are composed with Laurent geometry by polynomial
arithmetic. Graf's addition formula supplies only center-to-center Hankel
values. Boundary integrals select Fourier coefficients exactly.
"""
from time import perf_counter
import numpy as np
from scipy.special import hankel1
from scipy.linalg import lu_factor, lu_solve
from .coefficient_operator import CoefficientGeometry


def convolve_sparse(array, coefficients):
    result = np.zeros_like(array)
    size = array.shape[0]
    for shift, value in coefficients.items():
        if abs(shift) < size:
            result[max(shift, 0):min(size, size+shift)] += value*array[max(-shift, 0):min(size, size-shift)]
    return result


def polynomial_product(first, second):
    result = {}
    for i, a in first.items():
        for j, b in second.items():
            result[i+j] = result.get(i+j, 0) + a*b
    return result


class RegularWaves:
    def __init__(self, geometry, wave, bandwidth=96, angular_order=36, terms=28):
        self.geometry, self.wave = geometry, wave
        self.bandwidth, self.angular_order = bandwidth, angular_order
        z = geometry.coefficients
        zbar = {-j: v.conjugate() for j, v in z.items()}
        rho = polynomial_product(z, zbar)
        h = wave*geometry.scale
        positive = np.zeros((2*bandwidth+1,), complex)
        positive[bandwidth] = 1
        negative = positive.copy()
        modes = np.arange(-angular_order-1, angular_order+2)
        functions = np.zeros((2*bandwidth+1, len(modes)), complex)
        for order in range(angular_order+2):
            if order:
                positive = convolve_sparse(positive, z)*(h/(2*order))
                negative = convolve_sparse(negative, zbar)*(h/(2*order))
            term = np.stack((positive, negative), axis=1)
            result = term.copy()
            for p in range(1, terms):
                term = convolve_sparse(term, rho)*(-h*h/(4*p*(p+order)))
                result += term
            functions[:, angular_order+1+order] = result[:, 0]
            functions[:, angular_order+1-order] = (-1)**order*result[:, 1]
        self.values = functions[:, 1:-1]
        # J d_n f_l = (h/2)[(-i z')f_(l-1)+(-i zbar')f_(l+1)].
        self.flux = h/2*(convolve_sparse(functions[:, :-2], {j: j*v for j, v in z.items()})
                         + convolve_sparse(functions[:, 2:], {j: j*v for j, v in zbar.items()}))

    def point_kernels(self, points):
        points = np.asarray(points)
        delta = points[:, 0]+1j*points[:, 1]-self.geometry.center
        radius_bound = self.geometry.scale*sum(abs(v) for v in self.geometry.coefficients.values())
        if np.any(np.abs(delta) <= radius_bound):
            raise ValueError('Graf point expansion requires points outside the bounding circle.')
        modes = np.arange(-self.angular_order, self.angular_order+1)
        weights = .25j*hankel1(modes[:, None], self.wave*np.abs(delta)[None, :])*np.exp(
            -1j*modes[:, None]*np.angle(delta)[None, :])
        return self.values@weights, self.flux@weights

    def rhs(self, sources, strengths, cutoff):
        values, flux = self.point_kernels(sources)
        indices = self.bandwidth+np.arange(-cutoff, cutoff+1)
        return np.concatenate((values[indices], flux[indices]), axis=0)*np.asarray(strengths)

    def receiver(self, receivers, cutoff):
        values, flux = self.point_kernels(receivers)
        indices = self.bandwidth-np.arange(-cutoff, cutoff+1)
        return 2*np.pi*np.concatenate((flux[indices].T, -values[indices].T), axis=1)


def cross_matrix(target, source, cutoff):
    """Exact mode translations truncated only in cylindrical-wave order."""
    delta = target.geometry.center-source.geometry.center
    target_radius = target.geometry.scale*sum(abs(v) for v in target.geometry.coefficients.values())
    source_radius = source.geometry.scale*sum(abs(v) for v in source.geometry.coefficients.values())
    if abs(delta) <= target_radius+source_radius:
        raise ValueError('Cross translation requires disjoint bounding circles in this prototype.')
    if target.wave != source.wave:
        raise ValueError('Cross interactions require the same exterior wavenumber.')
    p = np.arange(-target.angular_order, target.angular_order+1)
    q = np.arange(-source.angular_order, source.angular_order+1)
    order = p[:, None]+q[None, :]
    translate = .25j*(-1.)**p[:, None]*hankel1(order, target.wave*abs(delta))*np.exp(-1j*order*np.angle(delta))
    test = target.bandwidth+np.arange(-cutoff, cutoff+1)
    trial = source.bandwidth-np.arange(-cutoff, cutoff+1)
    ft, qt = target.values[test], target.flux[test]
    fs, qs = source.values[trial], source.flux[trial]
    v, k = 2*np.pi*ft@translate@fs.T, 2*np.pi*ft@translate@qs.T
    kp, t = 2*np.pi*qt@translate@fs.T, 2*np.pi*qt@translate@qs.T
    return np.block([[-k, v], [-t, kp]])


def solve(geometries, ko, ki, sources, receivers, strengths=1e-6, *, cutoff=40,
          bandwidth=96, angular_order=36, terms=28, prepared=None):
    """Entire forward calculation in coefficient space; component-major state."""
    started = perf_counter()
    if prepared is None:
        prepared = [CoefficientGeometry(g, bandwidth) for g in geometries]
    waves = [RegularWaves(g, ko, bandwidth, angular_order, terms) for g in geometries]
    rhs = np.concatenate([w.rhs(sources, strengths, cutoff) for w in waves], axis=0)
    receiver = np.concatenate([w.receiver(receivers, cutoff) for w in waves], axis=1)
    blocks, diagnostics = [], []
    for i, geom in enumerate(prepared):
        own, diag = geom.assemble(ko, ki, cutoff, terms)
        diagnostics.append(diag)
        blocks.append([own if i == j else cross_matrix(waves[i], waves[j], cutoff)
                       for j in range(len(geometries))])
    matrix = np.block(blocks)
    assembled = perf_counter()
    factors = lu_factor(matrix)
    state = lu_solve(factors, rhs)
    y = receiver@state
    return dict(y=y, state=state, a=matrix, b=rhs, c=receiver, factors=factors, waves=waves,
                diagnostics=diagnostics, setup_seconds=assembled-started,
                solve_seconds=perf_counter()-assembled, total_seconds=perf_counter()-started,
                boundary_nodes=0, point_pair_kernel_calls=0)
