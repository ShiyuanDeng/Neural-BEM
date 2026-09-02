"""Continuous producers and solver-facing node-based curve contract tests."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import ellipe

from nystrom_ref import (
    build_curve as build_oracle_curve,
    circle_parameterization,
    ellipse_parameterization,
    star_parameterization,
)
from ordered_boundary import (
    PeriodicCurve2D,
    PeriodicParameterization2D,
    circle,
    ellipse,
    fourier_curve,
    star,
    validate_periodic_parameterization,
)


@pytest.mark.parametrize("num_nodes", [63, 64])
def test_circle_discretization_stores_all_solver_geometry_at_nodes(num_nodes: int) -> None:
    center = np.asarray((0.3, -0.2))
    radius = 1.7
    parameterization = circle(tuple(center), radius, component_id="target")
    curve = parameterization.discretize(num_nodes)
    expected_t = 2.0 * np.pi * np.arange(num_nodes) / num_nodes
    radial = np.column_stack((np.cos(expected_t), np.sin(expected_t)))
    tangent = np.column_stack((-np.sin(expected_t), np.cos(expected_t)))

    assert isinstance(parameterization, PeriodicParameterization2D)
    assert isinstance(curve, PeriodicCurve2D)
    assert not hasattr(curve, "evaluator")
    assert not hasattr(curve, "evaluate")
    np.testing.assert_allclose(curve.parameters, expected_t, rtol=0.0, atol=2.0e-15)
    np.testing.assert_allclose(curve.points, center + radius * radial, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.first_derivatives, radius * tangent, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.second_derivatives, -radius * radial, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.third_derivatives, -radius * tangent, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.speeds, radius, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.tangents, tangent, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.normals, radial, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.curvatures, 1.0 / radius, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(
        curve.arc_length_weights,
        2.0 * np.pi * radius / num_nodes,
        rtol=2.0e-14,
        atol=2.0e-14,
    )
    assert curve.parameters[-1] < 2.0 * np.pi
    assert curve.perimeter == pytest.approx(2.0 * np.pi * radius, rel=2.0e-14)
    assert curve.signed_area == pytest.approx(np.pi * radius**2, rel=2.0e-14)
    assert curve.orientation == "counterclockwise"
    assert curve.maximum_derivative_order == 3


def test_arbitrary_parameter_shapes_wrap_periodically() -> None:
    parameterization = ellipse((0.1, -0.4), 2.0, 0.7, rotation=0.3, component_id="ellipse")
    parameters = np.asarray([[-0.2, 0.17], [2.0 * np.pi + 0.4, 9.1]])
    wrapped = parameterization.evaluate(parameters)
    repeated = parameterization.evaluate(parameters + 4.0 * np.pi)
    assert wrapped.points.shape == parameters.shape + (2,)
    np.testing.assert_allclose(wrapped.points, repeated.points, rtol=3.0e-14, atol=3.0e-14)
    np.testing.assert_allclose(
        wrapped.first_derivatives,
        repeated.first_derivatives,
        rtol=3.0e-14,
        atol=3.0e-14,
    )
    scalar = parameterization.evaluate(0.3)
    assert scalar.points.shape == (2,)
    with pytest.raises(ValueError, match="real-valued"):
        parameterization.evaluate(np.asarray([1.0 + 1.0j]))


def test_ellipse_speed_curvature_and_nonconstant_weights() -> None:
    semi_major = 1.9
    semi_minor = 0.65
    curve = ellipse((0.0, 0.0), semi_major, semi_minor, component_id="e").discretize(256)
    t = curve.parameters
    expected_speed = np.sqrt((semi_major * np.sin(t)) ** 2 + (semi_minor * np.cos(t)) ** 2)
    expected_curvature = semi_major * semi_minor / expected_speed**3
    expected_perimeter = 4.0 * semi_major * ellipe(1.0 - (semi_minor / semi_major) ** 2)
    np.testing.assert_allclose(curve.speeds, expected_speed, rtol=3.0e-14, atol=3.0e-14)
    np.testing.assert_allclose(curve.curvatures, expected_curvature, rtol=5.0e-14, atol=5.0e-14)
    assert np.ptp(curve.arc_length_weights) > 0.5 * np.mean(curve.arc_length_weights)
    assert curve.perimeter == pytest.approx(expected_perimeter, rel=3.0e-14)


def _fft_derivative(values: np.ndarray, order: int) -> np.ndarray:
    count = values.shape[0]
    modes = np.fft.fftfreq(count, d=1.0 / count)
    transformed = np.fft.fft(values, axis=0)
    return np.fft.ifft((1j * modes[:, None]) ** order * transformed, axis=0).real


def test_star_derivatives_are_independently_spectral_and_rotation_is_rigid() -> None:
    unrotated = star((0.0, 0.0), 1.2, 0.22, 5, component_id="s")
    curve = unrotated.discretize(256)
    np.testing.assert_allclose(
        curve.first_derivatives,
        _fft_derivative(curve.points, 1),
        rtol=2.0e-11,
        atol=2.0e-11,
    )
    np.testing.assert_allclose(
        curve.second_derivatives,
        _fft_derivative(curve.points, 2),
        rtol=3.0e-10,
        atol=3.0e-10,
    )
    np.testing.assert_allclose(
        curve.third_derivatives,
        _fft_derivative(curve.points, 3),
        rtol=2.0e-9,
        atol=2.0e-9,
    )

    angle = 0.37
    rotation = np.asarray(((np.cos(angle), -np.sin(angle)), (np.sin(angle), np.cos(angle))))
    rotated = star((0.0, 0.0), 1.2, 0.22, 5, rotation=angle, component_id="r").discretize(256)
    np.testing.assert_allclose(rotated.points, curve.points @ rotation.T, rtol=3.0e-14, atol=3.0e-14)
    np.testing.assert_allclose(rotated.normals, curve.normals @ rotation.T, rtol=3.0e-14, atol=3.0e-14)


def test_nonuniform_parameter_speed_does_not_change_geometric_invariants() -> None:
    radius = 1.3
    amplitude = 0.2

    def evaluator(t: np.ndarray):
        q = t + amplitude * np.sin(t)
        q1 = 1.0 + amplitude * np.cos(t)
        q2 = -amplitude * np.sin(t)
        q3 = -amplitude * np.cos(t)
        radial = np.stack((np.cos(q), np.sin(q)), axis=-1)
        angular = np.stack((-np.sin(q), np.cos(q)), axis=-1)
        points = radius * radial
        first = radius * q1[..., None] * angular
        second = radius * (q2[..., None] * angular - q1[..., None] ** 2 * radial)
        third = radius * (
            (q3 - q1**3)[..., None] * angular - (3.0 * q1 * q2)[..., None] * radial
        )
        return points, first, second, third

    parameterization = PeriodicParameterization2D(
        "warped_circle", evaluator, name="warped_circle"
    )
    curve = parameterization.discretize(256)
    assert np.ptp(curve.arc_length_weights) > 0.25 * np.mean(curve.arc_length_weights)
    np.testing.assert_allclose(curve.curvatures, 1.0 / radius, rtol=8.0e-14, atol=8.0e-14)
    assert curve.perimeter == pytest.approx(2.0 * np.pi * radius, rel=3.0e-14)
    assert curve.signed_area == pytest.approx(np.pi * radius**2, rel=3.0e-14)
    assert validate_periodic_parameterization(parameterization).valid


def test_fourier_producer_is_owned_and_matches_ellipse() -> None:
    center = np.asarray((0.2, -0.1))
    cosine = np.zeros((2, 2))
    sine = np.zeros((2, 2))
    cosine[0] = center
    cosine[1, 0] = 1.8
    sine[1, 1] = 0.7
    parameterization = fourier_curve(cosine, sine, component_id="fourier")
    cosine[:] = 99.0
    sine[:] = -99.0
    expected = ellipse(tuple(center), 1.8, 0.7, component_id="analytic")
    actual_curve = parameterization.discretize(65)
    expected_curve = expected.discretize(65)
    for name in ("points", "first_derivatives", "second_derivatives", "third_derivatives"):
        np.testing.assert_allclose(getattr(actual_curve, name), getattr(expected_curve, name), atol=3.0e-14)
    assert parameterization.provenance.source_kind == "fourier"


@pytest.mark.parametrize(
    "our_curve,oracle_parameterization",
    [
        (circle((0.1, -0.2), 0.8, component_id="c"), circle_parameterization((0.1, -0.2), 0.8)),
        (
            ellipse((0.1, -0.2), 1.1, 0.6, component_id="e"),
            ellipse_parameterization((0.1, -0.2), 1.1, 0.6),
        ),
        (
            star((0.1, -0.2), 0.8, 0.2, 5, component_id="s"),
            star_parameterization((0.1, -0.2), 0.8, 0.2, 5),
        ),
    ],
)
def test_geometry_matches_independent_oracle_contract(our_curve, oracle_parameterization) -> None:
    curve = our_curve.discretize(128)
    oracle = build_oracle_curve(oracle_parameterization, 128)
    np.testing.assert_allclose(curve.parameters, oracle.t, rtol=0.0, atol=2.0e-15)
    np.testing.assert_allclose(curve.points, oracle.points, rtol=2.0e-14, atol=2.0e-14)
    np.testing.assert_allclose(curve.tangents, oracle.tangents / oracle.speeds[:, None], atol=2.0e-14)
    np.testing.assert_allclose(curve.normals, oracle.normals, atol=2.0e-14)
    np.testing.assert_allclose(curve.speeds, oracle.speeds, atol=2.0e-14)


def test_discretization_restrictions_are_solver_owned_and_node_arrays_are_immutable() -> None:
    parameterization = circle((0.0, 0.0), 1.0, component_id="odd_ok")
    curve = parameterization.discretize(63)
    assert curve.num_nodes == 63
    with pytest.raises(ValueError, match="odd_ok.*even"):
        parameterization.discretize(63, require_even=True)
    with pytest.raises(TypeError, match="integer"):
        parameterization.discretize(63.5)
    for values in (
        curve.parameters,
        curve.points,
        curve.first_derivatives,
        curve.second_derivatives,
        curve.third_derivatives,
        curve.speeds,
        curve.tangents,
        curve.normals,
        curve.curvatures,
        curve.arc_length_weights,
    ):
        assert values is not None
        assert not values.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        curve.points[0, 0] = 10.0


def test_direct_node_construction_owns_primary_arrays_and_derives_geometry() -> None:
    source = circle((0.2, -0.3), 0.9, component_id="source").discretize(32)
    parameters = source.parameters.copy()
    points = source.points.copy()
    first = source.first_derivatives.copy()
    second = source.second_derivatives.copy()
    third = source.third_derivatives.copy()
    curve = PeriodicCurve2D(
        component_id="owned",
        parameters=parameters,
        points=points,
        first_derivatives=first,
        second_derivatives=second,
        third_derivatives=third,
    )
    points[:] = 99.0
    first[:] = -99.0
    np.testing.assert_allclose(curve.points, source.points)
    np.testing.assert_allclose(curve.first_derivatives, source.first_derivatives)
    np.testing.assert_allclose(curve.normals, source.normals)
    np.testing.assert_allclose(curve.arc_length_weights, source.arc_length_weights)

    nonuniform_parameters = parameters.copy()
    nonuniform_parameters[1] += 1.0e-3
    with pytest.raises(ValueError, match="canonical uniform periodic grid"):
        PeriodicCurve2D(
            component_id="nonuniform",
            parameters=nonuniform_parameters,
            points=source.points,
            first_derivatives=source.first_derivatives,
            second_derivatives=source.second_derivatives,
        )


def test_validation_reports_explicit_orientation_and_bad_derivatives() -> None:
    clockwise = circle((0.0, 0.0), 1.0, component_id="cw").reversed()
    report = validate_periodic_parameterization(clockwise)
    assert not report.valid
    assert report.orientation == "clockwise"
    assert any("not counterclockwise" in issue for issue in report.issues)
    with pytest.raises(ValueError, match="counterclockwise"):
        clockwise.discretize(64)

    def bad_evaluator(t: np.ndarray):
        radial = np.stack((np.cos(t), np.sin(t)), axis=-1)
        wrong = np.zeros_like(radial)
        return radial, wrong + np.asarray((1.0, 0.0)), -radial

    bad = validate_periodic_parameterization(
        PeriodicParameterization2D("bad_derivative", bad_evaluator)
    )
    assert not bad.valid
    assert any("first derivative is inconsistent" in issue for issue in bad.issues)
