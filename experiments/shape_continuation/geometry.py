"""Cartesian Fourier storage; arclength is a gauge, not a radial constraint."""
from dataclasses import dataclass
import operator

import numpy as np
from scipy.interpolate import CubicSpline

from ordered_boundary import PeriodicCurve2D, sampled_self_intersection_count


def integer(value, name, minimum=1):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    value = operator.index(value)
    if value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return value


def grid_size(band):
    return 2 ** int(np.ceil(np.log2(max(1024, 16 * (2 * band + 1)))))


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
        if curve.signed_area <= 0 or np.min(curve.speeds) < 1e-6 * np.mean(curve.speeds):
            raise ValueError("Curve must be regular and counterclockwise.")
        if sampled_self_intersection_count(curve.points):
            raise ValueError("Curve self-intersects.")
        return curve


def arclength_angles(curve):
    """Normalized arclength at the supplied uniform parameter nodes."""
    theta = np.r_[curve.parameters, 2 * np.pi]
    speed = np.r_[curve.speeds, curve.speeds[0]]
    primitive = CubicSpline(theta, speed, bc_type="periodic").antiderivative()
    distance = primitive(theta) - primitive(0)
    if np.any(np.diff(distance) <= 0):
        raise ValueError("Non-monotone arclength map.")
    return 2 * np.pi * distance[:-1] / distance[-1], float(distance[-1])


def reparameterize(curve, band, *, tolerance=1e-7):
    """Refit uniform-arclength samples; refuse excessive Cartesian truncation."""
    count = grid_size(max(curve.band, band))
    nodes = curve.nodes(count)
    angles, _ = arclength_angles(nodes)
    inverse = CubicSpline(np.r_[angles, 2 * np.pi], np.r_[nodes.parameters, 2 * np.pi])
    theta = inverse(nodes.parameters)
    periodic = CubicSpline(np.r_[nodes.parameters, 2 * np.pi],
                           np.r_[curve.values(count), curve.values(count)[0]], bc_type="periodic")
    target = periodic(theta)
    result = FourierCurve.from_samples(target, band)
    error = float(np.max(np.abs(result.values(count) - target)))
    scale = nodes.perimeter / (2 * np.pi)
    if error > tolerance * scale:
        raise ValueError(f"Arclength projection unresolved: {error / scale:.3g} relative.")
    result.validate()
    return result, error


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


def displaced(curve, coefficients, storage_band, *, filter_index=0, step=1.0,
              projection_tolerance=1e-7):
    """Normal update, optional eq. 19 filter of Cartesian displacement, refit."""
    coefficients = np.asarray(coefficients, float)
    if coefficients.ndim != 1 or len(coefficients) % 2 != 1 or not np.isfinite(coefficients).all():
        raise ValueError("Expected finite real normal Fourier coefficients.")
    count = grid_size(max(curve.band, storage_band, len(coefficients) // 2))
    nodes = curve.nodes(count)
    normal = nodes.normals[:, 0] + 1j * nodes.normals[:, 1]
    delta = (normal_basis(nodes, len(coefficients) // 2) @ coefficients) * normal * step
    if filter_index:
        sigma = 10.0 ** (1 - filter_index)
        modes = np.fft.fftfreq(count) * count
        delta = np.fft.ifft(np.fft.fft(delta) * np.exp(-(modes / (sigma * storage_band)) ** 2))
    # Keep the product h*n well resolved before changing its parameterization.
    updated = FourierCurve.from_samples(curve.values(count) + delta, count // 2 - 1)
    # Avoid oversampling this already dense temporary Fourier interpolant.
    return _refit_samples(updated, storage_band, count, projection_tolerance)


def _refit_samples(curve, band, count, tolerance):
    nodes = curve.nodes(count)
    if nodes.signed_area <= 0 or np.min(nodes.speeds) < 1e-6 * np.mean(nodes.speeds):
        raise ValueError("Invalid displaced curve.")
    if sampled_self_intersection_count(nodes.points):
        raise ValueError("Displaced curve self-intersects.")
    angles, _ = arclength_angles(nodes)
    inverse = CubicSpline(np.r_[angles, 2 * np.pi], np.r_[nodes.parameters, 2 * np.pi])
    z = curve.values(count)
    interpolant = CubicSpline(np.r_[nodes.parameters, 2 * np.pi], np.r_[z, z[0]], bc_type="periodic")
    target = interpolant(inverse(nodes.parameters))
    result = FourierCurve.from_samples(target, band)
    error = float(np.max(np.abs(result.values(count) - target)))
    if error > tolerance * nodes.perimeter / (2 * np.pi):
        raise ValueError("Updated curve exceeds the Cartesian projection tolerance.")
    result.validate()
    return result, error
