"""Observe the heavy-policy tail without altering workers or numerical settings."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent


def main():
    path=HERE/'host_tail.jsonl'
    with path.open('x') as stream:
        while True:
            memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
            processes=subprocess.check_output(['ps','-eo','pid,ppid,etime,rss,pcpu,args'],text=True)
            workers=[line.strip() for line in processes.splitlines()
                     if str(HERE/'dispatch.py')+' kite ' in line]
            terminal=sum((p/'result.json').exists() or (p/'failure.json').exists()
                         for case in ('circle_to_star','kite','wrong_circle','circle_to_c','peanut','hook')
                         for policy in ('fixed','stagnation','atlas')
                         for p in [HERE/'runs'/case/policy])
            sample=dict(utc=datetime.now(timezone.utc).isoformat(),terminal=terminal,
                mem_available_kib=int(memory['MemAvailable'].split()[0]),
                pressure=Path('/proc/pressure/memory').read_text().strip(),workers=workers)
            stream.write(json.dumps(sample)+'\n')
            stream.flush()
            print(json.dumps(sample),flush=True)
            if terminal==18:break
            time.sleep(50)


if __name__=='__main__':main()
