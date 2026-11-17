"""Summarize native CSI logs and raw contrast arrays, without a support rule."""
import argparse
import csv
import json
import os
from pathlib import Path
import re

os.environ.setdefault('MPLCONFIGDIR', '/tmp/csi-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from scipy.special import hankel1

NAMES = {'CCCSI': 'MF-CC-CSI', 'MRCSI': 'MF-MR-CSI', 'CSI': 'CSI'}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    run = args.run
    rows = []
    method = None
    for line in (run / 'matlab.log').read_text().splitlines():
        match = re.match(r'^(CCCSI|MRCSI|CSI)-MF iteration starts', line)
        if match:
            method = NAMES[match[1]]
        if method and re.match(r'^\s+\d+\s+[-\d.]+e[+-]\d+', line):
            values = [float(x) for x in line.split()]
            rows.append(dict(method=method, iteration=int(values[0]), FS=values[1], FD=values[2],
                             FC=values[3], reported_cost=values[4], initial_guess_distance=values[5]))
    with (run / 'cost_history.csv').open('w') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    data = loadmat(run / 'reconstruction.mat', simplify_cells=True)
    summary = json.loads((run / 'matlab_summary.json').read_text())
    # Export the exact single-receiver source normalization used upstream.
    calibration = []
    raw = data['rawdat']
    para = data['para']
    for frequency, omega in zip(data['fre'], data['csi_pars']['omega']):
        table = raw[raw[:, 2] == frequency]
        count = len(table) // int(para['NTX'])
        selected = table[count // 2::count]
        tx, rx = np.deg2rad(selected[:, 0]), np.deg2rad(selected[:, 1])
        dx = para['Rr'] * np.cos(rx) - para['Tr'] * np.cos(tx)
        dy = para['Rr'] * np.sin(rx) - para['Tr'] * np.sin(tx)
        distance = np.hypot(dx, dy)
        k = omega / para['m_unit']
        if 'TM' in summary['case_name']:
            unit_incident = omega / 4 * hankel1(0, -k * distance + 0j) * omega**2 / (-1j * omega)
        else:  # PT.TE, measured tangential electric field
            radial = 1j * k / 4 * hankel1(1, -k * distance + 0j) / (distance + np.finfo(float).eps)
            unit_incident = -dy * radial * np.cos(rx + np.pi / 2) + dx * radial * np.sin(rx + np.pi / 2)
        measured = selected[:, 5] + 1j * selected[:, 6]
        factors = measured / unit_incident
        for source, factor in enumerate(factors, 1):
            calibration.append(dict(frequency_GHz=float(frequency), source=source,
                                    receiver_within_source_1based=count // 2 + 1,
                                    source_angle_deg=float(selected[source-1, 0]),
                                    receiver_angle_deg=float(selected[source-1, 1]),
                                    normalized_omega=float(omega), factor_real=float(factor.real),
                                    factor_imag=float(factor.imag)))
    with (run / 'source_calibration.csv').open('w') as file:
        writer = csv.DictWriter(file, fieldnames=list(calibration[0]))
        writer.writeheader()
        writer.writerows(calibration)
    results = []
    fig, ax = plt.subplots(figsize=(6, 4), layout='constrained')
    for index, seconds in enumerate(summary['time_seconds'], 1):
        name = list(NAMES.values())[index - 1]
        costs = [r['reported_cost'] for r in rows if r['method'] == name]
        fields = data[f'chi{index}']
        final = np.asarray(fields[-1])
        conductivity = -final.imag * 1000 * float(data['normlz_factor'])
        result = dict(method=name, native_seconds=seconds, seconds_per_iteration=seconds / len(costs),
                      iterations=len(costs), first_reported_cost=costs[0], last_reported_cost=costs[-1],
                      cost_increases=int(np.sum(np.diff(costs) > 0)),
                      all_finite=bool(all(np.isfinite(np.asarray(f)).all() for f in fields)),
                      final_frequency_real_range=[float(final.real.min()), float(final.real.max())],
                      final_frequency_conductivity_mSm_range=[float(conductivity.min()), float(conductivity.max())])
        results.append(result)
        ax.semilogy(range(1, len(costs) + 1), costs, label=name)
    ax.set(xlabel='Iteration', ylabel='Native reported cost', title=summary['case_name'])
    ax.legend()
    ax.grid(alpha=.2)
    repo = Path(__file__).resolve().parents[3]
    launch = json.loads((run / 'launch.json').read_text())
    figures = repo / launch.get('activity', 'docs/iterations/csi_adaptation/01_run_published_examples') / 'figures'
    fig.savefig(figures / f'{run.name}_costs.png', dpi=150)
    compact = run / 'final_contrast.mat'
    compact_equal = None
    if compact.exists():
        kept = loadmat(compact, simplify_cells=True)
        compact_equal = all(np.array_equal(np.asarray(x), np.asarray(y))
                            for index in range(1, len(results) + 1)
                            for x, y in zip(data[f'chi{index}'], kept[f'chi{index}']))
        assert compact_equal, 'Compact scoring contrasts differ from the full workspace'
    if len(results) == 2:
        paper, axes = plt.subplots(2, 2, figsize=(8, 8), layout='constrained')
        shape = tuple(int(x) for x in data['csi_pars']['Ninv'][:2])
        border = np.asarray(data['csi_pars']['rchiTV'], dtype=int) - 1
        dx = float(data['para']['m_unit']) * 1000
        extent = [data['yinv'][0]-dx/2, data['yinv'][-1]+dx/2,
                  data['xinv'][-1]+dx/2, data['xinv'][0]-dx/2]
        for index, result in enumerate(results, 1):
            values = np.asarray(data[f'chi{index}'][-1]).copy()
            values[border] = 0  # reproduce their display mask; not a scoring threshold
            image = values.reshape(shape, order='F')
            real_peak = np.unravel_index(np.argmax(image.real), shape)
            result['native_display_real_peak'] = float(image.real.max())
            result['native_display_peak_xy_mm'] = [float(data['yinv'][real_peak[1]]),
                                                    float(data['xinv'][real_peak[0]])]
            for column, array in enumerate((image.real, -image.imag * 1000 * data['normlz_factor'])):
                ax = axes[index-1, column]
                top = float(np.max(array))
                panel = ax.imshow(array, origin='upper', extent=extent, cmap='jet', interpolation='nearest',
                                  vmin=0, vmax=top if top > 0 else 1)
                ax.set(xlabel='Native x / mm', ylabel='Native y / mm',
                       title=result['method'] + (' : real contrast' if column == 0 else ' : conductivity (mS/m)'))
                paper.colorbar(panel, ax=ax, shrink=.8)
        paper.suptitle('FoamTwinDielTM, 7-10 GHz, 2048 iterations\nNative orientation and display mask; raw contrasts saved separately')
        paper.savefig(figures / f'{run.name}_contrasts.png', dpi=150)
    (run / 'analysis.json').write_text(json.dumps(dict(methods=results, threshold=None,
                                                     compact_matches_full_workspace=compact_equal), indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
