"""One authorized BEM glider fit on qualified, saved BRG observations."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import argparse
from dataclasses import dataclass,replace
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'solvers'),str(ROOT)]
from bem_inverse import Execution,FourierCurve,Problem
from bem_inverse.forward_solvers.modal_muller import ModalMuller,ModalSettings,forward_solve
from bem_inverse.policy import CumulativePolicy,Operation
from bem_inverse.runner import fit
from bem_inverse.io import write,curve_from
from experiments.baselines.brg.brg_data import observation,true_curve,REFERENCE_LENGTH_M

BASE=ROOT/'results/brg/bem_adaptation/2026-11-17'


@dataclass(frozen=True)
class BrgPolicy(CumulativePolicy):
    """Explicit observed-k ladder; existing LM/slider controls, no TG-002 change."""
    name:str='brg_observed_k_prefix'
    fit_seconds:float=3600.

    def operations(self,problem,physics):
        if not problem.real_only or not problem.allow_variable_acquisition:
            raise ValueError('BRG policy requires explicit variable-acquisition real-only data.')
        operations=[]
        for count in range(1,len(problem.real)+1):
            observations=problem.real[:count]
            band=max(1,int(np.floor(3*observations[-1].wavenumber)))
            quota=self.prefix_quotas[count-1] if count<=4 else 1500
            op=self._fit(problem,physics,f'k_{observations[-1].wavenumber:g}',observations,
                         band,2*band+2,quota,iterations=22,
                         purpose='Saved BRG frequency prefix; equal frequency weights; compact storage')
            operations.append(replace(op,stage=replace(op.stage,ragged_data=True)))
        operations.append(Operation('frontier','observable_frontier',
            'Record the normal-mode frontier at the qualified highest frequency; no extra fit stages',
            'all ladder stages returned normally','save the diagnostic and return',
            details=dict(top=self.frontier_top,threshold=self.frontier_threshold)))
        return tuple(operations)

    def tail(self,problem,physics,frontier):
        return ()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['glider_033'],default='glider_033')
    parser.add_argument('--plan-only',action='store_true');args=parser.parse_args()
    qualified=json.loads((BASE/args.case/'forward/qualification.json').read_text())
    regression=json.loads((BASE/'regression/comparison.json').read_text())
    assert regression['passes'],'Pinned CPU regression must pass first.'
    assert qualified['passing_prefix'],'No qualified data.'
    observations=[];sources=[]
    for k in qualified['passing_prefix']:
        obs,path,_=observation(args.case,k);observations.append(obs)
        sources.append(dict(k=k,path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    problem=Problem(FourierCurve.circle(),tuple(observations),None,.33,length_unit_m=REFERENCE_LENGTH_M,
                    origin_m=0j,bounds_m=((-2.,-2.),(2.,2.)),allow_variable_acquisition=True)
    context=ModalMuller(Execution(device='cpu',frequency_threads=1),ModalSettings(table_mode=True))
    policy=BrgPolicy()
    out=BASE/args.case/'inverse'
    if args.plan_only:
        out.mkdir(parents=True,exist_ok=True);write(out/'declared_plan.json',policy.plan(problem,context));return
    assert not (out/'manifest.json').exists(),'No tuning reruns or overwritten fits.'
    processes=subprocess.run(['ps','-C','MATLAB','-o','pid=,etime=,args='],capture_output=True,text=True).stdout.splitlines()
    assert len(processes)<3,'Three-heavy-worker limit: wait for a slot.'
    started=time.monotonic();out.mkdir(parents=True,exist_ok=True)
    write(out/'manifest.json',dict(case=args.case,started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
          eta=.33,material='known',reference_length_m=REFERENCE_LENGTH_M,sources=sources,
          other_matlab_at_start=processes,policy=policy.plan(problem,context),
          command=f'{sys.executable} experiments/baselines/brg/run_bem_adaptation.py --case {args.case}'))
    # Accepted curves are saved by runner after every accepted step; full stage receipts at each return.
    result=fit(problem,physics=context,forward_solve=lambda *a:forward_solve(*a,context=context),
               policy=policy,output=out/'local',geometry_update='slider',material=None)
    write(out/'fit.json',result)
    curve=curve_from(result['final_curve']);truth=true_curve('glider')
    from experiments.comparison.scoring import region,region_scores
    found,_=region([curve.values(16384)]);actual,_=region([truth.values(16384)])
    score=region_scores(found,actual)
    # Only dimensionless area ratios are reported for these reference-coordinate paper shapes.
    metrics={k:score[k] for k in ('area_error','missing_area','excess_area','components','holes')}
    accepted=json.loads((out/'local/accepted.json').read_text())['states']
    metrics.update(outcome=result['outcome'],detail=result['detail'],eta=.33,known_contrast=True,
                   cap=qualified['cap'],fit_seconds=result['fit_and_localization_seconds'],
                   maximum_active_residual=accepted[-1]['maximum_stage_residual'] if accepted else None,
                   final_active_frequency_count=accepted[-1]['active_frequency_count'] if accepted else 0,
                   total_seconds=time.monotonic()-started,
                   other_matlab_at_end=subprocess.run(['ps','-C','MATLAB','-o','pid=,etime=,args='],
                                                     capture_output=True,text=True).stdout.splitlines())
    write(out/'metrics.json',metrics)
    np.savez_compressed(out/'curves.npz',coefficients=curve.coefficients,true_coefficients=truth.coefficients)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(5,5));z=truth.values(4096);w=curve.values(4096)
    ax.plot(z.real,z.imag,'k-',label='True glider');ax.plot(w.real,w.imag,'r--',label='BEM, known eta 0.33')
    ax.axis('equal');ax.legend();ax.set_title(f'Area error {100*metrics["area_error"]:.4g}%; k cap {qualified["cap"]:g}')
    figures=ROOT/'docs/iterations/brg_adaptation/03_adapt_bem_to_brg_data/figures';figures.mkdir(exist_ok=True)
    fig.savefig(figures/'glider_033.png',dpi=160,bbox_inches='tight');plt.close(fig)
    files=[]
    for path in sorted((out/'local').rglob('*')):
        if path.is_file():files.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    write(out/'bulk_manifest.json',dict(files=files))
    print(json.dumps(metrics,indent=2),flush=True)


if __name__=='__main__':main()
