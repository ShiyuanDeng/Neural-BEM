"""Stage (a): compare exact true glider with the saved BRG plane-wave table."""
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
from experiments.baselines.brg.brg_data import observation,true_curve


def main():
    out=ROOT/'results/brg/bem_adaptation/2026-11-17/stage_a';out.mkdir(parents=True,exist_ok=True)
    assert not (out/'glider_k1.json').exists(),'Do not overwrite evidence.'
    start=time.monotonic()
    obs,path,data_record=observation('glider_033',1.)
    curve=true_curve('glider')
    context=ModalMuller(Execution(device='cpu',frequency_threads=1),ModalSettings(table_mode=True))
    profile=context.resolution_profile(curve.band)
    a=forward_solve(curve,obs,.33,profile['production'],context=context)
    b=forward_solve(curve,obs,.33,profile['refined'],context=context)
    error=np.linalg.norm(a.prediction-obs.scattered)/np.linalg.norm(obs.scattered)
    refined=np.linalg.norm(b.prediction-a.prediction)/np.linalg.norm(b.prediction)
    record=dict(case='glider_033',k=1.,eta=.33,relative_brg_difference=float(error),
        relative_refinement_difference=float(refined),max_absolute_difference=float(abs(a.prediction-obs.scattered).max()),
        shape=list(obs.scattered.shape),source=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        data_record=data_record,production=a.diagnostics,refined=b.diagnostics,profile=profile,
        wall_seconds=time.monotonic()-start,passes=bool(error<=1e-5 and refined<=1e-6))
    np.savez_compressed(out/'glider_k1.npz',observed=obs.scattered,production=a.prediction,refined=b.prediction,coefficients=curve.coefficients)
    (out/'glider_k1.json').write_text(json.dumps(record,indent=2)+'\n')
    (out/'check_receipt_forward.json').write_text(json.dumps(dict(wall_seconds=record['wall_seconds'],kind='shared_stage_a_forward'),indent=2)+'\n')
    print(json.dumps(record,indent=2),flush=True)
    assert record['passes'],'Forward check failed; preserve evidence before diagnosing.'


if __name__=='__main__':main()
