"""Amendment A2: evaluate the `parsimonious` band rule on SC-023's decisions (declared before this run).

Rule: the smallest band whose controlled-step model decrease (A1's feature,
unchanged) is at least 0.9 of the best band's. The recalibrated gate
requires, at lambda=1e-3, in each of physical/G1, physical/G2 and
coefficient/G2: median gain >= the ladder's, mean gain >= the ladder's, and
positive-gain fraction >= the ladder's - 0.02. Gains are EVALUATION ONLY.
"""
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[3]), str(HERE.parents[3] / "solvers")]
import amendment_a1 as a1  # noqa: E402
from analyze import group_of, ladder_bands  # noqa: E402
from experiments.shape_continuation import conditional_rules as cr  # noqa: E402
from experiments.shape_continuation import conditional_study as cs  # noqa: E402

TOLERANCE = 0.9


def parsimonious(group, context):
    best = max(r["controlled_fraction"] for r in group)
    return min(r["band"] for r in group if r["controlled_fraction"] >= TOLERANCE * best)


def main():
    rows = cr.load(HERE / "candidates" / "rows.jsonl.gz")
    by_state = defaultdict(list)
    for r in rows:
        by_state[(r["arm"], r["case"], r["state"])].append(r)
    values = {}
    with ProcessPoolExecutor(12) as pool:
        for arm, case, state, out in pool.map(a1.features, [(a, c, s, rs) for (a, c, s), rs in by_state.items()],
                                              chunksize=2):
            for key, v in out.items():
                values[(arm, case, state) + key] = v
    for r in rows:
        r["controlled_fraction"] = values[(r["arm"], r["case"], r["state"], r["f_max_hz"], r["damping"], r["band"],
                                           r["control"], r["gate"])]
    cr.RULES["parsimonious"] = parsimonious
    results = cr.evaluate(rows, ladder_bands())
    last_stage = {}
    for r in results:
        last_stage[(r["arm"], r["case"])] = max(last_stage.get((r["arm"], r["case"]), 0), r["stage"])
    for r in results:
        r["group"] = group_of(r, last_stage)
    verdict = {}
    for control, gate_name in (("physical", "G1"), ("physical", "G2"), ("coefficient", "G2")):
        s = cr.summarize(results, control=control, gate=gate_name, damping=1e-3)
        p, l = s["parsimonious"], s["ladder"]
        verdict[f"{control}/{gate_name}"] = dict(
            parsimonious=dict(median_gain=p["median_gain"], mean_gain=p["mean_gain"], positive_fraction=p["positive_fraction"],
                              median_regret=p["median_regret"], median_band=p["median_band"]),
            ladder=dict(median_gain=l["median_gain"], mean_gain=l["mean_gain"], positive_fraction=l["positive_fraction"],
                        median_regret=l["median_regret"], median_band=l["median_band"]),
            passes=bool(p["median_gain"] >= l["median_gain"] and p["mean_gain"] >= l["mean_gain"]
                        and p["positive_fraction"] >= l["positive_fraction"] - 0.02))
    verdict["qualifies"] = all(v["passes"] for k, v in verdict.items())
    summary = {}
    for control in cs.CONTROLS:
        for gate_name in cs.GATES:
            for damping in cs.DAMPINGS:
                key = f"{control}/{gate_name}/lambda={damping:g}"
                summary[key] = dict(pooled=cr.summarize(results, control=control, gate=gate_name, damping=damping),
                                    **{g: cr.summarize(results, control=control, gate=gate_name, damping=damping, group=g)
                                       for g in ("far", "middle", "near")})
    focus = [r for r in results if r["control"] == "coefficient" and r["gate"] == "G2" and r["damping"] == 1e-3]
    per_case = {f"{a}/{c}": {n: dict(median_gain=float(np.median([r[n]["gain"] for r in focus if (r["arm"], r["case"]) == (a, c)])),
                                     mean_gain=float(np.mean([r[n]["gain"] for r in focus if (r["arm"], r["case"]) == (a, c)])))
                             for n in ("ladder", "parsimonious")} for a, c in cs.RUNS}
    out = dict(amendment="A2 (declared in the plan before this evaluation; last development amendment)",
               tolerance=TOLERANCE, qualification=verdict, per_case_coefficient_G2=per_case, summary=summary)
    (HERE / "amendment_a2.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(qualification=verdict, per_case_coefficient_G2=per_case), indent=1))


if __name__ == "__main__":
    main()
