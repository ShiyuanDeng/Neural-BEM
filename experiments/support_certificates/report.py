"""Render the retained numerical evidence; no optimization is performed."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def run():
    root = Path('results/experiments')
    out = root / 'outsider_research_20260916'
    out.mkdir(parents=True, exist_ok=True)
    read = lambda name: json.loads((root / name).read_text())
    bounds = read('support_certificates_20260916/complex_material.json')
    broad = read('support_certificates_20260916/broad_qualification.json')
    passive = read('passive_shape_20260916/screen.json')['records']
    fixed = read('operator_rom_20260916/fixed_projection.json')
    qualification = read('operator_rom_20260916/qualification.json')
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'savefig.dpi': 170})
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.4), layout='constrained')
    ax = axes[0]
    for cross, label, color in [(False, 'Material constraints', '#6b7280'),
                               (True, '+ common-material identities', '#007c91')]:
        rows = [r for r in bounds if r['name'] == 'left' and r['cross'] == cross]
        ax.plot([r['n'] for r in rows], [100*r['relative_residual_bound'] for r in rows],
                'o-', label=label, color=color)
    ax.set(xlabel='Grid width (n)', ylabel='Residual lower bound (%)',
           title='Support exclusion: a conditional success', ylim=(0, 25), xticks=[8, 12, 16])
    ax.text(.04, .12, 'Independent ε′ = 2.7–6, σ = 0–0.04 S/m\n750 MHz, air–soil interface, 2 sources',
            transform=ax.transAxes, fontsize=9)
    ax.legend(loc='upper right', fontsize=8)
    ax = axes[1]
    ranks = [r['rank'] for r in fixed['results']]
    ax.plot(ranks, [100*r['basin_fraction'] for r in fixed['results']], 'o-',
            color='#007c91', label='Fixed-projection ROM')
    ax.axhline(100*fixed['raw_basin_fraction'], color='#6b7280', linestyle='--', label='Waveform objective')
    ax.set(xlabel='Retained ROM rank', ylabel='Starts reaching truth (%)', ylim=(0, 80),
           title='ROM: improvement depends on rank', xticks=ranks)
    ax.text(.04, .06, 'Noiseless, 2 sources\n55-point depth slice; local grid descent',
            transform=ax.transAxes, fontsize=9)
    ax.legend(fontsize=8)
    ax = axes[2]
    ax.semilogy([r['radius_mm'] for r in passive],
                [100*r['optimized_passive_error'] for r in passive], 'o-',
                color='#007c91', label='31 fitting frequencies')
    ax.semilogy([r['radius_mm'] for r in passive],
                [100*r['heldout_frequency_error'] for r in passive], 's--',
                color='#d17722', label='30 held-out frequencies')
    ax.axhline(1., color='#6b7280', linestyle=':', label='1% reference level')
    ax.set(xlabel='True radius (mm)', ylabel='Relative data residual (%)',
           title='Passivity: a 25% wrong radius can fit')
    ax.legend(fontsize=8)
    fig.suptitle('Three imports tested against stronger controls — no general GPR breakthrough', fontsize=14)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'findings.{ext}')
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13.7, 4.7), layout='constrained')
    p = np.asarray(broad['fit']['parameters'])
    eps = p[:128].reshape(16, 8)
    sigma = p[128:].reshape(16, 8)*8.8541878128e-12*2*np.pi*.75e9
    for ax, material, label, cmap in [(axes[0], eps, 'Relative permittivity ε′', 'viridis'),
                                      (axes[1], sigma, 'Conductivity (S/m)', 'magma')]:
        im = ax.imshow(material, extent=[-80, 0, -240, -80], origin='lower',
                       interpolation='nearest', cmap=cmap)
        ax.add_patch(Circle((10, -160), 36, fill=False, color='#d83b37', linewidth=2,
                            label='True circle (outline only)'))
        ax.axvline(0, color='#6b7280', linestyle='--', linewidth=1)
        ax.set(xlim=(-85, 55), ylim=(-245, -75), xlabel='x (mm)', ylabel='z (mm)', title=label)
        ax.legend(fontsize=7, loc='upper right')
        fig.colorbar(im, ax=ax, shrink=.8)
    ax = axes[2]
    rr = broad['refinement']
    ax.plot([r['n'] for r in rr], [100*r['relative_error'] for r in rr], 'o-', color='#007c91')
    ax.set(xlabel='Evaluation grid width (n)', ylabel='Relative residual (%)', ylim=(0, 4),
           title='Refining the same fitted material', xticks=[16, 32, 48])
    ax.text(.04, .74, 'No refitting after n = 16\nThird source: 33.2% residual\n600 / 900 MHz: 56.4% / 128.2%',
            transform=ax.transAxes, fontsize=10)
    fig.suptitle('Wrong-support witness with ε′ allowed up to 24: sparse-data ambiguity, limited generalization', fontsize=13)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'wrong_support.{ext}')
    plt.close(fig)

    summary = dict(
        strongest_discrete_bound=max(r['relative_residual_bound'] for r in bounds if r['n'] == 16 and r['cross']),
        stronger_baseline=max(r['relative_residual_bound'] for r in bounds if r['n'] == 16 and not r['cross']),
        broad_witness_coarse=broad['refinement'][0]['relative_error'],
        broad_witness_refined=broad['refinement'][-1]['relative_error'],
        passive_5mm=next(r for r in passive if r['radius_mm'] == 5.),
        rom_noise=[dict(level=level,
                        mean_raw=float(np.mean([r['raw_basin_fraction'] for r in qualification['noise'] if r['level'] == level])),
                        mean_rom=float(np.mean([r['rom_basin_fraction'] for r in qualification['noise'] if r['level'] == level])))
                   for level in (.001, .01, .05)])
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))


if __name__ == '__main__':
    run()
