"""Summarize the saved ten-frequency MF-CC-CSI evidence and draw its figures.

Reads saved scores and images only; it never fits. With ``--partial DIR`` it
writes a preview of whatever has finished into DIR and leaves the activity
folder alone.
"""
import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np
from scipy.io import loadmat

from experiments.baselines.csi import campaign_ten_frequency as c
from experiments.comparison import scoring as protocol

FIVE = c.base.REPO / 'results/csi/tg002/2026-11-18_five_frequency'
EIGHT = c.base.REPO / 'results/csi/tg002/2026-11-17_campaign'
BEM = c.base.REPO / 'results/bem/baseline_data'
COMMAND = ('PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 '
           '/home/drdeng/miniconda3/envs/EMNerf/bin/python -B '
           'docs/iterations/csi_adaptation/08_run_cases_at_ten_frequencies/make_report.py')

# The user's figure style: surface, ink, muted, spine, two validated series
# hues, amber accent and the dark-to-light blue ramp.
SURFACE, INK, MUTED, SPINE = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
BEM_HUE, CSI_HUE, AMBER = '#2a78d6', '#eb6834', '#eda100'
RAMP = ['#0a1628', '#123a6b', '#2a78d6', '#9cc7f2', '#f2f8fe']


def half(snapshot):
    """Scores at 0.5, 0.3 and 0.7 of the peak, in that order."""
    by = {round(s['fraction'], 1): s for s in snapshot['scores']}
    return by[0.5], by[0.3], by[0.7]


def csi_final(root, scene):
    path = root / scene / 'scores.json'
    if not path.exists():
        return None
    return half(c.read(path)['snapshots'][-1])[0]


def bem(band, scene):
    path = BEM / band / '2026-11-18' / f'{scene}__c4' / 'cuda/attempt_01/metrics.json'
    data = c.read(path)
    return dict(area=100 * data['score']['area_error'], contrast=data['contrast'],
                seconds=data['fit_seconds'], outcome=data['outcome'])


def collect():
    rows = []
    for scene in c.SHAPES:
        folder = c.ROOT / scene
        if not (folder / 'outcome.json').exists():
            continue
        launch, outcome = c.read(folder / 'launch.json'), c.read(folder / 'outcome.json')
        snapshots = c.read(folder / 'scores.json')['snapshots']
        main, low, high = half(snapshots[-1])
        five, eight = csi_final(FIVE, scene), csi_final(EIGHT, scene)
        bem_ten, bem_five = bem('csi_ten_frequency', scene), bem('csi_five_frequency', scene)
        rows.append(dict(
            shape=scene, state=outcome['state'], iterations=snapshots[-1]['iterations'],
            area_error_percent=100 * main['area_error'],
            sensitivity_03_percent=100 * low['area_error'],
            sensitivity_07_percent=100 * high['area_error'],
            mean_permittivity=main['mean_relative_permittivity'],
            relative_contrast_error_percent=100 * main['relative_contrast_error'],
            centre_error_mm=main['centroid_mm'], components=main['components'], holes=main['holes'],
            area_error_by_iteration={str(s['iterations']): 100 * half(s)[0]['area_error'] for s in snapshots},
            native_seconds=snapshots[-1]['native_elapsed_seconds'], wall_seconds=launch['wall_seconds'],
            started_utc=launch['started_utc'], finished_utc=launch['finished_utc'],
            peak_family_rss_gib=launch['peak_family_rss_bytes'] / 2**30,
            frozen_table_sha256=c.read(folder / 'data.json')['sha256'],
            csi_five_frequency_percent=None if five is None else 100 * five['area_error'],
            csi_eight_frequency_percent=None if eight is None else 100 * eight['area_error'],
            bem_ten_frequency_percent=bem_ten['area'], bem_ten_contrast=bem_ten['contrast'],
            bem_ten_seconds=bem_ten['seconds'], bem_ten_outcome=bem_ten['outcome'],
            bem_five_frequency_percent=bem_five['area'], bem_five_outcome=bem_five['outcome']))
    return rows


def style(axis):
    axis.set_facecolor(SURFACE)
    for spine in axis.spines.values():
        spine.set_color(SPINE)
    axis.tick_params(colors=MUTED, labelsize=9)


def draw_images(rows, path, plt):
    from matplotlib.colors import LinearSegmentedColormap
    ramp = LinearSegmentedColormap.from_list('blue_ramp', RAMP)
    fig, axes = plt.subplots(2, 5, figsize=(16, 7.9), dpi=140, facecolor=SURFACE,
                             sharex=True, sharey=True)
    fig.subplots_adjust(left=.05, right=.9, top=.86, bottom=.15, wspace=.08, hspace=.26)
    h, n = protocol.PROTOCOL['grid_half_width_m'], protocol.PROTOCOL['grid_cells']
    x = np.linspace(-h, h, n) * 1000
    y = x[::-1]
    plot = None
    for axis in axes.flat:
        axis.set_visible(False)
    for axis, row in zip(axes.flat, rows):
        axis.set_visible(True)
        style(axis)
        folder = c.ROOT / row['shape']
        raw = loadmat(folder / 'final_contrast.mat', simplify_cells=True)
        boundary = loadmat(folder / 'truth/geometry.mat', simplify_cells=True)['boundary']
        truth = c.base.Polygon(np.column_stack([boundary.real, boundary.imag]))
        _, image = c.base.score_field(raw['snapshots'][-1], (166, 166), raw['grid_x_primary_m'],
                                      raw['grid_y_primary_m'], truth)
        plot = axis.pcolormesh(x, y, image, shading='nearest', vmin=0, vmax=4, cmap=ramp, rasterized=True)
        peak = float(image.flat[np.argmax(np.abs(image))])
        axis.contour(x, y, np.sign(peak) * image, levels=[.5 * abs(peak)], colors=SURFACE, linewidths=1.3)
        axis.plot(boundary.real * 1000, boundary.imag * 1000, color=AMBER, lw=1.4, ls=(0, (4, 3)))
        axis.set_aspect('equal')
        axis.set_title(row['shape'], fontsize=11.5, color=INK, weight='bold', pad=20)
        five = row['csi_five_frequency_percent']
        detail = f"area error {row['area_error_percent']:.2f}%"
        detail += f" · at five {five:.2f}%" if five is not None else ''
        axis.text(.5, 1.012, detail, ha='center', va='bottom', transform=axis.transAxes, fontsize=9.5, color=MUTED)
    for axis in axes[-1]:
        axis.set_xlabel('x (mm)', color=MUTED, fontsize=9.5)
    for axis in axes[:, 0]:
        axis.set_ylabel('y (mm)', color=MUTED, fontsize=9.5)
    bar = fig.colorbar(plot, cax=fig.add_axes([.915, .23, .012, .55]))
    bar.set_label('Real susceptibility (truth 3 inside, 0 outside)', color=MUTED, fontsize=9.5)
    bar.ax.tick_params(colors=MUTED, labelsize=9)
    bar.outline.set_edgecolor(SPINE)
    fig.text(.5, .955, 'MF-CC-CSI images at ten frequencies, 0.25 to 2.5 GHz', ha='center',
             fontsize=17, weight='bold', color=INK)
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], color=AMBER, lw=1.4, ls=(0, (4, 3)), label='True boundary'),
                        Line2D([], [], color=SURFACE, lw=1.6, label='Support at half the image peak')],
               loc='lower center', bbox_to_anchor=(.475, .048), ncol=2, frameon=True, fontsize=9.5,
               labelcolor=RAMP[-1], facecolor=RAMP[1], edgecolor='none')
    fig.text(.475, .018, 'Saved final images after 2048 iterations on the frozen ten-frequency tables; '
             'one colour scale for all panels. Title line: area error at ten frequencies. No new solves.',
             ha='center', fontsize=9.5, color=MUTED)
    fig.savefig(path, dpi=140, facecolor=SURFACE)
    plt.close(fig)


def draw_errors(rows, path, plt):
    from matplotlib.lines import Line2D
    ordered = sorted(rows, key=lambda row: row['area_error_percent'])
    fig, axis = plt.subplots(figsize=(9.6, .52 * len(ordered) + 2.3), dpi=140, facecolor=SURFACE)
    fig.subplots_adjust(left=.14, right=.97, top=.8, bottom=.17)
    style(axis)
    for position, row in enumerate(ordered):
        for five, ten, hue in [(row['bem_five_frequency_percent'], row['bem_ten_frequency_percent'], BEM_HUE),
                               (row['csi_five_frequency_percent'], row['area_error_percent'], CSI_HUE)]:
            if five is not None:
                axis.plot([five, ten], [position, position], color=hue, lw=2, zorder=2, solid_capstyle='round')
                axis.plot(five, position, 'o', ms=12, mfc=SURFACE, mec=hue, mew=2, zorder=3)
            axis.plot(ten, position, 'o', ms=8.5, mfc=hue, mec=SURFACE, mew=1.2, zorder=4)
    axis.set_xscale('log')
    ticks = [.1, .2, .5, 1, 2, 5, 10, 20, 40]
    axis.set_xlim(.1, 40)
    axis.set_xticks(ticks)
    axis.set_xticklabels([f'{tick:g}%' for tick in ticks])
    axis.minorticks_off()
    axis.set_yticks(range(len(ordered)))
    axis.set_yticklabels([row['shape'] for row in ordered], color=INK, fontsize=10.5)
    axis.set_ylim(len(ordered) - .4, -.6)
    axis.grid(axis='x', color=SPINE, lw=.6, alpha=.6)
    axis.set_axisbelow(True)
    axis.tick_params(axis='y', length=0)
    for side in ['top', 'right', 'left']:
        axis.spines[side].set_visible(False)
    axis.set_xlabel('Area error (log scale; lower is better)', color=MUTED, fontsize=10)
    fig.text(.5, .945, 'Area error at five and ten frequencies', ha='center', fontsize=16, weight='bold', color=INK)
    fig.text(.5, .895, 'Table C simulated shapes at permittivity 4; both methods read the same frozen tables',
             ha='center', fontsize=10, color=MUTED)
    handles = [Line2D([], [], marker='o', ls='', ms=9, mfc=BEM_HUE, mec=SURFACE, label='Our BEM inverse'),
               Line2D([], [], marker='o', ls='', ms=9, mfc=CSI_HUE, mec=SURFACE, label='MF-CC-CSI'),
               Line2D([], [], marker='o', ls='', ms=11, mfc=SURFACE, mec=MUTED, mew=2, label='five frequencies'),
               Line2D([], [], marker='o', ls='', ms=8.5, mfc=MUTED, mec=SURFACE, label='ten frequencies')]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, .875), ncol=4, frameon=False,
               fontsize=9.5, labelcolor=MUTED, handletextpad=.3, columnspacing=1.6)
    missing = [row['shape'] for row in ordered if row['csi_five_frequency_percent'] is None]
    note = 'Saved scores only: MF-CC-CSI after 2048 iterations at half the image peak; BEM default method.'
    if missing:
        note += f"\nNo five-frequency MF-CC-CSI fit exists for {', '.join(missing)}. No new solves."
    else:
        note += ' No new solves.'
    fig.text(.5, .03, note, ha='center', fontsize=9, color=MUTED, linespacing=1.4)
    fig.savefig(path, dpi=140, facecolor=SURFACE)
    plt.close(fig)


def clock(seconds):
    return f'{int(seconds // 3600)}:{int(seconds % 3600 // 60):02d}'


def text(rows, campaign, activity, complete):
    shared = [row for row in rows if row['csi_five_frequency_percent'] is not None]
    errors = np.array([row['area_error_percent'] for row in rows])
    bems = np.array([row['bem_ten_frequency_percent'] for row in rows])
    best = min(rows, key=lambda row: row['area_error_percent'])
    worst = max(rows, key=lambda row: row['area_error_percent'])
    done = [row for row in rows if row['state'] == 'completed']
    full = [row for row in rows if row['iterations'] == 2048]
    lines = ['# MF-CC-CSI fits at ten frequencies', '']
    if not complete:
        lines += [f'**Preview: {len(rows)} of {len(c.SHAPES)} shapes have finished.**', '']
    span = f"Run {campaign['started_utc']} to {campaign.get('finished_utc', 'still running')}"
    if campaign.get('wall_seconds'):
        span += f": {len(rows)} outcomes in {clock(campaign['wall_seconds'])} wall time"
    lines += [span + '.',
              f'{len(done)} of {len(rows)} fits completed; {len(full)} reached 2048 iterations.',
              f"Half-peak area errors range from {best['area_error_percent']:.2f}% ({best['shape']}) to "
              f"{worst['area_error_percent']:.2f}% ({worst['shape']}).", '',
              'Settings: 0.25 to 2.5 GHz in 0.25 GHz steps, 2048 iterations, the 166 by 166 grid at 1.25 mm,',
              'native back-propagation, one centred start, eight compute threads. Only the frequency list',
              'differs from activity 07. The upstream code is unchanged. Up to three fits ran at once under',
              'the memory rule of the plan. No fit was stopped on time.', '',
              '## Ten-frequency results', '',
              '| Shape | Area error % (0.5) | Sensitivity % (0.3 / 0.7) | Mean permittivity | Contrast error % | Centre error mm | Native s | Wall s |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['shape']} | {row['area_error_percent']:.3f} | {row['sensitivity_03_percent']:.3f} / "
                     f"{row['sensitivity_07_percent']:.3f} | {row['mean_permittivity']:.4f} | "
                     f"{row['relative_contrast_error_percent']:.3f} | {row['centre_error_mm']:.3f} | "
                     f"{row['native_seconds']:.0f} | {row['wall_seconds']:.0f} |")
    lines += ['', '![Final images](figures/final_ten_shapes.png)', '',
              '## Against five frequencies and against BEM', '',
              'Both methods read the same frozen table at each frequency count. BEM numbers are read from the',
              "BEM side's saved `metrics.json` files; that side owns them.", '',
              '| Shape | CSI, ten | CSI, five | CSI change | BEM, ten | BEM, five | CSI / BEM at ten |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        five = row['csi_five_frequency_percent']
        change = '' if five is None else f"{row['area_error_percent'] - five:+.2f}"
        lines.append(f"| {row['shape']} | {row['area_error_percent']:.2f}% | "
                     f"{'not run' if five is None else f'{five:.2f}%'} | {change} | "
                     f"{row['bem_ten_frequency_percent']:.2f}% | {row['bem_five_frequency_percent']:.2f}% | "
                     f"{row['area_error_percent'] / row['bem_ten_frequency_percent']:.1f} |")
    lines += ['', '![Area error at five and ten frequencies](figures/area_error_five_and_ten_frequencies.png)', '',
              '## Findings', '']
    ratios = errors / bems
    lines += [f'- MF-CC-CSI at ten frequencies over {len(rows)} shapes: mean {errors.mean():.2f}%, median '
              f'{np.median(errors):.2f}%. BEM on the same tables: mean {bems.mean():.2f}%, median {np.median(bems):.2f}%.',
              f'- BEM has the lower error on {int((bems < errors).sum())} of {len(rows)} shapes. The ratio of the '
              f'CSI error to the BEM error runs from {ratios.min():.1f} to {ratios.max():.1f}.']
    if shared:
        ten = np.array([row['area_error_percent'] for row in shared])
        five = np.array([row['csi_five_frequency_percent'] for row in shared])
        bem_ten = np.array([row['bem_ten_frequency_percent'] for row in shared])
        bem_five = np.array([row['bem_five_frequency_percent'] for row in shared])
        change = ten - five
        lines += [f'- On the {len(shared)} shapes fitted by MF-CC-CSI at both counts, the ten-frequency error is lower on '
                  f'{int((ten < five).sum())} and higher on {int((ten > five).sum())}. Their mean moves from '
                  f'{five.mean():.2f}% to {ten.mean():.2f}%; the median from {np.median(five):.2f}% to {np.median(ten):.2f}%.',
                  f"- The CSI changes run from {change.min():+.2f} points ({shared[int(change.argmin())]['shape']}) to "
                  f"{change.max():+.2f} points ({shared[int(change.argmax())]['shape']}).",
                  f'- BEM on the same {len(shared)} shapes moves from a mean of {bem_five.mean():.2f}% to {bem_ten.mean():.2f}%, '
                  f'lower on {int((bem_ten < bem_five).sum())} of {len(shared)}.']
    permittivity = [row['mean_permittivity'] for row in rows]
    lines += [f'- Mean permittivity inside the half-peak support runs from {min(permittivity):.3f} to '
              f'{max(permittivity):.3f} against truth 4; it is below 4 on '
              f'{sum(value < 4 for value in permittivity)} of {len(rows)} shapes.',
              f"- Every final support is one piece without holes: "
              f"{'yes' if all(row['components'] == 1 and row['holes'] == 0 for row in rows) else 'no, see the scores'}."]
    lines += ['', '## Error during the fit', '',
              'Area error at half the image peak at each saved snapshot. The reported number is the one at 2048.', '',
              '| Shape | 256 | 512 | 1024 | 2048 | Lowest at |', '|---|---:|---:|---:|---:|---:|']
    early = []
    for row in rows:
        series = row['area_error_by_iteration']
        lowest = min(series, key=series.get)
        if lowest != '2048':
            early.append(row['shape'])
        lines.append(f"| {row['shape']} | " + ' | '.join(f'{series[key]:.2f}%' for key in ['256', '512', '1024', '2048'])
                     + f' | {lowest} |')
    lines += ['', f'The error is lowest at an earlier snapshot than 2048 on {len(early)} of {len(rows)} shapes'
              + (f" ({', '.join(early)})." if early else '.'),
              'No stopping rule picks the earlier snapshot without knowing the truth, so 2048 stays the reported number.', '',
              '## Limits', '',
              '- The table reports the fixed half-peak rule. The 0.3 and 0.7 columns show how much the cut-off matters.',
              '- Times are shared-machine times with up to three fits at once; they are not isolated timings.',
              '- Circle, kite and peanut have no five-frequency MF-CC-CSI fit. Their separate eight-frequency results',
              '  (' + ', '.join(f"{row['shape']} {row['csi_eight_frequency_percent']:.2f}%" for row in rows
                                if row['csi_eight_frequency_percent'] is not None)
              + ') use another frequency set, so the gap to this run is not an effect of the count alone.',
              '- One centred start and one noise-free table per shape: no spread over starts or noise is measured.', '',
              '## Runs and evidence', '',
              '| Shape | Start UTC | Finish UTC | Peak memory GiB | State |', '|---|---|---|---:|---|']
    for row in rows:
        folder = os.path.relpath(c.ROOT / row['shape'], activity)
        lines.append(f"| {row['shape']} | {row['started_utc']} | {row['finished_utc']} | "
                     f"{row['peak_family_rss_gib']:.1f} | [{row['state']}]({folder}/outcome.json) |")
    failures = [row['shape'] for row in rows if row['state'] != 'completed']
    alerts = (c.ROOT / 'alerts.jsonl').exists()
    root = os.path.relpath(c.ROOT, activity)
    lines += ['', f"Fit failures: {', '.join(failures) if failures else 'none'}. "
              f"Alerts: {'see ' + root + '/alerts.jsonl' if alerts else 'none'}.",
              f'The tables were checked before the first fit: [table checks]({root}/checks/table_checks.json).',
              f'Compact final measurements: [CSV]({root}/final_summary.csv) and [JSON]({root}/final_summary.json).',
              'Each case keeps scores at 256, 512, 1024 and 2048, costs, resources, the exact driver, the compressed',
              'native log and a SHA-256 manifest. Bulk histories, truths and tables stay local and ignored.',
              'Protocol 1 scoring is unchanged. No BEM solver or shared scoring code was edited.', '',
              'Rebuild this report and both figures, without a fit:', '', f'```bash\n{COMMAND}\n```', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial', type=Path, help='write a preview of the finished shapes into this folder')
    arguments = parser.parse_args()
    campaign = c.read(c.ROOT / 'campaign.json')
    rows = collect()
    complete = len(rows) == len(c.SHAPES) and bool(campaign.get('finished_utc'))
    if not complete and arguments.partial is None:
        raise RuntimeError('wait until the launcher has finished all ten shapes, or use --partial DIR')
    activity = c.ACT if arguments.partial is None else arguments.partial
    summary = c.ROOT if arguments.partial is None else arguments.partial
    figures = activity / 'figures'
    figures.mkdir(parents=True, exist_ok=True)
    record = dict(utc=c.now(), command=COMMAND, report_source_sha256=c.base.sha(Path(__file__)),
                  campaign=campaign, cases=rows)
    c.base.write(summary / 'final_summary.json', record)
    flat = [{key: value for key, value in row.items() if key != 'area_error_by_iteration'} for row in rows]
    with (summary / 'final_summary.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/csi-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    draw_images(rows, figures / 'final_ten_shapes.png', plt)
    draw_errors(rows, figures / 'area_error_five_and_ten_frequencies.png', plt)
    (activity / 'results.md').write_text(text(rows, campaign, activity if arguments.partial is None else c.ACT, complete))
    print(f'{len(rows)} shapes; complete: {complete}; wrote {activity}')


if __name__ == '__main__':
    main()
