"""Rebuild SC-031 tables and figures from saved evidence (no fitting, no forward solves).

Run from the repository root: PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-031-regularizing-metric/report.py
Truth enters only the already-saved scores and the evaluation-only boundary plot.
"""
import collections
import json
from pathlib import Path

import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.geometry import FourierCurve, normal_basis
from experiments.shape_continuation.metrics import boundary_distance
from experiments.shape_continuation.updates import BorgesUpdate

HERE = Path(__file__).resolve().parent
R0 = sc.ROOT / "results/validation/shape_continuation/SC-029-atlas-strategies/runs/baseline"
CASES = ast.CASES
ARMS = ("R0", "R1", "R2")
FLOOR = 0.01
L = sc.LENGTH


def radius_mm(curve):
    return float(1e3 * L / np.max(np.abs(curve.nodes(8192).curvatures)))


def cusp(before, step_m):
    nodes = before.nodes(8192)
    h = normal_basis(nodes, len(step_m) // 2) @ (np.asarray(step_m) / L)
    return float(np.max(-nodes.curvatures * h))


def geometry_score(case, curve):
    """Evaluation-only geometry, as `ast.score` computes it, without field solves."""
    truth = ast.curve_from(json.loads((ast.source_folder(case) / "truth.json").read_text()))
    error, bound = boundary_distance(truth, curve)
    return dict(symmetric_rms_mm=1e3 * symmetric_rms_distance(curve, truth.values(16384), L),
                hausdorff_mm=1e3 * L * error, hausdorff_upper_mm=1e3 * L * (error + bound),
                catalog_relative_residual=None)


def load(arm, case, stage_limit=None):
    """A run's result and histories; R0 truncated to `stage_limit` stages is scored on geometry only."""
    folder = R0 / case / "none" if arm == "R0" else HERE / "runs" / arm / case
    result = json.loads((folder / "result.json").read_text())
    stages = []
    for row in result["stages"]:
        path = folder / f"{row['stage']}_history.json"
        stages.append(json.loads(path.read_text()) if path.exists() else dict(history=[], trials=[]))
    if arm == "R0" and stage_limit:
        stages, rows = stages[:stage_limit], result["stages"][:stage_limit]
        last = stages[-1]["history"][-1]
        curve = ast.curve_from(last["coefficients"])
        result = dict(result, stages=rows, final_curve=last["coefficients"], status="COMPLETED_SCHEDULE",
                      reason=None, work=dict(work_units=last["work"]["work_units"]),
                      inverse_seconds=last["work"]["seconds"], score=geometry_score(case, curve))
    return result, stages


def metric_share(stages, case):
    """R2 only: share of each accepted step's R-norm^2 carried by the curvature term."""
    update, shares = BorgesUpdate(L, projection_tolerance=1e-5), []
    config = json.loads((HERE / "runs" / "R2" / case / "configuration.json").read_text())
    for record, stage in zip(stages, config["stages"]):
        smoothing = L / (2.5 * max(stage["wavenumbers"]))
        history = record["history"]
        for i in range(1, len(history)):
            space = update.prepare(ast.curve_from(history[i - 1]["coefficients"]), stage["update_modes"],
                                   stage["curve_modes"])
            a = np.asarray(history[i]["step_m"])
            mass = a @ update.metric(space, "mass") @ a
            total = a @ update.metric(space, "curvature", smoothing) @ a
            shares.append(float((total - mass) / total) if total > 0 else 0.0)
    return shares


def mechanism(stages):
    radii, cusps, rho, reasons, hanke = [], [], [], collections.Counter(), []
    for n, record in enumerate(stages):
        history, trials = record["history"], record["trials"]
        curves = [ast.curve_from(r["coefficients"]) for r in history]
        radii.append([radius_mm(c) for c in curves])
        cusps.append([cusp(curves[i - 1], history[i]["step_m"]) for i in range(1, len(history))])
        base = {r["iteration"]: r["loss"] for r in history}
        for t in trials:
            reasons[t.get("reason") or t.get("status")] += 1
            if "hanke_attainable" in t and t["backtrack"] == 0:
                hanke.append(bool(t["hanke_attainable"]))
            pred = t.get("predicted_decrease")
            if pred and pred > 0 and t.get("loss") is not None and (t["iteration"] - 1) in base:
                rho.append((base[t["iteration"] - 1] - t["loss"]) / pred)
    return dict(radius_trajectory_mm=radii, stage_1_end_radius_mm=radii[0][-1] if radii and radii[0] else None,
                minimum_radius_mm=min((r for s in radii for r in s), default=None),
                stage_1_max_cusp=max(cusps[0], default=None) if cusps else None,
                trial_outcomes=dict(reasons), hanke_attainable_fraction=float(np.mean(hanke)) if hanke else None,
                model_ratio_quartiles=np.percentile(rho, [25, 50, 75]).tolist() if rho else None,
                model_ratio_count=len(rho))


def gm(values):
    return float(np.exp(np.mean(np.log(values))))


def main():
    rows = {}
    stage_a_only = all(json.loads((HERE / "runs" / "R2" / c / "result.json").read_text()).get("stage_a_only")
                       for c in CASES)
    for arm in ARMS:
        for case in CASES:
            result, stages = load(arm, case, 1 if stage_a_only else None)
            score = result["score"]
            rows[(arm, case)] = dict(arm=arm, case=case, status=result["status"], reason=result.get("reason"),
                final_curve=result["final_curve"],
                stages_run=[s["stage"] for s in result["stages"]], rms_mm=score["symmetric_rms_mm"],
                hausdorff_mm=score["hausdorff_mm"], hausdorff_upper_mm=score["hausdorff_upper_mm"],
                work_units=result["work"]["work_units"], inverse_seconds=result["inverse_seconds"],
                catalog_relative_residual=score["catalog_relative_residual"],
                stops=[(s["stage"], s["outcome"], s["stop"], s["accepted"]) for s in result["stages"]],
                stage_1_final_loss=result["stages"][0]["final_loss"],
                curvature_share_of_step_metric=metric_share(stages, case) if arm == "R2" else None,
                **mechanism(stages))
    ratios = {}
    for num, den in (("R2", "R0"), ("R1", "R0"), ("R2", "R1")):
        r = [max(rows[(num, c)]["rms_mm"], FLOOR) / max(rows[(den, c)]["rms_mm"], FLOOR) for c in CASES]
        ratios[f"{num}/{den}"] = dict(per_case=dict(zip(CASES, r)), geometric_mean=gm(r), worst=max(r))
    added = {arm: [c for c in CASES if rows[(arm, c)]["status"] != "COMPLETED_SCHEDULE"
                   and rows[("R0", c)]["status"] == "COMPLETED_SCHEDULE"] for arm in ("R1", "R2")}
    gate = json.loads((HERE / "gate.json").read_text())
    decision = dict(stage_a_only=stage_a_only, gate_released=gate["released"],
                    comparison="stage-1 endpoints (R0 truncated, geometry-only score)" if stage_a_only
                    else "four-stage prefix endpoints")
    if not stage_a_only:
        r20, r21 = ratios["R2/R0"], ratios["R2/R1"]
        decision.update(
            r2_qualifies=r20["geometric_mean"] <= 0.8 and r20["worst"] <= 1.5 and not added["R2"],
            attributed_to_metric=r21["geometric_mean"] <= 0.8,
            r1_passes=ratios["R1/R0"]["geometric_mean"] <= 0.8 and ratios["R1/R0"]["worst"] <= 1.5 and not added["R1"],
            detail_regression={c: r20["per_case"][c] for c in ("circle_to_star", "kite") if r20["per_case"][c] > 1.5})
    summary = dict(rows=[{k: v for k, v in r.items() if k not in ("radius_trajectory_mm", "final_curve")}
                         for r in rows.values()],
                   ratios=ratios, added_hard_stops=added, decision=decision, gate=gate)
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1))
    table(rows, ratios, added, decision)
    figures(rows)


def table(rows, ratios, added, decision):
    lines = ["| Case | Arm | Status | RMS, mm | Hausdorff, mm | Stage-1 loss | Units | Stage-1 end radius, mm | Min radius, mm | Refit / self-int. refusals |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for case in CASES:
        for arm in ARMS:
            r = rows[(arm, case)]
            o = r["trial_outcomes"]
            status = r["status"] if r["status"] == "COMPLETED_SCHEDULE" else f"{r['status']} ({r['reason']})"
            lines.append(f"| {case} | {arm} | {status} | {r['rms_mm']:.4g} | {r['hausdorff_mm']:.4g} | {r['stage_1_final_loss']:.3g} | {r['work_units']} | "
                         f"{r['stage_1_end_radius_mm']:.2f} | {r['minimum_radius_mm']:.2f} | "
                         f"{o.get('unresolved_projection', 0)} / {o.get('self_intersection', 0)} |")
    lines += ["", "| Ratio (0.01-mm floor) | Geometric mean | Worst | Per case |", "|---|---:|---:|---|"]
    for name, v in ratios.items():
        lines.append(f"| {name} | {v['geometric_mean']:.3f} | {v['worst']:.3f} | " +
                     ", ".join(f"{c} {x:.3g}" for c, x in v["per_case"].items()) + " |")
    lines += ["", f"Added hard stops: {added}", f"Decision record: {decision}"]
    (HERE / "tables.md").write_text("\n".join(lines) + "\n")


def figures(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colours = dict(R0="C0", R1="C2", R2="C3")
    labels = dict(R0="R0 current (SC-029)", R1="R1 Hanke + mass", R2="R2 Hanke + curvature")
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharey=True)
    for ax, case in zip(axes.flat, CASES):
        for arm in ARMS:
            radii = [x for s in rows[(arm, case)]["radius_trajectory_mm"] for x in s]
            ax.semilogy(radii, color=colours[arm], label=labels[arm])
        ax.axhspan(5, 7, color="0.85", label="gate: collapse < 5 mm, avoided >= 7 mm")
        ax.set_title(case)
        ax.set_xlabel("accepted state along the run")
    axes[0, 0].set_ylabel("tightest curvature radius (mm)")
    axes[1, 0].set_ylabel("tightest curvature radius (mm)")
    handles, names = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, names, loc="lower center", ncol=4, fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(HERE / "radius_trajectories.png", dpi=110)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(13, 8.5))
    for ax, case in zip(axes.flat, CASES):
        truth = ast.curve_from(json.loads((ast.source_folder(case) / "truth.json").read_text())).values(2048)
        ax.plot(truth.real, truth.imag, "k", lw=2.5, alpha=0.35, label="truth (evaluation only)")
        for arm in ARMS:
            r = rows[(arm, case)]
            z = ast.curve_from(r["final_curve"]).values(2048)
            ax.plot(z.real, z.imag, color=colours[arm], lw=1, label=f"{arm}: {r['rms_mm']:.3g} mm RMS")
        ax.set_aspect("equal")
        ax.set_title(case)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(HERE / "boundaries.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
