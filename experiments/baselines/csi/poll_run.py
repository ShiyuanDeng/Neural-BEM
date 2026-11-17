"""Record baseline overlap and report saved status for a detached CSI run."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('run',type=Path)
    args=parser.parse_args(); run=args.run
    launch=json.loads((run/'launch.json').read_text())
    text=(run/'matlab.log').read_text()
    phase=None; iteration=None
    for line in text.splitlines():
        m=re.match(r'^(CCCSI|MRCSI|CSI)-MF iteration starts',line)
        if m: phase=m[1]; iteration=0
        m=re.match(r'^\s+(\d+)\s+[-\d.]+e[+-]\d+',line)
        if m: iteration=int(m[1])
    processes=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid=,args='],text=True)
    matlab=[line.strip() for line in processes.splitlines()
            if re.match(r'^\s*\d+\s+/\S+/bin/glnxa64/MATLAB\s+-batch',line)]
    record=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),phase=phase,iteration=iteration,
                active_matlab=matlab,matlab_count=len(matlab),csi_threads=8,
                returncode=launch.get('returncode'),complete='finished_utc' in launch)
    with (run/'overlap.jsonl').open('a') as file: file.write(json.dumps(record)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k!='active_matlab'}))
    print(text.splitlines()[-1] if text else 'Starting MATLAB')


if __name__=='__main__': main()
