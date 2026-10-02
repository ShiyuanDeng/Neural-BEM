"""Frequency-independent Laurent geometry for boundary-collocation-free Müller physics.

A curve z(t)=sum_j z_j exp(ijt), in package units, becomes centred coefficient
arrays in w=exp(i theta) (target, first axis) and v=exp(i phi) (source,
second axis). Every product is a padded linear convolution in floating point, projected to the
coefficient window |a|,|b|<=B after each step. Operator arrays never use
boundary samples. A sampled |W|^2 minimum only proposes the interval that the
coefficient residual certificate then accepts or replaces.

Chebyshev recurrences replace power series in R=|z(theta)-z(phi)|^2 and in
|W|^2, W=(z(w)-z(v))/(w-v). See docs/iterations/cleaned_interfaces/
node_free_modal_muller_summary.pdf and node_free_modal_muller_review.md.
"""
from threading import Lock
from time import perf_counter

import numpy as np
from scipy.fft import fftn, ifftn, irfftn, next_fast_len, rfftn
from scipy.signal import fftconvolve

EPS = np.finfo(float).eps


def half(array):
    return (array.shape[-1]-1)//2


def crop(array, band, ndim):
    """Centred crop or zero pad of the last ``ndim`` axes to half-width ``band``."""
    old = half(array)
    if old >= band:
        index = (Ellipsis,)+(slice(old-band, old+band+1),)*ndim
        return array[index].copy()
    return np.pad(array, ((0, 0),)*(array.ndim-ndim)+((band-old, band-old),)*ndim)


def delta(band, ndim):
    one = np.zeros((2*band+1,)*ndim, complex)
    one[(band,)*ndim] = 1
    return one


def reflect(array, ndim):
    """Coefficients of the complex conjugate function: c[-a,-b].conj()."""
    return array[(Ellipsis,)+(slice(None, None, -1),)*ndim].conj()


def real_product(first, second, ndim):
    """Coefficients of Re(first*conj(second)), without truncation."""
    axes = tuple(range(-ndim, 0))
    product = fftconvolve(first, reflect(second, ndim), axes=axes)
    return (product+reflect(product, ndim))/2


class Multiplier:
    """Multiplication by a fixed Laurent polynomial, projected to one window.

    The polynomial is cropped to half-width 2B first. For inputs supported in
    the window this changes nothing that is kept (review Lemma 4). The FFT has
    linear-convolution padding, never circular wraparound.
    """

    def __init__(self, poly, band, ndim=2):
        poly = crop(poly, min(half(poly), 2*band), ndim)
        self.band, self.ndim, self.offset = band, ndim, half(poly)
        self.shape = (next_fast_len(2*band+poly.shape[-1]),)*ndim
        self.axes = tuple(range(-ndim, 0))
        self.transform = fftn(poly, self.shape, axes=self.axes)

    def __call__(self, array, workers=1):
        full = ifftn(fftn(array, self.shape, axes=self.axes, workers=workers)*self.transform,
                     axes=self.axes, workers=workers)
        window = slice(self.offset, self.offset+2*self.band+1)
        return full[(Ellipsis,)+(window,)*self.ndim]


class RealMultiplier:
    """Multiplier for real functions (Hermitian 2-D coefficient arrays).

    Coefficients are placed in wrapped order, so transforms act on real grid
    values: half-spectrum FFTs at half the cost. The grid still has
    linear-convolution size, and the output is exactly Hermitian.
    """

    def __init__(self, poly, band):
        poly = crop(poly, min(half(poly), 2*band), 2)
        self.band = band
        self.size = next_fast_len(2*band+poly.shape[-1])
        self.values = irfftn(self._spectrum(poly), s=(self.size,)*2, axes=(-2, -1))*self.size**2

    def _spectrum(self, array):
        b, n = half(array), self.size
        out = np.zeros(array.shape[:-2]+(n, n//2+1), complex)
        out[..., np.arange(-b, b+1) % n, :b+1] = array[..., :, b:]
        return out

    def __call__(self, array, workers=1):
        n, b = self.size, self.band
        grid = irfftn(self._spectrum(array), s=(n, n), axes=(-2, -1), workers=workers)
        spectrum = rfftn(grid*self.values, axes=(-2, -1), workers=workers)
        right = spectrum[..., np.arange(-b, b+1) % n, :b+1]
        return np.concatenate((right[..., ::-1, :0:-1].conj(), right), axis=-1)


class ChebyshevArrays:
    """Arrays T_n(A)1 for the windowed multiplication A by a real map into [-1,1].

    A is self-adjoint on coefficients, with spectrum inside [-1,1] whenever the
    mapped polynomial is, so every stored array has coefficient L2 norm <=1.
    Arrays are extended on demand and never depend on the wavenumber.
    """

    def __init__(self, mapped, band):
        self.multiply = RealMultiplier(mapped, band)
        one = delta(band, 2)
        self._arrays = np.empty((32,)+one.shape, complex)
        self._arrays[0], self._arrays[1] = one, self.multiply(one)
        self.count = 2
        self._lock = Lock()
        self.seconds = 0.

    def ensure(self, degree, workers=1):
        with self._lock:
            started = perf_counter()
            if degree >= len(self._arrays):
                grown = np.empty((max(degree+1, 3*len(self._arrays)//2),)+self._arrays.shape[1:], complex)
                grown[:self.count] = self._arrays[:self.count]
                self._arrays = grown
            while self.count <= degree:
                n = self.count
                self._arrays[n] = 2*self.multiply(self._arrays[n-1], workers)-self._arrays[n-2]
                self.count += 1
            self.seconds += perf_counter()-started
            return self._arrays[:degree+1]

    def combine(self, coefficients, workers=1):
        """sum_n c[f,n] T_n for each function f; one BLAS contraction."""
        arrays = self.ensure(coefficients.shape[1]-1, workers)
        return np.tensordot(coefficients, arrays, axes=(1, 0))

    @property
    def nbytes(self):
        return self._arrays[:self.count].nbytes


def log_modulus(ww, band, tolerance=1e-16, max_degree=4000, workers=1):
    """Coefficients of log|W|^2 with a residual-based interval [beta, Lambda].

    Lambda is the coefficient triangle bound. beta starts at half the sampled
    minimum. The same Chebyshev arrays also build v ~ 1/|W|^2. If the complete
    (untruncated) product obeys r=||1-|W|^2 v||_1<1, then on the torus
    |W|^2 >= (1-r)/||v||_1. That bound either accepts beta, or replaces it for
    one recomputation that is valid by construction. A regular, simple curve
    has W != 0 everywhere; an inconclusive certificate is refused. The
    inequality is exact arithmetic; the FFT rounding allowance is heuristic,
    not a verified enclosure of all coefficient and convolution errors.
    """
    started = perf_counter()
    upper = float(np.sum(np.abs(ww)))
    if not np.isfinite(upper) or upper <= 0 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Positive finite modulus norm and log tolerance required.')
    k = half(ww)
    grid = max(64, next_fast_len(4*k+4))
    spectrum = np.zeros((grid, grid), complex)
    index = np.arange(-k, k+1) % grid
    spectrum[np.ix_(index, index)] = ww
    sampled = float(np.min(np.real(ifftn(spectrum, workers=workers)))*grid*grid)
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
        multiply = RealMultiplier(mapped, band)
        previous = delta(band, 2)
        current = multiply(previous, workers)
        scale = 1/np.sqrt(upper*beta)
        log = 2*np.log((root_upper+root_lower)/2)*previous+2*ratio*current
        inverse = scale*(previous-2*ratio*current)
        for n in range(2, degree+1):
            previous, current = current, 2*multiply(current, workers)-previous
            log += (2*(-1)**(n+1)*ratio**n/n)*current
            inverse += (2*scale*(-ratio)**n)*current
        if attempt:
            break
        product = fftconvolve(ww, inverse)
        centre = half(product)
        product[centre, centre] -= 1
        residual = float(np.sum(np.abs(product)))
        norm = float(np.sum(np.abs(inverse)))
        # Generous FFT rounding allowance; the inequality itself is exact arithmetic.
        allowance = 80*product.size*EPS*upper*norm
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
    if not np.isfinite(log).all():
        raise ValueError('Non-finite log modulus coefficients.')
    return log, dict(upper=upper, lower=beta, sampled_minimum=sampled, proposal_grid=grid, degree=degree,
                     series_bound=float(2*ratio**(degree+1)/((degree+1)*(1-ratio))),
                     recomputed=bool(attempt), certificate=certificate,
                     meaning='beta <= |W|^2 <= Lambda on the torus; beta from the coefficient residual '
                             'inequality, conditional on a heuristic rounding allowance; not interval verified',
                     seconds=perf_counter()-started)


class WaveArrays:
    """(zeta/rho)^n (|zeta|/rho)^(2p) in a 1-D window, zeta=z-z_0, rho=sum_(j!=0)|z_j|.

    Regular cylindrical waves J_n(k|zeta|)exp(in arg zeta) are weighted sums
    of these frequency-independent arrays. |zeta/rho|<=1 on the whole curve.
    """

    def __init__(self, coefficients, band):
        modes = np.arange(-half(coefficients), half(coefficients)+1)
        zeta = np.where(modes == 0, 0, coefficients)
        self.center = complex(coefficients[half(coefficients)])
        self.radius = float(np.sum(np.abs(zeta)))
        unit = zeta/self.radius
        self.band = band
        self._zeta = Multiplier(unit, band, 1)
        self._modulus = Multiplier(real_product(unit, unit, 1), band, 1)
        self.arrays = np.zeros((0, 0, 2*band+1), complex)
        self._lock = Lock()
        self.seconds = 0.

    def ensure(self, orders, terms, workers=1):
        """Arrays for n<=orders, p<terms; rebuilt (cheaply) only when enlarged."""
        with self._lock:
            have = self.arrays.shape
            if orders < have[0] and terms <= have[1]:
                return self.arrays[:orders+1, :terms]
            started = perf_counter()
            rows, columns = max(orders+1, have[0]), max(terms, have[1])
            arrays = np.empty((rows, columns, 2*self.band+1), complex)
            arrays[0, 0] = delta(self.band, 1)
            for n in range(1, rows):
                arrays[n, 0] = self._zeta(arrays[n-1, 0], workers)
            for p in range(1, columns):
                arrays[:, p] = self._modulus(arrays[:, p-1], workers)
            self.arrays = arrays
            self.seconds += perf_counter()-started
            return arrays[:orders+1, :terms]


class ModalGeometry:
    """Everything the modal operator needs from one curve at one window B."""

    def __init__(self, curve, band, *, log_tolerance=1e-16, max_log_degree=4000, workers=1):
        started = perf_counter()
        z = np.asarray(curve.coefficients, complex)
        k = curve.band
        if band < 1:
            raise ValueError('Coefficient window must be positive.')
        self.coefficients, self.band, self.curve_band = z, band, k
        self.normal = curve.modes*z  # N=-i z', the outward normal times speed
        area = float(np.pi*np.sum(curve.modes*np.abs(z)**2))
        if not area > 0:
            raise ValueError('Curve must be counterclockwise (positive signed area).')
        target, source = np.zeros((2, 2*k+1, 2*k+1), complex)
        target[:, k], source[k] = z, z
        normal_t, normal_s = np.zeros((2, 2*k+1, 2*k+1), complex)
        normal_t[:, k], normal_s[k] = self.normal, self.normal
        difference = target-source
        radius_squared = real_product(difference, difference, 2)
        # R=|z(theta)-z(phi)|^2 lies in [0, upper]; both bounds are rigorous.
        self.radial_upper = float(min((2*np.sum(np.abs(np.delete(z, k))))**2,
                                      np.sum(np.abs(radius_squared))))
        mapped = 2*radius_squared/self.radial_upper
        mapped[2*k, 2*k] -= 1
        self.radial = ChebyshevArrays(mapped, band)
        # W=sum_j z_j (w^j-v^j)/(w-v): support [0,K-1]^2 from j>0 and [-K,-1]^2 from j<0.
        quotient = np.zeros((2*k+1, 2*k+1), complex)
        for j in range(1, k+1):
            r = np.arange(j)
            quotient[k+j-1-r, k+r] += z[k+j]
            quotient[k-1-r, k-j+r] -= z[k-j]
        self.log, self.log_interval = log_modulus(real_product(quotient, quotient, 2), band,
                                                  log_tolerance, max_log_degree, workers)
        self.log_multiplier = Multiplier(self.log, band)
        self.source_dot = Multiplier(real_product(difference, normal_s, 2), band)
        self.normal_dot = Multiplier(real_product(normal_t, normal_s, 2), band)
        self.waves = WaveArrays(z, band)
        self.normal_multiplier = Multiplier(self.normal, band, 1)
        self.conjugate_normal_multiplier = Multiplier(reflect(self.normal, 1), band, 1)
        self.seconds = perf_counter()-started

    def diagnostics(self):
        return dict(window=self.band, curve_band=self.curve_band, radial_upper=self.radial_upper,
                    log_interval=self.log_interval, radial_degree_prepared=self.radial.count-1,
                    wave_arrays=list(self.waves.arrays.shape[:2]), preparation_seconds=self.seconds,
                    stored_bytes=int(self.radial.nbytes+self.waves.arrays.nbytes), boundary_nodes=0,
                    boundary_nodes_scope='operator collocation only; interval proposal uses a sampled torus grid')
