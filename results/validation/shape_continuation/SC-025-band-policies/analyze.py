"""SC-025 summary: four band policies on development and held-out cases. No solves.

Geometry scores are EVALUATION ONLY. Work units include the atlas arm's
policy probes (P=48 cells at each stage start).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[3]), str(HERE.parents[3] / "solvers")]
from experiments.shape_continuation import atlas_cases as ac  # noqa: E402
from experiments.shape_continuation import spd_cases as sc  # noqa: E402
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance  # noqa: E402
from experiments.shape_continuation.geometry import FourierCurve  # noqa: E402

ARMS = ("ladder", "fixed32", "progress", "atlas")
DEVELOPMENT = ("wrong_circle", "circle_to_star", "circle_to_c")
HELD_OUT = ("kite", "peanut", "hook")


def row(arm, case):
    path = HERE / "runs" / arm / case / "result.json"
    if not path.exists():
        return None
    d = sc.read(path)
    g = d["final_geometry"]
    probe_units = sum(v for k, v in {**d["work"]["solves"], **d["work"]["reciprocal_batches"]}.items()
                      if k.startswith("policy_probe"))
    return dict(status=d["status"], reason=d["reason"], bands=[x["band"] for x in d["decisions"]],
                symmetric_rms_mm=g["symmetric_rms_m"] * 1e3, hausdorff_mm=g["hausdorff_m"] * 1e3,
                area_relative_symmetric_difference=g["area"]["relative_symmetric_difference"],
                tightest_radius_mm=g["tightest_radius_m"] * 1e3,
                initial_symmetric_rms_mm=d["initial_geometry"]["symmetric_rms_m"] * 1e3,
                units=d["work"]["work_units"], policy_probe_units=probe_units, seconds=d["elapsed_seconds"],
                stage_symmetric_rms_mm=[s["geometry"]["symmetric_rms_m"] * 1e3 for s in d["stage_scores"]],
                trial_outcomes=d["trial_outcomes"])


def main():
    table = {case: {arm: row(arm, case) for arm in ARMS} for case in DEVELOPMENT + HELD_OUT}
    summary = {}
    for label, cases in (("development", DEVELOPMENT), ("held_out", HELD_OUT)):
        summary[label] = {}
        for arm in ARMS:
            rows = [table[c][arm] for c in cases if table[c][arm] is not None]
            if len(rows) < len(cases):
                continue
            summary[label][arm] = dict(
                geometric_mean_symmetric_rms_mm=float(np.exp(np.mean(np.log([r["symmetric_rms_mm"] for r in rows])))),
                total_units=int(sum(r["units"] for r in rows)),
                completed=int(sum(r["status"] == "COMPLETED_SCHEDULE" for r in rows)))
        wins = {}
        for c in cases:
            scores = {arm: table[c][arm]["symmetric_rms_mm"] for arm in ARMS if table[c][arm] is not None}
            wins[c] = dict(best=min(scores, key=scores.get), atlas_vs_ladder=(scores.get("atlas", np.nan)
                                                                              / scores.get("ladder", np.nan)))
        summary[label]["per_case"] = wins
    (HERE / "summary.json").write_text(json.dumps(dict(runs=table, summary=summary), indent=1) + "\n")
    print("| Case | Arm | Bands | Status | Sym. RMS (mm) | Hausdorff (mm) | Area sym. diff. | Units (probe) |")
    print("|---|---|---|---|---:|---:|---:|---:|")
    for case in DEVELOPMENT + HELD_OUT:
        for arm in ARMS:
            r = table[case][arm]
            if r is None:
                print(f"| {case} | {arm} | — | not run | | | | |")
                continue
            status = "completed" if r["status"] == "COMPLETED_SCHEDULE" else (r["reason"] or r["status"]).lower()
            print(f"| {case} | {arm} | {','.join(map(str, r['bands']))} | {status} | {r['symmetric_rms_mm']:.3f} | "
                  f"{r['hausdorff_mm']:.3f} | {r['area_relative_symmetric_difference']:.4f} | {r['units']} ({r['policy_probe_units']}) |")
    print(json.dumps(summary, indent=1))
    figure(table)


def figure(table):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cases = DEVELOPMENT + HELD_OUT
    fig, axes = plt.subplots(2, 3, figsize=(15, 9.5))
    for ax, case in zip(axes.ravel(), cases):
        _, truth = ac.load_case(HERE, case)
        z = truth.values(2048) * sc.LENGTH * 1e3
        ax.plot(z.real, z.imag, "k-", lw=2.4, label="truth")
        s = ac.start_curve().values(2048) * sc.LENGTH * 1e3
        ax.plot(s.real, s.imag, "k:", lw=1, label="start")
        for arm, color in zip(ARMS, ("C0", "C7", "C2", "C3")):
            if table[case][arm] is None:
                continue
            final = sc.read(HERE / "runs" / arm / case / "result.json")["final_curve"]
            c = FourierCurve(np.array(final["real"]) + 1j * np.array(final["imag"])).values(4096) * sc.LENGTH * 1e3
            ax.plot(c.real, c.imag, "-", color=color, lw=1.2,
                    label=f"{arm} ({table[case][arm]['symmetric_rms_mm']:.2f} mm)")
        ax.set_aspect("equal")
        ax.set_title(("held-out: " if case in HELD_OUT else "development: ") + case)
        ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(HERE / "boundaries.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
