"""Geometry-only checks for coefficient-owning Method A/B boundary fits."""

from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np
import pytest

from ordered_boundary import (
    BoundaryValidationConfig,
    OrderedBoundaryValidationError,
    PeriodicParameterization2D,
    circle,
    ellipse,
)
from sdf_to_ordered_boundary.frontend import polygon_self_intersection_count
from sdf_to_ordered_boundary import (
    ArcLengthConfig,
    FourierBoundary,
    MethodAConfig,
    MethodBConfig,
    PeriodicSplineBoundary,
    fit_fourier_least_squares,
    fit_method_a_from_samples,
    fit_method_b,
    fit_method_b_from_samples,
)


def _uniform_parameters(count: int) -> np.ndarray:
    return 2.0 * np.pi * np.arange(count, dtype=np.float64) / count


def _small_arclength_config(*, refit_samples: int | None = None) -> ArcLengthConfig:
    return ArcLengthConfig(
        dense_resolution=1024,
        refit_sample_count=refit_samples,
        validation_resolution=512,
    )


def test_periodic_spline_owns_power_basis_and_has_c2_seam() -> None:
    count = 64
    parameters = _uniform_parameters(count)
    points = ellipse((0.2, -0.1), 1.3, 0.7, component_id="reference").evaluate(
        parameters,
        wrap=False,
    ).points.copy()
    original_points = points.copy()
    boundary = PeriodicSplineBoundary.interpolate(
        parameters,
        points,
        component_id="spline",
    )
    points[:] = 99.0
    parameters[:] = -99.0

    assert boundary.coefficients.shape == (4, count, 2)
    assert boundary.knots.shape == (count + 1,)
    assert not boundary.coefficients.flags.writeable
    assert not boundary.knots.flags.writeable
    curve = boundary.to_parameterization()
    assert isinstance(curve, PeriodicParameterization2D)
    recovered = curve.evaluate(_uniform_parameters(count), wrap=False)
    np.testing.assert_allclose(recovered.points, original_points, rtol=0.0, atol=3.0e-14)
    assert recovered.third_derivatives is None

    seam = curve.evaluate(np.asarray([0.0, 2.0 * np.pi]), wrap=False)
    np.testing.assert_allclose(seam.points[0], seam.points[1], rtol=0.0, atol=2.0e-13)
    np.testing.assert_allclose(
        seam.first_derivatives[0],
        seam.first_derivatives[1],
        rtol=0.0,
        atol=2.0e-12,
    )
    np.testing.assert_allclose(
        seam.second_derivatives[0],
        seam.second_derivatives[1],
        rtol=0.0,
        atol=2.0e-11,
    )


def test_fourier_least_squares_recovers_finite_known_curve_and_coefficients() -> None:
    cosine = np.zeros((5, 2), dtype=np.float64)
    sine = np.zeros_like(cosine)
    cosine[0] = (0.2, -0.15)
    cosine[1, 0] = 1.1
    sine[1, 1] = 0.75
    cosine[3] = (0.035, -0.02)
    sine[4] = (-0.015, 0.025)
    reference = FourierBoundary(cosine, sine, component_id="reference")
    parameters = _uniform_parameters(97)
    points = reference.evaluate(parameters, wrap=False).points

    fit = fit_fourier_least_squares(
        parameters,
        points,
        bandwidth=4,
        component_id="fitted",
    )
    assert fit.diagnostics.rank == 9
    assert fit.diagnostics.num_unknowns == 9
    assert fit.residual.maximum < 3.0e-14
    np.testing.assert_allclose(
        fit.boundary.cosine_coefficients,
        cosine,
        rtol=0.0,
        atol=2.0e-15,
    )
    np.testing.assert_allclose(
        fit.boundary.sine_coefficients,
        sine,
        rtol=0.0,
        atol=2.0e-15,
    )

    updated_cosine = fit.boundary.cosine_coefficients.copy()
    updated_sine = fit.boundary.sine_coefficients.copy()
    updated_cosine[0, 0] += 0.1
    rebuilt = fit.boundary.with_coefficients(updated_cosine, updated_sine)
    assert isinstance(rebuilt.to_parameterization(), PeriodicParameterization2D)
    assert rebuilt.position(0.0)[0] == pytest.approx(fit.boundary.position(0.0)[0] + 0.1)


def test_method_a_arc_length_refit_reduces_ellipse_speed_crowding() -> None:
    count = 96
    parameters = _uniform_parameters(count)
    reference = ellipse((0.0, 0.0), 1.3, 0.7, component_id="reference")
    points = reference.evaluate(parameters, wrap=False).points
    result = fit_method_a_from_samples(
        parameters,
        points,
        config=MethodAConfig(arclength=_small_arclength_config(refit_samples=count)),
        component_id="ellipse-fit",
    )

    assert result.succeeded
    assert isinstance(result.representation, PeriodicSplineBoundary)
    assert result.validation is not None and result.validation.valid
    assert result.input_fit_residual is not None
    assert result.input_fit_residual.maximum < 5.0e-14
    assert result.arc_length is not None
    assert result.arc_length.speed_ratio_before > 1.8
    assert result.arc_length.speed_ratio_after < 1.002
    assert result.arc_length.maximum_refit_displacement < 1.0e-5
    assert result.parameterization is not None
    assert result.parameterization.discretize(64, require_even=True).num_nodes == 64


@dataclass(frozen=True)
class _ProjectedLoop:
    parameters: np.ndarray
    projected_points: np.ndarray


def test_method_b_frontend_adapter_recovers_circle_at_bandwidth_one() -> None:
    center = np.asarray((0.3, -0.2))
    radius = 0.8
    count = 80
    parameters = _uniform_parameters(count)
    points = circle(tuple(center), radius, component_id="reference").evaluate(
        parameters,
        wrap=False,
    ).points
    result = fit_method_b(
        _ProjectedLoop(parameters, points),
        config=MethodBConfig(
            bandwidth=1,
            arclength=_small_arclength_config(refit_samples=count),
        ),
        component_id="circle-fit",
    )

    assert result.succeeded
    assert isinstance(result.representation, FourierBoundary)
    assert result.representation.bandwidth == 1
    assert result.input_fit_residual is not None
    assert result.input_fit_residual.maximum < 3.0e-14
    assert result.arc_length is not None
    assert result.arc_length.maximum_refit_displacement < 3.0e-14
    assert result.arc_length.speed_ratio_after == pytest.approx(1.0, abs=3.0e-13)
    np.testing.assert_allclose(
        result.representation.cosine_coefficients[0],
        center,
        rtol=0.0,
        atol=2.0e-14,
    )
    dense = _uniform_parameters(257)
    expected = circle(tuple(center), radius, component_id="expected").evaluate(
        dense,
        wrap=False,
    ).points
    np.testing.assert_allclose(
        result.parameterization.evaluate(dense, wrap=False).points,
        expected,
        rtol=0.0,
        atol=5.0e-14,
    )
    json.dumps(result.to_summary_dict(), allow_nan=False, sort_keys=True)


def test_method_b_rejects_refit_resolution_below_fourier_degree_count() -> None:
    parameters = _uniform_parameters(40)
    points = circle((0.0, 0.0), 1.0, component_id="reference").evaluate(
        parameters,
        wrap=False,
    ).points
    with pytest.raises(ValueError, match=r"2 \* bandwidth \+ 1"):
        fit_method_b_from_samples(
            parameters,
            points,
            config=MethodBConfig(
                bandwidth=8,
                arclength=_small_arclength_config(refit_samples=16),
            ),
        )


def test_fourier_fit_rejects_underdetermined_samples() -> None:
    parameters = _uniform_parameters(8)
    points = circle((0.0, 0.0), 1.0, component_id="reference").evaluate(
        parameters,
        wrap=False,
    ).points
    with pytest.raises(ValueError, match="At least 9 samples"):
        fit_fourier_least_squares(parameters, points, bandwidth=4)


def test_near_nyquist_fourier_interpolant_rejects_created_self_intersection() -> None:
    sample_count = 9
    parameters = _uniform_parameters(sample_count)
    radii = np.ones(sample_count)
    radii[0] = 5.0
    points = np.column_stack((radii * np.cos(parameters), radii * np.sin(parameters)))
    assert polygon_self_intersection_count(points) == 0

    with pytest.raises(OrderedBoundaryValidationError) as captured:
        fit_method_b_from_samples(
            parameters,
            points,
            config=MethodBConfig(
                bandwidth=4,
                validation=BoundaryValidationConfig(
                    num_samples_per_component=2048,
                    derivative_relative_tolerance=1.0e-2,
                ),
            ),
        )
    assert captured.value.report.self_intersection_count > 0
