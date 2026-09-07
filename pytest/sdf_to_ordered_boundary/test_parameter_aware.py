"""Accuracy and failure contracts for the opt-in ordered-label fit."""

import numpy as np
import pytest

from ordered_boundary import BoundaryValidationConfig, validate_periodic_parameterization
from sdf_to_ordered_boundary.fields import EllipseLevelSet
from sdf_to_ordered_boundary.parameter_aware import (
    ParameterAwareConfig, _labels, _variable_projection, closest_parameters,
    exact_arclength_ellipse, fit_parameter_aware, fit_without_arclength,
)


def _ellipse_samples(count=64):
    field = EllipseLevelSet((0.5, 0.5), 0.07, 0.035, rotation=0.4)
    curve = exact_arclength_ellipse()
    labels = np.arange(count) * 2 * np.pi / count
    return field, labels, curve.evaluate(labels).points


def test_exact_arclength_ellipse_preserves_analytic_set_and_consistent_jets():
    field, labels, _ = _ellipse_samples(256)
    curve = exact_arclength_ellipse()
    evaluation = curve.evaluate(labels + 0.00123)
    assert np.max(np.abs(field.value(evaluation.points))) < 2e-14
    speed = np.linalg.norm(evaluation.first_derivatives, axis=-1)
    assert np.ptp(speed) < 2e-15
    report = validate_periodic_parameterization(curve, BoundaryValidationConfig(
        num_samples_per_component=512, derivative_samples_per_component=2048
    ), raise_on_error=True)
    assert report.valid
    tighter = exact_arclength_ellipse(inverse_tolerance=2e-15)
    np.testing.assert_allclose(evaluation.points, tighter.evaluate(labels + .00123).points,
                               atol=2e-14, rtol=0)


def test_reduced_objective_gradient_includes_cyclic_label_map_and_ridge():
    _, labels, points = _ellipse_samples(32)
    settings = ParameterAwareConfig(bandwidth=2, spectral_penalty=1e-5)
    logits = .1 * np.sin(labels[:-1])
    value, gradient, *_ = _variable_projection(logits, points, settings)
    direction = np.cos(1.3 * np.arange(len(logits)))
    h = 1e-5
    finite = (_variable_projection(logits + h * direction, points, settings)[0]
              - _variable_projection(logits - h * direction, points, settings)[0]) / (2*h)
    assert value > 0
    assert gradient @ direction == pytest.approx(finite, rel=2e-6, abs=1e-12)
    constrained, gaps, *_ = _labels(np.linspace(-100, 100, 31), settings.minimum_gap_fraction)
    assert constrained[0] == 0.0 and constrained[-1] < 2*np.pi
    assert np.all(np.diff(constrained) > 0) and np.all(gaps > 0)


def test_ordered_labels_recover_bandwidth_one_ellipse_and_preserve_frozen_input():
    field, labels, points = _ellipse_samples()
    original_points, original_labels = points.copy(), labels.copy()
    baseline = fit_without_arclength(labels, points, bandwidth=1)
    fitted = fit_parameter_aware(labels, points, fallback=baseline,
                                config=ParameterAwareConfig(bandwidth=1, max_iterations=160))
    assert fitted.status == "success"
    query = fitted.parameterization.discretize(256).points
    baseline_error = np.max(np.abs(field.value(baseline.parameterization.discretize(256).points)))
    assert np.max(np.abs(field.value(query))) < baseline_error / 100
    fitted_labels = np.asarray(fitted.diagnostics["parameter_labels"])
    assert fitted_labels[0] == 0 and np.all(np.diff(fitted_labels) > 0)
    np.testing.assert_array_equal(points, original_points)
    np.testing.assert_array_equal(labels, original_labels)
    assert fitted.diagnostics["spectral_penalty_m2"] == 0


def test_invalid_speed_candidate_returns_explicit_valid_baseline():
    _, labels, points = _ellipse_samples()
    baseline = fit_without_arclength(labels, points, bandwidth=1)
    fitted = fit_parameter_aware(labels, points, fallback=baseline,
                                config=ParameterAwareConfig(bandwidth=1,
                                                            minimum_speed_ratio=.99))
    assert fitted.status == "fallback"
    assert fitted.representation is baseline.representation
    assert fitted.validation.valid
    assert "speed ratio" in fitted.failure_reason


def test_closest_point_comparison_removes_parameter_phase_sampling_floor():
    curve = exact_arclength_ellipse()
    points = curve.evaluate(np.linspace(0, 2*np.pi, 100, endpoint=False) + .007).points
    _, distances = closest_parameters(points, curve, localization_samples=512)
    assert np.max(distances) < 1e-12


def test_reordered_labels_are_not_silently_repaired():
    _, labels, points = _ellipse_samples()
    baseline = fit_without_arclength(labels, points, bandwidth=1)
    labels[2:4] = labels[2:4][::-1]
    with pytest.raises(ValueError, match="strictly increasing"):
        fit_parameter_aware(labels, points, fallback=baseline,
                            config=ParameterAwareConfig(bandwidth=1))
