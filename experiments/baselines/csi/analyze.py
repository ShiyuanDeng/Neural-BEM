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
    figures = repo / 'docs/iterations/csi_adaptation/01_run_published_examples/figures'
    fig.savefig(figures / f'{run.name}_costs.png', dpi=150)
    (run / 'analysis.json').write_text(json.dumps(dict(methods=results, threshold=None), indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
