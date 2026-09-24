"""Bridge qualification against the existing physical point-source pipeline."""
from dataclasses import replace

import numpy as np
import pytest

from .forward import PointSourceAcquisition, Work, solve, shape_jacobian
from .geometry import FourierCurve, displaced, normal_basis
from .inverse import Observation, prepare_state
from .policy import AtlasPolicy
from .schedule import Stage


def legacy_problem():
    from run_sdf_inverse_comparison import _build_problem, _ring_scan
    sources, receivers = _ring_scan(center=(0.5, 0.5), standoff=0.3, num_pairs=12)
    return _build_problem((0.5,), sources, receivers)


def converted(problem, length=0.05):
    center = np.array([0.5, 0.5])
    wave = problem.angular_frequencies[0] * np.sqrt(problem.eps0 * problem.mu0 * problem.exterior.epsr)
    acquisition = PointSourceAcquisition((problem.source_points-center)/length,
        (problem.receiver_points-center)/length, problem.source_strengths[0])
    return wave * length, problem.interior.epsr/problem.exterior.epsr, acquisition


@pytest.mark.parametrize("target_name", ["circle", "star"])
def test_physical_units_and_paired_prediction_match_independent_old_oracles(target_name):
    from run_sdf_inverse_comparison import _build_target
    problem = legacy_problem()
    target = _build_target(target_name)
    points = target.exact_boundary_polyline(2048)
    shape = FourierCurve.from_samples(((points[:, 0]-.5)+1j*(points[:, 1]-.5))/.05, 6)
    wave, contrast, acquisition = converted(problem)
    actual = solve(shape, wave, contrast, acquisition, 256).prediction
    expected = target.observations(problem)[:, 0]
    assert actual.shape == (12,)
    assert np.linalg.norm(actual-expected)/np.linalg.norm(expected) < 1e-7


def test_paired_jacobian_matches_finite_difference_with_complex_strength():
    wave, contrast, acquisition = converted(legacy_problem())
    acquisition = replace(acquisition, strength=0.7+0.3j)
    shape = FourierCurve.circle(1.1, 0.1j)
    state = solve(shape, wave, contrast, acquisition, 128)
    direction = np.array([.1, .2, -.15, .03, .1])
    basis = normal_basis(state.curve, 2)
    predicted = shape_jacobian(state, basis) @ direction
    step = 1e-5
    plus = displaced(shape, step*direction, 32).shape
    minus = displaced(shape, -step*direction, 32).shape
    fd = (solve(plus, wave, contrast, acquisition, 128).prediction
          - solve(minus, wave, contrast, acquisition, 128).prediction)/(2*step)
    assert np.linalg.norm(fd-predicted)/np.linalg.norm(fd) < 1e-5
    full = replace(acquisition, paired=False)
    full_state = solve(shape, wave, contrast, full, 128)
    assert np.allclose(state.prediction, np.diag(full_state.prediction))
    indices = np.arange(12)
    assert np.allclose(shape_jacobian(state, basis),
                       shape_jacobian(full_state, basis)[indices, indices])


def test_cache_invalidates_on_point_source_strength_and_position():
    wave, contrast, acquisition = converted(legacy_problem())
    shape = FourierCurve.circle()
    stage = Stage(wave, 3, 16, 128, 20)
    data = solve(shape, wave, contrast, acquisition, 128).prediction
    obs = Observation(wave, acquisition, data)
    work = Work()
    first = prepare_state(shape, obs, stage, contrast, work=work)
    prepare_state(first.shape, obs, stage, contrast, cached=first, work=work)
    assert work.attempted == 1
    for changed in (replace(acquisition, strength=2*acquisition.strength),
                    replace(acquisition, sources=acquisition.sources+0.01)):
        prepare_state(first.shape, Observation(wave, changed, data), stage, contrast,
                      cached=first, work=work)
    assert work.attempted == 3


def test_sparse_measured_frequencies_are_not_mistaken_for_completion():
    wave, contrast, acquisition = converted(legacy_problem())
    data = np.ones(12, complex)
    observations = tuple(Observation(k, acquisition, data) for k in (wave, 3*wave, 5*wave))
    policy = AtlasPolicy(observations, contrast, Work(), mode="fixed")
    context = type("Context", (), {"history": ()})()
    assert np.allclose(policy.candidates(wave, context), [3*wave])
    assert np.allclose(policy.candidates(3*wave, context), [5*wave])


def test_legacy_cartesian_conversion_preserves_physical_curve():
    from sdf_inverse.explicit_fourier import CartesianFourierCurveState
    from .legacy_cases import from_cartesian, physical, dimensionless
    rng = np.random.default_rng(82)
    cosine, sine = rng.normal(size=(2, 7, 2))
    sine[0] = 0
    state = CartesianFourierCurveState(cosine, sine, "conversion-test")
    shape = from_cartesian(state)
    angles = np.arange(256)*2*np.pi/256
    expected = np.cos(angles[:, None]*np.arange(7))@cosine + np.sin(angles[:, None]*np.arange(7))@sine
    assert np.allclose(shape.values(256), expected[:, 0]+1j*expected[:, 1])
    assert np.allclose(physical(dimensionless(shape)).coefficients, shape.coefficients)


def test_terminal_refinement_requires_measured_progress_not_just_an_accepted_step():
    from .legacy_cases import LegacyCatalogPolicy
    from types import SimpleNamespace as NS
    def context(before, after, stop):
        return NS(history=(NS(committed=True, result=NS(stop_reason=stop,
            history=[dict(relative_residual=before),
                     dict(relative_residual=after, direction="gauss_newton")])),))
    assert LegacyCatalogPolicy.progressed(context(.5, .4, "iteration_limit"))
    assert not LegacyCatalogPolicy.progressed(context(.5, .4999999, "iteration_limit"))
    assert not LegacyCatalogPolicy.progressed(context(.5, .4, "small_step"))
