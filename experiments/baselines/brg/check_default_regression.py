"""Pinned CPU reference before/after BRG extensions; no comparison-code edits."""
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

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'solvers'),str(ROOT)]
BASE=ROOT/'results/brg/bem_adaptation/2026-11-17'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['before','after']);args=parser.parse_args()
    out=BASE/'regression'/args.phase;local=out/'local';local.mkdir(parents=True,exist_ok=True)
    assert not (out/'receipt.json').exists(),'Keep the first reference; do not overwrite a run.'
    prior=[]
    for p in BASE.glob('**/check_receipt*.json'):
        prior.append(json.loads(p.read_text()).get('wall_seconds',0))
    remaining=3600-sum(prior);assert remaining>0,'Shared-check budget exhausted.'
    start=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'solvers/bem_inverse').rglob('*.py'))}
    (out/'source_hashes.json').write_text(json.dumps(source,indent=2)+'\n')
    command=[sys.executable,'-m','pytest','pytest/bem_inverse','-q',f'--junitxml={out}/tests.xml']
    env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'solvers')+':'+str(ROOT)
    t=time.monotonic()
    with (local/'tests.log').open('w') as stream:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining)
    test_seconds=time.monotonic()-t
    receipt=dict(phase=args.phase,started=started,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        test_command=command,test_returncode=result.returncode,test_seconds=test_seconds,cpu_pinned=True)
    (out/'tests_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert time.monotonic()-start+180<remaining,'Not enough shared-check budget for the default fit.'
    import numpy as np
    from bem_inverse.physics import Execution
    from bem_inverse.io import write
    from experiments.comparison import bem,runs
    bem.EXECUTION=Execution(device='cpu',frequency_threads=4)
    run=runs.parse('bem/default_clean_uc_fc')
    write(out/'fit_settings.json',bem.settings(run))
    record,arrays=bem.fit_case(run,'circle__c0.5',out)
    write(out/'fit.json',record)
    np.savez_compressed(out/'fit.npz',**arrays)
    receipt.update(ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_seconds=time.monotonic()-start,
                   fit_outcome=record['outcome'],fit_seconds=record.get('fit_seconds'),case='circle__c0.5')
    for name in ['receipt.json','check_receipt_default.json']:
        write(out/name,receipt)
    print(json.dumps(receipt,indent=2),flush=True)
    files=[]
    for p in local.iterdir():
        if p.is_file():files.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    write(out/'bulk_manifest.json',dict(command=f'{sys.executable} experiments/baselines/brg/check_default_regression.py {args.phase}',files=files))


if __name__=='__main__':main()
