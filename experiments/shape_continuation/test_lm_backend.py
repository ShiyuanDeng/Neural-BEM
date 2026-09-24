"""SPD-style LM backend and the replaceable Borges update."""
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from .forward import PointSourceAcquisition, solve
from .geometry import FourierCurve
from .inverse import Observation
from .lm_backend import (BackendConfig, FitStage, FixedSchedule, Ledger, Objective, StageQuota,
                         acceptance, fit_stage, normalize, run_policy)
from .updates import BorgesUpdate, UpdateRefused

ROOT = Path(__file__).resolve().parents[2]


def acquisition(count=12, radius=6.0):
    t = 2 * np.pi * np.arange(count) / count
    sources = radius * np.column_stack((np.cos(t), np.sin(t)))
    receivers = radius * np.column_stack((np.cos(t + .2), np.sin(t + .2)))
    return PointSourceAcquisition(sources, receivers, 1.0)


def observations(truth, wavenumbers, contrast, nodes=256):
    scan = acquisition()
    return tuple(Observation(k, scan, solve(truth, k, contrast, scan, nodes).prediction) for k in wavenumbers)


def padded_circle(radius=1.0, band=8):
    return FourierCurve(np.pad(FourierCurve.circle(radius).coefficients, (band - 1, band - 1)))


def stage(obs, *, modes=4, curve_modes=24, nodes=96, iterations=8, quota=None):
    count = len(obs)
    return FitStage("s", obs, tuple(np.ones(count) / count), (1e-5,) * count, modes, curve_modes,
                    nodes, 2 * nodes, iterations, quota)


def test_normalization_matches_spd_residual_map():
    sys.path.insert(0, str(ROOT / "solvers"))
    from sdf_inverse.optimization import normalized_complex_residual
    rng = np.random.default_rng(3)
    observed = rng.standard_normal((24, 3)) + 1j * rng.standard_normal((24, 3))
    predicted = observed + 1e-3 * (rng.standard_normal((24, 3)) + 1j * rng.standard_normal((24, 3)))
    weights = np.array([.2, .3, .5])
    expected, _ = normalized_complex_residual(predicted, observed, weights)
    assert np.array_equal(normalize(predicted - observed, observed, weights), expected)
    # Trailing axes (Jacobian columns) follow the same row order.
    columns = np.stack((predicted - observed, 2 * (predicted - observed)), axis=-1)
    stacked = normalize(columns, observed, weights)
    assert np.allclose(stacked[:, 1], 2 * expected, rtol=0, atol=1e-15)


def test_acceptance_matches_spd_cross_resolution_rule():
    sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]
    import run_top016_pilot as spd
    rng = np.random.default_rng(4)
    for _ in range(200):
        base, refined = 10 ** rng.uniform(-14, -2, 2)
        values = (base, base * rng.uniform(.5, 1.01), refined, refined * rng.uniform(.5, 1.01))
        assert acceptance(*values, BackendConfig()) == spd.acceptance(*values)


def test_step_bounds_follow_harmonic_order():
    config = BackendConfig()
    update = BorgesUpdate(0.05)
    space = update.prepare(FourierCurve.circle(), 3, 1)
    assert space.labels == ("a0", "a1", "a2", "a3", "b1", "b2", "b3")
    assert np.array_equal(config.bounds(space.orders), [.012, .018, .006, .006, .018, .006, .006])


def test_jacobian_matches_finite_differences_through_the_actual_trial():
    contrast, k = .5, 1.2
    update = BorgesUpdate(0.05)
    curve, _ = update.regauge(FourierCurve(np.array([.25, 0j, 1.1])), 32)
    obs = observations(FourierCurve.circle(1.05), (k,), contrast)
    fit = stage(obs, modes=5, curve_modes=32, nodes=128)
    objective = Objective(fit, contrast, BackendConfig(), Ledger())
    base = objective.production(curve, "x")
    space = update.prepare(curve, fit.update_modes, fit.curve_modes)
    matrix = objective.jacobian(base, update, space)
    rng = np.random.default_rng(0)
    for direction in (rng.standard_normal(matrix.shape[1]), np.eye(matrix.shape[1])[5]):
        direction /= np.linalg.norm(direction)
        eps = 1e-7  # metres; one package unit is 5 cm
        plus = objective.production(update.trial(space, eps * direction)[0], "x").residual
        minus = objective.production(update.trial(space, -eps * direction)[0], "x").residual
        linear = matrix @ direction
        assert np.linalg.norm((plus - minus) / (2 * eps) - linear) < 1e-6 * np.linalg.norm(linear)


def test_measure_reports_physical_normal_distance():
    update = BorgesUpdate(0.05)
    space = update.prepare(padded_circle(band=8), 2, 8)
    metric = update.measure(space, np.array([.001, 0, 0, 0, 0]))
    assert abs(metric["maximum_normal_m"] - .001) < 1e-15 and abs(metric["rms_normal_m"] - .001) < 1e-15
    curve, geometry = update.trial(update.prepare(padded_circle(band=8), 2, 8), np.array([.005, 0, 0, 0, 0]))
    assert abs(abs(curve.coefficients[9]) - 1.1) < 1e-12 and abs(geometry["maximum_normal_m"] - .005) < 1e-12


def test_self_intersecting_trial_is_refused_with_a_stable_reason():
    update = BorgesUpdate(1.0)
    space = update.prepare(padded_circle(band=24), 4, 24)
    with pytest.raises(UpdateRefused) as refusal:
        update.trial(space, np.array([0, 0, 0, 0, 3., 0, 0, 0, 0]))
    assert refusal.value.reason in ("self_intersection", "irregular_parameterization")


def test_fit_stage_decreases_monotonically_and_only_commits_accepted_trials():
    contrast = .5
    truth = FourierCurve(np.array([.08, .1 + .05j, 1.15]))
    obs = observations(truth, (1.0, 1.5), contrast)
    update = BorgesUpdate(1.0)  # unit metres keeps the default step bounds meaningful here
    config = BackendConfig(step_bounds_m=(.12, .18, .06))
    initial, _ = update.regauge(FourierCurve.circle(1.0), 24)
    ledger = Ledger(cap=4000, seconds=600)
    ledger.begin_stage("s", None)
    committed = []
    result = fit_stage(initial, stage(obs, iterations=6), contrast, update, config, ledger,
                       on_accept=lambda i, e: committed.append(e.loss))
    losses = [row["loss"] for row in result.history]
    assert result.outcome == "NORMAL_OPTIMIZER_RETURN" and result.accepted_steps >= 3
    assert all(b < a for a, b in zip(losses, losses[1:])) and losses == committed
    assert losses[-1] < 1e-3 * losses[0]
    accepted = [t for t in result.trials if t["status"] == "accepted"]
    assert len(accepted) == result.accepted_steps
    assert result.work["work_units"] == sum(result.work["solves"].values()) + sum(
        result.work["reciprocal_batches"].values())


def test_stage_quota_is_a_normal_stage_end_that_keeps_the_accepted_state():
    ledger = Ledger(cap=1000, seconds=600)
    ledger.begin_stage("s", 20)
    ledger.reserve(7)  # 7 + 12 endpoint reserve fits a 20-unit quota
    with pytest.raises(StageQuota):
        ledger.reserve(9)
    with ledger.endpoint_scope():
        ledger.reserve(9)  # the endpoint itself carries no extra reserve
    contrast = .5
    obs = observations(FourierCurve.circle(1.1), (1.0,), contrast)
    update = BorgesUpdate(1.0)
    initial, _ = update.regauge(FourierCurve.circle(1.0), 24)
    ledger = Ledger(cap=4000, seconds=600)
    result = run_policy(initial, FixedSchedule([stage(obs, quota=22)]), contrast, update,
                        BackendConfig(step_bounds_m=(.12, .18, .06)), ledger)
    assert result.status == "COMPLETED_SCHEDULE"
    assert result.stages[0].outcome == "STAGE_QUOTA_REACHED"
    assert result.stages[0].final_loss < result.stages[0].initial_loss
    assert result.curve is result.stages[0].curve


def test_backend_and_update_never_load_spd_or_legacy_modules():
    code = """
import sys
from experiments.shape_continuation.lm_backend import run_policy, FitStage
from experiments.shape_continuation.updates import BorgesUpdate
forbidden = ('sdf_inverse', 'sdf_bem_multicomponent', 'gpr_bem_mod', 'gpr_bem_ref', 'torch',
             'run_top017', 'experiments.top025', 'experiments.modal_muller_research')
assert not any(name == f or name.startswith(f+'.') for name in sys.modules for f in forbidden)
"""
    environment = dict(os.environ, PYTHONPATH=f"{ROOT / 'solvers'}:{ROOT}")
    subprocess.run([sys.executable, "-c", code], env=environment, cwd=ROOT, check=True, capture_output=True)


def test_physical_step_control_scales_to_the_maximum_normal_bound_and_keeps_direction():
    from .lm_backend import control_step
    update = BorgesUpdate(0.05)
    space = update.prepare(padded_circle(1.0, 24), 8, 24)
    rng = np.random.default_rng(5)
    proposal = 0.01 * rng.standard_normal(17)
    physical = BackendConfig(step_control="physical", physical_step_bound_m=0.004)
    step = control_step(proposal, space, update, physical)
    assert np.isclose(update.measure(space, step)["maximum_normal_m"], 0.004)
    assert np.isclose(step @ proposal / np.linalg.norm(step) / np.linalg.norm(proposal), 1.0)
    small = 1e-6 * proposal
    assert np.array_equal(control_step(small, space, update, physical), small)
    clipped = control_step(proposal, space, update, BackendConfig())
    assert np.array_equal(clipped, np.clip(proposal, -BackendConfig().bounds(space.orders),
                                           BackendConfig().bounds(space.orders)))
    with pytest.raises(ValueError):
        control_step(proposal, space, update, BackendConfig(step_control="other"))
