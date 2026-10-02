import numpy as np

from experiments.cleaned_interface.geometry import ProjectedUpdate, project
from experiments.cleaned_interface.nu003 import SpectralProjectedUpdate, spectral_project
from experiments.shape_continuation.geometry import FourierCurve


def kite(K=24):
    t = 2*np.pi*np.arange(1024)/1024
    z = (np.cos(t)+.65*np.cos(2*t)-.65)+1.5j*np.sin(t)
    return FourierCurve.from_samples(z, K)


def test_circle_projection_is_exact():
    circle = FourierCurve(np.array([0, 0, .1+.2j, 1.3, 0]))  # modes -2..2: centre and radius
    a = np.zeros(5)
    coefficients, error = spectral_project(circle, a, circle.band, 1024, 1.)
    assert np.allclose(coefficients, circle.coefficients, atol=1e-14) and error < 1e-13


def test_spectral_matches_spline_projection_to_spline_error():
    curve, unit = kite(), .05
    a = np.random.default_rng(0).normal(size=7)*2e-4
    spline, _ = project(curve, a, curve.band, 1024, unit)
    fine, _ = project(curve, a, curve.band, 4096, unit)
    spectral, _ = spectral_project(curve, a, curve.band, 1024, unit)
    assert np.max(np.abs(spectral-fine)) < np.max(np.abs(spline-fine))
    assert np.max(np.abs(spectral-spline)) < 1e-7


def test_update_keeps_ci001_contract():
    curve, unit = kite(), .05
    spline, spectral = ProjectedUpdate(unit), SpectralProjectedUpdate(unit)
    s, p = spline.prepare(curve, 3, curve.band), spectral.prepare(curve, 3, curve.band)
    assert p.derivatives.shape == s.derivatives.shape
    rel = np.linalg.norm(p.derivatives-s.derivatives, axis=0)/np.linalg.norm(s.derivatives, axis=0)
    assert np.max(rel) < 1e-5
    assert spectral.trial(p, np.zeros(7))[0] is curve
    a = np.random.default_rng(1).normal(size=7)*1e-4
    candidate, info = spectral.trial(p, a)
    assert info['projection_relative'] < 1e-10 and spectral.settings()['construction'].startswith('z + P_K[R(')
