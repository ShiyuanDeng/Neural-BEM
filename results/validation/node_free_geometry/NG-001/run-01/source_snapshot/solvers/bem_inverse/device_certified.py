"""NU-007: the NU-006 update with its |W|^2 certificates evaluated on the GPU.

NU-005's tiers call ``n_update.curve_certificate`` (``modal_geometry.log_modulus`` on
scipy FFTs) for the accepted curve of each prepared space and for every trial curve that
reaches tier 3. In NU-006 these took 104 s of 242 s wall time. ``device_certificate``
is the same construction in torch float64:

  W divided-difference coefficients -> |W|^2 = Re(W conj W) by FFT convolution;
  Lambda = ||ww||_1; beta = half the sampled minimum on the same FFT grid size;
  Chebyshev degree from the same scalar bound; the windowed multiplier with the
  polynomial cropped to 2B and linear-convolution padding; the reciprocal series;
  the untruncated residual ||1 - |W|^2 Y||_1 and the same rounding allowance
  80 size eps Lambda ||Y||_1.

It refuses (ValueError) under the same conditions: sampled minimum <= 0, degree above
``max_degree`` (including after the one recomputation), or lower bound <= 0. The
log|W|^2 series itself is not formed, because no tier uses it; the recomputed interval
only reports its degree. Everything else is NU-006 unchanged.

Campaigns and diagnostics remain under experiments.cleaned_interface.
"""
import time
import numpy as np
import torch
from scipy.fft import next_fast_len
from .n_update import curve_certificate, derivative_norm
from .batched import BatchedCertifiedUpdate


EPS = np.finfo(float).eps


def _convolve(first, second):
    shape = (first.shape[0]+second.shape[0]-1,)*2
    return torch.fft.ifft2(torch.fft.fft2(first, shape)*torch.fft.fft2(second, shape))


def _degree(upper, beta, tolerance, max_degree):
    root_upper, root_lower = np.sqrt(upper), np.sqrt(beta)
    ratio = (root_upper-root_lower)/(root_upper+root_lower)
    degree = 1
    while 2*ratio**(degree+1)/((degree+1)*(1-ratio)) > tolerance:
        degree += 1
        if degree > max_degree:
            raise ValueError(f'log|W|^2 needs more than {max_degree} Chebyshev terms '
                             f'(beta/Lambda={beta/upper:.3g}); curve is nearly self-touching.')
    return degree, ratio


def device_certificate(curve, window, device, *, tolerance=1e-12, max_degree=4000):
    """``n_update.curve_certificate`` in torch float64 on ``device``; same keys and refusals."""
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
    if not np.isfinite(upper) or upper <= 0 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Positive finite modulus norm and log tolerance required.')
    half = (ww.shape[0]-1)//2
    grid = max(64, next_fast_len(4*half+4))
    spectrum = torch.zeros((grid, grid), dtype=torch.complex128, device=device)
    index = torch.arange(-half, half+1, device=device) % grid
    spectrum[index[:, None], index[None, :]] = ww
    sampled = float(torch.fft.ifft2(spectrum).real.min())*grid*grid
    if not sampled > 0:
        raise ValueError(f'Inconclusive interval proposal: sampled min |W|^2 = {sampled:g}.')
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
    if not np.isfinite([residual, norm, allowance, lower]).all() or norm <= 0:
        raise ValueError('Non-finite reciprocal residual certificate.')
    recomputed = False
    if lower < beta:
        if not lower > 0:
            raise ValueError(f'|W|^2 lower bound not certified (coefficient residual {residual:.3g}).')
        beta, recomputed = lower, True
        degree, _ = _degree(upper, beta, tolerance, max_degree)
    return dict(window=window, rho=residual, allowance=allowance, reciprocal_l1=norm, beta=beta, Lambda=upper,
                log_degree=degree, recomputed=recomputed, nu=float(derivative_norm(z)),
                arithmetic_verified=False, rounding_model='heuristic FFT allowance', proposal_grid=grid,
                seconds=time.perf_counter()-started)


class DeviceCertifiedUpdate(BatchedCertifiedUpdate):
    """NU-006 update; tier-2 and tier-3 certificates on the update's device."""

    def __init__(self, length_unit_m, **kwargs):
        super().__init__(length_unit_m, **kwargs)
        self.counts.update(device_certificate_fallbacks=0)

    def settings(self):
        return dict(super().settings(), certificate='torch float64 port of curve_certificate (NU-007)',
                    certificate_device=self.device)

    def _certificate(self, curve, window):
        started = time.perf_counter()
        try:
            return device_certificate(curve, window, self.device)
        except ValueError:
            return None
        except torch.OutOfMemoryError:
            torch.cuda.empty_cache()
            self.counts['device_certificate_fallbacks'] += 1
            try:
                return curve_certificate(curve, window)
            except ValueError:
                return None
        finally:
            self.counts['certificate_seconds'] += time.perf_counter()-started
