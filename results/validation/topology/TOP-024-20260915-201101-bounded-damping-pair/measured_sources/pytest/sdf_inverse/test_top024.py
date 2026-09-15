"""Bounded continuation controls and failure preservation, without BIE calls."""
from dataclasses import asdict
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.top024 import run as r
from experiments.top024 import summarize as report


def test_exact_control_and_only_initial_damping_differs():
    inputs, _ = r.diagnostic.terminal_inputs()
    a, b = (asdict(r.arm_config(inputs['optimizer'], arm)) for arm in ('A', 'B'))
    assert {key for key in a if not np.array_equal(a[key], b[key])} == {'initial_damping'}
    assert a['initial_damping'] == inputs['next_damping'] and b['initial_damping'] == .01
    assert a['max_iterations'] == b['max_iterations'] == 12
    assert r.CAP == 4000 and r.SECONDS == 3600 and r.NODES == (256, 512)


def test_release_uses_qualified_diagnostic_and_rejects_changed_source(monkeypatch):
    assert len(r.release_gate()) == 5
    monkeypatch.setattr(r.diagnostic, 'source_hashes', lambda: {})
    with pytest.raises(r.m.ImplementationError, match='source changed'):
        r.release_gate()


@pytest.fixture
def prepared(tmp_path):
    log = tmp_path/'tests.log'; log.write_text('synthetic test fixture; no physical solves')
    validation = tmp_path/'validation.json'
    r.write(validation, dict(status='PASS', source_sha256=r.source_hashes(), test_sha256={},
                            log=log.name, log_sha256=r.p.digest(log)))
    output = tmp_path/'pair'
    assert r.prepare(output, validation)['new_physical_solves'] == 0
    return output


def test_preparation_binds_exact_failed_endpoint_and_both_configs(prepared):
    state, observed, evaluation, *rest = r.load_inputs(prepared)
    assert r.m.state_hash(state) == r.read(r.DIAGNOSTIC/'inputs.json')['state_sha256']
    assert observed.shape == (24,4) and evaluation.shape == (24,2)
    for arm in ('A','B'):
        assert r.read(prepared/'arm_configs.json')[arm]['initial_damping'] == r.DAMPINGS[arm]
        witness = r.read(prepared/'witnesses.json')[arm]
        assert witness['state_sha256'] != r.m.state_hash(state)
    r.verify(prepared)
    config = r.read(prepared/'arm_configs.json'); config['B']['max_iterations'] += 1
    r.write(prepared/'arm_configs.json', config)
    with pytest.raises(r.m.ImplementationError): r.verify(prepared)


def test_stale_validation_and_failed_release_do_not_create_output(tmp_path, monkeypatch):
    validation = tmp_path/'validation.json'
    r.write(validation, dict(status='PASS', source_sha256={}))
    with pytest.raises(r.m.ImplementationError): r.prepare(tmp_path/'pair', validation)
    assert not (tmp_path/'pair').exists()


@pytest.mark.parametrize('arm', ['A','B'])
def test_first_step_tolerance_and_rejected_loss(prepared, arm):
    witness = r.read(prepared/'witnesses.json')[arm]
    state = r.p.driver.deserialize_state(witness['state'])
    assert r.first_step_check(state, witness['production_loss'], witness)['status'] == 'PASS'
    assert r.first_step_check(state, witness['production_loss']*1.001, witness)['status'] == 'FAIL'


def test_guard_preserves_checkpoint_before_mismatch_and_restores_optimizer(prepared, monkeypatch):
    witness = r.read(prepared/'witnesses.json')['B']
    state = r.p.driver.deserialize_state(witness['state']); checkpoints = []
    def fake(*args, **kwargs):
        kwargs['accepted_state_callback'](1, SimpleNamespace(state=state, loss=witness['production_loss']*2))
    monkeypatch.setattr(r.m.rt, 'run_multiradial_fd_inverse', fake)
    destination = prepared/'check.json'
    with pytest.raises(r.m.ImplementationError, match='first step differs'):
        with r.first_step_guard(witness, destination):
            r.m.rt.run_multiradial_fd_inverse(accepted_state_callback=lambda *args:checkpoints.append(args))
    assert len(checkpoints) == 1 and r.read(destination)['status'] == 'FAIL'
    assert r.m.rt.run_multiradial_fd_inverse is fake


def test_fit_receives_training_only_and_hard_failure_preserves_row(prepared, monkeypatch):
    def schedule(state, arm, observed, nodes, solve, optimizer, floor, ledger, folder, initial_score, scorer, stage_plan):
        assert observed.shape == (24,4) and set(initial_score) == {'training_errors','numerically_qualified'}
        assert stage_plan == ((4,4000),) and optimizer.max_iterations == 12
        assert ledger.cap == 4000 and ledger.seconds == 3600 and nodes == (256,512)
        raise r.m.PhysicalFailure('synthetic failure before first physical call')
    monkeypatch.setattr(r.m, 'run_schedule', schedule)
    result = r.run_arm(prepared, 'A')
    assert result['status'] == 'HARD_STOP' and not result['reconstruction_pass']
    assert result['work']['total_attempted'] == 0 and result['sources_and_inputs_unchanged']
    assert r.read(prepared/'runs/A/result.json') == result
    assert (prepared/'runs/A/artifact_manifest.json').exists()


def test_missing_worker_results_remain_two_incomplete_rows(prepared):
    r.write(prepared/'campaign.json', dict(status='COMPLETED', workers=[dict(arm=a,exit_code=124) for a in ('A','B')]))
    result, endpoints = report.verify(prepared)
    assert result['outcome'] == 'MATCHED_PAIR_INCOMPLETE' and len(result['rows']) == 2
    assert not result['accounting_complete'] and result['total_attempted_calls'] == 0
    assert len(endpoints) == 1 and result['new_physical_solves'] == 0


@pytest.mark.parametrize('a,b,expected', [(False,False,'NEITHER_ARM_RECOVERED'), (True,False,'A_RECOVERED'),
    (False,True,'B_RECOVERED'), (True,True,'BOTH_ARMS_RECOVERED')])
def test_reconstruction_classification_requires_all_gates(a,b,expected):
    rows = [dict(arm=arm,status='COMPLETED_SCHEDULE',reconstruction_pass=passed) for arm,passed in [('A',a),('B',b)]]
    assert report.classify(rows) == expected
