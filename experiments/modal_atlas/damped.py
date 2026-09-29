"""Complex-frequency (damped, Laplace-Fourier) forward solves and linearization horizons.

A time-domain trace damped by exp(-alpha t) has Fourier transform at the complex
angular frequency omega + i alpha. Every wavenumber scales by the same complex
factor, so k_e -> k_e (1 + i alpha/omega) and k_i = k_e sqrt(contrast) keeps
the known contrast. The scattering poles lie in the lower half k-plane. Moving
the evaluation point up by i beta = i k alpha/omega therefore increases
|k - k*| by at least beta. By the single-pole law (MA-001 A3, MA-002b),
horizon ~ 0.1 |k - k*| / |dk*|, so this should lengthen the linearization
horizon of the resonance-limited directions.

The Hadamard shape derivative DF[h] = (k_i^2 - k_e^2) \\int u v h ds holds for
complex k by analytic continuation. `shape_jacobian` already uses the state's
(complex) wavenumbers.

`solve` below is `experiments.shape_continuation.forward.solve` without the
real-positive wavenumber check, on the CPU reference path (the CUDA backend
covers real wavenumbers only).
"""
import numpy as np
from scipy.linalg import lu_factor, lu_solve

from gpr_bem_kress.execution import execution
from experiments.shape_continuation import forward as F


def solve(shape, wavenumber, contrast, acquisition, nodes, *, work=None):
    k = complex(wavenumber)
    if k.imag == 0:
        return F.solve(shape, k.real, contrast, acquisition, nodes, work=work)
    if not (np.isfinite(k.real) and np.isfinite(k.imag) and k.real > 0 and k.imag > 0 and contrast > 0):
        raise ValueError('Damped wavenumber must have positive real and imaginary parts.')
    if work is not None:
        work.check()
        work.attempted += 1
    try:
        curve = shape.nodes(nodes)
        assemble, receivers, incident = F._operators(curve)
        ki = k * np.sqrt(contrast)
        with execution(kernels='reference', device='cpu'):
            matrix = np.asarray(assemble(curve, k, ki).system_matrix)
            factors = lu_factor(matrix)
            receiver = receivers(curve, acquisition.receivers, k)
            field, normal = incident(curve, acquisition.sources, k, acquisition.strength)
            rhs = np.vstack((field.T, normal.T))
            if work is not None:
                work.factorizations += 1
                work.rhs_columns += rhs.shape[1]
            traces, residual = F._solve(matrix, factors, rhs)
            prediction = receiver.apply_state(traces)
            if isinstance(acquisition, F.PointSourceAcquisition) and acquisition.paired:
                prediction = np.diag(prediction).copy()
        if not np.isfinite(prediction).all():
            raise FloatingPointError('Nonfinite scattered field.')
    except Exception:
        if work is not None:
            work.failed += 1
        raise
    if work is not None:
        work.completed += 1
    return F.ForwardState(curve, k, ki, acquisition, matrix, factors, traces, prediction, residual, 'cpu')


def horizons(curve, wavenumber, contrast, acquisition, band, amplitudes, nodes=512, tolerance=0.1):
    """Per-harmonic 10% linearization horizons (cosine directions p = 0..band), as SC-016 measures them."""
    from experiments.shape_continuation.atlas import orthonormal_normal_basis
    from experiments.shape_continuation.horizon import HorizonProbe, default_storage_band, perturbed
    state = solve(curve, wavenumber, contrast, acquisition, nodes)
    basis = orthonormal_normal_basis(state.curve, band)
    J = F.shape_jacobian(state, basis)
    perimeter = float(state.curve.perimeter)
    storage = default_storage_band(curve, band)
    out = []
    for p in range(band + 1):
        direction = np.eye(2 * band + 1)[0 if p == 0 else 2 * p - 1]
        achieved, errors = [], []
        for amplitude in amplitudes:
            coefficients = direction * amplitude * np.sqrt(perimeter)
            moved = perturbed(curve, coefficients, storage)
            change = solve(moved.shape, wavenumber, contrast, acquisition, nodes).prediction - state.prediction
            linear = J @ coefficients
            achieved.append(moved.rms_displacement)
            errors.append(float(np.linalg.norm(change - linear) / np.linalg.norm(linear)))
        probe = HorizonProbe(float(abs(wavenumber)), f'cos{p}', np.asarray(amplitudes), np.asarray(achieved),
                             np.asarray(errors), np.zeros(len(errors)), np.zeros(len(errors)), np.zeros(len(errors)))
        out.append(dict(p=p, horizon=probe.horizon(tolerance), order=probe.order(),
                        column_norm=float(np.linalg.norm(J @ direction)),
                        relative_column=float(np.linalg.norm(J @ direction) / np.linalg.norm(state.prediction))))
    return out
