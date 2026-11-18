"""Information only, never fed to a fit: do the measured data support a 15 mm, eps 3 cylinder?

1. Exact series for r 15 mm, eps 3 at the GPU fit's centre: residual per frequency.
2. Least-squares exact-series circle (centre x, y, radius, permittivity) on all eight
   frequencies, with the fit's per-frequency scaling (each frequency divided by its data norm,
   equal weights), started from the nominal and from the fitted cylinder.
3. Per-stage table of the GPU fit from its saved stage receipts.
"""
from csi_runtime import ROOT, provenance  # noqa: E402  first: pins threads
import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from bem_inverse import FourierCurve
from bem_inverse.io import curve_from
import csi_data as D
from csi_forward_check import exact_circle

MM = 1e-3/D.LENGTH_M        # package units per mm


def circle(x_mm, y_mm, r_mm):
    return FourierCurve.circle(r_mm*MM, complex(x_mm, y_mm)*MM)


def per_frequency(real, params):
    x, y, r, eps = params
    curve = circle(x, y, r)
    return [float(np.linalg.norm(exact_circle(curve, eps, o)-o.scattered)/np.linalg.norm(o.scattered)) for o in real]


def loss(relative):
    """The fit's B5 loss: half the sum of squared relative residuals, equal weights 1/F."""
    return .5*float(np.mean(np.square(relative)))


def least_squares_circle(real, start):
    weights = np.sqrt(1./len(real))

    def residual(params):
        x, y, r, eps = params
        curve = circle(x, y, r)
        parts = []
        for o in real:
            d = (exact_circle(curve, eps, o)-o.scattered)/np.linalg.norm(o.scattered)*weights
            parts += [d.real, d.imag]
        return np.concatenate(parts)
    started = time.perf_counter()
    result = least_squares(residual, start, bounds=([-100, -100, 1, 1.01], [100, 100, 60, 20]),
                           x_scale=[1, 1, 1, .1], max_nfev=400)
    relative = per_frequency(real, result.x)
    return dict(start=dict(zip(('x_mm', 'y_mm', 'radius_mm', 'permittivity'), map(float, start))),
                end=dict(zip(('x_mm', 'y_mm', 'radius_mm', 'permittivity'), map(float, result.x))),
                loss=loss(relative), relative_residual=relative, status=int(result.status),
                message=result.message, evaluations=int(result.nfev), seconds=time.perf_counter()-started)


def stage_table(fit_path):
    from experiments.comparison.scoring import region
    out = []
    for stage in json.loads(Path(fit_path).read_text())['stages']:
        found, _ = region([D.LENGTH_M*curve_from(stage['curve']).values(16384)])
        out.append(dict(stage=stage['stage'], M=stage['M'], accepted_steps=stage['accepted_steps'],
                        equivalent_radius_mm=float(1e3*np.sqrt(found.area/np.pi)),
                        permittivity=float(stage['contrast']),
                        centre_mm=[float(1e3*found.centroid.x), float(1e3*found.centroid.y)],
                        loss_at_end=float(stage['final_loss']), loss_at_entry=float(stage['initial_loss']),
                        frequencies=stage.get('frequencies_hz')))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fit', required=True, help='GPU fit.json of dielTM_dec8f')
    parser.add_argument('--fit-metrics', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit('Evidence exists; not overwriting.')
    started = time.perf_counter()
    real, _, source = D.observations(D.MEASURED)
    fitted = json.loads(Path(args.fit_metrics).read_text())
    centre = fitted['score']['centre_mm']
    fit_relative = list(fitted['final_residual'].values())
    nominal = (0., 30., 15., 3.)
    fitted_start = (centre[0], centre[1], fitted['score']['equivalent_radius_mm'], fitted['contrast'])
    record = dict(
        note='Information only: data and exact series; never fed to a fit.', input=source, provenance=provenance(),
        scaling='each frequency divided by its data norm, equal weights 1/8; loss = half the mean squared relative residual',
        bem_fit=dict(params=dict(zip(('x_mm', 'y_mm', 'radius_mm', 'permittivity'), fitted_start)),
                     relative_residual=fit_relative, loss=loss(fit_relative)),
        nominal=dict(params=dict(zip(('x_mm', 'y_mm', 'radius_mm', 'permittivity'), nominal)),
                     relative_residual=per_frequency(real, nominal), loss=loss(per_frequency(real, nominal))),
        nominal_size_at_fitted_centre=dict(
            params=dict(x_mm=centre[0], y_mm=centre[1], radius_mm=15., permittivity=3.),
            relative_residual=per_frequency(real, (centre[0], centre[1], 15., 3.)),
            loss=loss(per_frequency(real, (centre[0], centre[1], 15., 3.)))),
        least_squares=dict(from_nominal=least_squares_circle(real, nominal),
                           from_bem_fit=least_squares_circle(real, fitted_start)),
        gpu_stages=stage_table(args.fit))
    record['seconds'] = time.perf_counter()-started
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1)+'\n')
    print(json.dumps({k: v for k, v in record.items() if k not in ('provenance', 'input')}, indent=1)[:9000])


if __name__ == '__main__':
    main()
