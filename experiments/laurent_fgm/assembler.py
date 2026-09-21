"""Hybrid analytic/spectral Fourier-Galerkin Muller assembly.

This is the construction recommended in the 2026-09-18 Laurent report, stage 2:

    A = A_universal_sing + A_smooth

The universal log symbol log(4 sin^2((t-s)/2)) has exact Fourier coefficients
L_l = -1/|l|, and the smooth two-variable amplitudes are sampled on an
oversampled tensor grid and transformed with FFTs.  Amplitudes are evaluated in
closed form from Hankel/Bessel functions, so unlike the power-series assembler
in ``experiments/modal_muller_research`` there is no high-frequency series
cancellation and kD = 30 is reachable.

Normalisation follows ``coefficient_operator.kernel_matrix`` exactly:

    A_mn = 2*pi * ( Shat[m, -n] + sum_l L_l * Phat[m-l, l-n] )

with ``f(t,s) = sum_ab c_ab e^{i a t} e^{i b s}`` and array index ``[a+B, b+B]``.
The half-shifted trial grid keeps t != s on every sample, so no diagonal limit
is ever evaluated.

Blocks reproduce the Muller flux system of ``CoefficientGeometry.assemble``:
state (u, J d_n u), matrix [[I-K, V], [-T, I+K']], T built through the Maue
identity before truncation.  ``kernel_matrix`` is imported read-only from the
hash-pinned research package; nothing here modifies it.
"""
from time import perf_counter

import numpy as np
from scipy.special import hankel1, jv

from experiments.modal_muller_research.coefficient_operator import kernel_matrix


def curve_values(coefficients, t):
    """z(t) and the normal-times-speed N = -i z'(t) = sum_j j z_j e^{ijt}."""
    z = np.zeros_like(t, dtype=complex)
    n = np.zeros_like(t, dtype=complex)
    for j, value in coefficients.items():
        phase = np.exp(1j * j * t)
        z += value * phase
        n += j * value * phase
    return z, n


def spectrum(array, bandwidth, shift):
    """Fourier coefficients c_ab of f = sum c_ab e^{iat} e^{ibs} on [-B,B]^2.

    ``shift`` is the trial-grid offset in units of the grid step, undone here.
    """
    grid = array.shape[0]
    coefficients = np.fft.fft2(array) / grid**2
    index = np.arange(-bandwidth, bandwidth + 1)
    picked = coefficients[np.ix_(index % grid, index % grid)]
    return picked * np.exp(-2j * np.pi * shift * index / grid)[None, :]


class FourierGalerkinMuller:
    """Exact Fourier-Galerkin Muller operator by analytic split plus FFT.

    ``coefficients`` maps Laurent index j to z_j for z(t) = sum_j z_j e^{ijt};
    the curve is used in physical units and wavenumbers are physical.
    """

    def __init__(self, coefficients, grid=512, bandwidth=None):
        started = perf_counter()
        self.coefficients = {int(j): complex(v) for j, v in coefficients.items()}
        self.grid = int(grid)
        self.bandwidth = self.grid // 2 - 1 if bandwidth is None else int(bandwidth)
        if 2 * self.bandwidth + 1 > self.grid:
            raise ValueError('Bandwidth must fit the aliasing-free DFT range.')
        step = 2 * np.pi / self.grid
        self.shift = 0.5
        test = step * np.arange(self.grid)
        trial = step * (np.arange(self.grid) + self.shift)
        zt, nt = curve_values(self.coefficients, test)
        zs, ns = curve_values(self.coefficients, trial)
        delta = zt[:, None] - zs[None, :]
        self.radius = np.abs(delta)
        self.source_dot = (delta * ns[None, :].conj()).real
        self.target_dot = (delta * nt[:, None].conj()).real
        self.normal_dot = (nt[:, None] * ns[None, :].conj()).real
        difference = test[:, None] - trial[None, :]
        self.log_symbol = np.log(4 * np.sin(difference / 2)**2)
        self.setup_seconds = perf_counter() - started

    def _amplitudes(self, wave):
        """Log amplitude and full value of G, dG/d(R^2) and k^2 G at one k."""
        argument = wave * self.radius
        h0, h1 = hankel1(0, argument), hankel1(1, argument)
        j0, j1 = jv(0, argument), jv(1, argument)
        green = .25j * h0
        green_log = -j0 / (4 * np.pi)
        derivative = -.125j * wave * h1 / self.radius
        derivative_log = wave * j1 / (8 * np.pi * self.radius)
        return (green, green_log, derivative, derivative_log,
                wave**2 * green, wave**2 * green_log)

    def blocks(self, k_exterior, k_interior):
        """Smooth/log amplitude pairs for V, K, K' and the Maue remainder."""
        outer = self._amplitudes(k_exterior)
        inner = self._amplitudes(k_interior)
        g, gl, d, dl, h, hl = (a - b for a, b in zip(outer, inner))
        return dict(v=(g, gl),
                    k=(d * (-2 * self.source_dot), dl * (-2 * self.source_dot)),
                    kp=(d * (2 * self.target_dot), dl * (2 * self.target_dot)),
                    t2=(h * self.normal_dot, hl * self.normal_dot))

    def assemble(self, k_exterior, k_interior, cutoff):
        started = perf_counter()
        if cutoff > self.bandwidth:
            raise ValueError('Trace cutoff must fit the coefficient bandwidth.')
        pieces = {}
        for name, (full, log_amplitude) in self.blocks(k_exterior, k_interior).items():
            smooth = full - log_amplitude * self.log_symbol
            pieces[name] = kernel_matrix(
                spectrum(log_amplitude, self.bandwidth, self.shift),
                spectrum(smooth, self.bandwidth, self.shift), cutoff)
        modes = np.arange(-cutoff, cutoff + 1)
        identity = np.eye(len(modes))
        t = -modes[:, None] * modes[None, :] * pieces['v'] + pieces['t2']
        matrix = np.block([[identity - pieces['k'], pieces['v']],
                           [-t, identity + pieces['kp']]])
        return matrix, dict(assembly_seconds=perf_counter() - started,
                            setup_seconds=self.setup_seconds, grid=self.grid,
                            coefficient_bandwidth=self.bandwidth, trace_cutoff=cutoff,
                            blocks={name: value for name, value in pieces.items()})


def point_source_traces(coefficients, points, wave, cutoff, grid=512, strengths=1.):
    """Modal (u, J d_n u) traces of incident point sources, by FFT on the grid."""
    t = 2 * np.pi * np.arange(grid) / grid
    z, n = curve_values(coefficients, t)
    points = np.asarray(points, dtype=float)
    p = points[:, 0] + 1j * points[:, 1]
    delta = z[:, None] - p[None, :]
    radius = np.abs(delta)
    value = .25j * hankel1(0, wave * radius)
    # d_n u * J = Re[(x-p).n] * (dG/dR^2) * 2, with N = n*J already in `n`.
    flux = (-.25j * wave * hankel1(1, wave * radius) / radius) * (
        delta * n[:, None].conj()).real
    index = np.arange(-cutoff, cutoff + 1) % grid
    modal_value = np.fft.fft(value, axis=0)[index] / grid
    modal_flux = np.fft.fft(flux, axis=0)[index] / grid
    return np.concatenate((modal_value, modal_flux), axis=0) * np.asarray(strengths)


def receiver_operator(coefficients, points, wave, cutoff, grid=512):
    """Row operator mapping modal traces to scattered field at receiver points.

    u^s(r) = int [ d_n G(r,y) u(y) - G(r,y) J d_n u(y) ] dt, exterior points.
    """
    t = 2 * np.pi * np.arange(grid) / grid
    z, n = curve_values(coefficients, t)
    points = np.asarray(points, dtype=float)
    p = points[:, 0] + 1j * points[:, 1]
    delta = z[None, :] - p[:, None]
    radius = np.abs(delta)
    green = .25j * hankel1(0, wave * radius)
    normal = (-.25j * wave * hankel1(1, wave * radius) / radius) * (
        delta * n[None, :].conj()).real
    modes = np.arange(-cutoff, cutoff + 1)
    basis = np.exp(1j * modes[None, :] * t[:, None])
    weight = 2 * np.pi / grid
    return np.concatenate((normal @ basis, -green @ basis), axis=1) * weight
