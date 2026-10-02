"""Experimental exact derivative of the NU-003 discrete quadrature trial.

For R_k = mean(z sigma / mean(sigma) exp(-ik alpha)), differentiate
the speed, its normalized spectral primitive, the weight AND the phase.
The displacement is projected through the same Nyquist removal as the finite
trial. This differentiates the quadrature actually computed, not a continuum
integration-by-parts approximation. It does not remove quadrature nodes.
"""
import time

import numpy as np

from experiments.shape_continuation.geometry import FourierCurve, arclength_angles, grid_size, normal_basis
from experiments.shape_continuation.updates import BorgesUpdate
from .nu003 import spectral_project
from .nu005 import CertifiedSpace, CertifiedSpectralUpdate


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
    if not np.all(np.isfinite(sigma)) or np.min(sigma) <= 0:
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
    if not np.isfinite(out).all():
        raise ValueError('Non-finite projection derivative.')
    return out


class AnalyticSpectralUpdate(CertifiedSpectralUpdate):
    """Opt-in analytic quadrature tangent; the NU-005 finite trial is unchanged."""

    def settings(self):
        return dict(super().settings(), derivative_step_m=None,
                    derivative='analytic derivative of discrete quadrature (NF-001; experimental)',
                    construction='z + P_K[R(z+h*n)-R(z)], analytic derivative of discrete quadrature')

    def prepare(self, curve, update_modes, curve_modes):
        started = time.perf_counter()
        plain = BorgesUpdate.prepare(self, curve, update_modes, curve_modes)
        count = grid_size(max(curve_modes, update_modes))
        zeros = np.zeros(len(plain.orders))
        base = spectral_project(curve, zeros, curve_modes, count, self.length_unit_m)[0]
        fine = spectral_project(curve, zeros, curve_modes, 2*count, self.length_unit_m)[0]
        derivatives = projection_derivatives(curve, update_modes, curve_modes, count, self.length_unit_m)
        elapsed = time.perf_counter()-started
        self.counts['preparations'] += 1
        self.counts['geometry_projections'] += 2
        self.counts['preparation_seconds'] += elapsed
        return CertifiedSpace(**plain.__dict__, derivatives=derivatives, base_projection=base,
                              fine_base_projection=fine, count=count, preparation_seconds=elapsed)
