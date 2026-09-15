"""Direct-frequency fresh dispatch and complete artifact replay; mocked BIE only."""
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.top022 import run as r
from experiments.top022 import summarize as report


def manifest(folder):
    r.write(folder/'artifact_manifest.json', {str(x.relative_to(folder)): r.p.digest(x)
        for x in folder.rglob('*') if x.is_file() and x.name != 'artifact_manifest.json'})


@pytest.mark.parametrize('changed', ['protocol', 'outcome', 'verification', 'bytes'])
def test_comparison_rejects_wrong_or_changed_evidence(tmp_path, changed):
    for name in ('contract.json', 'result.json', 'verification.json', 'topology/terminal.json'):
        destination = tmp_path/name; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(r.COMPARISON/name, destination)
    if changed == 'protocol':
        data = r.read(tmp_path/'contract.json'); data['experiment'] = 'TOP-022'
        r.write(tmp_path/'contract.json', data)
    elif changed == 'outcome':
        data = r.read(tmp_path/'result.json'); data['fresh_recovery_pass'] = True
        r.write(tmp_path/'result.json', data)
    elif changed == 'verification':
        data = r.read(tmp_path/'verification.json'); data['status'] = 'FAIL'
        r.write(tmp_path/'verification.json', data)
    manifest(tmp_path)
    if changed == 'bytes': (tmp_path/'result.json').write_text('{}')
    with pytest.raises(r.m.ImplementationError): r.comparison_record(tmp_path)


def test_unchanged_budget_and_comparison_is_hash_only():
    record = r.comparison_record()
    assert 'state' not in record and record['new_physical_solves'] == 0
    assert r.STAGE_PLAN == ((4, 8000),) and 12+sum(q for _, q in r.STAGE_PLAN) == 8012
    assert 4000+8012 == 12012


def test_dispatch_rejects_stale_sources_before_output(tmp_path):
    r.write(tmp_path/'validation.json', dict(status='PASS', source_sha256={}))
    with pytest.raises(r.m.ImplementationError, match='sources'):
        r.prepare(tmp_path/'run', tmp_path/'validation.json')
    assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('mismatch', [False, True])
def test_fresh_start_direct_exposure_and_saved_replay(tmp_path, monkeypatch, mismatch):
    log = tmp_path/'tests.log'; log.write_text('mock qualification; no physical solves')
    validation = tmp_path/'validation.json'
    r.write(validation, dict(status='PASS', source_sha256=r.source_hashes(), test_sha256={},
        log=log.name, log_sha256=r.p.digest(log)))
    expected = r.p.driver.deserialize_state(r.read(r.COMPARISON/'topology/terminal.json')['final_state'])
    seen = []
    def prefix(initial, data, control, solve, ledger, output):
        assert initial.component_ids == ('initial.circle',)
        assert r.m.state_hash(initial) == r.read(r.COMPARISON/'contract.json')['initial_state_sha256']
        np.testing.assert_allclose(data.forward_problem.angular_frequencies/(2*np.pi), r.p.TRAIN[:1])
        seen.append('fresh H')
        state = initial if mismatch else expected  # test fixture only
        output.mkdir()
        r.write(output/'initial_state.json', r.p.driver.serialize_state(initial))
        r.write(output/'terminal.json', dict(final_state=r.p.driver.serialize_state(state),
            controller_work=dict(totals=dict(bie_frequency_solve_count=0))))
        r.write(output/'events.json', [])
        (output/'trajectory.jsonl').write_text('{"loss": 1.0}\n')
        return state
    monkeypatch.setattr(r.follow, 'topology_prefix', prefix)
    # Refuse any accidental real physical objective or prediction.
    original = r.m.run_schedule
    def schedule(*args, **kwargs):
        def fit(state, data, nodes, solve, optimizer, floor, ledger, output):
            seen.append('full fit')
            np.testing.assert_allclose(data.forward_problem.angular_frequencies/(2*np.pi), r.p.TRAIN)
            assert nodes == (256, 512) and ledger.stage == 4 and ledger.stage_quota == 8000
            assert optimizer.max_iterations == 22 and optimizer.loss_tolerance == 1e-14
            assert r.m.state_hash(state) == r.m.state_hash(r.p.padded(expected))
            output.mkdir()
            r.write(output/'initial_state.json', r.p.driver.serialize_state(state))
            terminal = dict(stage_outcome='NORMAL_OPTIMIZER_RETURN', effective_training_exposure=True,
                convergence='UNCONFIRMED', state_sha256=r.m.state_hash(state),
                final_state=r.p.driver.serialize_state(state), production_nodes=256, refined_nodes=512)
            r.write(output/'terminal.json', terminal)
            return state, terminal
        return original(*args, **kwargs, fit=fit, feasibility=lambda *a: True)
    monkeypatch.setattr(r.m, 'run_schedule', schedule)
    observed = r.read(r.COMPARISON/'inputs/training_observations.json')
    evaluation = r.read(r.COMPARISON/'inputs/observations.json')
    responses = np.column_stack((np.array(observed['observed_real'])+1j*np.array(observed['observed_imag']),
        (np.array(evaluation['observed_real'])+1j*np.array(evaluation['observed_imag']))[:, 1:]))
    def prediction(state, frequencies, nodes, solve, ledger, category):
        seen.append('mock endpoint')
        for f in frequencies:
            ledger.reserve(1)
            ledger.attempted[category] += 1; ledger.completed[category] += 1
            ledger.frequency_attempted[str(f)] += 1; ledger.frequency_completed[str(f)] += 1
        return responses
    monkeypatch.setattr(r.p, 'prediction', prediction)
    output = tmp_path/'run'
    result = r.run(output, validation)
    assert result['sources_and_inputs_unchanged']
    if mismatch:
        assert result['status'] == 'HARD_STOP' and seen == ['fresh H']
        assert result['total_attempted_frequency_calls'] == 0 and not (output/'handoff.json').exists()
    else:
        assert result['status'] == 'COMPLETED_SCHEDULE', result
        assert seen == ['fresh H', 'mock endpoint', 'mock endpoint', 'full fit', 'mock endpoint', 'mock endpoint']
        assert [row['stage'] for row in result['schedule']['stages']] == [4]
        assert result['total_attempted_frequency_calls'] == 24 and not result['fresh_recovery_pass']
        assert report.verify_comparison(output)['status'] == 'PASS'
        verification, endpoints = report.base.verify(output)
        assert verification['endpoints_verified'] == 2 and endpoints[-1][0] == 'Stage 4'
        # The comparison gate remains binding even if a caller regenerates a manifest.
        data = r.read(output/'staged_comparison.json'); data['result_sha256'] = 'tampered'
        r.write(output/'staged_comparison.json', data); manifest(output)
        with pytest.raises(AssertionError): report.verify_comparison(output)
