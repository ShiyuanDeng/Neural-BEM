"""Post-campaign CPU profile of one real, training-only continuation stage.

Profiler timings diagnose call stacks, not matched speedups. This script has
its own source/input record and is never imported by the timed worker.
"""
import argparse
import cProfile
from dataclasses import asdict
import io
from pathlib import Path
import pstats
import shutil
import time
import numpy as np
from experiments.spd005_reciprocal import run as r
from sdf_inverse.runtime import inverse_runtime, runtime_metadata
from sdf_inverse.work_accounting import collect_work
from gpr_bem_kress.execution import execution


def profile(bundle):
    r.verify(bundle)
    if r.read(bundle/'execution_status.json')['status'] != 'COMPLETE':
        raise ValueError('Profiling must follow all matched timed workers')
    output = bundle/'remaining_cost_profile'
    output.mkdir(exist_ok=False)
    p, m = r.previous.p, r.previous.m
    original = bundle/'reciprocal_0/runs/death'
    inputs = [original/'handoff.json', original/'F/stage_1/optimizer.json',
              bundle/'reciprocal_0/inputs/death/training_observations.json']
    handoff, settings, observed = [r.read(path) for path in inputs]
    state = p.driver.deserialize_state(handoff['state'])
    observations = np.array(observed['observed_real'])+1j*np.array(observed['observed_imag'])
    data = p.training_data(p.TRAIN[:1], observations[:,:1])
    optimizer = m.rt.ParameterFDConfig(**settings['config'])
    solve = p.driver.baseline.iteration01_solve_config()
    ledger = m.Ledger(cap=400, seconds=120)
    ledger.begin_stage(1, 400)
    frozen = r.sources()
    this_file = Path(__file__).resolve()
    shutil.copyfile(this_file, output/'profile_remaining.py')
    r.write(output/'manifest.json', dict(source_sha256=frozen,
        profiler_sha256=r.sha(this_file), input_sha256={str(x.relative_to(bundle)):r.sha(x) for x in inputs},
        environment=r.previous.environment(), scope='one real stage; CPU profiling overhead; not a speedup timing'))
    profiler = cProfile.Profile()
    tick = time.perf_counter()
    with inverse_runtime('reciprocal'), execution(kernels='real_bessel') as work, collect_work() as passive:
        with ledger.instrument():
            profiler.enable()
            try:
                _, terminal = m.fit_stage(state, data, (256,512), solve, optimizer, .008, ledger, output/'stage')
            finally:
                profiler.disable()
        metadata = runtime_metadata()
    profiler.dump_stats(str(output/'profile.pstats'))
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats('cumulative')
    stats.print_stats(60)
    (output/'profile.txt').write_text(stream.getvalue())
    functions = [dict(file=key[0], line=key[1], function=key[2], primitive_calls=value[0],
                      calls=value[1], self_seconds=value[2], cumulative_seconds=value[3])
                 for key,value in stats.stats.items()]
    functions.sort(key=lambda x:x['cumulative_seconds'], reverse=True)
    r.write(output/'summary.json', dict(seconds_with_profiler=time.perf_counter()-tick,
        status=terminal['stage_outcome'], accepted_steps=terminal['accepted_steps'],
        effective_training_exposure=terminal['effective_training_exposure'], work=ledger.snapshot(),
        passive_work=passive.snapshot(), kernel_seconds=work.seconds, functions=functions,
        runtime=metadata, optimizer=asdict(optimizer)))
    r.verify(bundle)
    if (terminal['stage_outcome'] != 'NORMAL_OPTIMIZER_RETURN'
            or not terminal['effective_training_exposure'] or terminal['accepted_steps'] != 0):
        raise ValueError('Profile did not reproduce the intended terminal stage')
    print(stream.getvalue())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    profile(parser.parse_args().bundle.resolve())
