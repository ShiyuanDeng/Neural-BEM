"""DP-001 must retain screen failures and refuse unapproved inverse dispatch."""
import pytest
from experiments.benchmark import dp001 as d


def test_unapproved_run_cannot_reach_verification_or_dispatch(monkeypatch):
    def unexpected():
        pytest.fail('Unapproved run reached benchmark verification')
    monkeypatch.setattr(d, 'verify', unexpected)
    with pytest.raises(ValueError, match='ID approval'):
        d.run('F', 'screen', None)


def measured(recovered):
    return dict(recovered=recovered, audited_output_seconds=1., case_seconds=2.)


def test_screen_gate_retains_a_failed_pair_and_blocks_continuation(tmp_path, monkeypatch):
    e = {k: measured(True) for k in d.SCREEN}
    f = {k: measured(k != d.SCREEN[-1]) for k in d.SCREEN}
    monkeypatch.setattr(d, 'OUTPUT', tmp_path)
    monkeypatch.setattr(d, 'rows', lambda arm: e if arm=='E' else f)
    result=d.report()
    assert result['screen_complete']
    assert result['recovery_regressions']==[d.SCREEN[-1]]
    assert not result['remaining_allowed']
    assert len(result['paired_success_speedups'])==8


def test_missing_pair_does_not_pass_the_screen_gate(tmp_path, monkeypatch):
    e = {k: measured(True) for k in d.SCREEN}
    f = {k: measured(True) for k in d.SCREEN[:-1]}
    monkeypatch.setattr(d, 'OUTPUT', tmp_path)
    monkeypatch.setattr(d, 'rows', lambda arm: e if arm=='E' else f)
    result=d.report()
    assert not result['screen_complete'] and not result['remaining_allowed']
