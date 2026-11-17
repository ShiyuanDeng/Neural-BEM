"""Stage (b): B7 against two complete-slider differences on the true glider."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'solvers'),str(ROOT)]
from bem_inverse import Execution
from bem_inverse.forward_solvers.modal_muller import ModalMuller,ModalSettings,forward_solve
from bem_inverse.geometry_selection import make_update
from experiments.baselines.brg.brg_data import observation,true_curve


def main():
    out=ROOT/'results/brg/bem_adaptation/2026-11-17/stage_b';out.mkdir(parents=True,exist_ok=True)
    assert not (out/'glider_derivative.json').exists(),'Do not overwrite evidence.'
    start=time.monotonic();curve=true_curve('glider')
    full,source,_=observation('glider_033',1.)
    mask=np.indices(full.scattered.shape).sum(axis=0)%3!=0
    cases=[];arrays={}
    for label,use_mask in [('full',None),('masked',mask)]:
        obs,_,_=observation('glider_033',1.,use_mask)
        context=ModalMuller(Execution(device='cpu',frequency_threads=1),ModalSettings(table_mode=True))
        nodes=context.resolution_profile(curve.band)['production']
        update,trial=make_update('slider',1.,context.execution)
        space=update.prepare(curve,3,curve.band)
        state=forward_solve(curve,obs,.33,nodes,context=context)
        direction=np.array([.3,-.2,.1,.4,-.3,.2,.1]);direction/=np.linalg.norm(direction)
        analytic=context.derivative(state,update,space)@direction
        errors=[];steps=[2e-3,1e-3]
        for step in steps:
            plus,_=trial(step*direction,prepared=space);minus,_=trial(-step*direction,prepared=space)
            p=forward_solve(plus,obs,.33,nodes,context=context).prediction
            m=forward_solve(minus,obs,.33,nodes,context=context).prediction
            finite=(p-m)/(2*step)
            errors.append(float(np.linalg.norm(finite-analytic)/np.linalg.norm(analytic)))
        arrays[label+'_analytic']=analytic;arrays[label+'_finite']=finite
        cases.append(dict(layout=label,measured_pairs=int(obs.scattered.size),steps=steps,relative_errors=errors,
                          passes=bool(errors[-1]<1e-3 and errors[-1]<errors[0])))
    record=dict(case='glider_033',k=1.,eta=.33,cases=cases,wall_seconds=time.monotonic()-start,
                source=str(source.relative_to(ROOT)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (out/'glider_derivative.json').write_text(json.dumps(record,indent=2)+'\n')
    (out/'check_receipt_derivative.json').write_text(json.dumps(dict(wall_seconds=record['wall_seconds']),indent=2)+'\n')
    np.savez_compressed(out/'glider_derivative.npz',**arrays)
    print(json.dumps(record,indent=2),flush=True)
    assert all(c['passes'] for c in cases),'Derivative check failed; retain evidence.'


if __name__=='__main__':main()
