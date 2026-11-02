"""Render the frozen three-arm TG-002 comparison from saved results only."""
import argparse
import csv
import json
import os
from pathlib import Path
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse.io import curve_from
from experiments.benchmark import scenes as S
from . import ggb_scoring as G, tg002_data as D
from . import report_evidence as E

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
    row.update(E.bem_evidence(data, path, row, case.contrast, case.frequencies_hz, REPO))
    return row, image


def gaugal(case, preview=False):
    path = GGB/'G2_all'/f'{case.case_id}.json'
    if preview and not path.exists():
        path = GGB/'T0_timing'/f'{case.case_id}.json'
    if not path.exists():
        return dict(status='not_run', source=str(path.relative_to(REPO)),
                    recovery_status='not attempted', failure_reason='No saved outcome yet.',
                    evidence=[]), None
    data = read(path)
    row = dict(status=data.get('status', 'completed'), source=str(path.relative_to(REPO)),
               contrast=data.get('traced', {}).get('traced_contrast'),
               maximum_residual=data.get('maximum_residual'),
               seconds=data.get('wall_seconds'), iterations=data.get('iterations'),
               stop_reason=data.get('stop_reason'), **data.get('boundary', {}), **data.get('image', {}))
    row['meets_shared_limits'] = shared_limits(row)
    row.update(E.gaugal_evidence(data, path, row, case.contrast, REPO))
    arrays = path.with_suffix('.npz')
    image = np.load(arrays)['image'] if arrays.exists() else None
    return row, image


def link(path, destination, label):
    return f'[{label}]({os.path.relpath(REPO/path, destination)})'


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def full_tables(rows, destination):
    text = ['', '## Complete scores for each arm', '',
            'Contrast error is signed relative error in percent. PSNR and contrast SNR are in dB. '
            'All rows, including unsuccessful fits, contribute to the reported medians.', '']
    for key, label in LABELS.items():
        text += [f'### {label}', '',
                 '| Case | RMS mm | Hausdorff upper mm | Max field residual | Contrast | Error % | Seconds | Recovery |',
                 '|---|---:|---:|---:|---:|---:|---:|---|']
        for group in rows:
            row = group[key]
            values = [fmt(row.get(metric), 5) for metric in
                      ('rms_mm', 'hausdorff_upper_mm', 'maximum_residual', 'contrast')]
            error = row.get('contrast_relative_error')
            text.append(f"| {group['case']} | {' | '.join(values)} | "
                        f"{fmt(100*error if finite(error) else None, 5)} | {fmt(row.get('seconds'), 5)} | "
                        f"{row['recovery_status']} |")
        text += ['', '| Case | RRMSE | SSIM | PSNR dB | Contrast SNR dB |',
                 '|---|---:|---:|---:|---:|']
        for group in rows:
            values = [fmt(group[key].get(metric), 5) for metric in
                      ('rrmse', 'ssim', 'psnr', 'contrast_snr_db')]
            text.append(f"| {group['case']} | {' | '.join(values)} |")
        text += ['', f'### {label}: per-case stopping and failure reasons', '',
                 '| Case | Recorded stop | Observed reason / remaining failure | Saved evidence |',
                 '|---|---|---|---|']
        for group in rows:
            row = group[key]
            evidence = ', '.join(link(p, destination, 'result' if i == 0 else 'final checks')
                                 for i, p in enumerate(row['evidence']))
            text.append(f"| {group['case']} | {cell(row.get('stop_reason', row['status']))} | "
                        f"{cell(row['failure_reason'])} | {evidence or '—'} |")
        text.append('')
    return text


def tuning_and_forward(destination):
    text = ['', '## Tuning and saved forward evidence', '']
    tuning_path = GGB/'G1_tuning/tuning.json'
    if tuning_path.exists():
        tuning = read(tuning_path)
        text += [f"Frozen common step: **{tuning['chosen']['step']:g}**. "
                 + link(str(tuning_path.relative_to(REPO)), destination, 'Selection and all tuning scores')+'.', '',
                 '| Step | Circle c0.5 RRMSE | Circle c4 RRMSE | Circle c13.3 RRMSE | Mean RRMSE | Finite circles |',
                 '|---:|---:|---:|---:|---:|---:|']
        for setting in tuning['table']:
            scores = ' | '.join(fmt(r['rrmse'], 5) for r in setting['rows'])
            text.append(f"| {setting['step']:g} | {scores} | {fmt(setting['mean_rrmse'], 5)} | "
                        f"{setting['finite_cases']}/3 |")
        text += ['', 'The circle cases are tuning data, so their final scores are not held-out scores. '
                 'No further settings were selected using the other 27 cases.', '']
        text += ['| Step / circle | Stop | Observed limitations | Evidence |', '|---|---|---|---|']
        for setting in tuning['table']:
            for saved in setting['rows']:
                folder = f"step{setting['step']}"
                path = GGB/'G1_tuning'/folder/(saved['case']+'.json')
                data = read(path)
                row = dict(contrast=data.get('traced', {}).get('traced_contrast'),
                           maximum_residual=data.get('maximum_residual'), **data.get('boundary', {}))
                row['meets_shared_limits'] = shared_limits(row)
                info = E.gaugal_evidence(data, path, row, float(saved['case'].split('__c')[1]), REPO)
                text.append(f"| {setting['step']:g} / {saved['case']} | {data.get('stop_reason')} | "
                            f"{cell(info['failure_reason'])} | "
                            f"{link(str(path.relative_to(REPO)), destination, 'result')} |")
        text.append('')
    records = []
    for path in sorted((RESULTS/'FW-001/F2_gaugal_sweep').glob('*.json')):
        data = read(path)
        selected = [r for r in data['rows'] if r['grid'] == 51 and r['sigma_scale'] == .7]
        records.append((path, data['case'], selected))
    text += ['Existing forward checks at the selected lattice and width (relative field errors). '
             'These use truth-shaped coefficients and a 2,000-iteration inner cap. '
             'The inverse uses a cap of 100. These seven cases do not certify all 30 cases.', '',
             '| Case | 0.25 GHz | 0.75 GHz | 1.25 GHz | 1.75 GHz | 2.5 GHz | Unconverged forward solves |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for path, case, selected in records:
        by_frequency = {r['frequency_hz']: r for r in selected}
        values = [fmt(by_frequency.get(f, {}).get('relative_error'), 5)
                  for f in (.25e9, .75e9, 1.25e9, 1.75e9, 2.5e9)]
        bad = sum(not r.get('linear_solve', {}).get('converged') for r in selected)
        text.append(f"| {link(str(path.relative_to(REPO)), destination, case)} | {' | '.join(values)} | "
                    f"{bad}/{len(selected)} |")
    text += ['', 'Forward discrepancies combine representation error and remaining inner-solve error; '
             'the saved checks do not isolate either contribution. Likewise, unsuccessful inner solves '
             'in an inverse fit are evidence of approximate fields/gradients, not proof that this alone '
             'caused its reconstruction error.', '']
    return text


def diagnostic_bem(destination):
    text = ['', '## Earlier BEM diagnostic failures and timeouts', '',
            'S4/S4b bypassed the inconclusive bound using a sampled interval. These outputs are '
            'preserved as diagnostics and do not replace either frozen comparison arm. '
            'Neither a timeout nor a visually close curve is counted as recovery.', '',
            '| Run / case | Outcome | Observed reason | Evidence |', '|---|---|---|---|']
    for arm, case, relative in [
        ('S4', 'cog__c13.3', 'S4_slider_sampled_log_interval'),
        ('S4b', 'aphex_twin__c4', 'S4b_slider_sampled_log_interval/aphex_twin__c4'),
    ]:
        path = MR/relative/'runs'/case/'result.json'
        data = read(path)
        truth = D.load(case)
        row = dict(contrast=truth.contrast, maximum_residual=data.get('maximum_residual'), **data['metrics'])
        info = E.bem_evidence(data, path, row, truth.contrast, truth.frequencies_hz, REPO)
        refs = ', '.join(link(p, destination, 'result' if i == 0 else 'final checks')
                         for i, p in enumerate(info['evidence']))
        text.append(f"| {arm} / {case} | not recovered | {cell(info['failure_reason'])} | {refs} |")
    prefix = 'results/validation/cleaned_interfaces/MR-001/'
    text += [
        '| S4 / aphex_twin__c0.5 | timeout; no final result | The 900 s campaign limit expired '
        'while fixed_M25 was active. Last completed-stage checkpoint: release_M19 at 702.6 s of fit work. '
        'No final numerical checks or recovery score exist. | '
        + link(prefix+'S4_slider_sampled_log_interval/execution_status.json', destination, 'exit 124')+', '
        + link(prefix+'S4_slider_sampled_log_interval/runs/aphex_twin__c0.5/checkpoint.json', destination, 'checkpoint')+' |',
        '| S4b / aphex_twin__c13.3 | timeout; no final result | The 300 s case limit expired '
        'while fixed_M85 was active. Last completed-stage checkpoint: fixed_M79 at 289.0 s of fit work. '
        'No final numerical checks or recovery score exist. | '
        + link(prefix+'S4b_slider_sampled_log_interval/aphex_twin__c13.3/exit_code.txt', destination, 'exit 124')+', '
        + link(prefix+'S4b_slider_sampled_log_interval/aphex_twin__c13.3/runs/aphex_twin__c13.3/checkpoint.json', destination, 'checkpoint')+' |',
        '', 'The timeout records establish budget exhaustion. They do not establish that either '
        'fit would recover with more time. The saved active stages distinguish time spent '
        'progressing through the fit from an immediate numerical refusal.', '']
    return text


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
    summary = E.json_safe(summary)
    (destination/'comparison.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    columns = ['case', 'method', 'status', 'rms_mm', 'hausdorff_upper_mm', 'maximum_residual',
               'contrast_true', 'contrast', 'contrast_absolute_error', 'contrast_relative_error',
               'rrmse', 'ssim', 'psnr', 'contrast_snr_db', 'seconds', 'iterations',
               'fit_seconds', 'final_check_seconds', 'build_seconds', 'optimize_seconds',
               'recovered', 'meets_shared_limits', 'recovery_status', 'stop_reason', 'failure_reason',
               'final_checks_passed', 'final_field_discrepancy', 'final_jacobian_discrepancy',
               'final_trial_fd_discrepancy', 'inner_solve_calls', 'inner_solves_unconverged',
               'inner_solve_max_relative', 'process_returncode', 'source']
    with (destination/'comparison.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for r in rows:
            for key in LABELS:
                writer.writerow(E.json_safe(dict(case=r['case'], method=LABELS[key], **r[key])))
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
                    outcome = ('recovered' if row[key].get('recovered') else 'not recovered') if key != 'gaugal' \
                        else row[key].get('stop_reason', row[key]['status'])
                    ax.set_xlabel(f"RMS {fmt(row[key].get('rms_mm'))} mm · "
                                  f"contrast {fmt(row[key].get('contrast'))}\n{outcome}", fontsize=8)
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
        'Three separate arms use the same noiseless TG-002 real-frequency observations and geometry. '
        'BEM with supplied contrast knows the true contrast. BEM material recovery and GauGal estimate it. '
        'BEM also uses damped-frequency continuation data; GauGal uses the 19 real frequencies only.', '',
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
    text += full_tables(rows, destination)
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
        '| Arm | Material information | Representation / start | Frequency data |',
        '|---|---|---|---|',
        '| BEM supplied contrast | True contrast supplied | One homogeneous object bounded by a Fourier curve; centred 65 mm circle | Real and damped continuation catalogs |',
        '| BEM material recovery | Truth-free weak-scatterer contrast estimate | Same single-object curve prior and centred circle | Real and damped continuation catalogs |',
        '| GauGal | No true contrast supplied; common susceptibility bounds | 2,601 Gaussian coefficients; zero susceptibility start | 19 real frequencies |', '',
        'Each real frequency has 24 complex source–receiver measurements: 456 complex observations '
        'in total. GauGal’s 201×201 grid is used for quadrature and images, while its 51×51 lattice '
        'contains the unknown coefficients. BEM’s single homogeneous region is a stronger shape '
        'and material prior than GauGal’s spatially varying image.', '',
        '**GauGal adaptation.** One susceptibility image is fitted to a sum of energy-normalized '
        'frequency losses on 24 source–receiver pairs at 19 real frequencies. Gaussian lattice 51×51, '
        '201×201 quadrature pixels, width 0.7 lattice spacing, TV lambda scale 0.5, susceptibility '
        'bounds −0.9 to 15, released 100-iteration inner-solve cap. Initialization is zero susceptibility. '
        'Step sizes 1, 0.01 and 0.05 are tuned on the three circles only by mean image RRMSE. '
        'The two smaller steps replaced unrun larger steps after step 1 diverged on circle c0.5.', '',
        f"Chosen common step: **{selection['step']:g}**." if selection else 'Tuning selection is not yet available.', '',
        'The final common budget is at most 80 outer iterations and 400 seconds of optimization, '
        'with a 480-second outer process limit. The T0 timing fit required 50.1 seconds for ten '
        'iterations, so the original 300-iteration default could not fit the morning budget. '
        'Partial images have explicit stop reasons and actual iteration counts; an iteration-limit '
        'exit does not establish convergence. Inner-solve summaries cover the whole fit, including '
        'the final prediction. Their convergence tolerance is 1e-4. The saved `completed` status '
        'means the iteration budget finished, not that an accuracy target was reached.', '',
        '**Forward-model limitation.** The existing seven-case sweep did not identify any tested '
        'lattice meeting 1% error across those cases at 0.75 GHz and above. All 19 real frequencies '
        'are retained here rather than discarding 18 frequencies. Thus this measures this TG-002 '
        'adaptation under its stated budget; it is not a reproduction of GauGal’s published benchmark '
        'and does not establish an intrinsic ranking of the methods.', '',
        '**Scores and times.** All three image arms are rasterized on the same 1 mm grid. RRMSE, SSIM and '
        'PSNR use relative permittivity; contrast SNR uses susceptibility. GauGal’s longest closed '
        'half-peak contour supplies its boundary and mean interior contrast. All image scores, '
        'contrast estimates and Hausdorff bounds are in the CSV. BEM seconds include the fit and final checks; '
        'GauGal seconds include process, operator build and scoring, so they are not pure optimizer '
        'speed ratios. CSV/JSON also separate the available component times. Failed BEM fits can stop early.', '',
        'The overnight machine has an NVIDIA GeForce RTX 5090 (32,607 MiB reported), '
        'an Intel Core Ultra 9 285K and Python 3.9.25. At 02:42 London, the active GauGal '
        'worker was the only GPU compute process. The broad forward sweeps remained paused. '
        'Report scoring briefly ran on the CPU while tuning continued.', '',
        'Image scores use the relative-to-background permittivity image. Pixel-exact BEM '
        'rasterizations can produce zero image RRMSE and very large finite PSNR/SNR from '
        'the metric routines’ denominator floors; this does not imply an exactly recovered curve.', '',
        '**Reading failure reasons.** A trial curve can be refused while the last accepted curve '
        'passes numerical checks. A failed positive-lower-bound calculation is inconclusive; '
        'it does not establish that the trial curve is invalid. The four supplied-contrast failures '
        'all stop on that calculation in the selected records.', '',
        'In the material arm, circle c13.3 and aphex c4/c13.3 meet the shared shape/field limits '
        'but fail final numerical comparisons. Asymmetric and cross c13.3 show large contrast '
        'drift in the saved warm-up histories, before numerical refusal. Cog c13.3 also drifts '
        'in warm-up and returns toward the truth, but still ends at the wrong contrast and large residual.', '',
        'Final BEM field refinement tolerances are 1e-5 through 0.5 GHz and 1e-7 above it; '
        'Jacobian and complete-trial finite-difference tolerances are 0.001. These numerical '
        'discrepancies are separate from the 0.003 measurement-residual limit.', '',
        'For GauGal, a budget stop explains why computation ended; the scored shape and field '
        'errors explain why the saved output is unsuccessful. Limited iterations, approximate '
        'inner solves and representation error may each contribute. Their individual causal '
        'contributions are not established by these runs. Logged losses use extrapolated iterates '
        'and are not identical to the separately recomputed final field residual.', '']
    text += tuning_and_forward(destination)
    text += diagnostic_bem(destination)
    text += ['', '## Reconstruction gallery', '',
             'White outlines show truth. Every saved output is displayed, including inaccurate '
             'or partial outputs. Color clipping makes severely wrong material values less visible; '
             'read the contrast labels and failure tables alongside the images.', '']
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
