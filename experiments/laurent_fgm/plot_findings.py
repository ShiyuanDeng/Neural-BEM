"""Evidence figure for the Fourier-Galerkin Muller decay study.

    PYTHONPATH=solvers:. python -m experiments.laurent_fgm.plot_findings \
        --bundle results/experiments/laurent_fgm_20260918
"""
import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from . import curves as curvelib
from .run_decay import CONTRAST, acquisition, forward, grid_for

COLOURS = dict(circle='#4C72B0', ellipse='#DD8452', kite='#55A868',
               crescent='#C44E52', corrugated='#8172B3')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', required=True, type=Path)
    args = parser.parse_args()
    decay = args.bundle / 'decay'
    selected = json.load((decay / 'selected.json').open())
    profiles = json.load((decay / 'profiles.json').open())

    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8.6))

    # (a) |A_mn| for the kite at kD = 10, the image the report asks for.
    coefficients = curvelib.library()['kite']
    ko = 10. / curvelib.diameter(coefficients)
    cutoff = 36
    matrix, _, _ = forward(coefficients, ko, ko * CONTRAST, cutoff,
                           grid_for(cutoff), *acquisition())
    order = 2 * cutoff + 1
    block = np.abs(matrix[:order, order:])
    axis = axes[0, 0]
    image = axis.imshow(np.log10(np.maximum(block / block.max(), 1e-16)),
                        extent=[-cutoff, cutoff, cutoff, -cutoff],
                        cmap='magma', vmin=-16, vmax=0)
    row = next(r for r in selected if r['curve'] == 'kite' and r['kd'] == 10.
               and r['tolerance'] == 1e-6)
    for sign in (1, -1):
        axis.plot([-cutoff, cutoff],
                  [-cutoff + sign * row['gradient_halfband'],
                   cutoff + sign * row['gradient_halfband']],
                  color='#00E5FF', lw=1.4, ls='--')
    axis.set(xlim=(-cutoff, cutoff), ylim=(cutoff, -cutoff),
             xlabel='n', ylabel='m',
             title=f'(a) $\\log_{{10}}|V_{{mn}}|$, kite, $kD=10$\n'
                   f'dashed: band needed for $10^{{-6}}$ gradient '
                   f'($Q={row["gradient_halfband"]}$)')
    figure.colorbar(image, ax=axis, fraction=.046)

    # (b) envelopes at kD = 30 against the exp(-b* d) slopes.
    axis = axes[0, 1]
    for name in ('ellipse', 'kite', 'crescent', 'corrugated'):
        record = next(p for p in profiles if p['curve'] == name
                      and p['kd'] == 30. and p['block'] == 'V')
        offset = np.array(record['offset'])
        peak = np.array(record['peak'])
        peak = np.maximum.accumulate(peak[::-1])[::-1]     # monotone envelope
        axis.semilogy(offset, peak / peak[0], color=COLOURS[name], lw=1.6,
                      label=name)
        star = next(r for r in selected if r['curve'] == name
                    and r['kd'] == 30.)['halfwidth']
        axis.semilogy(offset, np.exp(-star * offset), color=COLOURS[name],
                      lw=.9, ls=':', alpha=.75)
    axis.set(xlabel='$d = |m-n|$', ylabel='envelope of $|V_{mn}|$, normalised',
             ylim=(1e-17, 3),
             title='(b) decay at $kD=30$ (solid) vs $e^{-b^* d}$ (dotted)\n'
                   'flat plateau of width $\\approx kD$ precedes the decay')
    axis.legend(fontsize=8, loc='lower left')
    axis.grid(alpha=.25)

    # (c) required band against kD, with the fitted rule and the published rule.
    axis = axes[1, 0]
    for name in ('ellipse', 'kite', 'crescent', 'corrugated'):
        rows = sorted([r for r in selected if r['curve'] == name
                       and r['tolerance'] == 1e-6 and r['gradient_halfband'] > 0],
                      key=lambda r: r['kd'])
        axis.plot([r['kd'] for r in rows], [r['gradient_halfband'] for r in rows],
                  'o-', color=COLOURS[name], label=name, lw=1.5, ms=5)
    grid = np.linspace(2, 30, 50)
    star = {n: next(r for r in selected if r['curve'] == n)['halfwidth']
            for n in ('ellipse', 'crescent')}
    for name, style in (('ellipse', '--'), ('crescent', '-.')):
        axis.plot(grid, 1.196 * grid + .162 * np.log(1e6) / star[name] - 2.295,
                  style, color='k', lw=1., alpha=.6,
                  label='fitted rule' if name == 'ellipse' else None)
    axis.plot(grid, 4. * np.log(2 * (2.2 * grid + 20) + 1), ':', color='crimson',
              lw=1.8, label='published $q\\ln N$, $q=4$')
    axis.set(xlabel='$kD$', ylabel='band half-width $Q$ for $10^{-6}$ gradient',
             title='(c) the band grows linearly in $kD$,\n'
                   'not like $q\\ln N$')
    axis.legend(fontsize=8)
    axis.grid(alpha=.25)

    # (d) retention does not improve with electrical size.
    axis = axes[1, 1]
    for name in ('ellipse', 'kite', 'crescent', 'corrugated'):
        rows = sorted([r for r in selected if r['curve'] == name
                       and r['tolerance'] == 1e-6 and r['gradient_halfband'] > 0],
                      key=lambda r: r['kd'])
        axis.plot([r['kd'] for r in rows],
                  [r['gradient_retained'] for r in rows],
                  'o-', color=COLOURS[name], label=name, lw=1.5, ms=5)
    axis.axhline(1., color='k', lw=.8, ls='--')
    axis.set(xlabel='$kD$', ylim=(0, 1.05),
             ylabel='fraction of entries retained',
             title='(d) retention at $10^{-6}$ gradient accuracy:\n'
                   'flat to rising, so a constant factor, not a complexity gain')
    axis.legend(fontsize=8, loc='lower right')
    axis.grid(alpha=.25)

    figure.tight_layout()
    target = args.bundle / 'decay_findings.png'
    figure.savefig(target, dpi=150)
    print(f'wrote {target}')


if __name__ == '__main__':
    main()
