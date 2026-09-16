"""Sequential full current-pipeline reference/fast controls; no altered settings."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

from experiments.top025 import run as pipeline
from sdf_inverse.runtime import inverse_runtime, runtime_metadata

ROOT = pipeline.ROOT
SOURCE = ROOT/'results/validation/topology/TOP-025-20260915-210356-all-scenes-current'
SCENES = ('death', 'split')
PLAN = ROOT/'docs/iterations/speedup/iteration_02/03_plan.md'
read, write = pipeline.read, pipeline.write


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def workers():
    result=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name)==os.getpid():continue
        try:
            args=(path/'cmdline').read_bytes().split(b'\0')
            executable=Path(args[0].decode()).name
            cmd=b' '.join(args).decode(errors='replace')
            if ((executable.startswith('python') and str((path/'cwd').resolve())==str(ROOT)
                 and any(x in cmd for x in ('.py','pytest','experiments.'))) or executable=='ffmpeg'):
                result.append(dict(pid=int(path.name),command=cmd))
        except (OSError,UnicodeError):pass
    return result


def prepare(bundle):
    if workers():raise RuntimeError('Other numerical/render worker active')
    bundle.mkdir(parents=True,exist_ok=False)
    sources={**pipeline.source_hashes(),str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))}
    write(bundle/'manifest.json',dict(source_sha256=sources,created_utc=datetime.now(timezone.utc).isoformat(),
        scenes=SCENES,profiles=['reference','fast'],wall_ceiling_seconds=2400,blas_threads=1,
        command=sys.argv,scope='two complete current-pipeline cases; original starts and settings'))
    for name in sources:
        dest=bundle/'measured_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    shutil.copyfile(PLAN,bundle/'approved_plan.md')
    for name in ('initial_tests','tests'):
        source=Path(f'/tmp/spd002_{name}.log')
        if source.exists():shutil.copyfile(source,bundle/f'{name}.log')
    for profile in ('reference','fast'):
        dest=bundle/profile;dest.mkdir()
        paths=[SOURCE/'scene_spec.json',SOURCE/'oracle_audit.json']
        paths += [p for scene in SCENES for p in sorted((SOURCE/'inputs'/scene).glob('*.json'))]
        for p in paths:
            target=dest/p.relative_to(SOURCE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        with inverse_runtime(profile):
            contract={**read(SOURCE/'contract.json'), 'experiment':'SPD-002', 'scenes':list(SCENES),
                'inverse_runtime':runtime_metadata(), 'budget_unit':'full system or analytic directional assembly/tangent',
                'approval':'user requested default promotion and current pipeline speedup'}
        write(dest/'contract.json',contract)
        write(dest/'manifest.json',dict(source_sha256=pipeline.source_hashes(),
            historical_input_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
            input_sha256={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*.json')}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True)
    bundle=parser.parse_args().bundle.resolve();prepare(bundle)
    rows=[];start=time.monotonic()
    try:
        for scene in SCENES:
            for profile in ('reference','fast'):
                active=workers()
                if active:raise RuntimeError(f'Other numerical worker: {active}')
                for name,h in read(bundle/'manifest.json')['source_sha256'].items():
                    if sha(ROOT/name)!=h:raise RuntimeError('Source changed: '+name)
                remaining=2400-(time.monotonic()-start)
                if remaining<=0:raise TimeoutError('SPD-002 wall ceiling')
                env={**os.environ,'SDF_INVERSE_RUNTIME':profile}
                before=time.monotonic();load_before=list(os.getloadavg())
                command=[sys.executable,'-u','-m','experiments.top025.run','scene','--bundle',str(bundle/profile),
                    '--scene',scene,'--inverse-runtime',profile]
                with (bundle/f'{profile}_{scene}.log').open('w') as stream:
                    process=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=remaining)
                row=dict(scene=scene,profile=profile,seconds=time.monotonic()-before,returncode=process.returncode,
                    workers_before=active,workers_after=workers(),load_before=load_before,load_after=list(os.getloadavg()),command=command)
                path=bundle/profile/'runs'/scene/'result.json'
                result=read(path) if path.exists() else {}
                row.update(recovered=result.get('fresh_recovery_pass',False),status=result.get('status','MISSING_RESULT'),
                    sources_and_inputs_unchanged=result.get('sources_and_inputs_unchanged',False),
                    full_system_attempts=result.get('actual_attempted_calls'))
                rows.append(row);write(bundle/'timings.json',rows);print(json.dumps(row),flush=True)
                if process.returncode or row['workers_after'] or not row['sources_and_inputs_unchanged']:
                    raise RuntimeError('Invalid pipeline run')
                if not row['recovered']:raise RuntimeError('Full-case recovery regression; stop before next arm')
        write(bundle/'execution_status.json',dict(status='COMPLETE',seconds=time.monotonic()-start))
    except BaseException as exc:
        write(bundle/'execution_status.json',dict(status='STOPPED',error=repr(exc),seconds=time.monotonic()-start))
        raise


if __name__=='__main__':main()
