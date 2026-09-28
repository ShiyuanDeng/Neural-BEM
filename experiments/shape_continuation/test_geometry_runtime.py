"""Native geometry default: exact physics, bounded scopes, explicit controls."""
from dataclasses import asdict

import numpy as np
import pytest

from ordered_boundary import sampled_self_intersection_count
from ordered_boundary.validation_cache import (
    current_intersection_backend, current_validation_cache, geometry_validation,
    intersection_validation, validation_cache,
)
from experiments.spd014_geometry.run import checks, strip_timing
from .forward import ordered_calls, solve, shape_jacobian
from .geometry import FourierCurve
from .geometry_runtime import geometry_batch, geometry_mode, geometry_runtime, geometry_validated
from .lm_backend import BackendConfig, Ledger, Objective, fit_stage
from .test_lm_backend import acquisition, observations, stage
from .updates import BorgesUpdate


def test_default_selection_override_and_restoration(monkeypatch):
    monkeypatch.delenv('SC_GEOMETRY_RUNTIME', raising=False)
    assert geometry_mode() == 'both'
    assert current_intersection_backend() == 'reference'
    with geometry_batch():
        assert current_intersection_backend() == 'spatial'
        assert current_validation_cache().mode == 'cache'
    assert current_validation_cache() is None
    assert current_intersection_backend() == 'reference'
    monkeypatch.setenv('SC_GEOMETRY_RUNTIME', 'reference')
    with geometry_batch():
        assert current_validation_cache() is None
        assert current_intersection_backend() == 'reference'
    with geometry_runtime('both'):
        assert geometry_mode() == 'both'
        with geometry_runtime('cache'):
            assert geometry_mode() == 'cache'
    assert geometry_mode() == 'reference'
    monkeypatch.setenv('SC_GEOMETRY_RUNTIME', 'typo')
    with pytest.raises(ValueError, match='SC_GEOMETRY_RUNTIME'):
        with geometry_batch():
            pass
    with pytest.raises(ValueError):
        with geometry_runtime('typo'):
            pass


def test_explicit_controls_take_precedence_and_cache_clears_on_exception():
    with geometry_runtime('both'), validation_cache('reference') as explicit:
        with intersection_validation('reference'), geometry_batch():
            assert current_validation_cache() is explicit
            assert current_intersection_backend() == 'reference'
    caches = []
    @geometry_validated
    def diagnostic(fail=False):
        cache = current_validation_cache()
        caches.append(cache)
        with geometry_batch():
            assert current_validation_cache() is cache
            sampled_self_intersection_count(FourierCurve.circle().nodes(96).points)
        if fail:
            raise RuntimeError('diagnostic failed')
    with geometry_runtime('both'):
        diagnostic()
        with pytest.raises(RuntimeError, match='diagnostic failed'):
            diagnostic(True)
    assert caches[0] is not caches[1]
    assert all(c.retained_bytes == 0 and not c._entries for c in caches)
    assert current_validation_cache() is None


@pytest.mark.parametrize('backend', ['cpu', 'cuda'])
def test_default_forward_jacobian_and_invalid_boundary_match_reference(monkeypatch, backend):
    if backend == 'cuda':
        torch = pytest.importorskip('torch')
        if not torch.cuda.is_available():
            pytest.skip('CUDA unavailable')
    monkeypatch.setenv('SC_FORWARD_BACKEND', backend)
    shape = FourierCurve(np.array([.08, .1+.05j, 1.15]))
    basis = np.cos(np.outer(2*np.pi*np.arange(96)/96, np.arange(1, 4)))
    results = []
    for mode in ('reference', 'both'):
        with geometry_runtime(mode):
            state = solve(shape, 1.25, .5, acquisition(), 96)
            results.append((state.prediction, shape_jacobian(state, basis)))
            with pytest.raises(ValueError):
                solve(FourierCurve(np.array([1., 0., 1.])), 1.25, .5, acquisition(), 96)
    for a, b in zip(*results):
        assert np.array_equal(a, b)


def test_objective_uses_one_shared_check_per_batch_and_reaudits(monkeypatch):
    monkeypatch.setenv('SC_FORWARD_BACKEND', 'cpu')
    monkeypatch.setenv('SC_FREQUENCY_THREADS', '4')
    obs = observations(FourierCurve.circle(1.1), (1., 1.2, 1.4), .5)
    ledger = Ledger(cap=4000, seconds=600)
    ledger.begin_stage('s', None)
    objective = Objective(stage(obs), .5, BackendConfig(), ledger)
    values = []
    with geometry_runtime('both'):
        for _ in range(2):
            with checks() as counters:
                values.append(objective.production(FourierCurve.circle(), 'audit'))
            assert counters['spatial_self_intersection_count']['calls'] == 1
            assert counters['_dense_self_intersection_count']['calls'] == 0
            assert current_validation_cache() is None
    assert np.array_equal(values[0].prediction, values[1].prediction)


def test_fit_trajectory_work_and_explicit_fit_callback_match(monkeypatch):
    monkeypatch.setenv('SC_FORWARD_BACKEND', 'cpu')
    monkeypatch.setenv('SC_FREQUENCY_THREADS', '4')
    obs = observations(FourierCurve.circle(1.1), (1., 1.2), .5)
    update = BorgesUpdate(1.)
    curve, _ = update.regauge(FourierCurve.circle(), 24)
    runs, snapshots = [], []
    for mode in ('reference', 'both'):
        ledger = Ledger(cap=4000, seconds=600)
        ledger.begin_stage('s', None)
        with geometry_runtime(mode), geometry_validation('cache', on_fit=snapshots.append):
            result = fit_stage(curve, stage(obs, iterations=2), .5, update, BackendConfig(), ledger)
        record = asdict(result)
        record.pop('curve')
        runs.append((result.curve.coefficients, strip_timing(record), strip_timing(ledger.snapshot())))
    assert np.array_equal(runs[0][0], runs[1][0])
    assert runs[0][1:] == runs[1][1:]
    assert len(snapshots) == 2 and all(s['entries'] > 0 for s in snapshots)


def test_copied_frequency_context_preserves_runtime_and_cache():
    with geometry_runtime('both'), geometry_batch():
        cache = current_validation_cache()
        with ordered_calls(lambda _: (geometry_mode(), current_intersection_backend(), current_validation_cache()), range(5), 4) as calls:
            assert all(call() == ('both', 'spatial', cache) for call in calls)
