"""MA-001 part A: exact (Mie) boundary wavefields and shape sensitivities of a circle.

Conventions: time dependence exp(-i omega t), incident field of a unit point
source at y is G(x, y) = (i/4) H0(k|x-y|), equal permeability, interior
wavenumber ki = k sqrt(contrast). For a source at polar (rho, phi) outside the
circle of radius R, the total boundary trace is

    u(R, theta) = sum_n U_n exp(i n theta),   U_n = b_n J_n(ki R) exp(-i n phi),
    b_n = (i/4) H_n(k rho) (2i / (pi R)) / D_n,
    D_n = k J_n(ki R) H_n'(k R) - ki J_n'(ki R) H_n(k R).

The reciprocal field of a receiver is the same expression at the receiver.
The Hadamard sensitivity of the scattered field at receiver r to a normal
velocity h = exp(i p theta) is

    J_p = (ki^2 - k^2) * 2 pi R * sum_n U_n V_{-p-n},

the Fourier-product identity of the vision document, exact on the circle.
The zeros of D_n in the lower half k-plane are the scattering resonances; for
kR < |n| < ki R they are the long-lived (trapped, whispering-gallery) modes.
"""
import numpy as np
from scipy.special import hankel1, h1vp, jv, jvp


def orders(cutoff):
    return np.arange(-cutoff, cutoff + 1)


def denominator(n, k, contrast, radius=1.0):
    ki = k * np.sqrt(contrast)
    return k * jv(n, ki * radius) * h1vp(n, k * radius) - ki * jvp(n, ki * radius) * hankel1(n, k * radius)


def _finite(values, n, k, contrast, radius):
    """Hankel overflow only occurs far beyond both field bands, where the terms vanish."""
    bad = ~np.isfinite(values)
    if np.any(np.abs(n[bad]) < 1.5 * k * np.sqrt(contrast) * radius + 30):
        raise FloatingPointError('Bessel overflow inside the physical band')
    return np.where(bad, 0, values)


def trace_coefficients(k, contrast, rho, phi, cutoff, radius=1.0):
    """U_n for |n| <= cutoff; rows are source positions phi (array)."""
    n = orders(cutoff)
    ki = k * np.sqrt(contrast)
    with np.errstate(all='ignore'):
        ratio = hankel1(n, k * rho) / hankel1(n, k * radius)
        log_derivative = h1vp(n, k * radius) / hankel1(n, k * radius)
        reduced = k * jv(n, ki * radius) * log_derivative - ki * jvp(n, ki * radius)
        b = 0.25j * (2j / (np.pi * radius)) * ratio / reduced
        b = _finite(b * jv(n, ki * radius), n, k, contrast, radius)
    return b[None, :] * np.exp(-1j * np.outer(np.atleast_1d(phi), n))


def scattered(k, contrast, rho_s, phi_s, rho_r, phi_r, cutoff, radius=1.0):
    """Exact scattered field at the receivers (paired: same index)."""
    n = orders(cutoff)
    ki = k * np.sqrt(contrast)
    alpha = 0.25j * hankel1(n, k * rho_s)
    # a_n from the exterior continuity equation: alpha J + a H = b J(ki R)
    b = alpha * (2j / (np.pi * radius)) / denominator(n, k, contrast, radius)
    a = (b * jv(n, ki * radius) - alpha * jv(n, k * radius)) / hankel1(n, k * radius)
    phase = np.exp(1j * np.outer(np.atleast_1d(phi_r) - np.atleast_1d(phi_s), n))
    return (phase * (a * hankel1(n, k * rho_r))[None, :]).sum(axis=1)


def pair_terms(U, V, p):
    """Terms U_n V_{-p-n} for every n where both indices are stored: (rows, n)."""
    cutoff = (U.shape[1] - 1) // 2
    n = orders(cutoff)
    j = -p - n
    keep = np.abs(j) <= cutoff
    out = np.zeros(U.shape, complex)
    out[:, keep] = U[:, keep] * V[:, j[keep] + cutoff]
    return out


def sensitivity(U, V, p, k, contrast, radius=1.0):
    delta = k ** 2 * (contrast - 1)
    return delta * 2 * np.pi * radius * pair_terms(U, V, p).sum(axis=1)
