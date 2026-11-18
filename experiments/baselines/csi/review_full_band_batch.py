"""Read the completed/pushed eight-frequency batch and write its review pack."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import re

import numpy as np
import psutil
from scipy.io import loadmat

from experiments.baselines.csi import campaign as base
from experiments.baselines.csi.campaign_low_band import verify_parent_push

ROOT=base.REPO/'results/csi/tg002/2026-11-17_campaign'
ACT=base.REPO/'docs/iterations/csi_adaptation/04_run_simulated_tg002_cases'
SCENES=['circle','kite','peanut']


def read(path):return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--published-commit',required=True)
    args=parser.parse_args()
    campaign=read(ROOT/'campaign.json')
    assert campaign.get('finished_utc'),'old launcher must finish by itself first'
    try:
        assert psutil.Process(campaign['launcher_pid']).status()==psutil.STATUS_ZOMBIE,'old launcher is still alive'
    except psutil.NoSuchProcess:pass
    verify_parent_push(args.published_commit)
    pack=dict(utc=base.now(),published_commit=args.published_commit,campaign=campaign,
              first_batch_forecast=read(ROOT/'first_batch_forecast.json'),cases=[],
              figure=str(ACT/'figures/batch_1.png'),all_further_fits_held=True,
              source_sha256=base.sha(Path(__file__)))
    assert Path(pack['figure']).exists()
    rows=[];odd=[]
    for scene in SCENES:
        folder=ROOT/scene
        outcome=read(folder/'outcome.json');launch=read(folder/'launch.json');summary=read(folder/'matlab_summary.json')
        assert outcome['state']=='completed' and outcome['returncode']==launch['returncode']==0
        assert summary['iterations']==2048 and summary['frequencies_GHz']==list(range(1,9))
        assert base.sha(Path(read(folder/'data.json')['path']))==read(folder/'data.json')['sha256']
        assert base.sha(folder/'executed_driver.m')==launch['driver_sha256']
        raw=loadmat(folder/'final_contrast.mat',simplify_cells=True)
        assert np.atleast_1d(raw['counts']).tolist()==[256,512,1024,2048]
        assert all(np.isfinite(a).all() for a in raw['snapshots'])
        assert np.atleast_1d(raw['frequencies_GHz']).tolist()==list(range(1,9))
        assert int(raw['reference_frequency_GHz'])==8
        scores=read(folder/'scores.json')['snapshots']
        assert [s['iterations'] for s in scores]==[256,512,1024,2048]
        for snapshot in scores:
            for s in sorted(snapshot['scores'],key=lambda s:s['fraction']):
                rows.append(dict(case=scene,iterations=snapshot['iterations'],threshold_fraction=s['fraction'],
                    area_error_percent=100*s['area_error'],mean_relative_permittivity=s['mean_relative_permittivity'],
                    contrast_error_percent=100*s['relative_contrast_error'],components=s['components'],holes=s['holes'],
                    native_elapsed_seconds=snapshot['native_elapsed_seconds']))
        log=folder/'matlab.log.gz'
        with gzip.open(log,'rt') as f:
            numerical=[line for line in f if re.match(r'^\s+\d+\s+[-\d.]+e[+-]\d+',line)]
        last=[float(x) for x in numerical[-1].split()]
        assert int(last[0])==2048 and len(last)==10
        costs=dict(zip(['FS','FD','FC','reported_fsb','native_ChiErr_against_initial_guess','initial_line_step',
                        'chosen_line_step','line_objective_at_step','line_objective_difference'],last[1:]))
        case=dict(scene=scene,outcome=outcome,snapshots=scores,final_costs=costs,native_seconds=summary['time_seconds'],
                  wall_seconds=launch['wall_seconds'],native_seconds_per_iteration=summary['time_seconds']/2048,
                  wall_seconds_per_iteration=launch['wall_seconds']/2048,peak_family_GiB=launch['peak_family_rss_bytes']/2**30,
                  minimum_available_GiB=launch['minimum_available_bytes']/2**30,
                  data_sha256=read(folder/'data.json')['sha256'],driver_sha256=launch['driver_sha256'])
        pack['cases'].append(case)
        main=[next(s for s in v['scores'] if s['fraction']==.5) for v in scores]
        if any(b['area_error']>a['area_error']+1e-8 for a,b in zip(main,main[1:])):
            odd.append(f'{scene}: main-threshold area error is not monotone across saved iterations.')
        final=scores[-1]['scores'];spread=100*(max(s['area_error'] for s in final)-min(s['area_error'] for s in final))
        if spread>5:odd.append(f'{scene}: final area errors span {spread:.2f} percentage points across thresholds 0.3/0.5/0.7.')
        for s in final:
            if s['components']!=1 or s['holes']:
                odd.append(f"{scene}, threshold {s['fraction']}: {s['components']} components, {s['holes']} holes; all count in scoring.")
    pack['oddities']=odd
    lines=['# Review the full-band first batch','',f"Updated {pack['utc']}; old launcher exited naturally and push {args.published_commit} is confirmed.",
           'All three fits ran 2048 iterations at 1–8 GHz. No further fit is authorized; wait for the new go and frequency list.','',
           'Area error is symmetric-difference area over true area. Main threshold is 0.5 of the signed peak; 0.3/0.7 are sensitivity rows.',
           'Mean permittivity and contrast error are measured in each threshold support. Contrast error is relative to 4.',
           'All components and holes count. Earlier snapshots are evidence and never replace the final 2048 result.','']
    for scene in SCENES:
        lines.extend([f'## {scene}','',
            '| Iterations | Threshold | Area error % | Mean permittivity | Contrast error % | Native elapsed s |',
            '|---:|---:|---:|---:|---:|---:|'])
        for row in rows:
            if row['case']!=scene:continue
            lines.append(f"| {row['iterations']} | {row['threshold_fraction']:.1f} | {row['area_error_percent']:.4f} | {row['mean_relative_permittivity']:.6f} | {row['contrast_error_percent']:.4f} | {row['native_elapsed_seconds']:.3f} |")
        lines.append('')
    lines.extend(['## Final native costs and timing','',
        '| Case | FS | FD | FC | Reported fsb | Native s | Wall s | Native s/iteration | Wall s/iteration |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|'])
    for case in pack['cases']:
        c=case['final_costs']
        lines.append(f"| {case['scene']} | {c['FS']:.6g} | {c['FD']:.6g} | {c['FC']:.6g} | {c['reported_fsb']:.7g} | {case['native_seconds']:.3f} | {case['wall_seconds']:.3f} | {case['native_seconds_per_iteration']:.6f} | {case['wall_seconds_per_iteration']:.6f} |")
    lines.extend(['','Costs retain native log precision. FS/FD/FC are frequency averages before the contrast step;',
        'reported fsb is the logged line-search total after that step, so it is not their displayed sum.',
        'Native ChiErr is against the initial back-propagated image, not truth; it is not the contrast-error score above.',
        'Native timers include checkpoint I/O. Wall time also includes startup/configuration/export.',
        'The fits overlap one another, BRG/BEM work and the later low-priority forward prefetch; times are not isolated.','',
        '## Figure and checks','',f"Final batch figure: [figures/batch_1.png](figures/batch_1.png). Absolute path: `{pack['figure']}`.",
        'Return codes, all four finite raw arrays, exact frequency/reference metadata, data/driver hashes and final iteration were checked.',
        'The unchanged MATLAB wrapper verifies exact final-array equality against checkpoint 2048 before writing its summary.','',
        '## Anything odd',''])
    lines.extend(['- '+s for s in odd] or ['No additional numerical failure was found.'])
    lines.extend(['','The known circle-table errors at 1–8 GHz are 0.1723, 0.1260, 0.3034, 1.1396, 0.8228, 1.6782, 2.2946, 5.9136 percent.',
        'Its independent best-contrast shifts and common equivalent-circle fit are in [grid_check/results.md](grid_check/results.md).',
        'Those diagnostic fits do not change any table or CSI result. Other shapes still need their BEM-side forward check.','',
        '## Original first-batch forecast','','```json',json.dumps(pack['first_batch_forecast'],indent=2),'```','',
        'The old nine-hour forecast check is historical. All three fits finished before the launcher exited; no agent stopped it.',
        'Current policy treats time as a target. All future fits are held for user review and a new coordinator go.',''])
    (ACT/'review_pack.md').write_text('\n'.join(lines))
    base.write(ROOT/'batch_1_review.json',pack)
    with (ROOT/'batch_1_review.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(str(ACT/'review_pack.md'))


if __name__=='__main__':main()
