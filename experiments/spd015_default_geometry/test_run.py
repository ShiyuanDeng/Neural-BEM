"""Qualification must measure the unset default and preserve caller settings."""
import os
import pickle
import pytest

from experiments.shape_continuation.geometry_runtime import geometry_mode
from experiments.shape_continuation.latest_video import load_renderer, prepare_case
from .run import native_arm


def test_candidate_really_uses_unset_default_and_restores_environment(monkeypatch):
    monkeypatch.setenv('SC_GEOMETRY_RUNTIME', 'reference')
    with pytest.raises(RuntimeError):
        with native_arm('both'):
            assert 'SC_GEOMETRY_RUNTIME' not in os.environ
            assert geometry_mode() == 'both'
            raise RuntimeError('worker failure')
    assert os.environ['SC_GEOMETRY_RUNTIME'] == 'reference'
    with native_arm('spatial'):
        assert geometry_mode() == 'spatial'
    assert geometry_mode() == 'reference'


def test_video_worker_is_importable_and_diagnostics_are_scoped():
    renderer = load_renderer()
    assert renderer.prepare_case is prepare_case
    assert pickle.loads(pickle.dumps(renderer.prepare_case)) is prepare_case
    assert renderer.diagnostic.__wrapped__.__name__ == 'diagnostic'
    assert renderer.original_prepare_case is not prepare_case
