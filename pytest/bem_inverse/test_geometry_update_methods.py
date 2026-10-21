"""Sampled spectral updates retain the prepared map and reject invalid moves."""
import numpy as np
import pytest

from bem_inverse import Execution, FourierCurve
from bem_inverse.continuation.geometry import resize
from bem_inverse.errors import UpdateRefused
from bem_inverse.geometry_selection import make_update


def test_sampled_spectral_matches_certified_construction_without_certificates():
    execution = Execution(device='cpu')
    sampled = make_update('spectral', .05, execution)
    certified = make_update('certified_spectral', .05, execution)
    curve = resize(FourierCurve.circle(), 8)
    current = sampled.prepare(curve, 2, curve.band)
    reference = certified.prepare(curve, 2, curve.band)
    np.testing.assert_array_equal(current.derivatives, reference.derivatives)
    np.testing.assert_array_equal(current.base_projection, reference.base_projection)
    np.testing.assert_array_equal(current.fine_base_projection, reference.fine_base_projection)

    zero, _ = sampled.geometry_update(np.zeros(5), prepared=current)
    assert zero is curve
    step = np.array([1e-4, -2e-4, 1e-4, 1.5e-4, 0.])
    candidate, report = sampled.geometry_update(step, prepared=current)
    expected, _ = certified.geometry_update(step, prepared=reference)
    np.testing.assert_array_equal(candidate.coefficients, expected.coefficients)
    assert report['projection_relative'] < sampled.projection_tolerance
    assert sampled.counts['trial_constructions'] == 2
    assert not any('certificate' in key for key in sampled.counts)


def test_sampled_spectral_reports_crossing_and_preserves_the_base():
    update = make_update('spectral', .05, Execution(device='cpu'))
    curve = resize(FourierCurve.circle(), 8)
    prepared = update.prepare(curve, 2, curve.band)
    before = curve.coefficients.copy()
    # A cos(2s) normal displacement larger than the radius creates crossing lobes.
    step = np.array([0., 0., .08, 0., 0.])
    with pytest.raises(UpdateRefused) as refusal:
        update.geometry_update(step, prepared=prepared)
    assert refusal.value.reason == 'self_intersection'
    assert update.counts['refused_trials'] == 1
    np.testing.assert_array_equal(curve.coefficients, before)
    # The compatibility entry must produce the same refusal and count the call once.
    with pytest.raises(UpdateRefused) as repeated:
        update.trial(prepared, step)
    assert repeated.value.reason == 'self_intersection'
    assert update.counts['trial_constructions'] == 2
    assert update.counts['refused_trials'] == 2
