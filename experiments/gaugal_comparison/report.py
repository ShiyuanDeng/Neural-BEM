"""Render the frozen three-arm TG-002 comparison from saved results only."""
import argparse
import csv
import json
from pathlib import Path
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse.io import curve_from
from experiments.benchmark import scenes as S
from . import ggb_scoring as G, tg002_data as D

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO/'results/validation/cleaned_interfaces'
MR = RESULTS/'MR-001'
GGB = RESULTS/'GGB-002'
DEST = REPO/'docs/iterations/gaugal_comparison/iteration_01'
LABELS = {'known': 'BEM: supplied contrast', 'material': 'BEM: recovered contrast', 'gaugal': 'GauGal'}


def read(path):
    return json.loads(path.read_text())


def finite(value):
    return isinstance(value, (int, float)) and np.isfinite(value)


def fmt(value, digits=3):
    return f'{value:.{digits}g}' if finite(value) else '—'


def shared_limits(row):
    return all(finite(row.get(k)) and row[k] <= limit for k, limit in
               [('rms_mm', 1.), ('hausdorff_upper_mm', 2.), ('maximum_residual', .003)])


def bem(case, material):
    arm = 'S2_slider_material_weak_start' if material else 'S1_slider_known_contrast'
    if not material and case.case_id in ('hook__c0.5', 'aphex_twin__c0.5'):
        arm = 'S3_slider_no_log_cap'
    path = MR/arm/'runs'/case.case_id/'result.json'
    data = read(path)
    contrast = data.get('final_contrast', case.contrast)
    image = G.bem_image(curve_from(data['final_curve']), contrast, 201)
    row = dict(status=data['outcome'], recovered=data['recovered'],
               contrast=contrast, maximum_residual=data.get('maximum_residual'),
               seconds=data.get('total_seconds'), iterations=None,
               source=str(path.relative_to(REPO)), **data['metrics'])
    row.update(G.image_scores(image, G.truth_image(case, 201)))
    row['meets_shared_limits'] = shared_limits(row)
    return row, image


def gaugal(case, preview=False):
    path = GGB/'G2_all'/f'{case.case_id}.json'
    if preview and not path.exists():
        path = GGB/'T0_timing'/f'{case.case_id}.json'
    if not path.exists():
        return dict(status='not_run', source=str(path.relative_to(REPO))), None
    data = read(path)
    row = dict(status=data.get('status', 'completed'), source=str(path.relative_to(REPO)),
               contrast=data.get('traced', {}).get('traced_contrast'),
               maximum_residual=data.get('maximum_residual'),
               seconds=data.get('wall_seconds'), iterations=data.get('iterations'),
               stop_reason=data.get('stop_reason'), **data.get('boundary', {}), **data.get('image', {}))
    row['meets_shared_limits'] = shared_limits(row)
    arrays = path.with_suffix('.npz')
    image = np.load(arrays)['image'] if arrays.exists() else None
    return row, image


def make_report(preview=False):
    destination = GGB/'report_preview' if preview else DEST
    destination.mkdir(parents=True, exist_ok=True)
    assets = destination/'comparison_figures'
    assets.mkdir(exist_ok=True)
    cases = list(S.CASES)[:3] if preview else list(S.CASES)
    rows, images, truths, objects = [], {}, {}, {}
    for case_id in cases:
        case = D.load(case_id)
        objects[case_id] = case
        truths[case_id] = G.truth_image(case, 201)
        group = dict(case=case_id, scene=case.scene, contrast=case.contrast)
        for key, function in [('known', lambda c: bem(c, False)),
                              ('material', lambda c: bem(c, True)), ('gaugal', lambda c: gaugal(c, preview))]:
            row, image = function(case)
            group[key] = row
            images[case_id, key] = image
        rows.append(group)
    attempted = sum(r['gaugal']['status'] != 'not_run' for r in rows)
    summary = dict(generated=time.strftime('%Y-%m-%d %H:%M:%S %Z'), cases=len(rows),
                   gaugal_attempted=attempted, complete=attempted == len(rows) and not preview,
                   rows=rows)
    (destination/'comparison.json').write_text(json.dumps(summary, indent=2)+'\n')
    columns = ['case', 'method', 'status', 'rms_mm', 'hausdorff_upper_mm', 'maximum_residual',
               'contrast', 'rrmse', 'ssim', 'psnr', 'contrast_snr_db', 'seconds', 'iterations',
               'recovered', 'meets_shared_limits', 'source']
    with (destination/'comparison.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for r in rows:
            for key in LABELS:
                writer.writerow(dict(case=r['case'], method=LABELS[key], **r[key]))
    for contrast in (0.5, 4., 13.3):
        selected = [r for r in rows if r['contrast'] == contrast]
        if not selected:
            continue
        fig, axes = plt.subplots(len(selected), 4, figsize=(11, 2.45*len(selected)), squeeze=False)
        chi = contrast-1
        for i, row in enumerate(selected):
            case_id = row['case']
            for j, key in enumerate(('truth', 'known', 'material', 'gaugal')):
                ax = axes[i, j]
                image = truths[case_id] if key == 'truth' else images[case_id, key]
                if image is not None:
                    ax.imshow(image/abs(chi), origin='upper', extent=(-100, 100, -100, 100),
                              cmap='coolwarm', vmin=-1.5, vmax=1.5, interpolation='nearest')
                    curve = objects[case_id].boundary*1000
                    ax.plot(curve.real, curve.imag, color='white', lw=.6, alpha=.8)
                else:
                    ax.set_facecolor('#eeeeee')
                    ax.text(.5, .5, row.get(key, {}).get('status', 'missing'),
                            ha='center', va='center', transform=ax.transAxes)
                ax.set_xlim(-100, 100); ax.set_ylim(-100, 100)
                ax.set_aspect('equal')
                ax.set_xticks([]); ax.set_yticks([])
                if i == 0:
                    ax.set_title('Truth' if key == 'truth' else LABELS[key], fontsize=10)
                if j == 0:
                    ax.set_ylabel(row['scene'].replace('_', ' '), fontsize=10)
                if key != 'truth':
                    ax.set_xlabel(f"RMS {fmt(row[key].get('rms_mm'))} mm · "
                                  f"contrast {fmt(row[key].get('contrast'))}", fontsize=8)
        fig.suptitle(f'Contrast {contrast:g} · susceptibility / |true susceptibility|\n'
                     'Common scale −1.5–1.5; white outline is truth; values outside scale are clipped', fontsize=11)
        fig.tight_layout(rect=(0, 0, .93, .97 if len(selected)>1 else .84))
        color_axis = fig.add_axes([.95, .12, .012, .65])
        fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(-1.5, 1.5), cmap='coolwarm'), cax=color_axis)
        fig.savefig(assets/f'gallery_c{contrast:g}.png', dpi=140)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for key, color in zip(LABELS, ('#2374ab', '#e08a28', '#6b4c9a')):
        x = np.arange(len(rows))
        for ax, metric, threshold in zip(axes, ('rms_mm', 'maximum_residual'), (1., .003)):
            values = [r[key].get(metric, np.nan) for r in rows]
            values = [v if finite(v) and v > 0 else np.nan for v in values]
            ax.plot(x, values, '.', color=color, label=LABELS[key], alpha=.85)
            ax.set_yscale('log'); ax.set_xlabel('TG-002 case index'); ax.grid(alpha=.2)
            ax.set_ylabel('Boundary RMS (mm)' if metric == 'rms_mm' else 'Maximum relative field residual')
    axes[0].axhline(1, color='black', ls='--', lw=.8)
    axes[1].axhline(.003, color='black', ls='--', lw=.8)
    axes[0].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(assets/'errors.png', dpi=160); plt.close(fig)

    def median(key, metric):
        values = [r[key].get(metric) for r in rows if finite(r[key].get(metric))]
        return fmt(float(np.median(values))) if values else '—'

    title = 'BEM and GauGal on TG-002 — 30-case comparison'
    text = [f'# {title}', '', f"Generated {summary['generated']}.", '',
        f"**{'All cases attempted' if summary['complete'] else 'INCOMPLETE'}:** GauGal outcomes "
        f"for {attempted}/{len(rows)} cases. Failed and time-limited outcomes are retained.", '',
        'Three separate arms use the same noiseless TG-002 observations and geometry. '
        'BEM with supplied contrast knows the true contrast. BEM material recovery and GauGal estimate it. '
        'BEM also uses damped-frequency warm-up data; GauGal uses the 19 real frequencies only.', '',
        '## Aggregate results', '',
        '| Arm | Saved images | Shared shape/field limits | Full BEM recovery | Median RMS mm | '
        'Median image RRMSE | Median recorded seconds |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for key in LABELS:
        count = sum(images[r['case'], key] is not None for r in rows)
        shared = sum(bool(r[key].get('meets_shared_limits')) for r in rows)
        recovered = str(sum(bool(r[key].get('recovered')) for r in rows)) if key != 'gaugal' else 'not applicable'
        text.append(f'| {LABELS[key]} | {count} | {shared} | {recovered} | {median(key,"rms_mm")} | '
                    f'{median(key,"rrmse")} | {median(key,"seconds")} |')
    text += ['', 'Shared limits are RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm and maximum relative '
             'field residual ≤ 0.003. Full BEM recovery additionally requires its independent final '
             'numerical checks. GauGal has no equivalent BEM Jacobian check; its shared-limit count is '
             'not claimed as full TG-002 numerical qualification.', '',
             '![Errors across all cases](comparison_figures/errors.png)', '',
             '## Per-case results', '',
             'Triples below are **supplied-contrast BEM / material-recovery BEM / GauGal**. '
             'A dash means no finite value was available. Circle cases were used for GauGal tuning.', '',
             '| Case | RMS mm | Maximum field residual | Image RRMSE | GauGal status / iterations |',
             '|---|---|---|---|---|']
    for row in rows:
        triples = [' / '.join(fmt(row[key].get(metric)) for key in LABELS)
                   for metric in ('rms_mm', 'maximum_residual', 'rrmse')]
        text.append(f"| {row['case']} | {' | '.join(triples)} | {row['gaugal']['status']} / "
                    f"{row['gaugal'].get('iterations', '—')} |")
    tuning = GGB/'G1_tuning/tuning.json'
    selection = read(tuning)['chosen'] if tuning.exists() else None
    text += ['', '## Methods and interpretation', '',
        '**BEM selection was fixed before GauGal results.** Supplied-contrast BEM is slider S1 with '
        'both degree-cap cases replaced by S3, for 26/30 recorded recoveries. The other cases never '
        'hit that cap and reuse their unchanged paths. This is combined evidence, not a new full '
        'campaign. It ties spectral R1’s 26/30. Material recovery uses S2, the best completed '
        'truth-free full campaign at 23/30; truth-assisted R3 starts are excluded.', '',
        'The sampled-log-interval experiments S4/S4b are not selected: they added no confirmed '
        'recoveries, and two cases timed out. Supplied-contrast BEM removes the degree cap; S2 retains '
        'its earlier numerical settings. Full source paths and all scores are in '
        '[comparison.csv](comparison.csv) and [comparison.json](comparison.json).', '',
        '**GauGal adaptation.** One susceptibility image is fitted to a sum of energy-normalized '
        'frequency losses on 24 source–receiver pairs at 19 real frequencies. Gaussian lattice 51×51, '
        '201×201 quadrature pixels, width 0.7 lattice spacing, TV lambda scale 0.5, susceptibility '
        'bounds −0.9 to 15, released 100-iteration inner-solve cap. Initialization is zero susceptibility. '
        'Step sizes 1, 0.01 and 0.05 are tuned on the three circles only by mean image RRMSE. '
        'The two smaller steps replaced unrun larger steps after step 1 diverged on circle c0.5.', '',
        f"Chosen tuning result: `{json.dumps(selection)}`." if selection else 'Tuning selection is not yet available.', '',
        'The final common budget is at most 80 outer iterations and 400 seconds of optimization, '
        'with a 480-second outer process limit. The T0 timing fit required 50.1 seconds for ten '
        'iterations, so the original 300-iteration default could not fit the morning budget. '
        'Partial images have explicit stop reasons and actual iteration counts; an iteration-limit '
        'exit does not establish convergence. Final inner-solve summaries are retained in the case JSON.', '',
        '**Forward-model limitation.** The existing seven-case sweep did not identify any tested '
        'lattice meeting 1% error across those cases at 0.75 GHz and above. All 19 real frequencies '
        'are retained here rather than discarding 18 frequencies. Thus this measures this TG-002 '
        'adaptation under its stated budget; it is not a reproduction of GauGal’s published benchmark '
        'and does not establish an intrinsic ranking of the methods.', '',
        '**Scores and times.** Both image arms are rasterized on the same 1 mm grid. RRMSE, SSIM and '
        'PSNR use relative permittivity; contrast SNR uses susceptibility. GauGal’s longest closed '
        'half-peak contour supplies its boundary and mean interior contrast. All image scores, '
        'contrast estimates and Hausdorff bounds are in the CSV. BEM seconds are recorded fit times; '
        'GauGal seconds include process, operator build and scoring, so they are not pure optimizer '
        'speed ratios. GauGal JSON separates build and optimizer times. Failed BEM fits can stop early.', '',
        '## Reconstruction gallery', '']
    for contrast in (0.5, 4., 13.3):
        if any(r['contrast'] == contrast for r in rows):
            text += [f'### Contrast {contrast:g}', '',
                     f'![Contrast {contrast:g} reconstructions](comparison_figures/gallery_c{contrast:g}.png)', '']
    (destination/'report.md').write_text('\n'.join(text)+'\n')
    assert len(rows) == (3 if preview else 30)
    print(f'Report: {destination / "report.md"}; GauGal attempted {attempted}/{len(rows)}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true')
    make_report(parser.parse_args().preview)
