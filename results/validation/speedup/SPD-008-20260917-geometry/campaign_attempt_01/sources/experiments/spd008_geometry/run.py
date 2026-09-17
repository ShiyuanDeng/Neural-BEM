"""SPD-008 tests, gated qualification and sequential matched full workers."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from . import common as c
from . import qualify
from ordered_boundary.validation_cache import geometry_validation
from sdf_inverse.runtime import inverse_runtime, runtime_metadata
from sdf_inverse.work_accounting import collect_work
from gpr_bem_kress.execution import execution


def environment():
    return {**os.environ, 'PYTHONPATH':str(c.ROOT/'solvers'), 'SDF_INVERSE_RUNTIME':'compiled',
            **{key:'1' for key in c.previous.THREAD_KEYS}}


def tests(bundle):
    log = bundle/'tests.log'
    if log.exists():
        raise ValueError('Refusing to overwrite recorded regression log')
    frozen = c.sources()
    command = [sys.executable,'-m','pytest','-q',*c.TESTS]
    started = time.perf_counter()
    with log.open('w') as stream:
        process = subprocess.run(command,cwd=c.ROOT,env=environment(),stdout=stream,
                                 stderr=subprocess.STDOUT,timeout=300)
    result = dict(status='PASS' if process.returncode==0 and frozen==c.sources() else 'FAIL',
                  command=command,returncode=process.returncode,source_sha256=frozen,
                  seconds=time.perf_counter()-started,log_sha256=c.sha(log))
    c.write(bundle/'tests.json',result)
    print(log.read_text()[-4000:])
    if result['status']!='PASS':
        raise RuntimeError('Regression or source-integrity failure')


def prepare(bundle):
    tests = c.read(bundle/'tests.json')
    if (tests['status']!='PASS' or tests['source_sha256']!=c.sources()
            or tests['log_sha256']!=c.sha(bundle/'tests.log')):
        raise ValueError('Current-source passing regressions required')
    for phase in ('geometry','updates'):
        c.verify(bundle/phase)
        if c.read(bundle/phase/'qualification.json')['status']!='PASS':
            raise ValueError('Current-source qualification required')
    if not c.read(bundle/'updates/qualification.json')['full_campaign_released']:
        raise ValueError('Two-fold stencil speedup gate did not release full workers')
    out = bundle/'campaign'
    c.freeze(out,[bundle/'tests.json',bundle/'tests.log',bundle/'geometry/qualification.json',
                  bundle/'updates/qualification.json',c.PLAN])
    shutil.copyfile(c.PLAN,out/'approved_plan.md')
    for rep in range(2):
        for arm in c.ARMS:
            with inverse_runtime('compiled'):
                target = c.previous.make_arm(out,f'{arm}_{rep}',c.SCENES)
                contract = c.read(target/'contract.json')
                contract.update(experiment='SPD-008',inverse_runtime=runtime_metadata(),readiness=True,
                                geometry_validation=arm,approval='user yes to prepared SPD-008, 2026-09-17')
                c.write(target/'contract.json',contract)
                manifest = c.read(target/'manifest.json')
                manifest['input_sha256'] = {str(p.relative_to(target)):c.sha(p)
                    for p in target.rglob('*.json') if p.name!='manifest.json'}
                c.write(target/'manifest.json',manifest)
    manifest = c.read(out/'manifest.json')
    for arm in c.ARMS:
        for rep in range(2):
            for path in (out/f'{arm}_{rep}').rglob('*.json'):
                manifest['input_sha256'][str(path.relative_to(c.ROOT))] = c.sha(path)
    manifest.update(campaign_seconds=10800,worker_seconds=2400,maximum_concurrent_workers=1,
                    total_workers=16,blas_threads=1)
    c.write(out/'manifest.json',manifest)
    return out


def worker(out, label, scene):
    c.verify(out)
    mode = label.rsplit('_',1)[0]
    if mode not in c.ARMS:
        raise ValueError('Unknown geometry arm')
    fits = []
    before = c.previous.environment()
    with inverse_runtime('compiled'), geometry_validation(mode,on_fit=fits.append), \
            execution(kernels='real_bessel') as work, collect_work() as passive:
        result = c.pipeline.run_scene(out/label,scene)
    c.write(out/label/'runs'/scene/'geometry_validation.json',dict(mode=mode,fits=fits,
        before=before,after=c.previous.environment(),physical_work=passive.snapshot(),
        kernel_counts=work.counts,kernel_seconds=work.seconds))
    c.verify(out)
    return result


def campaign(bundle):
    out = prepare(bundle)
    jobs = []
    for rep in range(2):
        for index,scene in enumerate(c.SCENES):
            order = c.ARMS if (rep+index)%2==0 else tuple(reversed(c.ARMS))
            jobs.extend((f'{arm}_{rep}',scene) for arm in order)
    rows = []
    started = time.monotonic()
    c.write(out/'execution_status.json',dict(status='IN_PROGRESS',jobs=jobs))
    try:
        for label,scene in jobs:
            c.verify(out)
            remaining = 10800-(time.monotonic()-started)
            if remaining <= 0:
                raise TimeoutError('Campaign wall ceiling')
            command = [sys.executable,'-u','-m','experiments.spd008_geometry.run','worker',
                       '--bundle',str(out),'--arm',label,'--scene',scene]
            before = c.previous.environment()
            tick = time.monotonic()
            print('START',label,scene,flush=True)
            with (out/f'{label}_{scene}.log').open('w') as stream:
                try:
                    process = subprocess.run(command,cwd=c.ROOT,env=environment(),stdout=stream,
                        stderr=subprocess.STDOUT,timeout=min(2400,remaining))
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    code = -999
            path = out/label/'runs'/scene/'result.json'
            result = c.read(path) if path.exists() else {}
            row = dict(arm=label,scene=scene,seconds=time.monotonic()-tick,returncode=code,
                       recovered=result.get('fresh_recovery_pass',False),status=result.get('status','NO_RESULT'),
                       command=command,before=before,after=c.previous.environment())
            rows.append(row)
            c.write(out/'timings.json',rows)
            print('FINISH',label,scene,row['seconds'],row['recovered'],flush=True)
            c.verify(out)
            if code or not row['recovered'] or not result.get('sources_and_inputs_unchanged'):
                raise RuntimeError('Full-worker failure or integrity regression')
            # Stop on the first completed-pair trajectory mismatch.
            from .report import compare_pair
            compare_pair(out,scene,int(label.rsplit('_',1)[1]))
        c.write(out/'execution_status.json',dict(status='COMPLETE',seconds=time.monotonic()-started))
    except BaseException as exc:
        c.write(out/'execution_status.json',dict(status='STOPPED',error=repr(exc),seconds=time.monotonic()-started))
        raise


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode',choices=('tests','qualify','campaign','worker','report'))
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--arm'); parser.add_argument('--scene')
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    if args.mode=='tests': tests(bundle)
    elif args.mode=='qualify':
        validation = c.read(bundle/'tests.json')
        if validation['status']!='PASS' or validation['source_sha256']!=c.sources():
            raise ValueError('Current-source passing regressions required')
        qualify.geometry(bundle)
        qualify.updates(bundle)
    elif args.mode=='campaign': campaign(bundle)
    elif args.mode=='worker': worker(bundle,args.arm,args.scene)
    else:
        from .report import report
        report(bundle/'campaign')
