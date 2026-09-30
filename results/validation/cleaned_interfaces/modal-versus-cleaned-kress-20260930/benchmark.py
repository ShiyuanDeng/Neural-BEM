"""Sequential, alternating-order comparison against the maintained CI backend.

Run in EMNerf, PYTHONPATH=solvers:., BLAS threads=1, with actual CUDA access.
The native implementation is the unchanged independent review prototype.
"""
import argparse
from dataclasses import asdict
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np
import scipy
import torch

REVIEW = Path('results/validation/cleaned_interfaces/chebyshev-review-20260930')
sys.path.insert(0, str(REVIEW.resolve()))
from replay import NativePhysics
from integration_checks import load_curve
from verify import relative
from experiments.cleaned_interface.geometry import ProjectedUpdate, resize
from experiments.cleaned_interface.physics import Execution, NodalKress
from experiments.cleaned_interface.problem import Observation
from experiments.cleaned_interface.io import portable
from experiments.shape_continuation.atlas_cases import observations, CATALOG_HZ
from experiments.shape_continuation.geometry_runtime import geometry_runtime, geometry_batch

OUT = Path(__file__).resolve().parent


def write(name, record):
    path = OUT/name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(portable(record), indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def sync():
    torch.cuda.synchronize()


def gpu_status():
    return subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
                                    '--format=csv'], text=True).strip()


def column_error(a, b):
    return float(np.max(np.linalg.norm(a-b, axis=0)/np.linalg.norm(b, axis=0)))


def make_observations(frequencies, damping=0):
    template = observations(np.zeros((24, 1)), [1e9])[0].acquisition
    return tuple(Observation(6.417188604442469*f/2.5e9*(1+1j*damping), template,
                             np.ones(24, complex), f) for f in frequencies)


def predict(physics, curve, catalog, resolution):
    with physics.ordered_calls(lambda o: physics.evaluate(curve, o, 13.3, resolution), catalog) as calls:
        return [call() for call in calls]


def differentiate(physics, states, update, space):
    with physics.ordered_calls(lambda s: physics.derivative(s, update, space), states) as calls:
        return [call() for call in calls]


def one(method, curve, catalog, resolution, update, space, backend, ref_y, ref_j):
    """A new native service makes the geometry cold; nodal retains only its ray table.

    Validation cache is fresh for each repetition and shared across frequencies,
    matching a cleaned-interface objective batch. Imports/CUDA startup excluded.
    """
    physics = NativePhysics() if method == 'modal_cpu' else backend
    gc.collect()
    sync()
    started = perf_counter()
    with geometry_runtime('both'), geometry_batch():
        states = predict(physics, curve, catalog, resolution)
        sync()
        forward_seconds = perf_counter()-started
        tick = perf_counter()
        jacobians = differentiate(physics, states, update, space)
        sync()
        jacobian_seconds = perf_counter()-tick
        y = np.column_stack([s.prediction for s in states])
        j = np.stack(jacobians, axis=1)
        del states, jacobians
        gc.collect()
        sync()
        tick = perf_counter()
        # Same geometry/frequency, but both methods rebuild the matrix and LU.
        warm = predict(physics, curve, catalog, resolution)
        sync()
        warm_forward_seconds = perf_counter()-tick
        del warm
    if method == 'modal_cpu':
        prepared = next(iter(physics.cache.values()))
        geometry_seconds = prepared.seconds
        receipt = dict(counts=physics.counts, device='cpu', frequency_threads=1,
                       coefficient_bandwidth=prepared.band,
                       trace_cutoff=((96 if resolution == 512 else 128) if curve.band > 24
                                     else (64 if resolution == 512 else 96)))
    else:
        geometry_seconds = None
        receipt = physics.receipt()
        if method == 'nodal_cuda':
            expected = 'cuda-damped' if complex(catalog[0].wavenumber).imag else 'cuda'
            assert receipt['devices'].get(expected, 0) > 0, receipt
            assert not receipt['fallback_reasons'], receipt
    row = dict(method=method, resolution_token=resolution,
        cold_geometry_forward_seconds=forward_seconds, retained_factor_jacobian_seconds=jacobian_seconds,
        cold_forward_plus_jacobian_seconds=forward_seconds+jacobian_seconds,
        same_geometry_forward_seconds=warm_forward_seconds, native_geometry_setup_seconds=geometry_seconds,
        relative_fields=relative(y, ref_y), worst_frequency_fields=column_error(y, ref_y),
        relative_jacobian=relative(j, ref_j),
        worst_jacobian_column=column_error(j.reshape(-1, j.shape[-1]), ref_j.reshape(-1, ref_j.shape[-1])),
        receipt=receipt)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=['single', 'catalog'])
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    assert torch.cuda.is_available(), 'This comparison must use actual CUDA; CPU fallback is not comparable.'
    status_before = gpu_status()
    curve_c = resize(load_curve('results/validation/shape_continuation/SC-050-localization-robustness/inputs/development_c/truth.json'), 24)
    endpoint = load_curve('results/validation/modal_atlas/MA-005/runs/DF/c13.3/shifted_rotated_c/fixed_M67.json')
    if args.part == 'single':
        fixtures = [('C_real_2.5GHz', curve_c, [2.5e9], 0., 24),
                    ('C_damped_1GHz', curve_c, [1e9], .25, 24),
                    ('DF_endpoint_real_2.5GHz', endpoint, [2.5e9], 0., 67)]
    else:
        fixtures = [('DF_endpoint_catalog19', endpoint, CATALOG_HZ, 0., 67)]
    cuda = NodalKress(Execution(device='cuda', frequency_threads=4, acceleration='spd016', geometry='both'))
    cpu = NodalKress(Execution(device='cpu', frequency_threads=1, acceleration='spd016', geometry='both'))
    # Load real CUDA kernels, factorization, and SPD-016 ray table once, as in a run.
    tick = perf_counter()
    for damping in (0., .25):
        obs = make_observations([1e9], damping)[0]
        with geometry_runtime('both'), geometry_batch():
            cuda.evaluate(curve_c, obs, 13.3, 512)
    sync()
    initialization = perf_counter()-tick
    rows, qualifications = [], []
    for name, curve, frequencies, damping, update_band in fixtures:
        catalog = make_observations(frequencies, damping)
        update = ProjectedUpdate(.05)
        tick = perf_counter()
        space = update.prepare(curve, update_band, curve.band)
        update_seconds = perf_counter()-tick
        # Single-frequency comparisons use an independent 2048-node CPU oracle.
        # The full catalog uses 1024 CPU; the endpoint's 2.5GHz point is also
        # independently checked at 2048 by the single-frequency fixture.
        oracle_resolution = 2048 if args.part == 'single' else 1024
        print(json.dumps(dict(event='oracle', fixture=name, nodes=oracle_resolution)), flush=True)
        with geometry_runtime('both'), geometry_batch():
            states = predict(cpu, curve, catalog, oracle_resolution)
            ref_y = np.column_stack([s.prediction for s in states])
            ref_j = np.stack(differentiate(cpu, states, update, space), axis=1)
        del states
        gc.collect()
        qualifications.append(dict(fixture=name, oracle_nodes=oracle_resolution,
            geometry_update_preparation_seconds=update_seconds, K=curve.band, M=update_band,
            contrast=13.3, frequencies_hz=list(frequencies), damping=damping))
        methods = [('nodal_cuda', 512), ('nodal_cpu', 512), ('modal_cpu', 512),
                   ('nodal_cuda', 1024), ('modal_cpu', 1024)]
        # CPU 1024 control is useful for a single solve; avoid turning the
        # 19-frequency comparison into a benchmark of a superseded baseline.
        if args.part == 'single':
            methods.append(('nodal_cpu', 1024))
        for repeat in range(args.repeats):
            order = methods[repeat:]+methods[:repeat]
            if repeat % 2:
                order = list(reversed(order))
            for method, resolution in order:
                row = one(method, curve, catalog, resolution, update, space,
                          cuda if method == 'nodal_cuda' else cpu, ref_y, ref_j)
                row.update(fixture=name, repetition=repeat, oracle_nodes=oracle_resolution)
                rows.append(row)
                print(json.dumps({k:v for k,v in row.items() if k != 'receipt'}), flush=True)
                write(args.part+'.json', dict(rows=rows, qualifications=qualifications,
                      initialization_seconds=initialization, status='RUNNING'))
    groups = []
    for name, *_ in fixtures:
        for method, resolution in methods:
            selected = [r for r in rows if r['fixture']==name and r['method']==method and r['resolution_token']==resolution]
            keys = ['cold_geometry_forward_seconds','retained_factor_jacobian_seconds',
                    'cold_forward_plus_jacobian_seconds','same_geometry_forward_seconds']
            groups.append(dict(fixture=name, method=method, resolution_token=resolution,
                medians={k:float(np.median([r[k] for r in selected])) for k in keys},
                ranges={k:[min(r[k] for r in selected),max(r[k] for r in selected)] for k in keys},
                worst_fields=max(r['worst_frequency_fields'] for r in selected),
                worst_jacobian=max(r['relative_jacobian'] for r in selected),
                modal_setup_median=(float(np.median([r['native_geometry_setup_seconds'] for r in selected]))
                                    if method=='modal_cpu' else None)))
    source_paths = [Path(__file__), REVIEW/'replay.py', REVIEW/'integration_checks.py', REVIEW/'verify.py',
        Path('experiments/cleaned_interface/physics.py'),Path('experiments/cleaned_interface/damped_cuda.py'),
        Path('experiments/shape_continuation/forward.py'),Path('solvers/gpr_bem_kress/cuda_assembly.py')]
    record = dict(status='COMPLETE', rows=rows, medians=groups, qualifications=qualifications,
        initialization_seconds=initialization, gpu_before=status_before, gpu_after=gpu_status(),
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
            torch=torch.__version__,gpu=torch.cuda.get_device_name(0),blas_threads=1,
            nodal_cuda_frequency_threads=4,modal_frequency_threads=1,cpu_nodal_frequency_threads=1),
        protocol='Sequential methods and repetitions, rotated/reversed order; GPU synchronization at timing boundaries; '
                 'fresh native geometry per repetition; persistent CUDA runtime/ray table; geometry update preparation '
                 'excluded from both physics timings and reported separately; same-geometry timing retains native '
                 'geometry/waves but rebuilds matrices and LU for both methods.',
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths})
    write(args.part+'.json', record)
    print(json.dumps(dict(event='complete', part=args.part, medians=groups), indent=2), flush=True)


if __name__ == '__main__':
    main()
