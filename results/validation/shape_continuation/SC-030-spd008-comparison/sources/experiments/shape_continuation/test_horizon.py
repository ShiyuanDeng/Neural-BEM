"""The horizon must measure geometry, not the gauge or the discretization."""
import numpy as np
import pytest

from .atlas import cell_at, orthonormal_normal_basis, to_solver_coefficients
from .forward import Acquisition, solve, shape_jacobian
from .geometry import FourierCurve, displaced, grid_size, normal_basis
from .horizon import (HorizonProbe, gauss_newton_direction, linearization_error,
                      perturbed, step_quality, unit_direction)
from .inverse import Observation
from .run import fixture


def observation_at(wavenumber, contrast, count, nodes, scene="glider"):
    acquisition = Acquisition.ring(count, count)
    field = solve(fixture(scene), wavenumber, contrast, acquisition, nodes).prediction
    return Observation(wavenumber, acquisition, field)


def test_solver_coefficient_conversion_round_trips_through_the_basis():
    nodes = fixture("glider").nodes(512)
    band = 5
    atlas = np.random.default_rng(0).normal(size=2 * band + 1)
    raw = to_solver_coefficients(atlas, nodes.perimeter)
    assert np.allclose(orthonormal_normal_basis(nodes, band) @ atlas,
                       normal_basis(nodes, band) @ raw, atol=1e-12)


def test_perturbed_keeps_the_gauge_and_reports_its_representation_error():
    shape = fixture("ellipse")
    moved = perturbed(shape, unit_direction(4, 3) * 0.05, 40)
    assert moved.representation_error < 1e-3 * moved.rms_displacement
    assert 0 < moved.rms_displacement <= moved.maximum_displacement
    # The gauge is untouched, so a zero displacement returns the same curve.
    identical = perturbed(shape, np.zeros(9), 40)
    assert np.allclose(identical.shape.values(256), shape.values(256), atol=1e-10)


def test_perturbed_rms_matches_the_requested_amplitude():
    shape = fixture("glider")
    perimeter = shape.nodes(grid_size(shape.band)).perimeter
    for column in (0, 1, 6):
        amplitude = 0.01
        moved = perturbed(shape, unit_direction(6, column) * amplitude * np.sqrt(perimeter),
                          3 * shape.band + 60)
        assert np.isclose(moved.rms_displacement, amplitude, rtol=2e-3)


def test_perturbed_refuses_an_unresolved_storage_band():
    with pytest.raises(ValueError):
        perturbed(fixture("glider"), unit_direction(30, 59) * 0.05, 34)


def test_representation_error_is_relative_and_amplitude_independent():
    """A fixed band gives a fixed relative error; this is why the check is relative."""
    shape, ratios = fixture("glider"), []
    for amplitude in (1e-4, 1e-2):
        moved = perturbed(shape, unit_direction(6, 6) * amplitude * np.sqrt(
            shape.nodes(grid_size(shape.band)).perimeter), 110)
        ratios.append(moved.representation_error / moved.rms_displacement)
    assert np.isclose(ratios[0], ratios[1], rtol=1e-3)


def test_linearization_error_is_first_order_and_ordered():
    shape, band = FourierCurve.circle(1.0), 4
    amplitudes = np.geomspace(1e-4, 1e-2, 5)
    probes, state, jacobian = linearization_error(
        shape, 3.0, 1.44, Acquisition.ring(24, 24), 192, band,
        {"harmonic_2": unit_direction(band, 3)}, amplitudes)
    probe = probes[0]
    assert np.all(np.isfinite(probe.relative_error))
    assert np.all(np.diff(probe.relative_error) > 0)
    assert 0.85 < probe.order() < 1.15
    assert probe.relative_error[0] < 1e-2


def test_horizon_interpolates_and_reports_its_ladder_limits():
    amplitudes = np.geomspace(1e-3, 1e-1, 5)
    errors = np.array([0.001, 0.01, 0.1, 0.4, 0.9])
    probe = HorizonProbe(1.0, "x", amplitudes, amplitudes, errors,
                         np.ones(5), np.ones(5), np.zeros(5))
    assert np.isclose(probe.horizon(0.1), 1e-2, rtol=1e-6)
    assert np.isclose(probe.horizon(0.03), 10 ** (-2.5 + np.log10(3) / 2), rtol=1e-6)
    assert probe.horizon(2.0) == float("inf")
    assert HorizonProbe(1.0, "x", amplitudes, amplitudes, np.full(5, 0.5),
                        np.ones(5), np.ones(5), np.zeros(5)).horizon(0.1) == 0.0


def test_horizon_is_insensitive_to_the_quadrature_it_is_measured_with():
    """A geometric horizon must not move when the solver is refined."""
    shape, band = fixture("ellipse"), 4
    amplitudes = np.geomspace(1e-3, 3e-2, 6)
    directions = {"harmonic_2": unit_direction(band, 3)}
    horizons = []
    for nodes in (160, 320):
        probes, _, _ = linearization_error(shape, 3.0, 1.44, Acquisition.ring(24, 24),
                                           nodes, band, directions, amplitudes)
        horizons.append(probes[0].horizon(0.1))
    assert np.isclose(horizons[0], horizons[1], rtol=5e-3)


def test_step_quality_model_matches_the_measurement_for_tiny_steps():
    shape, contrast, band, nodes = FourierCurve.circle(1.0), 1.44, 5, 192
    observation = observation_at(2.0, contrast, 20, 384)
    cell = cell_at(shape, observation, contrast, band, nodes)
    direction = gauss_newton_direction(cell)
    quality = step_quality(shape, observation, contrast, nodes, band, cell,
                           direction, [1e-4, 3e-4, 1e-3])
    assert np.all(np.isfinite(quality.actual_decrease))
    assert np.allclose(quality.ratio, 1.0, atol=0.02)
    assert quality.useful_fraction(0.5) == 1.0


def test_gauss_newton_direction_respects_a_band_restriction():
    shape, contrast, band, nodes = FourierCurve.circle(1.0), 1.44, 8, 192
    observation = observation_at(2.0, contrast, 20, 384)
    cell = cell_at(shape, observation, contrast, band, nodes)
    restricted = gauss_newton_direction(cell, band_limit=3)
    assert np.allclose(restricted[7:], 0.0)
    assert not np.allclose(restricted[:7], 0.0)
    assert float(cell.gradient @ restricted) < 0  # a descent direction
