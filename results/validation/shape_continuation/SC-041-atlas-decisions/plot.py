"""Rebuild SC-041 recovery plots from saved results; no forward solves."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc

HERE = Path(__file__).resolve().parent
COLORS = {19: '#747b86', 22: '#1268ac', 25: '#b35d15'}


def read(path):
    return json.loads(path.read_text())


def main():
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for col, case in enumerate(('circle_to_star', 'kite')):
        ax, shape = axes[0, col], axes[1, col]
        truth = ast.curve_from(sc.read(ast.source_folder(case)/'truth.json')).values(4096)*sc.LENGTH*1e3
        shape.plot(truth.real, truth.imag, '--', color='#282b30', lw=1.2, label='Target (evaluation only)')
        paths = sorted((HERE/'runs'/case).glob('M*/result.json'))
        if not paths:
            ax.text(.5, .5, 'Continuation withheld by finite-step gate', ha='center', transform=ax.transAxes)
        for index, path in enumerate(paths):
            row = read(path)
            M = row['M']
            progress = read(path.parent/'progress.json')['states']
            work = [0]+[s['work']['work_units'] for s in progress]+[row['work']['work_units']]
            error = [row['initial_score']['rms_mm']]+[s['score']['rms_mm'] for s in progress]+[row['score']['rms_mm']]
            ax.semilogy(work, error, '-o', ms=3, lw=1.5, color=COLORS[M], label=f'M={M}')
            z = ast.curve_from(row['curve']).values(4096)*sc.LENGTH*1e3
            shape.plot(z.real, z.imag, color=COLORS[M], lw=1.2,
                       label=f"M={M}, RMS {row['score']['rms_mm']:.4g} mm")
            if index == 0:
                initial = ast.curve_from(read(path.parent/'configuration.json')['initial']).values(4096)*sc.LENGTH*1e3
                shape.plot(initial.real, initial.imag, ':', color='#8b5ba5', lw=1., label='Shared start')
        name = 'Star' if case == 'circle_to_star' else 'Kite'
        ax.set(title=f'{name}: accepted-state recovery', xlabel='New inverse work units', ylabel='RMS boundary error (mm)')
        ax.grid(alpha=.2)
        if paths:
            ax.legend(fontsize=9)
        shape.set(aspect='equal', xlabel='x relative to scene centre (mm)', ylabel='y (mm)')
        shape.grid(alpha=.15)
        shape.legend(fontsize=8)
    fig.suptitle('SC-041: fixed data and state band, different update bands', fontsize=14)
    fig.savefig(HERE/'comparison.png', dpi=170)
    fig.savefig(HERE/'comparison.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
