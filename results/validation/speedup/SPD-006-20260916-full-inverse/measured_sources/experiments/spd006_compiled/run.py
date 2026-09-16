"""Source-frozen matched full inverse workers for SPD-006."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from .qualify import sources, ROOT, read, write, sha, previous
from sdf_inverse.runtime import inverse_runtime, runtime_metadata
from sdf_inverse.work_accounting import collect_work
from gpr_bem_kress.execution import execution

pipeline = previous.pipeline
SCENES = ('death', 'merge', 'central-ellipse-star', 'far-two-stars')
ARMS = ('reciprocal', 'compiled')
PLAN = ROOT/'docs/iterations/speedup/iteration_05/03_plan.md'
ORIGINAL_COMBINE = previous.combine_work


def combine_work(parts, elapsed):
    result = ORIGINAL_COMBINE(parts, elapsed)
    for prefix in ('reciprocal_batches_', 'compiled_batches_', 'compiled_per_frequency_'):
        for event in ('attempted', 'completed', 'failed'):
            key = prefix+event; counts = Counter()
            for part in parts: counts.update(part.get(key, {}))
            result[key] = dict(counts)
    result['budget_unit'] = 'one full system, operator direction, reciprocal RHS batch, or compiled frequency batch'
    return result


def verify(bundle):
    manifest = read(bundle/'manifest.json')
    if sources() != manifest['source_sha256']: raise RuntimeError('Measured source changed')
    for name, digest in manifest['input_sha256'].items():
        if sha(bundle/name) != digest: raise RuntimeError('Frozen input changed: '+name)


def prepare(bundle, qualification, test_log):
    qualified = read(qualification/'qualification.json')
    if qualified['status']!='PASS' or qualified['source_sha256']!=sources():
        raise ValueError('Current-source compiled qualification required')
    bundle.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(PLAN, bundle/'approved_plan.md'); shutil.copyfile(test_log, bundle/'tests.log')
    shutil.copytree(qualification, bundle/'qualification')
    for rep in range(2):
        for arm in ARMS:
            with inverse_runtime(arm):
                target = previous.make_arm(bundle, f'{arm}_{rep}', SCENES)
                contract = read(target/'contract.json')
                contract.update(experiment='SPD-006', inverse_runtime=runtime_metadata(), readiness=True,
                                approval='user: go after compiled scattering integration review')
                write(target/'contract.json', contract)
                manifest = read(target/'manifest.json')
                manifest['input_sha256'] = {str(x.relative_to(target)):sha(x)
                    for x in target.rglob('*.json') if x.name!='manifest.json'}
                write(target/'manifest.json', manifest)
    frozen = sources()
    for name in frozen:
        target = bundle/'measured_sources'/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    write(bundle/'manifest.json', dict(source_sha256=frozen,
        input_sha256={str(x.relative_to(bundle)):sha(x) for x in bundle.rglob('*')
            if x.is_file() and 'measured_sources' not in x.parts},
        git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        environment=previous.environment(), prepared_utc=datetime.now(timezone.utc).isoformat(),
        maximum_workers=16, campaign_seconds=10800, worker_seconds=2400))


def worker(bundle, label, scene):
    verify(bundle)
    previous.combine_work = combine_work
    pipeline.run_continuation = previous.readiness_continuation
    before = previous.environment()
    with inverse_runtime(label.rsplit('_',1)[0]), execution(kernels='real_bessel') as performance, collect_work() as passive:
        result = pipeline.run_scene(bundle/label, scene)
    write(bundle/label/'runs'/scene/'performance.json', dict(before=before, after=previous.environment(),
        kernel_counts=performance.counts, kernel_seconds=performance.seconds, outer_work=passive.snapshot()))
    verify(bundle)
    return result


def check_pair(bundle, scene, rep):
    results = []
    for arm in ARMS:
        path = bundle/f'{arm}_{rep}'/'runs'/scene/'result.json'
        if not path.exists(): return
        results.append(read(path))
    reference, candidate = results
    if reference['fresh_recovery_pass'] and not candidate['fresh_recovery_pass']:
        raise RuntimeError('Compiled arm lost reference recovery: '+scene)
    for arm, result in zip(ARMS, results):
        terminal = result.get('continuation',{}).get('schedule',{})
        reason = terminal.get('reason',result.get('reason'))
        if reason in ('IMPLEMENTATION_ERROR','NUMERICAL_FAILURE','UNRESOLVED_DERIVATIVE'):
            raise RuntimeError('Numerical/implementation failure: '+arm+' '+scene+' '+str(reason))


def campaign(bundle, qualification, test_log):
    prepare(bundle, qualification, test_log)
    jobs = []
    for rep in range(2):
        for index, scene in enumerate(SCENES):
            order = ARMS if (rep+index)%2==0 else tuple(reversed(ARMS))
            jobs.extend((f'{arm}_{rep}', scene, rep) for arm in order)
    rows = []; started = time.monotonic()
    write(bundle/'execution_status.json', dict(status='IN_PROGRESS', jobs=jobs))
    try:
        for label, scene, rep in jobs:
            verify(bundle); remaining = 10800-(time.monotonic()-started)
            if remaining<=0: raise TimeoutError('Campaign wall limit')
            command = [sys.executable,'-u','-m','experiments.spd006_compiled.run','worker',
                       '--bundle',str(bundle),'--arm',label,'--scene',scene]
            before = previous.environment(); tick = time.monotonic()
            print('START',label,scene,flush=True)
            with (bundle/f'{label}_{scene}.log').open('w') as stream:
                try:
                    process = subprocess.run(command,cwd=ROOT,env={**os.environ,
                        'SDF_INVERSE_RUNTIME':label.rsplit('_',1)[0], **{k:'1' for k in previous.THREAD_KEYS}},
                        stdout=stream,stderr=subprocess.STDOUT,timeout=min(2400,remaining))
                    code = process.returncode
                except subprocess.TimeoutExpired: code = -999
            path = bundle/label/'runs'/scene/'result.json'; result = read(path) if path.exists() else {}
            row = dict(arm=label, scene=scene, seconds=time.monotonic()-tick, returncode=code,
                status=result.get('status','NO_RESULT'), recovered=result.get('fresh_recovery_pass',False),
                skipped=result.get('continuation',{}).get('skipped_continuation',False),
                before=before,after=previous.environment())
            rows.append(row); write(bundle/'timings.json',rows)
            print('FINISH',json.dumps({k:v for k,v in row.items() if k not in ('before','after')}),flush=True)
            verify(bundle)
            if code or not result.get('sources_and_inputs_unchanged'):
                raise RuntimeError('Worker or integrity failure')
            check_pair(bundle,scene,rep)
        write(bundle/'execution_status.json',dict(status='COMPLETE',seconds=time.monotonic()-started))
    except BaseException as exc:
        write(bundle/'execution_status.json',dict(status='STOPPED',error=repr(exc),seconds=time.monotonic()-started))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=('campaign','worker'))
    parser.add_argument('--bundle',type=Path,required=True); parser.add_argument('--qualification',type=Path)
    parser.add_argument('--test-log',type=Path); parser.add_argument('--arm'); parser.add_argument('--scene')
    args=parser.parse_args()
    if args.mode=='campaign': campaign(args.bundle.resolve(),args.qualification.resolve(),args.test_log.resolve())
    else: worker(args.bundle.resolve(),args.arm,args.scene)
