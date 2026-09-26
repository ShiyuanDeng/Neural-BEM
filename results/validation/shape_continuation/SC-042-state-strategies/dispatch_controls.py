"""Scheduling only: fill freed worker slots without changing the frozen jobs.

Star and the unchanged kite have been inspected. Preserve the six-worker
host ceiling while the other kite jobs and two fresh-case workers continue.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc042_dispatch_source',HERE/'run.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def terminal(folder):
    return (folder/'result.json').exists() or (folder/'failure.json').exists()


def main():
    r.verify()
    if len(sys.argv)==3:
        r.worker(tuple(sys.argv[1:]))
        return
    pending=[(case,arm) for case in r.CASES[2:] for arm in r.ARMS
             if not (HERE/'runs'/case/arm).exists()]
    active=[]
    print('Slot-aware scheduling of the unchanged frozen control jobs:',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
    while pending or active:
        remaining=[]
        for process,job in active:
            code=process.poll()
            if code is None:
                remaining.append((process,job))
            elif not terminal(HERE/'runs'/job[0]/job[1]):
                folder=HERE/'runs'/job[0]/job[1]
                folder.mkdir(parents=True,exist_ok=True)
                r.write(folder/'failure.json',dict(case=job[0],arm=job[1],outcome='EXECUTION_FAILURE',
                    exit_code=code,detail='Worker exited without a terminal record; all partial files retained.'))
        active=remaining
        first_wave=sum(not terminal(HERE/'runs'/case/arm) for case in r.CASES[:2] for arm in r.ARMS)
        fresh=HERE.parent/'SC-044-noisy-fresh-cases/runs'
        fresh_done=sum(terminal(fresh/case/profile/arm) for case in ('asymmetric_lobes','deep_c')
                       for profile in ('clean','noise_seed_0','noise_seed_1') for arm in ('none','boundary','cap'))
        noise_reserve=2 if fresh_done<18 else 0
        slots=max(0,min(4-len(active),6-first_wave-noise_reserve-len(active)))
        for _ in range(min(slots,len(pending))):
            job=pending.pop(0)
            print('LAUNCH',*job,'first_wave',first_wave,'noise_reserved',noise_reserve,flush=True)
            process=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),*job])
            active.append((process,job))
        if pending or active:time.sleep(5)
    r.summarize()
    subprocess.run([sys.executable,str(HERE/'analyse.py')],check=True)


if __name__=='__main__':main()
