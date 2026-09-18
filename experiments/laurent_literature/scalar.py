"""Jiang--Wang--Yu 2021 Section 3 mask and scalar Helmholtz reference.

The physical kernel here is i/4 H0^(1); the paper uses 1/(2i) H0^(1).
Its additional scalar normalization is immaterial when both A and RHS are
scaled consistently. Densities use the orthonormal basis exp(imt)/sqrt(2*pi).
The paper's n includes |m| < n, so our cutoff is n-1. Its b[k,l] are DOUBLE
kernel Fourier coefficients: the matrix acting on input mode q uses l=-q.

Dense reference coefficient quadrature is intentional: it isolates the exact
published truncation from fast assembly, which is not claimed reproduced here.
"""
import numpy as np
from scipy.signal import fftconvolve
from scipy.special import hankel1, j0


def literature_mask(cutoff, mu=1.2, *, mask_n=None):
    if cutoff < 0 or not np.isfinite(mu) or mu <= 1:
        raise ValueError('Use nonnegative cutoff and mu > 1 (Theorem 4).')
    n=cutoff+1 if mask_n is None else mask_n
    if not np.isfinite(n) or n<cutoff+1:
        raise ValueError('mask_n must include the retained trace space.')
    modes = np.arange(-cutoff, cutoff+1, dtype=float)
    m, q = np.meshgrid(modes, modes, indexing='ij')
    return (1+(m-q)**2)**mu * np.minimum(1+m*m, 1+q*q) <= n*n


def convolution_diagonal(cutoff):
    modes = np.arange(-cutoff, cutoff+1)
    return np.where(modes == 0, 1., .5/np.maximum(1, np.abs(modes)))


def ellipse_coefficients(major, minor, wave, grid=256):
    """Smooth amplitudes P,S of i/4 H0 = P log(4 sin²/2)+S.

    Exact ellipse divided-distance formula supplies the diagonal and avoids
    subtracting nearby coordinates. Crop at grid/4 and qualify by grid doubling.
    """
    if min(major, minor, wave) <= 0 or grid < 32 or grid % 4:
        raise ValueError('Positive geometry/frequency; grid divisible by four.')
    theta = 2*np.pi*np.arange(grid)/grid
    t, s = theta[:, None], theta[None, :]
    sin2 = 4*np.sin((t-s)/2)**2
    speed2 = major**2*np.sin((t+s)/2)**2 + minor**2*np.cos((t+s)/2)**2
    r = np.sqrt(sin2*speed2)
    diagonal = np.eye(grid, dtype=bool)
    safe_r = np.where(diagonal, 1., r)
    log_sin = np.log(np.where(diagonal, 1., sin2))
    p = -j0(wave*r)/(4*np.pi)
    smooth = .25j*hankel1(0, wave*safe_r)-p*log_sin
    smooth[diagonal] = .25j-(np.euler_gamma+np.log(wave*np.sqrt(speed2[diagonal])/2))/(2*np.pi)
    b = grid//4
    def fourier(x):
        coeff = np.fft.fftshift(np.fft.fft2(x))/grid**2
        return coeff[grid//2-b:grid//2+b+1, grid//2-b:grid//2+b+1].copy()
    return fourier(p), fourier(smooth)


def kernel_matrix(p, s, cutoff):
    """Exact logarithm contraction, also for trace cutoff > coefficient window.

    Integrating input exp(iqt) selects S[m,-q]. For each d=m-q, log
    contraction is the linear convolution sum_a P[a,d-a] L[m-a].
    """
    b = (p.shape[0]-1)//2
    if p.shape != (2*b+1, 2*b+1) or s.shape != p.shape:
        raise ValueError('Matching odd square coefficient arrays required.')
    k = cutoff
    result = np.zeros((2*k+1, 2*k+1), complex)
    modes = np.arange(-k, k+1)
    keep = min(k, b)
    small = np.arange(-keep, keep+1)
    result[np.ix_(small+k, small+k)] = s[np.ix_(small+b, -small+b)]
    ell = np.arange(-k-b, k+b+1)
    symbol = -1/np.maximum(np.abs(ell), 1).astype(float)
    symbol[ell == 0] = 0
    aa = np.arange(-b, b+1)
    for d in range(-min(2*k, 2*b), min(2*k, 2*b)+1):
        bb = d-aa
        valid = np.abs(bb) <= b
        diag = np.zeros(2*b+1, complex)
        diag[valid] = p[aa[valid]+b, bb[valid]+b]
        product = fftconvolve(diag, symbol)
        rows = modes[(modes-d >= -k) & (modes-d <= k)]
        result[rows+k, rows-d+k] += product[rows+k+2*b]
    return 2*np.pi*result


def direct_log_matrix(p, s, cutoff):
    """Slow independent finite-sum formula for tiny regression fixtures."""
    b = (p.shape[0]-1)//2
    modes = np.arange(-cutoff, cutoff+1)
    out = np.zeros((len(modes), len(modes)), complex)
    for i, m in enumerate(modes):
        for j, q in enumerate(modes):
            if abs(m) <= b and abs(q) <= b:
                out[i, j] = s[m+b, -q+b]
            for a in range(-b, b+1):
                ell, other = m-a, m-q-a
                if ell and abs(other) <= b:
                    out[i, j] -= p[a+b, other+b]/abs(ell)
    return 2*np.pi*out


def ellipse_log_density(modes, major=2., minor=1., point=1.9):
    """Exact coefficients for paper Example 3, including the constant mode.

    z(t)-point = a/w (w-r1)(w-r2). For the stated ellipse and point both
    roots lie inside the unit disk. Log modulus then has explicit coefficients.
    """
    a, b = (major+minor)/2, (major-minor)/2
    roots = np.roots([a, -point, b])
    if np.max(np.abs(roots)) >= 1:
        raise ValueError('This formula requires both roots inside the unit disk.')
    modes = np.asarray(modes)
    order = np.abs(modes)
    coeff = -(roots[0]**order+roots[1]**order)/(2*np.maximum(order, 1))
    coeff = np.asarray(coeff, complex)
    coeff[order == 0] = np.log(a)
    return np.sqrt(2*np.pi)*coeff
