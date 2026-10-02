import numpy as np
import pytest

from experiments.cleaned_interface.nu003 import SpectralProjectedUpdate
from experiments.cleaned_interface.nu005 import CertifiedSpectralUpdate, regularity_floor
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.updates import UpdateRefused


def kite(K=24):
    t = 2*np.pi*np.arange(1024)/1024
    z = (np.cos(t)+.65*np.cos(2*t)-.65)+1.5j*np.sin(t)
    return FourierCurve.from_samples(z, K)


def test_small_step_is_certified_and_identical():
    curve, unit = kite(), .05
    plain, tiered = SpectralProjectedUpdate(unit), CertifiedSpectralUpdate(unit, shadow=True)
    p, c = plain.prepare(curve, 3, curve.band), tiered.prepare(curve, 3, curve.band)
    a = np.random.default_rng(1).normal(size=7)*1e-5
    expected, _ = plain.trial(p, a)
    candidate, info = tiered.trial(c, a)
    assert np.array_equal(candidate.coefficients, expected.coefficients)
    assert set(info['validity_tiers'].values()) <= {'increment', 'full'}
    assert tiered.counts['shadow_disagreements'] == 0
    assert sum(tiered.counts[f'{r}_sampled_accepted'] for r in ('moved_coarse', 'moved_fine', 'candidate')) == 0


def test_certify_refuses_reversed_and_accepts_circle():
    unit = .05
    circle = FourierCurve(np.array([0, 0, 0, 1.3, 0]))
    update = CertifiedSpectralUpdate(unit)
    space = update.prepare(circle, 2, circle.band)
    tier, row = update.certify(space, circle.coefficients[::-1])   # clockwise circle
    assert tier == 'refused' and row['signed_area'] < 0
    tier, _ = update.certify(space, circle.coefficients*1.01)
    assert tier == 'increment'


def test_large_step_falls_back_with_same_refusal():
    curve, unit = kite(), .05
    plain, tiered = SpectralProjectedUpdate(unit), CertifiedSpectralUpdate(unit)
    p, c = plain.prepare(curve, 3, curve.band), tiered.prepare(curve, 3, curve.band)
    a = np.zeros(7)
    a[0] = -2.   # shrink by 2 m: the moved curve turns inside out
    with pytest.raises(UpdateRefused) as first:
        plain.trial(p, a)
    with pytest.raises(UpdateRefused) as second:
        tiered.trial(c, a)
    assert first.value.reason == second.value.reason


def test_regularity_floor_is_parseval_bound():
    x = kite().coefficients
    modes = np.arange(-(len(x)//2), len(x)//2+1)
    assert regularity_floor(x) == pytest.approx(1e-12*np.sum(modes**2*np.abs(x)**2))
