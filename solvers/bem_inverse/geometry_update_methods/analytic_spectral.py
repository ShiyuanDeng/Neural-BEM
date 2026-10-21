"""Analytic derivative of the complete discrete spectral geometry update.

Preparation differentiates speed, its normalized arclength primitive, the
quadrature weight and the phase. The finite trial is the sampled spectral
method in ``spectral.geometry_update``; no validity certificate is used here.
"""
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from .. import checks
from ..continuation.geometry import (FourierCurve, arclength_angles, grid_size,
                                     integer, normal_basis, reparameterize, values)
from ..errors import refusal_from_value_error
from .spectral import Grid, push_and_refit, sample_grid, geometry_update as spectral_geometry_update


@dataclass(frozen=True)
class Prepared:
    """Analytic projection derivative and reusable base data for one curve."""
    curve: FourierCurve
    update_modes: int
    curve_modes: int
    length_unit_m: float
    orders: np.ndarray
    labels: tuple
    derivatives: np.ndarray
    base_projection: np.ndarray
    fine_base_projection: np.ndarray
    count: int
    preparation_seconds: float
    grid: Grid
    fine_grid: Grid


def projection_derivatives(curve, update_modes, band, count, length_unit_m):
    """Return d R(curve + h*n)/da at zero, coefficients by coordinate, per metre."""
    nodes = curve.nodes(count)
    normal = nodes.normals @ np.array([1, 1j])
    directions = normal_basis(nodes, update_modes)*normal[:, None]/length_unit_m
    modes = np.fft.fftfreq(count)*count
    spectrum = np.fft.fft(directions, axis=0)/count
    # Exactly the band kept by from_samples, including both omitted modes on
    # odd diagnostic grids (production grid_size always returns an even size).
    spectrum[np.abs(np.rint(modes)) > count//2-1] = 0
    dz = np.fft.ifft(spectrum, axis=0)*count
    dz_prime = np.fft.ifft(spectrum*(1j*modes[:, None]), axis=0)*count

    # Reproduce the zero-step FFT fit before differentiating its speed/map.
    moved = FourierCurve.from_samples(curve.values(count), count//2-1)
    base = moved.nodes(count)
    z, z_prime = moved.values(count), moved.values(count, 1)
    sigma = base.speeds
    if checks.irregular_projection_derivative(sigma):
        raise ValueError('Projection derivative requires a regular curve.')
    alpha, length = arclength_angles(base)
    mean = length/(2*np.pi)
    dsigma = (np.conj(z_prime)[:, None]*dz_prime).real/sigma[:, None]
    dspectrum = np.fft.fft(dsigma, axis=0)/count
    dmean = dspectrum[0].real
    primitive = np.zeros_like(dspectrum)
    primitive[1:] = dspectrum[1:]/(1j*modes[1:, None])
    oscillation = (np.fft.ifft(primitive, axis=0)*count).real
    ddistance = base.parameters[:, None]*dmean+oscillation-oscillation[0]
    dalpha = (ddistance-alpha[:, None]*dmean)/mean
    weights = z*sigma/mean
    dweights = (dz*sigma[:, None]+z[:, None]*dsigma)/mean-weights[:, None]*dmean/mean

    orders = np.arange(-band, band+1)
    out = np.empty((len(orders), 2*update_modes+1), complex)
    for start in range(0, len(orders), 32):
        k = orders[start:start+32, None]
        phase = np.exp(-1j*k*alpha)
        out[start:start+32] = (phase@dweights-1j*k*(phase@(weights[:, None]*dalpha)))/count
    if checks.nonfinite_projection_derivative(out):
        raise ValueError('Non-finite projection derivative.')
    return out


class AnalyticSpectralUpdate:
    """Analytic preparation with the same finite map as sampled spectral."""
    name = 'centred_state_band_spectral_projection'

    def __init__(self, length_unit_m, *, projection_tolerance=1e-5,
                 derivative_step_m=1e-7, window=64, shadow=False,
                 order='certificate_first'):
        if window != 64 or shadow or order != 'certificate_first':
            raise ValueError('Certificate settings require the certified_spectral method.')
        if not np.isfinite(length_unit_m) or length_unit_m <= 0:
            raise ValueError('length_unit_m must be positive.')
        if not np.isfinite(projection_tolerance) or projection_tolerance <= 0:
            raise ValueError('projection_tolerance must be positive.')
        self.length_unit_m = float(length_unit_m)
        self.projection_tolerance = float(projection_tolerance)
        self.derivative_step_m = float(derivative_step_m)
        checks.require_derivative_step(self.derivative_step_m)
        self.counts = dict(preparations=0, geometry_projections=0, trial_constructions=0,
            refused_trials=0, preparation_seconds=0., trial_seconds=0.,
            sampled_seconds=0., projection_seconds=0.)
        self.last_trial = {}

    def settings(self):
        return dict(name=self.name, length_unit_m=self.length_unit_m,
            projection_tolerance=self.projection_tolerance, derivative_step_m=None,
            coordinates='real Fourier coefficients of normal distance h (m) in normalized arclength',
            gauge='arclength refit on every trial',
            construction='z + P_K[R(z+h*n)-R(z)], analytic derivative of discrete quadrature',
            derivative='analytic derivative of discrete quadrature (NF-001; experimental)',
            projection_tolerance_meaning='grid refinement, not intentional smoothing',
            resampler='eq. 9 quadrature on the uniform grid (count and 2*count); no splines',
            boundary_samples=True, projection_error_control='coarse/fine diagnostic; not a rigorous bound',
            validity='coefficient area, sampled speed and sampled segment intersections',
            sampled_validity_fallback=False)

    def prepare(self, curve, update_modes, curve_modes):
        started = perf_counter()
        update_modes = integer(update_modes, 'update_modes', minimum=0)
        integer(curve_modes, 'curve_modes')
        if curve.band != curve_modes:
            raise ValueError('The accepted curve must already use the stage storage band.')
        harmonics = np.arange(1, update_modes+1)
        orders = np.concatenate(([0], harmonics, harmonics))
        labels = ('a0', *[f'a{m}' for m in harmonics], *[f'b{m}' for m in harmonics])
        count = grid_size(max(curve_modes, update_modes))
        zeros = np.zeros(len(orders))
        grid, fine_grid = sample_grid(curve, count, update_modes), sample_grid(curve, 2*count, update_modes)
        base = push_and_refit(grid, zeros, curve_modes, self.length_unit_m)[0]
        fine = push_and_refit(fine_grid, zeros, curve_modes, self.length_unit_m)[0]
        derivatives = projection_derivatives(curve, update_modes, curve_modes, count, self.length_unit_m)
        elapsed = perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['geometry_projections'] += 2
        self.counts['preparation_seconds'] += elapsed
        return Prepared(curve, update_modes, curve_modes, self.length_unit_m, orders, labels,
                        derivatives, base, fine, count, elapsed, grid, fine_grid)

    def regauge(self, curve, curve_modes):
        integer(curve_modes, 'curve_modes')
        try:
            shape, error = reparameterize(curve, curve_modes, tolerance=self.projection_tolerance)
        except ValueError as exc:
            raise refusal_from_value_error(exc) from exc
        return shape, float(error)

    @staticmethod
    def _checked(space, coefficients):
        a = np.asarray(coefficients, float)
        if a.shape != (len(space.orders),) or not np.isfinite(a).all():
            raise ValueError(f'Expected {len(space.orders)} finite update coefficients.')
        return a

    def velocities(self, space, nodes):
        vectors = values(space.derivatives, nodes.num_nodes)
        normal = nodes.normals @ np.array([1, 1j])
        return (vectors*np.conj(normal[:, None])).real

    def measure(self, space, coefficients):
        a = self._checked(space, coefficients)
        nodes = space.curve.nodes(space.count)
        displacement = self.velocities(space, nodes) @ a * self.length_unit_m
        weights = nodes.arc_length_weights/nodes.perimeter
        return dict(maximum_normal_m=float(np.max(np.abs(displacement))),
                    rms_normal_m=float(np.sqrt(weights @ displacement**2)))

    def metric(self, space, kind, smoothing_m=None):
        if kind != 'mass':
            raise ValueError('Analytic projection only implements the complete physical mass metric.')
        nodes = space.curve.nodes(space.count)
        basis = self.velocities(space, nodes)*self.length_unit_m
        return basis.T @ ((nodes.arc_length_weights/nodes.perimeter)[:, None]*basis)

    def geometry_update(self, normal_update, *, prepared):
        return geometry_update(normal_update, prepared=prepared, settings=self)

    def trial(self, space, coefficients):
        """Compatibility entry point for older callers."""
        return self.geometry_update(coefficients, prepared=space)


def geometry_update(normal_update, *, prepared, settings):
    """Use the sampled spectral trial; only its prepared derivative differs.

    ``spectral.geometry_update`` constructs both moved curves, projects them in
    arclength, checks grid agreement, and checks area, speed and intersections
    of the stored candidate.
    """
    return spectral_geometry_update(normal_update, prepared=prepared, settings=settings)
