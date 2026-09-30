"""Scratch end-to-end check: replay a recorded MA-004 D attempt with/without both speedups.

Everything is patched in this process only; outputs go to the scratch folder given as root.
  accelerated: damped solves assemble on the GPU (ray table) and factor with DeviceFactors;
               the dense Mie grid (multi-centre calls only) uses the order recurrence + GPU contraction.
  baseline:    the unchanged recorded code path, run now under the same conditions for timing.
"""
import sys, json, time
from pathlib import Path
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from damped_gpu import RayTable, gpu_matrix
import mie_grid

from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.execution import execution
from experiments.modal_atlas import damped, damped_screen as ds, mie_localize as ml
from experiments.shape_continuation import forward as F


def install():
    table = RayTable(ds.GAMMA)
    original_landscape = ml.landscape

    def landscape(observations, contrast, centers, radii, *, cutoff=None):
        if len(centers) == 1:      # coordinate refinement: unchanged reference evaluation
            return original_landscape(observations, contrast, centers, radii, cutoff=cutoff)
        return mie_grid.landscape_variant(observations, contrast, centers, radii, cutoff, device='cuda')
    ml.landscape = landscape

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
            _, receivers, incident = F._operators(curve)
            ki = k * np.sqrt(contrast)
            with CA._device_work:
                matrix = gpu_matrix(curve, k, ki, table)
            factors = CA.DeviceFactors(matrix)
            with execution(kernels='reference', device='cpu'):
                receiver = receivers(curve, acquisition.receivers, k)
                field, normal = incident(curve, acquisition.sources, k, acquisition.strength)
            rhs = np.vstack((field.T, normal.T))
            if work is not None:
                work.factorizations += 1
                work.rhs_columns += rhs.shape[1]
            traces, residual = F._solve(factors.host, factors, rhs)
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
        return F.ForwardState(curve, k, ki, acquisition, factors.host, factors, traces, prediction, residual, 'cuda-damped')
    damped.solve = solve
    return solve

