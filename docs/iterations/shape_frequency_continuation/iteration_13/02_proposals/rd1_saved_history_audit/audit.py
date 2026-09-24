"""RD-1 review diagnostic: saved-history audit of SC-029 and SC-024 (zero forward solves).

Reads accepted states, steps and trials already saved by SC-029 and SC-024 and
recomputes only geometry: stop anatomy, refusal categories, tightest curvature
radius along each trajectory, and the curvature a proposed normal step creates.
Truth enters only the evaluation-only reference radii printed beside the
trajectories. It also reads the saved, hash-verified SC-026 Jacobians to size
Marquardt's diag(G) at 0.5 GHz. Nothing here runs an inverse, a forward solve
or a Jacobian.

Run from the repository root in the EMNerf environment:
    PYTHONPATH=solvers:. python docs/iterations/shape_frequency_continuation/iteration_13/02_proposals/rd1_saved_history_audit/audit.py
"""
import collections
import json
import re
from pathlib import Path

import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as t
from experiments.shape_continuation.geometry import FourierCurve, arclength_angles, grid_size, normal_basis

HERE = Path(__file__).resolve().parent
SC029 = Path("results/validation/shape_continuation/SC-029-atlas-strategies/runs")
SC024 = Path("results/validation/shape_continuation/SC-024-backend-ablations/runs")
CASES = ("wrong_circle", "circle_to_star", "hook", "circle_to_c", "kite", "peanut")
PREFIXES = ("baseline", "protect")
L, NODES = 0.05, 8192  # package length unit (m), curvature sampling


def radius_mm(curve):
    return float(1e3 * L / np.max(np.abs(curve.nodes(NODES).curvatures)))


def step_geometry(before, step_m):
    """Pre-step prediction of the tightest radius: linearized and exact (unrefit) displaced curve."""
    a = np.asarray(step_m) / L
    nodes = before.nodes(NODES)
    kappa = nodes.curvatures
    h = normal_basis(nodes, len(a) // 2) @ a
    band = len(a) // 2
    m = np.arange(1, band + 1)
    theta, _ = arclength_angles(nodes)
    h_tt = -(np.cos(theta[:, None] * m) * m**2) @ a[1:band + 1] - (np.sin(theta[:, None] * m) * m**2) @ a[band + 1:]
    dk = -(h_tt * (2 * np.pi / nodes.perimeter) ** 2 + kappa**2 * h)  # outward normal, kappa > 0 convex
    normal = nodes.normals[:, 0] + 1j * nodes.normals[:, 1]
    moved = FourierCurve.from_samples(before.values(NODES) + h * normal, NODES // 2 - 1)
    return dict(r_linear_mm=float(1e3 * L / np.max(np.abs(kappa + dk))), r_exact_mm=radius_mm(moved),
                max_move_mm=float(1e3 * L * np.max(np.abs(h))), cusp_index=float(np.max(-kappa * h)))


def stage_rows(folder, stages):
    rows = []
    for st in stages:
        path = folder / f"{st['stage']}_history.json"
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        history, trials = record["history"], record["trials"]
        reasons = collections.Counter(tr.get("reason") or tr.get("status") for tr in trials)
        last = history[-1]
        final_trials = [tr for tr in trials if tr["iteration"] == last["iteration"] + 1]
        misses = [float(m.group(1)) for tr in trials if tr.get("reason") == "unresolved_projection"
                  for m in [re.search(r"([0-9.eE+-]+) relative", tr.get("detail", ""))] if m]
        radii = [radius_mm(t.curve_from(r["coefficients"])) for r in history]
        steps = [step_geometry(t.curve_from(history[i - 1]["coefficients"]), history[i]["step_m"]) | dict(
                 iteration=i, r_before_mm=radii[i - 1], r_after_mm=radii[i], damping=history[i]["damping"],
                 loss_before=history[i - 1]["loss"], loss_after=history[i]["loss"]) for i in range(1, len(history))]
        rows.append(dict(stage=st["stage"], stop=st["stop"], outcome=st["outcome"], accepted=st["accepted"],
                         initial_loss=st["initial_loss"], final_loss=st["final_loss"], trials=len(trials),
                         refusals=dict(reasons), final_iteration_trials=len(final_trials),
                         final_gradient_inf=last["gradient_inf"], final_next_damping=last["next_damping"],
                         refit_miss_relative=misses, radius_mm=radii, steps=steps))
    return rows


def marquardt_scale(case="circle_to_c", frequency_mhz=500, band=3, atlas_band=48):
    """diag(J^T J) over the stage-1 update coordinates on saved SC-026 states (metres^-2)."""
    arrays = np.load(f"results/validation/shape_continuation/SC-026-atlas-dataset/cells/{case}.npz")
    j = list(np.round(arrays["frequencies_hz"] / 1e6)).index(frequency_mhz)
    cols = np.r_[0:band + 1, atlas_band + 1:atlas_band + 1 + band]
    block = arrays["jacobian"][:, j][:, :, cols]
    diag = np.einsum("sri,sri->si", block, block)
    return dict(case=case, frequency_mhz=frequency_mhz, band=band, states=int(diag.shape[0]),
                median=float(np.median(diag)), minimum=float(diag.min()), maximum=float(diag.max()))


def main():
    truth = {c: radius_mm(t.curve_from(json.loads((t.source_folder(c) / "truth.json").read_text()))) for c in CASES}
    paths = []
    for prefix in PREFIXES:
        for case in CASES:
            for suffix in ("none", "repeat", "extend"):
                folder = SC029 / prefix / case / suffix
                result = json.loads((folder / "result.json").read_text())
                paths.append(dict(source="SC-029", prefix=prefix, case=case, suffix=suffix, status=result["status"],
                                  score={k: result["score"][k] for k in ("symmetric_rms_mm", "hausdorff_mm", "tightest_radius_mm")},
                                  stages=stage_rows(folder, result["stages"])))
    for variant in ("V1", "V2", "V3"):
        folder = SC024 / variant / "borges" / "circle_to_c"
        result = json.loads((folder / "result.json").read_text())
        stages = [dict(stage=s["stage_label"], stop=s["stop_reason"], outcome=s["outcome"], accepted=s["accepted_steps"],
                       initial_loss=s["initial_loss"], final_loss=s["final_loss"]) for s in result["stages"]]
        paths.append(dict(source="SC-024", prefix=variant, case="circle_to_c", suffix="none",
                          status=result["status"], score={}, stages=stage_rows(folder, stages)))
    scale = marquardt_scale()
    (HERE / "summary.json").write_text(json.dumps(dict(truth_tightest_radius_mm=truth, marquardt_diag_g=scale,
                                                       paths=paths), indent=1))
    figure(paths, truth)
    report(paths, truth)


def figure(paths, truth):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharey=True)
    for ax, case in zip(axes.flat, CASES):
        for p in paths:
            if p["case"] != case or p["suffix"] != "none":
                continue
            radii, edges = [], []
            for s in p["stages"]:
                radii += s["radius_mm"]
                edges.append(len(radii))
            style = dict(baseline=("C0", "-", "ladder M=3,5,7,9"), protect=("C1", "-", "M=2 first"),
                         V1=("C2", "--", "SC-024 V1: 6-mm cap"), V2=("C7", ":", "SC-024 V2"),
                         V3=("C3", "--", "SC-024 V3: cap + 1e-5 gate"))[p["prefix"]]
            if p["prefix"] == "V2":
                continue  # identical to the SC-029 ladder prefix
            ax.semilogy(radii, color=style[0], ls=style[1], label=style[2])
            for e in edges[:-1]:
                ax.axvline(e - 0.5, color=style[0], lw=0.4, alpha=0.4)
        ax.axhline(truth[case], color="k", lw=1, label="truth tightest radius (evaluation only)")
        ax.axhspan(1.1, 2.2, color="r", alpha=0.08, label="K=192 storage scale L/K")
        ax.set_title(case)
        ax.set_xlabel("accepted state along the four-stage prefix")
    axes[0, 0].set_ylabel("tightest curvature radius (mm)")
    axes[1, 0].set_ylabel("tightest curvature radius (mm)")
    handles = {}
    for ax in axes.flat:
        for handle, label in zip(*ax.get_legend_handles_labels()):
            handles.setdefault(label, handle)
    fig.legend(handles.values(), handles.keys(), loc="lower center", ncol=6, fontsize=8)
    fig.suptitle("RD-1: tightest radius along each four-stage prefix (saved SC-029/SC-024 states; thin lines = stage ends)")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(HERE / "radius_trajectories.png", dpi=110)


def report(paths, truth):
    lines = ["RD-1 saved-history audit (zero forward solves)", ""]
    lines.append("Truth tightest radius (evaluation only): " + ", ".join(f"{c} {r:.2f} mm" for c, r in truth.items()))
    lines.append("SC-026 diag(G), C, 0.5 GHz, M=3 coordinates: " + json.dumps(marquardt_scale()))
    for p in paths:
        s = p["score"]
        head = f"{p['source']} {p['prefix']:8s} {p['case']:14s} {p['suffix']:6s} {p['status']}"
        if s:
            head += f"  RMS {s['symmetric_rms_mm']:.3g} mm  H {s['hausdorff_mm']:.3g} mm"
        lines.append(head)
        for st in p["stages"]:
            refused = sum(v for k, v in st["refusals"].items() if k not in ("accepted", "nondecreasing", "acceptance_margin"))
            miss = np.median(st["refit_miss_relative"]) if st["refit_miss_relative"] else float("nan")
            lines.append(f"   {st['stage']:8s} stop={st['stop']} accepted={st['accepted']} trials={st['trials']} "
                         f"refused={refused} final-iteration trials={st['final_iteration_trials']} "
                         f"grad_inf={st['final_gradient_inf']:.2e} radius {st['radius_mm'][0]:.2f}->{st['radius_mm'][-1]:.2f} mm "
                         f"median refit miss={miss:.2e}")
    (HERE / "audit.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
