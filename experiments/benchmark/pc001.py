"""PC-001 (pre-registered, NOT yet approved to run): node-free versus nodal pipelines on TG-002.

Three arms, each a named recipe in ``bem_inverse.pipelines``, on all 30 TG-002 cases with
the centred start, no grid search and the default CumulativePolicy:

    N0  nodal_baseline  nodal Kress, spline update, hard stop          (CI-001)
    N1  nodal_fixed     nodal Kress, certified spectral, N1024/2048 response
    M1  modal_fixed     modal Müller, certified spectral, hard stop    (node-free)

Plan and predictions: docs/iterations/cleaned_interfaces/iteration_27/03_plan.md.

    python -m experiments.benchmark.pc001 run --arm M1      # or N0, N1, all
    python -m experiments.benchmark.pc001 report            # side-by-side table and figure
"""
import argparse
import csv
import json
from statistics import median

import numpy as np

from bem_inverse.io import curve_from, read, write, portable
from bem_inverse.physics import Execution
from . import campaign as c, scenes as S

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/PC-001'
ARMS = dict(N0='nodal_baseline', N1='nodal_fixed', M1='modal_fixed')
LOCALIZATION = 'none'
EXECUTION = Execution(device='auto', frequency_threads=4)
WORKERS = 2
PAIRS = (('M1', 'N1'), ('N1', 'N0'), ('M1', 'N0'))
RUN_ORDER = ('M1', 'N1', 'N0')  # headline arm first; the slow nodal baseline last
COLOURS = dict(N0='#52514e', N1='#2a78d6', M1='#eda100')  # muted, track, accent (TG-002 gallery)
WIDTHS = dict(N0=3.2, N1=2., M1=.9)  # nested widths keep identical endpoints visible
WINDOW_CM = (35, 65)  # every truth lies inside (test_truth_is_valid_inside_domain_and_placed_as_frozen)


def run(arm, cases=None, workers=WORKERS):
    return c.run(OUTPUT/arm, cases or list(S.CASES), pipeline=ARMS[arm], localization=LOCALIZATION,
                 execution=EXECUTION, workers=workers, experiment='PC-001 arm '+arm)


def _arm_rows(arm, output):
    folder = output/arm
    if not (folder/'runs').exists():
        return {}
    c.summarize(folder)
    return {r['id']: r for r in read(folder/'summary.json')['rows']}


def _final_curve(arm, case, output):
    path = output/arm/'runs'/case/'result.json'
    if not path.exists():
        return None
    record = read(path).get('final_curve')
    return None if record is None else curve_from(record)


def _pair(a, b, rows, cases):
    done = [k for k in cases if k in rows[a] and k in rows[b]]
    ra = {k: bool(rows[a][k]['recovered']) for k in done}
    rb = {k: bool(rows[b][k]['recovered']) for k in done}
    return dict(compared=len(done), both=sum(ra[k] and rb[k] for k in done),
                neither=sum(not ra[k] and not rb[k] for k in done),
                only_first=[k for k in done if ra[k] and not rb[k]],
                only_second=[k for k in done if rb[k] and not ra[k]])


def readings(rows):
    """The plan's pre-registered readings; 'pending' until every case in the needed arms has a result."""
    full = {arm: len(rows[arm]) == len(S.CASES) for arm in ARMS}
    count = {arm: {S.tag(x): sum(bool(r['recovered']) for r in rows[arm].values() if r['contrast'] == x)
                   for x in S.CONTRASTS} for arm in ARMS}
    out = {}
    if full['M1'] and full['N1']:
        holds = {t: count['M1'][t] >= count['N1'][t]-1 for t in count['M1']}
        out['R1_node_free_retains_best_nodal'] = dict(by_contrast=holds, holds=all(holds.values()))
    else:
        out['R1_node_free_retains_best_nodal'] = 'pending'
    if full['N1'] and full['N0']:
        lost = [k for k in S.CASES if rows['N0'][k]['recovered'] and not rows['N1'][k]['recovered']]
        out['R2_fixes_help_nodal'] = dict(not_worse=all(count['N1'][t] >= count['N0'][t] for t in count['N1']),
                                          regressions=lost, holds=not lost and
                                          all(count['N1'][t] >= count['N0'][t] for t in count['N1']))
    else:
        out['R2_fixes_help_nodal'] = 'pending'
    if full['M1'] and full['N1']:
        cases = [k for k in S.CASES if not rows['M1'][k]['recovered'] and rows['M1'][k]['outcome'] == 'NUMERICAL_FAILURE'
                 and rows['N1'][k]['recovered'] and rows['N1'][k].get('resolution_promoted')]
        out['R3_modal_resolution_limited'] = dict(cases=cases, count=len(cases))
    else:
        out['R3_modal_resolution_limited'] = 'pending'
    if all(full.values()):
        common = [k for k in S.CASES if all(rows[a][k].get('seconds') is not None for a in ARMS)]
        med = {a: median(rows[a][k]['seconds'] for k in common) if common else None for a in ARMS}
        out['R4_modal_fastest'] = dict(cases=len(common), median_seconds=med,
                                       holds=bool(common) and med['M1'] < min(med['N0'], med['N1']))
    else:
        out['R4_modal_fastest'] = 'pending'
    return out


def _fmt(value, spec='.2f'):
    return '—' if value is None else format(value, spec)


def _mark(row):
    if row is None:
        return 'not run'
    return ('✓' if row['recovered'] else '✗')+f" {_fmt(row.get('rms_mm'))} mm"


def markdown(rows, summary):
    present = [a for a in ARMS if rows[a]]
    lines = ['# PC-001 side-by-side comparison', '',
             'Generated by `python -m experiments.benchmark.pc001 report`. '
             'Plan: `docs/iterations/cleaned_interfaces/iteration_27/03_plan.md`.', '',
             '| Arm | Pipeline | Completed | Recovered | ' + ' | '.join(f'c{x:g}' for x in S.CONTRASTS) +
             ' | Median s | Promoted |', '|---|---|---:|---:|' + '---:|'*len(S.CONTRASTS) + '---:|---:|']
    for arm in ARMS:
        s = summary['arms'][arm]
        lines.append(f"| {arm} | `{ARMS[arm]}` | {s['completed']}/30 | {s['recovered']} | " +
                     ' | '.join(str(s['by_contrast'][S.tag(x)]) for x in S.CONTRASTS) +
                     f" | {_fmt(s['median_seconds'], '.0f')} | {s['promoted']} |")
    lines += ['', '## Paired outcomes', '', '| Pair | Compared | Both | Neither | Only first | Only second |',
              '|---|---:|---:|---:|---|---|']
    for (a, b), p in zip(PAIRS, summary['pairs']):
        lines.append(f"| {a} vs {b} | {p['compared']} | {p['both']} | {p['neither']} | "
                     f"{', '.join(p['only_first']) or '—'} | {', '.join(p['only_second']) or '—'} |")
    lines += ['', '## Pre-registered readings', '', '```json', json.dumps(portable(summary['readings']), indent=2),
              '```', '', '## Per case', '',
              '| Case | ' + ' | '.join(present) + ' | ' + ' | '.join(f'{a} outcome' for a in present) +
              ' | ' + ' | '.join(f'{a} s' for a in present) + ' |',
              '|---|' + '---|'*len(present)*3]
    for case in S.CASES:
        r = {a: rows[a].get(case) for a in present}
        lines.append(f'| `{case}` | ' + ' | '.join(_mark(r[a]) for a in present) + ' | ' +
                     ' | '.join('—' if r[a] is None else str(r[a]['outcome']) +
                                (' ↑N1024' if r[a].get('resolution_promoted') else '') for a in present) + ' | ' +
                     ' | '.join(_fmt(None if r[a] is None else r[a].get('seconds'), '.0f') for a in present) + ' |')
    lines += ['', '✓/✗: recovered under the unchanged CI-001 gates; mm: final RMS. ↑N1024: the N1 '
              'resolution response promoted this run.', '', '![PC-001 final curves](comparison.png)', '']
    return '\n'.join(lines)


def figure(rows, output=OUTPUT):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    ink, muted, spine, surface, truth_fill = '#0b0b0b', '#52514e', '#c9c8c2', '#fcfcfb', '#d9d8d3'
    fig, axes = plt.subplots(len(S.CONTRASTS), len(S.SCENES), figsize=(22, 7.6), facecolor=surface)
    start = S.START_CENTER_M+S.LENGTH*S.start_fixture().values(512)
    closed = lambda z: np.r_[z, z[:1]]
    for i, contrast in enumerate(S.CONTRASTS):
        for j, scene in enumerate(S.SCENES):
            ax, case = axes[i, j], S.case_id(contrast, scene)
            truth = S.CENTER+S.LENGTH*curve_from(read(c.INPUTS/'inputs'/scene/'truth.json')).values(2048)
            ax.set_facecolor(surface)
            ax.fill(100*truth.real, 100*truth.imag, color=truth_fill, lw=0)
            ax.plot(100*closed(start).real, 100*closed(start).imag, color=spine, lw=.8, ls='--')
            marks = []
            for arm in ARMS:
                curve = _final_curve(arm, case, output)
                if curve is not None:
                    z = closed(S.CENTER+S.LENGTH*curve.values(2048))
                    ax.plot(100*z.real, 100*z.imag, color=COLOURS[arm], lw=WIDTHS[arm])
                row = rows[arm].get(case)
                marks.append((arm, '·' if row is None else '✓' if row['recovered'] else '✗'))
            ax.set_xlim(*WINDOW_CM)
            ax.set_ylim(*WINDOW_CM)
            ax.set_aspect('equal')
            ax.set_xticks([])
            ax.set_yticks([])
            for side in ax.spines.values():
                side.set_color(spine)
            x = .02
            for arm, mark in marks:
                ax.text(x, .03, f'{arm}{mark}', transform=ax.transAxes, color=COLOURS[arm], fontsize=7.5,
                        fontweight='bold')
                x += .33
            if i == 0:
                ax.set_title(scene.replace('_', ' '), color=ink, fontweight='bold', fontsize=10, loc='left')
            if j == 0:
                ax.set_ylabel(f'contrast {contrast:g}', color=ink, fontsize=10)
    handles = [Line2D([], [], color=COLOURS[a], lw=WIDTHS[a], label=f'{a} {ARMS[a]}') for a in ARMS]
    handles += [Line2D([], [], color=truth_fill, lw=6, label='truth'),
                Line2D([], [], color=spine, ls='--', label='start (65 mm circle)')]
    fig.legend(handles=handles, loc='lower center', ncol=5, frameon=False, fontsize=9, labelcolor=muted)
    fig.text(.01, .985, 'PC-001: final curves of the three pipelines on TG-002 (✓ recovered, ✗ not, · not run). '
             f'Axes span {WINDOW_CM[0]}–{WINDOW_CM[1]} cm; nested line widths show identical endpoints.', color=muted, fontsize=9, va='top')
    fig.tight_layout(rect=(0, .05, 1, .97))
    fig.savefig(output/'comparison.png', dpi=130, facecolor=surface)
    plt.close(fig)
    return str(output/'comparison.png')


def report(output=OUTPUT):
    rows = {arm: _arm_rows(arm, output) for arm in ARMS}
    arms = {}
    for arm in ARMS:
        values = list(rows[arm].values())
        seconds = [r['seconds'] for r in values if r.get('seconds') is not None]
        arms[arm] = dict(pipeline=ARMS[arm], completed=len(values), recovered=sum(bool(r['recovered']) for r in values),
            by_contrast={S.tag(x): sum(bool(r['recovered']) for r in values if r['contrast'] == x) for x in S.CONTRASTS},
            median_seconds=median(seconds) if seconds else None,
            promoted=sum(bool(r.get('resolution_promoted')) for r in values),
            outcomes={o: sum(r['outcome'] == o for r in values) for o in sorted({r['outcome'] for r in values})})
    summary = dict(experiment='PC-001', arms=arms, pairs=[_pair(a, b, rows, S.CASES) for a, b in PAIRS],
                   readings=readings(rows))
    output.mkdir(parents=True, exist_ok=True)
    write(output/'report.json', dict(summary, rows=rows))
    with open(output/'comparison.csv', 'w', newline='') as handle:
        fields = ['case', 'scene', 'contrast'] + [f'{a}_{k}' for a in ARMS for k in
                  ('recovered', 'rms_mm', 'hausdorff_upper_mm', 'maximum_residual', 'outcome', 'last_stage',
                   'resolution_promoted', 'seconds', 'units')]
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for case in S.CASES:
            scene, tag = case.rsplit('__', 1)
            line = dict(case=case, scene=scene, contrast=tag)
            for a in ARMS:
                r = rows[a].get(case, {})
                line.update({f'{a}_{k}': r.get(k) for k in ('recovered', 'rms_mm', 'hausdorff_upper_mm',
                             'maximum_residual', 'outcome', 'last_stage', 'resolution_promoted', 'seconds', 'units')})
            writer.writerow(line)
    (output/'report.md').write_text(markdown(rows, summary))
    figure(rows, output)
    return summary


def main():
    parser = argparse.ArgumentParser(description='PC-001: nodal versus node-free pipelines on TG-002')
    parser.add_argument('command', choices=('run', 'report'))
    parser.add_argument('--arm', choices=(*ARMS, 'all'), default='all')
    parser.add_argument('--cases', nargs='+', help='subset of case IDs (default all 30)')
    parser.add_argument('--workers', type=int, default=WORKERS)
    args = parser.parse_args()
    if args.command == 'run':
        for arm in (RUN_ORDER if args.arm == 'all' else (args.arm,)):
            print(json.dumps(portable(run(arm, args.cases, args.workers)), indent=2), flush=True)
        args.command = 'report'
    summary = report()
    print(json.dumps(portable({k: v for k, v in summary.items()}), indent=2))


if __name__ == '__main__':
    main()
