"""Sequential, source-frozen full inverse comparison for SPD-005."""
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
from .qualify import sources, ROOT, read, write, sha, HISTORY
from experiments.spd004_pipeline_readiness import run as previous
from sdf_inverse.runtime import inverse_runtime, runtime_metadata
from sdf_inverse.work_accounting import collect_work
from gpr_bem_kress.execution import execution

pipeline = previous.pipeline
SCENES = ('death', 'split', 'merge')
ARMS = ('operator', 'reciprocal', 'combined')
PLAN = ROOT/'docs/iterations/speedup/iteration_04/03_plan.md'
ORIGINAL_COMBINE = previous.combine_work


def profile(arm):
    return 'fast' if arm.split('_')[0] == 'operator' else 'reciprocal'


def combine_work(parts, elapsed):
    result = ORIGINAL_COMBINE(parts, elapsed)
    for name in ('reciprocal_batches_attempted', 'reciprocal_batches_completed', 'reciprocal_batches_failed'):
        counts = Counter()
        for part in parts:
            counts.update(part.get(name, {}))
        result[name] = dict(counts)
    result['budget_unit'] = 'one full system, operator direction/tangent, or reciprocal RHS batch'
    return result


def verify(bundle):
    manifest = read(bundle/'manifest.json')
    if sources() != manifest['source_sha256']:
        raise RuntimeError('Measured source changed')
    for name, digest in manifest['input_sha256'].items():
        if sha(bundle/name) != digest:
            raise RuntimeError('Frozen campaign input changed: '+name)


def prepare(bundle, qualification, test_log):
    qualified = read(qualification/'qualification.json')
    if qualified['status'] != 'PASS' or qualified['source_sha256'] != sources():
        raise ValueError('Current-source reciprocal qualification required')
    bundle.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(PLAN, bundle/'approved_plan.md')
    shutil.copyfile(test_log, bundle/'tests.log')
    shutil.copytree(qualification, bundle/'qualification')
    for rep in range(2):
        for arm in ARMS:
            label = f'{arm}_{rep}'
            with inverse_runtime(profile(label)):
                target = previous.make_arm(bundle, label, SCENES)
                contract = read(target/'contract.json')
                contract.update(experiment='SPD-005', inverse_runtime=runtime_metadata(),
                    approval='user: then go; reciprocal integration and matched full inverse',
                    readiness=arm == 'combined')
                write(target/'contract.json', contract)
                manifest = read(target/'manifest.json')
                manifest['input_sha256'] = {str(x.relative_to(target)):sha(x)
                    for x in target.rglob('*.json') if x.name != 'manifest.json'}
                write(target/'manifest.json', manifest)
    frozen = sources()
    for name in frozen:
        target = bundle/'measured_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    write(bundle/'manifest.json', dict(source_sha256=frozen,
        input_sha256={str(x.relative_to(bundle)):sha(x) for x in bundle.rglob('*')
            if x.is_file() and 'measured_sources' not in x.parts},
        git_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        environment=previous.environment(), prepared_utc=datetime.now(timezone.utc).isoformat(),
        maximum_workers=18, campaign_seconds=7200, worker_seconds=1200))


def worker(bundle, arm, scene):
    verify(bundle)
    if arm.startswith('combined'):
        pipeline.run_continuation = previous.readiness_continuation
    before = previous.environment()
    with inverse_runtime(profile(arm)), execution(kernels='real_bessel') as performance, collect_work() as passive:
        result = pipeline.run_scene(bundle/arm, scene)
    write(bundle/arm/'runs'/scene/'performance.json', dict(before=before, after=previous.environment(),
        kernel_counts=performance.counts, kernel_seconds=performance.seconds,
        outer_work=passive.snapshot(),
        note='Topology owns a nested passive ledger; its counts are in topology/terminal.json.'))
    verify(bundle)
    return result


def campaign(bundle, qualification, test_log):
    prepare(bundle, qualification, test_log)
    jobs = []
    for rep in range(2):
        for index, scene in enumerate(SCENES):
            order = ARMS[index:]+ARMS[:index]
            if rep:
                order = tuple(reversed(order))
            jobs.extend((f'{arm}_{rep}', scene) for arm in order)
    rows = []
    started = time.monotonic()
    write(bundle/'execution_status.json', dict(status='IN_PROGRESS', jobs=jobs))
    try:
        for arm, scene in jobs:
            verify(bundle)
            remaining = 7200-(time.monotonic()-started)
            if remaining <= 0:
                raise TimeoutError('Campaign wall limit')
            command = [sys.executable, '-u', '-m', 'experiments.spd005_reciprocal.run',
                       'worker', '--bundle', str(bundle), '--arm', arm, '--scene', scene]
            before = previous.environment()
            tick = time.monotonic()
            print('START', arm, scene, flush=True)
            with (bundle/f'{arm}_{scene}.log').open('w') as stream:
                try:
                    process = subprocess.run(command, cwd=ROOT, env={**os.environ,
                        'SDF_INVERSE_RUNTIME':profile(arm), **{k:'1' for k in previous.THREAD_KEYS}},
                        stdout=stream, stderr=subprocess.STDOUT, timeout=min(1200, remaining))
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    code = -999
            path = bundle/arm/'runs'/scene/'result.json'
            result = read(path) if path.exists() else {}
            row = dict(arm=arm, scene=scene, seconds=time.monotonic()-tick, returncode=code,
                status=result.get('status', 'NO_RESULT'), recovered=result.get('fresh_recovery_pass', False),
                skipped=result.get('continuation', {}).get('skipped_continuation', False),
                before=before, after=previous.environment())
            rows.append(row)
            write(bundle/'timings.json', rows)
            print('FINISH', json.dumps({k:v for k,v in row.items() if k not in ('before','after')}), flush=True)
            verify(bundle)
            if code or not row['recovered'] or not result.get('sources_and_inputs_unchanged'):
                raise RuntimeError('Full-case recovery or integrity failure')
        write(bundle/'execution_status.json', dict(status='COMPLETE', seconds=time.monotonic()-started))
    except BaseException as exc:
        write(bundle/'execution_status.json', dict(status='STOPPED', error=repr(exc), seconds=time.monotonic()-started))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('campaign', 'worker'))
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--test-log', type=Path)
    parser.add_argument('--arm')
    parser.add_argument('--scene')
    args = parser.parse_args()
    if args.mode == 'campaign':
        campaign(args.bundle.resolve(), args.qualification.resolve(), args.test_log.resolve())
    else:
        worker(args.bundle.resolve(), args.arm, args.scene)
