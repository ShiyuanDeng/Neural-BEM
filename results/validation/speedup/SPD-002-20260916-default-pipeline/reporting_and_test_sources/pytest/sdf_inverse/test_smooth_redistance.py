"""Opt-in supervision keeps distance/sampling resolution separate from BEM."""

from dataclasses import replace
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ordered_boundary import circle
from sdf_inverse.neural import NeuralRedistanceConfig, SmoothMLPSDF2D, redistance_neural_sdf_to_curve
import sdf_inverse.neural as neural


def _model():
    return SmoothMLPSDF2D(
        bounds=((-0.15, -0.15), (0.15, 0.15)), hidden_features=8,
        hidden_layers=1, geometric_center=(0, 0), geometric_radius=0.055, seed=19,
    )


def _config(**kwargs):
    values = dict(
        bounds=((-0.15, -0.15), (0.15, 0.15)), max_steps=3, minimum_steps=3,
        warmup_steps=0, sample_count=32, heldout_sample_count=16,
        check_interval=3, smooth_boundary_sample_count=64,
        distance_initial_samples=64, distance_maximum_samples=256,
        distance_target="smooth_curve",
    )
    values.update(kwargs)
    return NeuralRedistanceConfig(**values)


def test_smooth_training_is_identical_when_only_bem_nodes_change():
    continuous = circle((0, 0), 0.065)
    models = [_model(), _model()]
    results = [
        redistance_neural_sdf_to_curve(
            model, continuous.discretize(count), _config(), continuous_curve=continuous,
        ) for model, count in zip(models, (16, 64))
    ]
    np.testing.assert_array_equal(results[0].loss_history, results[1].loss_history)
    for first, second in zip(models[0].parameters(), models[1].parameters()):
        torch.testing.assert_close(first, second, rtol=0, atol=0)
    assert results[0].diagnostics["boundary_sample_count"] == 64
    assert results[0].diagnostics["distance_refinement_agreement_m"] < 1e-6


def test_smooth_ablation_preserves_every_legacy_sample_location(monkeypatch):
    captured = []
    original = neural._redistance_objective
    def record(model, samples, targets, boundary, offsets, offset_targets, box, box_targets, **kwargs):
        captured.append(tuple(x.detach().clone() for x in (samples, boundary, offsets, box)))
        return original(model, samples, targets, boundary, offsets, offset_targets, box, box_targets, **kwargs)
    monkeypatch.setattr(neural, "_redistance_objective", record)
    continuous = circle((0, 0), 0.065)
    config = _config(distance_target="legacy_polygon")
    redistance_neural_sdf_to_curve(_model(), continuous.discretize(16), config)
    first = captured[0]
    captured.clear()
    redistance_neural_sdf_to_curve(
        _model(), continuous.discretize(16),
        replace(config, distance_target="smooth_curve", smooth_boundary_sampling="legacy_polygon"),
        continuous_curve=continuous,
    )
    for left, right in zip(first, captured[0]):
        torch.testing.assert_close(left, right, rtol=0, atol=0)


def test_legacy_default_ignores_optional_continuous_input_and_smooth_requires_matching_jets():
    curve = circle((0, 0), 0.065)
    config = _config(distance_target="legacy_polygon")
    models = [_model(), _model()]
    first = redistance_neural_sdf_to_curve(models[0], curve.discretize(16), config)
    second = redistance_neural_sdf_to_curve(
        models[1], curve.discretize(16), config, continuous_curve=circle((0, 0), 0.07),
    )
    np.testing.assert_array_equal(first.loss_history, second.loss_history)
    with pytest.raises(TypeError, match="require continuous_curve"):
        redistance_neural_sdf_to_curve(_model(), curve.discretize(16), _config())
    with pytest.raises(ValueError, match="match the supplied curve node jets"):
        redistance_neural_sdf_to_curve(
            _model(), curve.discretize(16), _config(), continuous_curve=circle((0, 0), 0.07),
        )
