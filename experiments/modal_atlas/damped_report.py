"""MA-004 post-run report: summary.json and figures. No optimization.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.damped_report
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.modal_atlas.contrast_screen import OUT as MA002, SC050, SCENES, tag
from experiments.modal_atlas import repair_screen as ma003
from experiments.modal_atlas.damped_screen import OUT, TRANSFER_SCENES, verify

SURFACE, INK, MUTED, SPINE = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
COLORS = dict(frozen='#eb6834', LB='#2a78d6', R='#9a9892', DP='#eda100', D='#1baf7a')
LABELS = dict(frozen='frozen SC-050', LB='LB (MA-003)', R='R: extra undamped pass', DP='DP: damped prefix',
              D='D: damped localization + prefix')


def read(path):
    return json.loads(Path(path).read_text())


def result(arm, contrast, scene):
    if scene in SCENES and arm == 'frozen':
        return read(MA002 / 'runs' / tag(contrast) / scene / 'result.json')
    if scene in SCENES and arm == 'LB':
        path = ma003.OUT / 'runs/both' / tag(contrast) / scene / 'result.json'
        return read(path) if path.exists() else None
    path = OUT / 'runs' / arm / tag(contrast) / scene / 'result.json'
    return read(path) if path.exists() else None


def brief(r):
    if r is None:
        return None
    loc = r.get('localization', {})
    return dict(outcome=r['outcome'], recovered=r['recovered'], rms_mm=r.get('metrics', {}).get('rms_mm'),
                hausdorff_upper_mm=r.get('metrics', {}).get('hausdorff_upper_mm'),
                final_audit_passed=r.get('final_audit_passed'), maximum_residual=r.get('maximum_residual'),
                localization_m=loc.get('parameters_m'), localization_units=loc.get('units'),
                localization_seconds=loc.get('seconds'),
                fit_and_localization_units=r.get('fit_and_localization_units'),
                fit_and_localization_seconds=r.get('fit_and_localization_seconds'),
                last_stage=r['stages'][-1]['stage'] if r.get('stages') else None)


def panel(ax, scene, contrast, arms):
    source = 'new_asymmetric' if scene == 'noisy_asymmetric' else scene
    truth = ast.curve_from(read(SC050 / 'inputs' / source / 'truth.json'))
    zt = truth.values(2048) * sc.LENGTH * 1000 + sc.CENTER * 1000
    ax.plot(np.r_[zt, zt[0]].real, np.r_[zt, zt[0]].imag, color=INK, ls='--', lw=1.1)
    shown, lines = [zt], []
    for arm in arms:
        r = result(arm, contrast, scene)
        if r is None:
            continue
        record = r.get('final_curve', r.get('last_curve'))
        if record:
            z = ast.curve_from(record).values(2048) * sc.LENGTH * 1000 + sc.CENTER * 1000
            ax.plot(np.r_[z, z[0]].real, np.r_[z, z[0]].imag, color=COLORS[arm], lw=1.6,
                    ls='-' if r['recovered'] else (0, (4, 2)))
            shown.append(z)
        rms = r.get('metrics', {}).get('rms_mm')
        lines.append(f"{arm}: {'ok' if r['recovered'] else 'fail'}" + (f' {rms:.2g} mm' if rms is not None else ''))
    z = np.concatenate(shown)
    ax.set_xlim(z.real.min() - 10, z.real.max() + 10)
    ax.set_ylim(z.imag.min() - 10, z.imag.max() + 10)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_title(f'{scene} · contrast {contrast:g}', fontweight='bold', loc='left', fontsize=9, pad=24)
    ax.text(0, 1.015, '\n'.join([' · '.join(lines[:3]), ' · '.join(lines[3:])]).strip(), transform=ax.transAxes,
            color=MUTED, fontsize=7, va='bottom')


def figure(scenes, contrasts, arms, name, title):
    plt.rcParams.update({'font.size': 8.5, 'axes.edgecolor': SPINE, 'axes.labelcolor': MUTED, 'xtick.color': MUTED,
                         'ytick.color': MUTED, 'text.color': INK, 'figure.facecolor': SURFACE,
                         'axes.facecolor': SURFACE, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(len(scenes), len(contrasts), figsize=(3.4 * len(contrasts), 3.2 * len(scenes)),
                             layout='constrained', squeeze=False)
    for i, scene in enumerate(scenes):
        for j, contrast in enumerate(contrasts):
            panel(axes[i, j], scene, contrast, arms)
    fig.suptitle(title, fontweight='bold', x=0.01, ha='left')
    handles = [plt.Line2D([], [], color=COLORS[a], lw=1.6) for a in arms] + [plt.Line2D([], [], color=INK, ls='--')]
    fig.legend(handles, [LABELS[a] for a in arms] + ['target'], loc='lower left', ncol=len(arms) + 1,
               frameon=False, bbox_to_anchor=(0.01, -0.03), fontsize=8)
    fig.text(0.01, -0.055, 'Solid: recovered; dashed coloured: not recovered. Contrast = interior/exterior '
             'permittivity (benchmark 0.5). Damping: k(1 + 0.25i). Data: MA-002/003/004 runs; synthetic '
             'observations (noisy_asymmetric: 1% noise).', color=MUTED, fontsize=7.5)
    fig.savefig(OUT / name, dpi=150, bbox_inches='tight')
    plt.close(fig)


def main():
    verify()
    development = {arm: {f'{tag(c)}/{s}': brief(result(arm, c, s)) for c in (0.5, 2.0, 4.0, 13.3) for s in SCENES}
                   for arm in ('frozen', 'LB', 'R', 'DP', 'D')}
    transfer = {arm: {f'{tag(c)}/{s}': brief(result(arm, c, s)) for c in (4.0, 13.3) for s in TRANSFER_SCENES}
                for arm in ('frozen', 'D')}
    count = lambda table: sum(bool(v and v['recovered']) for v in table.values())
    summary = dict(experiment='MA-004', replay=read(OUT / 'replay.json'),
                   gate_G1=read(OUT / 'gate_G1.json') if (OUT / 'gate_G1.json').exists() else None,
                   development_recovered={a: count(t) for a, t in development.items()},
                   transfer_recovered={a: count(t) for a, t in transfer.items()},
                   development=development, transfer=transfer,
                   notes='frozen development rows are MA-002, LB rows are MA-003 `both`; R and DP ran at contrasts 4 '
                         'and 13.3 only.')
    tr = summary['transfer_recovered']
    ran = any(v is not None for table in transfer.values() for v in table.values())
    summary['gate_G2'] = dict(passed=bool(tr['D'] >= 4 and tr['D'] >= tr['frozen'] + 2), **tr) if ran else \
        dict(passed=None, reason='G1 failed; transfer withheld')
    sc.write(OUT / 'summary.json', summary)
    figure(SCENES, (0.5, 2.0, 4.0, 13.3), ('frozen', 'LB', 'R', 'DP', 'D'), 'MA-004_development.png',
           'MA-004 development: a damped (complex-frequency) start for denser-than-host targets')
    if any(transfer['D'].values()):
        figure(TRANSFER_SCENES, (4.0, 13.3), ('frozen', 'D'), 'MA-004_transfer.png',
               'MA-004 transfer: untouched scenes, frozen SC-050 policy against the damped start')
    print(json.dumps(dict(development=summary['development_recovered'], transfer=tr, G2=summary['gate_G2'])))


if __name__ == '__main__':
    main()
