"""Sequential timing of modal_muller on CUDA and CPU against CUDA Kress.

Same protocol as modal-muller-service-20260930: rotated/reversed order, CUDA
synchronization, cold modal geometry in every repetition, geometry-update
preparation excluded. One-time CUDA context, Kress ray table and cuFFT plan
creation are warmed up before timing and reported separately.
Usage: benchmark.py {single|catalog} [--repeats 3]
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np
import scipy
import torch

PREVIOUS = Path('results/validation/cleaned_interfaces/modal-versus-cleaned-kress-20260930')
sys.path.insert(0, str(PREVIOUS.resolve()))
from benchmark import (column_error, differentiate, gpu_status, load_curve, make_observations,  # noqa: E402
                       predict, relative, sync)
from experiments.cleaned_interface.geometry import ProjectedUpdate, resize
from experiments.cleaned_interface.io import write
from experiments.cleaned_interface.modal_muller import ModalMuller
from experiments.cleaned_interface.physics import Execution, NodalKress
from experiments.shape_continuation.atlas_cases import CATALOG_HZ
from experiments.shape_continuation.geometry_runtime import geometry_batch, geometry_runtime

OUT = Path(__file__).resolve().parent
TIMES = ('new_geometry_forward_seconds', 'jacobian_seconds', 'new_geometry_forward_plus_jacobian_seconds',
         'same_geometry_forward_seconds')
METHODS = [('nodal_cuda', 'production'), ('modal_cpu_t4', 'production'), ('modal_cuda_t1', 'production'),
           ('modal_cuda_t4', 'production'), ('nodal_cuda', 'refined'), ('modal_cpu_t4', 'refined'),
           ('modal_cuda_t1', 'refined'), ('modal_cuda_t4', 'refined')]


def modal(method):
    device, threads = method.split('_')[1], int(method.rsplit('_t', 1)[1])
    return ModalMuller(Execution(device=device, frequency_threads=threads))


def one(method, level, curve, catalog, update, space, kress, ref_y, ref_j):
    physics = kress if method == 'nodal_cuda' else modal(method)
    resolution = ((512 if level == 'production' else 1024) if method == 'nodal_cuda'
                  else physics.resolution_profile(curve.band)[level])
    gc.collect()
    sync()
    started = perf_counter()
    with geometry_runtime('both'), geometry_batch():
        states = predict(physics, curve, catalog, resolution)
        sync()
        forward = perf_counter()-started
        tick = perf_counter()
        jacobians = differentiate(physics, states, update, space)
        sync()
        jacobian = perf_counter()-tick
        y = np.column_stack([s.prediction for s in states])
        j = np.stack(jacobians, axis=1)
        del states, jacobians
        gc.collect()
        sync()
        tick = perf_counter()
        warm = predict(physics, curve, catalog, resolution)
        sync()
        same = perf_counter()-tick
        del warm
    receipt = physics.receipt()
    expected = {'nodal_cuda': 'cuda-damped' if complex(catalog[0].wavenumber).imag else 'cuda',
                'modal_cpu_t4': 'cpu-modal'}.get(method, 'cuda-modal')
    if method == 'nodal_cuda':  # shared service: its receipt accumulates warm-up and earlier fixtures
        assert receipt['devices'].get(expected, 0) > 0 and not receipt['fallback_reasons'], receipt
    else:
        assert set(receipt['devices']) == {expected} and not receipt['fallback_reasons'], receipt
    return dict(method=method, level=level, resolution_token=resolution, new_geometry_forward_seconds=forward,
                jacobian_seconds=jacobian, new_geometry_forward_plus_jacobian_seconds=forward+jacobian,
                same_geometry_forward_seconds=same, relative_fields=relative(y, ref_y),
                worst_frequency_fields=column_error(y, ref_y), relative_jacobian=relative(j, ref_j),
                worst_jacobian_column=column_error(j.reshape(-1, j.shape[-1]), ref_j.reshape(-1, ref_j.shape[-1])),
                receipt=receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=['single', 'catalog'])
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    assert torch.cuda.is_available(), 'This comparison must use actual CUDA.'
    before = gpu_status()
    curve_c = resize(load_curve('results/validation/shape_continuation/SC-050-localization-robustness/inputs/development_c/truth.json'), 24)
    endpoint = load_curve('results/validation/modal_atlas/MA-005/runs/DF/c13.3/shifted_rotated_c/fixed_M67.json')
    if args.part == 'single':
        fixtures = [('C_real_2.5GHz', curve_c, [2.5e9], 0., 24), ('C_damped_1GHz', curve_c, [1e9], .25, 24),
                    ('DF_endpoint_real_2.5GHz', endpoint, [2.5e9], 0., 67)]
    else:
        fixtures = [('DF_endpoint_catalog19', endpoint, CATALOG_HZ, 0., 67)]
    kress = NodalKress(Execution(device='cuda', frequency_threads=4))
    reference = NodalKress(Execution(device='cpu', frequency_threads=1))
    tick = perf_counter()
    for damping in (0., .25):
        with geometry_runtime('both'), geometry_batch():
            kress.evaluate(curve_c, make_observations([1e9], damping)[0], 13.3, 512)
    for _, curve, frequencies, damping, _ in fixtures:  # cuFFT plans for this fixture's sizes
        for level in ('production', 'refined'):
            warm = modal('modal_cuda_t1')
            warm.evaluate(curve, make_observations(frequencies[-1:], damping)[0], 13.3,
                          warm.resolution_profile(curve.band)[level])
    sync()
    initialization = perf_counter()-tick
    rows, fixtures_record = [], []
    for name, curve, frequencies, damping, band in fixtures:
        catalog = make_observations(frequencies, damping)
        update = ProjectedUpdate(.05)
        space = update.prepare(curve, band, curve.band)
        oracle = 2048 if args.part == 'single' else 1024
        with geometry_runtime('both'), geometry_batch():
            states = predict(reference, curve, catalog, oracle)
            ref_y = np.column_stack([s.prediction for s in states])
            ref_j = np.stack(differentiate(reference, states, update, space), axis=1)
        del states
        fixtures_record.append(dict(fixture=name, oracle_nodes=oracle, K=curve.band, M=band, contrast=13.3,
                                    frequencies_hz=list(frequencies), damping=damping))
        for repeat in range(args.repeats):
            order = METHODS[repeat:]+METHODS[:repeat]
            if repeat % 2:
                order = order[::-1]
            for method, level in order:
                row = one(method, level, curve, catalog, update, space, kress, ref_y, ref_j)
                row.update(fixture=name, repetition=repeat)
                rows.append(row)
                print(json.dumps({k: v for k, v in row.items() if k != 'receipt'}), flush=True)
                write(OUT/f'{args.part}.json', dict(status='RUNNING', rows=rows, fixtures=fixtures_record))
    medians = []
    for name, *_ in fixtures:
        for method, level in METHODS:
            chosen = [r for r in rows if r['fixture'] == name and r['method'] == method and r['level'] == level]
            medians.append(dict(fixture=name, method=method, level=level, resolution_token=chosen[0]['resolution_token'],
                medians={k: float(np.median([r[k] for r in chosen])) for k in TIMES},
                ranges={k: [min(r[k] for r in chosen), max(r[k] for r in chosen)] for k in TIMES},
                worst_fields=max(r['worst_frequency_fields'] for r in chosen),
                worst_jacobian=max(r['relative_jacobian'] for r in chosen), repetitions=len(chosen)))
    sources = [Path(__file__), PREVIOUS/'benchmark.py', *sorted(Path('experiments/cleaned_interface').glob('modal_*.py')),
               Path('experiments/cleaned_interface/physics.py'), Path('experiments/cleaned_interface/damped_cuda.py')]
    write(OUT/f'{args.part}.json', dict(status='COMPLETE', rows=rows, medians=medians, fixtures=fixtures_record,
        initialization_seconds=initialization, gpu_before=before, gpu_after=gpu_status(),
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                         torch=torch.__version__, gpu=torch.cuda.get_device_name(0), blas_threads=1,
                         nodal_cuda_frequency_threads=4),
        protocol='sequential; rotated/reversed order; CUDA synchronized; cold modal geometry per repetition; '
                 'CUDA context, ray table and cuFFT plans warmed before timing; geometry-update preparation excluded',
        source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}))
    print(json.dumps(medians, indent=1), flush=True)


if __name__ == '__main__':
    main()
