"""SC-023 band rules and their evaluation on the stored candidate table.

A rule reads only truth-free features of the candidates at one decision
(run, state, F, damping, control, gate) and returns a band M. Evaluation
compares the chosen candidate's EVALUATION-ONLY gain with the best band's
(the oracle) at the same decision. Rules are declared in the SC-023 plan;
their thresholds are fixed here and not tuned on the table.
"""
from collections import defaultdict
import gzip
import json

import numpy as np

KNEE_CAPTURE = 0.9
DOF_THRESHOLD = 0.5
FIXED_BAND = 32


def ladder(rows, context):
    target = context["ladder_band"]
    feasible = [r["band"] for r in rows if r["band"] <= target]
    return max(feasible) if feasible else min(r["band"] for r in rows)


def fixed(rows, context):
    return min((r["band"] for r in rows), key=lambda m: abs(m - FIXED_BAND))


def knee(rows, context):
    good = [r["band"] for r in rows if r["capture"] >= KNEE_CAPTURE]
    return min(good) if good else max(r["band"] for r in rows)


def validation(rows, context):
    scored = [r for r in rows if r["validation_fraction"] is not None]
    if not scored:
        return None
    best = max(r["validation_fraction"] for r in scored)
    return min(r["band"] for r in scored if r["validation_fraction"] == best)


def dof(rows, context):
    good = [r["band"] for r in rows if r["dof_ratio"] >= DOF_THRESHOLD]
    return max(good) if good else min(r["band"] for r in rows)


RULES = dict(ladder=ladder, fixed32=fixed, knee=knee, validation=validation, dof=dof)


def load(path):
    with gzip.open(path, "rt") as source:
        return [json.loads(line) for line in source]


def decisions(rows):
    """Group candidate rows by decision; each group has one row per band."""
    groups = defaultdict(list)
    for row in rows:
        key = (row["arm"], row["case"], row["state"], row["f_max_hz"], row["damping"], row["control"], row["gate"])
        groups[key].append(row)
    return groups


def evaluate(rows, ladder_bands):
    """Per decision: each rule's choice and gain, and the oracle's."""
    results = []
    for key, group in decisions(rows).items():
        group = sorted(group, key=lambda r: r["band"])
        by_band = {r["band"]: r for r in group}
        oracle = max(group, key=lambda r: r["gain"])
        context = dict(ladder_band=ladder_bands[key[3]])
        entry = dict(zip(("arm", "case", "state", "f_max_hz", "damping", "control", "gate"), key),
                     stage=group[0]["stage"], oracle_band=oracle["band"], oracle_gain=oracle["gain"],
                     distance_before_m=group[0]["distance_before_m"])
        for name, rule in RULES.items():
            band = rule(group, context)
            if band is None:
                entry[name] = None
                continue
            chosen = by_band[band]
            entry[name] = dict(band=band, gain=chosen["gain"], regret=oracle["gain"] - chosen["gain"],
                               admissible=chosen["admissible"], halving=chosen["halving"],
                               first_order_gain=chosen["first_order_gain"])
        results.append(entry)
    return results


def summarize(results, **where):
    """Aggregate rule outcomes over decisions matching `where` (e.g. control="physical")."""
    subset = [r for r in results if all(r[k] == v for k, v in where.items())]
    out = dict(decisions=len(subset))
    for name in RULES:
        chosen = [r[name] for r in subset if r[name] is not None]
        if not chosen:
            continue
        gain = np.array([c["gain"] for c in chosen])
        regret = np.array([c["regret"] for c in chosen])
        out[name] = dict(count=len(chosen), median_gain=float(np.median(gain)), mean_gain=float(np.mean(gain)),
                         positive_fraction=float(np.mean(gain > 0)), median_regret=float(np.median(regret)),
                         mean_regret=float(np.mean(regret)),
                         admissible_without_halving=float(np.mean([c["halving"] == 0 for c in chosen])),
                         median_band=float(np.median([c["band"] for c in chosen])))
    oracle = np.array([r["oracle_gain"] for r in subset])
    out["oracle"] = dict(median_gain=float(np.median(oracle)) if len(oracle) else None,
                         positive_fraction=float(np.mean(oracle > 0)) if len(oracle) else None)
    return out


def qualifies(results, rule):
    """The plan's SC-023 gate: pooled, both gates, lambda=1e-3, physical control.

    A rule's decisions without a choice (validation at f_max=2.5 GHz) are
    compared with the ladder on the same decisions only.
    """
    verdict = {}
    for gate in ("G1", "G2"):
        subset = [r for r in results if r["gate"] == gate and r["damping"] == 1e-3
                  and r["control"] == "physical" and r[rule] is not None]
        regret = np.median([r[rule]["regret"] for r in subset])
        ladder_regret = np.median([r["ladder"]["regret"] for r in subset])
        positive = np.mean([r[rule]["gain"] > 0 for r in subset])
        ladder_positive = np.mean([r["ladder"]["gain"] > 0 for r in subset])
        verdict[gate] = dict(decisions=len(subset), median_regret=float(regret), ladder_median_regret=float(ladder_regret),
                             positive_fraction=float(positive), ladder_positive_fraction=float(ladder_positive),
                             passes=bool(regret <= ladder_regret - 0.05 and positive >= ladder_positive))
    verdict["qualifies"] = all(v["passes"] for v in verdict.values())
    return verdict
