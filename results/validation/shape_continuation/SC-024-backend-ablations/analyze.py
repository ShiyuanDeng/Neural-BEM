"""SC-024(a) summary: backend variants against SC-022's controls (V0). No solves.

V0 rows are rebuilt from SC-022's saved stage histories. Their symmetric RMS
distance and tightest curvature radius are computed here from the saved
curves; SC-022 did not record them. Geometry scores are EVALUATION ONLY.
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

SC022 = HERE.parent / "SC-022-atlas-survey"
VARIANTS = ("V0", "V1", "V2", "V3")
LABELS = dict(V0="coefficient clip, gate 1e-7 (SC-022)", V1="physical 6 mm, gate 1e-7",
              V2="coefficient clip, gate 1e-5", V3="physical 6 mm, gate 1e-5",
              V2x4="V2 with SPD's 22-iteration stage cap x4 (amendment; Borges C only)")


def curve_of(row):
    return FourierCurve(np.array(row["coefficients"]["real"]) + 1j * np.array(row["coefficients"]["imag"]))


def radius(curve):
    return float(sc.LENGTH / np.max(np.abs(curve.nodes(8192).curvatures)))


def control_row(arm, case, truth_points):
    folder = SC022 / "runs" / arm / case
    result = sc.read(folder / "result.json")
    curves, outcomes, stage_rms = [], {}, []
    for number in (1, 2, 3, 4):
        path = folder / f"stage_{number}_history.json"
        if not path.exists():
            continue
        record = sc.read(path)
        curves += [curve_of(r) for r in record["history"]]
        stage_rms.append(symmetric_rms_distance(curves[-1], truth_points, sc.LENGTH) * 1e3)
        for t in record["trials"]:
            key = t.get("reason") or t.get("status")
            outcomes[key] = outcomes.get(key, 0) + 1
    return dict(status=result["status"], reason=result["reason"],
                symmetric_rms_mm=stage_rms[-1], hausdorff_mm=result["final_geometry"]["hausdorff_m"] * 1e3,
                units=result["work"]["work_units"], seconds=result["elapsed_seconds"],
                tightest_radius_mm=min(radius(c) for c in curves) * 1e3, trial_outcomes=outcomes,
                stage_symmetric_rms_mm=stage_rms)


def variant_row(variant, arm, case):
    result = sc.read(HERE / "runs" / variant / arm / case / "result.json")
    return dict(status=result["status"], reason=result["reason"],
                symmetric_rms_mm=result["final_geometry"]["symmetric_rms_m"] * 1e3,
                hausdorff_mm=result["final_geometry"]["hausdorff_m"] * 1e3,
                units=result["work"]["work_units"], seconds=result["elapsed_seconds"],
                tightest_radius_mm=min(r["tightest_radius_m"] for r in result["accepted_state_radii"]) * 1e3,
                trial_outcomes=result["trial_outcomes"],
                stage_symmetric_rms_mm=[s["geometry"]["symmetric_rms_m"] * 1e3 for s in result["stage_scores"]])


def main():
    table = {}
    for case in ac.CASES:
        _, truth = ac.load_case(SC022, case)
        points = truth.values(16384)
        start = symmetric_rms_distance(ac.start_curve(), points, sc.LENGTH) * 1e3
        for arm in ("borges", "fixed32"):
            for variant in VARIANTS:
                row = control_row(arm, case, points) if variant == "V0" else variant_row(variant, arm, case)
                row["initial_symmetric_rms_mm"] = start
                table[f"{variant}/{arm}/{case}"] = row
        if case == "circle_to_c":
            row = variant_row("V2x4", "borges", case)
            row["initial_symmetric_rms_mm"] = start
            table["V2x4/borges/circle_to_c"] = row
    (HERE / "summary.json").write_text(json.dumps(dict(variants=LABELS, runs=table), indent=1) + "\n")
    print("| Variant | Band rule | Case | Status | Sym. RMS (mm) | Hausdorff (mm) | Units | Tightest radius (mm) | Refusals (proj / self-int.) |")
    print("|---|---|---|---|---:|---:|---:|---:|---|")
    for key, r in table.items():
        v, arm, case = key.split("/")
        o = r["trial_outcomes"]
        print(f"| {v} | {arm} | {case} | {r['status'] if r['reason'] is None else r['reason']} | {r['symmetric_rms_mm']:.3f} | "
              f"{r['hausdorff_mm']:.3f} | {r['units']} | {r['tightest_radius_mm']:.1f} | "
              f"{o.get('unresolved_projection', 0)} / {o.get('self_intersection', 0)} |")


def final_curve(variant, arm, case):
    if variant == "V0":
        folder = SC022 / "runs" / arm / case
        last = max(n for n in (1, 2, 3, 4) if (folder / f"stage_{n}_history.json").exists())
        return curve_of(sc.read(folder / f"stage_{last}_history.json")["history"][-1])
    final = sc.read(HERE / "runs" / variant / arm / case / "result.json")["final_curve"]
    return FourierCurve(np.array(final["real"]) + 1j * np.array(final["imag"]))


def figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(15, 9.5))
    for column, case in enumerate(ac.CASES):
        _, truth = ac.load_case(SC022, case)
        for row, arm in enumerate(("borges", "fixed32")):
            ax = axes[row, column]
            z = truth.values(2048) * sc.LENGTH * 1e3
            ax.plot(z.real, z.imag, "k-", lw=2.2, label="truth")
            s = ac.start_curve().values(2048) * sc.LENGTH * 1e3
            ax.plot(s.real, s.imag, "k:", lw=1, label="start")
            for variant, color in zip(VARIANTS, ("C7", "C0", "C3", "C2")):
                z = final_curve(variant, arm, case).values(4096) * sc.LENGTH * 1e3
                ax.plot(z.real, z.imag, "-", color=color, lw=1.1, label=f"{variant}: {LABELS[variant]}")
            ax.set_aspect("equal")
            ax.set_title(f"{case}, band rule {arm}")
            ax.set_xlabel("x − 0.5 m (mm)")
    axes[0, 0].legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(HERE / "boundaries.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__" and "--probes" not in sys.argv:
    main()
    figure()


def probes():
    """SC-024(b): realized against predicted decrease, acceptance, and agreement with geometry."""
    import gzip
    rows = sc.read(HERE / "probes" / "rows.json")
    table = {}
    with gzip.open(HERE.parent / "SC-023-conditional-candidates" / "candidates" / "rows.jsonl.gz", "rt") as source:
        for line in source:
            r = json.loads(line)
            if r["damping"] == 1e-3 and r["control"] == "physical" and r["gate"] == "G1":
                table[(r["arm"], r["case"], r["state"], r["f_max_hz"], r["band"])] = r
    joined = []
    for r in rows:
        f_max = max(r["frequencies_hz"])
        label = table[(r["arm"], r["case"], r["state_index"], f_max, r["band"])]
        joined.append(dict(r, gain=label["gain"], label_halving=label["halving"],
                           realized_fraction=(r.get("realized_decrease") or 0.0) / r["base_loss"]))
    executed = [r for r in joined if r.get("halving") is not None]
    ratio = np.array([r["ratio"] for r in executed if r["ratio"] is not None])
    out = dict(rows=len(joined), executed=len(executed),
               ratio_quantiles=np.quantile(ratio, [0, .1, .25, .5, .75, .9, 1]).tolist(),
               ratio_within_20_percent=float(np.mean(np.abs(ratio - 1) <= .2)),
               accepted=float(np.mean([r["backend_accepts"] for r in executed])),
               halving_matches_sc023=float(np.mean([r["halving"] == r["label_halving"] for r in executed])))
    by_rule = {}
    for name in ("ladder", "fixed32", "knee", "validation", "dof", "oracle"):
        mine = [r for r in executed if name in r["rules"]]
        by_rule[name] = dict(probes=len(mine), accepted=float(np.mean([r["backend_accepts"] for r in mine])),
                             median_ratio=float(np.median([r["ratio"] for r in mine if r["ratio"] is not None])),
                             median_realized_fraction=float(np.median([r["realized_fraction"] for r in mine])),
                             median_gain=float(np.median([r["gain"] for r in mine])),
                             accepted_but_geometry_worse=int(sum(r["backend_accepts"] and r["gain"] < 0 for r in mine)))
    out["by_rule"] = by_rule
    # Does the data decrease a step achieves order its geometric gain, across bands at one state?
    rhos = []
    for key in {(r["arm"], r["case"], r["state"]) for r in executed}:
        group = [r for r in executed if (r["arm"], r["case"], r["state"]) == key]
        if len(group) > 2 and np.std([r["gain"] for r in group]) > 0:
            x = np.argsort(np.argsort([r["realized_fraction"] for r in group]))
            y = np.argsort(np.argsort([r["gain"] for r in group]))
            rhos.append(float(np.corrcoef(x, y)[0, 1]))
    out["within_state_spearman_realized_decrease_vs_gain"] = dict(states=len(rhos), median=float(np.median(rhos)),
                                                                 positive_fraction=float(np.mean(np.array(rhos) > 0)))
    out["accepted_but_geometry_worse"] = [dict(arm=r["arm"], case=r["case"], state=r["state"], band=r["band"],
                                               rules=r["rules"], gain=r["gain"], realized_fraction=r["realized_fraction"])
                                          for r in executed if r["backend_accepts"] and r["gain"] < 0]
    (HERE / "probes" / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "accepted_but_geometry_worse"}, indent=1))
    print("accepted but geometry worse:", len(out["accepted_but_geometry_worse"]))


if __name__ == "__main__" and "--probes" in sys.argv:
    probes()
