"""MA-001 summary figure from circle.json and noncircular_analysis.json."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BLUE, ORANGE, INK, MUTED, SURFACE = '#2a78d6', '#eb6834', '#0b0b0b', '#52514e', '#fcfcfb'


def main(folder):
    folder = Path(folder)
    circle = json.loads((folder / 'circle.json').read_text())
    bie = json.loads((folder / 'noncircular_analysis.json').read_text())
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                         'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), facecolor=SURFACE)
    ax = axes[0]
    for contrast, colour in ((0.5, BLUE), (10.0, ORANGE)):
        rows = [r for r in circle['frontier'] if r['contrast'] == contrast and r['tau'] == 1e-2]
        k = np.array([r['k'] for r in rows]); f = np.array([r['frontier'] for r in rows])
        ax.plot(k, f / k, '-o', color=colour, lw=2, ms=5, label=f'contrast {contrast:g}')
    ax.axhline(2, color=MUTED, lw=1, ls='--'); ax.text(40, 2.03, 'Ewald limit 2k', color=MUTED)
    ax.set(xscale='log', xlabel='kR', ylabel='frontier / kR', title='A. Circle: observable band -> 2k')
    ax.legend(frameon=False)
    ax = axes[1]
    for p in circle['poles']:
        d = [r['detuning_linewidths'] for r in p['rows']]
        ratio = [r['horizon_times_abs_pole_over_distance'] for r in p['rows']]
        ax.plot(np.array(d) + 0.1, ratio, '-o', color=BLUE, lw=1.5, ms=4, alpha=0.8)
    ax.axhline(0.1, color=MUTED, lw=1, ls='--'); ax.text(0.12, 0.13, 'single-pole prediction 0.1', color=MUTED)
    ax.set(xscale='log', yscale='log', ylim=(1e-3, 1), xlabel='detuning / linewidth (+0.1)',
           ylabel='horizon x |k*| / |k - k*|', title='B. Circle, contrast 10: pole horizon law')
    ax = axes[2]
    xs, ys = [], []
    for name, s in bie.items():
        if name == 'end/F_released_m/kite':
            continue
        for row in s['per_frequency']:
            need = row['J_needed_K_1e-06']
            xs.append(row['trace_K_0.001']); ys.append(need[0])
            xs.append(row['trace_K_1e-06']); ys.append(np.nan)
    tk3 = [x for x, y in zip(xs[::2], ys[::2])]
    tk6 = xs[1::2]
    ax.scatter(tk6, ys[::2], s=10, color=ORANGE, label='vs trace band at tau', alpha=0.7)
    ax.scatter(tk3, ys[::2], s=10, color=BLUE, label='vs trace band at sqrt(tau)', alpha=0.7)
    lim = [0, 165]; ax.plot(lim, lim, color=MUTED, lw=1, ls='--')
    ax.set(xlim=lim, ylim=lim, xlabel='trace band K (projection)', ylabel='band needed by J_0 at tau = 1e-6',
           title='C. BIE states: J needs sqrt(tau) traces')
    ax.legend(frameon=False, loc='upper left', markerscale=2)
    for a in axes:
        a.set_facecolor(SURFACE); a.title.set_color(INK)
    fig.tight_layout()
    fig.savefig(folder / 'MA-001_summary.png', dpi=150, facecolor=SURFACE)


if __name__ == '__main__':
    main(sys.argv[1])
