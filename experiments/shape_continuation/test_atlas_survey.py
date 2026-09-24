"""Atlas layers in backend coordinates agree with the backend's own step."""
import numpy as np

from .atlas_survey import (band_coordinates, cell, conditional_step, gn_step, lm_step, normal_ray_error,
                           pair_magnitude, physical_cosine, physical_norm, stage_sum, symmetric_rms_distance,
                           true_error)
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


def test_conditional_step_is_the_schur_complement_solve_not_a_slice():
    rng = np.random.default_rng(3)
    rows = rng.standard_normal((12, 9))
    block, gradient, damping = rows.T @ rows, rng.standard_normal(9), 1e-3
    keep = np.array([0, 2, 3, 7])
    step = conditional_step(block, gradient, keep, damping)
    H = block + damping * np.diag(np.maximum(np.diag(block), 1.0))
    A, B = keep[:2], keep[2:]  # eliminate A, solve for B, as in the review's derivation
    Hk = H[np.ix_(keep, keep)]
    schur = Hk[2:, 2:] - Hk[2:, :2] @ np.linalg.solve(Hk[:2, :2], Hk[:2, 2:])
    rhs = gradient[B] - Hk[2:, :2] @ np.linalg.solve(Hk[:2, :2], gradient[A])
    assert np.allclose(step[B], -np.linalg.solve(schur, rhs))
    assert np.all(step[np.setdiff1d(np.arange(9), keep)] == 0)
    assert not np.allclose(step[B], lm_step(block, gradient, damping)[B])


def test_physical_metric_is_the_arclength_rms_of_h():
    s = 2 * np.pi * np.arange(4096) / 4096
    band = 3
    c = np.array([.2, .1, -.3, .05, .4, 0., -.2])
    h = c[0] + sum(c[p] * np.cos(p * s) + c[band + p] * np.sin(p * s) for p in range(1, band + 1))
    assert np.isclose(physical_norm(c, band), np.sqrt(np.mean(h ** 2)))
    d = np.array([.0, .3, .1, -.2, .1, .5, .0])
    g = d[0] + sum(d[p] * np.cos(p * s) + d[band + p] * np.sin(p * s) for p in range(1, band + 1))
    assert np.isclose(physical_cosine(c, d, band), np.mean(h * g) / np.sqrt(np.mean(h ** 2) * np.mean(g ** 2)))
    assert np.array_equal(band_coordinates(2, 5), [0, 1, 2, 6, 7])


def test_normal_ray_error_is_exact_for_offset_circles_where_the_proxy_is_not():
    # The review's counterexample: SC-022's 65 mm start circle and 50 mm target,
    # offset by (-20, 20) mm, in package units of 5 cm.
    L, offset, radius, target = 0.05, (-.02 + .02j) / 0.05, .065 / 0.05, .05 / 0.05
    curve = FourierCurve(np.pad(FourierCurve.circle(radius, offset).coefficients, (7, 7)))
    truth = target * np.exp(2j * np.pi * np.arange(16384) / 16384)
    coefficients, summary = normal_ray_error(curve, truth, 16, L, count=2048)
    nodes = curve.nodes(2048)
    normal = nodes.normals[:, 0] + 1j * nodes.normals[:, 1]
    b = np.real(offset * np.conj(normal))
    exact = (-b + np.sqrt(b * b + target ** 2 - abs(offset) ** 2) - radius) * L
    from .geometry import normal_basis
    h = normal_basis(nodes, 16) @ coefficients
    assert summary["coverage"] == 1.0
    assert np.max(np.abs(h - exact)) < 1e-8  # metres; the truth polygon limits it
    proxy, _ = true_error(curve, truth, 16, L, count=2048)
    assert np.max(np.abs(normal_basis(nodes, 16) @ proxy - exact)) > 2e-3  # ~3 mm, the review's value
    assert summary["proxy_difference_rms_m"] > 1e-3


def test_symmetric_rms_distance_of_concentric_circles():
    truth = 1.1 * np.exp(2j * np.pi * np.arange(8192) / 8192)
    assert abs(symmetric_rms_distance(padded_circle(1.0, 8), truth, 0.05) - 0.1 * 0.05) < 1e-6 * 0.05


def test_one_normal_move_on_a_circle_creates_the_doubled_harmonic_in_the_new_arclength():
    # Review point 5: h = eps cos(m theta) on a circle of radius R. In the new
    # curve's normalized arclength, the radial offset carries harmonic 2m with
    # amplitude eps^2 / (2R) and mean eps^2 / (2R), to O(eps^3).
    R, m, eps = 1.0, 3, 0.01
    update = BorgesUpdate(1.0)
    space = update.prepare(padded_circle(R, 32), m, 32)
    a = np.zeros(2 * m + 1)
    a[m] = eps
    moved, _ = update.trial(space, a)
    radial = np.abs(moved.values(4096)) - R  # the new curve is stored in its own arclength
    spectrum = np.fft.rfft(radial) / 4096
    assert np.isclose(abs(2 * spectrum[m]), eps, rtol=1e-3)
    assert np.isclose(2 * spectrum[2 * m].real, -eps ** 2 / (2 * R), rtol=0.01)  # -cos(2m phi)
    assert np.isclose(spectrum[0].real, eps ** 2 / (2 * R), rtol=0.01)


def test_dataset_jacobian_reproduces_the_atlas_cell_blocks(tmp_path):
    from . import atlas_dataset as ds
    contrast = .5
    truth = FourierCurve.circle(1.05)
    obs = observations(truth, (1.0, 1.6), contrast)
    ds._W.update(catalogs=dict(toy=obs), truths=dict(toy=truth), contrast=contrast)
    curve = padded_circle(1.0, 8)
    path = ds.compute(("toy", ds.curve_key(curve.coefficients), curve.coefficients, str(tmp_path)))
    stored = np.load(path)
    for j, o in enumerate(obs):
        reference = cell(curve, o, contrast, ds.NODES, ds.P, 0.05)
        J, r = stored["jacobian"][j], stored["residual"][j]
        assert np.allclose(J.T @ J, reference.gauss_newton, rtol=1e-12, atol=1e-12 * np.abs(reference.gauss_newton).max())
        assert np.allclose(J.T @ r, reference.gradient, rtol=1e-12, atol=1e-12 * np.abs(reference.gradient).max())
        assert np.isclose(stored["loss"][j], reference.loss, rtol=1e-14)
    assert abs(float(stored["symmetric_rms_m"]) - 0.05 * 0.05) < 1e-6 * 0.05
