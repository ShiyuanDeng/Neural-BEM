"""Opt-in ON-003 finite-tau outgoing controls; no solver registration/defaults.

The far multiplier is the radial transform of the *truncated far kernel*,
not samples of a Helmholtz pole. Circle controls use exact Fourier moments.
General boundary quadrature maps, when implemented, belong to this module.
All lengths and wavenumbers passed here are in metres and inverse metres.
"""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.special import erf, expn, hankel1, h1vp, j0, jv, jvp, roots_legendre


def flat_near(omega, k, tau):
    """Finite-tau line symbol with the removable grazing limit."""
    a = np.asarray(omega, complex)**2-complex(k)**2
    z = np.sqrt(a*tau)
    out = np.empty_like(z)
    small = np.abs(z) < 1e-4
    zz = z[small]**2
    out[small] = np.sqrt(tau/np.pi)*(1-zz/3+zz**2/10-zz**3/42)
    out[~small] = np.sqrt(tau)*erf(z[~small])/(2*z[~small])
    return out


def flat_curvature(omega, k, tau, curvature, order=128):
    """First arclength single-layer correction, constant curvature, order kappa^2.

    Chord squared = s^2-kappa^2*s^4/12+O(s^6). Fourier transforming the
    s^4/(48t) heat correction gives the integrand below. This is an asymptotic
    term, not a uniform bound or a correction for double layers.
    """
    x, w = roots_legendre(order)
    # t=tau*u^2 removes the t^-1/2 endpoint.
    u = (x+1)/2
    t = tau*u*u
    a = np.asarray(omega, complex)[..., None]**2-complex(k)**2
    om = np.asarray(omega, complex)[..., None]
    base = np.sqrt(tau/np.pi)*w/2*np.exp(-a*t)
    return curvature**2/48*np.sum(base*(12*t-48*t*t*om**2+16*t**3*om**4), axis=-1)


def _heat_series(k, tau):
    z = complex(k)**2*tau
    term = 1.+0j
    terms = [term]
    for p in range(1, 80):
        term *= z/p
        terms.append(term)
        if abs(term) < 2e-17:
            break
    else:
        raise ValueError("Unresolved heat series")
    return terms


def near_kernel(r, k, tau):
    """G_near for positive r; convergent exponential-integral series."""
    r = np.asarray(r, float)
    if np.any(r <= 0):
        raise ValueError("near_kernel requires positive separations")
    x = r*r/(4*tau)
    result = np.zeros_like(x, complex)
    for p, term in enumerate(_heat_series(k, tau)):
        result += term*expn(p+1, x)
    return result/(4*np.pi)


def near_derivative(r, k, tau):
    """d G_near/d(r^2), for positive r."""
    r = np.asarray(r, float)
    x = r*r/(4*tau)
    result = np.zeros_like(x, complex)
    for p, term in enumerate(_heat_series(k, tau)):
        result -= term*expn(p, x)/(16*np.pi*tau)
    return result


def far_origin(k, tau):
    terms = _heat_series(k, tau)
    return .25j-(np.euler_gamma+np.log(complex(k)**2*tau)
                   +sum(term/p for p, term in enumerate(terms) if p))/(4*np.pi)


def far_kernel(r, k, tau):
    """Smooth G_outgoing-G_near, including its analytically cancelled origin."""
    r = np.asarray(r, float)
    out = np.empty(r.shape, complex)
    zero = r == 0
    out[zero] = far_origin(k, tau)
    # Gauss nodes never equal zero. At the smallest nodes subtraction of two
    # logarithms loses only a few ulps; the control checks this against origin.
    out[~zero] = .25j*hankel1(0, k*r[~zero])-near_kernel(r[~zero], k, tau)
    return out


def cutoff(r, R0, R1):
    s = (np.asarray(r)-R0)/(R1-R0)
    w = np.ones_like(s)
    w[s >= 1] = 0
    interior = (s > 0) & (s < 1)
    a = np.exp(-1/s[interior])
    b = np.exp(-1/(1-s[interior]))
    w[interior] = b/(a+b)
    return w


@dataclass(frozen=True)
class FarGrid:
    q: np.ndarray
    unique_q: np.ndarray
    inverse: np.ndarray
    period: float
    size: int
    R0: float
    R1: float
    tau: float

    @classmethod
    def build(cls, size, tau, R0):
        if size not in (128, 256):
            raise ValueError("ON-003 permits only grids 128 and 256")
        R1 = R0+8*np.sqrt(tau)
        L = 2.1*R1
        modes = np.fft.fftfreq(size)*size
        xx, yy = np.meshgrid(modes, modes, indexing="ij")
        # Integer squared radii give identical reuse grouping at every grid.
        r2, inverse = np.unique((xx*xx+yy*yy).astype(int), return_inverse=True)
        return cls(2*np.pi/L*np.stack((xx.ravel(), yy.ravel()), axis=1),
                   2*np.pi/L*np.sqrt(r2), inverse, L, size, R0, R1, tau)

    def multiplier(self, k, order):
        """Integral 2pi int r w(r) G_far(r) J0(qr) dr / L^2."""
        started = perf_counter()
        x, w = roots_legendre(order)
        breaks = sorted(set([0., np.sqrt(self.tau), 4*np.sqrt(self.tau), self.R0, self.R1]))
        values = np.zeros(len(self.unique_q), complex)
        peak = 0
        for left, right in zip(breaks[:-1], breaks[1:]):
            r = left+(x+1)*(right-left)/2
            weights = w*(right-left)/2*r*cutoff(r, self.R0, self.R1)*far_kernel(r, k, self.tau)
            for start in range(0, len(values), 512):
                B = j0(self.unique_q[start:start+512, None]*r)
                values[start:start+512] += B@weights
                peak = max(peak, B.nbytes+weights.nbytes+r.nbytes)
        values *= 2*np.pi/self.period**2
        diagonal = values[self.inverse]
        cap = np.pi*self.size/self.period
        nyquist = np.any(np.isclose(np.abs(self.q), cap, rtol=1e-13, atol=0), axis=1)
        diagonal[nyquist] = 0
        return diagonal, dict(seconds=perf_counter()-started,
            quadrature_order=order, quadrature_intervals=len(breaks)-1,
            unique_radii=len(values), transient_workspace_bytes=peak,
            multiplier_bytes=self.size**2*16,
            q_spacing_per_m=2*np.pi/self.period,
            q_max_axis_per_m=np.pi*self.size/self.period)


def circle_near(radius, k, tau, modes, count):
    """Exact complete near remainder, Kress logarithmic quadrature on circle.

    Returns individual-medium V, K and Maue T diagonal actions in the fixed
    parameter basis (u,J*d_n u). The jump terms cancel in medium differences.
    """
    theta = 2*np.pi*np.arange(count)/count
    r = 2*radius*np.sin(theta/2)
    terms = _heat_series(k, tau)
    G = np.empty(count, complex)
    G[1:] = near_kernel(r[1:], k, tau)
    P = -jv(0, k*r)/(4*np.pi)
    logtheta = np.empty(count)
    logtheta[1:] = np.log(4*np.sin(theta[1:]/2)**2)
    # Split uses log(4 sin^2), so the constant radius factor stays in Q.
    smooth = np.empty(count, complex)
    smooth[1:] = G[1:]-P[1:]*logtheta[1:]
    smooth[0] = (-np.euler_gamma+np.log(4*tau/radius**2)
                  +sum(term/p for p, term in enumerate(terms) if p))/(4*np.pi)
    log_spectrum = np.zeros(count)
    ell = np.fft.fftfreq(count)*count
    log_spectrum[1:] = -1/np.abs(ell[1:])
    logweights = np.fft.ifft(log_spectrum).real*count
    integrated = P*logweights+smooth
    V = 2*np.pi*np.fft.fft(integrated)/count
    # source N dot (x-y)= -r^2/2 on a CCW circle.
    Gprime = near_derivative(r[1:], k, tau)
    K = np.zeros(count, complex)
    K[1:] = Gprime*r[1:]**2
    dp = np.empty(count, complex)
    dp[1:] = k*jv(1,k*r[1:])/(8*np.pi*r[1:])
    dp[0] = k*k/(16*np.pi)
    KP = dp*r*r
    KS = np.zeros(count, complex)
    KS[0] = -1/(4*np.pi)  # finite trace limit r^2 Gprime, universal in k
    KS[1:] = K[1:]-KP[1:]*logtheta[1:]
    Kcoeff = 2*np.pi*np.fft.fft(KP*logweights+KS)/count
    H = 2*np.pi*np.fft.fft(integrated*radius**2*k*k*np.cos(theta))/count
    idx = np.asarray(modes)%count
    return np.array([V[idx], Kcoeff[idx], -np.asarray(modes)**2*V[idx]+H[idx]])


def circle_far(radius, k, grid, diagonal, modes):
    """Analytic circle moment diagonal, all columns m=-K..K retained.

    A[q,n]=(-i)^n J_n(q*a) exp(i*n*arg(q)). The scalar diagonal is a lower
    bound on a failed full block action; passing it alone cannot qualify the
    anisotropic Cartesian-grid operator.
    """
    q = grid.unique_q
    weights = np.bincount(grid.inverse, weights=diagonal.real)+1j*np.bincount(grid.inverse, weights=diagonal.imag)
    qa = radius*q[:, None]
    modes = np.asarray(modes)
    J = jv(modes[None, :], qa)
    Jp = jvp(modes[None, :], qa)
    V = 2*np.pi*np.sum(weights[:, None]*J*J, axis=0)
    K = 2*np.pi*np.sum(weights[:, None]*J*qa*Jp, axis=0)
    normals = radius**2/2*(jv(modes[None,:]-1, qa)**2+jv(modes[None,:]+1, qa)**2)
    H = 2*np.pi*k*k*np.sum(weights[:, None]*normals, axis=0)
    return np.array([V, K, -modes*modes*V+H]), dict(workspace_bytes=J.nbytes+Jp.nbytes+normals.nbytes,
                                                   representation="analytic circle Fourier moments")


def circle_exact(radius, k, modes):
    """Outgoing circle V,K,T diagonal by Graf/Bessel trace limits."""
    x = k*radius
    n = np.asarray(modes)
    V = .5j*np.pi*jv(n,x)*hankel1(n,x)
    K = .5j*np.pi*x*jvp(n,x)*hankel1(n,x)-.5
    T = .5j*np.pi*x*x*jvp(n,x)*h1vp(n,x)
    return np.array([V,K,T])
