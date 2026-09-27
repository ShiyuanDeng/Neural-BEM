"""Export part-2 atlas states along three trajectories for the 3D atlas page (no solves)."""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SHOW, LOW = 24, -4
TRACKS = {
    'star': ('Star · SC-040 pipeline, then M 25 → 31 → 37 (K = 64 after M 25)',
             ['SC040/circle_to_star', 'SC041/star/M25', 'review/star/M31_K64', 'review/star/M37_K64']),
    'kite': ('Kite · recorded path into SC-041 M 22 (flank artefact forms)',
             ['F_released_m/kite', 'SC041/kite/M22']),
    'kite_clean': ('Kite · clean K = 64 refit, then M 28',
                   ['review/kite/refit_K64', 'review/kite/M28_K64']),
}


def main():
    index = {r['id']: r for r in json.loads((HERE/'atlas_index.json').read_text())['rows']}
    rows = {r['id']: r for r in json.loads((HERE/'atlas_analysis.json').read_text())['rows']}
    out = dict(ghz=[0.25 + 0.125*i for i in range(19)], orders=SHOW, low=LOW, tracks={})
    for key, (title, parts) in TRACKS.items():
        states = []
        for part in parts:
            ids = sorted(i for i, r in index.items() if r['track'] == part)
            for i in ids:
                heat = np.load(HERE/'atlas_local'/f'{i:03d}.npz')['heat'][:SHOW+1]
                log = np.log10(np.maximum(heat, 10.0**LOW))
                a, r = index[i], rows[i]
                states.append(dict(id=i, track=part, stage=str(a['stage']), iteration=a['iteration'], M=a['M'],
                                   K=a.get('K'), active=a['active'], heat=np.round(log, 3).tolist(),
                                   loss=r['loss'], rms=r['rms_mm'], hausdorff=r['hausdorff_mm'],
                                   radius=r['min_radius_mm'], inside=r['inside']))
        out['tracks'][key] = dict(title=title, states=states)
    (HERE/'atlas3d.json').write_text(json.dumps(out, separators=(',', ':')))
    print({k: len(v['states']) for k, v in out['tracks'].items()}, (HERE/'atlas3d.json').stat().st_size)


if __name__ == '__main__':
    main()
