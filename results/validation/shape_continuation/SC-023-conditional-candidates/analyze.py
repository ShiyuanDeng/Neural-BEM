"""SC-023 analysis: rule outcomes, the plan's qualification gate and feature correlations.

Reads only `candidates/rows.jsonl.gz`; no solves. Gains are EVALUATION ONLY
(symmetric RMS distance to the truth before and after one finite trial).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[3]), str(HERE.parents[3] / "solvers")]
from experiments.shape_continuation import conditional_rules as cr  # noqa: E402
from experiments.shape_continuation import conditional_study as cs  # noqa: E402
from experiments.shape_continuation import atlas_cases as ac  # noqa: E402


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    keep = np.isfinite(x) & np.isfinite(y)
    rx, ry = np.argsort(np.argsort(x[keep])), np.argsort(np.argsort(y[keep]))
    return float(np.corrcoef(rx, ry)[0, 1]) if keep.sum() > 2 else None


def ladder_bands():
    catalog, _ = ac.load_case(cs.SC022, "wrong_circle")
    position = cs.catalog_index()
    return {f: cs.ladder_band(catalog[position[f]].wavenumber, ac.contrast()) for f in cs.F_MAX_HZ}


def group_of(entry, last_stage):
    if entry["stage"] == 1:
        return "far"
    return "near" if entry["stage"] == last_stage[(entry["arm"], entry["case"])] else "middle"


def main():
    rows = cr.load(HERE / "candidates" / "rows.jsonl.gz")
    results = cr.evaluate(rows, ladder_bands())
    last_stage = {}
    for r in results:
        key = (r["arm"], r["case"])
        last_stage[key] = max(last_stage.get(key, 0), r["stage"])
    for r in results:
        r["group"] = group_of(r, last_stage)
    out = dict(rows=len(rows), decisions=len(results), ladder_bands={str(k): v for k, v in ladder_bands().items()})
    out["qualification"] = {rule: cr.qualifies(results, rule) for rule in cr.RULES if rule != "ladder"}
    out["summary"] = {}
    for control in cs.CONTROLS:
        for gate in cs.GATES:
            for damping in cs.DAMPINGS:
                key = f"{control}/{gate}/lambda={damping:g}"
                out["summary"][key] = dict(
                    pooled=cr.summarize(results, control=control, gate=gate, damping=damping),
                    **{g: cr.summarize(results, control=control, gate=gate, damping=damping, group=g)
                       for g in ("far", "middle", "near")})
    focus = [r for r in results if r["control"] == "physical" and r["gate"] == "G1" and r["damping"] == 1e-3]
    out["per_case_physical_G1_1e-3"] = {f"{a}/{c}": cr.summarize(focus, arm=a, case=c) for a, c in cs.RUNS}
    # Which band is best, as a function of the state's distance to the truth and f_max (descriptive).
    out["oracle_band_by_group_and_f_max"] = {
        g: {str(f): dict(median=float(np.median([r["oracle_band"] for r in focus if r["group"] == g and r["f_max_hz"] == f])),
                         quartiles=np.percentile([r["oracle_band"] for r in focus if r["group"] == g and r["f_max_hz"] == f],
                                                 [25, 75]).tolist())
            for f in cs.F_MAX_HZ if any(r["group"] == g and r["f_max_hz"] == f for r in focus)}
        for g in ("far", "middle", "near")}
    # Gain against frequency content, per rule, pooled (does adding higher frequencies help one step?).
    out["gain_by_f_max_physical_G1_1e-3"] = {
        rule: {str(f): float(np.median([r[rule]["gain"] for r in focus if r["f_max_hz"] == f and r[rule] is not None]))
               for f in cs.F_MAX_HZ if any(r["f_max_hz"] == f and r[rule] is not None for r in focus)}
        for rule in [*cr.RULES]}
    out["oracle_gain_by_f_max_physical_G1_1e-3"] = {
        str(f): float(np.median([r["oracle_gain"] for r in focus if r["f_max_hz"] == f])) for f in cs.F_MAX_HZ}
    # Feature-gain rank correlations over all candidates at the focus setting.
    cand = [r for r in rows if r["control"] == "physical" and r["gate"] == "G1" and r["damping"] == 1e-3]
    gain = [r["gain"] for r in cand]
    out["spearman_feature_vs_gain_physical_G1_1e-3"] = {
        name: spearman([np.nan if r[name] is None else r[name] for r in cand], gain)
        for name in ("predicted_fraction", "capture", "validation_fraction", "dof_ratio", "raw_maximum_normal_m",
                     "first_order_gain", "band")}
    # Within-decision correlation: does the feature rank bands correctly at one decision?
    within = {}
    for name in ("predicted_fraction", "capture", "validation_fraction", "dof_ratio", "first_order_gain"):
        values = []
        for key, group in cr.decisions(cand).items():
            x = [np.nan if r[name] is None else r[name] for r in group]
            y = [r["gain"] for r in group]
            if np.nanstd(x) > 0 and np.std(y) > 0:
                rho = spearman(x, y)
                if rho is not None and np.isfinite(rho):
                    values.append(rho)
        within[name] = dict(decisions=len(values), median=float(np.median(values)) if values else None,
                            positive_fraction=float(np.mean(np.array(values) > 0)) if values else None)
    out["within_decision_spearman_physical_G1_1e-3"] = within
    (HERE / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    figure(results, focus)
    q = out["qualification"]
    print(json.dumps({k: dict(qualifies=v["qualifies"], **{g: (round(v[g]["median_regret"], 4),
                     round(v[g]["ladder_median_regret"], 4), round(v[g]["positive_fraction"], 3),
                     round(v[g]["ladder_positive_fraction"], 3)) for g in ("G1", "G2")}) for k, v in q.items()}, indent=1))


def figure(results, focus):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    colors = dict(far="C3", middle="C1", near="C0")
    for g, c in colors.items():
        sub = [r for r in focus if r["group"] == g]
        axes[0].scatter([r["distance_before_m"] * 1e3 for r in sub],
                        np.array([r["oracle_band"] for r in sub]) * np.exp(np.random.default_rng(0).normal(0, .03, len(sub))),
                        s=6, c=c, alpha=.5, label=g)
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("state's symmetric RMS distance to truth (mm)")
    axes[0].set_ylabel("best band M for one step (oracle)")
    axes[0].legend()
    axes[0].set_title("oracle band vs distance (physical, G1, λ=1e-3)")
    names = list(cr.RULES)
    for i, g in enumerate(("far", "middle", "near")):
        data = [[r[n]["regret"] for r in focus if r["group"] == g and r[n] is not None] for n in names]
        axes[1].boxplot(data, positions=np.arange(len(names)) + (i - 1) * .25, widths=.22, showfliers=False,
                        patch_artist=True, boxprops=dict(facecolor=colors[g], alpha=.5))
    axes[1].set_xticks(np.arange(len(names)))
    axes[1].set_xticklabels(names)
    axes[1].set_ylabel("regret (oracle gain − rule gain)")
    axes[1].set_title("rule regret by state group (red far, orange middle, blue near)")
    fmax = sorted({r["f_max_hz"] for r in focus})
    for n in names + ["oracle"]:
        values = [np.median([(r["oracle_gain"] if n == "oracle" else r[n]["gain"]) for r in focus
                             if r["f_max_hz"] == f and (n == "oracle" or r[n] is not None)] or [np.nan]) for f in fmax]
        axes[2].plot(np.array(fmax) / 1e9, values, "o-", label=n, lw=2 if n == "oracle" else 1)
    axes[2].set_xlabel("f_max of the cumulative data set (GHz)")
    axes[2].set_ylabel("median one-step gain")
    axes[2].legend(fontsize=8)
    axes[2].set_title("one-step gain vs data used")
    fig.tight_layout()
    fig.savefig(HERE / "rules.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
