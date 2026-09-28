"""The replay wrapper must stage the manifest consumed by the archived worker."""
from types import SimpleNamespace

from ordered_boundary.validation_cache import current_validation_cache
from . import run


def test_inverse_worker_stages_manifest_and_uses_independent_audit_cache(tmp_path, monkeypatch):
    manifest = dict(inputs={'frozen-observations': 'input-hash'}, state_arm='once')
    seen = []
    def audit():
        assert current_validation_cache() is not None
        seen.append(current_validation_cache())
        return True
    module = SimpleNamespace(c=SimpleNamespace(write=run.write, audit=audit), forecast=audit)
    def worker(job):
        assert job == ('wrong_circle', 'fixed')
        assert run.read(tmp_path/'manifest.json') == manifest
        assert module.c.audit() and module.forecast()
        return dict(outcome='NORMAL_OPTIMIZER_RETURN', audit_passed=True)
    module.worker = worker
    replay = SimpleNamespace(load_sc043=lambda out: (module, manifest))
    monkeypatch.setattr(run, 'load', lambda *args: replay)
    monkeypatch.setattr(run, 'verify', lambda folder: None)
    run.inverse_worker(tmp_path, tmp_path, 'wrong_circle', 'both')
    assert len(seen) == 2 and seen[0] is not seen[1]
    assert all(cache.retained_bytes == 0 for cache in seen)
    assert current_validation_cache() is None
    assert (tmp_path/'geometry_checks.json').exists()
