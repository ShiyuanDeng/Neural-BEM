"""Optional coefficient certificates for spectral geometry updates.

These calculations bound the divided difference between every pair of curve
parameters. A positive bound proves both nonintersection and regularity.
The ordinary sampled geometry update does not use this module.
"""
import time
import numpy as np
import torch
from scipy.fft import next_fast_len
from .. import checks
from ..modal_geometry import log_modulus, real_product

EPS = np.finfo(float).eps
SPEED_FACTOR = 1e-6


def derivative_norm(coefficients):
    """Sum |j| |z_j|: an upper bound for a Fourier divided difference."""
    band = (coefficients.shape[-1]-1)//2
    return np.sum(np.abs(np.arange(-band, band+1)*coefficients), axis=-1)


def curve_certificate(curve, window, *, tolerance=1e-12, max_degree=4000):
    """rho_c=||1-|W|^2 Y||_1 and ||Y||_1 for the accepted curve (modal_geometry construction)."""
    started = time.perf_counter()
    z, k = curve.coefficients, curve.band
    quotient = np.zeros((2*k+1, 2*k+1), complex)
    for j in range(1, k+1):
        r = np.arange(j)
        quotient[k+j-1-r, k+r] += z[k+j]
        quotient[k-1-r, k-j+r] -= z[k-j]
    _, interval = log_modulus(real_product(quotient, quotient, 2), window, tolerance, max_degree)
    cert = interval['certificate']
    return dict(window=window, rho=cert['residual'], allowance=cert['allowance'],
                reciprocal_l1=cert['reciprocal_l1'], beta=interval['lower'], Lambda=interval['upper'],
                log_degree=interval['degree'], nu=float(derivative_norm(z)),
                arithmetic_verified=False, rounding_model='heuristic FFT allowance',
                proposal_grid=interval['proposal_grid'],
                seconds=time.perf_counter()-started)


def _convolve(first, second):
    shape = (first.shape[0]+second.shape[0]-1,)*2
    return torch.fft.ifft2(torch.fft.fft2(first, shape)*torch.fft.fft2(second, shape))


def _degree(upper, beta, tolerance, max_degree):
    root_upper, root_lower = np.sqrt(upper), np.sqrt(beta)
    ratio = (root_upper-root_lower)/(root_upper+root_lower)
    degree = 1
    while checks.log_tail_exceeds(ratio, degree, tolerance):
        degree += 1
        checks.require_log_degree(degree, max_degree, beta, upper)
    return degree, ratio


def device_certificate(curve, window, device, *, tolerance=1e-12, max_degree=4000):
    """``curve_certificate`` in torch float64 on ``device``; same keys and refusals."""
    started = time.perf_counter()
    z, k = curve.coefficients, curve.band
    quotient = np.zeros((2*k+1, 2*k+1), complex)
    for j in range(1, k+1):
        r = np.arange(j)
        quotient[k+j-1-r, k+r] += z[k+j]
        quotient[k-1-r, k-j+r] -= z[k-j]
    quotient = torch.as_tensor(quotient, device=device)
    product = _convolve(quotient, quotient.flip(0, 1).conj())
    ww = (product+product.flip(0, 1).conj())/2
    upper = float(ww.abs().sum())
    checks.require_modulus_domain(upper, tolerance)
    half = (ww.shape[0]-1)//2
    grid = max(64, next_fast_len(4*half+4))
    spectrum = torch.zeros((grid, grid), dtype=torch.complex128, device=device)
    index = torch.arange(-half, half+1, device=device) % grid
    spectrum[index[:, None], index[None, :]] = ww
    sampled = float(torch.fft.ifft2(spectrum).real.min())*grid*grid
    checks.require_positive_modulus_sample(sampled)
    beta = sampled/2
    degree, ratio = _degree(upper, beta, tolerance, max_degree)
    mapped = 2*ww/(upper-beta)
    mapped[half, half] -= (upper+beta)/(upper-beta)
    crop = min(half, 2*window)
    poly = mapped[half-crop:half+crop+1, half-crop:half+crop+1]
    size = 2*window+1
    shape = (size+poly.shape[0]-1,)*2
    transform = torch.fft.fft2(poly, shape)

    def multiply(array):
        return torch.fft.ifft2(torch.fft.fft2(array, shape)*transform)[crop:crop+size, crop:crop+size]

    previous = torch.zeros((size, size), dtype=torch.complex128, device=device)
    previous[window, window] = 1
    current = multiply(previous)
    scale = 1/np.sqrt(upper*beta)
    inverse = scale*(previous-2*ratio*current)
    for n in range(2, degree+1):
        previous, current = current, 2*multiply(current)-previous
        inverse = inverse+(2*scale*(-ratio)**n)*current
    product = _convolve(ww, inverse)
    centre = (product.shape[0]-1)//2
    product[centre, centre] -= 1
    residual = float(product.abs().sum())
    norm = float(inverse.abs().sum())
    allowance = 80*product.numel()*EPS*upper*norm
    lower = (1-residual-allowance)/norm
    checks.require_finite_certificate(residual, norm, allowance, lower)
    recomputed = False
    if checks.interval_needs_recompute(lower, beta):
        checks.require_positive_certificate(lower, residual)
        beta, recomputed = lower, True
        degree, _ = _degree(upper, beta, tolerance, max_degree)
    return dict(window=window, rho=residual, allowance=allowance, reciprocal_l1=norm, beta=beta, Lambda=upper,
                log_degree=degree, recomputed=recomputed, nu=float(derivative_norm(z)),
                arithmetic_verified=False, rounding_model='heuristic FFT allowance', proposal_grid=grid,
                seconds=time.perf_counter()-started)


def regularity_floor(x):
    """lambda needed so |x'|^2 >= lambda implies min|x'| >= 1e-6 mean|x'| (mean|x'| <= sqrt(sum j^2|x_j|^2))."""
    modes = np.arange(-(len(x)//2), len(x)//2+1)
    return SPEED_FACTOR**2*float(np.sum(modes**2*np.abs(x)**2))



def increment_bound(certificate, change):
    """Lemma 3 with Lemma 4: (bound, lambda); bound < 1 certifies |W_new|^2 >= lambda on the torus."""
    nu_d = float(derivative_norm(change))
    bound = certificate['rho']+certificate['allowance']+(2*certificate['nu']*nu_d+nu_d**2)*certificate['reciprocal_l1']
    return bound, (1-bound)/certificate['reciprocal_l1'], nu_d



