"""Do not accidentally add a new entry gate to the registered CI-001 suffix."""
from pathlib import Path

from bem_inverse.io import write
from . import fm003_suffix as suffix


def test_historical_entry_and_real_final_audit(tmp_path,monkeypatch):
    path=tmp_path/'initial_audit.json'
    write(path,dict(passed=True,work=dict(work_units=100)))
    monkeypatch.setattr(suffix.f.b,'path_ref',lambda p:str(p))
    calls=[]
    def final(*args):
        calls.append(args)
        return dict(passed=False,performed=True,work=dict(work_units=2))
    monkeypatch.setattr(suffix,'audit',final)
    adapter=suffix.SuffixAudit(path)
    entry=adapter('winner','stage3')
    assert not calls
    assert entry['passed'] and not entry['performed']
    assert entry['work']['work_units']==0
    end=adapter('endpoint','last_stage')
    assert calls==[('endpoint','last_stage')]
    assert not end['passed'] and end['performed']
