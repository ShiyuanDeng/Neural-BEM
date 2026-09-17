"""Bounded default-CLI smoke: fresh death/merge, with no runtime flag or override."""
import argparse
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time

import numpy as np

from experiments.spd004_pipeline_readiness import run as previous
from experiments.top025 import run as pipeline, summarize
from sdf_inverse.runtime import runtime_metadata

ROOT = pipeline.ROOT
SCENES = ('death', 'merge')
REFERENCE = ROOT/'results/validation/speedup/SPD-006-20260916-full-inverse/compiled_0'
read, write, sha = previous.read, previous.write, previous.sha


def run(bundle, test_log):
    if 'SDF_INVERSE_RUNTIME' in os.environ:
        raise ValueError('Run without SDF_INVERSE_RUNTIME to verify the actual default.')
    assert runtime_metadata()['profile'] == 'compiled'
    assert runtime_metadata()['continuation_readiness']
    bundle.mkdir(parents=True, exist_ok=False)
    target = previous.make_arm(bundle, 'default', SCENES)
    contract = read(target/'contract.json')
    contract.update(experiment='SPD-007', approval='user: yes to compiled + reciprocal + readiness default',
                    readiness=True, continuation_solve_cap=8020, continuation_fit_solve_cap=8012,
                    readiness_solve_cap=8, readiness_seconds=300, continuation_seconds=7500,
                    scene_outer_seconds=600, campaign_seconds=1200,
                    campaign_solve_cap=2*(4000+8020), maximum_workers=1,
                    budget_unit='full system, operator direction, reciprocal RHS batch, or compiled frequency batch')
    write(target/'contract.json', contract)
    manifest = read(target/'manifest.json')
    manifest['input_sha256'] = {str(p.relative_to(target)):sha(p)
        for p in target.rglob('*.json') if p.name != 'manifest.json'}
    write(target/'manifest.json', manifest)
    sources = {**pipeline.source_hashes(), str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))}
    tests = [*sorted((ROOT/'pytest/sdf_inverse').glob('test_spd00*.py')), ROOT/'pytest/sdf_inverse/test_top025.py']
    for path in tests:
        sources[str(path.relative_to(ROOT))] = sha(path)
    for name in sources:
        dest = bundle/'measured_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest)
    shutil.copyfile(test_log, bundle/'tests.log')
    write(bundle/'manifest.json', dict(source_sha256=sources, runtime=runtime_metadata(),
        environment=previous.environment(), original_starts=True, maximum_workers=1,
        purpose='Default dispatch and quality validation; no matched wall-time speedup claim',
        reference_sha256={str(p.relative_to(ROOT)):sha(p) for scene in SCENES
            for p in (REFERENCE/'runs'/scene/'F/metrics.json', REFERENCE/'runs'/scene/'topology/terminal.json')}))
    def verify():
        assert all(sha(ROOT/name) == digest for name, digest in sources.items())
        pipeline.verify(target)
    rows = []
    started = time.monotonic()
    for scene in SCENES:
        verify()
        command = [sys.executable, '-u', '-m', 'experiments.top025.run',
                   'scene', '--bundle', str(target), '--scene', scene]
        env = {**os.environ, **{k:'1' for k in previous.THREAD_KEYS}}
        tick = time.monotonic()
        with (bundle/(scene+'.log')).open('w') as stream:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                stderr=subprocess.STDOUT, timeout=min(600, 1200-(tick-started)))
        assert process.returncode == 0, scene
        verify()
        folder = target/'runs'/scene
        result = read(folder/'result.json')
        assert result['sources_and_inputs_unchanged'] and result['fresh_recovery_pass'], result
        assert result['continuation']['skipped_continuation'] == (scene == 'death')
        for work in (result['topology_work'], result['continuation']['work']):
            summarize.verify_work(work)
        train = read(target/'inputs'/scene/'training_observations.json')
        original = read(target/'inputs'/scene/'observations.json')
        summarize.old.verify_arm(folder/'F', result['continuation'], train, original, 'F')
        assert summarize.verify_readiness(folder/'F', result['continuation'], train, original) == (scene == 'death')
        actual = read(folder/'F/metrics.json')
        expected = read(REFERENCE/'runs'/scene/'F/metrics.json')
        a, b = [pipeline.p.driver.deserialize_state(v['final_state']) for v in (actual, expected)]
        assert a.component_ids == b.component_ids
        difference = float(np.max(abs(a.parameter_vector()-b.parameter_vector())))
        assert difference <= 1e-10
        steps = [s['terminal']['accepted_steps'] for s in actual['stages']]
        assert steps == [s['terminal']['accepted_steps'] for s in expected['stages']]
        events = [e['kind'] for e in read(folder/'topology/terminal.json')['events']]
        assert events == [e['kind'] for e in read(REFERENCE/'runs'/scene/'topology/terminal.json')['events']]
        rows.append(dict(scene=scene, seconds=time.monotonic()-tick, command=command,
            recovered=True, skipped=result['continuation']['skipped_continuation'],
            coefficient_difference_m=difference, accepted_steps=steps, events=events,
            readiness_physical_solves=result['continuation']['screening_work']['total_attempted'],
            compiled_batches=sum(result['continuation']['work']['compiled_batches_completed'].values()),
            reciprocal_batches=sum(result['continuation']['work']['reciprocal_batches_completed'].values())))
        write(bundle/'validation.json', dict(status='IN_PROGRESS', rows=rows))
        print(scene, rows[-1]['seconds'], 'PASS', flush=True)
    write(bundle/'validation.json', dict(status='PASS', rows=rows, seconds=time.monotonic()-started,
        runtime=runtime_metadata(), no_runtime_flag=True, no_runtime_environment_override=True,
        original_starts=True, source_and_input_hashes_verified=True))
    write(bundle/'artifact_manifest.json', {str(p.relative_to(bundle)):sha(p)
        for p in sorted(bundle.rglob('*')) if p.is_file() and p.name != 'artifact_manifest.json'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--test-log', type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle.resolve(), args.test_log.resolve())
