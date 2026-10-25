"""Cartesian Fourier storage; arclength is a gauge, not a radial constraint."""
from .. import checks
from dataclasses import dataclass
import operator

import numpy as np
from scipy.interpolate import CubicSpline

from ordered_boundary import PeriodicCurve2D


def integer(value, name, minimum=1):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    value = operator.index(value)
    if value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return value


def grid_size(band):
    return 2 ** int(np.ceil(np.log2(max(1024, 16 * (2 * band + 1)))))


def values(coefficients, count):
    """Evaluate centred Fourier coefficients, including columns of derivatives."""
    band = len(coefficients)//2
    spectrum = np.zeros((count,) + coefficients.shape[1:], complex)
    spectrum[np.arange(-band, band+1) % count] = coefficients
    return np.fft.ifft(spectrum, axis=0)*count


def signed_area(coefficients):
    """Signed area of the continuous Fourier curve, computed from coefficients."""
    modes = np.arange(-(len(coefficients)//2), len(coefficients)//2+1)
    return float(np.pi*np.sum(modes*np.abs(coefficients)**2))


def speed_ratio(curve):
    speeds = curve.nodes(grid_size(curve.band)).speeds
    return float(np.max(speeds)/np.min(speeds))


def resize(curve, band):
    """Exact centred coefficient crop/pad, without arclength refitting."""
    if band < curve.band:
        return FourierCurve(curve.coefficients[curve.band-band:curve.band+band+1])
    return FourierCurve(np.pad(curve.coefficients, (band-curve.band,)*2))


def cleanup(curve, retained_band=64, storage_band=192):
    """Crop Cartesian coefficients, then zero-pad; invoked by the policy."""
    return resize(resize(curve, retained_band), storage_band)


@dataclass(frozen=True)
class FourierCurve:
    """Physical complex coefficients ordered -K,...,K; no conjugacy constraint."""
    coefficients: np.ndarray

    def __post_init__(self):
        c = np.array(self.coefficients, dtype=complex, copy=True)
        if c.ndim != 1 or len(c) < 3 or len(c) % 2 != 1 or not np.isfinite(c).all():
            raise ValueError("Expected finite complex coefficients for modes -K,...,K.")
        c.setflags(write=False)
        object.__setattr__(self, "coefficients", c)

    @property
    def band(self):
        return len(self.coefficients) // 2

    @property
    def modes(self):
        return np.arange(-self.band, self.band + 1)

    @classmethod
    def circle(cls, radius=1.0, center=0j):
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError("radius must be positive.")
        return cls(np.array([0j, center, radius]))

    @classmethod
    def from_samples(cls, points, band):
        band = integer(band, "band")
        z = np.asarray(points, complex)
        if z.ndim != 1 or len(z) <= 2 * band or not np.isfinite(z).all():
            raise ValueError("Samples must resolve the requested Fourier band.")
        spectrum = np.fft.fft(z) / len(z)
        return cls(spectrum[np.arange(-band, band + 1) % len(z)])

    def values(self, count, derivative=0):
        count = integer(count, "count")
        if count <= 2 * self.band:
            raise ValueError("Node count must exceed twice the stored curve band.")
        spectrum = np.zeros(count, complex)
        spectrum[self.modes % count] = self.coefficients * (1j * self.modes) ** derivative
        return np.fft.ifft(spectrum) * count

    def nodes(self, count):
        jets = [self.values(count, j) for j in range(4)]
        return PeriodicCurve2D(
            "continuation-boundary", 2 * np.pi * np.arange(count) / count,
            *[np.column_stack((v.real, v.imag)) for v in jets],
        )

    def validate(self):
        # Sampled feasibility, not a certificate between arbitrary sample points.
        curve = self.nodes(grid_size(self.band))
        checks.require_sampled_stored_curve(curve)
        return curve


def arclength_angles(curve):
    """Normalized arclength at the supplied uniform parameter nodes."""
    count = curve.num_nodes
    modes = np.fft.fftfreq(count) * count
    speed = np.fft.fft(curve.speeds) / count
    primitive = np.zeros(count, complex)
    primitive[1:] = speed[1:] / (1j * modes[1:])
    oscillation = (np.fft.ifft(primitive) * count).real
    distance = speed[0].real * curve.parameters + oscillation - oscillation[0]
    length = 2 * np.pi * speed[0].real
    checks.require_arclength_monotone(np.diff(np.r_[distance, length]))
    return 2 * np.pi * distance / length, float(length)


def normal_basis(curve, band):
    band = integer(band, "update band", minimum=0)
    angles, _ = arclength_angles(curve)
    phase = angles[:, None] * np.arange(1, band + 1)
    return np.column_stack((np.ones(len(angles)), np.cos(phase), np.sin(phase)))


def curvature_tail(curve, band):
    """Fraction of arclength curvature energy above |mode|=band (eq. 13)."""
    nodes = curve.nodes(grid_size(max(curve.band, band)))
    angles, _ = arclength_angles(nodes)
    curvature = CubicSpline(np.r_[angles, 2 * np.pi],
                            np.r_[nodes.curvatures, nodes.curvatures[0]], bc_type="periodic")
    spectrum = np.fft.fft(curvature(nodes.parameters)) / nodes.num_nodes
    modes = np.fft.fftfreq(nodes.num_nodes) * nodes.num_nodes
    energy = np.abs(spectrum) ** 2
    return float(np.sum(energy[np.abs(modes) > band]) / np.sum(energy))
