"""NU-002 spectral arclength reparameterization (compass eq. 9) and its shape audit.

For a Laurent curve z(theta) with speed sigma=|z'| and normalized arclength
alpha(theta) = theta + eta(theta), alpha' = sigma/sigma_0, the arclength curve
z~(alpha) = z(theta(alpha)) has Fourier coefficients

    z~_k = <z(theta) alpha'(theta) e^{-i k alpha(theta)}>_0          (change of variables)

which is eq. 9 before its integration by parts (Koga 2021, eq. 3.6). The mean
is a trapezoid sum on a uniform theta grid used only as a quadrature engine:
no interpolation, no inversion theta(alpha), no composition. The integrand is
analytic, so the sum converges geometrically; the grid is doubled until two
successive results agree.

By Lemma 2 the arclength curve of a non-circle is not band-limited. Cropping
z~ to the storage band K therefore changes the SHAPE by the discarded tail.
``shape_distance`` measures that change exactly (Newton projection of the new
curve's samples onto the old curve), so a reset can be refused when the crop
would move the shape by more than a tolerance.

Campaigns and diagnostics remain under experiments.cleaned_interface.
"""
import numpy as np
from .continuation.geometry import FourierCurve


def _evaluate(coefficients, count, derivative=0):
    K = len(coefficients)//2
    modes = np.arange(-K, K+1)
    spectrum = np.zeros(count, complex)
    spectrum[modes % count] = coefficients*(1j*modes)**derivative
    return np.fft.ifft(spectrum)*count


def normalized_arclength(coefficients, count):
    """alpha(theta_i), alpha'(theta_i) and sigma_0 on a uniform grid of ``count`` nodes (alpha(0)=0)."""
    sigma = np.abs(_evaluate(coefficients, count, 1))
    spectrum = np.fft.fft(sigma)/count
    mean = spectrum[0].real
    modes = np.fft.fftfreq(count)*count
    primitive = np.zeros(count, complex)
    primitive[1:] = spectrum[1:]/(1j*modes[1:])
    eta = (np.fft.ifft(primitive)*count).real/mean
    theta = 2*np.pi*np.arange(count)/count
    return theta+eta-eta[0], sigma/mean, mean


def arclength_coefficients(coefficients, band, count):
    """z~_k for |k| <= band by the change-of-variables quadrature on ``count`` nodes."""
    alpha, slope, _ = normalized_arclength(coefficients, count)
    weighted = _evaluate(coefficients, count)*slope
    k = np.arange(-band, band+1)
    # Direct sum (band x count); band <= 192 and count <= 2^16 keep this small.
    return np.exp(-1j*np.outer(k, alpha))@weighted/count


def reparameterize(coefficients, band=None, *, tolerance=1e-13, start=None, max_count=2**17):
    """Arclength coefficients cropped to ``band`` (default: input band).

    Returns (coefficients, info). ``info['quadrature_change']`` is the l1
    difference between the last two grid doublings relative to ||z||_1.
    """
    z = np.asarray(coefficients, complex)
    K = len(z)//2
    band = K if band is None else int(band)
    count = start or int(2**np.ceil(np.log2(max(256, 8*(max(K, band)+1)))))
    previous = arclength_coefficients(z, band, count)
    scale = float(np.sum(np.abs(z)))
    while True:
        count *= 2
        current = arclength_coefficients(z, band, count)
        change = float(np.sum(np.abs(current-previous)))/scale
        if change <= tolerance or count >= max_count:
            break
        previous = current
    return current, dict(count=count, quadrature_change=change, converged=change <= tolerance)


def speed_ratio(coefficients, count=None):
    K = len(coefficients)//2
    count = count or int(2**np.ceil(np.log2(max(1024, 32*(K+1)))))
    s = np.abs(_evaluate(np.asarray(coefficients, complex), count, 1))
    return float(np.max(s)/np.min(s))


def _point(coefficients, theta, derivative=0):
    K = len(coefficients)//2
    modes = np.arange(-K, K+1)
    return np.exp(1j*np.outer(theta, modes))@(coefficients*(1j*modes)**derivative)


def shape_distance(old, new, samples=4096, newton=8):
    """max_i dist(new(t_i), old curve), by nearest sample then Newton on theta (exact Fourier)."""
    old = np.asarray(old, complex)
    new = np.asarray(new, complex)
    t = 2*np.pi*np.arange(samples)/samples
    points = _point(new, t)
    dense = 8*samples
    grid = 2*np.pi*np.arange(dense)/dense
    reference = _evaluate(old, dense)
    theta = np.empty(samples)
    for start in range(0, samples, 512):
        block = points[start:start+512]
        theta[start:start+512] = grid[np.argmin(np.abs(block[:, None]-reference[None, :]), axis=1)]
    for _ in range(newton):
        r = _point(old, theta)-points
        d1, d2 = _point(old, theta, 1), _point(old, theta, 2)
        grad = (np.conj(r)*d1).real
        hess = (np.abs(d1)**2+(np.conj(r)*d2).real)
        theta = theta-grad/np.where(hess > 0, hess, 1.)
    return float(np.max(np.abs(_point(old, theta)-points)))


def mean_radius(coefficients):
    _, _, mean = normalized_arclength(np.asarray(coefficients, complex), 4096)
    return float(mean)


def reset(curve, *, shape_tolerance):
    """Arclength reset at the curve's own band; refuses (returns None) if the crop moves the shape.

    ``shape_tolerance`` is relative to sigma_0 = L/(2 pi). Returns (FourierCurve | None, info).
    """
    z = curve.coefficients
    new, info = reparameterize(z)
    radius = mean_radius(z)
    distance = shape_distance(z, new)/radius
    info.update(shape_relative=distance, speed_ratio_before=speed_ratio(z), speed_ratio_after=speed_ratio(new),
                accepted=bool(info['converged'] and distance <= shape_tolerance))
    return (FourierCurve(new) if info['accepted'] else None), info
