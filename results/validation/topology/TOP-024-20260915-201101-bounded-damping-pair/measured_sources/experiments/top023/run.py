"""TOP-023: frozen training-model diagnosis; never runs an inverse."""
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

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top022 import run as previous
from experiments.top018 import run as qualified
import run_top016_screen as screen

m, p, base = previous.m, previous.p, previous.base
read, write, require = previous.read, previous.write, previous.require
HISTORY = ROOT/'results/validation/topology/TOP-022-20260915-165552-fresh-direct-two-stars'
PLAN = ROOT/'docs/iterations/topology/iteration_15/03_plan.md'
NODES, CAP, SECONDS = (256, 512), 600, 1200
DAMPINGS = (3.138105960899997e-15, 1e-6, 1e-4, 1e-2)
TOLERANCES = np.array([1e-5, 1e-7, 1e-7, 1e-7])


def source_hashes():
    return {**previous.source_hashes(), 'experiments/top018/run.py': p.digest(ROOT/'experiments/top018/run.py'),
        **{str(x.relative_to(ROOT)): p.digest(x) for x in sorted(Path(__file__).parent.glob('*.py'))}}


def terminal_inputs():
    previous.verify(HISTORY)
    base.verified_hashes(HISTORY, read(HISTORY/'artifact_manifest.json'))
    result, contract = read(HISTORY/'result.json'), read(HISTORY/'contract.json')
    require(contract['experiment'] == 'TOP-022' and result['status'] == 'COMPLETED_SCHEDULE'
        and not result['fresh_recovery_pass'] and result['sources_and_inputs_unchanged']
        and read(HISTORY/'verification.json')['status'] == 'PASS', 'terminal evidence is not qualified TOP-022 negative')
    folder = HISTORY/'continuation/stage_4'
    terminal, endpoint = read(folder/'terminal.json'), read(folder/'endpoint_predictions.json')
    trajectory = [json.loads(x) for x in (folder/'trajectory.jsonl').read_text().splitlines()]
    config = read(folder/'optimizer.json')
    h = m.state_hash(terminal['final_state'])
    require(h == endpoint['state_sha256'] == terminal['gradient']['state_sha256'] == trajectory[-1]['state_sha256'],
            'terminal state/model identity mismatch')
    require(terminal['optimizer_stop'] == 'maximum_iterations' and terminal['gradient']['iteration'] == 22,
            'unexpected terminal stopping/model')
    next_damping = max(trajectory[-1]['damping']*config['config']['damping_decrease'], np.finfo(float).tiny)
    require(np.isclose(next_damping, DAMPINGS[0], rtol=1e-14, atol=0), 'next damping differs from declared control')
    # Strip development columns and scores before entering the numerical API.
    predictions = {n: previous.follow.complex_record(qualified.complex_array(endpoint['predictions'][str(n)])[:, :4])
        for n in NODES}
    training = read(HISTORY/'inputs/training_observations.json')
    inputs = dict(state=terminal['final_state'], state_sha256=h, training=training,
        base_predictions=predictions, optimizer=config['config'], solve_config=endpoint['solve_config'],
        saved_gradient=terminal['gradient'], next_damping=next_damping, minimum_radius_m=.008,
        base_objectives={n: endpoint['score']['aggregate_objectives_by_nodes'][str(n)]['4'] for n in NODES})
    names = ['artifact_manifest.json', 'result.json', 'verification.json', 'contract.json',
        'inputs/training_observations.json', *['continuation/stage_4/'+n for n in
        ('terminal.json', 'endpoint_predictions.json', 'optimizer.json', 'trajectory.jsonl')]]
    return inputs, {str((HISTORY/name).relative_to(ROOT)): p.digest(HISTORY/name) for name in names}


def prepare(output, validation):
    require(not output.exists(), 'output must be fresh')
    tests = read(validation)
    require(tests['status'] == 'PASS' and tests['source_sha256'] == source_hashes(), 'tests do not qualify current sources')
    base.verified_hashes(ROOT, tests['test_sha256'])
    require(p.digest(validation.parent/tests['log']) == tests['log_sha256'], 'test log changed')
    inputs, history = terminal_inputs()
    output.mkdir(parents=True)
    write(output/'inputs.json', inputs)
    write(output/'contract.json', dict(experiment='TOP-023', approval='user remaining-work instruction, 2026-09-15',
        archived_terminal_diagnostic=True, inverse_executed=False, full_suite_released=False,
        nodes=NODES, frequencies_hz=p.TRAIN, fd_steps=[1e-4, 5e-5], dampings=DAMPINGS,
        selected_directions='argmax absolute saved reduced gradient, then last basis row (first if duplicate)',
        gradient_replay_rtol=1e-5, gradient_replay_atol=1e-8, derivative_relative_stability=.25,
        signal_floor_multiplier=5, maximum_backtracks=7, solve_cap=CAP, wall_seconds=SECONDS,
        worst_case_calls=580, reused_training_prediction_systems=8, numerical_workers=1, blas_threads=1,
        operational_gain_multiplier=2, owner='Codex /root', independent_review=False))
    for source, name in [(PLAN, 'approved_plan.md'), (validation, 'pre_dispatch_validation.json'),
            (validation.parent/tests['log'], 'pre_dispatch_tests.log'),
            (Path(__file__).parent/'implementation_review.md', 'implementation_review.md')]:
        shutil.copyfile(source, output/name)
    for name in {*tests['test_sha256'], *[x for x in source_hashes() if x.startswith('experiments/')]}:
        destination = output/'measured_sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT/name, destination)
    write(output/'manifest.json', dict(git_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
        cwd=ROOT, text=True).strip(), command=sys.argv, source_sha256=source_hashes(), historical_sha256=history,
        input_sha256={name: p.digest(output/name) for name in ('inputs.json', 'contract.json', 'approved_plan.md')},
        numerical_workers=1, blas_threads=1))
    return read(output/'inputs.json')


def verify(output):
    manifest = read(output/'manifest.json')
    require(source_hashes() == manifest['source_sha256'], 'measured source changed')
    base.verified_hashes(ROOT, manifest['historical_sha256'])
    base.verified_hashes(output, manifest['input_sha256'])


def selected_rows(saved_gradient):
    first = int(np.argmax(np.abs(saved_gradient))); last = len(saved_gradient)-1
    return (first, last if first != last else 0)


def lm_proposal(matrix, gradient, basis, max_steps, damping):
    normal = matrix.T@matrix
    scaling = np.maximum(np.diag(normal), 1.)
    bounds = np.min(np.where(np.abs(basis)>1e-12,
        max_steps/np.maximum(np.abs(basis), 1e-12), np.inf), axis=1)
    raw = np.linalg.solve(normal+damping*np.diag(scaling), -gradient)
    clipped = np.clip(raw, -bounds, bounds)
    return dict(raw_reduced_step=raw, reduced_step=clipped, coefficient_step=basis.T@clipped,
        reduced_bounds=bounds, active_bounds=np.abs(raw)>bounds, normal_scaling=scaling)


def operational_gate(arms):
    control = arms[0]
    eligible = [a['label'] for a in arms[1:] if a.get('accepted') and
        (not control.get('accepted') or (a['accepted']['production_gain'] >= 2*control['accepted']['production_gain']
            and a['candidate_calls'] <= control['candidate_calls']))]
    return dict(passed=bool(eligible), eligible_arms=eligible,
        scope='releases only a separately declared bounded continuation comparison; no recovery or full-suite claim')


def audit(inputs, ledger, output):
    """Only the frozen state, training samples/predictions and model settings enter."""
    state = p.driver.deserialize_state(inputs['state'])
    require(m.state_hash(state) == inputs['state_sha256'], 'input state hash mismatch')
    observed = np.array(inputs['training']['observed_real'])+1j*np.array(inputs['training']['observed_imag'])
    require(observed.shape == (24, 4) and inputs['training']['frequencies_hz'] == list(p.TRAIN), 'training input mismatch')
    data = p.training_data(p.TRAIN, observed)
    residual = lambda value: p.normalized_complex_residual(value, observed, data.frequency_weights)[0]
    solve = p.driver.baseline.iteration01_solve_config()
    require(asdict(solve) == inputs['solve_config'], 'solve configuration mismatch')
    optimizer = m.rt.ParameterFDConfig(**inputs['optimizer'])
    require(optimizer.max_backtracks == 7 and optimizer.finite_difference_steps == 1e-4
        and inputs['minimum_radius_m'] == .008 and inputs['next_damping'] == DAMPINGS[0],
        'optimizer/probe contract mismatch')
    basis = state.gauge_tangent_basis(); q = len(basis)
    require(q == 34 and np.allclose(basis@basis.T, np.eye(q), rtol=0, atol=1e-12), 'unexpected gauge coordinates')
    predictions, aliases, refusals, estimates = {}, {}, [], {}
    model = dict(state_sha256=m.state_hash(state), basis=basis, estimates=estimates,
        selected_direction_checks=[], selected_directions_qualified=False,
        coordinate_convention='orthonormal gauge basis in original metre-valued Cartesian coefficients')
    arms = [dict(label=label, damping=damping, status='NOT_STARTED', attempts=[], candidate_calls=0)
        for label, damping in zip(('baseline_next', 'damping_1e-6', 'damping_1e-4', 'damping_1e-2'), DAMPINGS)]
    def save():
        write(output/'predictions.json', dict(records=predictions, aliases=aliases, refusals=refusals))
        write(output/'model.json', model); write(output/'arms.json', arms)
    def predict(s, n, category, label, repeat=False):
        key = f'{m.state_hash(s)}:{n}'+(':repeat' if repeat else '')
        if key not in predictions:
            ledger.reserve(4)
            value = p.prediction(s, p.TRAIN, n, solve, ledger, category)
            predictions[key] = dict(state=p.driver.serialize_state(s), state_sha256=m.state_hash(s), nodes=n,
                prediction=previous.follow.complex_record(value), origin='new', category=category)
        else:
            ledger.calls['cache_hits'] += 1
            value = qualified.complex_array(predictions[key]['prediction'])
        aliases[label] = key
        return value
    def trial(step, label):
        try:
            s = state.incremented(step).polar_angle_gauge_fixed()[0]
            if not p.feasible(s, NODES, solve, inputs['minimum_radius_m']):
                refusals.append(dict(label=label, reason='geometry or radius floor')); return None
            return s
        except ValueError as exc:
            refusals.append(dict(label=label, reason=str(exc))); return None
    bases = {n: qualified.complex_array(inputs['base_predictions'][str(n)]) for n in NODES}
    base_res = {n: residual(value) for n, value in bases.items()}
    for n in NODES:
        key = f'{m.state_hash(state)}:{n}'
        predictions[key] = dict(state=inputs['state'], state_sha256=m.state_hash(state), nodes=n,
            prediction=inputs['base_predictions'][str(n)], origin='reused_TOP022')
        aliases[f'base:{n}'] = key
        require(np.isclose(.5*float(base_res[n]@base_res[n]), inputs['base_objectives'][str(n)], rtol=1e-10, atol=1e-16),
                'base objective does not replay')
    model['base_residuals'] = base_res
    def estimate(index, h, n):
        key = f'{index}:{h:g}:{n}'
        if key in estimates: return np.asarray(estimates[key]['derivative'])
        sides, labels = {}, {}
        for sign in (-1, 1):
            label = f'{key}:{sign}'
            s = trial(sign*h*basis[index], label)
            if s is not None:
                sides[sign] = residual(predict(s, n, 'derivative', label)); labels[str(sign)] = label
        derivative, stencil = qualified.quotient(base_res[n], sides, h)
        estimates[key] = dict(derivative=derivative, stencil=stencil, side_labels=labels)
        return derivative
    try:
        ledger.reserve(2*q*4)
        matrix = np.column_stack([estimate(i, 1e-4, 256) for i in range(q)])
        gradient = matrix.T@base_res[256]
        saved_gradient = basis@np.array(inputs['saved_gradient']['coefficient_gradient'])
        model.update(jacobian=matrix, reduced_gradient=gradient, saved_reduced_gradient=saved_gradient,
            singular_values=np.linalg.svd(matrix, compute_uv=False),
            gradient_replay_pass=bool(np.allclose(gradient, saved_gradient, rtol=1e-5, atol=1e-8)),
            selected_rows=selected_rows(saved_gradient))
        save()
        require(model['gradient_replay_pass'], 'saved terminal gradient does not replay')
        print('full terminal model replayed', ledger.total, flush=True)
        ledger.reserve(52)
        repeated = residual(predict(state, 256, 'repeatability', 'repeat', repeat=True))
        repeat = float(np.linalg.norm(repeated-base_res[256])); model['repeatability_residual_norm'] = repeat
        for i in model['selected_rows']:
            physical = screen.normal_rms(state, state.incremented(basis[i]*1e-5))/1e-5
            require(physical > 1e-10, 'selected direction is physically trivial')
            values = {(n, h): estimate(i, h, n) for n in NODES for h in (1e-4, 5e-5)}
            floor = max(repeat, 64*np.finfo(float).eps,
                5e-5*float(np.linalg.norm(values[256, 5e-5]-values[512, 5e-5])))
            checks = [dict(nodes=n, **qualified.derivative_qualified(values[n, 1e-4], values[n, 5e-5], 5e-5, floor)) for n in NODES]
            model['selected_direction_checks'].append(dict(index=i, normal_rms_per_unit_coefficient=physical,
                checks=checks, passed=all(c['passed'] for c in checks)))
        model['selected_directions_qualified'] = all(c['passed'] for c in model['selected_direction_checks'])
        save()
        if not model['selected_directions_qualified']:
            return dict(status='SELECTED_DIRECTION_GATE_FAILED', operational_improvement=False)
        for arm in arms:
            start = ledger.total
            arm.update(status='RUNNING', **lm_proposal(matrix, gradient, basis,
                optimizer.resolved_max_steps(state.parameter_count), arm['damping']))
            for j in range(optimizer.max_backtracks+1):
                coefficient_step = (2.**-j)*arm['coefficient_step']
                step = (2.**-j)*arm['reduced_step']
                item = dict(backtrack=j, coefficient_step=coefficient_step,
                    relative_step=float(np.linalg.norm(coefficient_step)/max(np.linalg.norm(state.parameter_vector()), 1.)))
                arm['attempts'].append(item)
                if item['relative_step'] <= optimizer.relative_step_tolerance:
                    item['status'] = 'RELATIVE_STEP_REFUSED'; continue
                label = f'{arm["label"]}:{j}'
                s = trial(coefficient_step, label)
                if s is None:
                    item['status'] = 'FEASIBILITY_REFUSED'; continue
                ledger.reserve(8)
                values = {n: predict(s, n, 'candidate_'+arm['label'], f'{label}:{n}') for n in NODES}
                losses = {n: .5*float(residual(v)@residual(v)) for n, v in values.items()}
                discrepancy = p.relative(values[256], values[512])
                item.update(state=p.driver.serialize_state(s), state_sha256=m.state_hash(s), losses=losses,
                    prediction_labels={n: f'{label}:{n}' for n in NODES}, prediction_discrepancy=discrepancy,
                    numerically_qualified=bool(np.all(discrepancy <= TOLERANCES)),
                    linear_predicted_gain=-float(gradient@step),
                    quadratic_predicted_gain=-float(gradient@step)-.5*float(np.linalg.norm(matrix@step)**2),
                    physical_normal_rms_m=screen.normal_rms(state, s),
                    **m.old.acceptance(inputs['base_objectives']['256'], losses[256], inputs['base_objectives']['512'], losses[512]))
                arm['candidate_calls'] = ledger.total-start
                if not item['numerically_qualified']:
                    item['status'] = 'NUMERICAL_OBSTRUCTION'; item['accepted'] = False
                    raise m.NumericalFailure('candidate leaves the declared numerical regime')
                item['status'] = 'ACCEPTED_DIAGNOSTIC_CANDIDATE' if item['accepted'] else 'NO_QUALIFIED_DECREASE'
                if item['accepted']:
                    arm['accepted'] = dict(backtrack=j, state_sha256=item['state_sha256'], production_gain=item['production_gain'])
                    break
            arm.update(status='COMPLETE', candidate_calls=ledger.total-start)
            save(); print(arm['label'], 'calls', arm['candidate_calls'], 'accepted', bool(arm.get('accepted')), flush=True)
        gate = operational_gate(arms)
        return dict(status='COMPLETED_DIAGNOSTIC', operational_improvement=gate['passed'], operational_gate=gate)
    finally:
        save()


def run(output, validation):
    inputs = prepare(output, validation)
    ledger = m.Ledger(cap=CAP, seconds=SECONDS)
    result = dict(inverse_executed=False, full_suite_released=False, archived_terminal_diagnostic=True,
        operational_improvement=False)
    try:
        with ledger.instrument(): result.update(audit(inputs, ledger, output))
    except Exception as exc:
        result.update(status='DIAGNOSTIC_STOP', reason=getattr(exc, 'code', type(exc).__name__),
            detail=str(exc), traceback=traceback.format_exc())
    result['work'] = ledger.snapshot()
    try:
        verify(output); result['sources_and_inputs_unchanged'] = True
    except Exception as exc:
        result.update(status='IMPLEMENTATION_ERROR', operational_improvement=False,
            sources_and_inputs_unchanged=False, integrity_error=str(exc))
    write(output/'result.json', result)
    write(output/'artifact_manifest.json', {str(x.relative_to(output)): p.digest(x)
        for x in sorted(output.rglob('*')) if x.is_file() and x.name != 'artifact_manifest.json'})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    args = parser.parse_args()
    require(all(os.environ.get(k) == '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')), 'BLAS must be one thread')
    result = run(args.output.resolve(), args.validation.resolve())
    print(json.dumps(dict(status=result['status'], operational_improvement=result['operational_improvement'],
        charged_calls=result['work']['total_attempted'])), flush=True)
    sys.exit(0 if result['status'] in ('COMPLETED_DIAGNOSTIC', 'SELECTED_DIRECTION_GATE_FAILED') else 1)
