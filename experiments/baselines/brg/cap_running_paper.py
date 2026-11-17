"""Redirect an already-loaded pre-max-k MATLAB wrapper at a saved frequency."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import time

ROOT=Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--pid',type=int,required=True);parser.add_argument('--max-k',type=float,required=True)
    args=parser.parse_args();out=ROOT/'results/brg/paper_examples/2026-11-17'/args.case/'shipped'
    index=round((args.max_k-1)*4)+1
    while not ((out/f'frequency_{index:03d}.mat').exists() and (out/'local'/f'state_{index:03d}.mat').exists()):
        if not Path(f'/proc/{args.pid}').exists():raise SystemExit('MATLAB ended before the requested saved frequency.')
        time.sleep(.2)
    command=Path(f'/proc/{args.pid}/cmdline').read_bytes()
    assert b'MATLAB' in command and b'run_paper_case' in command
    os.kill(args.pid,signal.SIGTERM)
    attempts=sorted(out.glob('attempt_*.json'));attempt=attempts[-1]
    for _ in range(120):
        row=json.loads(attempt.read_text())
        if 'wall_seconds' in row:break
        time.sleep(.5)
    row['status']='stopped_at_requested_max_k';row['requested_max_k']=args.max_k
    row['stop_reason']='Coordinator shortened the running paper sweep; exact state retained for resume.'
    attempt.write_text(json.dumps(row,indent=2)+'\n')
    summary=json.loads((out/'summary.json').read_text());summary['status']='complete_to_max_k';summary['requested_max_k']=args.max_k
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    record=dict(ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=args.pid,max_k=args.max_k,
                saved_frequency=index,status='redirected_after_saved_frequency',resume_allowed=True)
    (out/'redirect_k15.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)


if __name__=='__main__':main()
