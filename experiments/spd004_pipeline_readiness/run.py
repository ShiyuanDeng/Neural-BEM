"""SPD-004: isolated experiment wrapper around the unchanged full scene worker."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import numpy as np

from experiments.top025 import run as pipeline
from sdf_inverse.runtime import inverse_execution, inverse_runtime, runtime_metadata
from experiments.top025.readiness import combine_work, screen_training, readiness_continuation

ROOT, p, m = pipeline.ROOT, pipeline.p, pipeline.m
read, write = pipeline.read, pipeline.write
HISTORY = ROOT/'results/validation/topology/TOP-025-20260915-210356-all-scenes-current'
PLAN = ROOT/'docs/iterations/speedup/iteration_03/03_plan.md'
NODES = (256, 512)
THREAD_KEYS = ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {**pipeline.source_hashes(), 'pytest/sdf_inverse/test_spd004.py':sha(ROOT/'pytest/sdf_inverse/test_spd004.py'),
        **{str(x.relative_to(ROOT)):sha(x)
        for x in sorted(Path(__file__).parent.glob('*.py'))}}


def environment():
    # PID namespaces can hide host processes. Do not claim host-wide isolation.
    processes = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            try:
                command = (path/'comm').read_text().strip()
                if 'python' in command or command == 'ffmpeg':
                    processes.append(dict(pid=int(path.name), command=command))
            except OSError:
                pass
    return dict(cpu=next((s.split(':',1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines()
                if s.startswith('model name')), 'unknown'), platform=platform.platform(),
                python=sys.version, cpu_count=os.cpu_count(), load_average=os.getloadavg(),
                visible_numerical_processes=processes, process_visibility='current PID namespace; host-wide isolation unverified',
                threads={k:os.environ.get(k) for k in THREAD_KEYS})


def make_arm(parent, label, scenes):
    bundle = parent/label
    bundle.mkdir(exist_ok=False)
    for name in ('scene_spec.json','oracle_audit.json'):
        shutil.copyfile(HISTORY/name,bundle/name)
    historical = {}
    for scene in scenes:
        for path in sorted((HISTORY/'inputs'/scene).glob('*.json')):
            dest=bundle/path.relative_to(HISTORY);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,dest);historical[str(path.relative_to(ROOT))]=sha(path)
    write(bundle/'contract.json',{**read(HISTORY/'contract.json'),'experiment':'SPD-004',
        'inverse_runtime':runtime_metadata(),'scenes':list(scenes),'arm':label,
        'approval':'user: investigate go; bounded architecture investigation'})
    write(bundle/'manifest.json',dict(source_sha256=pipeline.source_hashes(),
        historical_input_sha256=historical,
        input_sha256={str(x.relative_to(bundle)):sha(x) for x in bundle.rglob('*.json')}))
    return bundle


def verify_all(parent):
    manifest=read(parent/'manifest.json')
    if sources()!=manifest['source_sha256']:
        raise RuntimeError('Numerical source changed after freeze')
    for name,digest in manifest['input_sha256'].items():
        if sha(parent/name)!=digest:
            raise RuntimeError('Experiment input changed: '+name)
    for name,digest in manifest['historical_sha256'].items():
        if sha(ROOT/name)!=digest:
            raise RuntimeError('Historical artifact changed: '+name)


def prepare(parent, test_log):
    # An audit may already occupy the freshly named parent; never overwrite a manifest.
    parent.mkdir(parents=True,exist_ok=True)
    if (parent/'manifest.json').exists():
        raise ValueError('Experiment manifest already exists')
    audit=read(parent/'archive/audit.json')
    if audit['status']!='PASS':
        raise ValueError('Archive identified a false early stop')
    shutil.copyfile(PLAN,parent/'approved_plan.md')
    shutil.copyfile(test_log,parent/'tests.log')
    scenes=('death','split','merge')
    with inverse_runtime('fast'):
        for label in ('baseline_0','readiness_0','baseline_1','readiness_1'):
            make_arm(parent,label,scenes if label.endswith('_0') else scenes[:2])
    frozen=sources()
    for name in frozen:
        target=parent/'measured_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    write(parent/'manifest.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
        source_sha256=frozen,git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        environment=environment(),historical_sha256=audit['consumed_sha256'],
        input_sha256={str(x.relative_to(parent)):sha(x) for x in parent.rglob('*.json')
            if 'measured_sources' not in x.parts},
        max_workers=10,campaign_seconds=3600,worker_seconds=1200))


@inverse_execution
def qualify(parent):
    """Recompute four stored handoffs, with strict source/input provenance."""
    output=parent/'qualification.json'
    if output.exists():
        raise ValueError('Qualification output exists')
    frozen=sources();inputs={};rows=[]
    ledger=m.Ledger(cap=64,seconds=300)
    try:
        with ledger.instrument():
            for scene in ('death','split','central-ellipse-star','far-two-stars'):
                handoff=HISTORY/'runs'/scene/'handoff.json'
                observed_path=HISTORY/'inputs'/scene/'training_observations.json'
                saved_path=HISTORY/'runs'/scene/'F/initial_endpoint_predictions.json'
                for path in (handoff,observed_path,saved_path):
                    inputs[str(path.relative_to(ROOT))]=sha(path)
                state=p.driver.deserialize_state(read(handoff)['state'])
                record=read(observed_path)
                observed=np.array(record['observed_real'])+1j*np.array(record['observed_imag'])
                decision,predictions=screen_training(state,observed,p.driver.baseline.iteration01_solve_config(),.008,ledger)
                saved=read(saved_path)
                errors=[]
                for n in NODES:
                    values=saved['predictions'][str(n)]
                    reference=(np.array(values['real'])+1j*np.array(values['imag']))[:,:4]
                    errors.append(float(np.linalg.norm(predictions[n]-reference)/np.linalg.norm(reference)))
                passed=max(errors)<=2e-11 and decision['ready']==(scene in ('death','split'))
                rows.append(dict(scene=scene,decision=decision,against_archived_prediction=errors,passed=passed))
                print('QUALIFY',scene,passed,flush=True)
                if not passed:
                    raise ValueError('Readiness qualification failed')
        if sources()!=frozen or any(sha(ROOT/name)!=h for name,h in inputs.items()):
            raise RuntimeError('Qualification source/input drift')
        status='PASS';error=None
    except Exception as exc:
        status='FAIL';error=repr(exc)
    write(output,dict(status=status,error=error,rows=rows,work=ledger.snapshot(),
        source_sha256=frozen,input_sha256=inputs,environment=environment()))
    if status!='PASS':
        raise RuntimeError(error)


def worker(parent, label, scene):
    verify_all(parent)
    if label.startswith('readiness'):
        pipeline.run_continuation=readiness_continuation
    before=environment()
    with inverse_runtime('fast'):
        result=pipeline.run_scene(parent/label,scene)
    verify_all(parent)
    write(parent/label/'runs'/scene/'worker_environment.json',dict(before=before,after=environment()))
    return result


def campaign(parent, test_log):
    if read(parent/'qualification.json')['status']!='PASS':
        raise ValueError('Physical readiness qualification required')
    prepare(parent,test_log)
    rows=[]; started=time.monotonic()
    jobs=[]
    for repetition in (0,1):
        for scene in ('death','split'):
            order=('baseline','readiness') if (repetition+(scene=='split'))%2==0 else ('readiness','baseline')
            jobs.extend((f'{arm}_{repetition}',scene) for arm in order)
    jobs.extend((f'{arm}_0','merge') for arm in ('baseline','readiness'))
    write(parent/'execution_status.json',dict(status='IN_PROGRESS',jobs=jobs))
    try:
        for label,scene in jobs:
            verify_all(parent)
            remaining=3600-(time.monotonic()-started)
            if remaining<=0:
                raise TimeoutError('Campaign wall ceiling')
            command=[sys.executable,'-u','-m','experiments.spd004_pipeline_readiness.run',
                'worker','--bundle',str(parent),'--arm',label,'--scene',scene]
            tick=time.monotonic(); before=environment()
            print('START',label,scene,flush=True)
            with (parent/f'{label}_{scene}.log').open('w') as stream:
                try:
                    process=subprocess.run(command,cwd=ROOT,env={**os.environ,'SDF_INVERSE_RUNTIME':'fast',
                        **{k:'1' for k in THREAD_KEYS}},stdout=stream,stderr=subprocess.STDOUT,timeout=min(1200,remaining))
                    code=process.returncode
                except subprocess.TimeoutExpired:
                    code=-999
            elapsed=time.monotonic()-tick
            path=parent/label/'runs'/scene/'result.json'
            result=read(path) if path.exists() else {}
            row=dict(arm=label,scene=scene,seconds=elapsed,returncode=code,
                status=result.get('status','NO_RESULT'),recovered=result.get('fresh_recovery_pass',False),
                skipped_continuation=result.get('continuation',{}).get('skipped_continuation',False),
                before=before,after=environment())
            rows.append(row);write(parent/'timings.json',rows);print('FINISH',json.dumps(row),flush=True)
            verify_all(parent)
            if code or not row['recovered'] or not result.get('sources_and_inputs_unchanged'):
                raise RuntimeError('Full-case failure or integrity regression')
        write(parent/'execution_status.json',dict(status='COMPLETE',seconds=time.monotonic()-started))
    except BaseException as exc:
        write(parent/'execution_status.json',dict(status='STOPPED',error=repr(exc),seconds=time.monotonic()-started))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('campaign','worker','qualify'))
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--test-log',type=Path)
    parser.add_argument('--arm');parser.add_argument('--scene');args=parser.parse_args()
    if args.mode=='campaign':campaign(args.bundle.resolve(),args.test_log.resolve())
    elif args.mode=='qualify':qualify(args.bundle.resolve())
    else:worker(args.bundle.resolve(),args.arm,args.scene)
