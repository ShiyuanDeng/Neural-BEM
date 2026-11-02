"""Side-by-side figures of the final GGB-002 recoveries, drawn from saved results only.

Reads docs/iterations/gaugal_comparison/iteration_01/comparison.json (written by
report.py) and the saved curves/images it points to. Runs no solves.

    PYTHONPATH=solvers:. python -m experiments.gaugal_comparison.recovery_figures
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
import numpy as np

from bem_inverse.io import curve_from
from experiments.benchmark import scenes as S
from . import tg002_data as D

REPO = Path(__file__).resolve().parents[2]
DEST = REPO/'docs/iterations/gaugal_comparison/iteration_01'
FIGURES = DEST/'comparison_figures'

SURFACE, INK, MUTED, SPINE = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
TRUTH_FILL = '#e6e5e0'
ARMS = {'known': ('BEM: supplied contrast', '#2a78d6'),
        'material': ('BEM: recovered contrast', '#eb6834'),
        'gaugal': ('GauGal', '#1baf7a')}
BLUES = LinearSegmentedColormap.from_list(
    'ramp', ['#f2f8fe', '#9cc7f2', '#2a78d6', '#123a6b', '#0a1628'])
DIVERGING = LinearSegmentedColormap.from_list('diverging', ['#2a78d6', '#f2f1ee', '#eb6834'])
CONTRASTS = (0.5, 4., 13.3)
HALF = 1000*D.BOX_HALF_WIDTH_M
FOOTNOTE = ('Data: saved GGB-002 GauGal runs and MR-001 BEM runs (TG-002, centred start, noiseless; '
            'nine BEM runs refit 2026-11-02 without the final check). Figures run no solves.')

plt.rcParams.update({'font.family': 'DejaVu Sans', 'axes.edgecolor': SPINE,
                     'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE})


def finite(value):
    return isinstance(value, (int, float)) and np.isfinite(value)


def fmt(value):
    return f'{value:.2g}' if finite(value) else '—'


def mm(curve_json, samples=2048):
    return 1000*S.LENGTH*curve_from(curve_json).values(samples)


def closed(z):
    return np.append(z, z[:1])


def load_rows():
    rows = json.loads((DEST/'comparison.json').read_text())['rows']
    for row in rows:
        case = D.load(row['case'])
        row['truth_mm'] = 1000*case.boundary
        for key in ('known', 'material'):
            row[key]['curve_mm'] = mm(json.loads((REPO/row[key]['source']).read_text())['final_curve'])
        source = REPO/row['gaugal']['source']
        traced = json.loads(source.read_text()).get('traced_curve')
        row['gaugal']['curve_mm'] = mm(traced) if traced else None
        row['gaugal']['image'] = np.load(source.with_suffix('.npz'))['image']
    return {(r['scene'], r['contrast']): r for r in rows}


def frame(ax):
    ax.set_xlim(-HALF, HALF); ax.set_ylim(-HALF, HALF)
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])


def header(fig, title, detail):
    fig.text(.012, .985, title, fontsize=15, fontweight='bold', color=INK, va='top')
    fig.text(.012, .955, detail, fontsize=10.5, color=MUTED, va='top')
    fig.text(.012, .008, FOOTNOTE, fontsize=8.5, color=MUTED, va='bottom')


def label_grid(axes, row_index, column_index, scene, contrast):
    if row_index == 0:
        axes[row_index, column_index].set_title(scene.replace('_', ' '), fontsize=11, color=INK)
    if column_index == 0:
        axes[row_index, column_index].set_ylabel(f'contrast {contrast:g}', fontsize=11, color=INK)


def shapes_figure(rows):
    """Truth and the three final boundaries on the full imaging box."""
    fig, axes = plt.subplots(3, len(S.SCENES), figsize=(23, 8.3), squeeze=False)
    for i, contrast in enumerate(CONTRASTS):
        for j, scene in enumerate(S.SCENES):
            ax, row = axes[i, j], rows[scene, contrast]
            truth = closed(row['truth_mm'])
            ax.fill(truth.real, truth.imag, color=TRUTH_FILL, lw=0, zorder=1)
            ax.plot(truth.real, truth.imag, color=MUTED, lw=1, ls=(0, (3, 2)), zorder=2)
            for key, style in [('gaugal', '-'), ('known', '-'), ('material', (0, (4, 2.5)))]:
                curve = row[key]['curve_mm']
                if curve is not None:
                    curve = closed(curve)
                    ax.plot(curve.real, curve.imag, color=ARMS[key][1], ls=style,
                            lw=1.7 if key == 'known' else 1.4, zorder=3)
            text = '\n'.join(f"{name}  {fmt(row[k].get('rms_mm'))}"
                             for k, name in [('known', 'S'), ('material', 'R'), ('gaugal', 'G')])
            ax.text(.03, .03, 'RMS mm\n'+text, transform=ax.transAxes, fontsize=7.5,
                    color=INK, va='bottom', family='DejaVu Sans Mono',
                    bbox=dict(boxstyle='round,pad=.25', fc=SURFACE, ec=SPINE, lw=.6, alpha=.9))
            failed = [ARMS[k][0].split(': ')[-1]+(' (shape off)' if row[k]['rms_mm'] > 1 else
                                                  ' (field residual)')
                      for k in ('known', 'material') if not row[k].get('recovered')]
            if failed:
                ax.text(.97, .97, 'BEM not recovered:\n'+'\n'.join(failed), transform=ax.transAxes,
                        fontsize=7, color=INK, ha='right', va='top',
                        bbox=dict(boxstyle='round,pad=.25', fc='#fdf3e1', ec='#eda100', lw=.8))
            frame(ax)
            label_grid(axes, i, j, scene, contrast)
    handles = [Line2D([], [], color=MUTED, ls=(0, (3, 2)), lw=1, label='Truth (shaded)')]
    handles += [Line2D([], [], color=c, lw=1.6, ls=(0, (4, 2.5)) if k == 'material' else '-',
                       label=f'{n} ({k[0].upper() if k != "material" else "R"})')
                for k, (n, c) in ARMS.items()]
    handles[1].set_label('BEM: supplied contrast (S)')
    fig.legend(handles=handles, loc='upper right', ncol=4, frameon=False, fontsize=10.5,
               bbox_to_anchor=(.995, .99))
    header(fig, 'Final boundaries: BEM traces the truth; GauGal is close only at contrast 0.5',
           'Full 200 mm imaging box. GauGal is its longest half-peak contour. Boxes mark BEM runs '
           'that were not recovered: "shape off" = RMS > 1 mm; "field residual" = shape close, '
           'field residual over 0.003.')
    fig.tight_layout(rect=(0, .02, 1, .93), h_pad=.6, w_pad=.4)
    fig.savefig(FIGURES/'final_boundaries.png', dpi=150)
    plt.close(fig)


def gaugal_figure(rows):
    """GauGal susceptibility on its own scale, so its structure is visible."""
    fig, axes = plt.subplots(3, len(S.SCENES), figsize=(23, 8.6), squeeze=False)
    for i, contrast in enumerate(CONTRASTS):
        for j, scene in enumerate(S.SCENES):
            ax, row = axes[i, j], rows[scene, contrast]
            image = row['gaugal']['image']
            scale = np.max(np.abs(image))
            ax.imshow(image/scale, origin='upper', extent=(-HALF, HALF, -HALF, HALF),
                      cmap=DIVERGING, vmin=-1, vmax=1, interpolation='nearest')
            truth = closed(row['truth_mm'])
            ax.plot(truth.real, truth.imag, color=INK, lw=1, ls=(0, (3, 2)))
            curve = row['gaugal']['curve_mm']
            if curve is not None:
                curve = closed(curve)
                ax.plot(curve.real, curve.imag, color=ARMS['gaugal'][1], lw=1.4)
            peak = row['gaugal'].get('peak_susceptibility')
            ax.text(.03, .03, f'peak {peak:+.2f}\ntrue {contrast-1:+.2f}', transform=ax.transAxes,
                    fontsize=7.5, color=INK, va='bottom', family='DejaVu Sans Mono',
                    bbox=dict(boxstyle='round,pad=.25', fc=SURFACE, ec=SPINE, lw=.6, alpha=.9))
            frame(ax)
            label_grid(axes, i, j, scene, contrast)
    bar = fig.add_axes([.935, .965, .055, .012])
    fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(-1, 1), cmap=DIVERGING),
                 cax=bar, orientation='horizontal', ticks=[-1, 0, 1])
    bar.tick_params(labelsize=8, length=2)
    bar.set_title('χ / max|χ| in panel', fontsize=8.5, color=MUTED, pad=2)
    handles = [Line2D([], [], color=INK, ls=(0, (3, 2)), lw=1, label='Truth boundary'),
               Line2D([], [], color=ARMS['gaugal'][1], lw=1.4, label='GauGal scored contour')]
    fig.legend(handles=handles, loc='upper right', ncol=2, frameon=False, fontsize=10.5,
               bbox_to_anchor=(.915, .99))
    header(fig, 'GauGal susceptibility images, each on its own scale',
           'Orange = susceptibility above background, blue = below. "peak" is the signed '
           'largest value; at contrasts 4 and 13.3 it is far too small and often the wrong sign.')
    fig.tight_layout(rect=(0, .02, 1, .93), h_pad=.6, w_pad=.4)
    fig.savefig(FIGURES/'gaugal_own_scale.png', dpi=150)
    plt.close(fig)


def scorecard_figure(rows):
    """Boundary RMS for every case and arm, plus the recovered contrasts."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(17, 7.2),
                                      gridspec_kw=dict(width_ratios=[1.55, 1]))
    keys = list(ARMS)
    values = np.full((len(S.SCENES), 9), np.nan)
    passed = np.zeros_like(values, bool)
    for j, contrast in enumerate(CONTRASTS):
        for k, key in enumerate(keys):
            for i, scene in enumerate(S.SCENES):
                arm = rows[scene, contrast][key]
                values[i, 3*j+k] = arm.get('rms_mm') if finite(arm.get('rms_mm')) else np.nan
                passed[i, 3*j+k] = arm.get('meets_shared_limits', False)
    norm = LogNorm(1e-5, 1e2)
    left.imshow(np.ma.masked_invalid(values), cmap=BLUES, norm=norm, aspect='auto')
    for i in range(values.shape[0]):
        for c in range(values.shape[1]):
            value = values[i, c]
            dark = finite(value) and norm(value) > .55
            left.text(c, i, ('✓ ' if passed[i, c] else '')+fmt(value), ha='center', va='center',
                      fontsize=8.5, color=SURFACE if dark else INK)
    for x in (2.5, 5.5):
        left.axvline(x, color=SURFACE, lw=4)
    left.set_xticks(range(9), [ARMS[k][0].replace('BEM: ', 'BEM\n').replace(' contrast', '')
                               for k in keys]*3, fontsize=8.5)
    left.set_yticks(range(len(S.SCENES)), [s.replace('_', ' ') for s in S.SCENES], fontsize=10)
    for j, contrast in enumerate(CONTRASTS):
        left.text(3*j+1, -.85, f'contrast {contrast:g}', ha='center', fontsize=11,
                  color=INK, fontweight='bold')
    left.tick_params(length=0)
    for spine in left.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=BLUES), ax=left,
                        fraction=.035, pad=.015)
    cbar.set_label('boundary RMS error (mm, log scale)', color=MUTED)
    cbar.outline.set_edgecolor(SPINE)
    left.set_title('Boundary RMS error (mm). ✓ = RMS ≤ 1 mm, Hausdorff ≤ 2 mm and field '
                   'residual ≤ 0.003', fontsize=10, color=MUTED, loc='left', pad=26)

    offsets = {'material': -.16, 'gaugal': .16}
    for j, contrast in enumerate(CONTRASTS):
        right.plot([j-.35, j+.35], [contrast]*2, color=INK, ls=(0, (3, 2)), lw=1.2, zorder=1)
        for key, dx in offsets.items():
            estimates = [rows[s, contrast][key].get('contrast') for s in S.SCENES]
            estimates = [e for e in estimates if finite(e)]
            jitter = np.linspace(-.12, .12, len(estimates))
            right.scatter(j+dx+jitter, estimates, s=46, color=ARMS[key][1], edgecolor=SURFACE,
                          lw=1.2, zorder=3, label=ARMS[key][0] if j == 0 else None)
    right.set_yscale('log')
    right.set_xticks(range(3), [f'true {c:g}' for c in CONTRASTS], fontsize=10.5)
    right.set_xlim(-.6, 2.6)
    right.set_ylabel('estimated contrast (log scale)')
    right.grid(axis='y', color=SPINE, lw=.5, alpha=.6)
    for spine in ('top', 'right'):
        right.spines[spine].set_visible(False)
    right.legend(frameon=False, fontsize=10, loc='upper left')
    right.text(2.38, 13.3, 'truth', color=MUTED, fontsize=9, va='center')
    right.set_title('Recovered contrast per case; dashed line = truth.', fontsize=10, color=MUTED, loc='left')
    counts = [sum(bool(r[k].get('meets_shared_limits')) for r in rows.values()) for k in keys]
    header(fig, 'Scorecard: all 30 TG-002 cases',
           f'BEM meets the shared limits in {counts[0]} (supplied) and {counts[1]} (recovered) cases; '
           f'GauGal in {counts[2]}. GauGal stopped at its 80-iteration limit every time.')
    fig.tight_layout(rect=(0, .025, 1, .91), w_pad=3)
    fig.savefig(FIGURES/'scorecard.png', dpi=150)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    shapes_figure(rows)
    gaugal_figure(rows)
    scorecard_figure(rows)
    print('wrote', *(FIGURES/n for n in ('final_boundaries.png', 'gaugal_own_scale.png',
                                         'scorecard.png')))


if __name__ == '__main__':
    main()
