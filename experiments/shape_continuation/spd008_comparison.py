"""SC-030: frozen six-case SPD-008 / clean-hybrid execution comparison.

Run with the EMNerf interpreter, PYTHONPATH=solvers:. and one BLAS thread.
The driver reuses both stage fitters. Truth is loaded only after fitting.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
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
from sdf_inverse.radial_topology import MultiRadialFourierState
from . import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from .forward import solve
from .lm_backend import Ledger, NORMAL_RETURN, STAGE_QUOTA, Stop, fit_stage, stage_record
from .updates import BorgesUpdate

CASES = ast.CASES
ARMS = ('spd008', 'hybrid_reference', 'hybrid_cache')
NODES = (512, 1024)
CAP, SECONDS, CAMPAIGN_SECONDS = 8012, 3600., 12*3600.
PLAN = sc.ROOT/'docs/iterations/shape_frequency_continuation/iteration_12/03_plan.md'
TEST = sc.ROOT/'pytest/shape_continuation/test_execution_cache.py'


def sources():
    return {**sc.source_hashes(), str(TEST.relative_to(sc.ROOT)): sc.digest(TEST)}


def environment():
    import scipy
    return dict(python=sys.version, executable=sys.executable, numpy=np.__version__, scipy=scipy.__version__,
        platform=platform.platform(), cpu=next((s.split(':', 1)[1].strip() for s in
        Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')), 'unknown'),
        affinity=sorted(os.sched_getaffinity(0)), load_average=os.getloadavg(),
        threads={k: os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')})


def untimed(value):
    """Remove clock observations, not work counts, decisions or numerical values."""
    if isinstance(value, dict):
        return {k: untimed(v) for k, v in value.items() if k not in
                ('seconds', 'active_wall_seconds', 'inverse_seconds', 'elapsed_seconds')}
    if isinstance(value, list):
        return [untimed(v) for v in value]
    return value


def semantic_digest(value):
    return hashlib.sha256(json.dumps(untimed(value), sort_keys=True, allow_nan=False).encode()).hexdigest()


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = {str(p.relative_to(sc.ROOT)): sc.digest(p) for case in CASES for p in
              (ast.source_folder(case)/name for name in ('observations.json', 'truth.json', 'oracle_check.json'))}
    assert all(sc.read(ast.source_folder(c)/'oracle_check.json')['passed'] for c in CASES)
    frozen = sources()
    for name in frozen:
        destination = output/'sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sc.ROOT/name, destination)
    shutil.copyfile(PLAN, output/'approved_plan.md')
    sc.write(output/'manifest.json', dict(experiment='SC-030', source_sha256=frozen, input_sha256=inputs,
        plan_sha256=sc.digest(PLAN), cases=CASES, arms=ARMS, nodes=NODES, repetitions=2,
        per_fit_cap=CAP, per_fit_seconds=SECONDS, campaign_seconds=CAMPAIGN_SECONDS,
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        command=sys.argv, environment=environment(), prepared_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))


def verify(output):
    manifest = sc.read(output/'manifest.json')
    if sources() != manifest['source_sha256']:
        raise RuntimeError('Frozen numerical sources changed')
    for name, digest in manifest['input_sha256'].items():
        if sc.digest(sc.ROOT/name) != digest:
            raise RuntimeError('Frozen input changed: '+name)
    if sc.digest(PLAN) != manifest['plan_sha256']:
        raise RuntimeError('Frozen plan changed')


def initial_spd():
    return MultiRadialFourierState((circle_cartesian_fourier_state(
        ac.START['center'], ac.START['radius'], 'comparison.circle', maximum_mode=17),))


def hybrid_fit(catalog, mode, folder, first_stage_only=False, cap=CAP, seconds=SECONDS):
    stages, config = ast.schedules(catalog, 'baseline')
    if first_stage_only:
        stages = stages[:1]
    update = BorgesUpdate(sc.LENGTH, projection_tolerance=1e-5)
    curve = update.regauge(ac.start_curve(), stages[0].curve_modes)[0]
    sc.write(folder/'configuration.json', dict(backend=asdict(config), update=update.settings(),
        geometry_validation=mode, stages=[stage_record(s) for s in stages]))
    snapshots, records, history = [], [], []
    status, reason = 'COMPLETED_SCHEDULE', None
    started = time.perf_counter()
    ledger = Ledger(cap=cap, seconds=seconds)
    with geometry_validation(mode, on_fit=snapshots.append):
        for stage in stages:
            try:
                ledger.begin_stage(stage.label, stage.quota)
                record = fit_stage(curve, stage, ac.contrast(), update, config, ledger)
            except Stop as exc:
                status, reason = 'HARD_STOP', exc.code
                break
            curve = record.curve
            row = dict(stage=stage.label, outcome=record.outcome, stop=record.stop_reason,
                accepted=record.accepted_steps, initial_loss=record.initial_loss, final_loss=record.final_loss,
                units=record.work['stage_units'])
            records.append(row)
            data = dict(history=record.history, trials=record.trials, acceptance_checks=record.acceptance_checks)
            history.append(data)
            sc.write(folder/(stage.label+'_history.json'), data)
            sc.write(folder/'checkpoint.json', dict(final_curve=ast.curve_record(curve), stages=records,
                work=ledger.snapshot()))
            if record.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                status, reason = 'HARD_STOP', record.outcome
                break
    elapsed, work = time.perf_counter()-started, ledger.snapshot()
    # Round-trip through the same portable JSON used for saved scientific records.
    sc.write(folder/'trajectory_semantics.json', dict(stages=records, histories=history,
        final_curve=ast.curve_record(curve), work=work, status=status, reason=reason))
    signature = semantic_digest(sc.read(folder/'trajectory_semantics.json'))
    return curve, dict(status=status, reason=reason, stages=records, work=work, work_units=work['work_units'],
        inverse_seconds=elapsed, cache=snapshots, trajectory_digest=signature)


def spd_fit(catalog, folder):
    from dataclasses import replace
    inputs = sc.load()
    top025, state = inputs['top025'], initial_spd()
    p, m = top025.p, top025.m
    optimizer = replace(p._optimizer_config(state, inputs['control']), loss_tolerance=1e-14)
    observed = np.column_stack([catalog[ac.CATALOG_HZ.index(f)].scattered for f in p.TRAIN])
    floor = inputs['control'].minimum_component_radius_m
    sc.write(folder/'configuration.json', dict(optimizer=asdict(optimizer), nodes=NODES,
        minimum_component_radius_m=floor, runtime=runtime_metadata(), geometry_validation='certified',
        kernels='real_bessel', gauge='polar_angle', maximum_mode=17,
        reduced_directions=len(state.gauge_tangent_basis()), frequencies_hz=p.TRAIN,
        stage_plan=top025.follow.FULL_PLAN, solve=asdict(inputs['solve'])))
    snapshots, records = [], []
    status, reason = 'COMPLETED_SCHEDULE', None
    started = time.perf_counter()
    ledger = m.Ledger(cap=CAP, seconds=SECONDS)
    with inverse_runtime('compiled'), execution(kernels='real_bessel', device='cpu'), \
            geometry_validation('certified', on_fit=snapshots.append), ledger.instrument():
        try:
            for number, quota in top025.follow.FULL_PLAN:
                ledger.begin_stage(number, quota)
                data = p.training_data(p.TRAIN[:number], observed[:, :number])
                state, terminal = m.fit_stage(state, data, NODES, inputs['solve'], optimizer,
                    floor, ledger, folder/f'stage_{number}')
                records.append(dict(stage=f'stage_{number}', outcome=terminal['stage_outcome'],
                    stop=terminal['optimizer_stop'], accepted=terminal['accepted_steps'],
                    final_loss=terminal['production_loss'], units=terminal['work']['stage_work_units'],
                    effective_training_exposure=terminal['effective_training_exposure']))
                sc.write(folder/'checkpoint.json', dict(final_state=p.driver.serialize_state(state),
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
    elapsed, work = time.perf_counter()-started, ledger.snapshot()
    sc.write(folder/'final_state.json', p.driver.serialize_state(state))
    semantic_files = [folder/'final_state.json'] + sorted(folder.glob('stage_*/*.jsonl')) + \
        sorted(folder.glob('stage_*/acceptance.json'))
    semantics = {str(path.relative_to(folder)):
        [json.loads(line) for line in path.read_text().splitlines()] if path.suffix == '.jsonl'
        else sc.read(path) for path in semantic_files}
    semantics.update(stages=records, work=work, status=status, reason=reason)
    return sc.from_cartesian(state.components[0]), dict(status=status, reason=reason, stages=records,
        work=work, work_units=work['budget_work_units'], inverse_seconds=elapsed,
        cache=snapshots, trajectory_digest=semantic_digest(semantics))


def qualify(output):
    verify(output)
    folder = output/'qualification'
    folder.mkdir(exist_ok=False)
    started = time.perf_counter()
    result = dict(status='IN_PROGRESS', forward=[], hybrid=[])
    try:
        catalog = ast.catalog_only('wrong_circle')
        train = sc.spd_modules()[0].p.TRAIN
        values = {}
        curve = ac.start_curve()
        delta = np.max(np.abs(curve.values(4096)-sc.from_cartesian(initial_spd().components[0]).values(4096)))
        assert delta*sc.LENGTH <= 1e-14, 'Physical starts differ'
        result['start_max_difference_m'] = float(delta*sc.LENGTH)
        for nodes in NODES:
            with execution(kernels='real_bessel', device='cpu'):
                reference = ac.kress_predictions(curve, train, nodes)
            package = np.column_stack([solve(curve, catalog[ac.CATALOG_HZ.index(f)].wavenumber,
                ac.contrast(), catalog[ac.CATALOG_HZ.index(f)].acquisition, nodes).prediction for f in train])
            discrepancy = ac.relative(reference, package)
            result['forward'].append(dict(nodes=nodes, package_vs_spd_relative=discrepancy))
            assert np.all(discrepancy <= 1e-8), 'Forward implementations disagree'
            values[nodes] = package
        cross = ac.relative(values[NODES[0]], values[NODES[1]])
        assert np.all(cross <= np.array([1e-5, 1e-7, 1e-7, 1e-7])), 'Start resolution unqualified'
        result['start_cross_resolution'] = cross
        for mode in ('reference', 'cache'):
            destination = folder/mode
            destination.mkdir()
            _, row = hybrid_fit(catalog, mode, destination, first_stage_only=True,
                cap=1000-16-sum(x['work_units'] for x in result['hybrid']),
                seconds=900-(time.perf_counter()-started))
            result['hybrid'].append(row)
            assert row['status'] == 'COMPLETED_SCHEDULE', row['reason']
        a, b = result['hybrid']
        # Qualification uses declining hard budgets; they are metadata, not work/trajectory differences.
        first, second = (sc.read(folder/m/'trajectory_semantics.json') for m in ('reference', 'cache'))
        for record in (first, second):
            for work in [record['work'], *[h['work'] for s in record['histories'] for h in s['history']]]:
                for key in ('cap', 'wall_seconds', 'wall_ceiling_seconds', 'solve_cap'):
                    work.pop(key, None)
        assert untimed(first) == untimed(second), 'Cache changed hybrid trajectory'
        assert sum(s['counts'].get('self_intersection.hits', 0) for s in b['cache']) > 0
        result.update(status='PASS', exact_trajectory=True,
            work_units=16+a['work_units']+b['work_units'])
    except Exception as exc:
        result.update(status='FAIL', error=repr(exc), traceback=traceback.format_exc())
    result['seconds'] = time.perf_counter()-started
    sc.write(folder/'result.json', result)
    verify(output)
    print(json.dumps(dict(qualification=result['status'], seconds=result['seconds'])), flush=True)
    if result['status'] != 'PASS':
        raise RuntimeError(result['error'])


def worker(output, case, arm, repeat):
    verify(output)
    assert sc.read(output/'qualification/result.json')['status'] == 'PASS'
    folder = output/'runs'/f'repeat_{repeat}'/case/arm
    folder.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    sc.write(folder/'environment_start.json', environment())
    catalog = ast.catalog_only(case)
    if arm == 'spd008':
        curve, result = spd_fit(catalog, folder)
    else:
        curve, result = hybrid_fit(catalog, 'cache' if arm == 'hybrid_cache' else 'reference', folder)
    result.update(case=case, arm=arm, repeat=repeat, final_curve=ast.curve_record(curve),
        setup_and_inverse_seconds=time.perf_counter()-started)
    sc.write(folder/'unscored_result.json', result)
    tick = time.perf_counter()
    try:
        result['score'] = ast.score(case, curve, catalog)
        training = [catalog[ac.CATALOG_HZ.index(f)] for f in sc.spd_modules()[0].p.TRAIN]
        values = [np.column_stack([solve(curve, o.wavenumber, ac.contrast(), o.acquisition, n).prediction
                                  for o in training]) for n in NODES]
        discrepancy = ac.relative(*values)
        result['score'].update(training_cross_resolution=discrepancy,
            training_numerically_qualified=bool(np.all(discrepancy <= [1e-5, 1e-7, 1e-7, 1e-7])),
            evaluation_field_solves=27)
    except Exception as exc:
        result['evaluation_error'] = dict(error=repr(exc), traceback=traceback.format_exc())
    result['evaluation_seconds'] = time.perf_counter()-tick
    result['worker_seconds'] = time.perf_counter()-started
    verify(output)
    sc.write(folder/'environment_end.json', environment())
    sc.write(folder/'result.json', result)
    print(json.dumps(dict(case=case, arm=arm, repeat=repeat, status=result['status'],
        reason=result['reason'], units=result['work_units'], inverse_seconds=result['inverse_seconds'],
        rms_mm=result.get('score', {}).get('symmetric_rms_mm'))), flush=True)


def campaign(output):
    verify(output)
    assert sc.read(output/'qualification/result.json')['status'] == 'PASS'
    progress = dict(status='RUNNING', workers=[], started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    path = output/'campaign.json'
    assert not path.exists(), 'Fresh campaign required'
    started = time.perf_counter()
    for repeat in range(2):
        for i, case in enumerate(CASES):
            order = list(ARMS[i % 3:]+ARMS[:i % 3])
            if repeat:
                order.reverse()
            for arm in order:
                remaining = CAMPAIGN_SECONDS-(time.perf_counter()-started)
                if remaining <= 0:
                    progress['status'] = 'CAMPAIGN_WALL_LIMIT'
                    sc.write(path, progress)
                    return
                command = [sys.executable, '-m', 'experiments.shape_continuation.spd008_comparison',
                    'worker', '--output', str(output), '--case', case, '--arm', arm, '--repeat', str(repeat)]
                tick = time.perf_counter()
                label = f'{repeat}_{case}_{arm}'
                try:
                    with (output/(label+'.log')).open('w') as log:
                        run = subprocess.run(command, cwd=sc.ROOT, stdout=log, stderr=subprocess.STDOUT,
                            timeout=min(4050., remaining), check=False)
                    row = dict(case=case, arm=arm, repeat=repeat, exit_code=run.returncode)
                except subprocess.TimeoutExpired:
                    row = dict(case=case, arm=arm, repeat=repeat, exit_code=None, reason='OUTER_WALL_LIMIT')
                row.update(elapsed_seconds=time.perf_counter()-tick, command=command)
                progress['workers'].append(row)
                progress['elapsed_seconds'] = time.perf_counter()-started
                sc.write(path, progress)
                print(json.dumps(row), flush=True)
                verify(output)
    progress['status'] = 'DISPATCH_COMPLETE'
    sc.write(path, progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'qualify', 'campaign', 'worker'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--arm', choices=ARMS)
    parser.add_argument('--repeat', type=int, choices=(0, 1))
    args = parser.parse_args()
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    if args.mode == 'worker':
        assert args.case is not None and args.arm is not None and args.repeat is not None
        worker(args.output.resolve(), args.case, args.arm, args.repeat)
    else:
        globals()[args.mode](args.output.resolve())
