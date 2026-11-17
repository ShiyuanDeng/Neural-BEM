"""Lightweight resource evidence during the coordinator-approved overlap."""
import datetime
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'results/brg/paper_examples/2026-11-17'
CASES=['glider_033','glider_10','star_full','star_limited','cavity_09','cavity_2']

if __name__=='__main__':
    with (BASE/'resource_monitor_k15.jsonl').open('a',buffering=1) as stream:
        while True:
            memory=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))/1024**2
            processes=subprocess.run(['ps','-C','MATLAB','-o','pid=,rss='],capture_output=True,text=True).stdout.splitlines()
            complete=[case for case in CASES if (BASE/case/'shipped/frequency_057.mat').exists()]
            row=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),available_gib=memory,
                     matlab_pid_rss_kib=processes,k15_saved=complete,reserve_ok=memory>=14)
            stream.write(json.dumps(row)+'\n')
            if memory<14:(BASE/'memory_alert.json').write_text(json.dumps(row,indent=2)+'\n')
            if len(complete)==6:break
            time.sleep(10)
