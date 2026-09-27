"""SPD-011 gates 1-2: CUDA systems, predictions and Jacobians against the CPU reference.

Geometries are the six SC-043 fixed-policy start (pre-fit) and endpoint curves.
Every catalog frequency is solved at N = 512 and 1024 on both backends. The
Jacobian basis is the renderer's ripple basis through order 48.

    python matrix_gate.py OUT.json
"""
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'solvers')]
from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, atlas_video as av  # noqa: E402
from experiments.shape_continuation import spd_cases as sc  # noqa: E402
from experiments.shape_continuation.forward import ordered_calls, shape_jacobian, solve  # noqa: E402
from gpr_bem_kress import cuda_assembly  # noqa: E402
from ordered_boundary.validation_cache import validation_cache  # noqa: E402

CASES = ('wrong_circle', 'circle_to_star', 'circle_to_c', 'kite', 'peanut', 'hook')
RUNS = ROOT / 'results/validation/shape_continuation/SC-043-prospective-band/runs'
LIMITS = dict(matrix=1e-14, prediction=1e-12, jacobian=1e-12, residual=1e-10)


def curves(case):
    decision = json.loads((RUNS / case / 'fixed/decisions.json').read_text())['rows'][0]
    result = json.loads((RUNS / case / 'fixed/result.json').read_text())
    return dict(start=ast.curve_from(decision['curve_before_fit']), endpoint=ast.curve_from(result['curve']))


def backend_states(curve, catalog, nodes, backend, basis):
    os.environ['SC_FORWARD_BACKEND'] = backend
    started = time.perf_counter()
    with validation_cache('cache'):
        with ordered_calls(lambda o: solve(curve, o.wavenumber, ac.contrast(), o.acquisition, nodes), catalog) as calls:
            states = [call() for call in calls]
        with ordered_calls(lambda s: shape_jacobian(s, basis), states) as calls:
            jacobians = [call() for call in calls]
    return states, jacobians, time.perf_counter() - started


def relative(a, b):
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def main(out):
    rows = []
    for case in CASES:
        catalog = ast.catalog_only(case)
        for label, curve in curves(case).items():
            for nodes in (512, 1024):
                basis = av.ripple_basis(curve.coefficients, nodes, sc.LENGTH)
                cpu, cpu_jac, cpu_seconds = backend_states(curve, catalog, nodes, 'cpu', basis)
                gpu, gpu_jac, gpu_seconds = backend_states(curve, catalog, nodes, 'cuda', basis)
                assert all(isinstance(s.factors, cuda_assembly.DeviceFactors) for s in gpu)
                # CPU states hold the reference build_muller_system matrix; GPU states hold the device one.
                matrix = [float(np.max(np.abs(g.matrix - c.matrix)) / np.max(np.abs(c.matrix)))
                          for g, c in zip(gpu, cpu)]
                row = dict(case=case, curve=label, nodes=nodes, frequencies=len(catalog),
                    matrix_max_relative=max(matrix),
                    prediction_max_relative=max(relative(g.prediction, c.prediction) for g, c in zip(gpu, cpu)),
                    jacobian_max_relative=max(relative(g, c) for g, c in zip(gpu_jac, cpu_jac)),
                    gpu_residual_max=max(s.system_residual for s in gpu),
                    cpu_residual_max=max(s.system_residual for s in cpu),
                    cpu_seconds=cpu_seconds, gpu_seconds=gpu_seconds)
                rows.append(row)
                print(json.dumps(row), flush=True)
    passed = dict(
        matrix=max(r['matrix_max_relative'] for r in rows) <= LIMITS['matrix'],
        prediction=max(r['prediction_max_relative'] for r in rows) <= LIMITS['prediction'],
        jacobian=max(r['jacobian_max_relative'] for r in rows) <= LIMITS['jacobian'],
        residual=max(r['gpu_residual_max'] for r in rows) <= LIMITS['residual'])
    worst = {k: max(r[k] for r in rows) for k in ('matrix_max_relative', 'prediction_max_relative',
                                                    'jacobian_max_relative', 'gpu_residual_max')}
    Path(out).write_text(json.dumps(dict(limits=LIMITS, passed=passed, all_passed=all(passed.values()),
        worst=worst, rows=rows, threads=os.environ.get('SC_FREQUENCY_THREADS'),
        note='timings include the cache-sharing thread pool; CPU and GPU arms are sequential'), indent=1))
    print('PASSED' if all(passed.values()) else 'FAILED', passed, worst)


if __name__ == '__main__':
    main(sys.argv[1])
