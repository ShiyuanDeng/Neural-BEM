"""FM-004 selection and certificate checks; no forward solves."""
import numpy as np
import pytest

from . import fm004


def test_truth_free_rule_reproduces_frozen_list():
    picked = fm004.candidates()
    assert tuple(picked['order']) == fm004.EXPECTED
    assert picked['threshold'] == pytest.approx(.9*0.004520901647471496)
    assert max(picked['losses'].values()) < picked['threshold'] < picked['next_loss']
    assert set(fm004.NEAR) | {fm004.REUSED, 399, 479} == set(fm004.EXPECTED)


def test_schedule_runs_new_candidates_then_control():
    _, runs = fm004.schedule()
    assert [i for _, _, i in runs[:-1]] == [i for i in fm004.EXPECTED if i != fm004.REUSED]
    assert runs[-1] == (fm004.f.LOW, 'phase4', fm004.CONTROL)


def test_certificate_uses_audit_and_every_residual():
    limits = [.003]*3
    ok = dict(final_audit_passed=True, relative_residual=[1e-6, 2e-3, 3e-3], residual_limits=limits)
    assert fm004.certified(ok)
    assert not fm004.certified(dict(ok, final_audit_passed=False))
    assert not fm004.certified(dict(ok, relative_residual=np.array([1e-6, 4e-3, 1e-6])))
    assert not fm004.certified(dict(ok, relative_residual=None))


def test_existing_run_folder_is_refused(tmp_path):
    (tmp_path/'runs'/fm004.f.HIGH/'0082').mkdir(parents=True)
    with pytest.raises(FileExistsError):
        fm004.continue_one(fm004.f.HIGH, 'phase1', 82, tmp_path)
