"""Geometric scaling and spectral checks for the diagnostic, not an optimizer."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_star_observability as study


@pytest.mark.parametrize("location", ["initial", "target"])
def test_normal_modes_are_equal_rms_and_orthogonal_on_arc_length(location):
    producer, probes = study.star_probes(location)
    curve = producer.discretize(1024)
    modal = [p for p in probes if p.family == "modal"]
    columns = np.stack([np.sum(p.evaluator(curve.parameters)[0]*curve.normals, axis=1) for p in modal], axis=1)
    gram = columns.T @ (curve.arc_length_weights[:,None]*columns)/sum(curve.arc_length_weights)
    np.testing.assert_allclose(gram, np.eye(21), atol=2e-10)
    for probe in probes:
        normal = np.sum(probe.evaluator(curve.parameters)[0]*curve.normals, axis=1)*probe.scale
        rms = np.sqrt(np.sum(curve.arc_length_weights*normal**2)/sum(curve.arc_length_weights))
        assert rms == pytest.approx(1e-3, abs=1e-12)


@pytest.mark.parametrize("location", ["initial", "target"])
def test_probe_jets_match_fresh_parameter_differences(location):
    _, probes = study.star_probes(location)
    t = np.array([.037, .34, 1.71, 3.9, 5.23])
    epsilon = 1e-6
    for probe in probes:
        values = probe.evaluator(t)
        minus, plus = probe.evaluator(t-epsilon), probe.evaluator(t+epsilon)
        np.testing.assert_allclose((plus[0]-minus[0])/(2*epsilon), values[1], rtol=2e-7, atol=1e-7)
        np.testing.assert_allclose((plus[1]-minus[1])/(2*epsilon), values[2], rtol=2e-7, atol=1e-6)


def test_spectrum_includes_dimension_forced_nullspace():
    rng = np.random.default_rng(19)
    matrix = rng.normal(size=(8,21))+1j*rng.normal(size=(8,21))
    singular, correlation, ranks = study.spectrum_metrics(matrix)
    assert len(singular) == 21
    assert np.count_nonzero(singular == 0) == 5
    assert max(ranks.values()) == 16
    np.testing.assert_allclose(np.diag(correlation), 1.)


def test_actual_perturbation_has_declared_direction():
    producer, probes = study.star_probes("target")
    t = np.linspace(0, 2*np.pi, 128, endpoint=False)
    for probe in probes:
        step = .01
        minus = study.perturbed_curve(producer, probe, -step).evaluate(t)
        plus = study.perturbed_curve(producer, probe, step).evaluate(t)
        np.testing.assert_allclose((plus.points-minus.points)/(2*step), probe.evaluator(t)[0]*probe.scale, rtol=1e-10, atol=1e-14)
