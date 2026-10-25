"""Compare two saved runs of one TG-002 case: accepted curves, losses, work units and trial decisions."""
import json
import sys
from pathlib import Path

import numpy as np


def load(folder):
    folder = Path(folder)
    result = json.loads((folder/'result.json').read_text())
    accepted = json.loads((folder/'accepted.json').read_text())['states']
    stages = {}
    for row in result.get('stages', []):
        path = folder/f"{row['stage']}.json"
        if path.exists():
            stages[row['stage']] = json.loads(path.read_text())
    return result, accepted, stages


def curve(record):
    return np.asarray(record['real']) + 1j*np.asarray(record['imag'])


def main(a, b):
    ra, aa, sa = load(a)
    rb, ab, sb = load(b)
    print('outcome', ra['outcome'], rb['outcome'])
    print('recovered', ra.get('recovered'), rb.get('recovered'))
    print('fit units', ra['fit_and_localization_units'], rb['fit_and_localization_units'])
    print('total units', ra.get('total_units'), rb.get('total_units'))
    print('metrics a', ra.get('metrics'))
    print('metrics b', rb.get('metrics'))
    print('accepted states', len(aa), len(ab))
    worst = 0.
    for x, y in zip(aa, ab):
        if (x['stage'], x['iteration'], x['units']) != (y['stage'], y['iteration'], y['units']):
            print('first path difference', (x['stage'], x['iteration'], x['units']), (y['stage'], y['iteration'], y['units']))
            break
        cx, cy = curve(x['curve']), curve(y['curve'])
        worst = max(worst, float(np.max(np.abs(cx-cy))) if cx.shape == cy.shape else np.inf)
    print('largest accepted-curve coefficient difference over the common path', worst)
    print('bit-identical accepted curves', all(x['curve'] == y['curve'] for x, y in zip(aa, ab)) and len(aa) == len(ab))
    print('identical losses', [x['loss'] for x in aa] == [y['loss'] for y in ab])
    print('final curve identical', ra['final_curve'] == rb['final_curve'])
    statuses = lambda s: [(t.get('iteration'), t.get('backtrack'), t.get('status')) for t in s.get('trials', [])]
    same = all(statuses(sa[k]) == statuses(sb.get(k, {})) for k in sa)
    print('identical trial decisions in every stage', same and set(sa) == set(sb))
    print('stage work', [(k, sa[k]['work']['work_units'], sb.get(k, {}).get('work', {}).get('work_units')) for k in sa])


if __name__ == '__main__':
    main(*sys.argv[1:3])
