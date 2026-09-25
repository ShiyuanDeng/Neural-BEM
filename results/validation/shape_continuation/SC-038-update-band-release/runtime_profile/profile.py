"""Time the two saved C/M=19 updates without changing numerical decisions.

Run from the repository root with EMNerf, PYTHONPATH=solvers:., and one BLAS
thread. Instrumentation is process-local; production modules are not edited.
"""
from dataclasses import replace
from pathlib import Path
from time import perf_counter
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation import forward, lm_backend as lm

OUT = Path(__file__).resolve().parent
HERE = OUT.parent
spec = importlib.util.spec_from_file_location('sc038_runtime_base', HERE / 'run.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
sc, ast, ac = base.sc, base.ast, base.ac
source_history = HERE / 'runs/circle_to_c/release_m/release_3_history.json'
saved = sc.read(source_history)
stages, config, _ = base.schedules('circle_to_c', 'release_m')
stage = replace(stages[-1], iterations=2)
curve = ast.curve_from(saved['history'][0]['coefficients'])
sources = base.hashes()
original = sc.read(HERE / 'manifest.json')['sources']
changed = [p for p, digest in original.items() if sc.digest(sc.ROOT / p) != digest]
assert not changed, changed
manifest = dict(source_history=str(source_history.relative_to(sc.ROOT)),
                history_hash=sc.digest(source_history), sources=sources,
                script_hash=sc.digest(Path(__file__)),
                head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                threads={k: os.environ.get(k) for k in
                         ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
                scope='Two saved C/M=19 updates, 19 frequencies, 512/1024 nodes',
                timing_note='Single worker; ambient machine load is uncontrolled.')
sc.write(OUT / 'manifest.json', manifest)
events, active_work = [], None
started = perf_counter()


def record(kind, tick, work=None, **details):
    event = dict(kind=kind, start=tick-started, end=perf_counter()-started,
                 seconds=perf_counter()-tick, **details)
    if work is not None:
        event['work'] = work.summary()
    events.append(event)
    print(json.dumps({k: v for k, v in event.items() if k != 'work'}), flush=True)


original_predict = lm.Objective._predict
original_jacobian = lm.Objective.jacobian


def predict(self, curve, nodes, category, keep):
    global active_work
    work = forward.Work(max_forwards=1000, max_seconds=1200)
    active_work = work
    tick = perf_counter()
    try:
        return original_predict(self, curve, nodes, category, keep)
    finally:
        active_work = None
        record(category, tick, work, nodes=nodes)


def jacobian(self, evaluation, update, space):
    global active_work
    work = forward.Work(max_forwards=1000, max_seconds=1200)
    active_work = work
    tick = perf_counter()
    try:
        return original_jacobian(self, evaluation, update, space)
    finally:
        active_work = None
        record('jacobian', tick, work, nodes=stage.nodes)


lm.Objective._predict = predict
lm.Objective.jacobian = jacobian
lm.solve = lambda *args, **kwargs: forward.solve(*args, **kwargs, work=active_work)
lm.shape_jacobian = lambda *args, **kwargs: forward.shape_jacobian(*args, **kwargs, work=active_work)
update = base.ProjectedUpdate(sc.LENGTH)
for name in ('prepare', 'trial', 'metric'):
    original_method = getattr(update, name)

    def timed_method(*args, _method=original_method, _name=name, **kwargs):
        tick = perf_counter()
        try:
            return _method(*args, **kwargs)
        finally:
            record('geometry_' + _name, tick)

    setattr(update, name, timed_method)

original_small_solve = np.linalg.solve


def small_solve(a, b):
    tick = perf_counter()
    try:
        return original_small_solve(a, b)
    finally:
        record('numpy_linear_solve', tick, dimension=a.shape[0])


np.linalg.solve = small_solve
ledger = lm.Ledger(cap=500, seconds=1200)
with geometry_validation('cache'):
    ledger.begin_stage(stage.label, stage.quota)
    result = lm.fit_stage(curve, stage, ac.contrast(), update, config, ledger)
elapsed = perf_counter()-started
expected = ast.curve_from(saved['history'][2]['coefficients'])
error = float(np.max(np.abs(result.curve.coefficients-expected.coefficients)))
passed = (result.accepted_steps == 2 and len(result.trials) == 2
          and error < 1e-12 and sources == base.hashes()
          and sc.digest(source_history) == manifest['history_hash'])
boundaries = [e['end'] for e in events if e['kind'] == 'jacobian']
segments = []
for i, end in enumerate(boundaries):
    begin = 0.0 if i == 0 else boundaries[i-1]
    selected = [e for e in events if e['start'] >= begin and e['end'] <= end]
    seconds_by_phase, seconds_by_kernel = {}, {}
    for event in selected:
        kind = event['kind']
        seconds_by_phase[kind] = seconds_by_phase.get(kind, 0.) + event['seconds']
        for name, seconds in event.get('work', {}).get('seconds', {}).items():
            seconds_by_kernel[name] = seconds_by_kernel.get(name, 0.) + seconds
    segments.append(dict(label='startup' if i == 0 else f'update_{i}',
                         seconds=end-begin, phase_seconds=seconds_by_phase,
                         kernel_seconds=seconds_by_kernel))
sc.write(OUT / 'result.json', dict(passed=passed, coefficient_max_abs_error=error,
         accepted_steps=result.accepted_steps, trial_count=len(result.trials),
         seconds=elapsed, outcome=result.outcome, stop=result.stop_reason,
         work=ledger.snapshot(), geometry_work=update.counts,
         segments=segments, events=events))
print(json.dumps(dict(passed=passed, seconds=elapsed, segments=segments)), flush=True)
assert passed, 'Replay changed the saved endpoint or inputs.'
