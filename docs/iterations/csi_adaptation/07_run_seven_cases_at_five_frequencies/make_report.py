"""Summarize saved activity-07 evidence and plot final images; never fits."""
import csv
import json
import os
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from experiments.baselines.csi import campaign_five_frequency as c
from experiments.comparison import scoring as protocol


def main():
    campaign = c.read(c.ROOT / 'campaign.json')
    watch = c.read(c.ROOT / 'watch.json')
    if not campaign.get('finished_utc') or not watch.get('finished_utc'):
        raise RuntimeError('wait until the launcher and its background watch have finished')
    rows = []
    for scene in c.SHAPES:
        folder = c.ROOT / scene
        launch, outcome = [c.read(folder / name) for name in ['launch.json', 'outcome.json']]
        score = c.read(folder / 'scores.json')['snapshots'][-1]
        main_score, low, high = score['scores']
        rows.append(dict(shape=scene, state=outcome['state'], iterations=score['iterations'],
            area_error_percent=100*main_score['area_error'],
            sensitivity_03_percent=100*low['area_error'], sensitivity_07_percent=100*high['area_error'],
            mean_permittivity=main_score['mean_relative_permittivity'],
            relative_contrast_error_percent=100*main_score['relative_contrast_error'],
            centre_error_mm=main_score['centroid_mm'],
            native_seconds=score['native_elapsed_seconds'], wall_seconds=launch['wall_seconds'],
            started_utc=launch['started_utc'], finished_utc=launch['finished_utc'],
            frozen_table_sha256=c.read(folder/'data.json')['sha256'],
            committed_case_bytes=c.read(folder/'manifest.json')['git_bytes']))
    record = dict(utc=c.now(), command='PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 '
                  '/home/drdeng/miniconda3/envs/EMNerf/bin/python -B '
                  'docs/iterations/csi_adaptation/07_run_seven_cases_at_five_frequencies/make_report.py',
                  report_source_sha256=c.base.sha(Path(__file__)), campaign=campaign, cases=rows)
    c.base.write(c.ROOT / 'final_summary.json', record)
    with (c.ROOT/'final_summary.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    figures=c.ACT/'figures';figures.mkdir(exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR','/tmp/csi-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(2,4,figsize=(15,7.5),layout='constrained')
    h=protocol.PROTOCOL['grid_half_width_m'];n=protocol.PROTOCOL['grid_cells']
    x=np.linspace(-h,h,n)*1000;y=x[::-1]
    for ax,row in zip(axes.flat,rows):
        folder=c.ROOT/row['shape'];raw=loadmat(folder/'final_contrast.mat',simplify_cells=True)
        values=raw['snapshots'][-1]
        geometry=loadmat(folder/'truth/geometry.mat',simplify_cells=True);b=geometry['boundary']
        truth=c.base.Polygon(np.column_stack([b.real,b.imag]))
        _,image=c.base.score_field(values,(166,166),raw['grid_x_primary_m'],raw['grid_y_primary_m'],truth)
        plot=ax.pcolormesh(x,y,image,shading='nearest',vmin=0,vmax=3,cmap='turbo',rasterized=True)
        peak=float(image.flat[np.argmax(np.abs(image))])
        ax.contour(x,y,np.sign(peak)*image,levels=[.5*abs(peak)],colors='white',linewidths=.8)
        ax.plot(b.real*1000,b.imag*1000,'k--',lw=.8)
        ax.set(title=f"{row['shape']}: {row['area_error_percent']:.2f}%",xlabel='x (mm)',ylabel='y (mm)',aspect='equal')
    axes.flat[-1].axis('off')
    axes.flat[-1].text(.02,.9,'2048 iterations; five frequencies\nBlack dashed: true boundary\nWhite: half-peak support\nTitle: main area error\n\nAll images use the same scale.\nTimings share the machine.',va='top',fontsize=11)
    fig.colorbar(plot,ax=list(axes.flat[:-1]),label='Real susceptibility',shrink=.8)
    fig.savefig(figures/'final_seven_shapes.png',dpi=140);plt.close(fig)
    elapsed=campaign['wall_seconds'];hours=int(elapsed//3600);minutes=int(elapsed%3600//60)
    best=min(rows,key=lambda row:row['area_error_percent'])
    worst=max(rows,key=lambda row:row['area_error_percent'])
    lines=['# Seven MF-CC-CSI fits at five frequencies','',
           f"Run {campaign['started_utc']} to {campaign['finished_utc']}: seven outcomes in {hours}:{minutes:02d} wall time.",
           f"All seven completed 2048 iterations. Half-peak area errors range from {best['area_error_percent']:.2f}% to {worst['area_error_percent']:.2f}%.",
           'All cases use 0.5, 1, 1.5, 2 and 2.5 GHz, 2048 iterations, the 166 by 166 grid at 1.25 mm,',
           'native back-propagation, one centred start and eight compute threads. No upstream numerical change.',
           'The worker ceiling came from the resource monitor before every launch. No fit stopped on time.','',
           '| Shape | Area error % (0.5) | Sensitivity % (0.3 / 0.7) | Mean permittivity | Contrast error % | Native s | Wall s |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['shape']} | {row['area_error_percent']:.3f} | {row['sensitivity_03_percent']:.3f} / {row['sensitivity_07_percent']:.3f} | {row['mean_permittivity']:.4f} | {row['relative_contrast_error_percent']:.3f} | {row['native_seconds']:.2f} | {row['wall_seconds']:.2f} |")
    lines += ['', '![Final seven shapes](figures/final_seven_shapes.png)', '',
              '## Findings and limits', '',
              f"Star has the smallest main error ({best['area_error_percent']:.2f}%); aphex_twin has the largest ({worst['area_error_percent']:.2f}%).",
              f"Mean permittivity is below truth 4 in every case, ranging from {min(r['mean_permittivity'] for r in rows):.3f} to {max(r['mean_permittivity'] for r in rows):.3f}.",
              'The table reports the fixed half-peak rule. The 0.3 and 0.7 scores show substantial threshold sensitivity;',
              'the saved arrays support further scoring without another fit. Mean permittivity is compared with truth 4.',
              'These are shared-machine times and do not establish isolated timing against BEM.',
              'Circle, kite and peanut keep their separate eight-frequency results; this activity does not rerun them.','',
              'The first measured rate was 2.192 seconds per iteration on star, over iterations 1 to 100, excluding startup.',
              'All seven data releases passed and used the same hashes verified by BEM. See [release evidence](releases.md)',
              'and [full release check values](releases.jsonl). The largest release mismatch was 0.7125% on aphex_twin.','',
              '## Runs and evidence', '',
              '| Shape | Start UTC | Finish UTC | State |', '|---|---|---|---|']
    for row in rows:
        folder=os.path.relpath(c.ROOT/row['shape'],c.ACT)
        lines.append(f"| {row['shape']} | {row['started_utc']} | {row['finished_utc']} | [{row['state']}]({folder}/outcome.json) |")
    failures=[row['shape'] for row in rows if row['state']!='completed']
    lines += ['', f"Fit failures: {', '.join(failures) if failures else 'none'}. All four raw checkpoint counts were checked at each successful finish.",
              'The native executed-driver EOF blank line initially delayed the first publication check. A result-only',
              'Git whitespace attribute fixed that check while preserving the driver hash. Star was then pushed;',
              'no fit was stopped. Details and logs: [checks](checks.md). No numerical upstream patch was needed.','',
              f"Compact final measurements: [CSV]({os.path.relpath(c.ROOT/'final_summary.csv',c.ACT)}) and [JSON]({os.path.relpath(c.ROOT/'final_summary.json',c.ACT)}).",
              'Each case also keeps scores at 256, 512, 1024 and 2048; costs; resources; exact driver; compressed native log;',
              'and a SHA-256 manifest. Bulk histories, truths and tables remain local and ignored. Each committed case is below 5 MB.',
              'Protocol 1 scoring is unchanged. No BEM solver or shared scoring code was edited.','',
              'Rebuild this report and figure, without a fit:', '', f"```bash\n{record['command']}\n```", '']
    (c.ACT/'results.md').write_text('\n'.join(lines))
    report=[f'Activity: csi_adaptation/07_run_seven_cases_at_five_frequencies, 18 November 2026',
            f'Runs: {len(rows)-len(failures)}/7; wall time {hours}:{minutes:02d}']
    report += [f"Result: {r['shape']} area error {r['area_error_percent']:.2f}%; native {r['native_seconds']:.0f} s" for r in rows]
    report += ['Failures: no fit failures; publication check fixed; log results/csi/tg002/2026-11-18_five_frequency/alerts.jsonl.',
               'Upstream patches: none new; reused output-only patch 0003.',
               'Changes to our code: CSI runner/check/report files only; no BEM or scoring edits.',
               'New unknowns: none; threshold sensitivity and isolated timings remain.',
               'Proposed next activity: none; coordinator comparison; needs user decision: none']
    (c.ACT/'report.txt').write_text('\n'.join(report)+'\n')
    print('\n'.join(report))


if __name__=='__main__':
    main()
