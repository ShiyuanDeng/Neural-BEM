"""MA-002 post-run report: summary.json and the reconstruction figure. No optimization.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.contrast_report
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.modal_atlas.contrast_screen import CONTRASTS, OUT, SC050, SCENES, tag, verify

SURFACE, INK, MUTED, SPINE = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
PASS, FAIL, ACCENT = '#1baf7a', '#eb6834', '#eda100'


def read(path):
    return json.loads(Path(path).read_text())


def stage_rows(result):
    rows = []
    for s in result.get('stages', []):
        rows.append(dict(stage=s['stage'], M=s['M'], outcome=s['outcome'], accepted=s['accepted_steps'],
                         final_loss=s['final_loss'], units=s['work'].get('units') if isinstance(s['work'], dict) else None))
    return rows


def trial_counts(folder):
    """Accepted / attempted LM trials over every saved stage record."""
    attempted = accepted = 0
    for path in folder.glob('*.json'):
        if path.name in ('result.json', 'configuration.json', 'accepted.json', 'checkpoint.json',
                         'localization.json', 'localization_progress.json') or path.name.endswith('_audit.json'):
            continue
        record = read(path)
        trials = record.get('trials')
        if isinstance(trials, list):
            attempted += len(trials)
            accepted += record.get('accepted_steps', 0)
    return attempted, accepted


def main():
    verify()
    rows = []
    for contrast in CONTRASTS:
        for scene in SCENES:
            folder = OUT / 'runs' / tag(contrast) / scene
            r = read(folder / 'result.json')
            attempted, accepted = trial_counts(folder)
            rows.append(dict(
                contrast=contrast, scene=scene, outcome=r['outcome'], recovered=r['recovered'],
                rms_mm=r.get('metrics', {}).get('rms_mm'), hausdorff_upper_mm=r.get('metrics', {}).get('hausdorff_upper_mm'),
                final_audit_passed=r.get('final_audit_passed'), maximum_residual=r.get('maximum_residual'),
                localization=r.get('localization', {}).get('parameters_m'),
                localization_units=r.get('localization', {}).get('units'),
                fit_and_localization_units=r.get('fit_and_localization_units'),
                fit_and_localization_seconds=r.get('fit_and_localization_seconds'), seconds=r.get('seconds'),
                lm_trials_attempted=attempted, lm_trials_accepted=accepted, stages=stage_rows(r),
                traceback=r.get('traceback')))
    inputs = {f'{tag(c)}/{s}': read(OUT / 'inputs' / tag(c) / s / 'qualification.json')['passed']
              for c in CONTRASTS for s in SCENES}
    summary = dict(experiment='MA-002', inputs_qualified=inputs, mie_check=read(OUT / 'mie_check.json')['worst_relative'],
                   attempts=rows,
                   recovered={f'{c:g}': sum(r['recovered'] for r in rows if r['contrast'] == c) for c in CONTRASTS},
                   scope='One attempt per scene and contrast; clean data; known interior permittivity.')
    sc.write(OUT / 'summary.json', summary)

    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': SPINE, 'axes.labelcolor': MUTED, 'xtick.color': MUTED,
                         'ytick.color': MUTED, 'text.color': INK, 'figure.facecolor': SURFACE,
                         'axes.facecolor': SURFACE, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(len(SCENES), len(CONTRASTS), figsize=(13, 9.6), layout='constrained')
    for i, scene in enumerate(SCENES):
        truth = ast.curve_from(read(SC050 / 'inputs' / scene / 'truth.json'))
        for j, contrast in enumerate(CONTRASTS):
            ax = axes[i, j]
            r = read(OUT / 'runs' / tag(contrast) / scene / 'result.json')
            row = next(x for x in rows if x['scene'] == scene and x['contrast'] == contrast)
            zt = truth.values(2048) * sc.LENGTH * 1000 + sc.CENTER * 1000
            ax.plot(np.r_[zt, zt[0]].real, np.r_[zt, zt[0]].imag, color=INK, ls='--', lw=1.2)
            shown = [zt]
            record = r.get('final_curve', r.get('last_curve'))
            if record:
                z = ast.curve_from(record).values(2048) * sc.LENGTH * 1000 + sc.CENTER * 1000
                ax.plot(np.r_[z, z[0]].real, np.r_[z, z[0]].imag, color=PASS if r['recovered'] else FAIL, lw=1.8)
                shown.append(z)
            z = np.concatenate(shown)
            pad = 12
            ax.set_xlim(z.real.min() - pad, z.real.max() + pad)
            ax.set_ylim(z.imag.min() - pad, z.imag.max() + pad)
            ax.set_aspect('equal', adjustable='datalim')
            status = 'recovered' if r['recovered'] else r['outcome'].lower()
            rms = row['rms_mm']
            ax.set_title(f'{scene} · contrast {contrast:g}', fontweight='bold', loc='left', fontsize=9.5, pad=15)
            detail = (f"{status}; RMS {rms:.3g} mm; {row['fit_and_localization_seconds'] or 0:.0f} s"
                      if rms is not None else status)
            ax.text(0, 1.015, detail, transform=ax.transAxes, color=MUTED, fontsize=8, va='bottom')
    fig.suptitle('MA-002: frozen SC-050 policy as the target becomes denser than the host',
                 fontweight='bold', x=0.01, ha='left')
    fig.text(0.01, -0.01, 'Dashed: target. Solid: returned boundary (green recovered, '
             'orange not). Contrast = interior/exterior permittivity; 0.5 is the campaign benchmark. '
             'Data: MA-002 runs; clean synthetic observations.', color=MUTED, fontsize=8)
    fig.savefig(OUT / 'MA-002_reconstructions.png', dpi=150, bbox_inches='tight')
    print(json.dumps(summary['recovered']))


if __name__ == '__main__':
    main()
