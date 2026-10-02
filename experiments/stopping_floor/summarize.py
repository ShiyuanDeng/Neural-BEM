"""Summarize already frozen stopping-floor prefixes; performs no fitting."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ARMS = (("", "FD 64"), ("refined_control", "FD 128"),
        ("analytic_control", "Analytic 128, reference geometry"),
        ("analytic_fast", "Analytic 128, accelerated geometry"))


def read(path):
    return json.loads(path.read_text())


def trajectory(root):
    # Chunk-start rows repeat their preceding endpoint and contain zero steps.
    rows = [json.loads(line) for line in (root / "stage_0/trajectory.jsonl").read_text().splitlines()]
    return {row["global_iteration"]: row for row in rows}


def parameters(row):
    return np.concatenate([c["parameters"] for c in row["state"]])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/stopping-floor-20261002"))
    args = parser.parse_args()
    root = args.output
    curves, summary = {}, []
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    work_lower = 0
    for folder, label in ARMS:
        base = root / folder
        final = read(base / "final.json")
        scores = read(base / "postfit_scores.json")
        rows = trajectory(base)
        curves[folder] = rows
        x = sorted(rows)
        y = np.array([rows[i]["loss"] for i in x])
        axes[0].semilogy(x, y, label=label)
        axes[1].semilogy(x[1:], -np.diff(y), label=label)
        count = max(final["checkpoint_work"]["totals"]["bie_frequency_solve_count"],
            final["completed_gradient_prefix_work"]["totals"]["bie_frequency_solve_count"])
        work_lower += count
        checks = [json.loads(line) for line in (base / "stage_0/acceptance.jsonl").read_text().splitlines()]
        accepted = [r for r in checks if r["accepted"]]
        minimum_gain = min(min(r["production_gain"], r["refined_gain"]) for r in accepted)
        summary.append(dict(arm=folder or "coarse_control", label=label, status=final["status"],
            accepted_steps=final["accepted_steps"], initial_loss=rows[0]["loss"], final_loss=final["final_loss"],
            improvement=rows[0]["loss"] / final["final_loss"],
            last_gradient_inf=final["last_measured_gradient_inf"], last_gradient_iteration=final["last_measured_gradient_iteration"],
            final_gradient_status=final["final_gradient_status"], observed_frequency_solves_lower_bound=count,
            interrupted_extra_frequency_solves_upper_bound=final["unreported_frequency_solves_upper_bound"],
            acceptance_checks=len(checks), rejected_acceptance_checks=len(checks)-len(accepted),
            accepted_below_old_floor=sum(min(r["production_gain"],r["refined_gain"]) < 1e-10 for r in accepted),
            minimum_accepted_gain=minimum_gain, postfit=scores["final"]))
    axes[0].set(xlabel="Accepted update", ylabel="Training objective", title="Progress before scope closure")
    axes[1].axhline(1e-10, color="black", linestyle=":", label="Historical acceptance floor")
    axes[1].set(xlabel="Accepted update", ylabel="Production objective decrease", title="Resolved decreases below the old floor")
    axes[0].legend(fontsize=7)
    axes[1].legend(fontsize=7)
    fig.savefig(root / "training_prefixes.png", dpi=170)
    plt.close(fig)
    exact = curves["analytic_control"]
    fast = curves["analytic_fast"]
    overlap = sorted(exact.keys() & fast.keys())
    equality = dict(updates_compared=max(overlap), loss_bitwise_equal=all(exact[i]["loss"] == fast[i]["loss"] for i in overlap),
        parameter_bitwise_equal=all(np.array_equal(parameters(exact[i]), parameters(fast[i])) for i in overlap))
    fd = curves["refined_control"]
    overlap_fd = sorted(fd.keys() & exact.keys())
    fd_comparison = dict(updates_compared=max(overlap_fd),
        maximum_absolute_parameter_difference=max(float(np.max(np.abs(parameters(fd[i])-parameters(exact[i])))) for i in overlap_fd),
        maximum_relative_objective_difference=max(abs(fd[i]["loss"]-exact[i]["loss"])/fd[i]["loss"] for i in overlap_fd))
    record = dict(status="CLOSED_BY_USER_SCOPE_CHANGE", question_fully_resolved=False,
        scope="Archived TOP-010 continuation; no production-policy change", arms=summary,
        exact_geometry_acceleration_overlap=equality, fd_analytic_overlap=fd_comparison,
        fit_frequency_solves_lower_bound=work_lower,
        fit_interruption_extra_frequency_solves_upper_bound=sum(r["interrupted_extra_frequency_solves_upper_bound"] for r in summary),
        work_note="Detailed files separately retain initial audits, kernel calibration, qualification, and post-fit scoring work; the fit-only bounds here exclude those categories.",
        initial_postfit=read(root / "postfit_scores.json")["initial"])
    (root / "summary.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(dict(equality=equality, fd_comparison=fd_comparison, fit_solves=work_lower)))


if __name__ == "__main__":
    main()
