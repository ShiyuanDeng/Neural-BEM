"""TOP-017 outer watchdog; at most two independent numerical workers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import run_top017 as m


def run_worker(bundle,label,arguments,deadline,clock=time.monotonic,popen=subprocess.Popen):
    command=[sys.executable,str(m.ROOT/'run_top017.py'),'--bundle',str(bundle),*arguments]
    started=clock()
    if started>=deadline:
        return dict(label=label,command=command,exit_code=None,campaign_timeout=True,
                    elapsed_seconds=0.,status='NOT_DISPATCHED')
    with (bundle/f'{label}.log').open('x') as log:
        process=popen(command,cwd=m.ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        timed_out=False
        try:code=process.wait(timeout=max(.001,deadline-clock()))
        except subprocess.TimeoutExpired:
            timed_out=True
            # A wall signal uses the same typed hard-stop path and retains evidence.
            os.killpg(process.pid,signal.SIGALRM)
            try:code=process.wait(timeout=5.)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);code=process.wait()
    return dict(label=label,command=command,exit_code=code,campaign_timeout=timed_out,
                elapsed_seconds=clock()-started)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();bundle=args.bundle.resolve()
    target=bundle/'campaign.json'
    if target.exists(): raise ValueError('campaign already exists; inspect artifacts before any resumption')
    began=time.monotonic();deadline=began+7500.
    environment=dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        cpu=subprocess.check_output(['lscpu'],text=True),threads={k:os.environ.get(k) for k in
        ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},numerical_workers=2,
        initial_load=os.getloadavg(),command=sys.argv)
    m.write(bundle/'environment.json',environment)
    record=dict(status='IN_PROGRESS',watchdog_seconds=7500,workers=[],command=sys.argv)
    m.write(target,record)
    def run(label,arguments):
        return run_worker(bundle,label,arguments,deadline)
    audit=run('phase_a',['--phase','audit']);record['workers'].append(audit)
    m.write(target,record)
    path=bundle/'phase_a/audit.json'
    if audit['exit_code']==0 and path.exists() and m.read(path)['status']=='PHASE_A_PASS':
        jobs=[(f'{arm}-{scene}',['--phase','trial','--scene',scene,'--arm',arm])
              for scene in m.SCENES for arm in ('S','F')]
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Writes stay in the parent; workers only own their own output paths.
            futures=[pool.submit(run,*job) for job in jobs]
            for future in futures:
                record['workers'].append(future.result());m.write(target,record)
        record['status']='COMPLETE' if all(w['exit_code']==0 and not w['campaign_timeout'] for w in record['workers']) else 'COMPLETE_WITH_UNAVAILABLE_OR_FAILED_WORKERS'
    else:record['status']='STOPPED_AT_PHASE_A'
    record['elapsed_seconds']=time.monotonic()-began
    m.write(target,record)
    print(json.dumps(record),flush=True)

if __name__=='__main__':main()
