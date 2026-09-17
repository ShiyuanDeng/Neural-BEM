"""TOP-021: the complete frozen twelve-scene matched S/F comparison.

This is an expanded-acquisition/continuation comparison. Existing numerical
algorithms are reused; a verified TOP-020 recovery releases physical dispatch.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top020 import run as base
import run_top016_screen as screen

m, p, follow = base.m, base.p, base.follow
read, write, require = m.read, m.write, base.require
NODES, STAGE_PLAN = base.NODES, base.STAGE_PLAN
REUSED = ('central-ellipse-star', 'far-two-stars', 'merge')
PLAN = ROOT/'docs/iterations/topology/iteration_13/02_proposals/02_conditional_twelve_scene_contract.md'
TOTAL_CAP = 240360
WALL_SECONDS = 14400


def source_hashes():
    return {**base.source_hashes(), **{str(x.relative_to(ROOT)): p.digest(x)
        for x in sorted(Path(__file__).parent.glob('*.py'))}}


def release_gate(top020):
    base.verified_hashes(top020, read(top020/'artifact_manifest.json'))
    contract = read(top020/'contract.json')
    require(contract['experiment'] == 'TOP-020' and contract['scene'] == 'far-two-stars'
        and contract['stage_plan'] == [list(row) for row in STAGE_PLAN],
        'release evidence is not the declared TOP-020 staged protocol')
    result, verification = read(top020/'result.json'), read(top020/'verification.json')
    require(result['fresh_recovery_pass'] and verification['status'] == 'PASS'
        and verification['fresh_recovery_pass'], 'TOP-020 does not release the suite')
    return dict(path=os.path.relpath(top020, ROOT), result_sha256=p.digest(top020/'result.json'),
        verification_sha256=p.digest(top020/'verification.json'), fresh_recovery_pass=True)


def capacity_start(state, control, solve):
    """Capacity allocation depends only on the returned geometry, never truth."""
    if state is None:
        raise m.NumericalFailure('empty automatic topology endpoint')
    maximum_mode = 17 if len(state.components) == 1 else 9
    require(all(c.maximum_mode <= maximum_mode for c in state.components), 'capacity rule would truncate geometry')
    padded = p.MultiRadialFourierState(tuple(p.zero_padded_component(c, maximum_mode)
        if c.maximum_mode < maximum_mode else c for c in state.components))
    delta = max(float(np.max(np.linalg.norm(a-b, axis=1))) for a, b in
        zip(p.boundary_points(state), p.boundary_points(padded)))
    require(delta <= 1e-10 and state.component_ids == padded.component_ids, 'padding changed geometry or IDs')
    if not p.feasible(padded, NODES, solve, control.minimum_component_radius_m):
        raise m.NumericalFailure('automatic endpoint infeasible at continuation nodes')
    optimizer = replace(p._optimizer_config(padded, control), loss_tolerance=1e-14)
    return padded, optimizer, dict(maximum_mode=maximum_mode, parameter_count=padded.parameter_count,
        reduced_directions=len(padded.gauge_tangent_basis()), maximum_point_change_m=delta,
        rule='K17 for one returned component; K9 per component otherwise', uses_truth_or_target_count=False)


def training_record(original, added, original_path):
    observed = np.array(original['observed_real']) + 1j*np.array(original['observed_imag'])
    combined = np.column_stack((observed[:, 0], added))
    require(combined.shape == (24, 4), 'unexpected training shape')
    return dict(frequencies_hz=p.TRAIN, observed_real=combined.real, observed_imag=combined.imag,
        acquisition_and_material_source=os.path.relpath(original_path, ROOT),
        source_sha256=p.digest(original_path), old_training_bytes_equal=True)


def load_scene(bundle, scene_id):
    spec = read(bundle/'scene_spec.json')
    scene = next(s for s in spec['scenes'] if s['id'] == scene_id)
    folder = bundle/'inputs'/scene_id
    original = read(folder/'observations.json')
    saved = read(folder/'training_observations.json')
    initial = p.driver.deserialize_state(read(folder/'initial_state.json'))
    require(m.state_hash(initial) == m.state_hash(p.benchmark.initial_state(scene)), 'original start changed')
    require(original == read(p.DATA/'scenes'/scene_id/'observations.json'), 'v1 observations changed')
    require(saved['frequencies_hz'] == list(p.TRAIN), 'training frequency mismatch')
    observed = np.array(saved['observed_real']) + 1j*np.array(saved['observed_imag'])
    full = np.array(original['observed_real']) + 1j*np.array(original['observed_imag'])
    require(observed.shape == (24, 4) and full.shape == (24, 3), 'observation dimensions changed')
    reference_training, reference_evaluation = p.benchmark.shared_data(p.DATA, scene, spec)
    np.testing.assert_array_equal(observed[:, :1], reference_training.observed_scattered_response)
    np.testing.assert_array_equal(full[:, 1:], reference_evaluation.observed_scattered_response)
    require(p.digest(ROOT/saved['acquisition_and_material_source']) == saved['source_sha256'], 'acquisition provenance changed')
    p.training_data(p.TRAIN, observed)
    return initial, observed, full[:, 1:], scene, spec


def prepare(bundle, validation, top020):
    require(not bundle.exists(), 'suite output must be fresh')
    release = release_gate(top020)
    tests = read(validation)
    require(tests['status'] == 'PASS' and tests['source_sha256'] == source_hashes(), 'tests do not qualify this source')
    base.verified_hashes(ROOT, tests['test_sha256'])
    require(p.digest(validation.parent/tests['log']) == tests['log_sha256'], 'test log changed')
    spec = read(p.DATA/'scene_spec.json')
    require(spec == read(ROOT/'config/topology_scenes_v1.json') and len(spec['scenes']) == 12, 'v1 scene matrix changed')
    bundle.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(p.DATA/'scene_spec.json', bundle/'scene_spec.json')
    for src, dest in ((PLAN, 'approved_plan.md'), (validation, 'pre_dispatch_validation.json'),
            (validation.parent/tests['log'], 'pre_dispatch_tests.log'),
            (Path(__file__).parent/'implementation_review.md', 'implementation_review.md')):
        shutil.copyfile(src, bundle/dest)
    for name in [*tests['test_sha256'], *[n for n in source_hashes() if n.startswith('experiments/')]]:
        target = bundle/'measured_sources'/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    historical = {str((p.DATA/'scene_spec.json').relative_to(ROOT)):p.digest(p.DATA/'scene_spec.json')}
    reused_audit_path = m.SOURCE/'phase1/sensitivity.json'
    reused_audit = read(reused_audit_path)
    historical[str(reused_audit_path.relative_to(ROOT))] = p.digest(reused_audit_path)
    for scene in spec['scenes']:
        target = bundle/'inputs'/scene['id']; target.mkdir(parents=True)
        for name in ('initial_state.json', 'observations.json', 'oracle_check.json'):
            source = p.DATA/'scenes'/scene['id']/name
            shutil.copyfile(source, target/name)
            historical[str(source.relative_to(ROOT))] = p.digest(source)
        require(read(target/'oracle_check.json')['passed'], 'original oracle is not qualified')
        if scene['id'] in REUSED:
            source = follow.HISTORY/'inputs'/scene['id']/'training_observations.json'
            shutil.copyfile(source, target/'training_observations.json')
            historical[str(source.relative_to(ROOT))] = p.digest(source)
    solve = p.driver.baseline.iteration01_solve_config()
    write(bundle/'contract.json', dict(experiment='TOP-021', approval='2026-09-15 user: finish the rest',
        scenes=[s['id'] for s in spec['scenes']], arms=['S', 'F'], topology_controller=asdict(p.benchmark.controller_config(spec, 'H')),
        topology_nodes=[64, 128], topology_solve_cap=4000, topology_seconds=600,
        continuation_nodes=NODES, stage_plan=STAGE_PLAN, continuation_solve_cap=8012, continuation_seconds=7200,
        oracle_solve_cap=72, oracle_seconds=300, campaign_solve_cap=TOTAL_CAP, campaign_seconds=WALL_SECONDS,
        maximum_workers=4, blas_threads=1, shared_prefix_charged_once=True, standalone_arm_cost_includes_full_prefix=True,
        training_frequencies_hz=p.TRAIN, evaluation_frequencies_hz=p.EVALUATION,
        prediction_tolerances=follow.TOLERANCES, solve_config=asdict(solve), normalization=m.NORMALIZATION,
        capacity_rule='K17 for one returned component; K9 per component otherwise',
        original_scene_count_and_gates_unchanged=True, new_comparison_protocol=True, independent_review=False))
    manifest = dict(git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256=source_hashes(), historical_input_sha256=historical, top020_release=release,
        command=sys.argv, workers=4, blas_threads=1)
    write(bundle/'manifest.json', manifest)
    ledger = m.Ledger(cap=72, seconds=300)
    audit = dict(status='IN_PROGRESS', scenes={})
    try:
        with ledger.instrument():
            for scene in spec['scenes']:
                name = scene['id']; folder = bundle/'inputs'/name
                if name in REUSED:
                    qualification = reused_audit['oracle_checks'][name]
                    require(qualification['passed'], 'reused expanded oracle did not pass')
                    audit['scenes'][name] = dict(reused=True, qualified=True, new_oracle_solves=0,
                        original_qualification=qualification, evidence_sha256=p.digest(reused_audit_path))
                    continue
                ledger.reserve(6)
                values = {n:screen.oracle(scene, p.TRAIN[1:], n, solve, ledger) for n in NODES}
                discrepancy = p.relative(values[256], values[512])
                qualified = bool(np.all(np.isfinite(discrepancy)) and np.max(discrepancy) <= spec['oracle_relative_tolerance'])
                audit['scenes'][name] = dict(reused=False, qualified=qualified, relative_discrepancy=discrepancy,
                    predictions={str(n):follow.complex_record(v) for n,v in values.items()}, new_oracle_solves=6)
                write(bundle/'oracle_audit.json', {**audit, 'work':ledger.snapshot()})
                if not qualified:
                    raise m.NumericalFailure(f'added oracle not qualified: {name}')
                original = read(folder/'observations.json')
                write(folder/'training_observations.json', training_record(original, values[256], folder/'observations.json'))
        audit['status'] = 'PASS'
    except Exception as exc:
        audit.update(status='HARD_STOP', reason=getattr(exc, 'code', type(exc).__name__), detail=str(exc), traceback=traceback.format_exc())
    audit['work'] = ledger.snapshot()
    write(bundle/'oracle_audit.json', audit)
    if audit['status'] == 'PASS':
        for scene in spec['scenes']: load_scene(bundle, scene['id'])
    manifest['input_sha256'] = {str(x.relative_to(bundle)):p.digest(x) for x in (bundle/'inputs').rglob('*') if x.is_file()}
    manifest['input_sha256']['scene_spec.json'] = p.digest(bundle/'scene_spec.json')
    write(bundle/'manifest.json', manifest)
    return audit


def verify(bundle):
    manifest = read(bundle/'manifest.json')
    require(source_hashes() == manifest['source_sha256'], 'suite measured source changed')
    base.verified_hashes(ROOT, manifest['historical_input_sha256'])
    base.verified_hashes(bundle, manifest['input_sha256'])
    release = manifest['top020_release']; directory = ROOT/release['path']
    require(p.digest(directory/'result.json') == release['result_sha256'] and
        p.digest(directory/'verification.json') == release['verification_sha256'], 'TOP-020 release evidence changed')


def run_arm(bundle, scene_id, arm, state, optimizer, observed, evaluation, scene, spec, control, solve, common_hash=None):
    output = bundle/'runs'/scene_id/arm; output.mkdir(parents=True, exist_ok=False)
    ledger = m.Ledger(cap=8012, seconds=7200)
    record = dict(status='IN_PROGRESS', arm=arm, fresh_recovery_pass=False)
    try:
        def scorer(current):
            destination = (output/'initial_endpoint_predictions.json' if ledger.stage is None else
                output/f'stage_{ledger.stage}'/'endpoint_predictions.json')
            return base.score_endpoint(current, scene, spec, observed, evaluation, solve, ledger, destination)
        def fit(*args, **kwargs):
            final, terminal = m.fit_stage(*args, **kwargs)
            if arm == 'F' and ledger.stage == 1 and m.state_hash(final) != common_hash:
                terminal.update(stage_outcome='IMPLEMENTATION_ERROR', reason='S/F stage-1 state mismatch')
                write(output/'stage_1/terminal.json', terminal)
            return final, terminal
        with ledger.instrument():
            initial_score = scorer(state)
            if not initial_score['numerically_qualified']:
                raise m.NumericalFailure('automatic endpoint not qualified for continuation')
            schedule = m.run_schedule(state, arm, observed, NODES, solve, optimizer,
                control.minimum_component_radius_m, ledger, output, initial_score, scorer, fit=fit, stage_plan=STAGE_PLAN)
        record.update(status=schedule['status'], schedule=schedule, fresh_recovery_pass=bool(
            schedule['schedule_complete'] and schedule['complete_effective_exposure'] and
            schedule['numerically_qualified'] and schedule['reconstruction_gates_pass']))
        verify(bundle)
        record['sources_and_inputs_unchanged'] = True
    except Exception as exc:
        record.update(status='HARD_STOP', fresh_recovery_pass=False,
            reason=getattr(exc, 'code', type(exc).__name__), detail=str(exc), traceback=traceback.format_exc())
    record['work'] = ledger.snapshot()
    write(output/'result.json', record)
    return record


def shared_stage_one(record):
    stages = record.get('schedule', {}).get('stages', [])
    if not stages or not stages[0].get('stage_complete'):
        return None
    return stages[0]['score_state_sha256']


def run_scene(bundle, scene_id):
    verify(bundle)
    require(read(bundle/'oracle_audit.json')['status'] == 'PASS', 'oracle gate did not release inversion')
    initial, observed, evaluation, scene, spec = load_scene(bundle, scene_id)
    output = bundle/'runs'/scene_id; output.mkdir(parents=True, exist_ok=False)
    control = p.benchmark.controller_config(spec, 'H')
    solve = p.driver.baseline.iteration01_solve_config()
    ledger = follow.TopologyLedger(cap=4000, seconds=600)
    record = dict(scene=scene_id, status='IN_PROGRESS', arms={}, supplied_target_count=False,
        original_start_sha256=m.state_hash(initial), archived_optimized_state_used=False)
    prefix_work = None
    try:
        with ledger.instrument():
            state = follow.topology_prefix(initial, p.training_data(p.TRAIN[:1], observed[:, :1]),
                control, solve, ledger, output/'topology')
        prefix_work = ledger.snapshot()
        terminal = read(output/'topology/terminal.json')
        require(sum(prefix_work['completed'].values()) == terminal['controller_work']['totals']['bie_frequency_solve_count'],
                'prefix passive and physical work disagree')
        record['topology_checks'] = base.topology_checks(output/'topology', control)
        state, optimizer, capacity = capacity_start(state, control, solve)
        write(output/'handoff.json', dict(state=p.driver.serialize_state(state), state_sha256=m.state_hash(state),
            source_state_sha256=m.state_hash(terminal['final_state']), capacity=capacity, optimizer=asdict(optimizer)))
        record['capacity'] = capacity
        record['topology_work'] = prefix_work
        write(output/'result.json', record)
        s = run_arm(bundle, scene_id, 'S', state, optimizer, observed, evaluation, scene, spec, control, solve)
        record['arms']['S'] = s; write(output/'result.json', record)
        common_hash = shared_stage_one(s)
        if common_hash is None:
            record['arms']['F'] = dict(status='NOT_DISPATCHED', reason='shared stage-1 gate not qualified', fresh_recovery_pass=False)
        else:
            verify(bundle)
            record['arms']['F'] = run_arm(bundle, scene_id, 'F', state, optimizer, observed, evaluation, scene, spec, control, solve, common_hash)
        record['status'] = 'SCENE_COMPLETE'
    except Exception as exc:
        record.update(status='HARD_STOP', reason=getattr(exc, 'code', type(exc).__name__), detail=str(exc), traceback=traceback.format_exc())
    record['topology_work'] = ledger.snapshot() if prefix_work is None else prefix_work
    for arm in ('S', 'F'):
        record['arms'].setdefault(arm, dict(status='NOT_DISPATCHED', reason='topology/handoff not qualified', fresh_recovery_pass=False))
    works = [record['topology_work']] + [a['work'] for a in record['arms'].values() if 'work' in a]
    record['actual_attempted_calls'] = sum(w['total_attempted'] for w in works)
    record['actual_completed_solves'] = sum(sum(w['completed'].values()) for w in works)
    record['actual_failed_or_refused_calls'] = sum(sum(w['failed'].values()) for w in works)
    record['geometry_refused_calls'] = sum(w['calls'].get('preserved_candidate_refusals', 0) for w in works)
    record['active_wall_seconds'] = sum(w['active_wall_seconds'] for w in works)
    verify(bundle)
    record['sources_and_inputs_unchanged'] = True
    write(output/'result.json', record)
    print(json.dumps(dict(scene=scene_id, status=record['status'], calls=record['actual_attempted_calls'],
        recovery={a:r['fresh_recovery_pass'] for a,r in record['arms'].items()})), flush=True)
    return record


def run_job(bundle, scene_id, deadline):
    command = [sys.executable, str(Path(__file__).resolve()), 'scene', '--bundle', str(bundle), '--scene', scene_id]
    with (bundle/f'{scene_id}.log').open('w') as log:
        if time.monotonic() >= deadline:
            return dict(scene=scene_id, status='NOT_DISPATCHED_CAMPAIGN_WALL_LIMIT', command=command)
        try:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)
        except OSError as exc:
            return dict(scene=scene_id, status='WORKER_LAUNCH_FAILED', detail=str(exc), command=command)
        try:
            code = process.wait(timeout=max(.001, deadline-time.monotonic()))
            return dict(scene=scene_id, status='WORKER_RETURN', returncode=code, command=command)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait()
            return dict(scene=scene_id, status='CAMPAIGN_WALL_LIMIT', returncode=process.returncode,
                partial_work_is_lower_bound=True, command=command)


def campaign(bundle, validation, top020):
    started = time.monotonic()
    audit = prepare(bundle, validation, top020)
    record = dict(status='IN_PROGRESS', workers=[], oracle_status=audit['status'])
    write(bundle/'campaign.json', record)
    if audit['status'] == 'PASS':
        scenes = read(bundle/'contract.json')['scenes']
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(run_job, bundle, scene, started+WALL_SECONDS) for scene in scenes]
            for future in as_completed(futures):
                worker = future.result(); record['workers'].append(worker)
                write(bundle/'campaign.json', record)
                print(json.dumps(worker), flush=True)
        record['status'] = 'DISPATCH_COMPLETE'
    else:
        record['status'] = 'ORACLE_GATE_STOP'
    verify(bundle)
    record['elapsed_wall_seconds'] = time.monotonic()-started
    write(bundle/'campaign.json', record)
    write(bundle/'artifact_manifest.json', {str(x.relative_to(bundle)):p.digest(x)
        for x in sorted(bundle.rglob('*')) if x.is_file() and x.name != 'artifact_manifest.json'})
    return record


def retained_state(bundle, scene_id, arm):
    """Pick the recorded terminal/checkpoint, never the best truth-scored state."""
    folder = bundle/'runs'/scene_id
    path = folder/arm/'result.json'
    if path.exists():
        record = read(path)
        if 'schedule' in record:
            return record['schedule']['final_state'], str(path.relative_to(bundle))+'::schedule.final_state'
    stages = sorted((folder/arm).glob('stage_*/accepted_state.json'))
    if stages:
        return read(stages[-1])['state'], str(stages[-1].relative_to(bundle))+'::state'
    for name, field in (('handoff.json', 'state'), ('topology/terminal.json', 'final_state'),
                        ('topology/checkpoint.json', 'state')):
        path = folder/name
        if path.exists():
            return read(path)[field], str(path.relative_to(bundle))+'::'+field
    return read(bundle/'inputs'/scene_id/'initial_state.json'), f'inputs/{scene_id}/initial_state.json'


def saved_geometry(bundle):
    """Evaluate every retained state geometrically, with physical calls forbidden."""
    spec = read(bundle/'scene_spec.json')
    record = {}
    ledger = m.Ledger(cap=0, seconds=1800)
    with ledger.instrument():
        for scene in spec['scenes']:
            record[scene['id']] = {}
            for arm in ('S', 'F'):
                state, source = retained_state(bundle, scene['id'], arm)
                record[scene['id']][arm] = dict(state_sha256=m.state_hash(state), source=source,
                    geometry=p.benchmark.geometry_metrics(p.driver.deserialize_state(state), scene, spec))
    require(ledger.total == 0, 'geometry reporting attempted physical work')
    write(bundle/'geometry_scores.json', dict(new_physical_solves=0, scenes=record))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('campaign', 'scene', 'geometry'))
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--validation', type=Path)
    parser.add_argument('--top020', type=Path)
    parser.add_argument('--scene')
    args = parser.parse_args()
    require(all(os.environ.get(k) == '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')), 'single-thread BLAS required')
    if args.phase == 'campaign':
        require(args.validation is not None and args.top020 is not None, 'validation and TOP-020 evidence required')
        campaign(args.bundle.resolve(), args.validation.resolve(), args.top020.resolve())
    elif args.phase == 'scene':
        run_scene(args.bundle.resolve(), args.scene)
    else:
        saved_geometry(args.bundle.resolve())


if __name__ == '__main__':
    main()
