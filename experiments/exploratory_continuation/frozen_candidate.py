"""Refine the same rejected merge proposal, avoiding changed-trajectory comparisons."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
os.environ['SC_FORWARD_BACKEND']='cpu'
os.environ['SC_FREQUENCY_THREADS']='1'
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from scipy.spatial.distance import cdist
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.multi_object import MultiCurve,MultiUpdate
from experiments.shape_continuation.updates import BorgesUpdate
from experiments.shape_continuation.forward import PointSourceAcquisition,Work,solve
from experiments.shape_continuation.inverse import Observation
from experiments.shape_continuation.lm_backend import FitStage,Ledger,BackendConfig,fit_stage
from .run import OUTPUT,write,LENGTH


class TrackingUpdate(MultiUpdate):
    last_candidate=None
    def trial(self,*args,**kwargs):
        curve,metadata=super().trial(*args,**kwargs)
        self.last_candidate=curve
        return curve,metadata


def main():
    previous=json.loads((OUTPUT/'continuation_cap512_n256/scif_0/merge.json').read_text())
    curves=tuple(FourierCurve(np.array(c['real'])+1j*np.array(c['imag'])) for c in previous['final_coefficients'])
    initial=MultiCurve(curves,tuple(f'topo.{i}' for i in range(len(curves))))
    saved=np.load(OUTPUT/'frequency_data/merge.npz')
    acquisition=PointSourceAcquisition(saved['sources'],saved['receivers'],complex(saved['strength']))
    observation=Observation(float(saved['wavenumbers'][-1]),acquisition,saved['observed'][-1])
    update=TrackingUpdate(BorgesUpdate(LENGTH,projection_tolerance=1e-3))
    stage=FitStage('replay-rejected-final-proposal',(observation,),(1.,),(1e-5,),3,24,256,512,1)
    ledger=Ledger(cap=40,seconds=300,endpoint_reserve=0)
    ledger.begin_stage(stage.label,None)
    result=fit_stage(initial,stage,float(saved['contrast']),update,
        BackendConfig(initial_damping=3e-4,max_damping_trials=2,max_backtracks=3),ledger)
    candidate=update.last_candidate
    record=dict(scope='Frozen last proposal, not a new inverse arm',
        replay_outcome=result.outcome,replay_acceptance_checks=result.acceptance_checks,
        original_rejected_discrepancy=previous['stages'][-1]['acceptance_checks'][-1]['prediction_discrepancy'],
        replay_work=ledger.snapshot(),resolution=[])
    if candidate is None:
        raise RuntimeError('Replay produced no candidate to diagnose.')
    nodes=[c.nodes(2048) for c in candidate.components]
    record['maximum_speed_ratios']=[float(n.speeds.max()/n.speeds.min()) for n in nodes]
    record['minimum_intercomponent_sample_gap_m']=min(float(cdist(a.points,b.points).min()*LENGTH)
        for i,a in enumerate(nodes) for b in nodes[i+1:])
    record['candidate_coefficients']=[dict(real=c.coefficients.real,imag=c.coefficients.imag) for c in candidate.components]
    work=Work(max_forwards=4,max_seconds=300)
    predictions=[]
    for n in (256,512,1024):
        started=perf_counter()
        state=solve(candidate,observation.wavenumber,float(saved['contrast']),acquisition,n,work=work)
        prediction=state.prediction
        row=dict(nodes_per_component=n,seconds=perf_counter()-started,system_residual=state.system_residual,
            relative_change=None if not predictions else float(np.linalg.norm(predictions[-1]-prediction)/np.linalg.norm(prediction)))
        predictions.append(prediction);record['resolution'].append(row);record['forward_work']=work.summary()
        write(OUTPUT/'frozen_candidate_resolution.json',record)
        print(row,flush=True)


if __name__=='__main__':main()
