"""Small review reproducers, not inverse campaigns; leaves production code alone."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np

from experiments.shape_continuation.forward import Acquisition, Work, solve, shape_jacobian
from experiments.shape_continuation.geometry import FourierCurve, curvature_tail, displaced, gaussian_filter, normal_basis
from experiments.shape_continuation.inverse import FitConfig, Observation, fit_prepared, optimise_step, prepare_state, real_stack
from experiments.shape_continuation.metrics import area_error
from experiments.shape_continuation.schedule import Stage
from experiments.shape_continuation.test_pipeline import circle_series


OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
RUNS = OUTPUT.parent / "SC-013-paper-glider-recovery"


def warmup_probe():
    """Compare the same two updates in one chunk versus two one-update chunks."""
    work = Work(max_forwards=12, max_seconds=5)
    acquisition = Acquisition.ring(6, 7)
    observation = Observation(1., acquisition, circle_series(.8, 1., 1.44, acquisition))
    state = prepare_state(FourierCurve.circle(), observation,
        Stage(1., 3, 16, 64, 2), 1.44, work=work)
    config = FitConfig(max_iterations=2, steepest_descent_iterations=1,
                       residual_tolerance=1e-14, step_tolerance=1e-14)
    whole, report = fit_prepared(state, config=config, work=work)
    split, first = fit_prepared(state, config=replace(config, max_iterations=1), work=work)
    split, second = fit_prepared(split, config=replace(config, max_iterations=1), work=work)
    whole_directions = sorted({t["direction"] for t in report.trials if t["iteration"] == 2})
    split_directions = sorted({t["direction"] for t in second.trials})
    assert whole_directions == ["gauss_newton", "steepest_descent"]
    assert split_directions == ["steepest_descent"]
    return dict(whole_second_update_directions=whole_directions,
        split_second_update_directions=split_directions,
        whole_residual=whole.relative_residual, split_residual=split.relative_residual,
        coefficient_difference=float(np.linalg.norm(whole.shape.coefficients - split.shape.coefficients)),
        work=work.summary())


def filter_probe():
    """Hold physics fixed; finish the GN search skipped by the joint early exit.

    This isolates source-level control flow. It does not execute MATLAB or
    reproduce the reference's different quadrature/resampling implementation.
    """
    case = RUNS / "run-contrast-10/contrast_10"
    record = json.loads((case / "decision_000.json").read_text())
    with np.load(case / "observation_000.npz") as arrays:
        observation = Observation(1., Acquisition(arrays["directions"], arrays["receivers"]), arrays["scattered"])
    with np.load(case / "decision_000.npz") as arrays:
        initial = FourierCurve(arrays["state_0"])
    config, stage = FitConfig(**record["decision"]["config"]), Stage(**record["decision"]["stage"])
    work = Work(max_forwards=8, max_seconds=10)
    state = prepare_state(initial, observation, stage, 10., work=work)
    current = optimise_step(state, config=config, work=work)
    assert current.accepted and current.accepted_record["direction"] == "steepest_descent"
    assert current.accepted_record["filter_index"] == 0

    jacobian = shape_jacobian(state.forward, normal_basis(state.forward.curve, stage.update_modes), work=work)
    raw = real_stack(jacobian.reshape(-1, 2*stage.update_modes+1))
    rhs = real_stack((state.forward.prediction-observation.scattered).ravel())
    matrix, residual = raw / state.data_scale, rhs / state.data_scale
    direction = np.linalg.lstsq(matrix, -residual, rcond=config.rank_tolerance)[0]

    # Independently compare the reference raw Cauchy formula to normalized LS.
    raw_gradient, gradient = raw.T @ rhs, matrix.T @ residual
    raw_sd = -raw_gradient * np.dot(raw_gradient, raw_gradient) / np.linalg.norm(raw @ raw_gradient)**2
    normalized_sd = -gradient * (np.linalg.norm(gradient) / np.linalg.norm(matrix @ gradient))**2
    cauchy_error = float(np.linalg.norm(raw_sd-normalized_sd) / np.linalg.norm(raw_sd))
    assert cauchy_error < 1e-12

    trials, best_gn = [], None
    # Reference maxit_filter=10 evaluates the raw update and filter levels 1..9.
    for level in range(10):
        trial = dict(filter_index=level)
        trials.append(trial)
        try:
            proposal = displaced(initial, direction, stage.curve_modes,
                filter_index=level, projection_tolerance=config.projection_tolerance)
            tail = curvature_tail(proposal.shape, stage.curvature_modes)
            trial["curvature_tail"] = tail
            if tail > config.curvature_tail_tolerance:
                trial["status"] = "curvature_refused"
                continue
            forward = solve(proposal.shape, 1., 10., observation.acquisition, stage.nodes, work=work)
            trial["relative_residual"] = float(np.linalg.norm(forward.prediction-observation.scattered)/state.data_scale)
            trial["status"] = "decreasing" if trial["relative_residual"] < state.relative_residual else "nondecreasing"
            if trial["status"] == "decreasing":
                best_gn = trial
                break
        except (ValueError, FloatingPointError) as exc:
            trial.update(status="invalid", detail=str(exc))
    assert best_gn is not None and best_gn["relative_residual"] < current.state.relative_residual
    return dict(initial_residual=state.relative_residual,
        current_accepted=current.accepted_record, independent_gn_search=trials,
        reference_order_would_choose="gauss_newton", raw_vs_normalized_cauchy_relative_error=cauchy_error,
        work=work.summary())


def filter_formula_check():
    """Literal indexing from reference update_inverse_iterate.m, lines 324-332."""
    errors = []
    for band in (1, 3, 9):
        coefficients = np.arange(1, 2*band+2, dtype=float)
        for level in (1, 2, 3):
            sigma = 1. / 10**(level-1)
            grid = np.linspace(-1., 1., 2*band+1)
            values = np.exp(-grid*grid/sigma)
            reference = coefficients * np.r_[values[band:], values[band-1::-1]]
            error = np.max(np.abs(gaussian_filter(coefficients, level) - reference))
            errors.append(float(error))
    assert max(errors) < 1e-13
    return dict(cases=len(errors), maximum_absolute_difference=max(errors))


def saved_run_audit():
    reports = {}
    for label in ("0.33", "10"):
        case = RUNS / f"run-contrast-{label}" / f"contrast_{label}"
        manifest = json.loads((case / "manifest.json").read_text())
        mismatches = [name for name, digest in manifest["source_sha256"].items()
                      if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest]
        summary = json.loads((case / "summary.json").read_text())
        for record in summary["decisions"]:
            assert record["committed"] and record["qualification"]["passed"]
            checks = record["qualification"]["diagnostics"]
            assert max(checks["field_relative"], checks["jacobian_relative"]) <= checks["tolerance"]
            history = record["history"]
            assert all(b["relative_residual"] < a["relative_residual"] for a, b in zip(history, history[1:]))
        with np.load(case / "endpoint.npz") as arrays:
            final = FourierCurve(arrays["shape"])
        with np.load(case / "observation_000.npz") as arrays:
            truth = FourierCurve(arrays["truth"])
        saved = summary["decisions"][-1]["area_error"]
        rescored = area_error(truth, final, count=saved["coarse_samples"])
        assert rescored["relative_symmetric_difference"] == saved["relative_symmetric_difference"]
        reports[label] = dict(source_hash_mismatches=mismatches, area_error=rescored,
                             qualified_stages=len(summary["decisions"]))
    return reports


def area_convention_check():
    """Sensitivity to raw versus normalized area; not a claim about Fig.1 units."""
    # Exact polar integration: A = (1/2) integral r(theta)^2 dtheta.
    area = float(np.pi*.9**2*(1+.5*(.2**2+.02**2+.1**2+.1**2)))
    compared = json.loads((RUNS / "figure1_comparison.json").read_text())
    cases = {}
    for label, data in compared.items():
        raw_ratios = {k: v/area for k, v in data["ratio"].items()}
        cases[label] = dict(current_ratio_range=[min(data["ratio"].values()), max(data["ratio"].values())],
            ratio_range_if_published_values_are_raw_area=[min(raw_ratios.values()), max(raw_ratios.values())],
            ours_not_smaller_under_raw_area_interpretation=[k for k, v in raw_ratios.items() if v < 1])
    return dict(analytic_true_area=area, figure1_plotting_convention_verified=False, cases=cases)


if __name__ == "__main__":
    started = perf_counter()
    report = dict(reviewed_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        reference_commit="bda24bddbf4562497280b671bc174ef891b47c6b",
        filter_formula=filter_formula_check(), warmup=warmup_probe(),
        independent_filter_search=filter_probe(), saved_runs=saved_run_audit(),
        area_convention=area_convention_check())
    report["elapsed_seconds"] = perf_counter()-started
    (OUTPUT / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
