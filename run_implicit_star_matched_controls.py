#!/usr/bin/env python3
"""Phase A: paired-12/paired-8 analytic-star controls using existing FD-GN.

The wrappers below only observe the production evaluator and Jacobian calls.
They do not supply an optimizer, modify candidates, or evaluate holdout data
until the complete accepted training trajectory has been fixed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shlex
import sys
from time import perf_counter
from unittest.mock import patch

import numpy as np

import run_sdf_inverse_comparison as driver
from sdf_inverse import optimization
from sdf_inverse.nystrom_oracle import nystrom_self_convergence


DEFAULT_OUTPUT = Path(
    "results/validation/implicit_mlp_adjoint/latest-direction-20260908/phase_a"
)


def write_json(path, value):
    path.write_text(json.dumps(driver._jsonable(value), indent=2, allow_nan=False) + "\n")


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class TrainingAudit:
    """Identify actual line-search trials separately from FD probes/cache hits."""

    def __init__(self):
        self.in_jacobian = False
        self.accepted_loss = None
        self.accepted_parameters = None
        self.accepted_iteration = 0
        self.trials = []
        self.progress = []
        self.started = perf_counter()
        self.original_evaluate = optimization._ObjectiveEvaluator.evaluate
        self.original_jacobian = optimization._finite_difference_jacobian

    def evaluate(self, evaluator, parameters):
        before_count = evaluator.evaluation_count
        result = self.original_evaluate(evaluator, parameters)
        if self.in_jacobian:
            return result
        if self.accepted_loss is None:
            self.accepted_loss = result.loss
            self.accepted_parameters = np.array(result.parameters, copy=True)
            return result
        # _make_iteration_record restores the accepted parameters through the
        # evaluator outside the Jacobian wrapper; this is also a cache hit.
        if np.array_equal(result.parameters, self.accepted_parameters):
            return result
        accepted = result.loss < self.accepted_loss
        self.trials.append({
            "trial": len(self.trials) + 1,
            "proposed_iteration": self.accepted_iteration + 1,
            "loss": result.loss,
            "previous_accepted_loss": self.accepted_loss,
            "accepted": accepted,
            "rejection_reason": "" if accepted else (
                "extraction/topology" if not result.feasible else "data_not_decreased"
            ),
            "new_forward_evaluations": evaluator.evaluation_count - before_count,
            "cumulative_forward_evaluations": evaluator.evaluation_count,
            "elapsed_seconds": perf_counter() - self.started,
            **evaluator.controller.physical_parameter_dict(),
        })
        if accepted:
            self.accepted_loss = result.loss
            self.accepted_parameters = np.array(result.parameters, copy=True)
        return result

    def jacobian(self, *args, **kwargs):
        self.in_jacobian = True
        try:
            return self.original_jacobian(*args, **kwargs)
        finally:
            self.in_jacobian = False

    def callback(self, record):
        self.accepted_iteration = record.iteration
        self.progress.append({
            "wall_seconds": perf_counter() - self.started,
            "accepted_trials": sum(row["accepted"] for row in self.trials),
            "rejected_trials": sum(not row["accepted"] for row in self.trials),
        })
        print(f"  accepted {record.iteration}: train={record.relative_l2_error:.6g}", flush=True)

    def run(self, model, controller, data, geometry, config):
        # Patching is confined to this single-process diagnostic. Both wrappers
        # return the exact production result and are restored even on failure.
        with patch.object(
            optimization._ObjectiveEvaluator, "evaluate",
            lambda evaluator, parameters: self.evaluate(evaluator, parameters),
        ), patch.object(optimization, "_finite_difference_jacobian", self.jacobian):
            return optimization.run_parameter_fd_inverse(
                model, controller, data, geometry, solver="kress", config=config,
                progress_callback=self.callback,
            )


def run_arm(pairs, output, target):
    print(f"[paired-{pairs}] independent observations and oracle refinement", flush=True)
    started = perf_counter()
    sources, receivers = driver._ring_scan(center=target.center, standoff=0.30, num_pairs=pairs)
    train_problem = driver._build_problem((0.5, 1.5), sources, receivers)
    holdout_problem = driver._build_problem((3.0,), sources, receivers)
    oracle_validation = nystrom_self_convergence(
        holdout_problem, target.shape.parameterization(),
        coarse_num_nodes=512, num_nodes=1024, curve_name="target-star",
    )
    if oracle_validation["maximum_relative_difference"] > 1.0e-8:
        raise RuntimeError("Reserved 3 GHz holdout oracle fails 512/1024-node refinement.")
    training_oracle_validation = target.oracle_diagnostics(train_problem)
    if training_oracle_validation["maximum_relative_difference"] > 1.0e-8:
        raise RuntimeError("Training oracle fails its historical 256/512-node refinement.")
    train_truth = target.observations(train_problem)
    holdout_truth = target.observations(holdout_problem)
    data = driver.ComplexScatteredData(train_problem, train_truth)
    model, controller = driver._build_initial_model("star")
    geometry = target.geometry_config(target.default_num_nodes)
    config = driver._inverse_config_for_controller(
        controller, max_iterations=target.default_max_iterations,
    )
    audit = TrainingAudit()
    result = audit.run(model, controller, data, geometry, config)
    inverse_finished = perf_counter()
    assert sum(row["accepted"] for row in audit.trials) == len(result.iterations) - 1
    assert audit.accepted_loss == result.final_iteration.loss
    assert np.array_equal(controller.parameter_vector(), result.final_iteration.parameter_vector)

    # Evaluation-only pass: holdout cannot influence the accepted trajectory,
    # stopping settings, damping, or trial choices.
    rows = []
    holdout_predictions = []
    assert len(result.iterations) == len(audit.progress)
    for record, progress in zip(result.iterations, audit.progress):
        controller.assign(record.parameter_vector)
        forward = driver.predict_paired_response(model, holdout_problem, geometry, solver="kress")
        assert np.array_equal(forward.geometry_build.curve.points, record.geometry_points)
        holdout_predictions.append(forward.scattered_response)
        _, holdout_relative = driver._objective_metrics(forward.scattered_response, holdout_truth)
        errors = target.shape_errors(record.physical_parameters, record.geometry_points)
        distances = target.curve_distance_metrics(record.geometry_points)
        rows.append({
            "iteration": record.iteration,
            "training_loss": record.loss,
            "training_relative_l2": record.relative_l2_error,
            "holdout_relative_l2": holdout_relative,
            **dict(record.physical_parameters),
            "center_error_m": errors["final_center_error_m"],
            "mean_radius_error_m": errors["final_radius_error_m"],
            "amplitude_error": errors["final_amplitude_error"],
            "rotation_error_radians": errors["final_rotation_error_radians"],
            **distances,
            "forward_evaluations": record.evaluation_count,
            **progress,
        })
    controller.assign(result.final_iteration.parameter_vector)
    final = rows[-1]
    gates = {
        "center_error": final["center_error_m"] <= 5e-4,
        "mean_radius_error": final["mean_radius_error_m"] <= 1e-3,
        "amplitude_error": final["amplitude_error"] <= 2e-2,
        "rotation_error": final["rotation_error_radians"] <= 2e-2,
        "maximum_node_boundary_error": final["maximum_node_to_exact_boundary_distance_m"] <= 1e-3,
        "training_relative_l2": final["training_relative_l2"] <= 1e-3,
        "holdout_relative_l2": final["holdout_relative_l2"] <= 1e-3,
    }
    metrics = {
        "acquisition": f"paired-{pairs}", "num_sources": pairs, "num_receivers": pairs,
        "training_frequencies_ghz": [0.5, 1.5], "holdout_frequencies_ghz": [3.0],
        "source_points": sources, "receiver_points": receivers,
        "target": target.parameter_dict(), "initial_parameters": rows[0],
        "exterior_material": asdict(train_problem.exterior),
        "interior_material": asdict(train_problem.interior),
        "source_strengths_real": train_problem.source_strengths.real,
        "geometry_config": asdict(geometry), "optimizer_config": asdict(config),
        "optimizer": "existing bounded central-FD damped Gauss-Newton",
        "stop_reason": result.stop_reason, "optimizer_converged": result.converged,
        "accepted_updates": len(result.iterations) - 1,
        "rejected_trials": sum(not trial["accepted"] for trial in audit.trials),
        "rejection_reason_counts": dict(Counter(
            trial["rejection_reason"] for trial in audit.trials if not trial["accepted"]
        )),
        "inverse_forward_evaluations": result.total_evaluation_count,
        "inverse_cache_hits": result.cache_hit_count,
        "posthoc_holdout_forward_evaluations": len(rows),
        "inverse_seconds": result.total_seconds,
        "oracle_and_inverse_seconds": inverse_finished - started,
        "total_arm_seconds": perf_counter() - started,
        "maximum_system_residual": result.maximum_system_residual,
        "training_oracle_validation": training_oracle_validation,
        "holdout_oracle_validation": oracle_validation,
        "recovery_gates": gates, "recovery_passed": all(gates.values()),
        "final": final, "accepted_iterates": rows,
    }
    arm_dir = output / f"paired-{pairs}"
    arm_dir.mkdir(parents=True, exist_ok=True)
    write_json(arm_dir / "metrics.json", metrics)
    write_csv(arm_dir / "trajectory.csv", rows)
    write_csv(arm_dir / "trials.csv", audit.trials)
    np.savez_compressed(arm_dir / "responses.npz", training_observed=train_truth,
                        holdout_observed=holdout_truth,
                        holdout_predictions=np.stack(holdout_predictions),
                        parameter_vectors=np.stack([r.parameter_vector for r in result.iterations]))
    print(f"[paired-{pairs}] {result.stop_reason}, recovery={all(gates.values())}", flush=True)
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if (output / "metrics.json").exists() and not args.overwrite:
        parser.error("Result metrics already exist; use --overwrite to rerun this result bundle.")
    output.mkdir(parents=True, exist_ok=True)
    command = "OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers " + shlex.join([sys.executable, *sys.argv])
    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": driver._git_provenance(), "python": platform.python_version(),
        "random_seed": None, "initialization": "deterministic analytic five-parameter star",
        "thread_environment": driver._thread_provenance(), "command": command,
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__).resolve(),
                driver.REPOSITORY_ROOT / "run_sdf_inverse_comparison.py",
                driver.REPOSITORY_ROOT / "solvers/sdf_inverse/optimization.py",
                driver.REPOSITORY_ROOT / "solvers/sdf_inverse/forward.py",
                driver.REPOSITORY_ROOT / "solvers/sdf_inverse/geometry.py",
                driver.REPOSITORY_ROOT / "solvers/sdf_inverse/models.py",
                driver.REPOSITORY_ROOT / "solvers/sdf_inverse/nystrom_oracle.py",
            )
        },
    }
    write_json(output / "provenance.json", provenance)
    (output / "commands.txt").write_text(command + "\n")
    target = driver.StarTarget()
    arms = {f"paired-{pairs}": run_arm(pairs, output, target) for pairs in (12, 8)}
    assert arms["paired-12"]["geometry_config"] == arms["paired-8"]["geometry_config"]
    # Config arrays are JSON-normalized before comparing for exact matching.
    assert driver._jsonable(arms["paired-12"]["optimizer_config"]) == driver._jsonable(arms["paired-8"]["optimizer_config"])
    write_json(output / "metrics.json", {"arms": arms, "matched_settings_verified": True})
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.6), constrained_layout=True)
    for name, arm in arms.items():
        trajectory = arm["accepted_iterates"]
        iterations = [row["iteration"] for row in trajectory]
        axes[0].plot(iterations, [row["amplitude"] for row in trajectory], marker=".", label=name)
        axes[1].plot(iterations, [row["rotation_radians"] for row in trajectory], marker=".")
        axes[2].semilogy(iterations, [1e3*row["maximum_node_to_exact_boundary_distance_m"] for row in trajectory], marker=".")
    axes[0].axhline(target.shape.amplitude, color="black", linestyle="--", label="target")
    axes[1].axhline(target.shape.rotation_radians, color="black", linestyle="--")
    for axis, label in zip(axes, ("Lobe amplitude", "Rotation (rad)", "Max node-to-target error (mm)")):
        axis.set(xlabel="Accepted iteration", ylabel=label)
        axis.grid(alpha=0.25)
    axes[0].legend()
    figure.savefig(output / "matched_trajectories.png", dpi=160)
    plt.close(figure)
    if arms["paired-8"]["recovery_passed"]:
        decision = "Eight paired views recover the star inside its five-parameter family at 0.5/1.5 GHz. Reducing 12 to 8 pairs does not explain the neural failure by itself. Physical and general-boundary modal observability remain necessary before claiming sufficiency for the neural inverse."
    elif arms["paired-12"]["recovery_passed"]:
        decision = "The 12-pair control succeeds while the 8-pair control fails the declared recovery gates. Angular acquisition matters even inside the five-parameter family; all three planned acquisition arms remain necessary."
    else:
        decision = "The historical recovery is not reproduced under this run's declared gates; inspect the matched-control evidence before drawing conclusions about the neural acquisition."
    table = []
    for name, arm in arms.items():
        final = arm["final"]
        table.append(f"| {name} | {final['training_relative_l2']:.3e} | {final['holdout_relative_l2']:.3e} | {1e3*final['maximum_node_to_exact_boundary_distance_m']:.5f} | {final['amplitude_error']:.3e} | {final['rotation_error_radians']:.3e} | {arm['accepted_updates']} / {arm['rejected_trials']} | {arm['inverse_forward_evaluations']} | {arm['inverse_seconds']:.2f} | {arm['stop_reason']} |")
    readme = f"""# Phase A: matched five-parameter star controls

Commit: `{provenance['git']['commit']}`. The source hashes and working-tree state at launch are in `provenance.json`.

Both arms use the existing analytic wrong star, target and materials from `run_sdf_inverse_comparison.py`. Paired readout observes receiver row i only for source row i; there are respectively 12/12 and 8/8 sources/receivers on a 0.30 m ring with the existing Tx/Rx offset. Independent Nystrom observations use 512 nodes. Training is {{0.5,1.5}} GHz. The common holdout is {{3.0}} GHz only: 0.25 GHz is excluded because the planned frequency audit probes it. Each arm verifies 512/1024-node oracle self-convergence at 3 GHz against 1e-8 before proceeding.

Both use the historical analytic-control Method-B settings unchanged: 128 Kress nodes, Fourier bandwidth 48, 257 x 257 extraction grid, 128 projected samples, arc-length dense resolution 2048, validation resolution 1024. These are the analytic-control settings, distinct from the neural bandwidth-96 study. Maximum boundary error below is the existing maximum **node-to-exact-target** distance; it is a sampled one-direction metric, not a continuous Hausdorff certificate.

The optimizer is the existing bounded central-FD damped Gauss-Newton implementation, with the same 14-update maximum, 6 damping trials, 8 backtracks, steps and stopping tolerances in both arms. No optimizer implementation or tolerance is changed. Its post-repair truthful `no_decreasing_step` stopping label can differ from the historical falsely converged small-rejected-step label. Recovery and optimizer termination are reported separately.

| Acquisition | Train rel. L2 | Holdout rel. L2 | Max boundary (mm) | Amplitude error | Rotation error (rad) | Accepted / rejected | Inverse forwards | Inverse seconds | Stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(table)}

`trajectory.csv` in each arm reports every accepted iterate, physical errors, training/holdout performance, cumulative accepted/rejected trials, forward evaluations and elapsed inverse wall time. `trials.csv` records every evaluated line-search candidate and rejection reason. Finite-difference probes and restoration cache hits are not mislabeled as rejected trials. Holdout is evaluated only in a separate pass after training finishes; its forwards and wall time are reported separately. Skipped proposals below the existing relative-step floor do not execute a forward and are not included in evaluated trial counts. Rejection counts by reason: {json.dumps({name: arm['rejection_reason_counts'] for name, arm in arms.items()})}.

Recovery gates retain the historical geometry/holdout allowances (center 0.5 mm, radius and node boundary error 1 mm, amplitude/rotation 0.02, holdout relative L2 1e-3), plus train relative L2 1e-3. Outcomes: {json.dumps({name: arm['recovery_passed'] for name, arm in arms.items()})}.

{decision}

This does not establish sufficiency for arbitrary neural boundaries, explain the neural basin, or select the acquisition for a full neural run. The 3 GHz holdout is never used for tuning, line search or frequency/acquisition selection. Timings are single-run engineering measurements. `matched_trajectories.png` shows amplitude, phase and boundary error through the two accepted trajectories.

Reproduce with the exact command in `commands.txt` from the repository root.
"""
    (output / "README.md").write_text(readme)
    return 0 if all(arm["recovery_passed"] for arm in arms.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
