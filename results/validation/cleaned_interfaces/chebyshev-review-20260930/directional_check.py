"""Complete-trial finite differences, independent of nodal Hadamard agreement."""
import hashlib
import json
from pathlib import Path

import numpy as np

from integration_checks import ArrayGeometry, native, load_curve
from verify import OUTPUT, relative
from experiments.cleaned_interface.geometry import ProjectedUpdate, resize
from experiments.shape_continuation.atlas_cases import observations


def main():
    acq = observations(np.zeros((24, 1)), [1e9])[0].acquisition
    update = ProjectedUpdate(.05)
    rows = []
    for name, path, band, M, K in [
        ('C', 'results/validation/shape_continuation/SC-050-localization-robustness/inputs/development_c/truth.json', 128, 24, 24),
        ('DF_endpoint', 'results/validation/modal_atlas/MA-005/runs/DF/c13.3/shifted_rotated_c/fixed_M67.json', 160, 67, 192),
    ]:
        curve = resize(load_curve(path), K)
        space = update.prepare(curve, M, K)
        direction = np.random.default_rng(901).normal(size=space.derivatives.shape[1])
        direction /= np.linalg.norm(direction)
        ko = 6.417188604442469
        prepared = ArrayGeometry(curve, band)
        _, jac, _ = native(prepared, ko, 13.3, acq, 128, space)
        exact = jac@direction
        for step in [1e-6, 5e-7]:
            pair = []
            for sign in [-1, 1]:
                trial, _ = update.trial(space, sign*step*direction)
                prediction, _, _ = native(ArrayGeometry(trial, band), ko, 13.3, acq, 128)
                pair.append(prediction)
            fd = (pair[1]-pair[0])/(2*step)
            row = dict(shape=name, contrast=13.3, frequency_ghz=2.5, cutoff=128,
                       bandwidth=band, step_m=step, relative_error=relative(fd, exact))
            rows.append(row)
            print(json.dumps(row), flush=True)
    result = dict(rows=rows, source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [Path(__file__), OUTPUT/'verify.py', OUTPUT/'integration_checks.py']})
    (OUTPUT/'directional.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
