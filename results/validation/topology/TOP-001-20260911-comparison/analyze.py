"""Recompute paired statistics and audit frozen controls from saved measurements."""
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
import run_topology_allocation_experiment as experiment


def load_rows(folder):
    return [json.loads(p.read_text()) for p in sorted((folder / 'comparison').glob('*/*/*/metrics.json'))]


def main():
    primary = load_rows(OUT)
    supplement = OUT.parent / 'TOP-001E-20260911'
    extra = load_rows(supplement)
    rows = primary + extra
    controls = {(m['chart'],m['magnitude'],m['seed']):m for m in primary if m['arm']=='A'}
    statistics, comparisons = [], []
    checks = dict(monotone=True, acceptance=True, source_hashes=True, paired_initial_states=True,
                  paired_observations=True, no_unclassified_rejections=True)
    expected_hashes = json.loads((OUT / 'manifest.json').read_text())['source_provenance']['source_sha256']
    grouped_initial, grouped_observations = {}, {}
    rejection_counts = Counter()
    for row in rows:
        folder = supplement if row['arm']=='E' else OUT
        path = folder / row['path']
        manifest = json.loads((path / 'manifest.json').read_text())
        checks['source_hashes'] &= manifest['source_provenance']['source_sha256']==expected_hashes
        key = (row['chart'],row['magnitude'],row['seed'])
        state = manifest['initial_state']
        checks['paired_initial_states'] &= grouped_initial.setdefault(key,state)==state
        observed = (path/'observations.json').read_text()
        checks['paired_observations'] &= grouped_observations.setdefault(row['chart'],observed)==observed
        trajectory = json.loads((path/'trajectory.json').read_text())
        loss = np.array([f['loss'] for f in trajectory])
        checks['monotone'] &= bool(np.all(np.diff(loss) <= 1e-12))
        config = manifest['controller']
        for event in row['events']:
            a = event['production_before']-event['production_after']
            b = event['refined_before']-event['refined_after']
            margin = config['acceptance_absolute_margin']+config['acceptance_relative_margin']*event['production_before']
            checks['acceptance'] &= min(a,b)>margin+config['cross_resolution_factor']*abs(a-b)
        rejection_counts.update(row['rejection_counts'])
        checks['no_unclassified_rejections'] &= row['rejection_counts'].get('unclassified',0)==0
        a = controls.get(key)
        if a and row['arm']!='A':
            cost = row['work']['totals']['bie_frequency_solve_count']
            a_cost = a['work']['totals']['bie_frequency_solve_count']
            ref = row['work']['stages']['candidate_refinement']['forward_frequency_solve_count']
            a_ref = a['work']['stages']['candidate_refinement']['forward_frequency_solve_count']
            comparisons.append(dict(chart=row['chart'], arm=row['arm'], magnitude=row['magnitude'],seed=row['seed'],
                total_cost=cost, baseline_total_cost=a_cost, cost_ratio=cost/a_cost,
                refinement_cost=ref, baseline_refinement_cost=a_ref,
                matched_cost=cost<=a_cost and ref<=a_ref,
                geometry_ratio=row['hausdorff_m']/a['hausdorff_m'],
                holdout_ratio=row['holdout_relative_error']/a['holdout_relative_error'],
                event_changed=row['first_event']!=a['first_event']))
    for chart in ('radial','cartesian'):
        for arm in ('A','B','C','E'):
            selected=[r for r in rows if (r['chart'],r['arm'])==(chart,arm)]
            if not selected:
                continue
            zero=next((r for r in selected if r['magnitude']==0),None)
            statistics.append(dict(chart=chart,arm=arm,count=len(selected),
                recovered_count=sum(r['stop_reason']=='recovered' for r in selected),
                hausdorff_min_m=min(r['hausdorff_m'] for r in selected),
                hausdorff_max_m=max(r['hausdorff_m'] for r in selected),
                hausdorff_median_m=float(np.median([r['hausdorff_m'] for r in selected])),
                holdout_max=max(r['holdout_relative_error'] for r in selected),
                total_bie_solves=sum(r['work']['totals']['bie_frequency_solve_count'] for r in selected),
                same_event_as_zero_count=None if zero is None else sum(r['first_event']==zero['first_event'] for r in selected if r['magnitude']!=0),
                perturbation_count=sum(r['magnitude']!=0 for r in selected)))
    result=dict(primary_count=len(primary), exploratory_count=len(extra), complete=len(primary)==60 and len(extra)==20,
                checks=checks, rejection_counts=dict(rejection_counts), statistics=statistics, comparisons=comparisons)
    experiment.write_json(OUT/'analysis.json',result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'A':'#425A70','B':'#D17B37','C':'#7B58A4','E':'#007F78'}
    labels={'A':'A · one × 3','B':'B · two × 3','C':'C · two × 1','E':'E · three × 1 (exploratory)'}
    fig,axes=plt.subplots(2,2,figsize=(11,7.6),layout='constrained')
    for i,chart in enumerate(('radial','cartesian')):
        for arm in colors:
            selected=[r for r in rows if (r['chart'],r['arm'])==(chart,arm)]
            for j,(key,scale,ylabel) in enumerate((('hausdorff_m',1e6,'Sampled Hausdorff (µm)'),('holdout_relative_error',1,'Holdout relative L2'))):
                axes[i,j].scatter([r['work']['totals']['bie_frequency_solve_count'] for r in selected],
                    [scale*r[key] for r in selected],s=40,c=colors[arm],alpha=.8,label=labels[arm],
                    marker='D' if arm=='E' else 'o',edgecolors='white',linewidths=.4)
                axes[i,j].set(yscale='log',xlabel='BIE frequency solves per inverse replay',ylabel=ylabel,
                              title=chart.capitalize())
                axes[i,j].grid(alpha=.18)
    axes[0,0].legend(fontsize=8,frameon=False)
    fig.suptitle('Candidate refinement: reconstruction quality versus actual BIE work',fontsize=14)
    fig.savefig(OUT/'comparison.svg')
    fig.savefig(OUT/'comparison.png',dpi=160)
    print(json.dumps({k:result[k] for k in ('primary_count','exploratory_count','complete','checks','statistics')},indent=2))

if __name__=='__main__':
    main()
