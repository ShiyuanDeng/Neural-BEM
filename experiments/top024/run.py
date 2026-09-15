"""TOP-024: matched archived-terminal continuations, differing in initial damping."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top023 import run as diagnostic

m, p, base = diagnostic.m, diagnostic.p, diagnostic.base
read, write, require = diagnostic.read, diagnostic.write, diagnostic.require
DIAGNOSTIC = ROOT/'results/validation/topology/TOP-023-20260915-181302-terminal-model'
HISTORY = diagnostic.HISTORY
PLAN = ROOT/'docs/iterations/topology/iteration_16/03_plan.md'
DAMPINGS = {'A': diagnostic.DAMPINGS[0], 'B': .01}
WITNESSES = {'A': 'baseline_next', 'B': 'damping_1e-2'}
CAP, SECONDS, MAX_UPDATES = 4000, 3600, 12
NODES = (256, 512)


def source_hashes():
    return {**diagnostic.source_hashes(), **{str(x.relative_to(ROOT)): p.digest(x)
        for x in sorted(Path(__file__).parent.glob('*.py'))}}


def release_gate():
    diagnostic.verify(DIAGNOSTIC)
    base.verified_hashes(DIAGNOSTIC, read(DIAGNOSTIC/'artifact_manifest.json'))
    result, verified = read(DIAGNOSTIC/'result.json'), read(DIAGNOSTIC/'verification.json')
    require(result['status'] == 'COMPLETED_DIAGNOSTIC' and result['sources_and_inputs_unchanged']
        and result['operational_improvement'] and verified['status'] == 'PASS'
        and verified['operational_improvement'] and 'damping_1e-2' in verified['eligible_arms'],
        'TOP-023 does not release the reset comparison')
    return {str((DIAGNOSTIC/name).relative_to(ROOT)): p.digest(DIAGNOSTIC/name) for name in
        ('artifact_manifest.json', 'result.json', 'verification.json', 'inputs.json', 'arms.json')}


def arm_config(config, arm):
    require(arm in DAMPINGS, 'unknown arm')
    return replace(m.rt.ParameterFDConfig(**config), initial_damping=DAMPINGS[arm], max_iterations=MAX_UPDATES)


def prepare(output, validation):
    require(not output.exists(), 'output must be fresh')
    tests = read(validation)
    require(tests['status'] == 'PASS' and tests['source_sha256'] == source_hashes(), 'tests do not qualify current source')
    base.verified_hashes(ROOT, tests['test_sha256'])
    require(p.digest(validation.parent/tests['log']) == tests['log_sha256'], 'test log changed')
    history = release_gate()
    output.mkdir(parents=True)
    inputs = output/'inputs'; inputs.mkdir()
    for name in ('scene_spec.json', 'initial_state.json', 'observations.json', 'training_observations.json'):
        source = HISTORY/'inputs'/name
        shutil.copyfile(source, inputs/name)
        history[str(source.relative_to(ROOT))] = p.digest(source)
    old = read(DIAGNOSTIC/'inputs.json')
    write(inputs/'terminal_state.json', old['state'])
    write(inputs/'optimizer.json', old['optimizer'])
    write(output/'arm_configs.json', {arm: asdict(arm_config(old['optimizer'], arm)) for arm in DAMPINGS})
    initial_predictions = HISTORY/'continuation/stage_4/endpoint_predictions.json'
    shutil.copyfile(initial_predictions, output/'initial_endpoint_predictions.json')
    history[str(initial_predictions.relative_to(ROOT))] = p.digest(initial_predictions)
    witnesses = {}
    for arm, label in WITNESSES.items():
        row = next(x for x in read(DIAGNOSTIC/'arms.json') if x['label'] == label)
        candidate = next(x for x in row['attempts'] if x.get('accepted'))
        witnesses[arm] = dict(state=candidate['state'], state_sha256=candidate['state_sha256'],
            production_loss=candidate['losses']['256'], initial_damping=row['damping'])
    write(output/'witnesses.json', witnesses)
    write(output/'contract.json', dict(experiment='TOP-024', approval='2026-09-15 user remaining-work instruction',
        arms=DAMPINGS, maximum_updates=MAX_UPDATES, nodes=NODES, stage_plan=[[4, CAP]],
        per_arm_solve_cap=CAP, per_arm_seconds=SECONDS, total_new_solve_cap=2*CAP,
        outer_worker_seconds=3900, termination_grace_seconds=10, numerical_workers=2, blas_threads=1,
        archived_fixed_topology_start=True, fresh_circle_start=False, diagnostic_candidate_used_for_initialization=False,
        initial_state_sha256=old['state_sha256'], reused_initial_endpoint_systems=12,
        first_step_absolute_coefficient_tolerance_m=1e-10, first_step_relative_loss_tolerance=1e-8,
        owner='Codex /root', independent_review=False))
    for source, name in [(PLAN, 'approved_plan.md'), (validation, 'pre_dispatch_validation.json'),
            (validation.parent/tests['log'], 'pre_dispatch_tests.log'),
            (Path(__file__).parent/'implementation_review.md', 'implementation_review.md')]:
        shutil.copyfile(source, output/name)
    for name in {*tests['test_sha256'], *[x for x in source_hashes() if x.startswith('experiments/')]}:
        destination = output/'measured_sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT/name, destination)
    frozen = [x for x in output.rglob('*') if x.is_file() and 'measured_sources' not in x.parts]
    write(output/'manifest.json', dict(git_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
        cwd=ROOT, text=True).strip(), command=sys.argv, source_sha256=source_hashes(), historical_sha256=history,
        input_sha256={str(x.relative_to(output)): p.digest(x) for x in frozen}))
    load_inputs(output)
    return dict(status='PREPARED', new_physical_solves=0)


def load_inputs(output):
    _, observed, evaluation, scene, spec = base.load_inputs(output/'inputs')
    state = p.driver.deserialize_state(read(output/'inputs/terminal_state.json'))
    endpoint = read(output/'initial_endpoint_predictions.json')
    require(m.state_hash(state) == endpoint['state_sha256'] == read(output/'contract.json')['initial_state_sha256'],
            'shared terminal initialization mismatch')
    require(endpoint['score']['numerically_qualified'], 'shared initial score is not qualified')
    solve = p.driver.baseline.iteration01_solve_config()
    require(asdict(solve) == endpoint['solve_config'] and p.feasible(state, NODES, solve, .008), 'initial model/geometry mismatch')
    return state, observed, evaluation, scene, spec, solve, endpoint


def verify(output):
    manifest = read(output/'manifest.json')
    require(source_hashes() == manifest['source_sha256'], 'measured source changed')
    base.verified_hashes(ROOT, manifest['historical_sha256'])
    base.verified_hashes(output, manifest['input_sha256'])


def first_step_check(state, loss, witness):
    reference = p.driver.deserialize_state(witness['state'])
    require(state.component_ids == reference.component_ids, 'first-step component IDs changed')
    coefficient_delta = float(np.max(np.abs(state.parameter_vector()-reference.parameter_vector())))
    geometry_delta = max(float(np.max(np.linalg.norm(a-b, axis=1)))
        for a, b in zip(p.boundary_points(state), p.boundary_points(reference)))
    loss_error = abs(loss-witness['production_loss'])/max(abs(witness['production_loss']), np.finfo(float).tiny)
    return dict(status='PASS' if max(coefficient_delta, geometry_delta) <= 1e-10 and loss_error <= 1e-8 else 'FAIL',
        state_sha256=m.state_hash(state), witness_state_sha256=witness['state_sha256'],
        maximum_coefficient_difference_m=coefficient_delta, maximum_boundary_point_difference_m=geometry_delta,
        relative_objective_difference=loss_error, state=p.driver.serialize_state(state), production_loss=loss)


@contextmanager
def first_step_guard(witness, destination):
    """Preserve the existing checkpoint before checking a training-only witness."""
    original = m.rt.run_multiradial_fd_inverse
    def guarded(*args, **kwargs):
        callback = kwargs['accepted_state_callback']
        def accepted(iteration, evaluation):
            callback(iteration, evaluation)
            if iteration == 1:
                check = first_step_check(evaluation.state, evaluation.loss, witness)
                write(destination, check)
                require(check['status'] == 'PASS', 'first step differs from the frozen TOP-023 witness')
        kwargs['accepted_state_callback'] = accepted
        return original(*args, **kwargs)
    m.rt.run_multiradial_fd_inverse = guarded
    try: yield
    finally: m.rt.run_multiradial_fd_inverse = original


def run_arm(output, arm):
    require(arm in DAMPINGS, 'unknown arm')
    verify(output)
    state, observed, evaluation, scene, spec, solve, endpoint = load_inputs(output)
    folder = output/'runs'/arm; folder.mkdir(parents=True, exist_ok=False)
    optimizer = arm_config(read(output/'inputs/optimizer.json'), arm)
    require(m.state_hash(asdict(optimizer)) == m.state_hash(read(output/'arm_configs.json')[arm]),
            'frozen arm configuration changed')
    write(folder/'arm_config.json', dict(arm=arm, optimizer=asdict(optimizer), initial_state_sha256=m.state_hash(state)))
    witness = read(output/'witnesses.json')[arm]
    ledger = m.Ledger(cap=CAP, seconds=SECONDS)
    result = dict(arm=arm, archived_fixed_topology_start=True, fresh_recovery_claim=False,
        reconstruction_pass=False, initial_state_sha256=m.state_hash(state))
    try:
        # Only training error/numerical status enter the schedule; the saved
        # historical truth/development score is not an optimizer input.
        initial_score = {k:endpoint['score'][k] for k in ('training_errors', 'numerically_qualified')}
        def scorer(s):
            return base.score_endpoint(s, scene, spec, observed, evaluation, solve, ledger,
                folder/'stage_4/endpoint_predictions.json')
        with ledger.instrument(), first_step_guard(witness, folder/'first_step_reproducibility.json'):
            schedule = m.run_schedule(state, 'F', observed, NODES, solve, optimizer, .008,
                ledger, folder, initial_score, scorer, stage_plan=((4, CAP),))
        result.update(status=schedule['status'], schedule=schedule,
            reconstruction_pass=bool(schedule['schedule_complete'] and schedule['complete_effective_exposure']
                and schedule['numerically_qualified'] and schedule['reconstruction_gates_pass']))
        if schedule['schedule_complete']:
            require((folder/'first_step_reproducibility.json').exists() and
                read(folder/'first_step_reproducibility.json')['status'] == 'PASS', 'missing first-step verification')
    except Exception as exc:
        result.update(status='HARD_STOP', reconstruction_pass=False, reason=getattr(exc, 'code', type(exc).__name__),
            detail=str(exc), traceback=traceback.format_exc())
    result['work'] = ledger.snapshot()
    try:
        verify(output); result['sources_and_inputs_unchanged'] = True
    except Exception as exc:
        result.update(status='IMPLEMENTATION_ERROR', reconstruction_pass=False, sources_and_inputs_unchanged=False, integrity_error=str(exc))
    write(folder/'result.json', result)
    write(folder/'artifact_manifest.json', {str(x.relative_to(folder)): p.digest(x)
        for x in sorted(folder.rglob('*')) if x.is_file() and x.name != 'artifact_manifest.json'})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'arm'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validation', type=Path)
    parser.add_argument('--arm', choices=('A', 'B'))
    args = parser.parse_args()
    if args.mode == 'prepare':
        require(args.validation is not None, 'validation required')
        print(json.dumps(prepare(args.output.resolve(), args.validation.resolve())))
    else:
        require(args.arm is not None, 'arm required')
        require(all(os.environ.get(k) == '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')), 'BLAS must be one thread')
        result = run_arm(args.output.resolve(), args.arm)
        print(json.dumps(dict(arm=args.arm, status=result['status'], reconstruction_pass=result['reconstruction_pass'],
            charged_calls=result['work']['total_attempted'])), flush=True)
        sys.exit(0 if result['status'] == 'COMPLETED_SCHEDULE' else 1)
