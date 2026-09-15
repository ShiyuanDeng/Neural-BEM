"""Approved TOP-019: capacity audit and one sequential, matched merge pair."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_top017 as m
import run_top016_screen as screen
from experiments.top018 import run as previous

p = m.p
read, write = m.read, m.write
require = previous.require
solve_config = previous.solve_config
discrepancy = previous.discrepancy
HISTORY = ROOT/'results/validation/topology/TOP-017-20260914-staged-continuation'
ORIGINAL = m.SOURCE/'phase0/inputs/merge/state.json'
SCENE = 'merge'
NODES = (256, 512)
FREQUENCIES = p.TRAIN+p.EVALUATION
TOLERANCES = np.array([1e-5, 1e-7, 1e-7, 1e-7, 1e-5, 1e-5])
STAGE_PLAN = ((1, 1000), (2, 1250), (3, 1750), (4, 4000))
AUDIT_STATES = ('ORIGINAL', 'COMMON', 'WITNESS')
ORIGINAL_HASH = 'ea1512563437fd71226342022cde7d7879b2c8f562627c04bfc30d17990984c3'
WITNESS_HASH = 'c3117d6954da02bb5d15ea48c1c7952c3ea9a894d66de82170e97ce13e87fa35'
INPUT_HASHES = dict(
    original='72f01280d665bd0b50d569dd372d13469f010ddcb536fe978159969b4e675ca6',
    observations='10069a80ed6a704998ccddb3034e1ed491da0b2b7a303a3896859626e459fc0f',
    training='a356db2dcedeb361d341b8718a2e516ee77d12e5fb6458915f5c56259f664645',
    witness='2eb56f1133ca261432b25c5fcc26f8cfe533b43457ef86074372efaf9df6072f')


def source_hashes():
    paths = [Path(previous.__file__), *sorted(Path(__file__).parent.glob('*.py'))]
    return {**m.source_hashes(), **{str(x.relative_to(ROOT)): p.digest(x) for x in paths}}


def validated_inputs():
    """Verify provenance and padding using geometry only; never a physical call."""
    paths = dict(original=ORIGINAL, observations=HISTORY/'inputs/merge/observations.json',
                 training=HISTORY/'inputs/merge/training_observations.json',
                 witness=HISTORY/'phase_a/audit.json')
    for key, path in paths.items():
        require(p.digest(path) == INPUT_HASHES[key], f'frozen {key} input changed')
    historical = {str(path.relative_to(ROOT)): p.digest(path) for path in paths.values()}
    def remember(path):
        historical[str(path.relative_to(ROOT))] = p.digest(path)
        return read(path)
    original = p.driver.deserialize_state(read(ORIGINAL))
    require(m.state_hash(original) == ORIGINAL_HASH, 'wrong original merge start')
    source = ROOT/'results/validation/topology/TOP-008-20260912-feasible-fd/runs/H/merge/metrics.json'
    require(m.state_hash(remember(source)['final_state']) == ORIGINAL_HASH, 'controller source differs')
    for arm in ('S', 'F'):
        require(m.state_hash(remember(m.SOURCE/f'runs/{arm}-merge/stage_1/initial_state.json'))
                == ORIGINAL_HASH, 'historical paired start differs')
    common = p.MultiRadialFourierState(tuple(p.zero_padded_component(c, 17) for c in original.components))
    require(common.component_ids == original.component_ids == ('t001.merge1',), 'component identity changed')
    for old, new in zip(original.components, common.components):
        for name in ('cosine_coefficients', 'sine_coefficients'):
            before, after = getattr(old, name), getattr(new, name)
            require(np.array_equal(before, after[:len(before)]) and np.count_nonzero(after[len(before):]) == 0,
                    f'nonzero extension or changed {name}')
    changes = {str(n): float(np.max(np.linalg.norm(p.boundary_points(original, n)[0]
                - p.boundary_points(common, n)[0], axis=1))) for n in (4096, 8192)}
    require(max(changes.values()) <= 1e-10, 'padding changed geometry')
    witness_record = read(paths['witness'])['merge_projection']['17']
    witness = p.driver.deserialize_state(witness_record['state'])
    require(m.state_hash(witness) == witness_record['state_sha256'] == WITNESS_HASH,
            'capacity witness state changed')
    require(witness_record['evaluation_only'] and not witness_record['used_for_inverse'],
            'capacity witness provenance invalid')
    states = dict(ORIGINAL=original, COMMON=common, WITNESS=witness)
    gauge = {}
    for label, state in states.items():
        fixed, _ = state.polar_angle_gauge_fixed()
        gauge[label] = float(np.max(np.abs(fixed.parameter_vector()-state.parameter_vector())))
        require(gauge[label] < 1e-10, f'{label} gauge mismatch; frozen state not replaced')
    observed, evaluation = m.observations(HISTORY, SCENE)
    original_data, training = read(paths['observations']), read(paths['training'])
    require(observed.shape == (24, 4) and evaluation.shape == (24, 2), 'data shape mismatch')
    require(training['frequencies_hz'] == list(p.TRAIN), 'training frequencies changed')
    require(original_data['frequencies_hz'] == [p.TRAIN[0], *p.EVALUATION], 'evaluation frequencies changed')
    for key in ('observed_real', 'observed_imag'):
        require([row[0] for row in training[key]] == [row[0] for row in original_data[key]], '0.5-GHz column differs')
    for src, key in [(m.SOURCE/'phase1/merge_training_observations.json', 'training'),
                     (m.SOURCE/'phase0/inputs/merge/observations.json', 'observations')]:
        remember(src)
        require(p.digest(src) == INPUT_HASHES[key], 'TOP-016 observation copy differs')
    linked = ROOT/training['acquisition_and_material_source']
    require(remember(linked) == original_data and p.digest(linked) == training['source_sha256'],
            'acquisition provenance mismatch')
    problem = p.driver.baseline._problem(np.array(original_data['frequencies_hz']))
    for key in ('source_points', 'receiver_points', 'eps0', 'mu0'):
        require(np.array_equal(getattr(problem, key), original_data[key]), f'acquisition changed: {key}')
    for key in ('interior', 'exterior'):
        require(asdict(getattr(problem, key)) == original_data[key], f'material changed: {key}')
    strengths = np.array(original_data['source_strengths_real'])+1j*np.array(original_data['source_strengths_imag'])
    require(np.array_equal(problem.source_strengths, strengths), 'source strengths changed')
    spec = remember(HISTORY/'scene_spec.json')
    require(spec == remember(ROOT/'config/topology_scenes_v1.json'), 'scene specification differs')
    require(asdict(solve_config()) == remember(HISTORY/'contract.json')['solve_config'], 'physical solve config differs')
    control = p.TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True, feasible_fd_jacobian=True)
    optimizer = replace(p._optimizer_config(common, control), loss_tolerance=1e-14)
    require(common.parameter_count == optimizer.max_parameters == 70
            and common.gauge_tangent_basis().shape == (33, 70), 'K=17 dimension mismatch')
    require(len(optimizer.max_steps) == 70 and optimizer.max_iterations == 22, 'optimizer accommodation mismatch')
    p.training_data(p.TRAIN, observed)
    provenance = dict(historical_sha256=historical, original_state_sha256=ORIGINAL_HASH,
        common_state_sha256=m.state_hash(common), witness_state_sha256=WITNESS_HASH,
        padding_point_change_m=changes, gauge_coefficient_change=gauge,
        supplied_component_count=True, truth_used_for_inverse=False, historical_prediction_solves_reused=0)
    return states, observed, evaluation, optimizer, provenance


def prepare(bundle, validation):
    bundle.mkdir(parents=True, exist_ok=False)
    states, observed, evaluation, optimizer, provenance = validated_inputs()
    tests = read(validation)
    require(tests['status'] == 'PASS' and tests['source_sha256'] == source_hashes(), 'tests do not qualify source')
    log = validation.parent/tests['log']
    require(p.digest(log) == tests['log_sha256'], 'test log changed')
    dest = bundle/'inputs'/SCENE; dest.mkdir(parents=True)
    for name in ('observations.json', 'training_observations.json'):
        shutil.copyfile(HISTORY/'inputs'/SCENE/name, dest/name)
    for name, label in [('state.json', 'COMMON'), ('original_state.json', 'ORIGINAL'), ('witness_state.json', 'WITNESS')]:
        write(dest/name, p.driver.serialize_state(states[label]))
    write(dest/'optimizer.json', dict(config=asdict(optimizer), minimum_component_radius_m=.008))
    shutil.copyfile(HISTORY/'scene_spec.json', bundle/'scene_spec.json')
    shutil.copyfile(validation, bundle/'pre_dispatch_validation.json')
    shutil.copyfile(log, bundle/'pre_dispatch_tests.log')
    for src, dst in [('docs/iterations/topology/iteration_12/03_plan.md', 'approved_plan.md'),
                     ('experiments/top019/implementation_review.md', 'implementation_review.md')]:
        shutil.copyfile(ROOT/src, bundle/dst)
    write(bundle/'reuse.json', provenance)
    write(bundle/'contract.json', dict(experiment='TOP-019', approval='2026-09-15 user: go',
        nodes=NODES, maximum_mode=17, frequencies_hz=FREQUENCIES, prediction_tolerances=TOLERANCES,
        phase_a_solve_cap=256, phase_a_seconds=900, trial_solve_cap=8000, trial_seconds=7200,
        campaign_solve_cap=16256, campaign_seconds=15300, stage_plan=STAGE_PLAN,
        endpoint_reserve=12, normalization=m.NORMALIZATION, derivative_steps=[1e-4, 5e-5],
        derivative_rows=[0, 32], derivative_relative_stability=.25, derivative_floor_multiplier=5,
        solve_config=asdict(solve_config()), optimizer=asdict(optimizer),
        geometry_configs={str(n): asdict(p.driver.baseline._geometry_config(n)) for n in NODES},
        acceptance=dict(absolute_margin=1e-14, relative_margin=1e-8, cross_resolution_factor=5),
        owner='Codex /root', reviewer='owner review; independent reviewer unassigned',
        supplied_component_count=True, new_observations=False, optimizer_receives_truth=False,
        optimizer_receives_evaluation=False, numerical_workers=1, blas_threads=1))
    # Preserve new experiment source alongside a committed base, without relying
    # on a future commit or a mutable checkout to reconstruct measured code.
    for source in sorted(Path(__file__).parent.glob('*.py')):
        target = bundle/'measured_sources'/source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    files = [x for x in bundle.rglob('*') if x.is_file()]
    write(bundle/'manifest.json', dict(git_revision=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), source_sha256=source_hashes(),
        input_sha256={str(x.relative_to(bundle)): p.digest(x) for x in files},
        historical_sha256=provenance['historical_sha256'], command=sys.argv))


def verify(bundle):
    manifest = read(bundle/'manifest.json')
    require(manifest['source_sha256'] == source_hashes(), 'source changed after freeze')
    for name, sha in manifest['input_sha256'].items():
        require(p.digest(bundle/name) == sha, f'input changed: {name}')
    for name, sha in manifest['historical_sha256'].items():
        require(p.digest(ROOT/name) == sha, f'historical input changed: {name}')


def objective_identity(state, frequencies, observed):
    objective = dict(active_frequencies_hz=list(frequencies), normalization=m.NORMALIZATION,
        production_nodes=256, refined_nodes=512, solve_config=asdict(solve_config()),
        geometry_configs={str(n): asdict(p.driver.baseline._geometry_config(n)) for n in NODES},
        acquisition_and_material_sha256=INPUT_HASHES['observations'],
        observation_sha256=hashlib.sha256(np.asarray(observed, dtype=np.complex128).tobytes()).hexdigest())
    return dict(state_sha256=m.state_hash(state), objective_sha256=m.state_hash(objective), **objective)


def score_predictions(state, spec, observed, evaluation, predictions):
    scene = next(s for s in spec['scenes'] if s['id'] == SCENE)
    geometry = p.benchmark.geometry_metrics(state, scene, spec)
    train = discrepancy(predictions[512][:, :4], observed)
    ev = discrepancy(predictions[512][:, 4:], evaluation)
    differences = discrepancy(predictions[256], predictions[512])
    gates = dict(count=geometry['component_count'] == geometry['truth_component_count'],
        boundary=geometry['maximum_matched_hausdorff_m'] <= .001, iou=geometry['union_iou'] >= .90,
        original_training=float(train[0]) <= .003, evaluation=float(max(ev)) <= .05)
    objectives = {str(n): {str(k): .5*float(np.mean(discrepancy(predictions[n][:, :4], observed)[:k]**2))
                          for k in (1, 2, 3, 4)} for n in NODES}
    return dict(geometry=geometry, training_errors=train, evaluation_errors=ev,
        maximum_evaluation_error=float(max(ev)), gates=gates, original_gates_pass=all(gates.values()),
        numerical_checks=dict(training_discrepancy=differences[:4], evaluation_discrepancy=differences[4:]),
        numerically_qualified=bool(np.all(differences <= TOLERANCES)),
        state_sha256=m.state_hash(state), production_nodes=256, refined_nodes=512,
        aggregate_objectives_by_nodes=objectives)


def prediction_record(state, predictions):
    return dict(state=p.driver.serialize_state(state), state_sha256=m.state_hash(state),
                frequencies_hz=FREQUENCIES, solve_config=asdict(solve_config()),
                acquisition_and_material_sha256=INPUT_HASHES['observations'],
                predictions={str(n): dict(real=value.real, imag=value.imag,
                    geometry_config=asdict(p.driver.baseline._geometry_config(n)))
                    for n, value in predictions.items()})


def derivative_check(state, observed, bases, ledger, output):
    """TOP-018's two-row audit, with merge-specific identities and no new math."""
    basis = state.gauge_tangent_basis(); selected = (0, len(basis)-1)
    data = p.training_data(p.TRAIN, observed)
    residual = lambda value: p.normalized_complex_residual(value, observed, data.frequency_weights)[0]
    base_res = {n: residual(bases[n][:, :4]) for n in NODES}
    repeated = p.prediction(state, p.TRAIN, 256, solve_config(), ledger, 'derivative_repeatability')
    repeat = float(np.linalg.norm(residual(repeated)-base_res[256]))
    record = dict(state_sha256=m.state_hash(state), basis=basis, selected_rows=selected,
        objective=objective_identity(state, p.TRAIN, observed), steps=[1e-4, 5e-5],
        residual_order='pair-major/frequency-minor real flatten, then imaginary flatten',
        residual_scaling='column observed L2 normalization times sqrt(1/4)',
        repeatability_residual_norm=repeat, rows=[], passed=False)
    write(output/'derivative.json', record)
    for index in selected:
        direction = basis[index]
        physical = screen.normal_rms(state, state.incremented(direction*1e-5))/1e-5
        row = dict(basis_index=index, direction=direction, physical_normal_rms_per_unit=physical,
                   estimates={}, checks=[], passed=False)
        record['rows'].append(row)
        if not np.isfinite(physical) or physical <= 1e-10:
            row['obstruction'] = 'physically trivial/nonfinite prescribed direction'
            write(output/'derivative.json', record); return record
        estimates = {}; ledger.reserve(32)
        for h in (1e-4, 5e-5):
            sides = {n: {} for n in NODES}; refusals = []
            for sign in (-1, 1):
                try:
                    trial = state.incremented(sign*h*direction).polar_angle_gauge_fixed()[0]
                    if not p.feasible(trial, NODES, solve_config(), .008):
                        refusals.append(dict(sign=sign, reason='physical feasibility refused')); continue
                except ValueError as exc:
                    refusals.append(dict(sign=sign, reason=str(exc))); continue
                for n in NODES:
                    sides[n][sign] = residual(p.prediction(trial, p.TRAIN, n, solve_config(), ledger, 'directional_derivative'))
            for n in NODES:
                try: value, stencil = previous.quotient(base_res[n], sides[n], h)
                except m.UnresolvedDerivative:
                    row['obstruction'] = 'both sides refused'
                    write(output/'derivative.json', record); return record
                estimates[n, h] = value
                row['estimates'][f'{n}:{h:g}'] = dict(derivative=value, stencil=stencil,
                    refusals=refusals, side_residuals={str(s): v for s, v in sides[n].items()})
        uncertainty = 5e-5*float(np.linalg.norm(estimates[256, 5e-5]-estimates[512, 5e-5]))
        floor = max(repeat, 64*np.finfo(float).eps, uncertainty)
        for n in NODES:
            row['checks'].append(dict(nodes=n, **previous.derivative_qualified(
                estimates[n, 1e-4], estimates[n, 5e-5], 5e-5, floor)))
        row['passed'] = all(c['passed'] for c in row['checks'])
        write(output/'derivative.json', record)
    record['passed'] = all(r['passed'] for r in record['rows'])
    write(output/'derivative.json', record)
    return record


def release_gate(audit):
    failures = [k for k in ('inputs_verified', 'tests_verified', 'source_integrity',
                            'padding_predictions_pass') if not audit.get(k)]
    for label in AUDIT_STATES:
        row = audit.get('states', {}).get(label, {})
        if (not all(row.get('feasible', {}).get(str(n), False) for n in NODES)
                or not row.get('qualified_256_512') or not row.get('gauge_coefficient_change', float('inf')) < 1e-10):
            failures.append(label)
    if not audit.get('states', {}).get('WITNESS', {}).get('capacity_pass'):
        failures.append('capacity_witness')
    if not audit.get('derivative', {}).get('passed'):
        failures.append('directional_derivative')
    return dict(passed=not failures, failed_requirements=failures)


def released_arms(audit):
    return ('S', 'F') if audit.get('status') == 'PHASE_A_PASS' and audit.get('gate', {}).get('passed') else ()


def phase_a(bundle, seconds=900):
    output = bundle/'phase_a'; output.mkdir(exist_ok=False)
    ledger = m.Ledger(cap=256, seconds=min(900, seconds))
    result = dict(status='IN_PROGRESS', states={}, inputs_verified=False, tests_verified=False,
                  source_integrity=False, padding_predictions_pass=False, derivative={'passed': False})
    predictions = {}
    try:
        verify(bundle)
        states, observed, evaluation, _, provenance = validated_inputs()
        spec = read(bundle/'scene_spec.json')
        result.update(inputs_verified=True, tests_verified=True)
        with ledger.instrument():
            for label in AUDIT_STATES:
                state = states[label]; predictions[label] = {}
                row = dict(state=p.driver.serialize_state(state), state_sha256=m.state_hash(state), feasible={},
                           gauge_coefficient_change=provenance['gauge_coefficient_change'][label])
                result['states'][label] = row
                for n in NODES:
                    row['feasible'][str(n)] = p.feasible(state, (n,), solve_config(), .008)
                if not all(row['feasible'].values()):
                    row['qualified_256_512'] = False
                    raise m.NumericalFailure(f'{label} geometry infeasible')
                for n in NODES:
                    predictions[label][n] = p.prediction(state, FREQUENCIES, n, solve_config(), ledger, 'audit_'+label.lower())
                    write(output/f'{label}_predictions.json', prediction_record(state, predictions[label]))
                eta = discrepancy(predictions[label][256], predictions[label][512])
                row.update(qualified_256_512=bool(np.all(eta <= TOLERANCES)), discrepancy=eta,
                    tolerances=TOLERANCES, threshold_ratio=eta/TOLERANCES)
                row['score'] = score_predictions(state, spec, observed, evaluation, predictions[label])
                if label == 'WITNESS':
                    row['capacity_pass'] = bool(row['score']['original_gates_pass'] and
                        row['score']['geometry']['maximum_matched_hausdorff_m'] <= .0001)
                if label == 'COMMON': result['common_score'] = row['score']
                write(output/'audit.json', result)
            padding = {str(n): discrepancy(predictions['COMMON'][n], predictions['ORIGINAL'][n]) for n in NODES}
            result.update(padding_prediction_discrepancy=padding,
                          padding_predictions_pass=all(np.all(x <= 1e-10) for x in padding.values()))
            if (result['padding_predictions_pass'] and all(r['qualified_256_512'] for r in result['states'].values())
                    and result['states']['WITNESS']['capacity_pass']):
                result['derivative'] = derivative_check(states['COMMON'], observed, predictions['COMMON'], ledger, output)
        verify(bundle); result['source_integrity'] = True
        result['gate'] = release_gate(result)
        result['status'] = 'PHASE_A_PASS' if result['gate']['passed'] else 'PHASE_A_FAIL'
    except Exception as exc:
        result.update(status='PHASE_A_FAIL', reason=getattr(exc, 'code', 'IMPLEMENTATION_ERROR'),
                      detail=str(exc), traceback=traceback.format_exc())
        result['gate'] = release_gate(result)
    finally:
        result['work'] = ledger.snapshot(); write(output/'audit.json', result)
    print('Phase A', result['status'], ledger.total, result['gate'], flush=True)
    return result


def bind_objective_records(result, observed, output):
    for stage in result['stages']:
        active = len(stage['active_frequencies_hz']); terminal = stage['terminal']
        state = p.driver.deserialize_state(terminal['final_state'])
        identity = objective_identity(state, p.TRAIN[:active], observed[:, :active])
        terminal['objective_identity'] = identity
        for key in ('gradient', 'last_measured_gradient'):
            gradient = terminal.get(key)
            if gradient is None: continue
            require(list(gradient['active_frequencies_hz']) == list(stage['active_frequencies_hz'])
                    and gradient['production_nodes'] == 256 and gradient['refined_nodes'] == 512,
                    f'{key} objective/resolution mismatch')
            if key == 'gradient': require(gradient['state_sha256'] == m.state_hash(state), 'stale terminal gradient')
            gradient['objective_sha256'] = identity['objective_sha256']
        path = output/f'stage_{stage["stage"]}'
        if path.exists():
            write(path/'objective_associations.json', dict(endpoint=identity,
                gradient=terminal.get('gradient'), last_measured_gradient=terminal.get('last_measured_gradient')))
    return result


def schedule(initial, arm, observed, optimizer, ledger, output, initial_score, scorer,
             expected_stage_one=None, fit=m.fit_stage, feasibility=p.feasible):
    if arm == 'F': require(expected_stage_one is not None, 'F needs a qualified S stage-1 endpoint')
    def guarded_fit(state, *args):
        if arm == 'F' and ledger.stage == 2:
            require(m.state_hash(state) == expected_stage_one, 'paired stage-1 endpoint mismatch')
        return fit(state, *args)
    def bound_score(state):
        score = scorer(state); active = 1 if arm == 'S' else ledger.stage
        score.update(objective_identity(state, p.TRAIN[:active], observed[:, :active]))
        return score
    result = m.run_schedule(initial, arm, observed, NODES, solve_config(), optimizer, .008, ledger,
        output, initial_score, bound_score, fit=guarded_fit, feasibility=feasibility, stage_plan=STAGE_PLAN)
    if result.get('reason') == 'NUMERICAL_FAILURE' and result.get('stages') and 'score' not in result['stages'][-1]:
        retained = p.driver.deserialize_state(result['final_state'])
        try:
            if feasibility(retained, NODES, solve_config(), .008):
                with ledger.endpoint_scope(): ledger.reserve(12)
                result['reporting_score'] = bound_score(retained)
                result.update(reporting_score_state_sha256=m.state_hash(retained), reporting_score_releases_stage=False)
            else: result['reporting_score_missing_reason'] = 'retained geometry infeasible'
        except Exception as exc: result['reporting_score_missing_reason'] = f'{type(exc).__name__}: {exc}'
    result['work'] = ledger.snapshot()
    bind_objective_records(result, observed, output)
    write(output/'metrics.json', result)
    return result


def qualified_stage_one(trial):
    if not trial.get('source_integrity') or not trial.get('stages'): return None
    first = trial['stages'][0]
    if (first['stage'] != 1 or not first.get('stage_complete') or not first.get('score', {}).get('numerically_qualified')
            or not first['terminal'].get('effective_training_exposure')): return None
    state = first['terminal']['final_state']; h = m.state_hash(state)
    require(first['score_state_sha256'] == h, 'S stage-1 score state mismatch')
    return h


def trial(bundle, arm, seconds=7200):
    verify(bundle); audit = read(bundle/'phase_a/audit.json')
    require(arm in released_arms(audit), 'Phase A did not release this arm')
    expected = None
    if arm == 'F':
        expected = qualified_stage_one(read(bundle/'runs/S-merge/metrics.json'))
        require(expected is not None, 'S has no qualified stage-1 endpoint')
    output = bundle/'runs'/f'{arm}-merge'; output.mkdir(parents=True, exist_ok=False)
    initial = p.driver.deserialize_state(read(bundle/'inputs/merge/state.json'))
    observed, evaluation = m.observations(bundle, SCENE)
    optimizer = m.rt.ParameterFDConfig(**read(bundle/'inputs/merge/optimizer.json')['config'])
    spec = read(bundle/'scene_spec.json'); ledger = m.Ledger(cap=8000, seconds=min(7200, seconds))
    write(output/'manifest.json', dict(source_sha256=source_hashes(), initial_state_sha256=m.state_hash(initial),
        input_manifest_sha256=p.digest(bundle/'manifest.json'), phase_a_sha256=p.digest(bundle/'phase_a/audit.json'),
        expected_stage_one_sha256=expected, command=sys.argv, numerical_workers=1, blas_threads=1))
    def scorer(state):
        with ledger.endpoint_scope():
            ledger.reserve(12)
            values = {n: p.prediction(state, FREQUENCIES, n, solve_config(), ledger, 'endpoint') for n in NODES}
        write(output/f'stage_{ledger.stage}'/'endpoint_predictions.json', prediction_record(state, values))
        return score_predictions(state, spec, observed, evaluation, values)
    result = None
    try:
        with ledger.instrument():
            result = schedule(initial, arm, observed, optimizer, ledger, output, audit['common_score'], scorer, expected)
        verify(bundle)
        result.update(scene=SCENE, source_integrity=True)
    except Exception as exc:
        # Keep the raw schedule artifacts if an annotation or verification fails.
        result = result or (read(output/'metrics.json') if (output/'metrics.json').exists() else {})
        result.update(worker_error=dict(type=type(exc).__name__, detail=str(exc), traceback=traceback.format_exc()),
                      source_integrity=False, work=ledger.snapshot())
        write(output/'metrics.json', result)
        raise
    finally:
        if result is not None: write(output/'metrics.json', result)
        write(output/'work.json', ledger.snapshot())
    print(arm, result['status'], result.get('reason'), ledger.total, flush=True)
    return result


def run_worker(bundle, arm, deadline, clock=time.monotonic, popen=subprocess.Popen):
    started = clock()
    if started >= deadline:
        return dict(arm=arm, status='NOT_DISPATCHED', campaign_timeout=True, exit_code=None)
    command = [sys.executable, str(Path(__file__).resolve()), 'trial', '--bundle', str(bundle),
               '--arm', arm, '--seconds', str(min(7200, deadline-started))]
    with (bundle/f'{arm}.log').open('x') as log:
        process = popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        timed_out = False
        try: code = process.wait(timeout=max(.001, deadline-clock()))
        except subprocess.TimeoutExpired:
            timed_out = True; os.killpg(process.pid, signal.SIGALRM)
            try: code = process.wait(timeout=5.)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); code = process.wait()
    return dict(arm=arm, command=command, exit_code=code, campaign_timeout=timed_out, elapsed_seconds=clock()-started)


def campaign(bundle, validation):
    prepare(bundle, validation)
    began = time.monotonic(); deadline = began+15300
    write(bundle/'environment.json', dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
        cpu=subprocess.check_output(['lscpu'], text=True), initial_load=os.getloadavg(), numerical_workers=1,
        threads={k: os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}, command=sys.argv))
    record = dict(status='IN_PROGRESS', workers=[], watchdog_seconds=15300)
    write(bundle/'campaign.json', record)
    try:
        audit = phase_a(bundle, min(900, deadline-time.monotonic()))
        record['phase_a_status'] = audit['status']; write(bundle/'campaign.json', record)
        if not released_arms(audit): record['status'] = 'STOPPED_AT_PHASE_A'
        else:
            for arm in released_arms(audit):
                worker = run_worker(bundle, arm, deadline)
                record['workers'].append(worker); write(bundle/'campaign.json', record)
                if worker['exit_code'] != 0 or worker['campaign_timeout']:
                    record['status'] = 'COMPLETE_WITH_FAILED_WORKERS'; break
                if arm == 'S' and qualified_stage_one(read(bundle/'runs/S-merge/metrics.json')) is None:
                    record['status'] = 'STOPPED_BEFORE_F'; break
            else: record['status'] = 'COMPLETE'
    except Exception as exc:
        record.update(status='CAMPAIGN_ERROR', detail=str(exc), traceback=traceback.format_exc())
    finally:
        record['elapsed_seconds'] = time.monotonic()-began; write(bundle/'campaign.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('campaign', 'trial'))
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--validation', type=Path)
    parser.add_argument('--arm', choices=('S', 'F'))
    parser.add_argument('--seconds', type=float, default=7200)
    args = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        require(os.environ.get(key) == '1', 'single-thread BLAS required')
    if args.phase == 'campaign':
        if args.validation is None: parser.error('--validation required')
        result = campaign(args.bundle.resolve(), args.validation.resolve())
    else:
        if args.arm is None: parser.error('--arm required')
        result = trial(args.bundle.resolve(), args.arm, args.seconds)
    print(result['status'], flush=True)


if __name__ == '__main__': main()
