"""Run frozen policies after SC-042, filling slots freed by SC-044.

Only scheduling changes. The worker, numerical contract, quotas and inputs
are the frozen run.py implementation. At most six PDE workers share the host.
"""
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc043_dispatch_source',HERE/'run.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def terminal(folder):
    return (folder/'result.json').exists() or (folder/'failure.json').exists()


def main():
    r.verify()
    if len(sys.argv)==3:
        r.worker(tuple(sys.argv[1:]))
        return
    state=HERE.parent/'SC-042-state-strategies/runs'
    print('Slot-aware policy queue: waiting for all 24 state-treatment paths.',flush=True)
    while not all(terminal(state/case/arm) for case in r.c.CASES for arm in r.c.ARMS):
        time.sleep(5)
    qualification=HERE.parent/'SC-045-timeout-qualification/summary.json'
    print('Waiting for the separately recorded timeout qualifications.',flush=True)
    while not qualification.exists():time.sleep(5)
    recovery=HERE.parent/'SC-046-lost-audit-recovery/summary.json'
    print('Waiting for the separately accounted lost-result recovery.',flush=True)
    while not recovery.exists():time.sleep(5)
    pending=[(case,policy) for case in r.c.CASES for policy in r.POLICIES
             if not (HERE/'runs'/case/policy).exists()]
    active=[]
    print('Starting frozen prospective policy study',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
    while pending or active:
        remaining=[]
        for process,job in active:
            code=process.poll()
            if code is None:
                remaining.append((process,job))
            elif not terminal(HERE/'runs'/job[0]/job[1]):
                folder=HERE/'runs'/job[0]/job[1]
                folder.mkdir(parents=True,exist_ok=True)
                r.c.write(folder/'failure.json',dict(case=job[0],policy=job[1],outcome='EXECUTION_FAILURE',
                    exit_code=code,detail='Worker exited without a terminal record; all partial files retained.'))
        active=remaining
        fresh=HERE.parent/'SC-044-noisy-fresh-cases/runs'
        fresh_done=sum(terminal(fresh/case/profile/arm) for case in ('asymmetric_lobes','deep_c')
                       for profile in ('clean','noise_seed_0','noise_seed_1') for arm in ('none','boundary','cap'))
        reserve=2 if fresh_done<18 else 0
        # A serial kite audit was observed above 17 GiB before its final
        # allocations. Do not overlap two such paths on this 64 GB host.
        weight=lambda job: 5 if job[0]=='kite' else 1
        while pending and len(active)+reserve<6:
            used=reserve+sum(weight(job) for _,job in active)
            candidates=[i for i,job in enumerate(pending) if used+weight(job)<=8]
            meminfo=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
            available_kib=int(meminfo['MemAvailable'].split()[0])
            if not candidates or available_kib<12*1024**2:break
            job=pending.pop(candidates[0])
            print('LAUNCH',*job,'noise_reserved',reserve,'memory_weight',used+weight(job),flush=True)
            process=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),*job])
            active.append((process,job))
        if pending or active:time.sleep(5)
    r.summarize()
    subprocess.run([sys.executable,str(HERE/'analyse.py')],check=True)


if __name__=='__main__':main()
