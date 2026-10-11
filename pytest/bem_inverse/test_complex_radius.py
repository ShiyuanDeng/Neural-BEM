"""Independent controls for a genuine complex-radius continuation instrument."""
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.special import hankel1, h1vp, jv, jvp

from bem_inverse.complex_radius import (ComplexDomainError, Cubic, DiskHomotopy,
    circle_path, coefficient_jets, pseudo_arclength, track)
from bem_inverse.continuation.forward import PointSourceAcquisition
from bem_inverse.mie_localize import paired_data


def model():
    angles = np.linspace(0, 2*np.pi, 8, endpoint=False)
    points = lambda a: 6*np.column_stack([np.cos(a), np.sin(a)])
    acq = PointSourceAcquisition(points(angles), points(angles+.07))
    observed = paired_data(2., 4., [.2+.1j], [1.], acq.sources, acq.receivers, 36)[0, 0]
    return DiskHomotopy([SimpleNamespace(wavenumber=2., acquisition=acq, scattered=observed)], 4.)


def test_complex_coefficients_match_wronskian_formula_and_cauchy_derivatives():
    q, k, contrast, cutoff = 1.1+.03j, 2., 4., 30
    jets, margin = coefficient_jets(k, contrast, q, cutoff)
    n = np.arange(-cutoff, cutoff+1)
    ki = k*np.sqrt(contrast)
    D = k*jv(n, ki*q)*h1vp(n, k*q)-ki*jvp(n, ki*q)*hankel1(n, k*q)
    reference = .25j*((2j/(np.pi*q))*jv(n, ki*q)/D-jv(n, k*q))/hankel1(n, k*q)
    np.testing.assert_allclose(jets[0], reference, rtol=1e-9, atol=1e-13)
    angles = 2*np.pi*np.arange(64)/64
    rho = .004
    samples = coefficient_jets(k, contrast, q+rho*np.exp(1j*angles), cutoff, degree=0)[0][:, 0]
    for derivative, factorial in ((1, 1), (2, 2), (3, 6)):
        cauchy = factorial*np.mean(samples*np.exp(-1j*derivative*angles[:, None]), axis=0)/rho**derivative
        np.testing.assert_allclose(jets[derivative], cauchy, rtol=2e-6, atol=3e-7)
    assert margin > 1e-10


def test_mirror_extension_matches_real_loss_and_is_holomorphic_off_axis():
    instrument = model()
    q, t, h = 1.1, .6, 2e-5
    gradient = (instrument.real_loss(q+h, t)-instrument.real_loss(q-h, t))/(2*h)
    assert abs(gradient-instrument.state(q, t)['F']) < 2e-7
    assert abs(instrument.state(1.3, 0)['F']) < 1e-12
    q, t = 1.1+.025j, .6+.02j
    st = instrument.state(q, t)
    for direction in (1., 1j):
        plus = instrument.state(q+direction*h, t)
        minus = instrument.state(q-direction*h, t)
        np.testing.assert_allclose((plus['F']-minus['F'])/(2*direction*h), st['Fq'], rtol=2e-6)
        np.testing.assert_allclose((plus['Fq']-minus['Fq'])/(2*direction*h), st['Fqq'], rtol=2e-6)
    mirrored = instrument.state(q.conjugate(), t.conjugate())
    for key in ('F', 'Fq', 'Fqq', 'Ft'):
        np.testing.assert_allclose(mirrored[key], np.conj(st[key]), atol=1e-12)


def test_fold_monodromy_swaps_sheets_and_second_loop_restores():
    cubic = Cubic()
    base = 1.9
    roots = np.sort(np.roots([1., 0., -3., -base]))
    q = roots[0]
    one = track(cubic, q, circle_path(2., .1, np.pi))
    assert one['status'] == 'COMPLETED'
    np.testing.assert_allclose(one['states'][-1]['q'], roots[1], atol=1e-8)
    two = track(cubic, q, circle_path(2., .1, np.pi, turns=2, points=512))
    assert two['status'] == 'COMPLETED'
    np.testing.assert_allclose(two['states'][-1]['q'], q, atol=1e-8)
    assert max(abs(r['q'].imag) for r in two['states']) > .1


def test_real_arclength_passes_fold_that_natural_parameter_cannot():
    cubic = Cubic()
    q = np.sort(np.roots([1., 0., -3., -1.9]))[0]
    natural = track(cubic, q, [1.9, 2.1])
    assert natural['status'] == 'MINIMUM_STEP'
    arc = pseudo_arclength(cubic, q, 1.9, direction=1, steps=200, ds=.003)
    assert arc['status'] == 'COMPLETED'
    assert arc['states'][-1]['q'].real > -1
    assert max(r['t'].real for r in arc['states']) > 1.999


def test_nonstationary_starts_are_not_silently_corrected_onto_a_branch():
    with pytest.raises(ValueError, match='stationary root'):
        track(Cubic(), 1., [0., .1])
    with pytest.raises(ValueError, match='stationary root'):
        pseudo_arclength(Cubic(), 1., 0.)


@pytest.mark.parametrize('q', [0., -.1, .25, 2.5, 1+.5j, np.nan])
def test_complex_domain_is_refused_without_projection(q):
    with pytest.raises(ComplexDomainError):
        coefficient_jets(2., 4., q, 30)
