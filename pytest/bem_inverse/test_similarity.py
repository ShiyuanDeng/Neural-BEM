"""Exact finite similarity moves and their physical-metre tangent."""
import numpy as np
import pytest

from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.updates import UpdateRefused
from bem_inverse.similarity import SimilarityUpdate


@pytest.mark.parametrize('unit', [1., .05])
def test_similarity_preserves_circle_and_physical_radius(unit):
    curve = FourierCurve.circle(.35/unit, (.03+.04j)/unit)
    update = SimilarityUpdate(unit)
    space = update.prepare(curve, 0, 1)
    np.testing.assert_allclose(space.radius_m, .35, rtol=2e-16)
    assert tuple(space.orders) == (1, 1, 0)
    step = np.array([.013, -.017, -.012])
    trial, details = update.trial(space, step)
    centre = .03+.04j+complex(*step[:2])
    np.testing.assert_allclose(abs(trial.values(2048)*unit-centre), .338, rtol=0, atol=3e-16)
    np.testing.assert_allclose(trial.coefficients[1]*unit, centre, rtol=0, atol=1e-17)
    assert details['refits'] == 0 and details['intrinsic_validity_preserved']
    np.testing.assert_allclose(details['equivalent_radius_m'], .338)
    assert update.trial(space, [0, 0, 0])[0] is curve
    nodes = curve.nodes(2048)
    physical_velocity = update.velocities(space, nodes)*unit
    np.testing.assert_allclose(physical_velocity[:, :2], nodes.normals, atol=1e-15)
    np.testing.assert_allclose(physical_velocity[:, 2], 1., atol=1e-15)
    np.testing.assert_allclose(update.metric(space, 'mass'), np.diag([.5, .5, 1.]), atol=2e-15)
    motion = update.measure(space, step)
    np.testing.assert_allclose(motion['rms_normal_m']**2, .5*sum(step[:2]**2)+step[2]**2, rtol=1e-14)
    trial.validate()


@pytest.mark.parametrize('unit', [1., .05])
def test_similarity_curved_shape_scaling_tangent_and_normal_measure(unit):
    physical = np.array([.004j, .007, .03+.04j, .2, .014j])
    curve = FourierCurve(physical/unit)
    update = SimilarityUpdate(unit)
    space = update.prepare(curve, 3, curve.band)
    step = np.array([.013, -.017, .008])
    trial, details = update.trial(space, step)
    keep = np.arange(len(physical)) != curve.band
    factor = 1+step[2]/space.radius_m
    np.testing.assert_array_equal(trial.coefficients[keep], curve.coefficients[keep]*factor)
    np.testing.assert_allclose(trial.coefficients[curve.band], curve.coefficients[curve.band]+complex(*step[:2])/unit)
    np.testing.assert_allclose(trial.values(2048, 1), factor*curve.values(2048, 1), rtol=1e-14, atol=1e-14)
    trial_nodes, nodes = trial.validate(), curve.nodes(2048)
    np.testing.assert_allclose(trial_nodes.signed_area/curve.validate().signed_area, factor**2, rtol=1e-14)
    for j in range(3):
        delta = np.eye(3)[j]*1e-7
        plus, _ = update.trial(space, delta)
        minus, _ = update.trial(space, -delta)
        np.testing.assert_allclose((plus.coefficients-minus.coefficients)/2e-7,
                                   space.derivatives[:, j], rtol=2e-9, atol=1e-11)
    actual_motion = (trial.values(2048)-curve.values(2048))*unit
    normal = nodes.normals[:, 0]+1j*nodes.normals[:, 1]
    actual_normal = (actual_motion*np.conj(normal)).real
    np.testing.assert_allclose(update.velocities(space, nodes)@step*unit, actual_normal, rtol=1e-12, atol=1e-15)
    metric = update.metric(space, 'mass')
    np.testing.assert_allclose(step@metric@step, details['rms_normal_m']**2, rtol=1e-14)
    assert details['scale_factor'] == factor


def test_similarity_rejects_invalid_base_or_scale():
    update = SimilarityUpdate(1.)
    with pytest.raises(ValueError):
        update.prepare(FourierCurve([1., 0., 0.]), 0, 1)
    space = update.prepare(FourierCurve.circle(.2), 0, 1)
    for radius_change in (-.2, -.3):
        with pytest.raises(UpdateRefused, match='invalid_scale'):
            update.trial(space, [0, 0, radius_change])
    assert update.counts['refused_trials'] == 2
    for step in ([0, 0], [0, 0, np.nan], [0, 0, np.inf]):
        with pytest.raises(ValueError):
            update.trial(space, step)
    with pytest.raises(ValueError):
        update.prepare(space.curve, 0, 2)
