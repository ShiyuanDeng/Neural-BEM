"""Fields, Jacobians and complete-trial derivatives of modal_muller against 2048-node Kress.

These are the fixtures of the independent Chebyshev review, evaluated through the
maintained service at its own resolution tokens (window = K_trace + 64). The
review prototype's recorded errors are copied beside each row for comparison.
Usage: accuracy.py {c|endpoint|damped|directional}
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

REVIEW = Path('results/validation/cleaned_interfaces/chebyshev-review-20260930')
sys.path.insert(0, str(REVIEW.resolve()))
from integration_checks import load_curve, nodal_state  # independent nodal reference, complex k included
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


def relative(a, b):
    return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review_rows(part):
    name = 'directional.json' if part == 'directional' else f'integration_{part}.json'
    return json.loads((REVIEW/name).read_text())['rows']


def fields(part):
    acquisition = observations(np.zeros((24, 1)), [1e9])[0].acquisition
    if part == 'endpoint':
        curve, frequencies, cutoffs, band, damping = load_curve(ENDPOINT), [1.25e9, 2.5e9], [96, 128], 67, 0.
    elif part == 'c':
        curve, frequencies, cutoffs, band, damping = resize(load_curve(C_TRUTH), 24), [1e9, 2.5e9], [64, 96], 24, 0.
    else:
        curve, frequencies, cutoffs, band, damping = load_curve(C_TRUTH), [.5e9, 1e9, 2.5e9], [64, 96], None, .25
    update = ProjectedUpdate(.05)
    space = update.prepare(curve, band, curve.band) if band else None
    previous = review_rows(part)
    rows = []
    for frequency in frequencies:
        k = K25*frequency/2.5e9*(1+1j*damping)
        k = k.real if not damping else k
        reference = nodal_state(curve, k, 13.3, acquisition, 2048)
        check = nodal_state(curve, k, 13.3, acquisition, 1024)
        jref = F.shape_jacobian(reference, update.velocities(space, reference.curve)) if space else None
        for cutoff in cutoffs:
            service = ModalMuller(Execution(device='cpu', frequency_threads=1))
            state = service.evaluate(curve, Observation(k, acquisition, reference.prediction, frequency), 13.3, token(cutoff))
            row = dict(part=part, frequency_hz=frequency, damping=damping, K=curve.band, M=band, K_trace=cutoff,
                       window=state.diagnostics['window'], field_error=relative(state.prediction, reference.prediction),
                       oracle_1024_2048=relative(check.prediction, reference.prediction),
                       diagnostics=state.diagnostics, stage_seconds=service.receipt()['stage_seconds'])
            if space is not None:
                j = service.derivative(state, update, space)
                row.update(jacobian_error=relative(j, jref), worst_column=float(np.max(
                    np.linalg.norm(j-jref, axis=0)/np.linalg.norm(jref, axis=0))))
            match = [r for r in previous if r['frequency_hz'] == frequency and r['cutoff'] == cutoff]
            if match:
                row['review_prototype'] = {k: match[0].get(k) for k in ('bandwidth', 'data_error', 'jacobian_error', 'worst_column')}
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in ('diagnostics', 'stage_seconds')}), flush=True)
    return rows


def directional():
    acquisition = observations(np.zeros((24, 1)), [1e9])[0].acquisition
    update = ProjectedUpdate(.05)
    previous = review_rows('directional')
    rows = []
    for name, path, M, K in [('C', C_TRUTH, 24, 24), ('DF_endpoint', ENDPOINT, 67, 192)]:
        curve = resize(load_curve(path), K)
        space = update.prepare(curve, M, K)
        direction = np.random.default_rng(901).normal(size=space.derivatives.shape[1])
        direction /= np.linalg.norm(direction)
        observation = Observation(K25, acquisition, np.ones(24, complex), 2.5e9)
        service = ModalMuller(Execution(device='cpu', frequency_threads=1))
        exact = service.derivative(service.evaluate(curve, observation, 13.3, token(128)), update, space)@direction
        for step in [1e-6, 5e-7]:
            pair = [service.evaluate(update.trial(space, s*step*direction)[0], observation, 13.3, token(128)).prediction
                    for s in (-1, 1)]
            row = dict(shape=name, K=K, M=M, K_trace=128, window=192, step_m=step,
                       relative_error=relative((pair[1]-pair[0])/(2*step), exact))
            match = [r for r in previous if r['shape'] == name and r['step_m'] == step]
            if match:
                row['review_prototype'] = dict(bandwidth=match[0]['bandwidth'], relative_error=match[0]['relative_error'])
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def main():
    part = sys.argv[1]
    assert part in ('c', 'endpoint', 'damped', 'directional')
    rows = directional() if part == 'directional' else fields(part)
    sources = [Path(__file__), *sorted(Path('experiments/cleaned_interface').glob('modal_*.py')), REVIEW/'integration_checks.py']
    write(OUT/f'accuracy_{part}.json', dict(part=part, rows=rows, reference='independent nodal Kress, 2048 nodes, CPU',
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        source_hashes={str(p): digest(p) for p in sources}))


if __name__ == '__main__':
    main()
