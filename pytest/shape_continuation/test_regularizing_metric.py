"""SC-031: opt-in step metrics and Hanke's regularizing-LM parameter choice."""
import numpy as np
import pytest

from experiments.shape_continuation.geometry import FourierCurve, arclength_angles, grid_size, normal_basis
from experiments.shape_continuation.lm_backend import BackendConfig, Ledger, fit_stage, hanke_damping
from experiments.shape_continuation.test_lm_backend import observations, stage
from experiments.shape_continuation.updates import BorgesUpdate

L = 0.05  # package length unit (m), as in the six-case study


def peanut(band=48):
    t = 2 * np.pi * np.arange(4096) / 4096
    radius = 1.0 + 0.25 * np.cos(2 * t) + 0.08 * np.sin(3 * t)
    update = BorgesUpdate(L, projection_tolerance=1e-5)
    return update.regauge(FourierCurve.from_samples(radius * np.exp(1j * t), 16), band)[0], update


def test_defaults_are_the_v2_rule():
    config = BackendConfig()
    assert (config.damping_rule, config.metric, config.log_model) == ("schedule", "marquardt", False)
    for bad in (dict(damping_rule="x"), dict(metric="x"), dict(hanke_ratio=1.0), dict(detectability_factor=0.)):
        with pytest.raises(ValueError):
            BackendConfig(**bad)


def test_circle_metrics_match_their_closed_forms():
    update = BorgesUpdate(L, projection_tolerance=1e-5)
    curve, _ = update.regauge(FourierCurve.circle(1.3), 24)
    space = update.prepare(curve, 5, 24)
    mass = update.metric(space, "mass")
    assert np.allclose(mass, np.diag([1.] + [.5] * 10), atol=1e-12)
    smoothing, radius = 0.0156, 1.3 * L
    orders = np.r_[0, np.arange(1, 6), np.arange(1, 6)]
    expected = np.diag((1 + smoothing**4 * (orders**2 - 1.)**2 / radius**4) * np.diag(mass))
    assert np.allclose(update.metric(space, "curvature", smoothing), expected, rtol=1e-9, atol=1e-12)
    with pytest.raises(ValueError):
        update.metric(space, "curvature")


def test_curvature_form_matches_a_finite_difference_normal_variation():
    curve, update = peanut()
    space = update.prepare(curve, 7, 48)
    smoothing = 0.01
    extra = (update.metric(space, "curvature", smoothing) - update.metric(space, "mass")) / smoothing**4
    count = grid_size(max(curve.band, 7))
    nodes = curve.nodes(count)
    normal = nodes.normals[:, 0] + 1j * nodes.normals[:, 1]
    weights = nodes.arc_length_weights / np.sum(nodes.arc_length_weights)
    rng = np.random.default_rng(31)
    for _ in range(4):
        a = 1e-3 * rng.standard_normal(15)  # metres
        h = normal_basis(nodes, 7) @ a / L   # package units
        eps = 1e-4

        def kappa(sign):
            moved = FourierCurve.from_samples(curve.values(count) + sign * eps * h * normal, count // 2 - 1)
            return moved.nodes(count).curvatures / L  # 1/m, at the same material points
        change = (kappa(1) - kappa(-1)) / (2 * eps)
        assert abs(a @ extra @ a / np.sum(weights * change**2) - 1) < 1e-3


def test_metrics_are_covariant_under_an_arclength_origin_shift():
    curve, update = peanut()
    count = grid_size(curve.band)
    shift = 517
    angles, _ = arclength_angles(curve.nodes(count))
    phi = angles[shift]
    rotated = FourierCurve(curve.coefficients * np.exp(1j * curve.modes * 2 * np.pi * shift / count))
    band = 7
    m = np.arange(1, band + 1)
    rotation = np.zeros((2 * band + 1,) * 2)  # a' = S a for the same physical h
    rotation[0, 0] = 1
    rotation[m, m] = rotation[band + m, band + m] = np.cos(m * phi)
    rotation[m, band + m] = np.sin(m * phi)
    rotation[band + m, m] = -np.sin(m * phi)
    for kind, smoothing in (("mass", None), ("curvature", 0.008)):
        before = update.metric(update.prepare(curve, band, 48), kind, smoothing)
        after = update.metric(update.prepare(rotated, band, 48), kind, smoothing)
        assert np.linalg.norm(rotation.T @ after @ rotation - before) < 1e-10 * np.linalg.norm(before)


def test_hanke_parameter_hits_the_requested_linearized_residual():
    rng = np.random.default_rng(7)
    matrix = rng.standard_normal((48, 7)) * np.logspace(0, -3, 7)
    residual = matrix @ rng.standard_normal(7) + 1e-3 * rng.standard_normal(48)
    base = rng.standard_normal((7, 7))
    metric = base @ base.T + 7 * np.eye(7)
    for ratio in (0.3, 0.7, 0.95):
        lam, attainable = hanke_damping(matrix, residual, metric, ratio)
        step = -np.linalg.solve(matrix.T @ matrix + lam * metric, matrix.T @ residual)
        assert attainable and abs(np.linalg.norm(residual + matrix @ step) / np.linalg.norm(residual) - ratio) < 1e-8
    # Residual almost orthogonal to the range of J: Gauss-Newton cannot reach the ratio.
    q, _ = np.linalg.qr(matrix, mode="complete")
    orthogonal = q[:, 7:] @ rng.standard_normal(41) + 1e-3 * q[:, :7] @ rng.standard_normal(7)
    lam, attainable = hanke_damping(matrix, orthogonal, metric, 0.7)
    gram = np.linalg.eigvalsh(np.linalg.solve(np.linalg.cholesky(metric), matrix.T) @
                              np.linalg.solve(np.linalg.cholesky(metric), matrix.T).T)
    assert not attainable and np.isclose(lam, 1e-12 * np.mean(gram))


def test_hanke_curvature_stage_runs_decreases_and_logs_its_model():
    contrast = .5
    truth = FourierCurve(np.array([.08, .1 + .05j, 1.15]))
    obs = observations(truth, (1.0, 1.5), contrast)
    update = BorgesUpdate(1.0)
    config = BackendConfig(step_bounds_m=(.12, .18, .06), damping_rule="hanke", metric="curvature", log_model=True)
    initial, _ = update.regauge(FourierCurve.circle(1.0), 24)
    ledger = Ledger(cap=4000, seconds=600)
    ledger.begin_stage("s", None)
    result = fit_stage(initial, stage(obs, iterations=6), contrast, update, config, ledger)
    losses = [row["loss"] for row in result.history]
    assert result.accepted_steps >= 3 and all(b < a for a, b in zip(losses, losses[1:]))
    assert all({"predicted_decrease", "hanke_lambda", "hanke_attainable"} <= set(t) for t in result.trials)
    first = result.trials[0]
    assert first["damping"] == first["hanke_lambda"] or first["backtrack"] > 0
