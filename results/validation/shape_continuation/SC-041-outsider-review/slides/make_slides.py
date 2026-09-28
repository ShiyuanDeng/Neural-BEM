"""Slide figures for the shape-continuation programme and this outsider review. No field solves.

Reads committed JSON and the local atlas arrays of parts 2 and 4-6. Writes 16:9 PNG and PDF here.
    PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-041-outsider-review/slides/make_slides.py
"""
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle
import numpy as np

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent
RESULTS = REVIEW.parent

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import FourierCurve

spec = importlib.util.spec_from_file_location('analyse', REVIEW/'atlas_analyse.py')
analyse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyse)

L = 1e3*sc.LENGTH
INK, MUTED, FAINT, SURFACE, GRID = '#0b0b0b', '#52514e', '#b9b8b2', '#fcfcfb', '#e9e8e4'
BLUE, ORANGE, AQUA, AMBER, RED = '#2a78d6', '#eb6834', '#1baf7a', '#c98500', '#e34948'
SEQ = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 13, 'axes.edgecolor': FAINT, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.titlecolor': INK, 'axes.titlesize': 14,
                     'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': .8, 'figure.facecolor': SURFACE,
                     'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE, 'axes.spines.top': False,
                     'axes.spines.right': False, 'legend.frameon': False})
from matplotlib.colors import LinearSegmentedColormap
HEAT = LinearSegmentedColormap.from_list('seq', SEQ)
# atlas heat: the videos' own map (atlas_video.CMAP): dark = little left to remove, bright = potential
ATLAS = LinearSegmentedColormap.from_list('atlas', ['#0a1628', '#123a6b', '#2a78d6', '#9cc7f2', '#f2f8fe'])


def slide(title, subtitle=None):
    fig = plt.figure(figsize=(13.333, 7.5))
    fig.text(.04, .94, title, fontsize=22, fontweight='bold', color=INK, va='top')
    if subtitle:
        fig.text(.04, .885, subtitle, fontsize=13.5, color=MUTED, va='top')
    return fig


def save(fig, name, source):
    fig.text(.04, .02, source, fontsize=9.5, color=MUTED)
    fig.savefig(HERE/f'{name}.png', dpi=150)
    fig.savefig(HERE/f'{name}.pdf')
    plt.close(fig)
    print('wrote', name)


def read(path):
    return json.loads(Path(path).read_text())


def truth(case):
    for folder in (RESULTS/'SC-044-noisy-fresh-cases/inputs', REVIEW/'infometric/inputs'):
        if (folder/case/'truth.json').exists():
            return ast.curve_from(read(folder/case/'truth.json'))
    return ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))


def radius(curve):
    return L/np.max(np.abs(curve.nodes(16384).curvatures))


def outline(ax, curve, **kw):
    z = curve.values(4096)*L
    ax.plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]], **kw)


# 1 ------------------------------------------------------------------------------------------ shapes
def shapes():
    fig = slide('Test shapes', 'Six development shapes tuned on for months; five fresh shapes fixed before any fit. '
                'Radius = tightest true curvature.')
    dev = [('circle_to_star', 'star'), ('kite', 'kite'), ('circle_to_c', 'C'), ('peanut', 'peanut'), ('hook', 'hook'),
           ('wrong_circle', 'circle')]
    fresh = [('asymmetric_lobes', 'lobes (SC-044)'), ('deep_c', 'deep C (SC-044)'), ('hooked_tip', 'hooked tip'),
             ('fresh_a', 'fresh A'), ('fresh_b', 'fresh B')]
    for row, (items, label, color) in enumerate(((dev, 'Development', BLUE), (fresh, 'Fresh, untouched', ORANGE))):
        fig.text(.04, .81 - row*.40, label, fontsize=14, fontweight='bold', color=color)
        for i, (case, name) in enumerate(items):
            ax = fig.add_axes([.04 + i*.155, .47 - row*.40, .14, .30])
            c = truth(case)
            outline(ax, c, color=color, lw=2)
            z = c.values(4096)*L
            ax.set_aspect('equal'); ax.axis('off')
            ax.set_title(name, fontsize=12.5, pad=2)
            ax.text(.5, -.04, f'radius {radius(c):.1f} mm', transform=ax.transAxes, ha='center', va='top', fontsize=10.5, color=MUTED)
    save(fig, '01_test_shapes', 'Truth curves: SC-025/039 inputs, SC-044 inputs, SC-041 outsider review part 5-6 inputs.')


# 2 ------------------------------------------------------------------------------------------ error along boundary
def error_along_boundary():
    fig = slide('Where the final error sits', 'Normal distance to truth along the boundary, current pipeline endpoints '
                '(SC-040 / SC-038 / SC-041). Error concentrates in a few places, not evenly.')
    index = {t['case']: t for t in read(RESULTS/'SC-040-six-scene-pipeline/trajectories.json')['trajectories']}
    cases = [('circle_to_star', 'star'), ('kite', 'kite, SC-041 M22'), ('circle_to_c', 'C'), ('peanut', 'peanut'),
             ('hook', 'hook'), ('wrong_circle', 'circle')]
    for i, (case, name) in enumerate(cases):
        if case == 'kite':
            curve = ast.curve_from(read(RESULTS/'SC-041-atlas-decisions/runs/kite/M22/result.json')['curve'])
        else:
            s = index[case]['steps'][-1]
            record = read(sc.ROOT/s['source'])
            row = next((r for r in record.get('history', []) if isinstance(r, dict) and r.get('iteration') == s['iteration']), None)
            curve = ast.curve_from(row['coefficients'] if row else record['curve'])
        e = analyse.normal_error(curve, truth(case).nodes(65536).points)
        s_mm = np.linspace(0, 1, len(e), endpoint=False)
        ax = fig.add_axes([.07 + (i % 3)*.315, .47 - (i//3)*.38, .26, .26])
        ax.plot(s_mm, np.abs(e), color=BLUE, lw=1.6)
        ax.set_yscale('log'); ax.set_ylim(1e-5, 1)
        ax.set_title(f'{name}\nRMS {np.sqrt(np.mean(e**2)):.2g} mm · max {np.max(np.abs(e)):.2g} mm', fontsize=12, loc='left')
        ax.set_xlabel('fraction of perimeter' if i//3 == 1 else '')
        ax.set_ylabel('|error|, mm' if i % 3 == 0 else '')
    save(fig, '02_error_along_boundary', 'Final states of the SC-040 six-scene pipeline (kite: SC-041 M22). Truth used for scoring only.')


# 3 ------------------------------------------------------------------------------------------ atlas filmstrip
def filmstrip():
    data = read(REVIEW/'atlas3d.json')
    fig = slide('The atlas along a trajectory', 'Removable misfit by frequency (x) and ripple order (y) at stage ends; bright = more left to remove.\n'
                'Amber: the update band each stage may use. Brightness fades as the band widens.')
    for row, key in enumerate(('star', 'kite')):
        st = data['tracks'][key]['states']
        ends = [k for k in range(len(st)) if k == 0 or k == len(st)-1 or st[k]['track'] + st[k]['stage'] != st[k+1]['track'] + st[k+1]['stage']]
        pick = sorted({ends[round(i*(len(ends)-1)/7)] for i in range(8)}) if len(ends) > 8 else ends
        fig.text(.04, .80 - row*.415, {'star': 'Star', 'kite': 'Kite, into the flank artefact'}[key], fontsize=13, fontweight='bold', color=BLUE)
        for j, k in enumerate(pick):
            s = st[k]
            ax = fig.add_axes([.045 + j*.113, .47 - row*.415, .1, .24])
            ax.imshow(np.array(s['heat']), origin='lower', aspect='auto', cmap=ATLAS, vmin=data['low'], vmax=0,
                      extent=[.25-.0625, 2.5+.0625, -.5, data['orders']+.5])
            g = [data['ghz'][i] for i in s['active']]
            ax.add_patch(Rectangle((min(g)-.0625, -.5), max(g)-min(g)+.125, min(s['M'], data['orders'])+1, fill=False, ec=AMBER, lw=2.2))
            ax.grid(False)
            ax.set_xticks([.5, 1.5, 2.5] if j == 0 else []); ax.set_yticks([0, 10, 20] if j == 0 else [])
            name = s['track'].split('/')[-1] if s['track'].startswith(('SC041', 'review')) else s['stage']
            ax.set_title(f"{name.replace('_', ' ')}\nM={s['M']} · loss {s['loss']:.0e}", fontsize=9.5)
            ax.set_xlabel(f"H {s['hausdorff']:.2f} mm", fontsize=10, color=MUTED)
    cax = fig.add_axes([.935, .2, .012, .5])
    fig.colorbar(plt.cm.ScalarMappable(cmap=ATLAS, norm=plt.Normalize(data['low'], 0)), cax=cax).set_label('log₁₀ removable misfit (bright = more)', fontsize=11)
    save(fig, '03_atlas_filmstrip', 'Historical capped-QR atlas (atlas_video.py), recomputed for these states in outsider-review part 2. H = Hausdorff to truth.')


# 4 ------------------------------------------------------------------------------------------ atlas tracks loss
def atlas_tracks_loss():
    q2 = read(REVIEW/'atlas_analysis.json')['Q2']
    fig = slide('The atlas colour tracks the loss, not the shape',
                'When the colour inside the update box drains between consecutive steps, how often does each measure also improve?')
    ax = fig.add_axes([.08, .14, .6, .66])
    groups = [('star', 'Star'), ('kite_before_feature', 'Kite, before artefact'), ('kite_after_feature', 'Kite, after artefact')]
    metrics = [('loss', 'Loss', BLUE), ('rms', 'RMS to truth', ORANGE), ('hausdorff', 'Hausdorff to truth', AQUA)]
    for gi, (g, gname) in enumerate(groups):
        for mi, (m, mname, color) in enumerate(metrics):
            v = 100*q2[g][m+'_agreement']
            ax.bar(gi + (mi-1)*.26, v, .24, color=color, label=mname if gi == 0 else None)
            ax.text(gi + (mi-1)*.26, v+1.5, f'{v:.0f}%', ha='center', fontsize=11, color=INK)
        ax.text(gi, -12, f"{q2[g]['pairs']} step pairs", ha='center', fontsize=10.5, color=MUTED)
    ax.axhline(50, color=MUTED, lw=1, ls='--'); ax.text(2.5, 51, 'coin flip', color=MUTED, fontsize=10, ha='right', va='bottom')
    ax.set_xticks(range(3)); ax.set_xticklabels([g[1] for g in groups]); ax.set_ylim(0, 110); ax.set_ylabel('sign agreement, %')
    ax.legend(loc='upper right', ncols=3, bbox_to_anchor=(1, 1.08))
    fig.text(.73, .72, 'Reading', fontsize=14, fontweight='bold')
    fig.text(.73, .68, 'Colour drains because misfit is fitted\n(111 of 111 cells: residual removed,\nnot sensitivity lost).\n\n'
             'It does not tell you whether the\nshape is converging. After kite\'s\nflank artefact forms, dimming goes\n'
             'with a worse Hausdorff error\nmore often than a better one.', fontsize=12.5, color=MUTED, va='top', linespacing=1.4)
    save(fig, '04_atlas_tracks_loss', 'Outsider review part 2: 79 recomputed atlas states, frozen plan atlas_plan.md.')


# 5 ------------------------------------------------------------------------------------------ artefact spectrum
def artefact_spectrum():
    rows = {r['id']: r for r in read(REVIEW/'atlas_analysis.json')['rows']}
    kid = next(i for i, r in rows.items() if r['track'] == 'SC041/kite/M22' and r['iteration'] == max(
        x['iteration'] for x in rows.values() if x['track'] == 'SC041/kite/M22'))
    curve = FourierCurve(np.load(REVIEW/'atlas_local'/f'{kid:03d}.npz')['coefficients'])
    c = np.array(curve.coefficients); c[np.abs(curve.modes) > 32] = 0
    delta = analyse.normal_error(curve, FourierCurve(c).nodes(65536).points)
    e = analyse.order_energy(delta)[:193]
    fig = slide('Kite\'s artefact lives where the atlas cannot look',
                'Energy of the flank feature (state minus its K ≤ 32 low-pass) by arclength ripple order, SC-041 kite M = 22 endpoint.')
    ax = fig.add_axes([.08, .14, .62, .66])
    ax.axvspan(-.5, 30.5, color=AMBER, alpha=.12, lw=0)
    ax.text(15, .96, 'atlas orders\n0–30', ha='center', va='top', color=AMBER, fontsize=11.5, fontweight='bold', transform=ax.get_xaxis_transform())
    ax.bar(np.arange(len(e)), e/e.sum(), width=1, color=BLUE)
    ax.set_yscale('log'); ax.set_xlim(-1, 192); ax.set_ylim(1e-6, 1)
    ax.set_xlabel('ripple order'); ax.set_ylabel('share of feature energy')
    share = e[:31].sum()/e.sum()
    fig.text(.74, .72, f'{100*(1-share):.0f}%', fontsize=40, fontweight='bold', color=INK)
    fig.text(.74, .62, 'of the feature\'s energy is above\norder 30, outside the atlas.', fontsize=13, color=MUTED, va='top')
    fig.text(.74, .47, 'Yet its small low-order part moves\nthe data by 1.3–2.1× the remaining\nresidual: the artefact absorbs\nmisfit, which is why the fit keeps it.',
             fontsize=13, color=MUTED, va='top', linespacing=1.4)
    save(fig, '05_artefact_spectrum', 'Outsider review parts 1-2 (kite_feature_survey.py, atlas_analysis.json Q4).')


# 6 ------------------------------------------------------------------------------------------ probe
def probe():
    rows = read(REVIEW/'probe.json')['rows']
    fig = slide('The data do not ask for the artefact',
                'Loss of the unchanged SC-041 kite objective at the truth, the M = 22 endpoint, and the endpoint low-passed to K.')
    names = [('truth', 'truth'), ('endpoint_M22', 'end-\npoint'), ('endpoint_lowpass_K64', '≤64'),
             ('endpoint_lowpass_K32', '≤32'), ('endpoint_lowpass_K16', '≤16'), ('endpoint_lowpass_K8', '≤8')]
    x = np.arange(len(names))
    panels = [('loss', 'data loss', True), ('hausdorff_mm', 'Hausdorff to truth, mm', False), ('tightest_radius_fine_mm', 'tightest radius, mm', True)]
    for i, (key, label, log) in enumerate(panels):
        ax = fig.add_axes([.07 + i*.32, .2, .25, .52])
        v = [rows[n]['loss'] if key == 'loss' else rows[n]['score'][key] for n, _ in names]
        colors = [MUTED, ORANGE, BLUE, BLUE, BLUE, BLUE]
        ax.bar(x, v, color=colors, width=.62)
        if log:
            ax.set_yscale('log')
        ax.set_xticks(x); ax.set_xticklabels([n[1] for n in names], fontsize=10)
        ax.set_title(label, loc='left')
        for xi, vi in zip(x, v):
            ax.text(xi, vi, f'{vi:.2g}', ha='center', va='bottom', fontsize=9.5, color=INK)
    fig.text(.07, .115, 'Truth fits the data to 7e-29; the endpoint sits at 2.7e-9. Keeping only modes up to 32 (≤32) removes the artefact\n'
             '(radius 0.08 → 3.4 mm) and cuts Hausdorff 40%, for 2.4× the loss. Blue bars: endpoint low-passed to that band.', fontsize=12, color=INK, va='top')
    save(fig, '06_probe_lowpass', 'Outsider review part 1, frozen plan.md, probe.json. Noiseless data from the same forward model.')


# 7 ------------------------------------------------------------------------------------------ roughness vs error
def roughness():
    d = read(REVIEW/'signals.json')
    rows = d['test_rows']
    fig = slide('Rougher does not mean wrong',
                'Every accepted state of the untouched SC-044 reconstructions (the circle start omitted from the plot). Truth-free signal against true Hausdorff error.')
    for i, (case, name) in enumerate((('asymmetric_lobes', 'lobes'), ('deep_c', 'deep C'))):
        sel = [r for r in rows if r['case'] == case and r['S4_curvature_roughness'] > 1e-8]
        for j, (key, label, color) in enumerate((('S4_curvature_roughness', 'curvature roughness, 1/mm²', ORANGE), ('S6_loss', 'data loss', BLUE))):
            ax = fig.add_axes([.08 + j*.47, .5 - i*.37, .39, .25])
            ax.scatter([r[key] for r in sel], [r['hausdorff_mm'] for r in sel], s=14, color=color, alpha=.7, lw=0)
            ax.set_xscale('log'); ax.set_yscale('log')
            res = d['test']['result'][case][f'{key}|hausdorff_mm']
            ax.set_title(f"{name}: Spearman {res['rho']:+.2f}, step agreement {100*res['agreement']:.0f}%", loc='left', fontsize=12.5)
            ax.set_xlabel(label if i == 1 else ''); ax.set_ylabel('Hausdorff, mm' if j == 0 else '')
    save(fig, '07_roughness_vs_error', 'Outsider review part 3, frozen signal_plan.md. Detail grows with progress, true and spurious alike.')


# 8 ------------------------------------------------------------------------------------------ information maps
def information_maps():
    fig = slide('Where spurious sharpening forms',
                'Entry-state boundary coloured by posterior ratio ρ (dark = best determined). ✕ = final sharpest point; ○ = entry sharpest point.')
    cases = []
    k = np.load(REVIEW/'infometric/runs/kite/A0_mass/entry_ratio.npz')
    kentry = FourierCurve(np.load(REVIEW/'infometric/runs/kite/A0_mass/weight_release_M11.npz')['coefficients'])
    cases.append(('kite (development)', kentry, k['P1_white_1mm'],
                  ast.curve_from(read(RESULTS/'SC-041-atlas-decisions/runs/kite/M22/result.json')['curve']), 'kite'))
    for case, label in (('hooked_tip', 'hooked tip'), ('fresh_b', 'fresh B'), ('fresh_a', 'fresh A')):
        p = read(REVIEW/'predictions'/f'{case}.json')
        cases.append((label, ast.curve_from(p['entry_curve']), np.array(p['rho_white']),
                      ast.curve_from(read(REVIEW/'infometric/runs'/case/'clean/none/result.json')['curve']), case))
    score = read(REVIEW/'predict_score.json')['shapes']
    for i, (label, entry, rho, final, case) in enumerate(cases):
        ax = fig.add_axes([.03 + i*.24, .16, .22, .62])
        z = analyse.arclength_series(entry, lambda nd: nd.points[:, 0] + 1j*nd.points[:, 1])[::2]*L
        pct = np.argsort(np.argsort(rho))/len(rho)
        seg = np.stack([np.c_[z.real, z.imag], np.roll(np.c_[z.real, z.imag], -1, axis=0)], axis=1)
        lc = LineCollection(seg, cmap=HEAT.reversed(), norm=plt.Normalize(0, 1), lw=7)
        lc.set_array(pct); ax.add_collection(lc)
        outline(ax, truth(case), color=MUTED, lw=1, ls='--')
        fn = final.nodes(16384); j = int(np.argmax(np.abs(fn.curvatures))); p = fn.points[j]*L
        ax.plot(*p, marker='x', color=RED, ms=13, mew=3)
        kap = np.abs(analyse.arclength_series(entry, lambda nd: np.asarray(nd.curvatures))[::2]); q = z[int(np.argmax(kap))]
        ax.plot(q.real, q.imag, marker='o', mfc='none', mec=INK, ms=16, mew=1.8)
        ax.set_aspect('equal'); ax.axis('off'); ax.autoscale()
        spur = 'spurious' if (case == 'kite' or score.get(case, {}).get('sharpest_spurious')) else 'true feature'
        ax.set_title(f'{label}\nfinal sharpest point: {spur}', fontsize=12.5)
    fig.text(.04, .12, 'Pointwise-sensitivity prediction refuted (sites at the 38th–68th percentile). ρ puts every site in its best-determined 10%, '
             'but ρ tracks the entry\ncurvature (Spearman −0.63 to −0.79) and also flags fresh A\'s true feature: sharp features grow where the entry shape is already most curved.',
             fontsize=11.5, color=INK, va='top')
    save(fig, '08_where_sharpening_forms', 'Outsider review parts 4-6; predictions committed before each suffix (1728c600, 323eab2d, 9917657b).')


# 9 ------------------------------------------------------------------------------------------ scoreboard
def scoreboard():
    fig = slide('What was tested, and what held', 'Outsider review of SC-041, parts 1–6. Every verdict against a plan committed before the run.')
    rows = [
        ('1', 'Kite\'s sharp point is the kite\'s tip', 'No: spurious flank staircase, 5 mm from the tip', RED),
        ('1', 'The data require that feature', 'No: truth loss 7e-29 vs 2.7e-9', RED),
        ('2', 'Dimming atlas colour means a better shape', 'No: tracks loss (97%), not Hausdorff (39–71%)', RED),
        ('2', 'The atlas can see the artefact', 'No: 93% of its energy above order 30', RED),
        ('3', 'A truth-free shape signal flags artefacts', 'No: roughness anti-correlated with error', RED),
        ('4', 'Artefacts form where the data are blind', 'No, inverted: best-determined 10% (13/13)', RED),
        ('5', 'Sensitivity-weighted step suppresses them', 'Inert: weight 0.88–1.12, metric does not steer', MUTED),
        ('6', 'Pointwise sensitivity predicts the site', 'Refuted on unseen shapes (0 of 2)', RED),
        ('6', 'Posterior ratio predicts the site', 'Supported 2/2, but reduces to entry curvature', AMBER),
    ]
    fig.text(.04, .80, 'Part', fontsize=12, color=MUTED, fontweight='bold'); fig.text(.10, .80, 'Hypothesis', fontsize=12, color=MUTED, fontweight='bold')
    fig.text(.55, .80, 'Result', fontsize=12, color=MUTED, fontweight='bold')
    for i, (part, h, r, color) in enumerate(rows):
        y = .74 - i*.072
        fig.add_artist(plt.Line2D([.04, .96], [y+.03, y+.03], color=GRID, lw=1))
        fig.text(.045, y, part, fontsize=13, color=MUTED); fig.text(.10, y, h, fontsize=13.5, color=INK)
        fig.add_artist(Rectangle((.535, y+.002), .008, .025, color=color, transform=fig.transFigure))
        fig.text(.55, y, r, fontsize=13.5, color=INK)
    save(fig, '09_scoreboard', 'Details and receipts: results/validation/shape_continuation/SC-041-outsider-review/README.md.')


if __name__ == '__main__':
    for f in (shapes, error_along_boundary, filmstrip, atlas_tracks_loss, artefact_spectrum, probe, roughness, information_maps, scoreboard):
        f()
