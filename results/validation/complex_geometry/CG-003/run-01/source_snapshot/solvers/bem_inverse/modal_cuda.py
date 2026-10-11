"""CUDA execution of the modal Müller geometry stage and per-frequency assembly.

This module mirrors modal_geometry.ModalGeometry and modal_operator.muller_matrix
in torch float64/complex128. On the device it runs:

- the polynomial products,
- the certified log|W|^2 recurrence,
- the stored T_n(R) arrays,
- the frequency combination,
- the exact-log Galerkin contraction.

The assembled matrix returns to the host. Several parts stay on the CPU:

- analytic radial coefficients (extended-precision Bessel recurrence) and
  other scalar Bessel/Hankel values (SciPy; no torch.special Bessel calls),
- Graf sources and receivers,
- the regular-wave arrays,
- LU.

Handles therefore hold no device memory. The CPU modules remain the reference,
and the two agree to roundoff.
"""
from threading import Lock
from time import perf_counter
from functools import lru_cache

import numpy as np
from scipy.fft import next_fast_len
import torch

from .modal_geometry import EPS, Multiplier, WaveArrays, half, reflect
from .modal_operator import radial_coefficients

COMPLEX = torch.complex128


def _tensor(array, device):
    return torch.tensor(np.asarray(array), dtype=COMPLEX, device=device)


def _crop(array, band, ndim):
    old = half(array)
    if old >= band:
        return array[(Ellipsis,)+(slice(old-band, old+band+1),)*ndim]
    return torch.nn.functional.pad(array, (band-old,)*(2*ndim))


def _delta(band, ndim, device):
    one = torch.zeros((2*band+1,)*ndim, dtype=COMPLEX, device=device)
    one[(band,)*ndim] = 1
    return one


def _reflect(array, ndim):
    return array.flip(tuple(range(-ndim, 0))).conj()


def _convolve(first, second, ndim):
    """Full linear convolution over the last ``ndim`` axes (scipy fftconvolve 'full')."""
    axes = tuple(range(-ndim, 0))
    size = [first.shape[a]+second.shape[a]-1 for a in axes]
    fast = [next_fast_len(n) for n in size]
    full = torch.fft.ifftn(torch.fft.fftn(first, s=fast, dim=axes)*torch.fft.fftn(second, s=fast, dim=axes), dim=axes)
    return full[(Ellipsis,)+tuple(slice(0, n) for n in size)]


def _real_product(first, second, ndim):
    product = _convolve(first, _reflect(second, ndim), ndim)
    return (product+_reflect(product, ndim))/2


class DeviceMultiplier:
    """modal_geometry.Multiplier on the device (2-D)."""

    def __init__(self, poly, band):
        poly = _crop(poly, min(half(poly), 2*band), 2)
        self.band, self.offset = band, half(poly)
        self.shape = (next_fast_len(2*band+poly.shape[-1]),)*2
        self.transform = torch.fft.fftn(poly, s=self.shape, dim=(-2, -1))

    def __call__(self, array):
        full = torch.fft.ifftn(torch.fft.fftn(array, s=self.shape, dim=(-2, -1))*self.transform, dim=(-2, -1))
        window = slice(self.offset, self.offset+2*self.band+1)
        return full[..., window, window]


class DeviceRealMultiplier:
    """modal_geometry.RealMultiplier on the device: half-spectrum transforms of real functions."""

    def __init__(self, poly, band):
        poly = _crop(poly, min(half(poly), 2*band), 2)
        self.band, self.device = band, poly.device
        self.size = next_fast_len(2*band+poly.shape[-1])
        self.rows = torch.arange(-band, band+1, device=self.device) % self.size
        self.values = torch.fft.irfftn(self._spectrum(poly), s=(self.size,)*2, dim=(-2, -1))*self.size**2

    def _spectrum(self, array):
        b, n = half(array), self.size
        out = torch.zeros(array.shape[:-2]+(n, n//2+1), dtype=COMPLEX, device=self.device)
        out[..., torch.arange(-b, b+1, device=self.device) % n, :b+1] = array[..., :, b:]
        return out

    def __call__(self, array):
        n, b = self.size, self.band
        grid = torch.fft.irfftn(self._spectrum(array), s=(n, n), dim=(-2, -1))
        right = torch.fft.rfftn(grid*self.values, dim=(-2, -1))[..., self.rows, :b+1]
        return torch.cat((right.flip(-2).flip(-1)[..., :b].conj(), right), dim=-1)


class DeviceChebyshevArrays:
    """modal_geometry.ChebyshevArrays with device storage."""

    def __init__(self, mapped, band):
        self.multiply = DeviceRealMultiplier(mapped, band)
        one = _delta(band, 2, mapped.device)
        self._arrays = torch.empty((32,)+one.shape, dtype=COMPLEX, device=mapped.device)
        self._arrays[0], self._arrays[1] = one, self.multiply(one)
        self.count = 2
        self._lock = Lock()

    def ensure(self, degree):
        with self._lock:
            if degree >= len(self._arrays):
                grown = torch.empty((max(degree+1, 3*len(self._arrays)//2),)+self._arrays.shape[1:],
                                    dtype=COMPLEX, device=self._arrays.device)
                grown[:self.count] = self._arrays[:self.count]
                self._arrays = grown
            while self.count <= degree:
                n = self.count
                self._arrays[n] = 2*self.multiply(self._arrays[n-1])-self._arrays[n-2]
                self.count += 1
            return self._arrays[:degree+1]

    def combine(self, coefficients):
        arrays = self.ensure(coefficients.shape[1]-1)
        return torch.tensordot(_tensor(coefficients, arrays.device), arrays, dims=([1], [0]))

    @property
    def nbytes(self):
        return self._arrays[:self.count].numel()*16


def log_modulus(ww, band, tolerance=1e-16, max_degree=4000):
    """modal_geometry.log_modulus on the device; same interval rule and certificate."""
    started = perf_counter()
    device = ww.device
    upper = float(ww.abs().sum())
    if not np.isfinite(upper) or upper <= 0 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Positive finite modulus norm and log tolerance required.')
    k = half(ww)
    grid = max(64, next_fast_len(4*k+4))
    spectrum = torch.zeros((grid, grid), dtype=COMPLEX, device=device)
    index = torch.arange(-k, k+1, device=device) % grid
    spectrum[index[:, None], index[None, :]] = ww
    sampled = float(torch.fft.ifftn(spectrum).real.min())*grid*grid
    if not sampled > 0:
        raise ValueError(f'Inconclusive interval proposal: sampled min |W|^2 = {sampled:g}.')
    beta, certificate = sampled/2, None
    for attempt in range(2):
        root_upper, root_lower = np.sqrt(upper), np.sqrt(beta)
        ratio = (root_upper-root_lower)/(root_upper+root_lower)
        degree = 1
        while 2*ratio**(degree+1)/((degree+1)*(1-ratio)) > tolerance:
            degree += 1
            if degree > max_degree:
                raise ValueError(f'log|W|^2 needs more than {max_degree} Chebyshev terms '
                                 f'(beta/Lambda={beta/upper:.3g}); curve is nearly self-touching.')
        mapped = 2*ww/(upper-beta)
        mapped[k, k] -= (upper+beta)/(upper-beta)
        multiply = DeviceRealMultiplier(mapped, band)
        previous = _delta(band, 2, device)
        current = multiply(previous)
        scale = 1/np.sqrt(upper*beta)
        log = 2*np.log((root_upper+root_lower)/2)*previous+2*ratio*current
        inverse = scale*(previous-2*ratio*current)
        for n in range(2, degree+1):
            previous, current = current, 2*multiply(current)-previous
            log += (2*(-1)**(n+1)*ratio**n/n)*current
            inverse += (2*scale*(-ratio)**n)*current
        if attempt:
            break
        product = _convolve(ww, inverse, 2)
        centre = half(product)
        product[centre, centre] -= 1
        residual = float(product.abs().sum())
        norm = float(inverse.abs().sum())
        allowance = 80*product.numel()*EPS*upper*norm
        lower = (1-residual-allowance)/norm
        if not np.isfinite([residual, norm, allowance, lower]).all() or norm <= 0:
            raise ValueError('Non-finite reciprocal residual certificate.')
        certificate = dict(residual=residual, allowance=allowance, reciprocal_l1=norm, lower=lower,
                           arithmetic_verified=False, rounding_model='heuristic FFT allowance')
        if lower >= beta:
            break
        if not lower > 0:
            raise ValueError(f'|W|^2 lower bound not certified (coefficient residual {residual:.3g}).')
        beta = lower
    if not bool(torch.isfinite(log).all()):
        raise ValueError('Non-finite log modulus coefficients.')
    return log, dict(upper=upper, lower=beta, sampled_minimum=sampled, proposal_grid=grid, degree=degree,
                     series_bound=float(2*ratio**(degree+1)/((degree+1)*(1-ratio))),
                     recomputed=bool(attempt), certificate=certificate,
                     meaning='beta <= |W|^2 <= Lambda on the torus; beta from the coefficient residual '
                             'inequality, conditional on a heuristic rounding allowance; not interval verified',
                     seconds=perf_counter()-started)


class DeviceModalGeometry:
    """modal_geometry.ModalGeometry with device operator arrays and CPU wave arrays."""

    def __init__(self, curve, band, *, device='cuda', log_tolerance=1e-16, max_log_degree=4000):
        started = perf_counter()
        z = np.asarray(curve.coefficients, complex)
        k = curve.band
        if band < 1:
            raise ValueError('Coefficient window must be positive.')
        self.coefficients, self.band, self.curve_band, self.device = z, band, k, device
        self.normal = curve.modes*z
        if not float(np.pi*np.sum(curve.modes*np.abs(z)**2)) > 0:
            raise ValueError('Curve must be counterclockwise (positive signed area).')
        coefficients, normal = _tensor(z, device), _tensor(self.normal, device)
        target, source, normal_t, normal_s = torch.zeros((4, 2*k+1, 2*k+1), dtype=COMPLEX, device=device)
        target[:, k], source[k], normal_t[:, k], normal_s[k] = coefficients, coefficients, normal, normal
        difference = target-source
        radius_squared = _real_product(difference, difference, 2)
        self.radial_upper = float(min((2*np.sum(np.abs(np.delete(z, k))))**2, float(radius_squared.abs().sum())))
        mapped = 2*radius_squared/self.radial_upper
        mapped[2*k, 2*k] -= 1
        self.radial = DeviceChebyshevArrays(mapped, band)
        quotient = np.zeros((2*k+1, 2*k+1), complex)
        for j in range(1, k+1):
            r = np.arange(j)
            quotient[k+j-1-r, k+r] += z[k+j]
            quotient[k-1-r, k-j+r] -= z[k-j]
        quotient = _tensor(quotient, device)
        self.log, self.log_interval = log_modulus(_real_product(quotient, quotient, 2), band,
                                                  log_tolerance, max_log_degree)
        self.log_multiplier = DeviceMultiplier(self.log, band)
        self.source_dot = DeviceMultiplier(_real_product(difference, normal_s, 2), band)
        self.normal_dot = DeviceMultiplier(_real_product(normal_t, normal_s, 2), band)
        self.waves = WaveArrays(z, band)
        self.normal_multiplier = Multiplier(self.normal, band, 1)
        self.conjugate_normal_multiplier = Multiplier(reflect(self.normal, 1), band, 1)
        torch.cuda.synchronize(device)
        self.seconds = perf_counter()-started

    def diagnostics(self):
        return dict(window=self.band, curve_band=self.curve_band, radial_upper=self.radial_upper,
                    log_interval=self.log_interval, radial_degree_prepared=self.radial.count-1,
                    wave_arrays=list(self.waves.arrays.shape[:2]), preparation_seconds=self.seconds,
                    device_bytes=int(self.radial.nbytes), boundary_nodes=0, device=str(self.device),
                    boundary_nodes_scope='operator collocation only; interval proposal uses a sampled torus grid')


@lru_cache(maxsize=8)
def assembly_indices(band, cutoff, device_name):
    device = torch.device(device_name)
    modes = torch.arange(-cutoff, cutoff+1, device=device)
    a = torch.arange(-band, band+1, device=device)[None, :]
    b = torch.arange(-2*cutoff, 2*cutoff+1, device=device)[:, None]-a
    ell = torch.arange(-band-cutoff, band+cutoff+1, device=device)
    symbol = torch.where(ell == 0, 0., -1/ell.abs().clamp(min=1).double()).to(COMPLEX)
    m, n = torch.meshgrid(modes, modes, indexing='ij')
    return (modes, a+band, (b+band).clamp(0, 2*band), b.abs()<=band, symbol,
            m+band, band-n, m-n+2*cutoff, m+2*band+cutoff,
            torch.eye(len(modes), dtype=COMPLEX, device=device))


def kernel_matrix(log_part, smooth, cutoff):
    """modal_operator.kernel_matrix on the device."""
    band = half(log_part)
    if cutoff > band:
        raise ValueError('Trace cutoff must fit inside the coefficient window.')
    modes, a, b, mask, symbol, sm, sn, pm, pn, identity = assembly_indices(band, cutoff, str(log_part.device))
    diagonals = torch.where(mask, log_part[a, b], 0)
    product = _convolve(diagonals, symbol[None, :], 1)
    return 2*np.pi*(smooth[sm, sn]+product[pm, pn])


def muller_matrix(geometry, ko, ki, cutoff, *, tolerance=1e-15, timing=None):
    """modal_operator.muller_matrix on the device; returns a host (NumPy) matrix."""
    coefficients, info = radial_coefficients(ko, ki, geometry.radial_upper, tolerance)
    # Scalar coefficient construction is CPU work; measure GPU assembly after it.
    if timing is not None:
        queued = perf_counter()
        torch.cuda.synchronize(geometry.device)
        timing['assembly_gpu_prior_work_wait'] = perf_counter()-queued
        begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        begin.record(torch.cuda.current_stream(geometry.device))
    started = perf_counter()
    p, q, dp, dq, hp, hq = geometry.radial.combine(coefficients)
    q, dq, hq = torch.stack((q, dq, hq))+geometry.log_multiplier(torch.stack((p, dp, hp)))
    k_log, k_smooth = -2*geometry.source_dot(torch.stack((dp, dq)))
    t_log, t_smooth = geometry.normal_dot(torch.stack((hp, hq)))
    v = kernel_matrix(p, q, cutoff)
    k = kernel_matrix(k_log, k_smooth, cutoff)
    modes, *_, identity = assembly_indices(geometry.band, cutoff, str(p.device))
    t = -(modes[:, None]*modes[None, :])*v+kernel_matrix(t_log, t_smooth, cutoff)
    kp = k.flip(0).flip(1).T
    matrix = torch.cat((torch.cat((identity-k, v), 1), torch.cat((-t, identity+kp), 1)), 0)
    if timing is not None:
        end.record(torch.cuda.current_stream(p.device))
        end.synchronize()
        timing['assembly_gpu_execution'] = begin.elapsed_time(end)/1000.
        timing['assembly_gpu_execution_wall'] = perf_counter()-started
    transfer = perf_counter()
    host = matrix.cpu().numpy()
    if timing is not None:
        timing['assembly_host_transfer'] = perf_counter()-transfer
    return host, info
