"""Indexed readout preserves the paired solver and its full-matrix derivatives."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

import gpr_bem_kress
from gpr_bem_kress.shape_derivative import (
    KressDirection,
    build_indexed_objective_adjoint,
    linearize_kress_forward,
)
from ordered_boundary import circle
from sdf_inverse import (
    IndexedForwardProblem,
    IndexedForwardResult,
    MaterialSpec,
    OrderedSDFGeometryConfig,
    PairedForwardProblem,
    PairedForwardResult,
    predict_indexed_curve_response,
    predict_indexed_response,
    predict_paired_curve_response,
)
import sdf_inverse.forward as forward_module


def _config():
    return OrderedSDFGeometryConfig(
        bounds=((-0.1, -0.1), (0.1, 0.1)), grid_shape=(17, 17),
        projected_samples=64, bandwidth=5, num_nodes=64,
        arclength_dense_resolution=128, validation_resolution=128,
    )


def _paired():
    return PairedForwardProblem(
        source_points=np.array([[0.27, 0.02], [-0.24, 0.11]]),
        receiver_points=np.array([[0.04, 0.29], [-0.17, -0.25]]),
        angular_frequencies=2 * np.pi * np.array([0.5e9, 1.5e9]),
        source_strengths=np.array([1 + 0.2j, -0.4 + 0.7j]),
        exterior=MaterialSpec(2.0), interior=MaterialSpec(4.2),
        eps0=8.8541878128e-12, mu0=4e-7 * np.pi,
    )


def _indexed(readout):
    problem = IndexedForwardProblem.from_paired(_paired(), multistatic=True)
    if readout == "rectangular_duplicates":
        return replace(
            problem,
            receiver_points=np.vstack([problem.receiver_points, [0.22, -0.19]]),
            source_indices=np.array([1, 0, 1, 0, 0]),
            receiver_indices=np.array([2, 0, 1, 2, 0]),
        )
    return problem


def _curve(radius=0.05):
    return circle((0.0, 0.0), radius).discretize(_config().num_nodes)


def test_indexed_diagonal_is_bitwise_identical_to_paired_and_full_readout():
    paired = _paired()
    diagonal = IndexedForwardProblem.from_paired(paired)
    full = IndexedForwardProblem.from_paired(paired, multistatic=True)
    curve = _curve()
    old = predict_paired_curve_response(curve, paired, _config(), solver="kress")
    new = predict_indexed_curve_response(curve, diagonal, _config())
    all_entries = predict_indexed_curve_response(curve, full, _config(), retain_kress_state=True)
    assert type(old) is PairedForwardResult
    assert type(new) is IndexedForwardResult
    assert not hasattr(new, "paired_scattered_response")
    assert not new.kress_states
    assert len(all_entries.kress_states) == paired.num_frequencies
    np.testing.assert_array_equal(full.source_indices, [0, 0, 1, 1])
    np.testing.assert_array_equal(full.receiver_indices, [0, 1, 0, 1])
    assert full.num_measurements == 4
    for name in ("scattered_response", "total_response"):
        np.testing.assert_array_equal(getattr(old, name), getattr(new, name))
        np.testing.assert_array_equal(getattr(old, name), getattr(all_entries, name)[[0, 3]])
        assert not getattr(new, name).flags.writeable
    np.testing.assert_array_equal(old.linear_system_relative_residuals, new.linear_system_relative_residuals)


def test_rectangular_sdf_entrypoint_extracts_once_and_reuses_full_kress_solve(monkeypatch):
    problem = _indexed("rectangular_duplicates")
    config = _config()
    geometry = forward_module._curve_geometry_build(_curve(), config)
    extractions, solves = [], []

    def extract(model, supplied_config):
        extractions.append((model, supplied_config))
        return geometry

    def solve(curve, sources, receivers, omega, strength, **kwargs):
        solves.append((sources.shape, receivers.shape, omega, strength))
        full = np.arange(6).reshape(2, 3) + omega * 1j
        return SimpleNamespace(
            scattered_receiver=full, total_receiver=full + strength,
            linear_system_relative_residual=1e-14,
        )

    monkeypatch.setattr(forward_module, "build_ordered_sdf_geometry", extract)
    monkeypatch.setattr(gpr_bem_kress, "solve_kress_tmz_total_field_batch", solve)
    model = object()
    result = predict_indexed_response(model, problem, config, retain_kress_state=True)
    assert extractions == [(model, config)]
    assert len(solves) == len(result.kress_states) == 2
    assert all(source_shape == (2, 2) and receiver_shape == (3, 2)
               for source_shape, receiver_shape, _, _ in solves)
    expected = np.array([5, 0, 4, 2, 0])[:, None] + 1j * problem.angular_frequencies[None, :]
    np.testing.assert_array_equal(result.scattered_response, expected)
    np.testing.assert_array_equal(result.total_response, expected + problem.source_strengths)


@pytest.mark.parametrize("readout", ["full", "rectangular_duplicates"])
@pytest.mark.parametrize("observable", ["scattered", "total"])
def test_indexed_jvp_and_adjoint_have_central_difference_convergence(readout, observable):
    problem = _indexed(readout)
    curve = _curve()
    result = predict_indexed_curve_response(curve, problem, _config(), retain_kress_state=True)
    direction = KressDirection(**{
        name: getattr(curve, name) / 0.05 for name in (
            "points", "first_derivatives", "second_derivatives", "third_derivatives",
        )
    })
    derivative = np.column_stack([
        problem.select_response(getattr(linearize_kress_forward(base, direction), f"d_{observable}_receiver"))
        for base in result.kress_states
    ])
    rng = np.random.default_rng(901)
    shape = (problem.num_measurements, problem.num_frequencies)
    observations = 0.02 * (rng.normal(size=shape) + 1j * rng.normal(size=shape))
    transform = rng.normal(size=(13, 2 * observations.size))
    objective = build_indexed_objective_adjoint(
        result.kress_states, observations, problem.source_indices, problem.receiver_indices,
        residual_transform=transform, observable=observable,
    )
    np.testing.assert_array_equal(objective.prediction, getattr(result, f"{observable}_response"))
    analytic_loss_derivative = objective.directional_derivative(direction)
    direct = objective.residual @ transform @ np.concatenate([derivative.real.ravel(), derivative.imag.ravel()])
    np.testing.assert_allclose(analytic_loss_derivative, direct, rtol=2e-12, atol=1e-12)
    errors, loss_errors = [], []
    for step in (2e-4, 1e-4, 5e-5):
        responses, losses = [], []
        for radius in (0.05 + step, 0.05 - step):
            perturbed = predict_indexed_curve_response(_curve(radius), problem, _config())
            prediction = getattr(perturbed, f"{observable}_response")
            responses.append(prediction)
            difference = prediction - observations
            residual = transform @ np.concatenate([difference.real.ravel(), difference.imag.ravel()])
            losses.append(0.5 * np.dot(residual, residual))
        fd = (responses[0] - responses[1]) / (2 * step)
        errors.append(np.linalg.norm(fd - derivative) / np.linalg.norm(derivative))
        loss_errors.append(abs((losses[0] - losses[1]) / (2 * step) - analytic_loss_derivative)
                           / abs(analytic_loss_derivative))
    assert errors[0] > 3.5 * errors[1] > 3.5**2 * errors[2]
    assert errors[-1] < 2e-5
    assert loss_errors[0] > 3.5 * loss_errors[1] > 3.5**2 * loss_errors[2]
    assert loss_errors[-1] < 5e-5
    assert objective.diagnostics["adjoint_solve_count"] == problem.num_frequencies
    assert objective.diagnostics["tangent_solve_count"] == 0


@pytest.mark.parametrize("indices", [[0.0], [True], [-1], [2], [2**64 - 1], []])
def test_indexed_problem_rejects_invalid_source_indices(indices):
    with pytest.raises(ValueError, match="source_indices"):
        replace(_indexed("full"), source_indices=indices, receiver_indices=[0])


def test_indexed_validation_does_not_weaken_paired_contract():
    problem = _indexed("rectangular_duplicates")
    with pytest.raises(ValueError, match="same shape"):
        replace(problem, receiver_indices=[0])
    with pytest.raises(ValueError, match="distinct"):
        replace(problem, receiver_points=problem.source_points)
    with pytest.raises(ValueError, match="same .* shape"):
        replace(_paired(), receiver_points=problem.receiver_points)
    with pytest.raises(TypeError, match="PairedForwardProblem"):
        predict_paired_curve_response(_curve(), problem, _config(), solver="kress")
    with pytest.raises(ValueError, match="require solver='kress'"):
        predict_indexed_curve_response(_curve(), problem, _config(), solver="mod")
    with pytest.raises(RuntimeError, match="shape"):
        problem.select_response(np.ones((3, 2)))
    with pytest.raises(FloatingPointError, match="non-finite"):
        problem.select_response(np.full((2, 3), np.nan))
    for name in ("source_indices", "receiver_indices", "source_points", "receiver_points"):
        assert not getattr(problem, name).flags.writeable
