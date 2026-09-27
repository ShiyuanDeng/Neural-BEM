"""Characterize CUDA-vs-archive drift in the SPD-013 two-object replays.

Per run: worst accepted-state and final coefficient difference relative to
max|c| over both components, and worst relative accepted/final loss difference.

    python drift.py REPLAY_DIR OUT.json
"""
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_multi import archive, jobs  # noqa: E402


def coefficients(state):
    return np.concatenate([np.array(c['real']) + 1j * np.array(c['imag']) for c in state['components']])


def main(replay, out):
    rows = {}
    for study, case, arm in jobs(['sc047', 'sc048']):
        a, b = (json.loads((p / 'unscored.json').read_text())
                for p in (archive(study, case, arm), Path(replay) / 'runs' / study / case / arm))
        states = [(x['state'], y['state']) for x, y in zip(a.get('accepted', a.get('states', [])),
                                                             b.get('accepted', b.get('states', [])))]
        states.append((a['final_state'], b['final_state']))
        coef = max(float(np.max(np.abs(coefficients(x) - coefficients(y))) / np.max(np.abs(coefficients(x))))
                   for x, y in states)
        losses = [(r['final_loss'], s['final_loss']) for r, s in zip(a['records'], b['records'])]
        loss = max(abs(x - y) / abs(x) for x, y in losses)
        rows[f'{study}/{case}/{arm}'] = dict(coefficients_relative_to_max=coef, dispatch_final_loss_relative=loss)
        print(study, case, arm, 'coef %.1e loss %.1e' % (coef, loss))
    Path(out).write_text(json.dumps(rows, indent=1))
    print('worst', {k: max(r[k] for r in rows.values()) for k in next(iter(rows.values()))})


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
