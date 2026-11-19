"""Report figure: saved CSI images and BEM curves on the native 24-pair data. No new solves.

Run from the repository root:
    PYTHONPATH=solvers:. python docs/iterations/compare_sparse_baselines/01_test_single_frequency_csi/make_figures.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
import numpy as np
from scipy.io import loadmat

from bem_inverse.io import curve_from
from experiments.baselines.csi.registered_metrics import score_field
from experiments.benchmark import scenes as S
from experiments.comparison import scoring as G

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CSI = REPO/'results/csi/native_tg002/2026-11-19/fits'
BEM = {'clean': REPO/'results/bem/default_clean_uc_sf0.5', 'n1d0': REPO/'results/bem/default_n1d0_uc_sf0.5'}
SURFACE, INK, MUTED, SPINE = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
BEM_COLOUR, CSI_COLOUR = '#eb6834', '#eda100'
RAMP = LinearSegmentedColormap.from_list('ramp', ['#0a1628', '#123a6b', '#2a78d6', '#9cc7f2', '#f2f8fe'])
ROWS = [('clean', 'clean'), ('n1d0', '1% noise, draw 0')]
CASES = [('circle__c4', 'circle'), ('kite__c4', 'kite')]


def read(path):
    return json.loads(Path(path).read_text())


def closed(points):
    points = np.asarray(points)
    return np.append(points, points[:1])


def panel(ax, case, name, data, label):
    row, truth, _ = G.truth_for(case)
    ax.set_facecolor(SURFACE)
    detail = []
    final = CSI/f'{case}__{data}'/'final_image.mat'
    drawn = None
    if final.exists():
        saved = loadmat(final, simplify_cells=True)
        values = np.asarray(saved['chi_image'])
        _, image = score_field(values, values.shape, np.ravel(saved['x_m']), np.ravel(saved['y_m']), truth)
        drawn = ax.imshow(image, extent=(-100, 100, -100, 100), origin='upper', cmap=RAMP, vmin=0, vmax=4)
        rings, _ = G.support_rings(image, .5)
        for ring in rings:
            ring = closed(ring)
            ax.plot(1e3*ring.real, 1e3*ring.imag, color=CSI_COLOUR, lw=1.6)
        score = CSI/f'{case}__{data}'/'score.json'
        if score.exists():
            detail.append(f"CSI area error {100*read(score)['area_error']:.1f}%")
    else:
        ax.text(0, 0, 'CSI fit not saved', ha='center', va='center', color=MUTED)
        ax.set_xlim(-100, 100); ax.set_ylim(-100, 100)
    fit = BEM[data]/case/'fit.json'
    if fit.exists() and read(fit).get('final_curve'):
        curve = closed(S.LENGTH*curve_from(read(fit)['final_curve']).values(2048))
        ax.plot(1e3*curve.real, 1e3*curve.imag, color=BEM_COLOUR, lw=1.6)
        score = BEM[data]/case/'score.json'
        if score.exists():
            detail.append(f"BEM {100*read(score)['area_error']:.1f}%")
    target = closed(S.LENGTH*curve_from(read(G.ci.ROOT/row['truth'])).values(2048))
    ax.plot(1e3*target.real, 1e3*target.imag, color=SURFACE, lw=1.2, ls=(0, (4, 3)))
    ax.set_title(f'{name}, {label}', loc='left', fontsize=11, fontweight='bold', color=INK, pad=18)
    ax.text(0, 1.02, ' · '.join(detail), transform=ax.transAxes, fontsize=8.5, color=MUTED, va='bottom')
    ax.set_aspect('equal')
    ax.tick_params(colors=MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(SPINE)
    return drawn


def main():
    figure, axes = plt.subplots(2, 2, figsize=(8.6, 8.9), facecolor=SURFACE)
    drawn = None
    for i, (data, label) in enumerate(ROWS):
        for j, (case, name) in enumerate(CASES):
            image = panel(axes[i, j], case, name, data, label)
            drawn = image or drawn
            if i == 1:
                axes[i, j].set_xlabel('x (mm)', color=MUTED, fontsize=9)
            if j == 0:
                axes[i, j].set_ylabel('y (mm)', color=MUTED, fontsize=9)
    figure.subplots_adjust(left=.09, right=.88, top=.86, bottom=.13, hspace=.34, wspace=.18)
    if drawn is not None:
        bar = figure.colorbar(drawn, cax=figure.add_axes([.905, .13, .018, .73]))
        bar.set_label('CSI susceptibility relative to the exterior (true value 3)', color=MUTED, fontsize=9)
        bar.ax.tick_params(colors=MUTED, labelsize=8)
        bar.outline.set_edgecolor(SPINE)
    figure.suptitle('Classical CSI and BEM on the native 24 readings at 0.5 GHz', x=.09, y=.965, ha='left',
                    fontsize=13, fontweight='bold', color=INK)
    figure.text(.09, .925, 'Contrast ratio 4, exterior permittivity 6. One start per method, 2,048 CSI iterations.',
                fontsize=9, color=MUTED)
    handles = [Line2D([], [], color=MUTED, lw=1.2, ls=(0, (4, 3)), label='target (white dashes on the images)'),
               Line2D([], [], color=CSI_COLOUR, lw=1.6, label='CSI region at half peak'),
               Line2D([], [], color=BEM_COLOUR, lw=1.6, label='BEM curve')]
    figure.legend(handles=handles, loc='lower left', bbox_to_anchor=(.09, .045), ncol=3, frameon=False, fontsize=9,
                  labelcolor=INK)
    figure.text(.09, .02, 'Data: sealed TG-002 real catalog, 0.5 GHz column, 24 fixed-offset pairs. Saved fits only; '
                'no new solves.', fontsize=8, color=MUTED)
    (HERE/'figures').mkdir(exist_ok=True)
    figure.savefig(HERE/'figures/csi_and_bem_native_0p5ghz.png', dpi=170, facecolor=SURFACE)


if __name__ == '__main__':
    main()
