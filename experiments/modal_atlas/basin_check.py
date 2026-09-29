"""Evaluation-only: is a stalled stage a wrong basin or a band-capacity limit?

For each prefix stage of a saved MA-003 attempt, compare the stage objective at
the stage's end state with the objective of the truth truncated to the stage's
stored band K (least-squares Fourier truncation), on 1,024 nodes.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.basin_check band 4.0 development_c
"""
import json
import sys
import warnings

import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.forward import solve
from experiments.shape_continuation.geometry import FourierCurve
from experiments.modal_atlas.contrast_screen import SC050
from experiments.modal_atlas.repair_screen import OUT, fitting_data


def main(arm, contrast, scene):
    warnings.simplefilter('ignore')
    folder = OUT / 'runs' / arm / f'c{contrast:g}' / scene
    catalog, _ = fitting_data(contrast, scene)
    lookup = {round(o.wavenumber, 9): o for o in catalog}
    truth = ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'truth.json'))

    def loss(curve, stage):
        values = []
        for k in stage['wavenumbers']:
            o = lookup[round(k, 9)]
            pred = solve(curve, o.wavenumber, contrast, o.acquisition, 1024).prediction
            values.append((np.linalg.norm(pred - o.scattered) / np.linalg.norm(o.scattered)) ** 2)
        return 0.5 * float(np.average(values, weights=stage['weights']))

    rows = []
    for stage in sc.read(folder / 'configuration.json')['stages'][1:6]:
        path = folder / f"{stage['label']}.json"
        if not path.exists():
            break
        end = ast.curve_from(sc.read(path)['curve'])
        limited = FourierCurve.from_samples(truth.values(8192), stage['curve_modes'])
        rows.append(dict(stage=stage['label'], M=stage['update_modes'], K=stage['curve_modes'],
                         end_loss=loss(end, stage), band_limited_truth_loss=loss(limited, stage),
                         truth_loss=loss(truth, stage)))
        print(rows[-1], flush=True)
    target = OUT / f'basin_check_{arm}_c{contrast:g}_{scene}.json'
    target.write_text(json.dumps(dict(arm=arm, contrast=contrast, scene=scene, rows=rows), indent=1))


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]), sys.argv[3])
