"""CUDA and CPU modal_muller against 2048-node Kress on the review fixtures.

Records each device's error against the independent nodal reference and the
CUDA-CPU difference, plus complete-trial centered differences on CUDA.
Usage: accuracy.py {fields|directional}
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

REVIEW = Path('results/validation/cleaned_interfaces/chebyshev-review-20260930')
sys.path.insert(0, str(REVIEW.resolve()))
from integration_checks import load_curve, nodal_state  # noqa: E402
from experiments.cleaned_interface.geometry import ProjectedUpdate, resize
from experiments.cleaned_interface.io import write
from experiments.cleaned_interface.modal_muller import ModalMuller, token
from experiments.cleaned_interface.physics import Execution
from experiments.cleaned_interface.problem import Observation
from experiments.shape_continuation import forward as F
from experiments.shape_continuation.atlas_cases import observations

OUT = Path(__file__).resolve().parent
C_TRUTH = 'results/validation/shape_continuation/SC-050-localization-robustness/inputs/development_c/truth.json'
ENDPOINT = 'results/validation/modal_atlas/MA-005/runs/DF/c13.3/shifted_rotated_c/fixed_M67.json'
K25 = 6.417188604442469
FIXTURES = [('C', C_TRUTH, 24, 24, [(1e9, 0.), (2.5e9, 0.)], [64, 96]),
            ('DF_endpoint', ENDPOINT, 192, 67, [(1.25e9, 0.), (2.5e9, 0.)], [96, 128]),
            ('C_damped', C_TRUTH, None, None, [(.5e9, .25), (1e9, .25), (1.25e9, .25), (2.5e9, .25)], [64, 96])]


def relative(a, b):
    return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def column(a, b):
    return float(np.max(np.linalg.norm(a-b, axis=0)/np.linalg.norm(b, axis=0)))


def fields():
    acquisition = observations(np.zeros((24, 1)), [1e9])[0].acquisition
    update = ProjectedUpdate(.05)
    rows = []
    for name, path, band, M, catalog, cutoffs in FIXTURES:
        curve = load_curve(path) if band is None else resize(load_curve(path), band)
        space = update.prepare(curve, M, curve.band) if M else None
        for frequency, damping in catalog:
            k = K25*frequency/2.5e9*(1+1j*damping)
            k = k if damping else k.real
            reference = nodal_state(curve, k, 13.3, acquisition, 2048)
            jref = F.shape_jacobian(reference, update.velocities(space, reference.curve)) if space else None
            for cutoff in cutoffs:
                row = dict(fixture=name, frequency_hz=frequency, damping=damping, K=curve.band, M=M, K_trace=cutoff)
                results = {}
                for device in ('cpu', 'cuda'):
                    service = ModalMuller(Execution(device=device, frequency_threads=1))
                    state = service.evaluate(curve, Observation(k, acquisition, reference.prediction, frequency),
                                             13.3, token(cutoff))
                    assert state.diagnostics['device'] == f'{device}-modal'
                    j = service.derivative(state, update, space) if space else None
                    results[device] = (state.prediction, j)
                    row[f'{device}_field_error'] = relative(state.prediction, reference.prediction)
                    if j is not None:
                        row[f'{device}_jacobian_error'] = relative(j, jref)
                        row[f'{device}_worst_column'] = column(j, jref)
                row['cuda_cpu_field_difference'] = relative(results['cuda'][0], results['cpu'][0])
                if space:
                    row['cuda_cpu_jacobian_difference'] = relative(results['cuda'][1], results['cpu'][1])
                rows.append(row)
                print(json.dumps(row), flush=True)
    return rows


def directional():
    acquisition = observations(np.zeros((24, 1)), [1e9])[0].acquisition
    update = ProjectedUpdate(.05)
    rows = []
    for name, path, K, M, *_ in FIXTURES[:2]:
        curve = resize(load_curve(path), K)
        space = update.prepare(curve, M, K)
        direction = np.random.default_rng(901).normal(size=space.derivatives.shape[1])
        direction /= np.linalg.norm(direction)
        observation = Observation(K25, acquisition, np.ones(24, complex), 2.5e9)
        service = ModalMuller(Execution(device='cuda', frequency_threads=1))
        exact = service.derivative(service.evaluate(curve, observation, 13.3, token(128)), update, space)@direction
        for step in [1e-6, 5e-7]:
            pair = [service.evaluate(update.trial(space, s*step*direction)[0], observation, 13.3, token(128)).prediction
                    for s in (-1, 1)]
            rows.append(dict(shape=name, K=K, M=M, K_trace=128, step_m=step, device='cuda',
                             relative_error=relative((pair[1]-pair[0])/(2*step), exact)))
            print(json.dumps(rows[-1]), flush=True)
    return rows


def main():
    part = sys.argv[1]
    rows = fields() if part == 'fields' else directional()
    sources = [Path(__file__), *sorted(Path('experiments/cleaned_interface').glob('modal_*.py'))]
    write(OUT/f'accuracy_{part}.json', dict(part=part, rows=rows, reference='independent nodal Kress, 2048 nodes, CPU',
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}))


if __name__ == '__main__':
    main()
