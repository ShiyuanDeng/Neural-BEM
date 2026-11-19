"""Read-only stage frontier measurements; no fits or schedule changes.

The solver frontier uses only the highest active frequency. The stacked
frontier uses B5 equal-frequency weights and observed-data normalization.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['SC_FORWARD_BACKEND'] = 'cpu'
os.environ.setdefault('MPLCONFIGDIR', '/tmp/stage_frontiers_mpl')
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'solvers'), str(ROOT), str(ROOT/'experiments/bem_on_baseline_data')]
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from bem_inverse import Execution, FourierCurve
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings, forward_solve
from bem_inverse.io import read, curve_from, digest
from bem_inverse.policy import CumulativePolicy
from bem_inverse import checks
from experiments.benchmark import campaign
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE
from experiments.comparison.runs import RESULTS
import csi_data as D
import csi_measured_schedule as measured

OUT = RESULTS/'bem/stage_scheduling/2026-11-19/stage_frontiers'
DOC = ROOT/'docs/iterations/investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes'
THRESHOLD = CumulativePolicy().frontier_threshold
TOP = CumulativePolicy().frontier_top


def frontier(profile):
    checks.require_observable_frontier(profile)
    return int(np.flatnonzero(profile >= THRESHOLD*profile.max()).max())


def specs():
    info = read(ROOT/'results/bem/baseline_data/csi_adapter/2026-11-18/cylinder_info/cylinder_info.json')
    best = info['least_squares']['from_bem_fit']['end']
    real, _, source = D.observations(D.MEASURED)
    saved = read(measured.CONTROL)
    stages = [(f'1–{n} GHz' if n>1 else '1 GHz', list(range(n)), str(3*n)) for n in range(1, 5)]
    stages.append(('1–8 GHz', list(range(8)), '11,15,19,25,31,37'))
    for position, curve, material in [
            ('start', FourierCurve.circle(.065/D.LENGTH_M), saved['settings']['start_contrast']),
            ('best_circle', FourierCurve.circle(best['radius_mm']*.001/D.LENGTH_M,
                complex(best['x_mm'],best['y_mm'])*.001/D.LENGTH_M), best['permittivity'])]:
        yield dict(case='measured_cylinder', position=position, curve=curve, contrast=material,
                   real=real, stages=stages, table=True, input_sha256=source['sha256'])
    for case in ('circle__c4','star__c4','kite__c4','c_shape__c4','aphex_twin__c4'):
        row = campaign.row(case); real, _ = bem.observations(BASE,row,RESULTS)
        original = read(BASE.folder()/case/'fit.json')
        freqs = [o.frequency_hz for o in real]
        stages = [('0.25 GHz warm-up',[freqs.index(.25e9)],'1')]
        for n in range(1,5):
            selected = [.5e9+i*.25e9 for i in range(n)]
            stages.append((','.join(f'{f/1e9:g}' for f in selected)+' GHz',
                           [freqs.index(f) for f in selected],str([3,5,7,9][n-1])))
        stages.append(('all 19 frequencies',list(range(len(real))),'11,15,19,25,31,37'))
        for position, curve, material in [
                ('start',curve_from(read(ROOT/row['initial'])),original['contrast_start']['start_contrast']),
                ('truth',curve_from(read(ROOT/row['truth'])),4.)]:
            yield dict(case=case,position=position,curve=curve,contrast=material,real=real,
                       stages=stages,table=False,input_sha256=digest(ROOT/row['data']))


def measure(spec, workers):
    physics = ModalMuller(Execution('cpu', workers),ModalSettings(table_mode=spec['table']))
    # Match runner's frontier diagnostic: refined solve, not production solve.
    resolution = physics.resolution_profile(spec['curve'].band)['refined']
    def at_frequency(obs):
        state = forward_solve(spec['curve'],obs,spec['contrast'],resolution,context=physics)
        result = physics.observable_frontier(state,TOP,THRESHOLD)
        return dict(frequency_hz=obs.frequency_hz,frontier=result['frontier'],
                    data_norm=float(np.linalg.norm(obs.scattered)),
                    paired_column_norm=np.asarray(result['column_profile']).tolist())
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            frequencies = list(pool.map(at_frequency,spec['real']))
    finally:
        if hasattr(physics,'close'):physics.close()
    stages = []
    for label, indices, band in spec['stages']:
        profiles = np.array([frequencies[i]['paired_column_norm'] for i in indices])
        norms = np.array([frequencies[i]['data_norm'] for i in indices])
        raw = np.sqrt(np.sum(profiles**2,axis=0))
        stacked = np.sqrt(np.mean((profiles/norms[:,None])**2,axis=0))
        high = frequencies[max(indices,key=lambda i:frequencies[i]['frequency_hz'])]
        stages.append(dict(stage=label,default_band=band,indices=indices,
                           frequencies_hz=[frequencies[i]['frequency_hz'] for i in indices],
                           highest_frequency_frontier=high['frontier'],
                           highest_frequency_column_norm=high['paired_column_norm'],
                           stacked_frontier=frontier(stacked),stacked_column_norm=stacked.tolist(),
                           stacked_raw_frontier=frontier(raw),stacked_raw_column_norm=raw.tolist()))
    return dict(case=spec['case'],position=spec['position'],contrast=spec['contrast'],
                curve_band=spec['curve'].band,refined_resolution=resolution,
                input_sha256=spec['input_sha256'],threshold=THRESHOLD,top=TOP,
                frequencies=frequencies,stages=stages)


def table(records):
    lines=['| Case | Frequency set | Default band | Start: highest / stacked | Target: highest / stacked |',
           '|---|---|---|---:|---:|']
    cases=list(dict.fromkeys(r['case'] for r in records))
    for case in cases:
        start=next(r for r in records if r['case']==case and r['position']=='start')
        target=next(r for r in records if r['case']==case and r['position']!='start')
        for a,b in zip(start['stages'],target['stages']):
            lines.append(f"| {case} | {a['stage']} | {a['default_band']} | {a['highest_frequency_frontier']} / {a['stacked_frontier']} | {b['highest_frequency_frontier']} / {b['stacked_frontier']} |")
    return '\n'.join(lines)+'\n'


def figure(records):
    cases=list(dict.fromkeys(r['case'] for r in records))
    fig, axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    colors=plt.cm.viridis(np.linspace(.08,.95,6))
    for ax,case in zip(axes.ravel(),cases):
        target=next(r for r in records if r['case']==case and r['position']!='start')
        for stage,color in zip(target['stages'],colors):
            p=np.array(stage['stacked_column_norm']);p=p/p.max()
            ax.semilogy(np.arange(13),p[:13],'.-',color=color,label=stage['stage'],ms=3,lw=1)
        ax.axhline(THRESHOLD,color='grey',ls='--',lw=1)
        ax.set(title=case,xlabel='Normal harmonic p',ylabel='Normalized paired column norm',ylim=(1e-6,2),xticks=range(0,13,2))
        ax.legend(fontsize=6,loc='lower left')
    fig.suptitle('Shape sensitivity at the target: normalized stacked stage Jacobian norms\nDashed line: 1% of the largest harmonic; full frontiers measured through p=95',fontsize=12)
    (DOC/'figures').mkdir(exist_ok=True)
    fig.savefig(DOC/'figures/stage_frontiers.png',dpi=140);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    parser.add_argument('--reuse',action='store_true',help='Reuse completed per-outline measurements')
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for spec in specs():
        path=OUT/f"{spec['case']}__{spec['position']}.json"
        record=read(path) if args.reuse and path.exists() else measure(spec,args.workers)
        if (record['input_sha256'] != spec['input_sha256'] or record['contrast'] != spec['contrast']
                or record['threshold'] != THRESHOLD or record['top'] != TOP):
            raise ValueError(f'Cached measurement settings changed: {path}')
        path.write_text(json.dumps(record,indent=2)+'\n');records.append(record)
        print(spec['case'],spec['position'],[(s['highest_frequency_frontier'],s['stacked_frontier']) for s in record['stages']],flush=True)
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),threshold=THRESHOLD,top=TOP,
                 highest_rule='Solver observable_frontier on highest active frequency, using refined resolution.',
                 stacked_rule='Root mean squared paired column norms after division by each frequency data norm (B5 equal weights).',
                 positions='Starts use saved weak material estimates; target uses best measured circle or TG-002 truth with contrast 4.',
                 records=records)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (OUT/'harmonics_0_to_12.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['case','position','stage','p','highest_frequency_raw_norm',
            'highest_frequency_relative_norm','stacked_B5_norm','stacked_B5_relative_norm','stacked_raw_norm'])
        writer.writeheader()
        for record in records:
            for stage in record['stages']:
                high=np.array(stage['highest_frequency_column_norm'])
                stacked=np.array(stage['stacked_column_norm'])
                for p in range(13):
                    writer.writerow(dict(case=record['case'],position=record['position'],stage=stage['stage'],p=p,
                        highest_frequency_raw_norm=high[p],highest_frequency_relative_norm=high[p]/high.max(),
                        stacked_B5_norm=stacked[p],stacked_B5_relative_norm=stacked[p]/stacked.max(),
                        stacked_raw_norm=stage['stacked_raw_column_norm'][p]))
    (OUT/'table.md').write_text(table(records));figure(records)
    print(table(records))

if __name__=='__main__':main()
