"""Render and summarize the explicit full-matrix initializer extension."""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    summary=json.loads((args.output/'summary.json').read_text())
    rows=summary['rows']
    root=Path(__file__).resolve().parents[2]
    import run_topology_scene_benchmark as benchmark
    spec=benchmark.read(root/'config/topology_scenes_v1.json')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    cmap=plt.get_cmap('magma').copy()
    cmap.set_bad('#d9d9d9')
    for method in ('lsm','topo_full'):
        fig,axes=plt.subplots(3,4,figsize=(13,10),constrained_layout=True)
        for ax,scene,row in zip(axes.flat,spec['scenes'],rows):
            with np.load(args.output/(scene['id']+'.npz')) as data:
                values=(data['indicator'].reshape(81,81) if method=='lsm' else np.maximum(-data['td'],0))
            image=ax.imshow(values/np.nanmax(values),origin='lower',extent=(.3,.7,.3,.7),cmap=cmap,vmin=0,vmax=1)
            for curve in benchmark.truth_curves(scene):
                p=curve.discretize(512).points
                ax.plot(p[:,0],p[:,1],color='cyan',lw=1)
            angle=np.linspace(0,2*np.pi,160)
            for seed in row['initializers'][method]['seeds']:
                ax.plot(seed['center'][0]+seed['radius']*np.cos(angle),seed['center'][1]+seed['radius']*np.sin(angle),'w-',lw=1)
            ax.set_title(scene['id'],fontsize=9);ax.set_aspect('equal')
        fig.colorbar(image,ax=axes.ravel().tolist(),shrink=.6,label='Indicator / maximum in each scene')
        handles=[Line2D([],[],color='cyan',label='Evaluation truth'),Line2D([],[],color='black',marker='o',markerfacecolor='white',linestyle='none',label='Seed circles (white on maps)')]
        if method=='lsm':handles.append(Patch(facecolor='#d9d9d9',label='1% probe discrepancy unattainable'))
        fig.legend(handles=handles,loc='outside lower center',ncol=len(handles))
        fig.suptitle(f'{method}: additional 24×24 data at 0.5 GHz; axes in metres')
        fig.savefig(args.output/(method+'_reviewed.png'),dpi=150);plt.close(fig)
    reports={}
    for method in ('lsm','topo_full'):
        outcomes=[]
        for row in rows:
            folder=args.output/method/'runs/H'/row['scene']
            path=folder/'metrics.json'
            if path.exists():
                value=json.loads(path.read_text())
                outcomes.append(dict(scene=row['scene'],status='COMPLETED',passed=value['passed'],
                    stop_reason=value['stop_reason'],geometry=value['geometry'],gates=value['gates'],
                    inversion_work=value['work'],audit_work=value['audit_work'],seconds=value['inversion_seconds']))
            else:
                failure=folder/'failure.json'
                value=json.loads(failure.read_text()) if failure.exists() else {}
                checkpoint=folder/'checkpoint.json'
                partial=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
                outcomes.append(dict(scene=row['scene'],status=value.get('reason','IN_PROGRESS'),passed=False,
                    partial_checkpoint=partial,failure=value,work_is_lower_bound=True))
        reports[method]=dict(passes=sum(r['passed'] for r in outcomes),rows=outcomes,
            completed=sum(r['status']=='COMPLETED' for r in outcomes),
            finished=all(r['status']!='IN_PROGRESS' for r in outcomes))
    (args.output/'controller_summary.json').write_text(json.dumps(reports,indent=2)+'\n')
    finished=all(r['finished'] for r in reports.values())
    lines=['# Full-matrix LSM and topological initializers','',
        'This follow-up completes an eligible LSM input contract for all twelve frozen scenes. '
        'It adds552 complex0.5GHz observations per scene on the original24 transmitters and24 receivers. '
        'These off-diagonal measurements are explicitly synthesized and qualified, never inferred from the original paired values. '
        'Both LSM and TD initializers receive these same additional samples; controller fitting still uses only the original24 pairs. '
        'The original1.5/2.5GHz holdouts and geometry remain evaluation-only.','',
        f"All twelve full matrices agree at256/512 nodes within {max(r['refinement_relative'] for r in rows):.3g} relative error. "
        f"Their diagonals agree with the archived paired observations within {max(r['original_pair_relative'] for r in rows):.3g}. "
        'The source-generation cost is24 factorizations and48 primal/reciprocal RHS batches.','',
        '## Initial images','',
        'Both initializers identify the target component count in6/12 scenes with the fixed60% threshold. '
        'For comparison, paired-data TD identified10/12; more measurements do not guarantee that this particular threshold heuristic improves. '
        'LSM discrepancy sensitivity at0.5%,1%,2% is retained per scene; geometry did not select these settings.','',
        '![LSM with unattainable probes labeled](lsm_reviewed.png)','',
        '![Topological derivative with the same full matrix](topo_full_reviewed.png)','',
        '## Matched controller comparison','',
        ('All24 additional controller jobs have returned or reached the declared cap.' if finished else '**Controller campaign is in progress; counts below are provisional.**'),'',
        'All use existing policy H, the original ten-cycle numerical budgets, and600seconds per job. '
        'There is no additional aggregate queue timeout. The original-start arm is reused from the earlier identical-data/configuration run, where5/12passed and one job timed out; it consumes no additional observations. '
        'This compares starting geometries under paired fitting, not a full-matrix inverse.','',
        '| Start | Passes /12 | Completed jobs /12 |','|---|---:|---:|',
        '| Original frozen start (prior run) |5|11|']
    for method in ('lsm','topo_full'):
        r=reports[method];lines.append(f"| {method}, extra initialization data | {r['passes']} | {r['completed']} |")
    lines += ['','All failures, checkpoints and separate inversion/audit work counters are in [controller_summary.json](controller_summary.json). '
        'Timeout work remains a lower bound. Shared CPU load prevents a controlled wall-time speed claim.','',
        '## Numerical qualification and derivation','',
        'For source-by-receiver dataY and common physical source strengtha, the discretized near-field operator is '
        '`N = Y.T / a * (2πR / 24)`. Probe columns are `G_k(receiver,z)`. '
        'We use SVD/Tikhonov regularization and choose its parameter for a1% probe residual. '
        '[Garnier, Haddar and Montanelli, §2 and §5](https://arxiv.org/html/2210.15560v2) describe this active near-field construction alongside their random-source extension. '
        'Their sound-soft theory is not asserted as a dielectric recovery guarantee here.','',
        'The numerical SVD drops singular values below1e-12σ₁, well above the measured matrix refinement error. '
        'Writing `N=UΣV*`, source coordinates in the retained V basis preserve their norm; '
        'the reused discrepancy solver therefore acts on the rectangular `U_rΣ_r`. '
        'It explicitly includes the unresolved receiver-space residual. Unattainable probes are masked, not converted into bright objects. '
        f"Resolved ranks are {min(r['resolved_rank'] for r in rows)}–{max(r['resolved_rank'] for r in rows)}. "
        f"Coarse/fine LSM images differ by at most {max(r['indicator_refinement_relative'] for r in rows):.3g} on their common eligible probes, with zero eligibility-mask changes.", '',
        'The empty-domain TD is derived from the small-disk response '
        '`δY_sr/δarea = (ki²−ke²) a G(source_s,z)G(receiver_r,z)`, contracted with the normalized negative measured residual. '
        'A focused test compares the full-matrix contraction with the existing paired implementation expanded to every source/receiver combination. '
        '[Carpio, Pena and Rapún](https://arxiv.org/html/2501.15327v1) provide the dielectric topological-sensitivity setting.','',
        'Earlier diagnostics remain in sibling directories. The first used slightly different rounded vacuum constants and differed from archived pairs by about5e-10. '
        'The next used exactly matching constants but retained unresolved singular directions. '
        'This final version uses the exact constants and an explicit numerical SVD floor; the image eligibility now agrees under refinement.','',
        '## Reproduce','',
        'The main benchmark now accepts `--init {current,topo,lsm}` and `--initializer-data`. '
        'Without a full-matrix input, `--init lsm` rejects before creating an output bundle. '
        '`--init topo` alone uses the original paired data; adding the matrix directory uses the full-data TD. '
        'Prepared initial states, raw matrix hashes, physical constants and initializers are stored in each bundle.','',
        '```bash','export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:.',
        'PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python',
        '$PY -m experiments.initialization_followup.run --output NEW_DATA',
        '$PY run_topology_scene_benchmark.py --output NEW_DATA/lsm --reference-data results/validation/topology/TOP-006-20260911-scenes-v1 --arms H --init lsm --initializer-data NEW_DATA --prepare-only',
        '$PY run_topology_scene_benchmark.py --output NEW_DATA/topo_full --reference-data results/validation/topology/TOP-006-20260911-scenes-v1 --arms H --init topo --initializer-data NEW_DATA --prepare-only',
        '$PY -m experiments.initialization_followup.campaign --output NEW_DATA --workers 4',
        '$PY -m experiments.initialization_followup.report NEW_DATA',
        '$PY -m pytest -q experiments/initialization_followup/test_full_matrix.py pytest/sdf_inverse/test_topology_scene_benchmark.py','```','']
    text='\n'.join(lines)
    replacements={'adds552':'adds 552','complex0.5GHz':'complex 0.5 GHz','original24':'original 24','and24':'and 24','original1.5/2.5GHz':'original 1.5/2.5 GHz',
        'at256/512':'at 256/512','is24':'is 24','and48':'and 48','in6/12':'in 6/12','fixed60%':'fixed 60%','identified10/12':'identified 10/12',
        'at0.5%,1%,2%':'at 0.5%, 1%, 2%','All24':'All 24','and600seconds':'and 600 seconds','where5/12passed':'where 5/12 passed',
        'dataY':'data Y','strengtha':'strength a','a1%':'a 1%','below1e-12':'below 1e-12','about5e-10':'about 5e-10'}
    for before,after in replacements.items():text=text.replace(before,after)
    (args.output/'README.md').write_text(text)


if __name__=='__main__':main()
