"""MA-005 post-run report: summary.json, gate G2 and figures. No optimization.

    PYTHONPATH=solvers:. python -m experiments.modal_atlas.frontier_report
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.modal_atlas.contrast_screen import OUT as MA002, SC050, SCENES, tag
from experiments.modal_atlas import damped_screen as ds
from experiments.modal_atlas.frontier_tail import OUT, TRANSFER, verify

SURFACE, INK, MUTED, SPINE = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
COLORS = dict(frozen='#eb6834', D='#2a78d6', DF='#1baf7a')
LABELS = dict(frozen='frozen SC-050', D='D: damped start (MA-004)', DF='DF: D + frontier tail')


def read(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def result(arm, contrast, scene, phase):
    if phase == 'development':
        if arm == 'frozen':
            return read(MA002 / 'runs' / tag(contrast) / scene / 'result.json')
        if arm == 'D':
            return read(ds.OUT / 'runs/D' / tag(contrast) / scene / 'result.json')
    return read(OUT / 'runs' / arm / tag(contrast) / scene / 'result.json')


def brief(r):
    if r is None:
        return None
    tail = r.get('tail') or {}
    return dict(outcome=r['outcome'], recovered=r['recovered'], rms_mm=r.get('metrics', {}).get('rms_mm'),
                hausdorff_upper_mm=r.get('metrics', {}).get('hausdorff_upper_mm'),
                final_audit_passed=r.get('final_audit_passed'), maximum_residual=r.get('maximum_residual'),
                fit_and_localization_units=r.get('fit_and_localization_units'),
                fit_and_localization_seconds=r.get('fit_and_localization_seconds'),
                frontier=tail.get('frontier'), tail_bands=tail.get('bands'), tail_applied=tail.get('applied'))


def panel(ax, scene, contrast, phase, arms):
    source = 'new_asymmetric' if scene == 'noisy_asymmetric' else scene
    truth = ast.curve_from(read(SC050 / 'inputs' / source / 'truth.json'))
    zt = truth.values(2048) * sc.LENGTH * 1000 + sc.CENTER * 1000
    ax.plot(np.r_[zt, zt[0]].real, np.r_[zt, zt[0]].imag, color=INK, ls='--', lw=1.1)
    shown, lines = [zt], []
    for arm in arms:
        r = result(arm, contrast, scene, phase)
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
    ax.set_title(f'{scene} · contrast {contrast:g}', fontweight='bold', loc='left', fontsize=9, pad=14)
    ax.text(0, 1.015, ' · '.join(lines), transform=ax.transAxes, color=MUTED, fontsize=7, va='bottom')


def figure(rows, phase, name, title):
    plt.rcParams.update({'font.size': 8.5, 'axes.edgecolor': SPINE, 'axes.labelcolor': MUTED, 'xtick.color': MUTED,
                         'ytick.color': MUTED, 'text.color': INK, 'figure.facecolor': SURFACE,
                         'axes.facecolor': SURFACE, 'axes.spines.top': False, 'axes.spines.right': False})
    scenes = list(dict.fromkeys(s for _, s in rows))
    contrasts = list(dict.fromkeys(c for c, _ in rows))
    fig, axes = plt.subplots(len(contrasts), len(scenes), figsize=(3.4 * len(scenes), 3.3 * len(contrasts)),
                             layout='constrained', squeeze=False)
    for i, contrast in enumerate(contrasts):
        for j, scene in enumerate(scenes):
            panel(axes[i, j], scene, contrast, phase, ('frozen', 'D', 'DF'))
    fig.suptitle(title, fontweight='bold', x=0.01, ha='left')
    arms = ('frozen', 'D', 'DF')
    handles = [plt.Line2D([], [], color=COLORS[a], lw=1.6) for a in arms] + [plt.Line2D([], [], color=INK, ls='--')]
    fig.legend(handles, [LABELS[a] for a in arms] + ['target'], loc='lower left', ncol=4, frameon=False,
               bbox_to_anchor=(0.01, -0.035), fontsize=8)
    fig.text(0.01, -0.085, 'Solid: recovered; dashed coloured: not recovered. Contrast = interior/exterior permittivity '
             '(benchmark 0.5). Curves closer than ~0.1 mm overlap.\nD: localization and prefix at k(1 + 0.25i). DF: '
             'then fixed stages up to the measured 1% observable frontier at 2.5 GHz. Synthetic data '
             '(noisy_asymmetric: 1% noise).', color=MUTED, fontsize=7.5)
    fig.savefig(OUT / name, dpi=150, bbox_inches='tight')
    plt.close(fig)


def main():
    verify()
    development_rows = [(c, s) for c in (0.5, 2.0, 4.0, 13.3) for s in SCENES]
    development = {arm: {f'{tag(c)}/{s}': brief(result(arm, c, s, 'development')) for c, s in development_rows}
                   for arm in ('frozen', 'D', 'DF')}
    transfer = {arm: {f'{tag(c)}/{s}': brief(result(arm, c, s, 'transfer')) for c, s in TRANSFER}
                for arm in ('frozen', 'D', 'DF')}
    count = lambda table: sum(bool(v and v['recovered']) for v in table.values())
    complete = all(v is not None for table in transfer.values() for v in table.values())
    tr = {a: count(t) for a, t in transfer.items()}
    audits = all(v['final_audit_passed'] for v in transfer['DF'].values() if v and v['recovered'])
    summary = dict(experiment='MA-005', replay=read(OUT / 'replay.json'), gate_G1=read(OUT / 'gate_G1.json'),
                   development_recovered={a: count(t) for a, t in development.items()}, transfer_recovered=tr,
                   gate_G2=dict(passed=bool(complete and tr['DF'] >= 4 and tr['DF'] >= tr['frozen'] + 2 and audits),
                                complete=complete, DF=tr['DF'], frozen=tr['frozen'],
                                recovered_endpoints_pass_final_audit=audits),
                   disclosure=dict(
                       note='Found after the run: opposite_c has the development C target and identical data '
                            '(8.6e-16); only its initial curve differs, which every localizing arm discards.',
                       transfer_recovered_excluding_opposite_c={
                           a: sum(bool(v and v['recovered']) for k, v in t.items() if 'opposite_c' not in k)
                           for a, t in transfer.items()}),
                   development=development, transfer=transfer,
                   notes='Development frozen rows are MA-002, D rows MA-004. Transfer frozen and D ran from scratch '
                         'under MA-005 with MA-004\'s driver; DF continues each D.')
    sc.write(OUT / 'summary.json', summary)
    figure(development_rows[6:], 'development', 'MA-005_development.png',
           'MA-005 development: the frontier tail at contrasts 4 and 13.3')
    if complete:
        figure(list(TRANSFER), 'transfer', 'MA-005_transfer.png',
               "MA-005 transfer: SC-050's transfer scenes at contrasts 4 and 13.3 "
               "(opposite_c has the development C's target and data)")
    print(json.dumps(dict(development=summary['development_recovered'], transfer=tr, G2=summary['gate_G2'])))


if __name__ == '__main__':
    main()
