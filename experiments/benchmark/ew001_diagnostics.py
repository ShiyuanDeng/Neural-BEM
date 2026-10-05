"""EW-001 registered independent heat-time near controls and saved-spectrum attribution.

No new grids, cutoffs, splits, candidate corrections or forward services.
"""
import json
from time import perf_counter
import numpy as np
from bem_inverse.on003_circle_reference import heat_circle
from .ew001 import OUT, ROOT, SPLITS, read, provenance
from .on003 import digest, write


def main():
    started = perf_counter()
    manifest = read(OUT / 'manifest.json')
    coefficients = manifest['states'][0]['coefficients']
    radius = abs(complex(coefficients['real'][-1], coefficients['imag'][-1])) * manifest['states'][0]['length_unit_m']
    controls, rows, arrays = [], [], {}
    for xi in SPLITS:
        phase = OUT / f'stage_A_xi{xi}'
        receipt = read(phase / 'receipt.json')
        labels = read(phase / 'near_and_flat_controls.json')['wave_order']
        indices = {label: i for i, label in enumerate(labels)}
        tau = receipt['grids'][0]['tau_m2']
        heat = {}
        with np.load(phase / 'grid256_arrays.npz') as saved:
            modes = saved['modes']
            for index, label in enumerate(labels):
                k = complex(*map(float, label.split(',')))
                first = heat_circle(radius, k, tau, modes, 256)
                second = heat_circle(radius, k, tau, modes, 512)
                heat[label] = second
                delta = abs(saved[f'near_{index}'] - second)
                controls.append(dict(xi_over_kstar=xi, wavenumber_per_m=[k.real, k.imag],
                      heat_256_512_max_difference=float(np.max(abs(first-second))),
                      angular4096_vs_heat512_absolute_by_block=[float(np.max(r)) for r in delta]))
                arrays[f'heat256_xi{xi}_wave{index}'] = first
                arrays[f'heat512_xi{xi}_wave{index}'] = second
        for grid in (128, 256):
            with np.load(phase / f'grid{grid}_arrays.npz') as saved:
                for row in (r for r in receipt['rows'] if r['grid'] == grid):
                    o, i = indices[row['exterior']], indices[row['interior']]
                    reference = saved[f'exact_{o}']-saved[f'exact_{i}']
                    true_near = heat[row['exterior']]-heat[row['interior']]
                    near = saved[f'near_{o}']-saved[f'near_{i}']
                    far = saved[f'far_{o}']-saved[f'far_{i}']
                    near_error = near-true_near
                    far_error = far-(reference-true_near)
                    b = dict(V=0, K=1, Kprime=1, T=2)[row['block']]
                    use = abs(modes) <= row['trace_cutoff']
                    norm = max(float(np.max(abs(reference[b, use]))), 1e-14)
                    total = near_error+far_error
                    direct = (saved[f'near_{o}']+saved[f'far_{o}']-saved[f'near_{i}']-saved[f'far_{i}'])-reference
                    np.testing.assert_allclose(total, direct, rtol=0, atol=1e-12)
                    worst = int(np.argmax(abs(direct[b, use])))
                    mode = int(modes[use][worst])
                    j = int(np.flatnonzero(modes == mode)[0])
                    rows.append(dict(xi_over_kstar=xi, contrast=row['contrast'], frequency_hz=row['frequency_hz'],
                          kind=row['kind'], grid=grid, trace_cutoff=row['trace_cutoff'], block=row['block'],
                          total_normalized_error=row['normalized_max_diagonal_error'], worst_mode=mode,
                          near_normalized_error_at_total_worst=float(abs(near_error[b, j])/norm),
                          far_normalized_error_at_total_worst=float(abs(far_error[b, j])/norm),
                          near_max_normalized_error=float(np.max(abs(near_error[b, use]))/norm),
                          far_max_normalized_error=float(np.max(abs(far_error[b, use]))/norm),
                          component_cancellation_at_total_worst=float((abs(near[b,j])+abs(far[b,j]))/max(abs(reference[b,j]), 1e-30))))
    maxima = []
    for xi in SPLITS:
        for block in ('V', 'K', 'Kprime', 'T'):
            subset = [r for r in rows if r['xi_over_kstar'] == xi and r['grid'] == 256 and r['trace_cutoff'] == 128 and r['block'] == block]
            maxima.append(max(subset, key=lambda r:r['total_normalized_error']))
    np.savez_compressed(OUT / 'independent_heat_arrays.npz', **arrays)
    result = dict(experiment='EW-001', stage='Q1 independent near checks and error attribution',
                  seconds=perf_counter()-started, controls=controls, rows=rows, worst_256_cutoff128=maxima,
                  diagnostic_source_sha256=digest(ROOT / 'experiments/benchmark/ew001_diagnostics.py'),
                  **provenance(),
                  scope='saved registered splits/grids; independent heat orders 256/512 unchanged; no candidate repair')
    write(OUT / 'near_error_attribution.json', result)
    print(json.dumps(maxima, indent=2))


if __name__ == '__main__':
    main()
