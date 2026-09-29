"""Resonance exposure of a frequency catalog: the scattering pole nearest to each frequency.

Newton on det T started just below each catalog wavenumber converges to the
pole that dominates tr(T^{-1} T') there, which is normally the nearest one.
For each frequency the record keeps the pole, its quality factor Q, the
relative distance |k - k*| / |k*| that enters the single-pole horizon law
(MA-001 A3: horizon ~ 0.1 |k - k*| / |k*| for dilation on the disk), and the
detuning |k - Re k*| / |Im k*| in half-linewidths. Every pole is qualified by
recomputing it at twice the node count.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.exposure --output <json>
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import warnings

import numpy as np

from experiments.modal_atlas import poles as P


def nearest_poles(curve, contrast, wavenumbers, nodes):
    base, fine = curve.nodes(nodes), curve.nodes(2 * nodes)
    rows = []
    for k in wavenumbers:
        pole = P.polish(base, contrast, complex(k, -1e-3 * k))
        check = P.polish(fine, contrast, pole.k, steps=8)
        rows.append(dict(k=float(k), pole_real=pole.k.real, pole_imag=pole.k.imag, quality=pole.quality,
                         relative_distance=abs(k - pole.k) / abs(pole.k),
                         half_linewidths=abs(k - pole.k.real) / abs(pole.k.imag),
                         sigma_ratio=pole.smallest_singular, newton_steps=pole.newton_steps,
                         refined_relative_shift=abs(check.k - pole.k) / abs(pole.k),
                         refined_sigma_ratio=check.smallest_singular))
    return rows


def _job(args):
    name, coefficients, contrast, wavenumbers, nodes = args
    from experiments.shape_continuation.geometry import FourierCurve
    warnings.simplefilter('ignore')
    return name, contrast, nearest_poles(FourierCurve(np.asarray(coefficients)), contrast, wavenumbers, nodes)


def main():
    from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
    from experiments.modal_atlas.contrast_screen import SC050, SCENES
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--contrasts', default='2,4,13.3')
    parser.add_argument('--nodes', type=int, default=256)
    parser.add_argument('--workers', type=int, default=9)
    args = parser.parse_args()
    wavenumbers = [float(o.wavenumber) for o in ast.catalog_only('circle_to_c')]
    jobs = []
    for scene in SCENES:
        curve = ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'truth.json'))
        for contrast in map(float, args.contrasts.split(',')):
            jobs.append((scene, curve.coefficients, contrast, wavenumbers, args.nodes))
    out = dict(nodes=args.nodes, wavenumbers=wavenumbers, rows=[])
    with ProcessPoolExecutor(args.workers) as pool:
        for name, contrast, rows in pool.map(_job, jobs):
            out['rows'].append(dict(scene=name, contrast=contrast, frequencies=rows))
            q = [r['quality'] for r in rows]
            print(name, contrast, 'median Q %.0f' % np.median(q),
                  'min rel dist %.2e' % min(r['relative_distance'] for r in rows), flush=True)
    Path(args.output).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
