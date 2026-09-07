"""Contracts for the experimental continuous-field distance/contact adapter."""

from dataclasses import replace

import numpy as np
import pytest

from sdf_to_ordered_boundary.distance_tangency import (
    DistanceContactSamples, DistanceTangencyConfig, _tangent_objective,
    audit_closest_contacts, fit_distance_tangency, make_offsurface_queries,
    projected_contact_samples, sample_distance_contacts,
)
from sdf_to_ordered_boundary.fields import CircleSDF, CountedImplicitField2D
from sdf_to_ordered_boundary.parameter_aware import fit_without_arclength


def fixture(count=32):
    t = 2*np.pi*np.arange(count)/count
    normals = np.column_stack((np.cos(t), np.sin(t)))
    points = .5+.05*normals
    field = CircleSDF((.5, .5), .05)
    baseline = fit_without_arclength(t, points, bandwidth=1)
    sources = points + .003*np.where(np.arange(count)%2, -1., 1.)[:, None]*normals
    return t, points, field, baseline, sources


def test_exact_signed_contacts_count_queries_and_preserve_inputs():
    t, points, field, baseline, sources = fixture()
    copy = sources.copy()
    counted = CountedImplicitField2D(field)
    samples = sample_distance_contacts(counted, sources)
    np.testing.assert_allclose(samples.contacts, points, atol=2e-16)
    np.testing.assert_array_equal(sources, copy)
    assert not samples.contacts.flags.writeable
    assert counted.counts.value_points == 2*len(points)
    assert counted.counts.gradient_points == 2*len(points)
    result, candidate = fit_distance_tangency(samples, t, fallback=baseline,
                                             config=DistanceTangencyConfig(bandwidth=1))
    assert result.status == "success"
    assert result.diagnostics["closest_contacts"]["source_side_mismatches"] == 0
    assert result.diagnostics["maximum_contact_fit_error_m"] < 1e-13
    assert candidate is result.representation


def test_tangent_reduced_gradient_matches_directional_finite_difference_with_penalty():
    t, points, field, _, sources = fixture()
    sources = sources+.0003*np.column_stack((np.sin(3*t), np.cos(2*t)))
    samples = sample_distance_contacts(field, sources)
    config = DistanceTangencyConfig(bandwidth=2, tangency_weight=.1, spectral_penalty=1e-5)
    logits = .04*np.sin(t[:-1])
    direction = np.cos(1.7*np.arange(len(logits)))
    value, gradient, *_ = _tangent_objective(logits, samples, config)
    h = 1e-5
    finite = (_tangent_objective(logits+h*direction, samples, config)[0]
              - _tangent_objective(logits-h*direction, samples, config)[0])/(2*h)
    assert value > 0
    assert gradient@direction == pytest.approx(finite, rel=1e-5, abs=1e-12)


def test_same_zero_and_unit_boundary_gradient_do_not_certify_metric_contacts():
    t, points, field, baseline, sources = fixture()
    class Distorted:
        def value(self, x):
            d = field.value(x)
            return d*(1+.4*np.tanh(d/.02))
        def gradient(self, x):
            d = field.value(x); u = d/.02; z = np.tanh(u)
            return field.gradient(x)*(1+.4*z+.4*u*(1-z*z))[:, None]
    distorted = Distorted()
    np.testing.assert_allclose(distorted.value(points), 0, atol=1e-15)
    np.testing.assert_allclose(np.linalg.norm(distorted.gradient(points), axis=1), 1, atol=1e-14)
    samples = sample_distance_contacts(distorted, sources)
    assert np.max(samples.contact_normalized_zero_residual_m) > 1e-4
    result, raw = fit_distance_tangency(samples, t, fallback=baseline,
                                       config=DistanceTangencyConfig(bandwidth=1))
    assert result.status == "fallback"
    assert result.representation is baseline.representation
    assert raw is not baseline.representation
    assert "not on the queried field zero set" in result.failure_reason
    control = projected_contact_samples(distorted, sources, points)
    result, _ = fit_distance_tangency(control, t, fallback=baseline,
                                      config=DistanceTangencyConfig(bandwidth=1))
    assert result.status == "success"
    assert result.diagnostics["closest_contacts"]["metric_radius_maximum_error_m"] is None


def test_tangent_stationarity_on_far_branch_is_not_closest_contact():
    t, _, field, baseline, sources = fixture()
    samples = sample_distance_contacts(field, sources)
    audit = audit_closest_contacts(samples, baseline.parameterization, assigned_parameters=t+np.pi)
    assert audit["assigned_contact_excess_distance_m"] > .09
    assert audit["metric_radius_maximum_error_m"] < 1e-12


def test_offsurface_proposal_uses_only_queried_seed_normals_and_is_not_tautological():
    t, points, field, _, _ = fixture()
    counted = CountedImplicitField2D(field)
    sources = make_offsurface_queries(counted, points)
    assert counted.counts.value_points == 0
    assert counted.counts.gradient_points == len(points)
    contacts = sample_distance_contacts(field, sources)
    assert np.max(np.linalg.norm(contacts.contacts-points, axis=1)) > 1e-4


def test_normal_orientation_and_bad_sample_contracts():
    t, _, field, baseline, sources = fixture()
    samples = sample_distance_contacts(field, sources)
    reversed_normals = replace(samples, normals=-samples.normals)
    result, _ = fit_distance_tangency(reversed_normals, t, fallback=baseline,
                                     config=DistanceTangencyConfig(bandwidth=1))
    assert result.status == "fallback"
    assert "normal orientation" in result.failure_reason
    with pytest.raises(ValueError, match="unit"):
        replace(samples, normals=2*samples.normals)
    with pytest.raises(TypeError, match="integer"):
        DistanceTangencyConfig(bandwidth=True)
    with pytest.raises(ValueError, match="parameter_origin|phase gauge"):
        fit_distance_tangency(samples, t+.001, fallback=baseline,
                              config=DistanceTangencyConfig(bandwidth=1))


def test_crossed_contact_order_is_rejected_without_silent_sorting():
    t, _, field, baseline, sources = fixture()
    samples = sample_distance_contacts(field, sources)
    contacts = samples.contacts.copy()
    contacts[[1, 2]] = contacts[[2, 1]]
    crossed = replace(samples, contacts=contacts)
    result, _ = fit_distance_tangency(crossed, t, fallback=baseline,
                                     config=DistanceTangencyConfig(bandwidth=1))
    assert result.status == "fallback"
    assert "contact order/orientation" in result.failure_reason
    np.testing.assert_array_equal(crossed.contacts, contacts)
