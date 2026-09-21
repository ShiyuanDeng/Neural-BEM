"""Render standalone scientific figures and a local gallery from saved evidence."""
import argparse
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .core import blocks, BLOCK_NAMES, deserialize, evaluate


def save(fig, folder, name):
    fig.savefig(folder/f'{name}.png', dpi=160, bbox_inches='tight')
    fig.savefig(folder/f'{name}.svg', bbox_inches='tight')
    plt.close(fig)


def heat(ax, matrix, cutoff):
    # Each block uses its own maximum. This reveals support, not relative
    # physical importance of blocks with different dimensions/units.
    parts = []
    for b in blocks(matrix):
        scale = np.max(np.abs(b))
        parts.append(np.log10(np.maximum(np.abs(b)/max(scale, 1e-300), 1e-12)))
    display = np.block([[parts[0], parts[1]], [parts[2], parts[3]]])
    n = 2*cutoff+1
    im = ax.imshow(display, origin='lower', cmap='magma', vmin=-12, vmax=0,
                   interpolation='nearest', rasterized=True)
    ax.axhline(n-.5, color='cyan', lw=.45)
    ax.axvline(n-.5, color='cyan', lw=.45)
    ax.set_xticks([cutoff, n+cutoff], ['u modes', 'q modes'], fontsize=7)
    ax.set_yticks([cutoff, n+cutoff], ['u modes', 'q modes'], fontsize=7)
    return im


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    folder = args.bundle/'figures'
    folder.mkdir(exist_ok=True)
    cases = [json.loads(p.read_text()) | {'path': p.parent}
             for p in sorted(args.bundle.glob('*/case.json'))]
    order = ['circle', 'ellipse', 'asymmetric_star', 'crescent']
    cases.sort(key=lambda c: (order.index(c['name']), c['kd']))
    lookup = {(c['name'], c['kd']): c for c in cases}
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.facecolor': 'white'})

    for key, title, filename in [
        ('a', 'Müller remainder A − I', '01_forward_heatmaps'),
        ('da', 'Directional derivative ∂A: p=6 cosine normal displacement', '02_derivative_heatmaps')]:
        fig, axes = plt.subplots(4, 3, figsize=(11, 12), constrained_layout=True)
        for row, name in enumerate(order):
            for col, kd in enumerate((2, 10, 30)):
                ax = axes[row, col]
                case = lookup.get((name, kd))
                if case is None:
                    ax.set_axis_off()
                    continue
                with np.load(case['path']/'arrays.npz') as arrays:
                    matrix = arrays['a']-np.eye(case['dimension']) if key=='a' else arrays['da'][4]
                im = heat(ax, matrix, case['cutoff'])
                ax.set_title(f"{name.replace('_', ' ')} · kD={kd} · K={case['cutoff']}"+
                             ('' if case['qualified'] else ' [unqualified]'), fontsize=9)
        fig.colorbar(im, ax=axes, shrink=.65, label='log₁₀ |entry| / maximum in its block')
        fig.suptitle(title+'\nBlock normalization reveals patterns; it does not rank physical importance.', fontsize=13)
        save(fig, folder, filename)

    fig, axes = plt.subplots(4, 3, figsize=(12, 12), constrained_layout=True)
    for row, name in enumerate(order):
        for col, kd in enumerate((2, 10, 30)):
            ax = axes[row, col]
            case = lookup.get((name, kd))
            if case is None:
                ax.set_axis_off()
                continue
            curves = case['curves']
            x = np.array([r['tolerance'] for r in curves])
            den = case['full_slots']
            individual = np.array([list(r['derivative_counts'].values()) for r in curves])/den
            ax.fill_between(x, individual.min(axis=1), individual.max(axis=1),
                            color='#dd8a25', alpha=.25, label='individual ∂A range')
            ax.plot(x, individual.max(axis=1), color='#c87813', lw=1, label='largest individual ∂A')
            ax.plot(x, np.array([r['forward_count'] for r in curves])/den,
                    color='#2379ae', label='A − I only')
            ax.plot(x, np.array([r['union_count']+case['identity_slots'] for r in curves])/den,
                    color='#9b285e', lw=2, label='union + exact identity')
            ax.axhline(.5, color='.4', ls=':', lw=1)
            ax.set(xscale='log', xlim=(1e-2, 1e-8), ylim=(0, 1.05),
                   title=f"{name.replace('_', ' ')} · kD={kd} · K={case['cutoff']}")
            ax.grid(alpha=.15)
            if col==0:
                ax.set_ylabel('Retained fraction of dense matrix')
            if row==3:
                ax.set_xlabel('Allowed relative Frobenius tail, each block')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=4, fontsize=9)
    fig.suptitle('How many entries are actually needed?\nSorted magnitudes; no diagonal-band assumption. Union covers all six physical directions.', fontsize=13)
    save(fig, folder, '03_retained_entries')

    fig, axes = plt.subplots(4, 3, figsize=(12, 12), constrained_layout=True)
    for row, name in enumerate(order):
        for col, kd in enumerate((2, 10, 30)):
            ax = axes[row, col]
            case = lookup.get((name, kd))
            if case is None:
                ax.set_axis_off()
                continue
            for arm, style in [('forward', '--'), ('common', '-')]:
                rows = [r for r in case['scans'] if r['arm']==arm]
                x = [r['represented_fraction'] for r in rows]
                for metric, gate, color, label in [
                    ('field_error', 1e-6, '#2379ae', 'field / 10⁻⁶'),
                    ('worst_derivative_error', 1e-3, '#9b285e', 'discrete ∂data / 10⁻³'),
                    ('worst_hadamard_error', 1e-3, '#168373', 'Hadamard / 10⁻³')]:
                    ax.plot(x, [max(r[metric]/gate, 1e-10) for r in rows], style,
                            marker='.', color=color, label=f'{arm}: {label}', lw=1.25)
            ax.axhline(1., color='black', lw=.8)
            ax.axvline(.5, color='black', ls=':', lw=.8)
            ax.set(yscale='log', xlim=(0, 1.05), ylim=(1e-7, 1e5),
                   title=f"{name.replace('_', ' ')} · kD={kd}"+
                   (' · PASS' if case['winner'] else ' · no pass'))
            ax.grid(alpha=.15)
            if col==0:
                ax.set_ylabel('Error / allowed error (≤1 passes)')
            if row==3:
                ax.set_xlabel('Represented fraction, including identity')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=3, fontsize=8)
    fig.suptitle('Does entry removal survive a fresh solve?\nA release candidate needs common-mask field and discrete sensitivity curves below 1, left of 50%.', fontsize=12)
    save(fig, folder, '04_resolve_errors')

    for case in cases:
        with np.load(case['path']/'arrays.npz') as arrays:
            da = arrays['da']
        fig, axes = plt.subplots(2, 3, figsize=(11, 7), constrained_layout=True)
        for ax, name, matrix in zip(axes.flat, case['physical_directions'], da):
            im = heat(ax, matrix, case['cutoff'])
            ax.set_title(name.replace('_', ' '))
        fig.colorbar(im, ax=axes, label='log₁₀ block-relative magnitude', shrink=.8)
        fig.suptitle(f"All six ∂A patterns: {case['name']} · kD={case['kd']:g}")
        save(fig, folder, f"derivatives_{case['name']}_kd{case['kd']:g}")

    fig, axes = plt.subplots(1, 4, figsize=(12, 3), constrained_layout=True)
    config = json.loads((args.bundle/'config.json').read_text())
    for ax, (name, data) in zip(axes, config['coefficients'].items()):
        z = evaluate(deserialize(data), np.linspace(0, 2*np.pi, 1025))
        ax.plot(z.real, z.imag, color='#2379ae')
        ax.set(title=name.replace('_', ' '), aspect='equal', xlim=(-.6,.6), ylim=(-.6,.6))
        ax.grid(alpha=.2)
    save(fig, folder, '00_shapes')
    summary = json.loads((args.bundle/'summary.json').read_text())
    cards = []
    for p in sorted(folder.glob('*.png')):
        cards.append(f'<section><h2>{html.escape(p.stem.replace("_", " "))}</h2>'
                     f'<a href="figures/{p.stem}.svg">SVG</a> · <a href="figures/{p.name}">PNG</a>'
                     f'<img loading="lazy" src="figures/{p.name}" alt="{html.escape(p.stem)}"></section>')
    (args.bundle/'gallery.html').write_text('<!doctype html><meta charset="utf-8">'
        '<title>MC-001 modal entry screen</title><style>body{font:16px system-ui;max-width:1200px;'
        'margin:32px auto;padding:0 20px;color:#172332}img{width:100%}section{margin:48px 0}'
        'pre{white-space:pre-wrap;background:#f3f5f7;padding:20px}</style>'
        '<h1>MC-001: modal matrix and derivative entry screen</h1>'
        '<p>Diagnostic full assembly. These counts do not establish faster assembly or solves. '
        'Heatmaps normalize each block separately; cumulative-tail curves use per-block norms. '
        'The derivative union covers six directions, not every possible shape perturbation.</p>'
        f'<pre>{html.escape(json.dumps(summary, indent=2))}</pre>'+''.join(cards))
    print(f'Rendered {len(cards)} figures and {args.bundle / "gallery.html"}')


if __name__ == '__main__':
    main()
