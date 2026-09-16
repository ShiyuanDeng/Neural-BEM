"""Independent analytic and concave-branch checks for smooth distance targets."""

import numpy as np
import pytest

from ordered_boundary import circle, star
from sdf_inverse.continuous_distance import signed_distance_to_continuous_curve
from sdf_inverse.neural import signed_distance_to_curve_polygon
from sdf_inverse.targets import StarShape


def test_circle_distance_sign_and_chord_error_are_resolved_independently():
    radius, count = 0.065, 32
    continuous = circle((0.02, -0.01), radius)
    parameters = (np.arange(count) + 0.5) * 2.0 * np.pi / count
    boundary = continuous.evaluate(parameters).points
    query = np.vstack((boundary, (0.02, -0.01), (0.2, 0.0)))
    observed, diagnostics = signed_distance_to_continuous_curve(
        query, continuous, tolerance_m=1e-10, return_diagnostics=True,
    )
    expected = np.linalg.norm(query - (0.02, -0.01), axis=1) - radius
    np.testing.assert_allclose(observed, expected, atol=2e-11, rtol=0)
    polygon = signed_distance_to_curve_polygon(boundary, continuous.discretize(count))
    np.testing.assert_allclose(polygon, radius * (1 - np.cos(np.pi / count)), atol=1e-15)
    assert diagnostics["distance_refinement_agreement_m"] < 1e-10
    assert not observed.flags.writeable


def test_concave_star_checks_competing_minima_and_independent_radial_sign():
    target = StarShape((0.01, -0.02), 0.065, 0.35, 5, 0.19)
    continuous = star(target.center, target.mean_radius, target.amplitude, 5, rotation=0.19)
    queries = np.random.default_rng(17).uniform(-0.10, 0.10, size=(160, 2))
    queries = np.vstack((queries, target.center))
    observed, diagnostics = signed_distance_to_continuous_curve(
        queries, continuous, initial_samples=128, tolerance_m=1e-10,
        return_diagnostics=True,
    )
    expected_distance = target.distance_to_boundary(queries, coarse_samples=4096)
    delta = queries - target.center
    angle = np.arctan2(delta[:, 1], delta[:, 0])
    inside = np.linalg.norm(delta, axis=1) < target.radius(angle)
    np.testing.assert_allclose(np.abs(observed), expected_distance, atol=2e-10, rtol=0)
    np.testing.assert_array_equal(observed < 0, inside)
    assert diagnostics["distance_maximum_local_candidates"] >= 5
    tighter = signed_distance_to_continuous_curve(
        queries, continuous, initial_samples=1024, maximum_samples=4096,
        tolerance_m=1e-12, refinement_iterations=56,
    )
    np.testing.assert_allclose(observed, tighter, atol=2e-10, rtol=0)


def test_distance_rejects_nonconverged_refinement_and_invalid_inputs():
    curve = star((0, 0), 0.065, 0.3, 5)
    queries = np.random.default_rng(91).uniform(-0.1, 0.1, (12, 2))
    with pytest.raises(ValueError, match="did not reach numerical refinement"):
        signed_distance_to_continuous_curve(
            queries, curve, tolerance_m=1e-16, initial_samples=32,
            maximum_samples=64, refinement_iterations=8,
        )
    with pytest.raises(ValueError, match="real-valued"):
        signed_distance_to_continuous_curve(queries.astype(complex), curve)
    with pytest.raises(TypeError, match="PeriodicParameterization2D"):
        signed_distance_to_continuous_curve(queries, curve.discretize(32))
