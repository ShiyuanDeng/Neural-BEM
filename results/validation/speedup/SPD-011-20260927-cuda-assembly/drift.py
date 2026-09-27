"""Characterize CUDA-vs-archive drift in the SPD-011 trajectory replays.

Per case: worst relative accepted-state loss difference, worst accepted-curve
coefficient difference relative to max|c|, and the per-field worst leaf-wise
relative differences with the magnitude at which they occur.

    python drift.py REPLAY_DIR OUT.json
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
ARCHIVE = ROOT / 'results/validation/shape_continuation/SC-043-prospective-band/runs'
CASES = ('wrong_circle', 'circle_to_star', 'circle_to_c', 'kite', 'peanut', 'hook')


def leaves(a, b, path, worst):
    if isinstance(a, dict):
        for key in a:
            if key != 'seconds':
                leaves(a[key], b[key], f'{path}/{key}', worst)
    elif isinstance(a, list):
        for x, y in zip(a, b):
            leaves(x, y, path, worst)
    elif isinstance(a, (int, float)) and not isinstance(a, bool) and a != b:
        relative = abs(a - b) / max(abs(a), abs(b))
        old = worst.get(path, dict(relative=0.0, magnitude=0.0))
        worst[path] = dict(relative=max(old['relative'], relative), magnitude=max(old['magnitude'], abs(a)))


def main(replay, out):
    rows = {}
    for case in CASES:
        runs = [root / case / 'fixed' for root in (ARCHIVE, Path(replay) / 'runs')]
        states = [json.loads((r / 'accepted.json').read_text())['states'] for r in runs]
        coefficients = lambda s: np.array(s['curve']['real']) + 1j * np.array(s['curve']['imag'])
        worst = {}
        for name in ('block_1.json', 'block_2.json', 'block_3.json'):
            leaves(*(json.loads((r / name).read_text()) for r in runs), name, worst)
        rows[case] = dict(
            accepted_loss_relative=max(abs(a['loss'] - b['loss']) / abs(a['loss']) for a, b in zip(*states)),
            accepted_coefficients_relative_to_max=max(
                float(np.max(np.abs(coefficients(a) - coefficients(b))) / np.max(np.abs(coefficients(a))))
                for a, b in zip(*states)),
            worst_leaf_fields=dict(sorted(worst.items(), key=lambda kv: -kv[1]['relative'])[:8]))
        print(case, json.dumps({k: v for k, v in rows[case].items() if k != 'worst_leaf_fields'}))
    Path(out).write_text(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
