"""The revised schedule preserves the prefix and carries accepted states."""
from dataclasses import replace

import numpy as np
import pytest

from bem_inverse.continuation_policy import ShapeFrequencyPolicy
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.lm_backend import StageResult
from bem_inverse.continuation.forward import PointSourceAcquisition
from bem_inverse.geometry import resize
from bem_inverse.geometry_selection import describe_plan
from bem_inverse.modal_muller import ModalMuller
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from bem_inverse.problem import Problem, Observation
from bem_inverse.similarity import SimilarityUpdate
from bem_inverse import runner


def fixture():
    angles = np.arange(8)*2*np.pi/8
    ring = 6*np.column_stack((np.cos(angles), np.sin(angles)))
    acquisition = PointSourceAcquisition(ring, 1.05*ring, 1e-6)
    frequencies = (.25e9, .5e9, .75e9, 1e9, 1.25e9, 2.5e9)
    real = tuple(Observation(f/1.25e9*3.2, acquisition, np.ones(8, complex), f) for f in frequencies)
    damped = tuple(replace(o, wavenumber=o.wavenumber*(1+.25j)) for o in real)
    return Problem(FourierCurve.circle(1.3), real, damped, 4.)


def test_prefix_is_exactly_preserved_and_four_shapes_use_full_real_catalog():
    problem, physics = fixture(), ModalMuller(Execution(device='cpu'))
    base = CumulativePolicy().operations(problem, physics)
    policy = ShapeFrequencyPolicy()
    revised = policy.operations(problem, physics)
    old_prefix = [o.record() for o in base if o.label.startswith('stage_')]
    new_prefix = [o.record() for o in revised if o.label.startswith('stage_')]
    assert new_prefix == old_prefix
    fits = [o for o in revised if o.kind == 'fit']
    init = fits[0]
    assert init.fit_geometry_update == 'similarity'
    assert (init.stage.update_modes, init.stage.curve_modes) == (0, 4)
    assert init.stage.observations == (problem.damped[0],)
    shapes = fits[-5:]
    assert [(o.stage.update_modes, o.stage.curve_modes) for o in shapes] == [
        (11, 24), (15, 32), (19, 40), (25, 52), (95, 192)]
    assert all(o.stage.observations is not None and
               all(a is b for a, b in zip(o.stage.observations, problem.real)) and
               len(o.stage.observations) == len(problem.real) for o in shapes)
    assert not any(o.kind in ('frontier', 'cleanup') or o.cleanup_band for o in revised)
    plan = describe_plan(policy.plan(problem, physics), {'construction': 'spectral'})
    assert plan['operations'][2]['geometry_update'] == 'similarity'
    assert plan['operations'][3]['geometry_update'] == 'spectral'


@pytest.mark.parametrize('settings', [dict(shape_bands=(11, 15, 19)),
    dict(shape_bands=(9, 15, 19, 25)), dict(shape_bands=(11, 15, 19, 25), full_release_band=25),
    dict(storage_band=52), dict(shape_bands=(11., 15, 19, 25))])
def test_non_increasing_or_incomplete_ladders_are_refused(settings):
    with pytest.raises(ValueError):
        ShapeFrequencyPolicy(**settings).operations(fixture(), ModalMuller(Execution(device='cpu')))


@pytest.mark.parametrize('failure', [False, True])
def test_runner_switches_only_initial_fit_and_keeps_spectral_audits(monkeypatch, tmp_path, failure):
    physics, problem = ModalMuller(Execution(device='cpu')), fixture()
    calls, audited, inherited = [], [], []
    def fake_audit(curve, stage, config, problem, physics, update, seconds):
        assert not isinstance(update, SimilarityUpdate)
        audited.append((stage.update_modes, curve.coefficients.copy()))
        return dict(passed=True, relative_residual=np.ones(len(problem.real)), seconds=0., work={})
    def fake_fit(curve, stage, contrast, update, config, ledger, **kwargs):
        calls.append((stage.label, isinstance(update, SimilarityUpdate)))
        if len(calls) == 1:
            final = update.trial(update.prepare(curve, 0, curve.band), [.013, -.008, -.006])[0]
            inherited.append(final)
        else:
            np.testing.assert_array_equal(curve.coefficients, resize(inherited[0], curve.band).coefficients)
            final = curve
        return StageResult(stage.label, final,
            'NUMERICAL_FAILURE' if failure else 'NORMAL_OPTIMIZER_RETURN',
            'gradient_tolerance', True, 1, 1., .5, [], [], [], detail='fixture' if failure else None)
    monkeypatch.setattr(runner, 'fit_stage', fake_fit)
    result = runner.fit(problem, physics=physics, policy=ShapeFrequencyPolicy(), output=tmp_path,
        geometry_update='spectral', localization_adapter=lambda p, *args: (p.initial, {}),
        audit_adapter=fake_audit)
    assert calls[0] == ('initialize_translation_scale', True)
    assert all(not similarity for _, similarity in calls[1:])
    assert len(calls) == (1 if failure else 11)
    assert len(audited) == 2 and audited[0][0] == 1
    assert audited[-1][0] == (1 if failure else 95)
    np.testing.assert_array_equal(result['final_curve']['real'],
        resize(inherited[0], 4 if failure else 192).coefficients.real)
    assert result['outcome'] == ('NUMERICAL_FAILURE' if failure else 'COMPLETED_SCHEDULE')
    assert result['stage_geometry_updates']['similarity']['work']['trial_constructions'] == 1
