"""Bounded subprocess campaign; timeout and exception rows remain in denominator."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['controller','controller_guarded','controller_full','continuation'])
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--scenes',nargs='*')
    parser.add_argument('--arms',nargs='*')
    parser.add_argument('--output',type=Path,default=ROOT/'results/exploratory_continuation')
    args = parser.parse_args()
    spec = json.loads((ROOT/'config/topology_scenes_v1.json').read_text())
    scenes = args.scenes or [s['id'] for s in spec['scenes']]
    arms = args.arms or (['current','topo'] if args.mode.startswith('controller')
            else ['sc_fixed_band','rla_0.5','rla_1.0','rla_1.5']+[f'scif_{j}' for j in range(8)])
    def run(job):
        scene,arm = job
        result = args.output/args.mode/arm/f'{scene}.json'
        if result.exists() and json.loads(result.read_text()).get('status')!='STARTED':
            return dict(scene=scene,arm=arm,status='EXISTING')
        logs = args.output/'logs'
        logs.mkdir(parents=True,exist_ok=True)
        started = perf_counter()
        command = [sys.executable,'-m','experiments.exploratory_continuation.run',args.mode,
                   '--scene',scene,'--arm',arm,'--output',str(args.output)]
        env = dict(os.environ,PYTHONPATH=f'{ROOT}/solvers:{ROOT}')
        with (logs/f'{args.mode}-{arm}-{scene}.log').open('w') as stream:
            try:
                completed = subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
                                           timeout=args.timeout)
                status = 'RETURNED' if completed.returncode==0 else 'PROCESS_FAILURE'
            except subprocess.TimeoutExpired:
                status = 'TIMEOUT'
        if status!='RETURNED':
            record = json.loads(result.read_text()) if result.exists() else dict(scene=scene,arm=arm)
            checkpoint = args.output/args.mode/arm/f'{scene}.checkpoint.json'
            if checkpoint.exists():
                record['last_checkpoint']=json.loads(checkpoint.read_text())
            record.update(status=status,timeout_seconds=args.timeout,wall_seconds=perf_counter()-started,
                          work_incomplete=True,reason='Process ended before final work ledger; partial counters unavailable.')
            result.parent.mkdir(parents=True,exist_ok=True)
            result.write_text(json.dumps(record,indent=2)+'\n')
        row = dict(scene=scene,arm=arm,status=status,seconds=perf_counter()-started)
        print(json.dumps(row),flush=True)
        return row
    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(run,[(s,a) for s in scenes for a in arms]))
    (args.output/f'{args.mode}_campaign.json').write_text(json.dumps(dict(
        rows=rows,workers=args.workers,timeout=args.timeout,expected_runs=len(scenes)*len(arms)),indent=2)+'\n')


if __name__=='__main__':
    main()
