"""TOP-022: fresh H followed immediately by the full four-frequency objective."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top020 import run as base

follow, m, p = base.follow, base.m, base.p
read, write, require = base.read, base.write, base.require
SCENE, NODES = base.SCENE, base.NODES
STAGE_PLAN = ((4, 8000),)
PLAN = ROOT/'docs/iterations/topology/iteration_14/03_plan.md'
COMPARISON = ROOT/'results/validation/topology/TOP-020-20260915-153359-fresh-two-stars'


def source_hashes():
    return {**base.source_hashes(), **{str(x.relative_to(ROOT)): p.digest(x)
        for x in sorted(Path(__file__).parent.glob('*.py'))}}


def comparison_record(directory=COMPARISON):
    base.verified_hashes(directory, read(directory/'artifact_manifest.json'))
    contract, result = read(directory/'contract.json'), read(directory/'result.json')
    verification = read(directory/'verification.json')
    require(contract['experiment'] == 'TOP-020' and contract['scene'] == SCENE and
        contract['stage_plan'] == [list(x) for x in follow.FULL_PLAN], 'wrong comparison protocol')
    require(result['status'] == 'COMPLETED_SCHEDULE' and not result['fresh_recovery_pass'] and
        result['sources_and_inputs_unchanged'] and verification['status'] == 'PASS' and
        not verification['fresh_recovery_pass'], 'comparison is not the verified completed negative')
    return dict(path=os.path.relpath(directory, ROOT),
        artifact_manifest_sha256=p.digest(directory/'artifact_manifest.json'),
        result_sha256=p.digest(directory/'result.json'),
        verification_sha256=p.digest(directory/'verification.json'),
        topology_state_sha256=m.state_hash(read(directory/'topology/terminal.json')['final_state']),
        role='protocol comparison and fresh-prefix reproducibility; never a fitting initialization',
        new_physical_solves=0)


def check_fresh_prefix(state, comparison):
    require(m.state_hash(state) == comparison['topology_state_sha256'],
            'fresh H endpoint differs from the frozen TOP-020 comparison')
    return dict(status='PASS', computed_state_sha256=m.state_hash(state),
        comparison_state_sha256=comparison['topology_state_sha256'], archived_state_used_for_fitting=False)


def prepare(output, validation):
    require(not output.exists(), 'output must be fresh')
    tests = read(validation)
    require(tests['status'] == 'PASS' and tests['source_sha256'] == source_hashes(),
            'pre-dispatch tests do not qualify current sources')
    base.verified_hashes(ROOT, tests['test_sha256'])
    require(p.digest(validation.parent/tests['log']) == tests['log_sha256'], 'test log changed')
    comparison, central = comparison_record(), base.verify_central()
    output.mkdir(parents=True, exist_ok=False)
    inputs = output/'inputs'; inputs.mkdir()
    sources = {'scene_spec.json': p.DATA/'scene_spec.json',
        'initial_state.json': p.DATA/'scenes'/SCENE/'initial_state.json',
        'observations.json': follow.HISTORY/'inputs'/SCENE/'observations.json',
        'training_observations.json': follow.HISTORY/'inputs'/SCENE/'training_observations.json'}
    for name, source in sources.items():
        shutil.copyfile(source, inputs/name)
    initial, observed, evaluation, scene, spec = base.load_inputs(inputs)
    control = p.benchmark.controller_config(spec, 'H')
    solve = p.driver.baseline.iteration01_solve_config()
    write(output/'contract.json', dict(experiment='TOP-022',
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
        numerical_workers=1, blas_threads=1, owner='Codex /root', independent_review=False,
        intervention='all four training frequencies immediately; same total budget allocated to one stage'))
    for source, name in [(PLAN, 'approved_plan.md'), (validation, 'pre_dispatch_validation.json'),
            (validation.parent/tests['log'], 'pre_dispatch_tests.log'),
            (Path(__file__).parent/'implementation_review.md', 'implementation_review.md')]:
        shutil.copyfile(source, output/name)
    for name in {*tests['test_sha256'], *[n for n in source_hashes() if n.startswith('experiments/')]}:
        destination = output/'measured_sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
    write(output/'manifest.json', dict(git_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
        cwd=ROOT, text=True).strip(), command=sys.argv, source_sha256=source_hashes(),
        input_sha256={str(x.relative_to(output)): p.digest(x) for x in inputs.iterdir()},
        historical_input_sha256={str(x.relative_to(ROOT)): p.digest(x) for x in sources.values()},
        central_control=central, staged_comparison=comparison, numerical_workers=1, blas_threads=1))
    write(output/'central_regression_verification.json', central)
    write(output/'staged_comparison.json', comparison)
    return initial, observed, evaluation, scene, spec, control, solve, comparison


def verify(output):
    manifest = read(output/'manifest.json')
    require(source_hashes() == manifest['source_sha256'], 'measured source changed')
    base.verified_hashes(output, manifest['input_sha256'])
    base.verified_hashes(ROOT, manifest['historical_input_sha256'])
    require(base.verify_central() == manifest['central_control'], 'central control changed')
    require(comparison_record() == manifest['staged_comparison'], 'staged comparison changed')
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
    initial, observed, evaluation, scene, spec, control, solve, comparison = prepare(output, validation)
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
        result['topology_checks'] = base.topology_checks(output/'topology', control)
        result['fresh_prefix_reproducibility'] = check_fresh_prefix(state, comparison)
        state, optimizer, delta = base.continuation_start(state, control, solve)
        write(output/'handoff.json', dict(state=p.driver.serialize_state(state), state_sha256=m.state_hash(state),
            source_state_sha256=m.state_hash(terminal['final_state']), supplied_target_count=False,
            zero_padding_maximum_point_change_m=delta, optimizer=asdict(optimizer), nodes=NODES))
        continuation_ledger = m.Ledger(cap=8012, seconds=7200)
        (output/'continuation').mkdir()
        def scorer(state):
            destination = (output/'initial_endpoint_predictions.json' if continuation_ledger.stage is None else
                output/'continuation'/f'stage_{continuation_ledger.stage}'/'endpoint_predictions.json')
            return base.score_endpoint(state, scene, spec, observed, evaluation, solve, continuation_ledger, destination)
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    args = parser.parse_args()
    require(all(os.environ.get(key) == '1' for key in
        ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')), 'single-thread BLAS required')
    result = run(args.output.resolve(), args.validation.resolve())
    print(json.dumps({key: result[key] for key in ('status', 'fresh_recovery_pass',
        'total_attempted_frequency_calls', 'completed_frequency_solves', 'geometry_refused_calls')}), flush=True)
    sys.exit(0 if result['status'] == 'COMPLETED_SCHEDULE' else 1)
