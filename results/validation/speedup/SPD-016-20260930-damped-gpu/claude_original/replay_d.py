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

mode, contrast, scene, root = sys.argv[1], float(sys.argv[2]), sys.argv[3], Path(sys.argv[4])

if mode == 'accelerated':
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

started = time.perf_counter()
row = ds.attempt('D', contrast, scene, root=root / mode)
wall = time.perf_counter() - started
recorded = json.loads((ds.OUT / 'runs' / 'D' / ds.tag(contrast) / scene / 'result.json').read_text())


def summary(r):
    return dict(outcome=r['outcome'], recovered=r['recovered'], rms_mm=r['metrics']['rms_mm'],
                units=r['fit_and_localization_units'], localization_s=r['localization']['seconds'],
                grid_s=r['localization']['grid_seconds'], localization_start=r['localization'].get('parameters_m'),
                stages=[(s['stage'], s['outcome'], s['accepted_steps'], s['final_loss'], s['seconds']) for s in r['stages']],
                fit_and_localization_s=r['fit_and_localization_seconds'], total_s=r['seconds'])


new, old = summary(row), summary(recorded)
stage_loss = max(abs(a[3] - b[3]) / abs(b[3]) for a, b in zip(new['stages'], old['stages']))
print('SUMMARY', json.dumps(dict(
    mode=mode, contrast=contrast, scene=scene, wall_s=wall,
    same_outcome=new['outcome'] == old['outcome'] and new['recovered'] == old['recovered'],
    same_units=new['units'] == old['units'],
    same_accepted=[a[2] for a in new['stages']] == [b[2] for b in old['stages']],
    max_stage_loss_rel=stage_loss, rms_mm=(new['rms_mm'], old['rms_mm']),
    localization_s=(new['localization_s'], old['localization_s']), grid_s=(new['grid_s'], old['grid_s']),
    damped_stage_s=(sum(s[4] for s in new['stages'] if s[0].endswith('_damped')), sum(s[4] for s in old['stages'] if s[0].endswith('_damped'))),
    undamped_stage_s=(sum(s[4] for s in new['stages'] if not s[0].endswith('_damped')), sum(s[4] for s in old['stages'] if not s[0].endswith('_damped'))),
    total_s=(new['total_s'], old['total_s']))), flush=True)
