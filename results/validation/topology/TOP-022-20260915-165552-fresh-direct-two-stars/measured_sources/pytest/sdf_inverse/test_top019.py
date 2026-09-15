"""TOP-019 contracts: geometry and mocked physical calls only."""
from copy import deepcopy
from dataclasses import replace
import inspect
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.top019 import run as n

m, p = n.m, n.p


@pytest.fixture(scope='module')
def inputs():
    return n.validated_inputs()


def mock_score():
    return dict(training_errors=[.1, .2, .3, .4], numerically_qualified=True,
                original_gates_pass=False, production_nodes=256, refined_nodes=512)


def good_audit():
    return dict(status='PHASE_A_PASS', inputs_verified=True, tests_verified=True,
                source_integrity=True, padding_predictions_pass=True,
                derivative={'passed': True}, states={label: dict(
                    feasible={'256': True, '512': True}, gauge_coefficient_change=0.,
                    qualified_256_512=True, capacity_pass=True)
                    for label in n.AUDIT_STATES})


def test_frozen_inputs_and_geometry_preserving_padding(inputs):
    states, obs, evaluation, opt, provenance = inputs
    original, common, witness = (states[k] for k in n.AUDIT_STATES)
    assert m.state_hash(original) == n.ORIGINAL_HASH
    assert m.state_hash(witness) == n.WITNESS_HASH
    assert common.component_ids == original.component_ids == ('t001.merge1',)
    assert common.parameter_count == opt.max_parameters == 70
    assert common.gauge_tangent_basis().shape == (33, 70)
    assert len(opt.max_steps) == 70 and opt.max_iterations == 22
    a, b = original.components[0], common.components[0]
    np.testing.assert_array_equal(a.cosine_coefficients, b.cosine_coefficients[:10])
    np.testing.assert_array_equal(a.sine_coefficients, b.sine_coefficients[:10])
    assert np.count_nonzero(b.cosine_coefficients[10:]) == 0
    assert np.count_nonzero(b.sine_coefficients[10:]) == 0
    assert max(provenance['padding_point_change_m'].values()) <= 1e-10
    assert obs.shape == (24, 4) and evaluation.shape == (24, 2)
    assert opt.loss_tolerance == 1e-14 and opt.finite_difference_steps == 1e-4
    assert m.state_hash(common) != m.state_hash(witness)


@pytest.mark.parametrize('field', ['inputs_verified', 'tests_verified', 'source_integrity',
                                  'padding_predictions_pass', 'derivative'])
def test_release_fails_closed(field):
    audit = good_audit()
    assert n.release_gate(audit)['passed']
    audit[field] = {'passed': False} if field == 'derivative' else False
    assert not n.release_gate(audit)['passed']
    audit['gate'] = n.release_gate(audit)
    assert n.released_arms(audit) == ()


@pytest.mark.parametrize('label', n.AUDIT_STATES)
def test_every_audit_state_is_required(label):
    audit = good_audit()
    del audit['states'][label]
    assert not n.release_gate(audit)['passed']


def test_capacity_witness_and_nodes_are_binding():
    audit = good_audit()
    audit['states']['WITNESS']['capacity_pass'] = False
    assert not n.release_gate(audit)['passed']
    audit = good_audit()
    audit['states']['COMMON']['feasible']['512'] = False
    assert not n.release_gate(audit)['passed']


@pytest.mark.parametrize('arm', ['S', 'F'])
def test_complete_schedule_and_matching_stage_one(tmp_path, inputs, arm):
    states, obs, _, opt, _ = inputs
    state = states['COMMON']; seen = []
    def fit(start, data, nodes, solve, optimizer, floor, ledger, output):
        seen.append((ledger.stage, len(data.frequency_weights), m.state_hash(start), nodes))
        return start, dict(stage_outcome='STAGE_QUOTA_REACHED', effective_training_exposure=True,
            convergence='UNCONFIRMED', gradient=None, final_state=p.driver.serialize_state(start))
    result = n.schedule(state, arm, obs, opt, m.Ledger(cap=8000), tmp_path,
                        mock_score(), lambda s: mock_score(),
                        expected_stage_one=m.state_hash(state) if arm == 'F' else None,
                        fit=fit, feasibility=lambda *args: True)
    assert result['schedule_complete']
    assert [r[0] for r in seen] == [1, 2, 3, 4]
    assert [r[1] for r in seen] == ([1]*4 if arm == 'S' else [1, 2, 3, 4])
    assert all(r[2:] == (m.state_hash(state), (256, 512)) for r in seen)


def test_stage_one_mismatch_stops_before_f_stage_two(tmp_path, inputs):
    states, obs, _, opt, _ = inputs; seen = []
    def fit(start, *args):
        seen.append('fit')
        return start, dict(stage_outcome='NORMAL_OPTIMIZER_RETURN', effective_training_exposure=True,
            convergence='UNCONFIRMED', gradient=None, final_state=p.driver.serialize_state(start))
    result = n.schedule(states['COMMON'], 'F', obs, opt, m.Ledger(cap=8000), tmp_path,
                        mock_score(), lambda s: mock_score(), expected_stage_one='wrong',
                        fit=fit, feasibility=lambda *args: True)
    assert seen == ['fit'] and result['reason'] == 'IMPLEMENTATION_ERROR'
    assert not result['schedule_complete']


@pytest.mark.parametrize('code', ['NUMERICAL_FAILURE', 'UNRESOLVED_DERIVATIVE',
    'TRIAL_SOLVE_CAP', 'TRIAL_WALL_LIMIT', 'PHYSICAL_SOLVE_FAILED', 'IMPLEMENTATION_ERROR'])
def test_hard_stop_cannot_release_stage(tmp_path, inputs, code):
    states, obs, _, opt, _ = inputs; seen = []
    def fit(start, *args):
        seen.append('fit')
        return start, dict(stage_outcome=code, effective_training_exposure=False,
            convergence='UNCONFIRMED', gradient=None, final_state=p.driver.serialize_state(start))
    result = n.schedule(states['COMMON'], 'S', obs, opt, m.Ledger(cap=8000), tmp_path,
                        mock_score(), lambda s: mock_score(), fit=fit, feasibility=lambda *args: True)
    assert seen == ['fit'] and result['reason'] == code
    assert not result['schedule_complete'] and not result['numerically_qualified']
    assert ('reporting_score' in result) == (code == 'NUMERICAL_FAILURE')
    assert not result.get('reporting_score_releases_stage', False)


def test_complete_batch_and_endpoint_reserve(inputs):
    state = inputs[0]['COMMON']; assert len(state.gauge_tangent_basis()) == 33
    ledger = m.Ledger(cap=8000); ledger.begin_stage(1, 1000)
    ledger.attempted['used'] = 920
    with pytest.raises(m.StageQuota): ledger.reserve(70)
    with ledger.endpoint_scope(): ledger.reserve(12)
    assert ledger.total == 920
    assert 256 + 2*sum(q for _, q in n.STAGE_PLAN) == 16256


def test_merge_objective_identity_and_frequency_container(inputs):
    state, obs = inputs[0]['COMMON'], inputs[1]
    identity = n.objective_identity(state, p.TRAIN[:2], obs[:, :2])
    assert identity['acquisition_and_material_sha256'] == n.INPUT_HASHES['observations']
    assert identity == n.objective_identity(state, list(p.TRAIN[:2]), obs[:, :2])
    assert identity['objective_sha256'] != n.objective_identity(state, p.TRAIN[:1], obs[:, :1])['objective_sha256']
    assert set(inspect.signature(m.fit_stage).parameters) == {
        'initial', 'data', 'nodes', 'solve', 'optimizer', 'floor', 'ledger', 'output'}


def test_real_optimizer_uses_seventy_parameters_and_new_nodes(tmp_path, monkeypatch, inputs):
    states, obs, _, opt, _ = inputs; state = states['COMMON']; seen = []
    center = state.components[0].center[0]
    def objective(candidate, data, geometry, **kwargs):
        seen.append(geometry.num_nodes)
        prediction = data.observed_scattered_response*(1+candidate.components[0].center[0]-center+.001)
        residual, _ = p.normalized_complex_residual(prediction, data.observed_scattered_response, data.frequency_weights)
        return m.rt.MultiRadialObjectiveEvaluation(candidate, .5*float(residual@residual),
            float(np.linalg.norm(residual)), residual, prediction, 0., 0.)
    monkeypatch.setattr(m.rt, 'evaluate_multiradial_objective', objective)
    ledger = m.Ledger(cap=8000); ledger.begin_stage(1, 1000)
    final, terminal = m.fit_stage(state, p.training_data(p.TRAIN[:1], obs[:, :1]), n.NODES,
        n.solve_config(), replace(opt, max_iterations=1), .008, ledger, tmp_path/'stage')
    assert terminal['stage_outcome'] == 'NORMAL_OPTIMIZER_RETURN'
    assert terminal['accepted_steps'] == 1 and set(seen) == {256, 512}
    assert terminal['gradient']['state_sha256'] == m.state_hash(final)
    assert ledger.total == 0


def test_campaign_audit_failure_dispatches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(n, 'prepare', lambda *args: None)
    monkeypatch.setattr(n, 'phase_a', lambda *args: {'status': 'PHASE_A_FAIL', 'gate': {'passed': False}})
    monkeypatch.setattr(n, 'run_worker', lambda *args: pytest.fail('inverse after failed audit'))
    record = n.campaign(tmp_path, tmp_path/'validation.json')
    assert record['workers'] == [] and record['status'] == 'STOPPED_AT_PHASE_A'


def test_expired_worker_and_existing_output_are_refused(tmp_path):
    with pytest.raises(FileExistsError): n.prepare(tmp_path, tmp_path/'validation.json')
    def forbidden(*args, **kwargs): pytest.fail('expired dispatch')
    assert n.run_worker(tmp_path, 'S', 1., clock=lambda: 2., popen=forbidden)['status'] == 'NOT_DISPATCHED'


def test_historical_numerical_defaults_unchanged():
    assert m.NODES == (128, 256) and m.QUOTAS == (1250, 1750, 4000)
    assert n.previous.SCENE == 'far-two-stars' and n.previous.NODES == (256, 512)


@pytest.mark.parametrize('arm', ['S', 'F'])
def test_gradient_list_and_frequency_tuple_reporting(tmp_path, inputs, arm):
    state, obs, opt = inputs[0]['COMMON'], inputs[1], inputs[3]
    def fit(initial, data, nodes, solve, optimizer, floor, ledger, output):
        output.mkdir(parents=True)
        gradient = dict(state_sha256=m.state_hash(initial), production_nodes=256, refined_nodes=512,
                        active_frequencies_hz=list(p.TRAIN[:len(data.frequency_weights)]))
        return initial, dict(stage_outcome='STAGE_QUOTA_REACHED', effective_training_exposure=True,
            convergence='UNCONFIRMED', final_state=p.driver.serialize_state(initial),
            gradient=gradient, last_measured_gradient=dict(gradient))
    result = n.schedule(state, arm, obs, opt, m.Ledger(cap=8000), tmp_path,
        mock_score(), lambda state: mock_score(), expected_stage_one=m.state_hash(state),
        fit=fit, feasibility=lambda *args: True)
    for stage in result['stages']:
        terminal = stage['terminal']
        assert terminal['gradient']['objective_sha256'] == stage['score']['objective_sha256']
        assert terminal['last_measured_gradient']['objective_sha256'] == stage['score']['objective_sha256']


@pytest.mark.parametrize('stage_one_qualified', [False, True])
def test_campaign_sequential_pair_and_common_prefix_gate(tmp_path, monkeypatch, stage_one_qualified):
    monkeypatch.setattr(n, 'prepare', lambda *args: None)
    audit = good_audit(); audit['gate'] = n.release_gate(audit)
    monkeypatch.setattr(n, 'phase_a', lambda *args: audit)
    calls = []
    def worker(bundle, arm, deadline):
        calls.append(arm)
        folder = bundle/'runs'/f'{arm}-merge'; folder.mkdir(parents=True)
        n.write(folder/'metrics.json', {'source_integrity': True})
        return dict(arm=arm, exit_code=0, campaign_timeout=False)
    monkeypatch.setattr(n, 'run_worker', worker)
    monkeypatch.setattr(n, 'qualified_stage_one', lambda _: 'state' if stage_one_qualified else None)
    result = n.campaign(tmp_path, tmp_path/'validation.json')
    assert calls == (['S', 'F'] if stage_one_qualified else ['S'])
    assert result['status'] == ('COMPLETE' if stage_one_qualified else 'STOPPED_BEFORE_F')


def test_failed_audit_summary_rebuild_has_no_physical_calls(tmp_path, monkeypatch, inputs):
    from experiments.top019 import summarize as report
    def forbidden(*args, **kwargs): pytest.fail('report or mocked audit dispatched physics')
    monkeypatch.setattr(p.physical, 'solve_multicomponent_kress_tmz_total_field_batch', forbidden)
    log = tmp_path/'mock.log'; log.write_text('mock pre-dispatch record\n')
    validation = tmp_path/'validation.json'
    n.write(validation, dict(status='PASS', source_sha256=n.source_hashes(), log=log.name,
                            log_sha256=p.digest(log)))
    bundle = tmp_path/'bundle'; n.prepare(bundle, validation)
    all_data = np.column_stack((inputs[1], inputs[2]))
    def prediction(state, frequencies, nodes, solve, ledger, category):
        ledger.reserve(len(frequencies))
        ledger.attempted[category] += len(frequencies)
        ledger.completed[category] += len(frequencies)
        return all_data[:, [n.FREQUENCIES.index(f) for f in frequencies]].copy()
    monkeypatch.setattr(p, 'prediction', prediction)
    monkeypatch.setattr(n, 'derivative_check', lambda *args: dict(passed=False, reason='mock floor obstruction'))
    audit = n.phase_a(bundle)
    assert audit['status'] == 'PHASE_A_FAIL' and audit['gate']['failed_requirements'] == ['directional_derivative']
    assert audit['work']['total_attempted'] == 36
    n.write(bundle/'campaign.json', dict(status='STOPPED_AT_PHASE_A', workers=[], elapsed_seconds=1.))
    scorecard, ledger = report.summarize(bundle)
    assert scorecard['outcome'] == 'PHASE_A_NOT_QUALIFIED'
    assert ledger['total_attempted'] == 36 and ledger['attempt_counts_complete']
    before = (bundle/'scorecard.json').read_bytes()
    report.summarize(bundle)
    assert (bundle/'scorecard.json').read_bytes() == before
    assert report.read(bundle/'verification.json')['new_physical_solves'] == 0
    assert (bundle/'endpoints.svg').exists()


def test_summary_distinguishes_recovery_and_incomplete_comparison():
    from experiments.top019.summarize import classify
    def trial(recovered):
        return dict(schedule_complete=True, numerically_qualified=True, source_integrity=True,
                    complete_effective_exposure=True, final={'original_gates_pass': recovered})
    cases = [(False, True, 'F_RECOVERED_RELATIVE_TO_MATCHED_S'),
             (True, True, 'BOTH_ARMS_RECOVERED'), (True, False, 'ADVERSE_MATCHED_F_CONTROL'),
             (False, False, 'NEITHER_ARM_RECOVERED')]
    for s, f, expected in cases:
        trials = {'S': trial(s), 'F': trial(f)}
        outcome, complete, _ = classify({'status': 'PHASE_A_PASS'}, trials)
        assert outcome == expected and complete
        trials['F']['schedule_complete'] = False
        assert classify({'status': 'PHASE_A_PASS'}, trials)[:2] == ('MATCHED_PAIR_INCOMPLETE', False)


def test_pair_artifact_roundtrip_without_physics(tmp_path, monkeypatch, inputs):
    from experiments.top019 import summarize as report
    def forbidden(*args, **kwargs): pytest.fail('mock pair dispatched physics')
    monkeypatch.setattr(p.physical, 'solve_multicomponent_kress_tmz_total_field_batch', forbidden)
    log = tmp_path/'mock.log'; log.write_text('mock test record\n')
    validation = tmp_path/'validation.json'
    n.write(validation, dict(status='PASS', source_sha256=n.source_hashes(), log=log.name, log_sha256=p.digest(log)))
    bundle = tmp_path/'bundle'; n.prepare(bundle, validation)
    all_data = np.column_stack((inputs[1], inputs[2]))
    def prediction(state, frequencies, nodes, solve, ledger, category):
        ledger.reserve(len(frequencies))
        ledger.attempted[category] += len(frequencies)
        ledger.completed[category] += len(frequencies)
        return all_data[:, [n.FREQUENCIES.index(f) for f in frequencies]].copy()
    monkeypatch.setattr(p, 'prediction', prediction)
    monkeypatch.setattr(n, 'derivative_check', lambda *args: dict(passed=True))
    audit = n.phase_a(bundle); assert audit['status'] == 'PHASE_A_PASS'
    def fit(state, data, nodes, solve, optimizer, floor, ledger, output):
        output.mkdir(parents=True)
        active = len(data.frequency_weights); ledger.reserve(70*active)
        ledger.attempted['mock_model'] += 70*active; ledger.completed['mock_model'] += 70*active
        return state, dict(stage_outcome='NORMAL_OPTIMIZER_RETURN', effective_training_exposure=True,
            optimizer_stop='maximum_iterations', convergence='UNCONFIRMED', accepted_steps=0,
            final_state=p.driver.serialize_state(state), state_sha256=m.state_hash(state),
            production_nodes=256, refined_nodes=512, gradient=None, work=ledger.snapshot())
    original_schedule = n.schedule
    monkeypatch.setattr(n, 'schedule', lambda *args, **kwargs: original_schedule(*args, **kwargs, fit=fit))
    trials = {arm: n.trial(bundle, arm) for arm in ('S', 'F')}
    assert all(t['schedule_complete'] for t in trials.values())
    n.write(bundle/'campaign.json', dict(status='COMPLETE', elapsed_seconds=1.,
        workers=[dict(arm=arm, exit_code=0, campaign_timeout=False) for arm in ('S', 'F')]))
    scorecard, work = report.summarize(bundle)
    assert scorecard['outcome'] == 'BOTH_ARMS_RECOVERED'
    assert scorecard['pair_complete_and_qualified'] and work['total_attempted'] == 36+70*(4+10)+12*8
    before = (bundle/'scorecard.json').read_bytes()
    report.summarize(bundle)
    assert (bundle/'scorecard.json').read_bytes() == before
    broken = report.read(bundle/'runs/F-merge/metrics.json')
    broken['stages'][-1]['score']['training_errors'][0] = .01
    report.write(bundle/'runs/F-merge/metrics.json', broken)
    with pytest.raises(AssertionError, match='prediction error differs'): report.summarize(bundle)
