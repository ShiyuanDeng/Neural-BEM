"""Manifest preparation inputs, compact evidence and ignored local payloads."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

REPO=Path(__file__).resolve().parents[3]


def entry(path):
    path=path.resolve();digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    ignored=subprocess.run(['git','check-ignore','-q',str(path)],cwd=REPO).returncode==0
    return dict(path=str(path.relative_to(REPO)),bytes=path.stat().st_size,sha256=digest.hexdigest(),storage='local, git-ignored' if ignored else 'git')


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('purpose');args=parser.parse_args()
    run=REPO/f'results/csi/preparation/2026-11-17_{args.purpose}'
    record=dict(files=[entry(p) for p in sorted(run.iterdir()) if p.is_file() and p.name!='manifest.json'],
        wrapper_sources=[entry(p) for p in sorted((REPO/'experiments/baselines/csi').iterdir()) if p.suffix in ('.py','.m')],
        patches=[entry(p) for p in sorted((REPO/'external/patches/cc-csi').glob('*.patch'))])
    launch=run/'launch.json'
    if launch.exists():
        record['launch']=json.loads(launch.read_text())
        record['wrapper_command']=['python3','experiments/baselines/csi/run_preparation.py',args.purpose]
    elif args.purpose=='cost':record['command']='python3 experiments/baselines/csi/preparation_cost.py'
    else:record['command']='env PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.baselines.csi.'+('prepare_geometry' if args.purpose=='geometry' else 'register_saved')
    inputs=[]
    if args.purpose=='frame':inputs.append(REPO/'results/csi/fresnel/2026-11-17_diel_tm/final_contrast.mat')
    if args.purpose=='geometry':inputs.append(REPO/'experiments/benchmark/scenes.py')
    if args.purpose=='cost':
        inputs.extend(sorted((REPO/'results/csi').rglob('matlab_summary.json')))
        inputs.extend(REPO/'results/csi/preparation'/p for p in (
            '2026-11-17_probe/launch.json','2026-11-17_probe/scores.json',
            '2026-11-17_snapshots/scores.json','2026-11-17_generate/forward_summary.json',
            '2026-11-17_generate/launch.json'))
    if args.purpose in ('generate','probe'):inputs.append(REPO/'results/csi/preparation/2026-11-17_geometry/geometry.mat')
    if args.purpose=='probe':inputs.append(REPO/'results/csi/preparation/2026-11-17_generate/synthetic_input.txt')
    if args.purpose in ('generate','snapshots'):
        inputs.append(next((Path.home()/'neural_bem_external/CC-CSI').rglob('dielTM_dec8f.txt')))
    record['inputs']=[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs]
    record['git_bytes']=sum(e['bytes'] for e in record['files'] if e['storage']=='git')
    assert record['git_bytes']<5*1024**2
    (run/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(purpose=args.purpose,git_bytes=record['git_bytes'],files=len(record['files']))))


if __name__=='__main__':main()
