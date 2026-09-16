"""TOP-020: one fresh automatic far-circle-to-two-star integration.

Existing topology and continuation algorithms are imported unchanged. The
outer owner freezes truth/evaluation inputs for scoring; fitting receives only
training observations and the freshly computed state.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_topology_recovery_followup as follow

m, p = follow.m, follow.p
read, write = m.read, m.write
SCENE = 'far-two-stars'
NODES = (256, 512)
STAGE_PLAN = follow.FULL_PLAN
CENTRAL = ROOT/'results/validation/topology/TOP-017-followup-20260914-engineering/central-validated'
PLAN = ROOT/'docs/iterations/topology/iteration_13/03_plan.md'


def require(condition, reason):
    if not condition:
        raise m.ImplementationError(reason)


def source_hashes():
    return {**m.source_hashes(), 'experiments/top019/summarize.py': p.digest(ROOT/'experiments/top019/summarize.py'),
        **{str(x.relative_to(ROOT)): p.digest(x)
        for x in sorted(Path(__file__).parent.glob('*.py'))}}


def verified_hashes(base, records):
    for name, sha in records.items():
        require(p.digest(base/name) == sha, f'changed artifact/source: {name}')


def verify_central():
    verified_hashes(CENTRAL, read(CENTRAL/'artifact_manifest.json'))
    result = read(CENTRAL/'result.json')
    require(result['fresh_recovery_pass'] and result['sources_and_history_unchanged'],
            'saved fresh central control is not qualified')
    return dict(path=str(CENTRAL.relative_to(ROOT)), result_sha256=p.digest(CENTRAL/'result.json'),
        artifact_manifest_sha256=p.digest(CENTRAL/'artifact_manifest.json'),
        new_physical_solves=0, fresh_recovery_pass=True,
        role='preserved historical regression evidence; remeasure in later full suite')


def load_inputs(directory):
    spec = read(directory/'scene_spec.json')
    scene = next(s for s in spec['scenes'] if s['id'] == SCENE)
    initial = p.driver.deserialize_state(read(directory/'initial_state.json'))
    frozen = p.benchmark.initial_state(scene)
    require(m.state_hash(initial) == m.state_hash(frozen), 'original initial state mismatch')
    require(initial.component_ids == ('initial.circle',), 'unexpected original circle ID')
    original = read(directory/'observations.json')
    saved = read(directory/'training_observations.json')
    require(saved['frequencies_hz'] == list(p.TRAIN), 'training frequencies changed')
    require(original['frequencies_hz'] == [p.TRAIN[0], *p.EVALUATION], 'evaluation frequencies changed')
    observed = np.array(saved['observed_real']) + 1j*np.array(saved['observed_imag'])
    full = np.array(original['observed_real']) + 1j*np.array(original['observed_imag'])
    require(observed.shape == (24, 4) and full.shape == (24, 3), 'unexpected observation dimensions')
    reference_train, reference_evaluation = p.benchmark.shared_data(p.DATA, scene, spec)
    np.testing.assert_array_equal(observed[:, :1], reference_train.observed_scattered_response)
    np.testing.assert_array_equal(full[:, 1:], reference_evaluation.observed_scattered_response)
    require(read(p.DATA/'scenes'/SCENE/'observations.json') == original, 'v1 observations changed')
    require(p.digest(ROOT/saved['acquisition_and_material_source']) == saved['source_sha256'],
            'training acquisition provenance mismatch')
    np.testing.assert_array_equal(observed[:, :1], full[:, :1])
    p.training_data(p.TRAIN, observed)  # validates norms without physical calls
    return initial, observed, full[:, 1:], scene, spec


def prepare(output, validation):
    require(not output.exists(), 'output must be fresh')
    tests = read(validation)
    require(tests['status'] == 'PASS' and tests['source_sha256'] == source_hashes(),
            'pre-dispatch tests do not qualify current sources')
    verified_hashes(ROOT, tests['test_sha256'])
    require(p.digest(validation.parent/tests['log']) == tests['log_sha256'], 'test log changed')
    central = verify_central()
    output.mkdir(parents=True, exist_ok=False)
    inputs = output/'inputs'; inputs.mkdir()
    sources = {'scene_spec.json': p.DATA/'scene_spec.json',
        'initial_state.json': p.DATA/'scenes'/SCENE/'initial_state.json',
        'observations.json': follow.HISTORY/'inputs'/SCENE/'observations.json',
        'training_observations.json': follow.HISTORY/'inputs'/SCENE/'training_observations.json'}
    for name, source in sources.items():
        shutil.copyfile(source, inputs/name)
    initial, observed, evaluation, scene, spec = load_inputs(inputs)
    control = p.benchmark.controller_config(spec, 'H')
    solve = p.driver.baseline.iteration01_solve_config()
    write(output/'contract.json', dict(experiment='TOP-020',
        approval='2026-09-15 user: cp first. then i approve you to finish the rest',
        scene=SCENE, topology_controller=asdict(control), topology_nodes=[64, 128],
        topology_solve_cap=4000, topology_wall_seconds=600,
        continuation_nodes=NODES, maximum_mode=9, stage_plan=STAGE_PLAN,
        continuation_solve_cap=8012, continuation_wall_seconds=7200,
        total_solve_cap=12012, total_active_wall_seconds=7800,
        initial_state_sha256=m.state_hash(initial), solve_config=asdict(solve),
        training_frequencies_hz=p.TRAIN, evaluation_frequencies_hz=p.EVALUATION,
        prediction_tolerances=follow.TOLERANCES, normalization=m.NORMALIZATION,
        supplied_target_count=False, archived_optimized_state_used=False,
        numerical_workers=1, blas_threads=1, owner='Codex /root', independent_review=False))
    shutil.copyfile(PLAN, output/'approved_plan.md')
    shutil.copyfile(validation, output/'pre_dispatch_validation.json')
    shutil.copyfile(validation.parent/tests['log'], output/'pre_dispatch_tests.log')
    shutil.copyfile(Path(__file__).parent/'implementation_review.md', output/'implementation_review.md')
    for name in [*tests['test_sha256'], *[x for x in source_hashes() if x.startswith('experiments/top020/')]]:
        destination = output/'measured_sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
    manifest = dict(git_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
        cwd=ROOT, text=True).strip(), command=sys.argv, source_sha256=source_hashes(),
        input_sha256={str(x.relative_to(output)): p.digest(x) for x in inputs.iterdir()},
        historical_input_sha256={str(x.relative_to(ROOT)): p.digest(x) for x in sources.values()},
        central_control=central, numerical_workers=1, blas_threads=1)
    write(output/'manifest.json', manifest)
    write(output/'central_regression_verification.json', central)
    return initial, observed, evaluation, scene, spec, control, solve


def continuation_start(state, control, solve):
    """Pure count-independent handoff; no truth, scene or evaluation argument."""
    if state is None:
        raise m.NumericalFailure('empty automatic topology endpoint')
    padded = p.padded(state)
    delta = max(float(np.max(np.linalg.norm(a-b, axis=1)))
        for a, b in zip(p.boundary_points(state), p.boundary_points(padded)))
    require(delta <= 1e-10 and state.component_ids == padded.component_ids,
            'padding changed automatic geometry or IDs')
    if not p.feasible(padded, NODES, solve, control.minimum_component_radius_m):
        raise m.NumericalFailure('fresh endpoint infeasible at continuation nodes')
    optimizer = replace(p._optimizer_config(padded, control), loss_tolerance=1e-14)
    return padded, optimizer, delta


def topology_checks(output, control):
    rows = [json.loads(line) for line in (output/'trajectory.jsonl').read_text().splitlines()]
    require(bool(rows), 'missing topology accepted trajectory')
    checks = p.benchmark.trajectory_checks([SimpleNamespace(loss=r['loss']) for r in rows],
        read(output/'events.json'), control)
    require(all(checks.values()), 'topology event or monotonicity gate failed')
    return checks


def score_predictions(state, scene, spec, observed, evaluation, predictions):
    geometry = p.benchmark.geometry_metrics(state, scene, spec)
    high, low = predictions[NODES[1]], predictions[NODES[0]]
    train = p.relative(high[:, :4], observed)
    ev = p.relative(high[:, 4:], evaluation)
    differences = p.relative(low, high)
    require(np.all(np.isfinite(np.r_[train, ev, differences])), 'nonfinite endpoint metric')
    gates = dict(count=geometry['component_count'] == geometry['truth_component_count'],
        boundary=geometry['maximum_matched_hausdorff_m'] is not None and
                 geometry['maximum_matched_hausdorff_m'] <= .001,
        iou=geometry['union_iou'] >= .90, original_training=float(train[0]) <= .003,
        evaluation=float(max(ev)) <= .05)
    return dict(state_sha256=m.state_hash(state), geometry=geometry, training_errors=train,
        evaluation_errors=ev, maximum_evaluation_error=float(max(ev)), gates=gates,
        original_gates_pass=all(gates.values()),
        numerical_checks=dict(training_discrepancy=differences[:4], evaluation_discrepancy=differences[4:]),
        numerically_qualified=bool(np.all(differences <= follow.TOLERANCES)),
        aggregate_objectives_by_nodes={str(n): {str(k): .5*float(np.mean(
            p.relative(predictions[n][:, :4], observed)[:k]**2)) for k in (1, 2, 3, 4)} for n in NODES})


def score_endpoint(state, scene, spec, observed, evaluation, solve, ledger, destination):
    with ledger.endpoint_scope():
        ledger.reserve(12)
        predictions = {n: p.prediction(state, follow.FREQUENCIES, n, solve, ledger, 'endpoint') for n in NODES}
    score = score_predictions(state, scene, spec, observed, evaluation, predictions)
    write(destination, dict(state=p.driver.serialize_state(state), state_sha256=m.state_hash(state),
        frequencies_hz=follow.FREQUENCIES, solve_config=asdict(solve),
        predictions={str(n): follow.complex_record(value) for n, value in predictions.items()}, score=score))
    return score


def verify(output):
    manifest = read(output/'manifest.json')
    require(source_hashes() == manifest['source_sha256'], 'measured source changed')
    verified_hashes(output, manifest['input_sha256'])
    verified_hashes(ROOT, manifest['historical_input_sha256'])
    require(verify_central() == manifest['central_control'], 'central control changed')
    return manifest


def seal(output, result):
    try:
        verify(output)
        result['sources_and_inputs_unchanged'] = True
    except Exception as exc:
        result.update(status='IMPLEMENTATION_ERROR', fresh_recovery_pass=False,
            sources_and_inputs_unchanged=False, integrity_error=str(exc))
    write(output/'result.json', result)
    write(output/'artifact_manifest.json', {str(x.relative_to(output)): p.digest(x)
        for x in sorted(output.rglob('*')) if x.is_file() and x.name != 'artifact_manifest.json'})
    return result


def run(output, validation):
    initial, observed, evaluation, scene, spec, control, solve = prepare(output, validation)
    topology_ledger = follow.TopologyLedger(cap=4000, seconds=600)
    continuation_ledger = None
    topology_work = None
    result = dict(status='IN_PROGRESS', fresh_circle_start=True, supplied_target_count=False,
        archived_optimized_state_used=False, fresh_recovery_pass=False)
    try:
        topology_ledger.started = topology_ledger.clock()
        with topology_ledger.instrument():
            state = follow.topology_prefix(initial, p.training_data(p.TRAIN[:1], observed[:, :1]),
                control, solve, topology_ledger, output/'topology')
        topology_work = topology_ledger.snapshot()
        terminal = read(output/'topology/terminal.json')
        require(sum(topology_work['completed'].values()) ==
            terminal['controller_work']['totals']['bie_frequency_solve_count'], 'topology work mismatch')
        result['topology_checks'] = topology_checks(output/'topology', control)
        state, optimizer, delta = continuation_start(state, control, solve)
        write(output/'handoff.json', dict(state=p.driver.serialize_state(state), state_sha256=m.state_hash(state),
            source_state_sha256=m.state_hash(terminal['final_state']), supplied_target_count=False,
            zero_padding_maximum_point_change_m=delta, optimizer=asdict(optimizer), nodes=NODES))
        continuation_ledger = m.Ledger(cap=8012, seconds=7200)
        (output/'continuation').mkdir()
        def scorer(state):
            destination = (output/'initial_endpoint_predictions.json' if continuation_ledger.stage is None else
                output/'continuation'/f'stage_{continuation_ledger.stage}'/'endpoint_predictions.json')
            return score_endpoint(state, scene, spec, observed, evaluation, solve, continuation_ledger, destination)
        with continuation_ledger.instrument():
            initial_score = scorer(state)
            if not initial_score['numerically_qualified']:
                raise m.NumericalFailure('fresh automatic endpoint fails numerical qualification')
            schedule = m.run_schedule(state, 'F', observed, NODES, solve, optimizer,
                control.minimum_component_radius_m, continuation_ledger, output/'continuation',
                initial_score, scorer, stage_plan=STAGE_PLAN)
        result.update(status=schedule['status'], schedule=schedule,
            fresh_recovery_pass=bool(schedule['schedule_complete'] and schedule['complete_effective_exposure']
                and schedule['numerically_qualified'] and schedule['reconstruction_gates_pass']
                and all(result['topology_checks'].values())))
    except Exception as exc:
        result.update(status='HARD_STOP', reason=getattr(exc, 'code', type(exc).__name__),
            detail=str(exc), traceback=traceback.format_exc())
    result['topology_work'] = topology_ledger.snapshot() if topology_work is None else topology_work
    result['continuation_work'] = None if continuation_ledger is None else continuation_ledger.snapshot()
    work = [result['topology_work']] + ([] if continuation_ledger is None else [result['continuation_work']])
    result['total_attempted_frequency_calls'] = sum(w['total_attempted'] for w in work)
    result['completed_frequency_solves'] = sum(sum(w['completed'].values()) for w in work)
    result['geometry_refused_calls'] = sum(w['calls'].get('preserved_candidate_refusals', 0) for w in work)
    result['failed_or_refused_calls'] = sum(sum(w['failed'].values()) for w in work)
    result['active_wall_seconds'] = sum(w['active_wall_seconds'] for w in work)
    return seal(output, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    args = parser.parse_args()
    require(all(os.environ.get(key) == '1' for key in
        ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')), 'single-thread BLAS required')
    result = run(args.output.resolve(), args.validation.resolve())
    print(json.dumps({key: result[key] for key in ('status', 'fresh_recovery_pass',
        'total_attempted_frequency_calls', 'completed_frequency_solves', 'geometry_refused_calls')}), flush=True)
    return 0 if result['status'] == 'COMPLETED_SCHEDULE' else 1


if __name__ == '__main__':
    sys.exit(main())
