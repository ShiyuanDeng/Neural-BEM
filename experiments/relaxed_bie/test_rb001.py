"""Replay gates and dispatch ceilings: no large campaign is run by these tests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import numpy as np
import pytest

from . import rb001 as r


def test_replay_gate_detects_changed_decision_curve_and_work():
    *_, reference = r.inputs(*r.CASES[0])
    assert r.compare(reference, reference)['passed']
    for mutate in (
        lambda x: x['trials'][0].update(status='nondecreasing'),
        lambda x: x['curve']['real'].__setitem__(0, x['curve']['real'][0]+2e-9),
        lambda x: x['history'][0]['work'].update(work_units=0),
    ):
        changed = deepcopy(reference)
        mutate(changed)
        assert not r.compare(reference, changed)['passed']


def test_concurrent_dispatch_cap_is_checked_before_work():
    budget = r.Budget(units=7)
    def attempt(_):
        try:
            budget.charge('evaluation')
            return 1
        except r.lm.TrialSolveCap:
            return 0
    with ThreadPoolExecutor(4) as pool:
        assert sum(pool.map(attempt, range(20))) == 7
    assert budget.units == 7


def test_all_four_inputs_are_ordinary_archived_stages():
    for case, expected_steps in zip(r.CASES, (3, 14, 0, 1)):
        problem, stage, config, curve, work, record = r.inputs(*case)
        assert tuple(stage.observations) == problem.real
        assert (stage.nodes, stage.refined_nodes) == (512, 1024)
        assert record['accepted_steps'] == expected_steps
        assert work['stage_units'] == 0
        assert record['outcome'] == 'NUMERICAL_FAILURE'


def test_fine_candidate_cannot_pass_with_unqualified_base():
    *_, record = r.inputs(*r.CASES[0])
    curve = r.curve_from(record['curve'])
    def value(loss, field):
        return r.lm.Evaluation(curve, loss, 0, np.zeros(2), np.array([[field]]))
    stage = type('Stage', (), dict(discrepancy_tolerances=(1e-7,), nodes=512, refined_nodes=1024))
    result = r.probe_pair(value(1, 1.01), value(.5, 1), value(1, 1), value(.5, 1),
                          stage, r.lm.BackendConfig())
    assert result['accepted'] and result['candidate_qualified']
    assert not result['base_qualified'] and not result['passed']


def test_original_artifact_and_source_archive_hashes():
    receipt = r.verify_archive()
    assert receipt['passed'] and receipt['source_members'] >= 300


def test_saved_resume_keeps_archived_work_and_excludes_failed_proposal_cache():
    from .continuation import checkpoint, resume_policy
    if not (r.OUTPUT/'stage_a.json').exists():
        pytest.skip('Requires the preserved RB-001 Stage-A bundle')
    for case, arm, label in r.CASES:
        problem, stage, config, state, original = checkpoint(r.OUTPUT, case, arm, label)
        assert state.iteration == original['accepted_steps']
        assert state.work == original['history'][-1]['work']
        assert state.damping == original['history'][-1]['next_damping']
        assert all(t['iteration'] <= state.iteration for t in state.trials)
        failed = r.curve_from(r.read(r.OUTPUT/'stage_a'/case/arm/'candidate.json')['curve'])
        assert failed.coefficients.tobytes() not in state.refined_cache
        if not state.iteration:
            assert not state.refined_cache
        physics = r.NodalKress(r.Execution())
        _, _, resume, _ = resume_policy(r.OUTPUT, case, arm, label, physics)
        assert resume.operations[0].label == label
        future_frontier = any(op.kind == 'frontier' for op in resume.operations)
        assert future_frontier == (label == 'release_M11')
