"""Independent adversarial contracts for bounded material continuation/restarts."""

from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sdf_inverse.forward import MaterialSpec, PairedForwardProblem
from sdf_inverse.material_inverse import (
    PHYSICAL_LOWER, PHYSICAL_UPPER, PARAMETER_SCALES, candidate_state, scaled_parameters,
)
from sdf_inverse.curve_updates import RadialFourierCurveState, radial_fourier_parameterization
import sdf_inverse.robust_material_inverse as robust
import sdf_inverse.material_inverse as material_core


def _problem(frequencies=(1.5, .5, 2.5)):
    angles = np.asarray([.1, 2.1, 4.3])
    sources = .5 + .3*np.column_stack((np.cos(angles), np.sin(angles)))
    receivers = .5 + .3*np.column_stack((np.cos(angles+.13), np.sin(angles+.13)))
    strengths = np.asarray([1+.7j, -.3+.2j, .1-.9j])[:len(frequencies)]*1e-6
    return PairedForwardProblem(sources, receivers, 2*np.pi*1e9*np.asarray(frequencies), strengths,
                                MaterialSpec(6), MaterialSpec(3), 8.8541878128e-12, 1.25663706212e-6)


def _initial():
    return np.asarray([.052, .501, .497, .001, -.002, 8.])


def test_cumulative_frequency_indices_keep_final_original_dataset_identity():
    problem = _problem()
    before = [array.copy() for array in (problem.angular_frequencies, problem.source_strengths)]
    indices = robust.cumulative_frequency_indices(problem)
    assert indices == ((1,), (1, 0), (0, 1, 2))
    for previous, current in zip(indices, indices[1:]):
        assert set(previous).issubset(current)
    for selection in indices:
        subset = robust.subset_problem(problem, selection)
        np.testing.assert_array_equal(subset.angular_frequencies, problem.angular_frequencies[list(selection)])
        np.testing.assert_array_equal(subset.source_strengths, problem.source_strengths[list(selection)])
        np.testing.assert_array_equal(subset.source_points, problem.source_points)
        np.testing.assert_array_equal(subset.receiver_points, problem.receiver_points)
        assert subset.exterior == problem.exterior and subset.interior == problem.interior
        assert not subset.source_strengths.flags.writeable
    np.testing.assert_array_equal(problem.angular_frequencies, before[0])
    np.testing.assert_array_equal(problem.source_strengths, before[1])


@pytest.mark.parametrize("indices", [(), (-1,), (3,), (True,), (.0,), (0, 0), (np.uint64(2**64-1),)])
def test_invalid_frequency_selections_never_wrap_or_silently_duplicate(indices):
    with pytest.raises((ValueError, TypeError, IndexError)):
        robust.subset_problem(_problem(), indices)


def test_restart_seeds_are_deterministic_readonly_bound_derived_and_not_truth_driven():
    initial = _initial()
    preserved = initial.copy()
    random_state = np.random.get_state()
    first = robust.make_restart_candidates(initial, joint_shape=True)
    second = robust.make_restart_candidates(initial, joint_shape=True)
    assert isinstance(first, tuple) and len(first) >= 3
    np.testing.assert_array_equal(first[0], initial)
    assert len({tuple(candidate) for candidate in first}) == len(first)
    np.testing.assert_array_equal(initial, preserved)
    for old, new in zip(random_state, np.random.get_state()):
        np.testing.assert_array_equal(old, new)
    for a, b in zip(first, second):
        np.testing.assert_array_equal(a, b)
        assert a.shape == (6,) and not a.flags.writeable
        assert np.all(a >= PHYSICAL_LOWER) and np.all(a <= PHYSICAL_UPPER)
        _, state = candidate_state(scaled_parameters(a))
        assert state.minimum_radius_lower_bound_m > 0
    expected_epsr = PHYSICAL_LOWER[5] + np.asarray([.25, .75])*(PHYSICAL_UPPER[5]-PHYSICAL_LOWER[5])
    generated_epsr = [candidate[5] for candidate in first[1:]]
    for value in expected_epsr:
        assert any(np.isclose(value, actual, atol=1e-14) for actual in generated_epsr)


@pytest.mark.parametrize("initial", [PHYSICAL_LOWER, PHYSICAL_UPPER, _initial()])
def test_fixed_shape_restarts_preserve_all_five_shape_controls_even_at_bounds(initial):
    candidates = robust.make_restart_candidates(initial, joint_shape=False)
    assert len({tuple(candidate) for candidate in candidates}) == len(candidates)
    for candidate in candidates:
        np.testing.assert_array_equal(candidate[:5], initial[:5])
        _, state = candidate_state(scaled_parameters(candidate))
        assert state.minimum_radius_lower_bound_m > .029


@pytest.mark.parametrize("initial", [np.full(6, np.nan), np.ones(5), PHYSICAL_LOWER-1e-3])
def test_invalid_initial_box_candidates_are_rejected_before_a_search(initial):
    with pytest.raises((ValueError, TypeError)):
        robust.make_restart_candidates(initial, joint_shape=True)


@pytest.mark.parametrize("kwargs", [
    {"policy": "unknown"}, {"maximum_forward_solves": -1},
    {"maximum_direction_evaluations": -1}, {"screening_keep": 0},
    {"nodes": 15}, {"stage_max_evaluations": ()},
])
def test_invalid_robust_configuration_is_rejected(kwargs):
    with pytest.raises((ValueError, TypeError)):
        robust.RobustMaterialConfig(**kwargs)


def test_global_budget_preserves_initial_full_band_audit_and_never_fabricates_stationarity():
    problem = _problem()
    observed = np.broadcast_to(problem.source_strengths, (problem.num_pairs, problem.num_frequencies)).copy()
    preserved_observations = observed.copy()
    preserved_strengths = problem.source_strengths.copy()
    config = robust.RobustMaterialConfig(policy="continuation", nodes=16,
        stage_max_evaluations=(1, 1), maximum_forward_solves=3, maximum_direction_evaluations=1)
    selected, report = robust.solve_robust_material(problem, observed, _initial(), config=config)
    assert selected is not None
    np.testing.assert_allclose(selected.physical, _initial(), rtol=0, atol=2e-15)
    assert selected.prediction.shape == observed.shape  # Never a low-band residual masquerading as full band.
    expected = (selected.prediction-preserved_observations)/np.linalg.norm(preserved_observations, axis=0)
    expected_real = np.r_[expected.real.ravel(), expected.imag.ravel()]
    np.testing.assert_allclose(selected.residual, expected_real, rtol=1e-14, atol=0)
    np.testing.assert_allclose(report["selected_training_loss"], .5*np.dot(expected_real, expected_real))
    assert report["work"]["forward_solves"] == 3
    assert report["work"]["analytic_direction_evaluations"] <= 1
    assert report["budget_exhausted"] is True
    assert report["search_completed"] is False
    assert report["verified_stationarity"] is False
    np.testing.assert_array_equal(observed, preserved_observations)
    np.testing.assert_array_equal(problem.source_strengths, preserved_strengths)
    assert not selected.residual.flags.writeable
    assert not selected.prediction.flags.writeable


def _observed(problem):
    return np.broadcast_to(problem.source_strengths, (problem.num_pairs, problem.num_frequencies)).copy()


def _toy_physics(monkeypatch):
    """Low-band minimum9.3 loses decisively to3.9 on the common full band."""
    forwards, directions = [], []
    def forward(curve, sources, receivers, omega, strength, **kwargs):
        epsr = kwargs["interior"].epsr
        factor, target = (1., 9.3) if omega < 2*np.pi*1e9 else (10., 3.9)
        forwards.append((float(omega), complex(strength), float(epsr)))
        return SimpleNamespace(
            system=SimpleNamespace(k_interior=complex(epsr), geometry=curve),
            scattered_receiver=np.full((len(sources), len(receivers)), strength*(1+factor*(epsr-target))),
            test_factor=factor, test_strength=strength,
        )
    def jvp(base, direction):
        directions.append(direction.interior_epsr)
        return SimpleNamespace(d_scattered_receiver=np.full_like(base.scattered_receiver,
            base.test_factor*base.test_strength*direction.interior_epsr))
    monkeypatch.setattr(material_core, "solve_kress_tmz_total_field_batch", forward)
    monkeypatch.setattr(robust, "linearize_kress_forward", jvp)
    return forwards, directions


def _unchanged_fake_fit(evaluator, initial_physical, **kwargs):
    value = evaluator.evaluate(scaled_parameters(initial_physical))
    return value, {"optimizer_success": True, "verified_stationarity": True,
                   "weighted_loss": .5*float(value.residual@value.residual)}


def test_full_band_ranking_overrides_low_band_winner_and_unverified_optimizer_claim(monkeypatch):
    forwards, directions = _toy_physics(monkeypatch)
    monkeypatch.setattr(robust, "fit_material_curve", _unchanged_fake_fit)
    problem = _problem((.5, 1.5))
    config = robust.RobustMaterialConfig(policy="multistart", nodes=16,
        stage_max_evaluations=(1, 1), maximum_forward_solves=100, maximum_direction_evaluations=100)
    selected, report = robust.solve_robust_material(problem, _observed(problem), _initial(), config=config)
    low_winner = min(report["screening"], key=lambda row: row["loss"])
    np.testing.assert_allclose(low_winner["physical"][5], 9.3)
    np.testing.assert_allclose(selected.physical[5], 3.9)
    np.testing.assert_allclose(report["selected_training_loss"], .5*(9.3-3.9)**2)
    assert report["selected_diagnostics"]["stationarity_evaluated"] is True
    assert report["verified_stationarity"] is False  # Every fake local fitter claimed True.
    assert report["selected_diagnostics"]["projected_gradient_inf"] > config.stationarity_tolerance
    assert report["work"]["forward_solves"] == len(forwards) == 11
    assert report["work"]["analytic_direction_evaluations"] == len(directions) == 2
    assert len(report["candidates"]) == 3
    assert report["selected_training_loss"] == min(row["training_loss"] for row in report["candidates"])
    for candidate in report["candidates"]:
        np.testing.assert_array_equal(candidate["physical"][:5], _initial()[:5])
    assert "recovered" not in report  # Stationarity is not a truth-based recovery certificate.
    assert set(report["phase_work"]) == {"initial_fullband_audit", "screening", "stages", "selected_stationarity_audit"}
    for key, value in report["work"].items():
        actual = sum(phase[key] for phase in report["phase_work"].values())
        if isinstance(value, float):
            assert actual == pytest.approx(value, abs=1e-12)
        else:
            assert actual == value


def test_stages_use_frozen_full_data_and_correct_frequency_strength_normalization(monkeypatch):
    _toy_physics(monkeypatch)
    problem = _problem()
    observed = _observed(problem)
    original = observed.copy()
    scales = np.linalg.norm(original, axis=0)
    seen = []
    def fit(evaluator, initial_physical, **kwargs):
        seen.append((evaluator.problem.angular_frequencies.copy(), evaluator.problem.source_strengths.copy(),
                     evaluator.observed.copy(), evaluator.frequency_scales.copy()))
        assert not evaluator.observed.flags.writeable
        assert not evaluator.frequency_scales.flags.writeable
        if len(seen) == 1:
            observed[:] *= 17  # Caller buffer changes cannot replace later-stage frozen data.
        return _unchanged_fake_fit(evaluator, initial_physical, **kwargs)
    monkeypatch.setattr(robust, "fit_material_curve", fit)
    config = robust.RobustMaterialConfig(policy="continuation", nodes=16, stage_max_evaluations=(1, 1))
    selected, report = robust.solve_robust_material(problem, observed, _initial(), config=config)
    schedule = robust.cumulative_frequency_indices(problem)
    assert len(seen) == len(schedule)
    for (frequency, strength, data, normalization), indices in zip(seen, schedule):
        np.testing.assert_array_equal(frequency, problem.angular_frequencies[list(indices)])
        np.testing.assert_array_equal(strength, problem.source_strengths[list(indices)])
        np.testing.assert_array_equal(data, original[:, list(indices)])
        np.testing.assert_array_equal(normalization, scales[list(indices)])
    expected_hash = hashlib.sha256(str((original.shape, original.dtype.str)).encode()+original.tobytes()).hexdigest()
    assert report["observation_sha256"] == expected_hash
    np.testing.assert_array_equal(report["frequency_normalization"], scales)
    expected = (selected.prediction-original)/scales
    np.testing.assert_allclose(selected.residual, np.r_[expected.real.ravel(), expected.imag.ravel()])


def test_failed_low_stage_cannot_mark_unattempted_full_stage_as_completed(monkeypatch):
    _toy_physics(monkeypatch)
    def failed_fit(*args, **kwargs):
        raise np.linalg.LinAlgError("controlled failed low-band path")
    monkeypatch.setattr(robust, "fit_material_curve", failed_fit)
    problem = _problem((.5, 1.5))
    selected, report = robust.solve_robust_material(problem, _observed(problem), _initial(),
        config=robust.RobustMaterialConfig(policy="continuation", nodes=16, stage_max_evaluations=(1, 1)))
    np.testing.assert_array_equal(selected.physical, _initial())
    assert len(report["stages"]) == 1 and report["stages"][0]["status"] == "numerical_failure"
    assert report["search_completed"] is False
    assert report["verified_stationarity"] is False


def test_failed_full_band_fit_retains_best_audited_trial_not_last_or_fabricated_success(monkeypatch):
    forwards, directions = _toy_physics(monkeypatch)
    def failed_fit(evaluator, initial_physical, **kwargs):
        better = np.asarray(initial_physical).copy(); better[5] = 3.9
        worse = np.asarray(initial_physical).copy(); worse[5] = 9.3
        evaluator.evaluate(scaled_parameters(better))
        evaluator.evaluate(scaled_parameters(worse))
        raise FloatingPointError("controlled terminal failure after useful valid trial")
    monkeypatch.setattr(robust, "fit_material_curve", failed_fit)
    problem = _problem((.5, 1.5))
    selected, report = robust.solve_robust_material(problem, _observed(problem), _initial(),
        config=robust.RobustMaterialConfig(policy="full_band", nodes=16, stage_max_evaluations=(1, 1),
                                          maximum_forward_solves=6))
    np.testing.assert_allclose(selected.physical[5], 3.9)
    assert report["stages"][0]["status"] == "numerical_failure"
    assert report["search_completed"] is False
    assert report["verified_stationarity"] is False
    assert report["work"]["forward_solves"] == len(forwards) == 6
    assert report["work"]["analytic_direction_evaluations"] == len(directions) == 2
    assert report["selected_diagnostics"]["stationarity_evaluated"] is True
    assert report["phase_work"]["selected_stationarity_audit"]["forward_solves"] == 0


def test_budgeted_evaluator_cache_costs_and_invalid_probe_accounting(monkeypatch):
    forwards, directions = _toy_physics(monkeypatch)
    problem = _problem((.5, 1.5))
    budget = robust._Budget(robust.RobustMaterialConfig(nodes=16,
        maximum_forward_solves=2, maximum_direction_evaluations=2))
    evaluator = robust._BudgetedEvaluator(problem, _observed(problem), budget=budget, nodes=16)
    scaled = scaled_parameters(_initial())
    first = evaluator.evaluate(scaled)
    jacobian = evaluator.jacobian(scaled, active_indices=(5,))
    assert evaluator.evaluate(scaled) is first
    np.testing.assert_array_equal(evaluator.jacobian(scaled, active_indices=(5,)), jacobian)
    assert budget.work["forward_solves"] == len(forwards) == 2
    assert budget.work["analytic_direction_evaluations"] == len(directions) == 2
    with pytest.raises(robust.BudgetExhausted):
        evaluator.jacobian(scaled, active_indices=(0,))
    assert budget.work["analytic_direction_evaluations"] == 2
    invalid = scaled.copy(); invalid[5] = -100
    with pytest.raises(ValueError, match="bounds"):
        evaluator.evaluate(invalid)
    assert budget.work["invalid_candidate_probes"] == 1
    assert evaluator.work["invalid_candidate_probes"] == 1


def test_partial_failed_forward_attempts_consume_exact_global_work(monkeypatch):
    _toy_physics(monkeypatch)
    original = material_core.solve_kress_tmz_total_field_batch
    attempts = []
    def fail_second(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 2:
            raise np.linalg.LinAlgError("second frequency failed")
        return original(*args, **kwargs)
    monkeypatch.setattr(material_core, "solve_kress_tmz_total_field_batch", fail_second)
    problem = _problem((.5, 1.5))
    budget = robust._Budget(robust.RobustMaterialConfig(nodes=16, maximum_forward_solves=3))
    evaluator = robust._BudgetedEvaluator(problem, _observed(problem), budget=budget, nodes=16)
    with pytest.raises(np.linalg.LinAlgError):
        evaluator.evaluate(scaled_parameters(_initial()))
    assert budget.work["forward_solves"] == len(attempts) == 2
    assert budget.work["failed_forward_solves"] == 1
    assert evaluator.best is None and evaluator._cached is None
    with pytest.raises(robust.BudgetExhausted):
        evaluator.evaluate(scaled_parameters(_initial()))
    assert len(attempts) == 2  # A whole new frequency batch cannot fit remaining budget.


def test_partial_derivative_failure_never_caches_a_zero_or_incomplete_column(monkeypatch):
    _toy_physics(monkeypatch)
    original = robust.linearize_kress_forward
    attempts = []
    def fail_second(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 2:
            raise FloatingPointError("second frequency JVP failed")
        return original(*args, **kwargs)
    monkeypatch.setattr(robust, "linearize_kress_forward", fail_second)
    problem = _problem((.5, 1.5))
    budget = robust._Budget(robust.RobustMaterialConfig(nodes=16,
        maximum_forward_solves=2, maximum_direction_evaluations=3))
    evaluator = robust._BudgetedEvaluator(problem, _observed(problem), budget=budget, nodes=16)
    with pytest.raises(FloatingPointError):
        evaluator.jacobian(scaled_parameters(_initial()), active_indices=(5,))
    assert budget.work["analytic_direction_evaluations"] == len(attempts) == 2
    assert budget.work["failed_direction_evaluations"] == 1
    assert 5 not in evaluator._jacobian_cache
    with pytest.raises(robust.BudgetExhausted):
        evaluator.jacobian(scaled_parameters(_initial()), active_indices=(5,))
    assert len(attempts) == 2


def test_signed_zero_cannot_bypass_byte_key_forward_budget(monkeypatch):
    forwards, _ = _toy_physics(monkeypatch)
    problem = _problem((.5, 1.5))
    budget = robust._Budget(robust.RobustMaterialConfig(nodes=16, maximum_forward_solves=2))
    evaluator = robust._BudgetedEvaluator(problem, _observed(problem), budget=budget, nodes=16)
    positive = scaled_parameters(_initial()); positive[3] = 0.0
    negative = positive.copy(); negative[3] = -0.0
    assert np.array_equal(positive, negative) and positive.tobytes() != negative.tobytes()
    first = evaluator.evaluate(positive)
    with pytest.raises(robust.BudgetExhausted):
        evaluator.evaluate(negative)
    assert budget.work["forward_solves"] == len(forwards) == 2
    assert evaluator.evaluate(positive) is first  # Previously paid exact cache hits remain usable.


@pytest.mark.parametrize("field,change", [
    ("observed", "reshape"), ("observed", "dtype"),
    ("frequency_scales", "reshape"), ("frequency_scales", "dtype"),
])
def test_immutable_identity_includes_shape_and_dtype_not_only_bytes(monkeypatch, field, change):
    forwards, _ = _toy_physics(monkeypatch)
    problem = _problem((.5, 1.5))
    budget = robust._Budget(robust.RobustMaterialConfig(nodes=16, maximum_forward_solves=2))
    evaluator = robust._BudgetedEvaluator(problem, _observed(problem), budget=budget, nodes=16)
    evaluator.evaluate(scaled_parameters(_initial()))
    original = getattr(evaluator, field)
    if change == "reshape":
        changed = original.reshape((1, original.size)) if original.ndim == 1 else original.reshape(-1)
    else:
        changed = original.view(np.float64 if field == "observed" else np.complex128)
    assert changed.tobytes() == original.tobytes()
    setattr(evaluator, field, changed)
    with pytest.raises(RuntimeError, match="shape or dtype"):
        evaluator.evaluate(scaled_parameters(_initial()))
    assert budget.work["forward_solves"] == len(forwards) == 2


def test_low_only_zero_loss_cannot_replace_audited_initial_when_full_band_budget_is_spent(monkeypatch):
    forwards, directions = _toy_physics(monkeypatch)
    def low_optimum(evaluator, initial_physical, **kwargs):
        physical = np.array(initial_physical); physical[5] = 9.3
        return _unchanged_fake_fit(evaluator, physical, **kwargs)
    monkeypatch.setattr(robust, "fit_material_curve", low_optimum)
    problem = _problem((.5, 1.5))
    selected, report = robust.solve_robust_material(problem, _observed(problem), _initial(),
        config=robust.RobustMaterialConfig(policy="continuation", nodes=16,
            stage_max_evaluations=(1, 1), maximum_forward_solves=3, maximum_direction_evaluations=20))
    assert report["stages"][0]["best_seen_stage_loss"] < 1e-25
    np.testing.assert_array_equal(selected.physical, _initial())
    assert len(report["candidates"]) == 1
    assert selected.prediction.shape == (problem.num_pairs, problem.num_frequencies)
    assert report["budget_exhausted"] is True and report["search_completed"] is False
    assert report["verified_stationarity"] is False
    assert report["work"]["forward_solves"] == len(forwards) == 3
    assert report["work"]["analytic_direction_evaluations"] == len(directions) == 2


def test_audited_candidate_pin_rejects_another_experiment_identity(monkeypatch):
    _toy_physics(monkeypatch)
    problem = _problem((.5, 1.5))
    budget = robust._Budget(robust.RobustMaterialConfig(nodes=16, maximum_forward_solves=4))
    evaluator = robust._BudgetedEvaluator(problem, _observed(problem), budget=budget, nodes=16)
    foreign = robust._BudgetedEvaluator(problem, 2*_observed(problem), budget=budget, nodes=16)
    candidate = foreign.evaluate(scaled_parameters(_initial()))
    with pytest.raises(ValueError, match="another experiment identity"):
        evaluator.pin_audited_candidate(candidate)
    assert evaluator._cached is None


def test_high_loss_true_bound_stationarity_is_not_labeled_physical_recovery(monkeypatch):
    _toy_physics(monkeypatch)
    def boundary_minimum(curve, sources, receivers, omega, strength, **kwargs):
        epsr = kwargs["interior"].epsr
        return SimpleNamespace(system=SimpleNamespace(k_interior=complex(epsr), geometry=curve),
            scattered_receiver=np.full((len(sources), len(receivers)), strength*(1+epsr-20)),
            test_factor=1., test_strength=strength)
    monkeypatch.setattr(material_core, "solve_kress_tmz_total_field_batch", boundary_minimum)
    monkeypatch.setattr(robust, "fit_material_curve", _unchanged_fake_fit)
    initial = _initial(); initial[5] = PHYSICAL_UPPER[5]
    problem = _problem((.5, 1.5))
    selected, report = robust.solve_robust_material(problem, _observed(problem), initial,
        config=robust.RobustMaterialConfig(policy="full_band", nodes=16, stage_max_evaluations=(1, 1)))
    assert report["verified_stationarity"] is True
    assert report["selected_training_loss"] > 1
    assert report["selected_diagnostics"]["near_upper_bounds"][5] is True
    assert "not physical recovery" in report["stationarity_contract"]
    assert "recovered" not in report and "recovery_success" not in report


def test_fixed_shape_non_binary_coefficient_roundtrip_is_allowed_without_geometry_drift(monkeypatch):
    _toy_physics(monkeypatch)
    monkeypatch.setattr(robust, "fit_material_curve", _unchanged_fake_fit)
    initial = _initial(); initial[4] = .0019043086815929682
    problem = _problem((.5, 1.5))
    selected, report = robust.solve_robust_material(problem, _observed(problem), initial,
        config=robust.RobustMaterialConfig(policy="full_band", nodes=16, stage_max_evaluations=(1, 1)))
    absolute_tolerance = 8*np.finfo(float).eps*np.maximum(1, np.abs(scaled_parameters(initial)[:5]))*PARAMETER_SCALES[:5]
    assert np.all(np.abs(selected.physical[:5]-initial[:5]) <= absolute_tolerance)
    direct = RadialFourierCurveState(initial[1:3], [initial[0], 0, initial[3]],
                                     [0, 0, initial[4]], "unscaled_initial")
    parameters = np.arange(32)*2*np.pi/32
    expected = radial_fourier_parameterization(direct).evaluate(parameters).points
    actual = radial_fourier_parameterization(selected.state).evaluate(parameters).points
    np.testing.assert_allclose(actual, expected, rtol=0, atol=2e-16)
    assert report["joint_shape"] is False


def test_fixed_shape_roundoff_tolerance_does_not_hide_a_real_selected_geometry_change(monkeypatch):
    _toy_physics(monkeypatch)
    def rogue_fit(evaluator, initial_physical, **kwargs):
        changed = np.array(initial_physical)
        changed[1] += 1e-4
        changed[5] = 3.9  # A lower full-band score makes this a selected candidate.
        return _unchanged_fake_fit(evaluator, changed, **kwargs)
    monkeypatch.setattr(robust, "fit_material_curve", rogue_fit)
    problem = _problem((.5, 1.5))
    with pytest.raises(RuntimeError, match="fixed-shape solve changed geometry"):
        robust.solve_robust_material(problem, _observed(problem), _initial(),
            config=robust.RobustMaterialConfig(policy="full_band", nodes=16, stage_max_evaluations=(1, 1)))


@pytest.mark.parametrize("initial_overflows", [False, True])
def test_finite_residual_loss_overflow_is_ineligible_json_safe_and_preserves_paid_incumbent(
        monkeypatch, initial_overflows):
    forwards, directions = _toy_physics(monkeypatch)
    original = material_core.solve_kress_tmz_total_field_batch
    overflowing_predictions = []

    def finite_but_unscorable(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs["interior"].epsr > 9:
            # Each prediction and normalized residual is finite. Only the
            # squared scalar objective overflows; no solver call has failed.
            result.scattered_receiver[:] = result.test_strength*1e195
            assert np.all(np.isfinite(result.scattered_receiver))
            overflowing_predictions.append(result.scattered_receiver.copy())
        return result

    def overflowing_trial(evaluator, initial_physical, **kwargs):
        trial = np.array(initial_physical)
        trial[5] = 9.3
        return _unchanged_fake_fit(evaluator, trial, **kwargs)

    monkeypatch.setattr(material_core, "solve_kress_tmz_total_field_batch", finite_but_unscorable)
    monkeypatch.setattr(robust, "fit_material_curve", overflowing_trial)
    initial = _initial()
    if initial_overflows:
        initial[5] = 9.3
    problem = _problem((.5, 1.5))
    observed = _observed(problem)
    with np.errstate(over="ignore"):
        selected, report = robust.solve_robust_material(problem, observed, initial,
            config=robust.RobustMaterialConfig(policy="full_band", nodes=16,
                stage_max_evaluations=(1, 1), maximum_forward_solves=4,
                maximum_direction_evaluations=2))
    assert overflowing_predictions
    for prediction in overflowing_predictions:
        assert np.all(np.isfinite(prediction/np.linalg.norm(observed[:, 0])))
    assert report["stages"][0]["status"] == "numerical_failure"
    assert report["stages"][0]["fit"] is None
    assert report["search_completed"] is False
    assert report["verified_stationarity"] is False
    history = report["stages"][0]["candidate_history"]
    assert len(history) == 1
    assert history[0]["loss"] is None
    assert history[0].get("failure_reason")
    assert "best_seen_physical" not in report["stages"][0]
    assert report["work"]["forward_solves"] == len(forwards) == 4
    assert report["work"]["failed_forward_solves"] == 0
    if initial_overflows:
        assert selected is None
        assert report["initial_audit_failure"]
        assert report["selected_training_loss"] is None
        assert report["candidates"] == []
        assert report["work"]["analytic_direction_evaluations"] == len(directions) == 0
    else:
        assert selected is not None
        np.testing.assert_array_equal(selected.physical, initial)
        assert np.isfinite(report["selected_training_loss"])
        assert len(report["candidates"]) == 1
        assert report["work"]["analytic_direction_evaluations"] == len(directions) == 2
        assert report["phase_work"]["selected_stationarity_audit"]["forward_solves"] == 0
    json.dumps(report, allow_nan=False)
