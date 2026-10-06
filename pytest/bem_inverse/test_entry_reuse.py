"""Stage-entry reuse is exact: identical decisions and ledgers, fewer physics solves."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from bem_inverse import runner
from bem_inverse.continuation import lm_backend as lm
from bem_inverse.continuation.forward import ordered_calls
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.lm_backend import StageResult
from bem_inverse.modal_muller import ModalMuller
from bem_inverse.physics import Execution, Prediction
from bem_inverse.policy import CumulativePolicy
from test_continuation_policy import fixture
from test_resolution_resume import ScalarUpdate


class TwoFrequencyPhysics:
    """Deterministic radius model: prediction k*r, refined adds a tiny resolution term."""

    def __init__(self):
        self.calls = []

    def ordered_calls(self, function, items):
        return ordered_calls(function, items, threads=2)

    def evaluate(self, curve, obs, contrast, nodes):
        radius = curve.coefficients[-1].real
        self.calls.append((nodes, round(radius, 12), obs.wavenumber))
        return Prediction(np.array([obs.wavenumber*radius*(1+1e-12/nodes)], complex), dict(nodes=nodes), nodes)

    def derivative(self, evaluation, update, space):
        return np.array([[evaluation.prediction[0]/max(abs(evaluation.prediction[0]), 1e-30)]], complex)


def stages():
    observations = tuple(SimpleNamespace(scattered=np.array([k*1.6], complex), wavenumber=k) for k in (1., 2.))
    first = lm.FitStage('first', observations, (.5, .5), (1e-3, 1e-3), 0, 1, 8, 16, 1, 40)
    return first, replace(first, label='second', iterations=4)


def run(reuse, *, strict=False):
    physics, (first, second) = TwoFrequencyPhysics(), stages()
    ledger = lm.Ledger(cap=500, clock=lambda: 0., endpoint_reserve=0, strict_dispatch=strict)
    config = lm.BackendConfig(step_bounds_m=(.15,)*3, max_damping_trials=2)
    ledger.begin_stage('first', first.quota)
    a = lm.fit_stage(FourierCurve.circle(2), first, .5, ScalarUpdate(), config, ledger, physics=physics,
                     retain_final=True)
    ledger.begin_stage('second', second.quota)
    before = len(physics.calls)
    b = lm.fit_stage(a.curve, second, .5, ScalarUpdate(), config, ledger, physics=physics,
                     entry=a.final_entry if reuse else None)
    return a, b, ledger.snapshot(), len(physics.calls)-before, second


@pytest.mark.parametrize('strict', [False, True])
def test_reused_entry_reproduces_the_stage_and_its_charges(strict):
    a0, fresh, ledger0, calls0, _ = run(False, strict=strict)
    a1, reused, ledger1, calls1, _ = run(True, strict=strict)
    assert a1.final_entry is not None and a1.final_entry.refined_prediction is not None
    assert not fresh.entry_reused and reused.entry_reused
    assert fresh.accepted_steps >= 1
    for key in ('outcome', 'stop_reason', 'accepted_steps', 'initial_loss', 'final_loss'):
        assert getattr(fresh, key) == getattr(reused, key)
    assert fresh.history == reused.history and fresh.trials == reused.trials
    assert fresh.acceptance_checks == reused.acceptance_checks
    np.testing.assert_array_equal(fresh.curve.coefficients, reused.curve.coefficients)
    assert ledger0 == ledger1
    # The base production and the base refined solve at both frequencies are skipped.
    assert calls0-calls1 == 4


def test_entry_requires_the_same_curve_catalog_and_resolution():
    a, _, _, _, second = run(False)
    entry = a.final_entry
    assert entry.matches(a.curve, second, .5, entry.physics)
    assert not entry.matches(a.curve, replace(second, nodes=10, refined_nodes=20), .5, entry.physics)
    assert not entry.matches(FourierCurve.circle(1.7), second, .5, entry.physics)
    assert not entry.matches(a.curve, second, .6, entry.physics)
    assert not entry.matches(a.curve, second, .5, object())
    other = tuple(SimpleNamespace(**vars(o)) for o in second.observations)
    assert not entry.matches(a.curve, replace(second, observations=other), .5, entry.physics)


@pytest.mark.parametrize('enabled', [False, True])
def test_runner_carries_entries_between_stages_and_drops_them_at_cleanup(monkeypatch, tmp_path, enabled):
    physics, problem = ModalMuller(Execution(device='cpu', stage_entry_reuse=enabled)), fixture()
    seen = []
    def fake_fit(curve, stage, contrast, update, config, ledger, **kwargs):
        seen.append((stage.label, kwargs['entry'], kwargs['retain_final']))
        return StageResult(stage.label, curve, 'NORMAL_OPTIMIZER_RETURN', 'gradient_tolerance', True, 0, 1., 1.,
                           [], [], [], final_entry=('endpoint', stage.label), entry_reused=kwargs['entry'] is not None)
    def fake_audit(curve, stage, config, problem, physics, update, seconds):
        return dict(passed=True, relative_residual=np.ones(len(problem.real)), seconds=0., work={})
    monkeypatch.setattr(runner, 'fit_stage', fake_fit)
    monkeypatch.setattr(physics, 'observable_frontier', lambda *args: dict(frontier=0))
    result = runner.fit(problem, physics=physics, policy=CumulativePolicy(), output=tmp_path,
        geometry_update='spectral', localization_adapter=lambda p, *args: (p.initial, {}), audit_adapter=fake_audit)
    labels = [label for label, _, _ in seen]
    assert labels[0] == 'warmup_025_damped' and 'fixed_M25' in labels
    for index, (label, entry, retain) in enumerate(seen):
        assert retain is enabled
        if not enabled or index == 0 or label == 'fixed_M25':  # fixed_M25 follows the one-time cleanup
            assert entry is None, label
        else:
            assert entry == ('endpoint', labels[index-1]), label
    assert all(('entry_reused' in row) is enabled for row in result['stages'])
