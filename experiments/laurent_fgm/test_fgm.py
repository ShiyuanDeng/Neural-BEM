"""Independent physical and algebraic checks for the FFT Galerkin package."""
import numpy as np
import pytest
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1, h1vp, jv, jvp

from experiments.modal_muller_research.coefficient_operator import (
    LaurentGeometry, CoefficientGeometry)
from . import curves as curvelib
from .assembler import (FourierGalerkinMuller, point_source_traces,
                        receiver_operator)
from .decay import band_profile, decay_rate, fjs_band, jwy_mask, truncate
from .multiobject import (LocalResponse, local_solve, mie_response, monolithic,
                          translation)

RING = np.column_stack((.25 * np.cos(np.arange(5) * 2 * np.pi / 5),
                        .25 * np.sin(np.arange(5) * 2 * np.pi / 5)))


def relative(value, reference):
    return np.linalg.norm(value - reference) / np.linalg.norm(reference)


def mie_field(radius, ko, ki, sources, receivers, order=48):
    modes = np.arange(-order, order + 1)
    jo, ji = jv(modes, ko * radius), jv(modes, ki * radius)
    djo, dji = ko * jvp(modes, ko * radius), ki * jvp(modes, ki * radius)
    ho, dho = hankel1(modes, ko * radius), ko * h1vp(modes, ko * radius)
    ratio = (dji * jo - ji * djo) / (ji * dho - dji * ho)
    s = sources[:, 0] + 1j * sources[:, 1]
    r = receivers[:, 0] + 1j * receivers[:, 1]
    incident = .25j * hankel1(modes[:, None], ko * np.abs(s)[None, :]) * np.exp(
        -1j * modes[:, None] * np.angle(s)[None, :])
    outgoing = hankel1(modes[None, :], ko * np.abs(r)[:, None]) * np.exp(
        1j * modes[None, :] * np.angle(r)[:, None])
    return (outgoing * ratio) @ incident


def test_fft_assembly_matches_the_coefficient_recurrence():
    """Two independent routes to the same Galerkin operator must agree."""
    prepared = CoefficientGeometry(LaurentGeometry.ellipse(0j, .045, .026, .55), 96)
    fgm = FourierGalerkinMuller({1: np.exp(.55j) * .0355, -1: np.exp(.55j) * .0095},
                                grid=512)
    native, _ = prepared.assemble(64., 45.25, 24, terms=40)
    fourier, _ = fgm.assemble(64., 45.25, 24)
    assert relative(fourier, native) < 1e-12


@pytest.mark.parametrize('kd', [2., 30.])
def test_circle_field_matches_analytic_mie_without_a_power_series(kd):
    """The closed-form amplitudes carry to electrical sizes the series cannot."""
    radius = .05
    ko = kd / (2 * radius)
    ki = ko / np.sqrt(2.)
    cutoff = int(max(24, 1.6 * ko * radius + 20))
    grid = 1 << int(np.ceil(np.log2(8 * cutoff)))
    receivers = RING + np.array([.015, -.01])
    matrix, _ = FourierGalerkinMuller({1: radius}, grid=grid).assemble(ko, ki, cutoff)
    rhs = point_source_traces({1: radius}, RING, ko, cutoff, grid=grid)
    obs = receiver_operator({1: radius}, receivers, ko, cutoff, grid=grid)
    y = obs @ lu_solve(lu_factor(matrix), rhs)
    assert relative(y, mie_field(radius, ko, ki, RING, receivers)) < 1e-12


def test_analyticity_halfwidth_reproduces_the_closed_form_for_an_ellipse():
    for major, minor in [(.65, .35), (.8, .2), (.9, .1)]:
        numeric = curvelib.analyticity_halfwidth({1: major, -1: minor})
        assert abs(numeric - .5 * np.log(major / minor)) < 1e-9


def test_the_library_is_simple_and_the_crescent_is_not_star_shaped():
    library = curvelib.library()
    for name, coefficients in library.items():
        assert curvelib.is_simple(coefficients), name
        assert abs(curvelib.diameter(coefficients) - 1.) < 1e-9, name
    assert curvelib.star_shaped_defect(library['crescent']) < 0
    assert curvelib.star_shaped_defect(library['ellipse']) > 0


def test_b_star_orders_the_measured_decay_rates():
    """FJS give b* as a lower bound on the rate; check it holds and orders."""
    rates, stars = {}, {}
    for name in ('ellipse', 'kite', 'crescent'):
        coefficients = curvelib.library()[name]
        ko = 10. / curvelib.diameter(coefficients)
        matrix, _ = FourierGalerkinMuller(coefficients, grid=512).assemble(
            ko, ko / np.sqrt(2.), 36)
        block = matrix[:73, 73:]
        profile = band_profile(block)
        rates[name] = decay_rate(profile['offset'], profile['peak'])['rate']
        stars[name] = curvelib.analyticity_halfwidth(coefficients)
    for name in rates:
        assert rates[name] > stars[name], name
    assert rates['ellipse'] > rates['kite'] > rates['crescent']
    assert stars['ellipse'] > stars['kite'] > stars['crescent']


def test_masks_are_nested_and_truncation_accounting_is_consistent():
    narrow, wide = fjs_band(8, 3), fjs_band(8, 6)
    assert np.all(wide[narrow])
    assert fjs_band(8, 0).sum() == 4 * 17
    matrix = np.arange((2 * 17)**2, dtype=float).reshape(34, 34) + 1.
    kept, stats = truncate(matrix, fjs_band(8, 4))
    assert stats['nonzeros'] == int(fjs_band(8, 4).sum())
    assert np.allclose(kept + (matrix - kept), matrix)
    assert 0 < stats['retained'] < 1
    assert jwy_mask(8, 1.2).shape == (34, 34)


def test_local_response_of_a_circle_is_the_analytic_mie_diagonal():
    response = LocalResponse({1: .5, 0: 0j}, 6., 6. / np.sqrt(2.), 32, 10, 256)
    exact = mie_response(.5, 6., 6. / np.sqrt(2.), 10)
    assert relative(response.s, exact) < 1e-12
    off = response.s - np.diag(np.diag(response.s))
    assert np.abs(off).max() < 1e-13 * np.abs(response.s).max()


def test_graf_translation_reexpands_an_outgoing_field():
    order, wave = 24, 3.
    target, source = 2.5 + .4j, 0j
    generator = np.random.default_rng(0)
    modes = np.arange(-order, order + 1)
    b = (generator.normal(size=modes.size) + 1j * generator.normal(size=modes.size))
    b *= np.exp(-.25 * np.abs(modes))
    a = translation(target, source, wave, order) @ b
    angle = np.linspace(0, 2 * np.pi, 17)[:-1]
    x = target + .35 * np.exp(1j * angle)
    direct = (hankel1(modes[None, :], wave * np.abs(x - source)[:, None])
              * np.exp(1j * modes[None, :] * np.angle(x - source)[:, None])) @ b
    reexpanded = (jv(modes[None, :], wave * np.abs(x - target)[:, None])
                  * np.exp(1j * modes[None, :] * np.angle(x - target)[:, None])) @ a
    assert relative(reexpanded, direct) < 1e-9


def test_local_coupling_matches_the_monolithic_muller_solve():
    ko, ki, cutoff, grid = 6., 6. / np.sqrt(2.), 32, 256
    objects = [{1: .5, 0: 0j}, {1: .4, 0: 3. + 0j}]
    angle = 2 * np.pi * np.arange(8) / 8
    sources = np.column_stack((6 * np.cos(angle), 6 * np.sin(angle)))
    receivers = np.column_stack((6 * np.cos(angle + .3), 6 * np.sin(angle + .3)))
    matrix, _ = monolithic(objects, ko, ki, cutoff, grid)
    rhs = np.concatenate([point_source_traces(o, sources, ko, cutoff, grid=grid)
                          for o in objects], axis=0)
    obs = np.concatenate([receiver_operator(o, receivers, ko, cutoff, grid=grid)
                          for o in objects], axis=1)
    reference = obs @ lu_solve(lu_factor(matrix), rhs)
    responses = [LocalResponse(o, ko, ki, cutoff, 16, grid) for o in objects]
    field, _ = local_solve(responses, ko, sources, receivers)
    assert relative(field, reference) < 1e-12


def test_snapshot_basis_reconstructs_its_snapshots_and_interpolates_its_nodes():
    """The affine identity must be exact where it is fitted, before it is trusted
    anywhere else: A(k_j) = sum_r theta_r(k_j) A_r at full rank, and a spline
    through the coefficients must return them at the training frequencies."""
    from .run_affine import interpolate, snapshot_basis
    coefficients = curvelib.library()['ellipse']
    waves = np.linspace(4., 10., 9)
    matrices = [FourierGalerkinMuller(coefficients, grid=256).assemble(
        kd / curvelib.diameter(coefficients),
        kd / curvelib.diameter(coefficients) / np.sqrt(2.), 24)[0]
        for kd in waves]
    basis, theta, values = snapshot_basis(matrices)
    assert values[0] == 1. and np.all(np.diff(values) <= 0)
    for column, matrix in enumerate(matrices):
        assert relative((basis @ theta[:, column]).reshape(matrix.shape), matrix) < 1e-13
    assert relative(interpolate(waves, theta, waves), theta) < 1e-12
