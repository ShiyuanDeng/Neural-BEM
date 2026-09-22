"""Step/controller contracts, including real solves and rejected handoffs."""
from dataclasses import replace

import numpy as np
import pytest

from .continuation import Decision, FixedSchedule, Qualification, ResolutionGate, run_adaptive
from .forward import Acquisition, Work, solve
from .geometry import FourierCurve, gaussian_filter, reparameterize
from .inverse import FitConfig, Observation, fit_frequency, fit_prepared, optimise_step, prepare_state
from .schedule import Stage
from .test_pipeline import circle_series


def problem(k=1.):
    acquisition = Acquisition.ring(6, 7)
    observation = Observation(k, acquisition, circle_series(.8, k, 1.44, acquisition))
    return FourierCurve.circle(), observation, Stage(k, 3, 16, 64, 2)


def counters(work):
    return {key: value for key, value in work.summary().items() if key != "seconds"}


def test_policy_retuning_reuses_exact_physics_and_new_data_reuses_prediction():
    shape, observation, stage = problem()
    work = Work()
    first = prepare_state(shape, observation, stage, 1.44, work=work)
    assert prepare_state(first.shape, observation, stage, 1.44, cached=first, work=work) is first
    retuned = prepare_state(first.shape, observation,
        replace(stage, update_modes=5, curvature_modes=4, curve_modes=24), 1.44, cached=first, work=work)
    assert retuned.forward is first.forward
    assert retuned.forward.factors is first.forward.factors
    assert work.attempted == work.factorizations == 1
    independent = solve(retuned.shape, 1., 1.44, observation.acquisition, stage.nodes)
    assert np.array_equal(independent.prediction, retuned.forward.prediction)
    changed_data = replace(observation, scattered=2 * observation.scattered)
    updated = prepare_state(retuned.shape, changed_data, retuned.stage, 1.44, cached=retuned, work=work)
    assert updated.forward is first.forward and work.attempted == 1
    expected = np.linalg.norm(first.forward.prediction - changed_data.scattered) / np.linalg.norm(changed_data.scattered)
    assert updated.relative_residual == expected != retuned.relative_residual
    with pytest.raises(ValueError, match="discard"):
        prepare_state(retuned.shape, observation, stage, 1.44, cached=retuned, work=work)


@pytest.mark.parametrize("change", ["geometry", "frequency", "nodes", "contrast", "directions", "receivers"])
def test_physical_changes_invalidate_cache(change):
    shape, observation, stage = problem()
    work = Work()
    first = prepare_state(shape, observation, stage, 1.44, work=work)
    shape, contrast = first.shape, 1.44
    if change == "geometry":
        shape = FourierCurve.circle(.95)
    elif change == "frequency":
        stage, observation = replace(stage, wavenumber=1.25), replace(observation, wavenumber=1.25)
    elif change == "nodes":
        stage = replace(stage, nodes=96)
    elif change == "contrast":
        contrast = 1.6
    else:
        acquisition = observation.acquisition
        if change == "directions":
            acquisition = replace(acquisition, directions=np.roll(acquisition.directions, 1, axis=0))
        else:
            acquisition = replace(acquisition, receivers=1.1 * acquisition.receivers)
        observation = replace(observation, acquisition=acquisition)
    updated = prepare_state(shape, observation, stage, contrast, cached=first, work=work)
    independent = prepare_state(shape, observation, stage, contrast)
    assert updated.forward is not first.forward
    assert work.attempted == work.factorizations == 2
    assert np.array_equal(updated.forward.prediction, independent.forward.prediction)


def test_manual_steps_reproduce_whole_fit_without_repeated_initial_solves():
    shape, observation, stage = problem()
    config = FitConfig(max_iterations=12)
    whole_work, step_work = Work(), Work()
    whole = fit_frequency(shape, observation, stage, 1.44, config=config, work=whole_work)
    state = prepare_state(shape, observation, stage, 1.44, work=step_work)
    states, trials = [state.shape], []
    for iteration in range(1, config.max_iterations + 1):
        step = optimise_step(state, config=config, work=step_work, iteration=iteration)
        state = step.state
        trials.extend(step.trials)
        if step.accepted:
            states.append(state.shape)
        if step.stop_reason is not None:
            break
    assert step.stop_reason == whole.stop_reason == "data_fit"
    assert step.diagnostics.keys() == {"gradient_inf", "jacobian_rank",
                                       "singular_values", "base_curvature_tail"}
    assert state.relative_residual == whole.relative_residual
    assert trials == whole.trials
    assert len(states) == len(whole.states)
    assert all(np.array_equal(a.coefficients, b.coefficients) for a, b in zip(states, whole.states))
    assert counters(step_work) == counters(whole_work)


def test_strategy_repeats_frequency_changes_modes_then_advances_with_full_history():
    shape, observation, stage = problem()
    other = problem(1.25)[1]
    chunk = FitConfig(max_iterations=1)
    seen, saved = [], []
    def strategy(context):
        seen.append(context)
        index = len(context.history)
        if index == 0:
            return Decision(replace(stage, update_modes=1), chunk, "start with low harmonics")
        if index == 1:
            assert context.history[0].result.trials
            assert context.history[0].result.history[0]["jacobian_rank"] == 3
            return Decision(stage, chunk, "increase harmonics at the same frequency")
        if index == 2:
            return Decision(replace(stage, wavenumber=1.25), chunk, "advance frequency")
        return None
    work = Work()
    result = run_adaptive(shape, [other, observation], 1.44, strategy, work=work, on_decision=saved.append)
    assert result.stop_reason == "policy_stop"
    assert len(result.history) == 3 and len(seen[-1].history) == 3
    assert seen[0].available_wavenumbers == (1., 1.25)
    assert all(record.committed for record in result.history)
    assert all(saved[i] is record for i, record in enumerate(result.history))
    # 2 frequency setups, not 3 decisions; every accepted trial already has a solve.
    assert work.factorizations == work.attempted == 2 + sum(
        "relative_residual" in trial for record in result.history for trial in record.result.trials)
    assert not any(hasattr(record, "forward") or hasattr(record.result, "forward") for record in result.history)


def test_failed_qualification_rolls_back_curve_and_reuses_previous_live_cache():
    shape, observation, stage = problem()
    configs = [FitConfig(max_iterations=1), FitConfig(max_iterations=1), FitConfig(max_iterations=0)]
    inspected, contexts = [], []
    def strategy(context):
        contexts.append(context)
        i = len(context.history)
        return Decision(stage, configs[i], "rollback control") if i < 3 else None
    def gate(state, work):
        inspected.append(state)
        return Qualification(len(inspected) != 2, {"check": len(inspected)})
    result = run_adaptive(shape, [observation], 1.44, strategy, qualify=gate)
    first, rejected, repeated = result.history
    assert first.committed and not rejected.committed and repeated.committed
    assert not rejected.qualification.passed
    assert contexts[2].shape is first.result.shape is result.shape
    assert rejected.result.relative_residual < first.result.relative_residual
    assert inspected[0].forward is inspected[2].forward
    assert repeated.work_after["attempted"] == repeated.work_before["attempted"]


@pytest.mark.parametrize("budget", [1, 3])
def test_unqualified_progress_is_not_committed_on_budget_exhaustion(budget):
    shape, observation, stage = problem()
    result = run_adaptive(shape, [observation], 1.44,
        FixedSchedule((stage,), FitConfig(max_iterations=1)),
        work=Work(max_forwards=budget), qualify=ResolutionGate())
    assert result.stop_reason == "budget_exhausted"
    record = result.history[0]
    assert not record.committed and not record.qualification.passed
    assert np.max(abs(result.shape.values(128) - shape.values(128))) < 1e-13
    assert record.work_after["attempted"] == budget
    if budget == 3:
        assert len(record.result.states) == 2  # Candidate is retained in the rejected report.
        assert record.result.shape is not result.shape


def test_shared_budget_and_decision_limit_stop_repeated_policies():
    shape, observation, stage = problem()
    result = run_adaptive(shape, [observation], 1.44,
        lambda context: Decision(stage, FitConfig(max_iterations=1)), work=Work(max_forwards=4))
    assert result.stop_reason == "budget_exhausted"
    assert len(result.history) == 2 and result.history[-1].work_after["attempted"] == 4
    assert result.shape is result.history[0].result.shape  # Second decision accepted no update.
    limited = run_adaptive(shape, [observation], 1.44,
        lambda context: Decision(stage, FitConfig(max_iterations=0)), max_decisions=3)
    assert limited.stop_reason == "decision_limit" and len(limited.history) == 3
    assert limited.history[-1].work_after["attempted"] == 1


def test_controller_validates_catalog_and_can_revisit_frequencies():
    shape, observation, stage = problem()
    with pytest.raises(ValueError, match="unique"):
        run_adaptive(shape, [observation, observation], 1.44, lambda context: None)
    with pytest.raises(ValueError, match="without an observation"):
        run_adaptive(shape, [observation], 1.44, FixedSchedule((replace(stage, wavenumber=2.),)))
    other = problem(1.25)[1]
    result = run_adaptive(shape, [observation, other], 1.44,
        FixedSchedule((stage, replace(stage, wavenumber=1.25), stage), FitConfig(max_iterations=0)))
    assert result.stop_reason == "policy_stop" and len(result.history) == 3
    assert result.history[-1].work_after["attempted"] == 3


def test_resolution_gate_reuses_coarse_solve_and_checks_jacobian():
    shape, observation, stage = problem()
    work = Work()
    state = prepare_state(shape, observation, stage, 1.44, work=work)
    check = ResolutionGate()(state, work)
    assert check.passed and work.attempted == 2 and work.jacobians == 2
    # A converged field alone is insufficient, as in the existing derivative control.
    from .run import fixture
    glider = fixture("glider")
    stage = Stage(8., 28, 48, 128, 16)
    observation = Observation(8., observation.acquisition, observation.scattered)
    state = prepare_state(glider, observation, stage, 1.44)
    check = ResolutionGate()(state, Work())
    assert not check.passed
    assert check.diagnostics["field_relative"] < 1e-6 < check.diagnostics["jacobian_relative"]


def test_direction_policy_does_not_depend_on_how_updates_are_chunked():
    """A per-frequency iteration counter would make these two paths differ."""
    shape, observation, stage = problem()
    config = FitConfig(max_iterations=2, directions=("steepest_descent",),
                       residual_tolerance=1e-14, step_tolerance=1e-14)
    whole_work, split_work = Work(), Work()
    state = prepare_state(shape, observation, stage, 1.44, work=whole_work)
    whole, report = fit_prepared(state, config=config, work=whole_work)
    split = prepare_state(shape, observation, stage, 1.44, work=split_work)
    single = replace(config, max_iterations=1)
    trials = []
    for _ in range(2):
        split, chunk = fit_prepared(split, config=single, work=split_work)
        trials.extend(chunk.trials)
    assert {t["direction"] for t in report.trials} == {"steepest_descent"}
    assert [t["direction"] for t in trials] == [t["direction"] for t in report.trials]
    assert np.array_equal(whole.shape.coefficients, split.shape.coefficients)
    assert counters(whole_work) == counters(split_work)


def test_each_direction_is_filtered_to_admissibility_independently(monkeypatch):
    """The reference compares survivors; it does not stop at the first success.

    Gauss-Newton is searched first, so the first distinct coefficient vector
    reaching `displaced` is its proposal. Refusing that one at weak filters
    leaves steepest descent succeeding immediately at level 0; the joint search
    this replaced would have stopped there and never revisited Gauss-Newton.
    """
    from . import inverse
    real, seen = inverse.displaced, []

    def refuse_weak_gauss_newton(curve, coefficients, *args, **kwargs):
        key = id(coefficients)
        if key not in seen:
            seen.append(key)
        if seen.index(key) == 0 and kwargs["filter_index"] < 2:
            raise ValueError("Controlled rejection of a weakly filtered proposal.")
        return real(curve, coefficients, *args, **kwargs)

    monkeypatch.setattr(inverse, "displaced", refuse_weak_gauss_newton)
    shape, observation, stage = problem()
    work = Work()
    state = prepare_state(shape, observation, stage, 1.44, work=work)
    step = optimise_step(state, config=FitConfig(backtracks=0), work=work)
    assert step.accepted
    attempted = {}
    for trial in step.trials:
        attempted.setdefault(trial["direction"], []).append(trial["filter_index"])
    assert attempted["steepest_descent"] == [0]        # succeeded straight away
    assert attempted["gauss_newton"] == [0, 1, 2]      # still searched past it
    assert [t["status"] for t in step.trials if t["direction"] == "gauss_newton"][:2] \
        == ["invalid", "invalid"]


def test_filter_sweep_stops_once_the_update_stops_changing():
    """Saturated Gaussian levels rebuild an identical candidate; skip them."""
    coefficients = np.arange(1., 8.)
    saturated = [level for level in range(11)
                 if np.array_equal(gaussian_filter(coefficients, level),
                                   gaussian_filter(coefficients, level + 1))]
    assert saturated, "the filter must saturate within the configured levels"
    shape, observation, stage = problem()
    work = Work()
    state = prepare_state(shape, observation, stage, 1.44, work=work)
    # Refuse every proposal so both directions sweep to the end of the search.
    from . import inverse
    real = inverse.displaced
    try:
        inverse.optimise_step.__globals__["displaced"] = \
            lambda *a, **k: (_ for _ in ()).throw(ValueError("refused"))
        step = optimise_step(state, config=FitConfig(backtracks=0), work=work)
    finally:
        inverse.optimise_step.__globals__["displaced"] = real
    assert step.stop_reason == "no_acceptable_step"
    levels = [t["filter_index"] for t in step.trials if t["direction"] == "gauss_newton"]
    assert levels == list(range(len(levels)))
    assert max(levels) <= saturated[0] + 1 < 10   # stopped early, not at filter_steps
