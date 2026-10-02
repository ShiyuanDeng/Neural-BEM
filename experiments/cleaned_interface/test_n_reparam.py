import numpy as np

from experiments.cleaned_interface.n_reparam import reparameterize, reset, shape_distance, speed_ratio
from experiments.shape_continuation.geometry import FourierCurve


def ellipse(K=16):
    z = np.zeros(2*K+1, complex)
    z[K+1], z[K-1] = 1.5, .5          # semi-axes 2 and 1, speed ratio 2 in theta
    return z


def test_ellipse_reset_is_arclength_and_shape_preserving_with_enough_band():
    z = ellipse()
    new, info = reparameterize(z, 64)
    assert info['converged']
    assert speed_ratio(z) > 1.99
    assert speed_ratio(new) < 1+1e-8
    assert shape_distance(z, new) < 1e-9


def test_crop_error_decays_with_band():
    z = ellipse()
    errors = [shape_distance(z, reparameterize(z, b)[0]) for b in (16, 24, 32, 48)]
    assert all(b < a/5 for a, b in zip(errors, errors[1:]))


def test_reparameterization_is_idempotent_and_keeps_circles():
    z = ellipse()
    once, _ = reparameterize(z, 64)
    twice, _ = reparameterize(once)
    assert np.sum(np.abs(twice-once)) < 1e-10*np.sum(np.abs(once))
    circle = np.zeros(9, complex)
    circle[4], circle[5] = .3+.1j, 2.
    assert np.allclose(reparameterize(circle)[0], circle, atol=1e-14)


def test_reset_refuses_a_shape_changing_crop():
    curve = FourierCurve(ellipse())
    refused, info = reset(curve, shape_tolerance=1e-6)
    assert refused is None and info['shape_relative'] > 1e-6
    accepted, info = reset(FourierCurve(np.pad(ellipse(), 48)), shape_tolerance=1e-6)
    assert accepted is not None and info['speed_ratio_after'] < 1+1e-6
