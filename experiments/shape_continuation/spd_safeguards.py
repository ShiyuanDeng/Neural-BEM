"""SC-034: the SPD comparison fitter with the legacy single-object controls restored.

SC-030's SPD arm ran the topology LM at K17 from the first frequency, without
the controls the legacy single-object inverse used. This driver reruns that
fitter on the six SC cases, changing only:

* ``L``  - a harmonic ladder, Cartesian K = 4/6/8/10 (radial orders 3/5/7/9,
           the hybrid's M), zero-padded between stages;
* ``S``  - ``StepSafeguards()`` at K17: m**4 step ridge, damping floor 1e-6,
           2 mm normal-move trust region, Armijo 1e-4;
* ``LS`` - both (the candidate SPD reference).

Everything else is SC-030's `spd_fit`: data, start, schedule and quotas,
512/1024 nodes, compiled/real-Bessel/certified runtime, acceptance checks and
budgets. Truth is loaded only after fitting. Run with the EMNerf interpreter,
PYTHONPATH=solvers:. and one BLAS thread.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np

from ordered_boundary.validation_cache import geometry_validation
from gpr_bem_kress.execution import execution
from sdf_inverse.runtime import inverse_runtime, runtime_metadata
from sdf_inverse.explicit_fourier import circle_cartesian_fourier_state
from sdf_inverse.radial_topology import MultiRadialFourierState, StepSafeguards
from sdf_inverse.topology_controller import zero_padded_component
from . import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from . import spd008_comparison as base
from .forward import solve
from .lm_backend import NORMAL_RETURN, STAGE_QUOTA

CASES = ast.CASES
LADDER, FULL = (4, 6, 8, 10), (17, 17, 17, 17)
ARMS = dict(L=(LADDER, False), S=(FULL, True), LS=(LADDER, True))
NODES, CAP, SECONDS = base.NODES, base.CAP, base.SECONDS
WORKERS, CAMPAIGN_SECONDS, OUTER_SECONDS = 9, 3 * 3600., 4050.
# The SPD polar-angle chart holds only curves star-shaped about their centre.
STAR_SHAPED = dict(wrong_circle=True, circle_to_star=True, circle_to_c=False, kite=True, peanut=True, hook=False)
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_15/03_plan.md'
TEST = sc.ROOT / 'pytest/sdf_inverse/test_step_safeguards.py'
REPLAY = sc.ROOT / 'results/validation/shape_continuation/SC-030-spd008-comparison/runs/repeat_0/wrong_circle/spd008'


def sources():
    return {**sc.source_hashes(), str(TEST.relative_to(sc.ROOT)): sc.digest(TEST)}


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = {str(p.relative_to(sc.ROOT)): sc.digest(p) for case in CASES for p in
              (ast.source_folder(case) / name for name in ('observations.json', 'truth.json', 'oracle_check.json'))}
    assert all(sc.read(ast.source_folder(c) / 'oracle_check.json')['passed'] for c in CASES)
    shutil.copyfile(PLAN, output / 'approved_plan.md')
    sc.write(output / 'manifest.json', dict(experiment='SC-034', source_sha256=sources(), input_sha256=inputs,
        plan_sha256=sc.digest(PLAN), cases=CASES, arms={k: dict(bands=v[0], safeguards=v[1]) for k, v in ARMS.items()},
        safeguards=asdict(StepSafeguards()), nodes=NODES, per_fit_cap=CAP, per_fit_seconds=SECONDS,
        workers=WORKERS, campaign_seconds=CAMPAIGN_SECONDS, star_shaped_truth=STAR_SHAPED,
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        command=sys.argv, environment=base.environment(),
        prepared_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))


def verify(output):
    manifest = sc.read(output / 'manifest.json')
    changed = sorted(k for k, v in sources().items() if manifest['source_sha256'].get(k) != v)
    if changed or set(manifest['source_sha256']) != set(sources()):
        raise RuntimeError('Frozen numerical sources changed: ' + ', '.join(changed[:5]))
    for name, digest in manifest['input_sha256'].items():
        if sc.digest(sc.ROOT / name) != digest:
            raise RuntimeError('Frozen input changed: ' + name)
    if sc.digest(PLAN) != manifest['plan_sha256']:
        raise RuntimeError('Frozen plan changed')


def fit(catalog, folder, bands, safeguarded):
    """SC-030 `spd_fit` with a declared band per stage and optional safeguards."""
    inputs = sc.load()
    top025 = inputs['top025']
    p, m = top025.p, top025.m
    safeguards = StepSafeguards() if safeguarded else None
    state = MultiRadialFourierState((circle_cartesian_fourier_state(
        ac.START['center'], ac.START['radius'], 'comparison.circle', maximum_mode=bands[0]),))
    observed = np.column_stack([catalog[ac.CATALOG_HZ.index(f)].scattered for f in p.TRAIN])
    floor = inputs['control'].minimum_component_radius_m
    sc.write(folder / 'configuration.json', dict(bands=bands, step_safeguards=None if safeguards is None else
        asdict(safeguards), optimizer_template=asdict(replace(p._optimizer_config(state, inputs['control']),
        loss_tolerance=1e-14)), nodes=NODES, minimum_component_radius_m=floor, runtime=runtime_metadata(),
        geometry_validation='certified', kernels='real_bessel', gauge='polar_angle', frequencies_hz=p.TRAIN,
        stage_plan=top025.follow.FULL_PLAN, solve=asdict(inputs['solve'])))
    snapshots, records = [], []
    status, reason = 'COMPLETED_SCHEDULE', None
    started = time.perf_counter()
    ledger = m.Ledger(cap=CAP, seconds=SECONDS)
    with inverse_runtime('compiled'), execution(kernels='real_bessel', device='cpu'), \
            geometry_validation('certified', on_fit=snapshots.append), ledger.instrument():
        try:
            for (number, quota), band in zip(top025.follow.FULL_PLAN, bands):
                if band != state.components[0].maximum_mode:
                    # Zero padding: the same physical curve in the larger space.
                    state = MultiRadialFourierState((zero_padded_component(state.components[0], band),))
                optimizer = replace(p._optimizer_config(state, inputs['control']), loss_tolerance=1e-14)
                ledger.begin_stage(number, quota)
                data = p.training_data(p.TRAIN[:number], observed[:, :number])
                state, terminal = m.fit_stage(state, data, NODES, inputs['solve'], optimizer, floor, ledger,
                    folder / f'stage_{number}', step_safeguards=safeguards)
                records.append(dict(stage=f'stage_{number}', band=band, outcome=terminal['stage_outcome'],
                    stop=terminal['optimizer_stop'], accepted=terminal['accepted_steps'],
                    final_loss=terminal['production_loss'], units=terminal['work']['stage_work_units'],
                    effective_training_exposure=terminal['effective_training_exposure'],
                    exposure=terminal['exposure']))
                sc.write(folder / 'checkpoint.json', dict(final_state=p.driver.serialize_state(state),
                    stages=records, work=ledger.snapshot()))
                if terminal['stage_outcome'] not in (NORMAL_RETURN, STAGE_QUOTA):
                    status, reason = 'HARD_STOP', terminal['stage_outcome']
                    break
                if not terminal['effective_training_exposure']:
                    raise m.ExposureObstruction('stage lacks a usable model')
                if not p.feasible(state, NODES, inputs['solve'], floor):
                    raise m.NumericalFailure('retained endpoint infeasible')
        except m.Stop as exc:
            status, reason = 'HARD_STOP', exc.code
    elapsed, work = time.perf_counter() - started, ledger.snapshot()
    sc.write(folder / 'final_state.json', p.driver.serialize_state(state))
    return sc.from_cartesian(state.components[0]), dict(status=status, reason=reason, stages=records, work=work,
        work_units=work['budget_work_units'], inverse_seconds=elapsed, final_band=state.components[0].maximum_mode)


def endpoint(case, curve, catalog):
    """Evaluation only, identical to SC-030's worker scoring."""
    result = ast.score(case, curve, catalog)
    training = [catalog[ac.CATALOG_HZ.index(f)] for f in sc.spd_modules()[0].p.TRAIN]
    values = [np.column_stack([solve(curve, o.wavenumber, ac.contrast(), o.acquisition, n).prediction
                               for o in training]) for n in NODES]
    discrepancy = ac.relative(*values)
    result.update(training_cross_resolution=discrepancy,
        training_numerically_qualified=bool(np.all(discrepancy <= [1e-5, 1e-7, 1e-7, 1e-7])))
    return result


def qualify(output):
    """Defaults replay SC-030's SPD circle exactly; then the campaign may run."""
    verify(output)
    folder = output / 'qualification'
    folder.mkdir(exist_ok=False)
    started = time.perf_counter()
    result = dict(status='IN_PROGRESS')
    try:
        replay = folder / 'spd008_wrong_circle'
        replay.mkdir()
        _, row = base.spd_fit(ast.catalog_only('wrong_circle'), replay)
        recorded = sc.read(REPLAY / 'result.json')
        result.update(replay_digest=row['trajectory_digest'], recorded_digest=recorded['trajectory_digest'],
            replay_status=[row['status'], row['reason']], recorded_status=[recorded['status'], recorded['reason']],
            replay_units=row['work_units'], recorded_units=recorded['work_units'])
        assert row['trajectory_digest'] == recorded['trajectory_digest'], 'Default path changed SC-030 trajectory'
        result['status'] = 'PASS'
    except Exception as exc:
        result.update(status='FAIL', error=repr(exc), traceback=traceback.format_exc())
    result['seconds'] = time.perf_counter() - started
    sc.write(folder / 'result.json', result)
    verify(output)
    print(json.dumps(dict(qualification=result['status'], seconds=result['seconds'])), flush=True)
    if result['status'] != 'PASS':
        raise RuntimeError(result.get('error'))


def worker(output, case, arm):
    verify(output)
    assert sc.read(output / 'qualification/result.json')['status'] == 'PASS'
    folder = output / 'runs' / arm / case
    folder.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    sc.write(folder / 'environment_start.json', base.environment())
    catalog = ast.catalog_only(case)
    bands, safeguarded = ARMS[arm]
    curve, result = fit(catalog, folder, bands, safeguarded)
    result.update(case=case, arm=arm, bands=bands, safeguards=safeguarded, star_shaped_truth=STAR_SHAPED[case],
        final_curve=ast.curve_record(curve), setup_and_inverse_seconds=time.perf_counter() - started)
    sc.write(folder / 'unscored_result.json', result)
    tick = time.perf_counter()
    try:
        result['score'] = endpoint(case, curve, catalog)
    except Exception as exc:
        result['evaluation_error'] = dict(error=repr(exc), traceback=traceback.format_exc())
    result['evaluation_seconds'] = time.perf_counter() - tick
    verify(output)
    sc.write(folder / 'environment_end.json', base.environment())
    sc.write(folder / 'result.json', result)
    print(json.dumps(dict(case=case, arm=arm, status=result['status'], reason=result['reason'],
        units=result['work_units'], rms_mm=result.get('score', {}).get('symmetric_rms_mm'))), flush=True)


def campaign(output):
    verify(output)
    assert sc.read(output / 'qualification/result.json')['status'] == 'PASS'
    path = output / 'campaign.json'
    assert not path.exists(), 'Fresh campaign required'
    progress = dict(status='RUNNING', workers=[], started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    started = time.perf_counter()
    # Full-band arms are the slowest; dispatch them first.
    jobs = [(case, arm) for arm in ('S', 'LS', 'L') for case in CASES]

    def run(job):
        case, arm = job
        remaining = CAMPAIGN_SECONDS - (time.perf_counter() - started)
        row = dict(case=case, arm=arm)
        if remaining <= 0:
            row.update(exit_code=None, reason='CAMPAIGN_WALL_LIMIT')
            return row
        command = [sys.executable, '-m', 'experiments.shape_continuation.spd_safeguards', 'worker',
                   '--output', str(output), '--case', case, '--arm', arm]
        tick = time.perf_counter()
        try:
            with (output / f'{arm}_{case}.log').open('w') as log:
                done = subprocess.run(command, cwd=sc.ROOT, stdout=log, stderr=subprocess.STDOUT,
                                      timeout=min(OUTER_SECONDS, remaining), check=False)
            row['exit_code'] = done.returncode
        except subprocess.TimeoutExpired:
            row.update(exit_code=None, reason='OUTER_WALL_LIMIT')
        row.update(elapsed_seconds=time.perf_counter() - tick, command=command)
        print(json.dumps(row), flush=True)
        return row

    with ThreadPoolExecutor(WORKERS) as pool:
        for row in pool.map(run, jobs):
            progress['workers'].append(row)
            progress['elapsed_seconds'] = time.perf_counter() - started
            sc.write(path, progress)
    verify(output)
    progress['status'] = 'DISPATCH_COMPLETE'
    sc.write(path, progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'qualify', 'campaign', 'worker'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--arm', choices=tuple(ARMS))
    args = parser.parse_args()
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    if args.mode == 'worker':
        assert args.case is not None and args.arm is not None
        worker(args.output.resolve(), args.case, args.arm)
    else:
        globals()[args.mode](args.output.resolve())
