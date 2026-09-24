"""Atlas layers in backend coordinates agree with the backend's own step."""
import numpy as np

from .atlas_survey import cell, gn_step, lm_step, pair_magnitude, stage_sum, true_error
from .geometry import FourierCurve
from .lm_backend import BackendConfig, Ledger, Objective
from .test_lm_backend import observations, padded_circle, stage
from .updates import BorgesUpdate


def test_stage_step_from_per_frequency_layers_equals_backend_proposal():
    contrast, damping = .5, 3e-4
    update = BorgesUpdate(0.05)
    curve, _ = update.regauge(FourierCurve(np.array([.2, .05j, 1.1])), 24)
    obs = observations(FourierCurve.circle(1.05), (1.0, 1.6), contrast)
    fit = stage(obs, modes=6, curve_modes=24, nodes=96)
    objective = Objective(fit, contrast, BackendConfig(), Ledger())
    base = objective.production(curve, "x")
    matrix = objective.jacobian(base, update, update.prepare(curve, 6, 24))
    normal, gradient = matrix.T @ matrix, matrix.T @ base.residual
    expected = np.linalg.solve(normal + damping * np.diag(np.maximum(np.diag(normal), 1.0)), -gradient)
    cells = [cell(curve, o, contrast, 96, 6, 0.05) for o in obs]
    assembled = lm_step(*stage_sum(cells, fit.weights), damping)
    assert np.allclose(assembled, expected, rtol=1e-9, atol=1e-14 * np.linalg.norm(expected))
    assert abs(sum(w * c.loss for c, w in zip(cells, fit.weights)) - base.loss) < 1e-12 * base.loss


def test_gauss_newton_step_and_predicted_decrease_for_full_rank_block():
    rng = np.random.default_rng(1)
    a = rng.standard_normal((20, 5))
    block, gradient = a.T @ a, rng.standard_normal(5)
    step, decrease = gn_step(block, gradient)
    assert np.allclose(step, -np.linalg.solve(block, gradient))
    assert np.isclose(decrease, 0.5 * gradient @ np.linalg.solve(block, gradient))
    assert np.allclose(pair_magnitude(np.array([3., 1, 2, 4, 2]), 2), [3, np.hypot(1, 4), np.hypot(2, 2)])


def test_true_error_of_concentric_circles_is_a_uniform_outward_move():
    t = np.linspace(0, 2 * np.pi, 4000, endpoint=False)
    coefficients, summary = true_error(padded_circle(1.0, 8), 1.1 * np.exp(1j * t), 6, 0.05)
    assert abs(coefficients[0] - 0.1 * 0.05) < 1e-6 * 0.05
    assert np.max(np.abs(coefficients[1:])) < 1e-6 * 0.05
    assert summary["beyond_band_rms_m"] < 1e-6 * 0.05
