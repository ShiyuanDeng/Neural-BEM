"""Validate saved endpoints and render the paper-case evidence."""
import argparse
from collections import Counter
import json
import re
from pathlib import Path
import numpy as np
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'results/brg/paper_examples/2026-11-17'
FIG=ROOT/'docs/iterations/brg_adaptation/02_rebuild_paper_examples/figures'


def summarize(case, curvature, max_k=None):
    out=BASE/case/curvature
    summary=json.loads((out/'summary.json').read_text())
    rows=summary['frequencies']
    if isinstance(rows,dict): rows=[rows]
    assert len(rows)==summary['inverse_frequencies']
    if max_k is not None: rows=[r for r in rows if r['k']<=max_k]
    suffix='' if max_k is None else f'_k{max_k:g}'
    for i,row in enumerate(rows,1):
        assert row['index']==i and row['k']==1+(i-1)*.25
        curve=loadmat(out/f'frequency_{i:03d}.mat',simplify_cells=True)['record']
        assert len(curve['xs'])==row['nodes'] and np.isfinite(curve['xs']).all()
        assert np.isfinite(curve['ys']).all() and np.isfinite(curve['residual_history']).all()
    assert all(np.isfinite(r['relative_area_error']) and np.isfinite(r['wall_seconds']) for r in rows)
    attempts=[json.loads(p.read_text()) for p in out.glob('attempt_*.json')]
    data_path=out/'data_summary.json'
    if not data_path.exists(): data_path=BASE/case/'shipped/data_summary.json'
    data=json.loads(data_path.read_text())
    all_data_seconds=sum(r['wall_seconds'] for r in data)
    if max_k is not None: data=[r for r in data if r['k']<=max_k]
    generated=set()
    for log in out.glob('progress_*.log'):
        generated.update(int(i) for i in re.findall(r'BRG DATA \S+ (\d+)/\d+',log.read_text()))
    generated.intersection_update(r['index'] for r in data)
    status=summary['status'] if max_k is None else ('complete_at_target' if rows[-1]['k']==max_k else 'partial')
    stats=dict(case=case,curvature=curvature,status=status,frequencies=len(rows),
        requested_max_k=max_k,all_saved_data_generation_seconds=all_data_seconds,
        data_seconds=sum(r['wall_seconds'] for r in data if r['index'] in generated),
        dataset_generation_seconds=sum(r['wall_seconds'] for r in data),
        new_data_frequencies=len(generated),
        inverse_seconds=sum(r['wall_seconds'] for r in rows),
        attempts_wall_seconds=sum(r.get('wall_seconds',0) for r in attempts),
        started=min((r['started'] for r in attempts),default=None),
        ended=max((r.get('ended','') for r in attempts),default=None),
        process_time_is_upper_bound=any(r.get('wall_seconds_is_conservative_upper_bound',False) for r in attempts),
        iterations=sum(r['iterations'] for r in rows),
        exit_flags=dict(Counter(str(r['exit_flag']) for r in rows)),
        final={k:rows[-1][k] for k in ['k','residual','area_error','relative_area_error','nodes']},
        max_analytic_error=max(r['err_est'] for r in data),
        compute_threads=8,
        other_matlab_at_start=[r['other_matlab_at_start'] for r in attempts],
        other_matlab_at_end=[r.get('other_matlab_at_end',[]) for r in attempts])
    FIG.mkdir(parents=True,exist_ok=True)
    truth=loadmat(out/'truth_curve.mat',simplify_cells=True)['truth_curve']
    fig,ax=plt.subplots(figsize=(6,6))
    ax.plot(truth['xs'],truth['ys'],'k-',lw=1.5,label='True curve' if case.startswith('glider') else 'True curve (paper vector recovery)')
    snapshots=[(1,'--'),(17,':'),(37,'-.'),(57,'-'),(117,'--')] if case.startswith('glider') else [(1,'--'),(57,':'),(117,'-.')]
    for i,style in snapshots:
        if i<=len(rows):
            curve=loadmat(out/f'frequency_{i:03d}.mat',simplify_cells=True)['record']
            ax.plot(curve['xs'],curve['ys'],style,lw=1,label=f"k={curve['k']:g}")
    ax.set(aspect='equal',xlabel='x',ylabel='y',title=f'{case}, curvature={curvature}')
    ax.legend(fontsize=8);fig.tight_layout();fig.savefig(FIG/f'{case}_{curvature}{suffix}_curves.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    ks=[r['k'] for r in rows]
    axes[0].semilogy(ks,[r['relative_area_error'] for r in rows],label='Rebuilt case')
    axes[1].semilogy(ks,[r['residual'] for r in rows],label='Relative field residual')
    if case.startswith('glider'):
        key='eta_033' if case=='glider_033' else 'eta_10'
        paper=json.loads((BASE/'shapes/figure1_errors.json').read_text())[key]
        axes[0].semilogy(paper['k'],paper['relative_area_error'],'k.',ms=3,label='Paper Figure 1 vectors')
        if len(rows)>=37:
            mine=np.array([r['relative_area_error'] for r in rows[:37]])
            ref=np.array(paper['relative_area_error'])
            diff=np.log10(mine/ref)
            comparison=dict(rms_log10_difference=float(np.sqrt(np.mean(diff**2))),
                median_absolute_log10_difference=float(np.median(abs(diff))),
                endpoint_ratio=float(mine[-1]/ref[-1]),
                paper_endpoint=float(ref[-1]),run_endpoint=float(mine[-1]))
            comparison['clear_disagreement']=comparison['rms_log10_difference']>.30 or not(.5<=comparison['endpoint_ratio']<=2)
            stats['figure1_comparison']=comparison
            (out/'figure1_comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    for ax in axes:
        ax.set(xlabel='Exterior k');ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[0].set_ylabel('Relative symmetric-difference area');axes[1].set_ylabel('Relative scattered-field residual')
    fig.suptitle(f'{case}, curvature={curvature}');fig.tight_layout()
    fig.savefig(FIG/f'{case}_{curvature}{suffix}_errors.png',dpi=150);plt.close(fig)
    (out/f'metrics{suffix}.json').write_text(json.dumps(stats,indent=2)+'\n')
    if case=='glider_033' and len(rows)>=37 and max_k is None:
        fig,ax=plt.subplots(figsize=(6,4))
        paper=json.loads((BASE/'shapes/figure1_errors.json').read_text())['eta_033']
        ax.semilogy(paper['k'],paper['relative_area_error'],'k.',label='Paper Figure 1 vectors')
        for variant in ['shipped','default']:
            candidate=BASE/case/variant/'summary.json'
            if candidate.exists():
                rs=json.loads(candidate.read_text())['frequencies'][:37]
                ax.semilogy([r['k'] for r in rs],[r['relative_area_error'] for r in rs],label=variant)
        ax.set(xlabel='Exterior k',ylabel='Relative symmetric-difference area',title='Glider eta=0.33: authorized curvature check')
        ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(FIG/'glider_033_figure1_comparison.png',dpi=150);plt.close(fig)
    print(json.dumps(stats,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--curvature',required=True)
    parser.add_argument('--max-k',type=float)
    args=parser.parse_args();summarize(args.case,args.curvature,args.max_k)
