"""Evaluation-only probes of complex-frequency damping (motivating MA-004; no inverse runs).

horizon: the contrast-4 C warm-up endpoint from MA-002, at 0.5 GHz with the
wavenumber moved to k + i beta; per-harmonic 10% linearization horizons at
contrasts 0.5 (beta = 0), 4 and 13.3.

localization: SC-050's circle-localization objective on MA-002's dense grid at
contrast 13.3, with the exact truth data evaluated at k (1 + i gamma), for
gamma = 0, 0.25, 0.5. The truth enters only as the synthetic data source, as it
does for every observation, and for scoring against the equivalent circle.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.damped_probe horizon
    PYTHONPATH=solvers:. python -m experiments.modal_atlas.damped_probe localization
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from types import SimpleNamespace
import warnings

import numpy as np

OUTFILE = 'results/validation/modal_atlas/MA-003/probe_damped_{}.json'
AMPLITUDES = np.geomspace(1e-5, 0.3, 24)


def _horizon_job(args):
    contrast, beta = args
    warnings.simplefilter('ignore')
    from experiments.shape_continuation import atlas_strategy_tests as ast
    from experiments.modal_atlas import damped
    from experiments.modal_atlas.contrast_screen import OUT
    curve = ast.curve_from(json.loads((OUT / 'runs/c4/development_c/warmup_025.json').read_text())['curve'])
    obs = ast.catalog_only('circle_to_c')[2]
    rows = damped.horizons(curve, obs.wavenumber + 1j * beta, contrast, obs.acquisition, 6, AMPLITUDES)
    return dict(contrast=contrast, beta=beta, k=float(obs.wavenumber), rows=rows)


def horizon(workers):
    jobs = [(0.5, 0.0)] + [(4.0, b) for b in (0.0, 0.1, 0.25, 0.5, 1.0)] + [(13.3, b) for b in (0.0, 0.25, 0.5, 1.0)]
    with ProcessPoolExecutor(workers) as pool:
        result = list(pool.map(_horizon_job, jobs))
    for r in result:
        print(r['contrast'], r['beta'], [f"{x['horizon']:.2e}" for x in r['rows']], flush=True)
    with open(OUTFILE.format('horizon'), 'w') as handle:
        json.dump(dict(state='MA-002 runs/c4/development_c warmup_025 curve', amplitudes=AMPLITUDES.tolist(),
                       results=result), handle, indent=1)


def localization(workers):
    from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
    from experiments.modal_atlas import damped, mie_localize as ml
    from experiments.modal_atlas.diagnose import dense_grid
    from experiments.modal_atlas.contrast_screen import SC050, SCENES
    warnings.simplefilter('ignore')
    centers_m, radii_m, centers, radii, inside = dense_grid()
    catalog = ast.catalog_only('circle_to_c')[:3]
    out = []
    for scene in SCENES:
        truth = ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'truth.json'))
        z = truth.values(4096)
        area = abs(0.5 * np.imag(np.sum(np.conj(z) * np.roll(z, -1))))
        cen, req = np.mean(z) * sc.LENGTH + sc.CENTER, np.sqrt(area / np.pi) * sc.LENGTH
        for gamma in (0.0, 0.25, 0.5):
            obs = [SimpleNamespace(wavenumber=o.wavenumber * (1 + 1j * gamma), acquisition=o.acquisition,
                                   scattered=damped.solve(truth, o.wavenumber * (1 + 1j * gamma), 13.3,
                                                          o.acquisition, 1024).prediction) for o in catalog]
            cut = int(np.ceil(abs(obs[-1].wavenumber) * np.sqrt(13.3) * radii.max() + 30))
            L = np.concatenate([ml.landscape(obs, 13.3, centers[i:i + 800], radii, cutoff=cut)
                                for i in range(0, len(centers), 800)])
            L = np.where(inside, L, np.inf)
            i, j = np.unravel_index(np.argmin(L), L.shape)
            row = dict(scene=scene, gamma=gamma, optimum=[centers_m[i].real, centers_m[i].imag, radii_m[j]],
                       loss=float(L[i, j]), centre_error_mm=float(abs(centers_m[i] - cen) * 1000),
                       equivalent_circle=[cen.real, cen.imag, req])
            out.append(row)
            print(row, flush=True)
    with open(OUTFILE.format('localization'), 'w') as handle:
        json.dump(dict(contrast=13.3, grid='MA-002 diagnose.dense_grid', results=out), handle, indent=1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=('horizon', 'localization'))
    parser.add_argument('--workers', type=int, default=10)
    args = parser.parse_args()
    globals()[args.part](args.workers)
