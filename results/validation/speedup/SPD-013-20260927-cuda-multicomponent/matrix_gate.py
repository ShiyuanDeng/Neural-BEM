"""SPD-013 gate 1: CUDA multi-component systems, predictions and Jacobians against the CPU.

Scenes: SC-047 initial and true pairs at both separations, SC-047 joint clean
endpoints, and SC-048's perturbed initial pair and three arm endpoints. Every
catalog frequency is solved at N = 256 and 512 nodes per component on both
backends. The Jacobian basis is the M5 complete-trial projected update.

    python matrix_gate.py OUT.json
"""
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
SC047 = ROOT / 'results/validation/shape_continuation/SC-047-coupled-continuation'
SC048 = ROOT / 'results/validation/shape_continuation/SC-048-global-motion-directions'
sys.path[:0] = [str(ROOT), str(ROOT / 'solvers'), str(SC047)]
import qualify as q  # noqa: E402
from experiments.shape_continuation.forward import ordered_calls, shape_jacobian, solve  # noqa: E402
from experiments.shape_continuation.multi_object import MultiUpdate  # noqa: E402
from gpr_bem_kress import cuda_assembly  # noqa: E402
from ordered_boundary.validation_cache import validation_cache  # noqa: E402

LIMITS = dict(matrix=1e-14, prediction=1e-12, jacobian=1e-12, residual=1e-10)


def scenes():
    rows = []
    for sep in ('0.14', '0.20'):
        inputs = json.loads((SC047 / 'inputs' / f'separation_{sep}' / 'input.json').read_text())
        rows += [(f'sc047_sep{sep}_initial', inputs['initial']), (f'sc047_sep{sep}_truth', inputs['truth'])]
        result = json.loads((SC047 / 'runs' / f'sep{sep}_clean' / 'joint' / 'result.json').read_text())
        rows.append((f'sc047_sep{sep}_joint_endpoint', result['final_state']))
    inputs = json.loads((SC048 / 'inputs' / 'sep0.14_clean.json').read_text())
    rows.append(('sc048_initial', inputs['initial']))
    for arm in ('normal_m5', 'normal_m9', 'global_m5'):
        result = json.loads((SC048 / 'runs' / 'sep0.14_clean' / arm / 'result.json').read_text())
        rows.append((f'sc048_{arm}_endpoint', result['final_state']))
    return [(label, q.load_scene(row)) for label, row in rows]


def backend_states(scene, catalog, contrast, nodes, backend, update, space):
    os.environ['SC_FORWARD_BACKEND'] = backend
    started = time.perf_counter()
    with validation_cache('cache'):
        with ordered_calls(lambda o: solve(scene, o.wavenumber, contrast, o.acquisition, nodes), catalog) as calls:
            states = [call() for call in calls]
        with ordered_calls(lambda s: shape_jacobian(s, update.velocities(space, s.curve)), states) as calls:
            jacobians = [call() for call in calls]
    return states, jacobians, time.perf_counter() - started


def relative(a, b):
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def main(out):
    catalog, contrast, _ = q.setup()
    update = MultiUpdate(q.ProjectedUpdate(q.LENGTH))
    rows = []
    for label, scene in scenes():
        space = update.prepare(scene, 5, q.BAND)
        for nodes in (256, 512):
            cpu, cpu_jac, cpu_seconds = backend_states(scene, catalog, contrast, nodes, 'cpu', update, space)
            gpu, gpu_jac, gpu_seconds = backend_states(scene, catalog, contrast, nodes, 'cuda', update, space)
            assert all(isinstance(s.factors, cuda_assembly.DeviceFactors) for s in gpu)
            row = dict(scene=label, components=len(scene.components), nodes_per_component=nodes,
                frequencies=len(catalog),
                matrix_max_relative=max(float(np.max(np.abs(g.matrix - c.matrix)) / np.max(np.abs(c.matrix)))
                                        for g, c in zip(gpu, cpu)),
                prediction_max_relative=max(relative(g.prediction, c.prediction) for g, c in zip(gpu, cpu)),
                jacobian_max_relative=max(relative(g, c) for g, c in zip(gpu_jac, cpu_jac)),
                gpu_residual_max=max(s.system_residual for s in gpu),
                cpu_residual_max=max(s.system_residual for s in cpu),
                cpu_seconds=cpu_seconds, gpu_seconds=gpu_seconds)
            rows.append(row)
            print(json.dumps(row), flush=True)
    worst = {k: max(r[k] for r in rows) for k in ('matrix_max_relative', 'prediction_max_relative',
                                                    'jacobian_max_relative', 'gpu_residual_max')}
    passed = dict(matrix=worst['matrix_max_relative'] <= LIMITS['matrix'],
                  prediction=worst['prediction_max_relative'] <= LIMITS['prediction'],
                  jacobian=worst['jacobian_max_relative'] <= LIMITS['jacobian'],
                  residual=worst['gpu_residual_max'] <= LIMITS['residual'])
    Path(out).write_text(json.dumps(dict(limits=LIMITS, passed=passed, all_passed=all(passed.values()),
        worst=worst, rows=rows, threads=os.environ.get('SC_FREQUENCY_THREADS')), indent=1))
    print('PASSED' if all(passed.values()) else 'FAILED', passed, worst)


if __name__ == '__main__':
    main(sys.argv[1])
