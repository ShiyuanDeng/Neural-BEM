"""Amendment A1: evaluate the post hoc `controlled` band rule on SC-023's decisions.

Feature (truth-free): the Gauss-Newton model decrease, as a fraction of the
F-loss, of the step the backend would take: the conditional LM step at the
decision's damping, the decision's control (coefficient clip or physical
6 mm), and the halving that SC-023 recorded as the decision gate's first
admissible trial (geometry only). No solves and no new trials. The rule
picks the band with the largest feature, with ties going to the smaller
band. Evaluation reuses SC-023's EVALUATION-ONLY gains and the plan's
qualification gate.
"""
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[3]), str(HERE.parents[3] / "solvers")]
from experiments.shape_continuation import conditional_rules as cr  # noqa: E402
from experiments.shape_continuation import conditional_study as cs  # noqa: E402
from experiments.shape_continuation import spd_cases as sc  # noqa: E402
from experiments.shape_continuation.atlas_survey import band_coordinates, conditional_step, predicted_decrease  # noqa: E402
from experiments.shape_continuation.geometry import FourierCurve  # noqa: E402
from experiments.shape_continuation.lm_backend import BackendConfig  # noqa: E402
from experiments.shape_continuation.updates import BorgesUpdate  # noqa: E402


def features(job):
    """Controlled-step model decrease for every (F, damping, band, control, gate) at one state."""
    arm, case, state, rows = job
    atlas = np.load(cs.SC022 / "runs" / arm / case / "atlas.npz")
    G_all, g_all, loss_all = atlas["gauss_newton"][state], atlas["gradient"][state], atlas["loss"][state]
    states, _, _ = cs.run_states(arm, case)
    curve = FourierCurve(states[state]["coefficients"])
    update, config = BorgesUpdate(sc.LENGTH), BackendConfig()
    sets = {f: members for f, members, _ in cs.frequency_sets()}
    out = {}
    cache = {}
    for r in rows:
        f, damping, band = r["f_max_hz"], r["damping"], r["band"]
        key = (f, damping, band)
        if key not in cache:
            members = sets[f]
            G, g = G_all[members].mean(0), g_all[members].mean(0)
            keep = band_coordinates(band, cs.P)
            local = conditional_step(G, g, keep, damping)[keep]
            space = update.prepare(curve, band, curve.band)
            size = update.measure(space, local)["maximum_normal_m"]
            bound = config.bounds(space.orders)
            proposals = dict(coefficient=np.clip(local, -bound, bound),
                             physical=local * min(1.0, cs.PHYSICAL_BOUND_M / size) if size > 0 else local)
            cache[key] = (G, g, float(loss_all[members].mean()), keep, proposals)
        G, g, loss, keep, proposals = cache[key]
        if r["halving"] is None:
            value = 0.0
        else:
            step = np.zeros(2 * cs.P + 1)
            step[keep] = 0.5 ** r["halving"] * proposals[r["control"]]
            value = predicted_decrease(G, g, step) / loss
        out[(f, damping, band, r["control"], r["gate"])] = value
    return arm, case, state, out


def main():
    rows = cr.load(HERE / "candidates" / "rows.jsonl.gz")
    by_state = defaultdict(list)
    for r in rows:
        by_state[(r["arm"], r["case"], r["state"])].append(r)
    jobs = [(a, c, s, rs) for (a, c, s), rs in by_state.items()]
    values = {}
    with ProcessPoolExecutor(12) as pool:
        for arm, case, state, out in pool.map(features, jobs, chunksize=2):
            for (f, damping, band, control, gate), v in out.items():
                values[(arm, case, state, f, damping, band, control, gate)] = v
    for r in rows:
        r["controlled_fraction"] = values[(r["arm"], r["case"], r["state"], r["f_max_hz"], r["damping"], r["band"],
                                           r["control"], r["gate"])]

    def controlled(group, context):
        best = max(r["controlled_fraction"] for r in group)
        return min(r["band"] for r in group if r["controlled_fraction"] == best)

    cr.RULES["controlled"] = controlled
    sys.path.insert(0, str(HERE))
    from analyze import ladder_bands, group_of, spearman  # noqa: E402
    results = cr.evaluate(rows, ladder_bands())
    last_stage = {}
    for r in results:
        last_stage[(r["arm"], r["case"])] = max(last_stage.get((r["arm"], r["case"]), 0), r["stage"])
    for r in results:
        r["group"] = group_of(r, last_stage)

    def gate(control, gate_name):
        subset = [r for r in results if r["gate"] == gate_name and r["damping"] == 1e-3 and r["control"] == control]
        regret = float(np.median([r["controlled"]["regret"] for r in subset]))
        ladder_regret = float(np.median([r["ladder"]["regret"] for r in subset]))
        positive = float(np.mean([r["controlled"]["gain"] > 0 for r in subset]))
        ladder_positive = float(np.mean([r["ladder"]["gain"] > 0 for r in subset]))
        return dict(decisions=len(subset), median_regret=regret, ladder_median_regret=ladder_regret,
                    positive_fraction=positive, ladder_positive_fraction=ladder_positive,
                    passes=bool(regret <= ladder_regret - 0.05 and positive >= ladder_positive))

    verdict = {f"physical/{g}": gate("physical", g) for g in ("G1", "G2")}
    verdict["coefficient/G2"] = gate("coefficient", "G2")
    verdict["qualifies"] = all(v["passes"] for v in verdict.values())
    summary = {}
    for control in cs.CONTROLS:
        for gate_name in cs.GATES:
            for damping in cs.DAMPINGS:
                key = f"{control}/{gate_name}/lambda={damping:g}"
                summary[key] = dict(pooled=cr.summarize(results, control=control, gate=gate_name, damping=damping),
                                    **{g: cr.summarize(results, control=control, gate=gate_name, damping=damping, group=g)
                                       for g in ("far", "middle", "near")})
    within = {}
    for control in cs.CONTROLS:
        for gate_name in cs.GATES:
            cand = [r for r in rows if r["control"] == control and r["gate"] == gate_name and r["damping"] == 1e-3]
            rhos = []
            for key, group in cr.decisions(cand).items():
                x, y = [r["controlled_fraction"] for r in group], [r["gain"] for r in group]
                if np.std(x) > 0 and np.std(y) > 0:
                    rho = spearman(x, y)
                    if rho is not None and np.isfinite(rho):
                        rhos.append(rho)
            within[f"{control}/{gate_name}"] = dict(decisions=len(rhos), median=float(np.median(rhos)),
                                                    positive_fraction=float(np.mean(np.array(rhos) > 0)))
    out = dict(amendment="A1 (post hoc; declared in the plan before this evaluation)", qualification=verdict,
               within_decision_spearman_controlled_vs_gain_lambda_0p001=within, summary=summary)
    (HERE / "amendment_a1.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(qualification=verdict, within=within), indent=1))
    for key in ("physical/G1/lambda=0.001", "physical/G2/lambda=0.001", "coefficient/G2/lambda=0.001"):
        print(key)
        for g in ("far", "middle", "near", "pooled"):
            s = summary[key][g]
            print("  %-7s" % g, " ".join("%s: gain %.3f/%.3f regret %.3f pos %.2f M %.0f" % (
                n, s[n]["median_gain"], s[n]["mean_gain"], s[n]["median_regret"], s[n]["positive_fraction"],
                s[n]["median_band"]) for n in ("ladder", "controlled")), "oracle %.3f" % s["oracle"]["median_gain"])


if __name__ == "__main__":
    main()
