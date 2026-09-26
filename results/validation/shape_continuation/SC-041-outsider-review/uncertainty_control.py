"""Part 4 follow-up control (uncertainty_plan.md): truth-curve information at the artefact sites."""
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('u', HERE/'uncertainty.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
from experiments.shape_continuation.geometry import arclength_angles


def arclength_position(curve, point, n=u.SAMPLES):
    z = u.analyse.arclength_series(curve, lambda nd: nd.points[:, 0] + 1j*nd.points[:, 1], n=2*n)[::2]
    return int(np.argmin(abs(z - point))), z


def main():
    listed = {s['id']: s for s in u.states()}
    rows = json.loads((HERE/'uncertainty.json').read_text())['rows']
    out = dict(plan='uncertainty_plan.md (follow-up control)', sites=[])
    maps = {}
    for case, n in (('kite', 768), ('deep_c', 512)):
        truth = u.truth_curve(case)
        maps[case], _ = u.ratio_map(truth, n, case)
        _, maps[case + '_z'] = arclength_position(truth, 0)
    for r in rows:
        if not r.get('spurious_sharpest') or r['case'] not in ('kite', 'deep_c'):
            continue
        s = listed[r['id']]
        curve = s['curve']
        kappa = np.load(HERE/'atlas_local'/f"uncertainty_{r['id']:02d}.npz")['kappa']
        j = int(np.argmax(np.abs(kappa)))
        z = u.analyse.arclength_series(curve, lambda nd: nd.points[:, 0] + 1j*nd.points[:, 1])[::2][j]
        i = int(np.argmin(abs(maps[r['case'] + '_z'] - z)))
        site = dict(id=r['id'], label=r['label'], set=r['set'])
        for name in u.PRIORS:
            t = maps[r['case']][name]
            site[name] = float(100*np.mean(t < t[i]))
        out['sites'].append(site)
    for name in u.PRIORS:
        out[name + '_median_percentile'] = float(np.median([s[name] for s in out['sites']]))
    m = [out[p + '_median_percentile'] for p in u.PRIORS]
    out['verdict'] = ('artefact sites intrinsically high-information' if all(x <= 25 for x in m) else
                      'inversion attributed to the artefact itself' if any(x >= 50 for x in m) else 'inconclusive')
    (HERE/'uncertainty_control.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
