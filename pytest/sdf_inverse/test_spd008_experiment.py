"""The experiment freezes inputs while allowing live documentation progress."""
import pytest
from experiments.spd008_geometry import common as c, run, qualify


def test_prepared_campaign_uses_archived_plan_not_live_status(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'ROOT',tmp_path)
    monkeypatch.setattr(c,'sources',lambda: {})
    plan = tmp_path/'plan.md'; plan.write_text('approved design\n')
    monkeypatch.setattr(c,'PLAN',plan)
    bundle = tmp_path/'run';bundle.mkdir()
    log = bundle/'tests.log';log.write_text('passed\n')
    c.write(bundle/'tests.json',dict(status='PASS',source_sha256={},log_sha256=c.sha(log)))
    for phase in ('geometry','updates'):
        folder = bundle/phase;folder.mkdir()
        c.write(folder/'manifest.json',dict(source_sha256={},input_sha256={}))
        c.write(folder/'qualification.json',dict(status='PASS',full_campaign_released=True))
    def make_arm(parent,label,scenes):
        target = parent/label;target.mkdir()
        c.write(target/'contract.json',dict(scenes=scenes))
        c.write(target/'manifest.json',{})
        return target
    monkeypatch.setattr(c.previous,'make_arm',make_arm)
    out = run.prepare(bundle)
    plan.write_text('approved design\nprogress update\n')
    c.verify(out)
    assert (out/'approved_plan.md').read_text()=='approved design\n'
    (out/'approved_plan.md').write_text('altered frozen design\n')
    with pytest.raises(RuntimeError,match='input drift'):
        c.verify(out)


def test_preserved_attempts_reduce_the_original_diagnostic_budget(tmp_path):
    folder = tmp_path/'updates_attempt_01';folder.mkdir()
    c.write(folder/'qualification.json',dict(seconds=215.,work=dict(budget_work_units=113)))
    assert qualify.remaining_budget(tmp_path,'updates',1800,2000)==(1585.,1887)
    with pytest.raises(RuntimeError,match='budget exhausted'):
        qualify.remaining_budget(tmp_path,'updates',200,2000)
