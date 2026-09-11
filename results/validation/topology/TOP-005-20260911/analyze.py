"""Saved-artifact audits and plots for TOP-005; no physics is rerun."""
from collections import Counter
import json
from pathlib import Path
import sys
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT))
import run_topology_allocation_experiment as replay


def main():
    result=json.loads((OUT/'qualification.json').read_text())
    expected=json.loads((OUT/'manifest.json').read_text())['source_provenance']['source_sha256']
    checks=dict(source_hashes=True,paired_inputs=all(r['paired_inputs']for r in result['split_pairs']),
                monotone=True,event_margins=True,no_unclassified_rejections=True,all_split_quality=True)
    counts=Counter()
    rows=[json.loads(p.read_text())for p in (OUT/'comparison').glob('*/*/*/metrics.json')]
    for row in rows:
        path=OUT/row['path']
        manifest=json.loads((path/'manifest.json').read_text())
        checks['source_hashes'] &= manifest['source_provenance']['source_sha256']==expected
        counts.update(row['rejection_counts'])
        checks['no_unclassified_rejections'] &= not row['rejection_counts'].get('unclassified')
        pair=next(p for p in result['split_pairs']if (p['chart'],p['magnitude'],p['seed'])==(row['chart'],row['magnitude'],row['seed']))
        checks['all_split_quality'] &= row['stop_reason']=='recovered' and row['hausdorff_m']<=max(1.1*pair['baseline_hausdorff_m'],1e-6) and row['holdout_relative_error']<=max(1.1*pair['baseline_holdout'],1e-5)
    for path in list((OUT/'comparison').glob('*/*/*'))+list((OUT/'controller/F').glob('*')):
        if not (path/'metrics.json').exists():continue
        metric=json.loads((path/'metrics.json').read_text())
        config=json.loads((path/'manifest.json').read_text())['controller']
        loss=np.array([f['loss']for f in json.loads((path/'trajectory.json').read_text())])
        checks['monotone'] &= bool(np.all(np.diff(loss)<=1e-12))
        for event in metric['events']:
            a=event['production_before']-event['production_after'];b=event['refined_before']-event['refined_after']
            margin=config['acceptance_absolute_margin']+config['acceptance_relative_margin']*event['production_before']
            checks['event_margins'] &= min(a,b)>margin+config['cross_resolution_factor']*abs(a-b)
    stats=[]
    for chart in ('radial','cartesian'):
        selected=[r for r in rows if r['chart']==chart]
        zero=next(r for r in selected if r['magnitude']==0)
        stats.append(dict(chart=chart,count=len(selected),worst_hausdorff_m=max(r['hausdorff_m']for r in selected),
            worst_holdout=max(r['holdout_relative_error']for r in selected),
            exact_baseline_trajectory_count=sum(p['exact_baseline_trajectory']for p in result['split_pairs']if p['chart']==chart),
            same_construction_as_zero=sum(r['first_event']==zero['first_event']for r in selected if r['magnitude']!=0),
            zero=zero))
    audit=dict(checks=checks,statistics=stats,rejection_counts=dict(counts))
    replay.write_json(OUT/'verification.json',audit)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.5),layout='constrained')
    pairs=[r for r in result['split_pairs']if r['chart']=='cartesian']
    for label,prefix,color,marker in [('Baseline A','baseline','#52677A','o'),('Selective F','selective','#087F78','D')]:
        axes[0].scatter([p[f'{prefix}_cost']for p in pairs],[p[f'{prefix}_hausdorff_m']*1e6 for p in pairs],
            c=color,s=55,marker=marker,label=label,alpha=.8,edgecolors='white',linewidths=.5)
    axes[0].set(yscale='log',xlabel='BIE frequency solves per split replay',ylabel='Sampled Hausdorff (µm)',title='Ten paired Cartesian split replays')
    axes[0].legend(frameon=False);axes[0].grid(alpha=.2)
    cases=result['controller_cases'];x=np.arange(len(cases))
    for shift,key,label,color in [(-.19,'baseline','Baseline A','#52677A'),(.19,'selective','Selective F','#087F78')]:
        axes[1].bar(x+shift,[c[key]['work']['totals']['bie_frequency_solve_count']for c in cases],width=.38,label=label,color=color)
    axes[1].set(xticks=x,xticklabels=[c['case'].replace('-','\n')for c in cases],ylabel='BIE frequency solves',title='Five full controller cases')
    axes[1].legend(frameon=False);axes[1].grid(axis='y',alpha=.2)
    fig.suptitle('Selective refinement: retain the raw winner and test a simpler family',fontsize=13)
    fig.savefig(OUT/'comparison.svg');fig.savefig(OUT/'comparison.png',dpi=160)
    print(json.dumps(dict(checks=checks,statistics=[{k:v for k,v in s.items()if k!='zero'}for s in stats]),indent=2))

if __name__=='__main__':main()
