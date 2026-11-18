"""Copied BRG reference driver; CPU/GPU table-path checks, no comparison-code edits."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
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
BASE=ROOT/'results/bem/baseline_data/gpu_table_path/2026-11-18'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['cpu_before','gpu_before_1','gpu_before_2','cpu_after','gpu_after'])
    parser.add_argument('--device',choices=['cpu','cuda'],required=True)
    parser.add_argument('--suite',action='store_true')
    args=parser.parse_args()
    if args.device == 'cpu': os.environ['CUDA_VISIBLE_DEVICES']=''
    dirty=subprocess.check_output(['git','status','--porcelain','--','solvers/bem_inverse'],cwd=ROOT,text=True)
    if 'before' in args.phase: assert not dirty,'Pre-edit references require a clean solver.'
    out=BASE/args.phase;local=out/'local';local.mkdir(parents=True,exist_ok=True)
    assert not (out/'receipt.json').exists(),'Keep the first reference; do not overwrite a run.'
    remaining=3600
    start=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'solvers/bem_inverse').rglob('*.py'))}
    (out/'source_hashes.json').write_text(json.dumps(source,indent=2)+'\n')
    command=[sys.executable,'-m','pytest','pytest/bem_inverse','-q',f'--junitxml={out}/tests.xml']
    env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'solvers')+':'+str(ROOT)
    receipt=dict(phase=args.phase,started=started,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        solver_dirty=dirty,device=args.device,cpu_pinned=args.device=='cpu')
    if args.suite:
        t=time.monotonic()
        with (local/'tests.log').open('w') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining)
        receipt.update(test_command=command,test_returncode=result.returncode,test_seconds=time.monotonic()-t)
        (out/'tests_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        assert result.returncode == 0, 'Pre-edit suite failed; retain evidence and stop.'
    import numpy as np
    from bem_inverse.physics import Execution
    from bem_inverse.io import write
    from experiments.comparison import bem,runs
    if args.device == 'cuda':
        import torch
        assert torch.cuda.is_available(), 'GPU reference requires CUDA.'
        torch.cuda.reset_peak_memory_stats()
    bem.EXECUTION=Execution(device=args.device,frequency_threads=4)
    run=runs.parse('bem/default_clean_uc_fc')
    write(out/'fit_settings.json',bem.settings(run))
    record,arrays=bem.fit_case(run,'circle__c0.5',out)
    write(out/'fit.json',record)
    np.savez_compressed(out/'fit.npz',**arrays)
    receipt.update(ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_seconds=time.monotonic()-start,
                   fit_outcome=record['outcome'],fit_seconds=record.get('fit_seconds'),case='circle__c0.5')
    receipt['solver_dirty_end']=subprocess.check_output(['git','status','--porcelain','--','solvers/bem_inverse'],cwd=ROOT,text=True)
    if args.device == 'cuda':
        receipt.update(gpu_name=torch.cuda.get_device_name(),
                       gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                       gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved())
    write(out/'receipt.json',receipt)
    print(json.dumps(receipt,indent=2),flush=True)
    files=[]
    for p in [out/'fit.npz', *local.rglob('*')]:
        if p.is_file():files.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    assert record['outcome'] != 'WORKER_EXCEPTION',record['detail']
    write(out/'bulk_manifest.json',dict(command=[sys.executable,*sys.argv],files=files))


if __name__=='__main__':main()
