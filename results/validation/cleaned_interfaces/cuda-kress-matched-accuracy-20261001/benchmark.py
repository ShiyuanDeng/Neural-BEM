"""CUDA-only Kress resolution search; do not import the changing modal service.

Run in EMNerf with PYTHONPATH=solvers:. and one BLAS thread. No CPU solve
or CPU reference-convergence campaign is performed. The reference is CUDA
Kress N=2048, supported by the earlier CPU/CUDA and CPU convergence checks.
"""
import argparse
import csv
import gc
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
import torch

from experiments.cleaned_interface.io import curve_from
from experiments.cleaned_interface.physics import Execution, NodalKress
from experiments.cleaned_interface.problem import Observation
from experiments.shape_continuation.atlas_cases import CATALOG_HZ, observations
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.geometry_runtime import geometry_batch, geometry_runtime

OUT = Path(__file__).resolve().parent
TOLERANCES = (1e-7, 1e-9, 1e-11)
CONTRAST = 13.3
REFERENCE_N = 2048


class SampledFourierCurve(FourierCurve):
    """Exact uniform samples of every stored coefficient, at any node count.

    Folding modes into FFT bins evaluates the finite Fourier sum; it does
    not drop high modes. Derivative jets are folded separately. This removes
    SC's storage-band guard without changing the continuous curve.
    """
    def values(self, count, derivative=0):
        spectrum = np.zeros(count, complex)
        np.add.at(spectrum, self.modes % count,
                  self.coefficients * (1j*self.modes)**derivative)
        return np.fft.ifft(spectrum)*count


def load(path):
    record = json.loads(Path(path).read_text())
    curve = curve_from(record.get('curve', record))
    sampled = SampledFourierCurve(curve.coefficients)
    for d in range(4):
        np.testing.assert_array_equal(sampled.values(1024, d), curve.values(1024, d))
    # Also verify folding below the stored band against direct summation.
    t = 2*np.pi*np.arange(30)/30
    for d in range(4):
        direct = np.exp(1j*t[:, None]*curve.modes) @ (curve.coefficients*(1j*curve.modes)**d)
        np.testing.assert_allclose(sampled.values(30, d), direct, rtol=2e-11, atol=2e-9)
    return sampled


def catalog(frequencies, damping):
    acquisition = observations(np.zeros((24, 1)), [1e9])[0].acquisition
    return tuple(Observation(6.417188604442469*f/2.5e9*(1+1j*damping),
                             acquisition, np.ones(24, complex), f) for f in frequencies)


def predict(service, curve, obs, n):
    def call(o):
        state = service.evaluate(curve, o, CONTRAST, n)
        expected = 'cuda-damped' if complex(o.wavenumber).imag else 'cuda'
        assert state.diagnostics['device'] == expected, state.diagnostics
        assert state.diagnostics['fallback'] is None, state.diagnostics
        return state.prediction
    with geometry_runtime('both'), geometry_batch():
        with service.ordered_calls(call, obs) as calls:
            return np.column_stack([f() for f in calls])


def errors(y, reference):
    return np.linalg.norm(y-reference, axis=0)/np.linalg.norm(reference, axis=0)


def write(record):
    temporary = OUT/'results.tmp'
    temporary.write_text(json.dumps(record, indent=2, allow_nan=False)+'\n')
    temporary.replace(OUT/'results.json')


def gpu():
    return subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.used,utilization.gpu',
                                    '--format=csv'], text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-nodes', type=int, default=1024)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--accuracy-only', action='store_true')
    parser.add_argument('--timing-only', action='store_true', help='Reuse the completed accuracy sweep')
    args = parser.parse_args()
    assert torch.cuda.is_available()
    c_path = 'results/validation/shape_continuation/SC-050-localization-robustness/inputs/development_c/truth.json'
    endpoint_path = 'results/validation/modal_atlas/MA-005/runs/DF/c13.3/shifted_rotated_c/fixed_M67.json'
    c, endpoint = load(c_path), load(endpoint_path)
    fixtures = [('C_real_2.5GHz', c, [2.5e9], 0., c_path),
                ('C_damped_1GHz', c, [1e9], .25, c_path),
                ('DF_endpoint_real_2.5GHz', endpoint, [2.5e9], 0., endpoint_path),
                ('DF_endpoint_catalog19', endpoint, CATALOG_HZ, 0., endpoint_path)]
    service = NodalKress(Execution(device='cuda', frequency_threads=4))
    record = dict(status='RUNNING', contrast=CONTRAST, tolerances=list(TOLERANCES),
        reference_nodes=REFERENCE_N, reference_device='cuda', fixtures=[], timings=[],
        reference_basis='Earlier CPU Kress convergence and CPU/CUDA equivalence accepted; no CPU solves repeated.',
        geometry='All original Fourier coefficients preserved; exact samples at arbitrary N.',
        protocol='Every even N from 8 upward; minimum is exhaustive among admitted resolutions; '
                 'verify next two even counts; four frequency threads; one BLAS thread; '
                 'timing includes geometry, assembly, factorization and receiver predictions; '
                 'fresh validation scope; no retained matrices/factors; CUDA startup excluded.',
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        torch_version=torch.__version__, cuda_version=torch.version.cuda,
        gpu_before=gpu(), source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), Path('experiments/cleaned_interface/physics.py'),
                      Path('experiments/cleaned_interface/damped_cuda.py'),
                      Path('experiments/shape_continuation/forward.py'), Path(c_path), Path(endpoint_path)]})
    if args.timing_only:
        record = json.loads((OUT/'results.json').read_text())
        assert len(record['fixtures']) == len(fixtures)
        record['status'], record['timings'] = 'TIMING', []
        record['source_hashes'][str(Path(__file__))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    # CUDA initialization/ray-table setup is excluded for both reference and timings.
    for damping in (0., .25):
        predict(service, c, catalog([1e9], damping), 512)
    for name, curve, frequencies, damping, path in ([] if args.timing_only else fixtures):
        obs = catalog(frequencies, damping)
        reference = predict(service, curve, obs, REFERENCE_N)
        np.savez(OUT/f'{name}_reference.npz', prediction=reference, frequencies=frequencies,
                 coefficients=curve.coefficients, nodes=REFERENCE_N, contrast=CONTRAST, damping=damping)
        row = dict(fixture=name, curve_path=path, curve_band=curve.band,
                   frequencies_hz=list(frequencies), damping=damping, sweep=[], selected=[])
        record['fixtures'].append(row)
        found = {}
        for n in range(8, args.max_nodes+1, 2):
            try:
                e = errors(predict(service, curve, obs, n), reference)
                entry = dict(nodes=n, unknowns=2*n, worst_frequency_error=float(max(e)),
                             frequency_errors=e.tolist())
                for tol in TOLERANCES:
                    if tol not in found and max(e) <= tol:
                        found[tol] = n
                        print(name, 'first pass', tol, 'N=', n, 'error=', max(e), flush=True)
            except (ValueError, FloatingPointError) as exc:
                entry = dict(nodes=n, unknowns=2*n, refusal=str(exc))
            row['sweep'].append(entry)
            if n % 32 == 0:
                write(record)
            if len(found) == len(TOLERANCES) and n >= max(found.values())+4:
                break
        by_n = {r['nodes']: r for r in row['sweep']}
        for tol in TOLERANCES:
            n = found.get(tol)
            if n is None:
                row['selected'].append(dict(tolerance=tol, qualified=False, reason='No passing size in search range'))
                continue
            following = [by_n.get(n+step, {}) for step in (2, 4)]
            stable = all(e.get('worst_frequency_error', float('inf')) <= tol for e in following)
            row['selected'].append(dict(tolerance=tol, nodes=n, unknowns=2*n,
                worst_frequency_error=by_n[n]['worst_frequency_error'], qualified=stable,
                next_two_even_counts_pass=stable))
        write(record)
    if not args.accuracy_only:
        for row, (_, curve, frequencies, damping, _) in zip(record['fixtures'], fixtures):
            obs = catalog(frequencies, damping)
            sizes = sorted({512, 1024, *[r['nodes'] for r in row['selected'] if r.get('qualified')]})
            values = {n: [] for n in sizes}
            for n in sizes:
                predict(service, curve, obs, n)  # warm CUDA plans at each selected size
            for repetition in range(args.repeats):
                order = sizes[repetition % len(sizes):]+sizes[:repetition % len(sizes)]
                if repetition % 2:
                    order = order[::-1]
                for n in order:
                    gc.collect()
                    torch.cuda.synchronize()
                    start = perf_counter()
                    predict(service, curve, obs, n)
                    torch.cuda.synchronize()
                    values[n].append(perf_counter()-start)
            for n, seconds in values.items():
                record['timings'].append(dict(fixture=row['fixture'], nodes=n, unknowns=2*n,
                    median_seconds=float(np.median(seconds)), seconds=seconds))
            write(record)
    record.update(status='COMPLETE', gpu_after=gpu(), receipt=service.receipt())
    assert not record['receipt']['fallback_reasons']
    write(record)
    with (OUT/'selected.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['fixture', 'tolerance', 'nodes', 'unknowns',
                                                   'worst_frequency_error', 'qualified', 'median_seconds'])
        writer.writeheader()
        for row in record['fixtures']:
            for selected in row['selected']:
                timed = next((r for r in record['timings'] if r['fixture']==row['fixture'] and
                              r['nodes']==selected.get('nodes')), {})
                writer.writerow(dict(fixture=row['fixture'], **{k: selected.get(k) for k in
                    ('tolerance', 'nodes', 'unknowns', 'worst_frequency_error', 'qualified')},
                    median_seconds=timed.get('median_seconds')))
    print(json.dumps(dict(selected=[dict(fixture=r['fixture'], selected=r['selected'])
                                   for r in record['fixtures']], timings=record['timings']), indent=2))


if __name__ == '__main__':
    main()
