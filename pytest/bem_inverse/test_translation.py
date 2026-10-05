"""Exact rigid-motion geometry and its metre-scaled discrete tangent."""
import numpy as np
import pytest

from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.translation import TranslationUpdate


@pytest.mark.parametrize('unit', [1., .05])
def test_translation_preserves_shape_and_matches_complete_tangent(unit):
    physical = np.array([.004j, .007, .03+.04j, .2, .014j])
    curve = FourierCurve(physical/unit)
    update = TranslationUpdate(unit)
    space = update.prepare(curve, 3, curve.band)
    step = np.array([.013, -.017])
    trial, details = update.trial(space, step)
    keep = np.arange(len(physical)) != curve.band
    np.testing.assert_array_equal(trial.coefficients[keep], curve.coefficients[keep])
    np.testing.assert_allclose((trial.values(2048)-curve.values(2048))*unit,
                               complex(*step), rtol=0, atol=2e-15)
    np.testing.assert_allclose(trial.values(2048, 1), curve.values(2048, 1), rtol=0, atol=0)
    np.testing.assert_array_equal(update.trial(space, [0,0])[0].coefficients, curve.coefficients)
    for j in range(2):
        delta = np.eye(2)[j]*1e-7
        plus, _ = update.trial(space, delta)
        minus, _ = update.trial(space, -delta)
        np.testing.assert_allclose((plus.coefficients-minus.coefficients)/2e-7,
                                   space.derivatives[:,j], rtol=1e-9, atol=1e-12)
    assert details['refits'] == 0
    assert details['intrinsic_geometry_preserved']
    trial.validate()


def test_translation_normal_velocities_have_correct_units():
    update = TranslationUpdate(.2)
    curve = FourierCurve.circle(1., .1+.1j)
    space = update.prepare(curve, 0, 1)
    nodes = curve.nodes(2048)
    np.testing.assert_allclose(update.velocities(space,nodes)*.2,nodes.normals)
    np.testing.assert_allclose(update.metric(space,'mass'),np.eye(2)*.5,atol=1e-14)
    assert tuple(space.orders) == (1,1)
    for bad in ([1.], [1.,2.,3.], [np.nan,0.]):
        with pytest.raises(ValueError):
            update.trial(space,bad)


def test_translation_refuses_invalid_base():
    update = TranslationUpdate(1.)
    with pytest.raises(ValueError):
        update.prepare(FourierCurve([1.,0.,0.]),3,1)
