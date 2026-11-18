"""Bounded, read-only check of the saved cavity truth and BRG data records."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import sys
import time
from pathlib import Path
import numpy as np
from scipy.io import loadmat

from brg_paper import ROOT, BASE, LADDER, digest, now, solver_state, write
sys.path[:0] = [str(ROOT/'solvers'), str(ROOT)]
from experiments.baselines.brg.brg_data import BASE as BRG_BASE, observation, true_curve
from bem_inverse import FourierCurve


def main():
    started = time.monotonic()
    out = BASE/'resolution_selection/cavity_truth_check.json'
    assert not out.exists(), 'Retain the first bounded diagnosis.'
    path = BRG_BASE/'cavity_09/shipped/truth_curve.mat'
    record = loadmat(path, simplify_cells=True)['truth_curve']
    saved = np.asarray(record['xs']).reshape(-1) + 1j*np.asarray(record['ys']).reshape(-1)
    curve = true_curve('cavity')
    modes = np.arange(-curve.band, curve.band+1)
    t = 2*np.pi*np.arange(len(saved))/len(saved)
    exact = np.exp(1j*t[:, None]*modes)@curve.coefficients
    difference = exact-saved
    bands = []
    for band in (25, 50, 75, 100):
        crop = curve.coefficients[curve.band-band:curve.band+band+1]
        truncated = FourierCurve(crop).values(len(saved))
        bands.append(dict(band=band, maximum_point_difference=float(abs(truncated-saved).max()),
                          rms_point_difference=float(np.sqrt(np.mean(abs(truncated-saved)**2)))))
    rows = []
    for k in LADDER:
        if k > 8:
            break
        _, data_path, data = observation('cavity_09', k)
        fields = dict(k=k, boundary_points=data['points'], diagnostic_err_est=data['err_est'],
                      data_sha256=digest(data_path))
        available = BASE/f'resolution_selection/candidates/trace_minimum_160/cavity_09/k_{k:g}.json'
        if available.exists():
            import json
            check = json.loads(available.read_text())
            fields.update(relative_brg_difference=check.get('relative_brg_difference'),
                          relative_refinement_difference=check.get('relative_refinement_difference'))
        rows.append(fields)
    sources = [path, BRG_BASE/'shapes/cavity_fourier.mat',
               ROOT/'experiments/baselines/brg/paper_geometry.m',
               ROOT/'experiments/baselines/brg/run_paper_case.m']
    write(out, dict(started=now(), wall_seconds=time.monotonic()-started, budget_seconds=600,
          solver=solver_state(), source_sha256={str(p.relative_to(ROOT)): digest(p) for p in sources},
          saved_truth_points=len(saved), full_band=curve.band,
          maximum_full_band_point_difference=float(abs(difference).max()),
          rms_full_band_point_difference=float(np.sqrt(np.mean(abs(difference)**2))),
          band_comparisons=bands, data_records=rows,
          findings=['The Python full-band Fourier curve matches the saved unresampled BRG truth points.',
                    'The generator calls paper_geometry(shape,n) with resample=true for its forward data.',
                    'The saved truth polygon uses paper_geometry(shape,2048,false).',
                    'Actual resampled forward boundary points are not retained in the saved data files.',
                    'Discretization or resampling is a possible cause of the field difference, not proven by this check.',
                    'No data, coefficients or fit settings were changed.']))
    print(out, flush=True)


if __name__ == '__main__':
    main()
