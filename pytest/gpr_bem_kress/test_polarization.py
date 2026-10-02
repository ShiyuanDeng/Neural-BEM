"""Independent physics regressions for the opt-in weighted transmission API."""
import numpy as np
import pytest
from scipy.special import hankel1

from ordered_boundary import circle, ellipse
from gpr_bem_kress.polarization import (
    EPS0, passive_permittivity, passive_wavenumber,
    solve_polarized_transmission, polarized_shape_derivative,
)
from experiments.polarization.run_validation import circle_series, deform, relative_error, ring


@pytest.mark.parametrize("kr,nodes", [(1, 64), (5, 128), (15, 192)])
def test_te_circle_against_separable_series(kr, nodes):
    curve = circle((0, 0), 1).discretize(nodes)
    sources, receivers = ring(3, 3), ring(4, 24, .13)
    result = solve_polarized_transmission(curve, sources, receivers, kr, 2 * kr, normal_ratio=4)
    reference = circle_series(1, sources, receivers, kr, 2 * kr, 4)
    assert relative_error(result.scattered_receiver, reference) < 1e-9
    assert result.relative_residual < 1e-12


@pytest.mark.parametrize("polarization", ["TM", "TE"])
def test_passive_lossy_circle_and_shape_derivative(polarization):
    omega = 2 * np.pi * 5e8
    ko, ki = passive_wavenumber(6, .05, omega), passive_wavenumber(12, .005, omega)
    ratio = 1 if polarization == "TM" else passive_permittivity(12, .005, omega) / passive_permittivity(6, .05, omega)
    curve = circle((0, 0), .2).discretize(128)
    sources, receivers = ring(.6, 3), ring(.8, 20, .07)
    base = solve_polarized_transmission(curve, sources, receivers, ko, ki, normal_ratio=ratio)
    reference = circle_series(.2, sources, receivers, ko, ki, ratio)
    assert relative_error(base.scattered_receiver, reference) < 1e-9
    h = np.cos(3 * curve.parameters) + .3 * np.sin(5 * curve.parameters)
    analytic = polarized_shape_derivative(base, h)[0]
    step = 1e-6
    values = [solve_polarized_transmission(deform(curve, h, sign * step), sources, receivers,
              ko, ki, normal_ratio=ratio).scattered_receiver for sign in (1, -1)]
    assert relative_error(analytic, (values[0] - values[1]) / (2 * step)) < 1e-6


def test_te_ellipse_ten_random_harmonic_directions():
    curve = ellipse((0, 0), 1, .75).discretize(128)
    sources, receivers = ring(3, 3), ring(4, 20, .09)
    base = solve_polarized_transmission(curve, sources, receivers, 3, 6, normal_ratio=4)
    theta = curve.parameters
    basis = np.column_stack([np.ones(len(theta))] + [f(n * theta) for n in range(1, 6) for f in (np.sin, np.cos)])
    directions = basis @ np.random.default_rng(471).normal(size=(basis.shape[1], 10))
    directions /= np.max(abs(directions), axis=0)
    analytic = polarized_shape_derivative(base, directions)
    step = 2e-5
    for column in range(10):
        values = [solve_polarized_transmission(deform(curve, directions[:, column], sign * step),
            sources, receivers, 3, 6, normal_ratio=4).scattered_receiver for sign in (1, -1)]
        assert relative_error(analytic[column], (values[0] - values[1]) / (2 * step)) < 1e-6


def test_passive_sign_and_zero_contrast():
    omega = 2 * np.pi * 1e8
    permittivity = passive_permittivity(6, .05, omega)
    assert permittivity.real == 6 * EPS0
    assert permittivity.imag > 0
    wave = passive_wavenumber(6, .05, omega)
    assert wave.real > 0 and wave.imag > 0
    radii = np.array([2., 4., 6.])
    assert np.all(np.diff(abs(hankel1(0, wave * radii)) * np.sqrt(radii)) < 0)
    curve = circle((0, 0), .2).discretize(64)
    result = solve_polarized_transmission(curve, ring(.6, 2), ring(.8, 10, .1), wave, wave)
    assert np.max(abs(result.scattered_receiver)) < 1e-13
    assert np.max(abs(polarized_shape_derivative(result, np.ones(64)))) == 0
