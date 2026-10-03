"""Bounded runtime investigation; does not change or qualify the public default.

Run from repository root with PYTHONPATH=solvers:. and one BLAS thread.
Alternating sequential CPU/GPU certificate trials, shared CUDA preparation,
three repetitions, four saved states, three deterministic step sizes.
"""
import cProfile
import hashlib
import io
import os
from pathlib import Path
import platform
import pstats
import subprocess
import time

import numpy as np
import torch

from bem_inverse.batched import BatchedCertifiedUpdate
from bem_inverse.device_certified import DeviceCertifiedUpdate
from bem_inverse.io import curve_from, read, write
from bem_inverse.continuation.updates import UpdateRefused
from bem_inverse.n_update import curve_certificate


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'results/validation/cleaned_interfaces'
SELECTION = (
    ('core__wrong_circle', 'warmup_025_damped'),
    ('core__peanut', 'fixed_M37'),
    ('core__hook', 'fixed_M37'),
    ('core__kite', 'fixed_M37'),
)


def timed(function):
    torch.cuda.synchronize()
    started = time.perf_counter()
    value = function()
    torch.cuda.synchronize()
    return value, time.perf_counter() - started


def trial(update, space, step):
    before = update.counts['certificate_seconds']
    try:
        curve, _ = update.trial(space, step)
        result = dict(status='accepted', coefficients=curve.coefficients)
    except (UpdateRefused, ValueError) as exc:
        result = dict(status='refused', reason=getattr(exc, 'reason', str(exc)))
    return dict(result, records=list(update.records),
                certificate_seconds=update.counts['certificate_seconds'] - before)


def main():
    assert torch.cuda.is_available(), 'This investigation requires CUDA; no silent CPU fallback.'
    source_paths = sorted((ROOT / 'solvers/bem_inverse').rglob('*.py')) + [Path(__file__).resolve()]
    provenance = dict(
        branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        python=platform.python_version(), numpy=np.__version__, torch=torch.__version__,
        gpu=torch.cuda.get_device_name(0), load_average_start=os.getloadavg(),
        threads={key: os.environ.get(key) for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
        source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
    )
    archived = {}
    for arm in ('NU-006', 'NU-005', 'NU-004-MS', 'NU-004-MN', 'CI-001'):
        cases = []
        for path in sorted((BASE / arm / 'runs').glob('core__*/result.json')):
            result = read(path)
            cases.append(dict(case=path.parent.name, wall=result['total_seconds'],
                              geometry=result['geometry_work'], recovered=result['recovered']))
        archived[arm] = dict(cases=cases, wall=sum(r['wall'] for r in cases))
    states = []
    for case, stage in SELECTION:
        path = BASE / 'NU-006/runs' / case / 'accepted.json'
        state = [r for r in read(path)['states'] if r['stage'] == stage][-1]
        states.append((case, stage, curve_from(state['curve']), state['M']))
        provenance.setdefault('input_sha256', {})[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()

    # Warm CUDA, preparation and certificate kernels outside the timed replay.
    for cls in (BatchedCertifiedUpdate, DeviceCertifiedUpdate):
        update = cls(.05, device='cuda')
        _, _, curve, modes = states[-1]
        space = update.prepare(curve, modes, curve.band)
        step = np.random.default_rng(5).normal(size=len(space.orders))
        step *= 6e-3 / update.measure(space, step)['maximum_normal_m']
        trial(update, space, step)
    rows = []
    for case, stage, curve, modes in states:
        for repeat in range(3):
            updates = dict(host=BatchedCertifiedUpdate(.05, device='cuda'),
                           device=DeviceCertifiedUpdate(.05, device='cuda'))
            spaces, preparation = {}, {}
            order = ('host', 'device') if repeat % 2 == 0 else ('device', 'host')
            for name in order:
                spaces[name], preparation[name] = timed(lambda: updates[name].prepare(curve, modes, curve.band))
            rng = np.random.default_rng(5)
            for size in (1e-7, 6e-3, 1.8e-2):
                step = rng.normal(size=len(spaces['host'].orders))
                step *= size / updates['host'].measure(spaces['host'], step)['maximum_normal_m']
                outcomes = {}
                for name in order:
                    value, seconds = timed(lambda: trial(updates[name], spaces[name], step))
                    outcomes[name] = dict(value, trial_seconds=seconds)
                h, d = outcomes['host'], outcomes['device']
                same = h['status'] == d['status'] and (h.get('reason') == d.get('reason')
                    if h['status'] == 'refused' else np.array_equal(h['coefficients'], d['coefficients']))
                same_tiers = [(r['role'], r['tier']) for r in h['records']] == [(r['role'], r['tier']) for r in d['records']]
                bounds = []
                for x, y in zip(h['records'], d['records']):
                    for key in ('increment_bound', 'full_bound'):
                        if key in x and key in y:
                            bounds.append(dict(role=x['role'], key=key, host=x[key], device=y[key],
                                absolute=abs(x[key]-y[key]), scaled=abs(x[key]-y[key])/max(1., abs(x[key])),
                                same_side=(x[key] < 1) == (y[key] < 1), margin=min(abs(x[key]-1), abs(y[key]-1))))
                for value in outcomes.values():
                    value.pop('coefficients', None)
                rows.append(dict(case=case, stage=stage, K=curve.band, M=modes, repeat=repeat, size_m=size,
                                 order=order, preparation_seconds=preparation, same_decision=same,
                                 same_tiers=same_tiers, bounds=bounds, outcomes=outcomes))
            print(case, stage, repeat, 'trial seconds',
                  {name: round(sum(r['outcomes'][name]['trial_seconds'] for r in rows[-3:]), 4) for name in order}, flush=True)
        assert all(u.counts.get('prepare_fallbacks', 0) == 0 and u.counts.get('device_certificate_fallbacks', 0) == 0
                   for u in updates.values())
    bounds = [b for row in rows for b in row['bounds']]
    summary = dict(paired_trials=len(rows), all_same_decisions=all(r['same_decision'] for r in rows),
        all_same_tiers=all(r['same_tiers'] for r in rows), all_bounds_same_side=all(b['same_side'] for b in bounds),
        max_scaled_bound_difference=max(b['scaled'] for b in bounds), min_threshold_margin=min(b['margin'] for b in bounds),
        certificate_seconds={name: sum(r['outcomes'][name]['certificate_seconds'] for r in rows) for name in ('host', 'device')},
        trial_seconds={name: sum(r['outcomes'][name]['trial_seconds'] for r in rows) for name in ('host', 'device')})
    profiler = cProfile.Profile()
    profiler.runcall(curve_certificate, states[-1][2], 64)
    report = io.StringIO()
    pstats.Stats(profiler, stream=report).strip_dirs().sort_stats('cumulative').print_stats(25)
    (OUT / 'host-certificate-profile.txt').write_text(report.getvalue())
    provenance['load_average_end'] = os.getloadavg()
    write(OUT / 'review.json', dict(protocol=__doc__, provenance=provenance, archived=archived,
                                  summary=summary, rows=rows))
    print(summary, flush=True)


if __name__ == '__main__':
    main()
