"""True-shape forward qualification only; largest passing BRG ladder prefix."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'solvers'),str(ROOT)]
BASE=ROOT/'results/brg/bem_adaptation/2026-11-17'


def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def check_one(case,k,out):
    import numpy as np
    from bem_inverse import Execution
    from bem_inverse.forward_solvers.modal_muller import ModalMuller,ModalSettings,forward_solve
    from experiments.baselines.brg.brg_data import observation,true_curve
    from experiments.baselines.brg.run_paper import CASES
    start=time.monotonic();record=dict(k=k,passes=False)
    try:
        shape,eta,_=CASES[case];curve=true_curve(shape)
        obs,path,data_record=observation(case,k)
        context=ModalMuller(Execution(device='cpu',frequency_threads=1),ModalSettings(table_mode=True))
        profile=context.resolution_profile(curve.band)
        record.update(source=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      profile=profile,data_record=data_record)
        a=forward_solve(curve,obs,eta,profile['production'],context=context)
        b=forward_solve(curve,obs,eta,profile['refined'],context=context)
        difference=a.prediction-obs.scattered
        relative=float(np.linalg.norm(difference)/np.linalg.norm(obs.scattered))
        refinement=float(np.linalg.norm(a.prediction-b.prediction)/np.linalg.norm(b.prediction))
        record.update(relative_brg_difference=relative,relative_refinement_difference=refinement,
                      max_absolute_difference=float(abs(difference).max()),production=a.diagnostics,refined=b.diagnostics,
                      illumination_relative_errors=(np.linalg.norm(difference,axis=1)/np.linalg.norm(obs.scattered,axis=1)).tolist(),
                      receiver_relative_errors=(np.linalg.norm(difference,axis=0)/np.linalg.norm(obs.scattered,axis=0)).tolist(),
                      passes=relative<=1e-5 and refinement<=1e-6)
        np.savez_compressed(out/'local'/f'k_{k:g}.npz',production=a.prediction,refined=b.prediction,observed=obs.scattered)
    except Exception as error:
        record.update(exception=repr(error),traceback=traceback.format_exc())
    record['wall_seconds']=time.monotonic()-start
    write(out/f'k_{k:g}.json',record)
    print(json.dumps(record),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--one',type=float);args=parser.parse_args()
    out=BASE/args.case/'forward';(out/'local').mkdir(parents=True,exist_ok=True)
    if args.one is not None:return check_one(args.case,args.one,out)
    from experiments.baselines.brg.brg_data import LADDER
    assert not (out/'qualification.json').exists(),'Do not overwrite the first qualification.'
    start=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    passed=[];rows=[];reason=None
    for k in LADDER:
        remaining=1800-(time.monotonic()-start)
        if remaining<=0:reason='30-minute forward limit';break
        command=[sys.executable,str(Path(__file__).resolve()),'--case',args.case,'--one',str(k)]
        with (out/'local'/f'k_{k:g}.log').open('w') as stream:
            try:
                result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining)
            except subprocess.TimeoutExpired:
                reason='30-minute forward limit';break
        file=out/f'k_{k:g}.json'
        if not file.exists():reason=f'check process failed with {result.returncode} at k={k}';break
        row=json.loads(file.read_text());rows.append(row)
        if not row['passes']:reason=row.get('exception','forward comparison/refinement threshold failed');break
        passed.append(k)
        print(f'PASS {args.case} k={k:g} error={row["relative_brg_difference"]:.3g}',flush=True)
    manifest=[]
    for p in sorted((out/'local').iterdir()):
        if p.is_file():manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    write(out/'qualification.json',dict(case=args.case,started=started,wall_seconds=time.monotonic()-start,
          passing_prefix=passed,cap=max(passed) if passed else None,stop_reason=reason,
          attempted=[r['k'] for r in rows],thresholds=dict(brg=1e-5,refinement=1e-6),
          series_loss=1e-9,bulk_files=manifest,
          command=f'{sys.executable} experiments/baselines/brg/check_forward_prefix.py --case {args.case}'))


if __name__=='__main__':main()
