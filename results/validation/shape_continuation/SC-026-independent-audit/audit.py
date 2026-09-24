"""Independent, read-only SC-026 audit; run from the repository root."""
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from experiments.shape_continuation import atlas_dataset as ad
from experiments.shape_continuation import spd_cases as sc


def main():
    source = ad.BASE / "SC-026-atlas-dataset"
    index = sc.read(source / "index.json")
    manifest = sc.read(source / "manifest.json")
    summary = sc.read(source / "summary.json")
    checks = {name: ad.digest(source / name) == expected
              for name, expected in summary["files_sha256"].items()}
    inputs = {name: ad.digest(ad.BASE / name) == expected
              for name, expected in manifest["inputs"].items()}
    recollected = ad.collect()
    assert len(recollected) == len(index) == 1286
    assert all(checks.values()) and all(inputs.values())
    assert {(r["case"], r["state_key"]) for r in index} == set(recollected)
    cases, worst, counts = {}, dict(gauss_newton=0., gradient=0., loss=0.), Counter()
    occurrences = {}
    for row in index:
        for o in row["occurrences"]:
            occurrences[o["run"], o["stage"], o["iteration"]] = row["state_key"]
    old = {}
    for case in ad.INPUTS:
        with np.load(source / "cells" / f"{case}.npz") as cells, np.load(
                source / "evaluation" / f"{case}_EVALUATION_ONLY.npz") as ev:
            keys = cells["state_key"]
            assert np.array_equal(keys, ev["state_key"])
            assert all(np.isfinite(cells[k]).all() for k in ad.CELL_FIELDS)
            J, residual = cells["jacobian"], cells["residual"]
            assert J.shape == (len(keys), 19, 48, 97)
            np.testing.assert_allclose(cells["loss"], .5 * np.sum(residual**2, axis=-1), rtol=1e-14)
            members = [r for r in index if r["case"] == case]
            for row in members:
                i = row["row"]
                assert keys[i] == row["state_key"] == ad.curve_key(cells["coefficients"][i])
                assert row["occurrences"] == recollected[case, row["state_key"]]["occurrences"]
                for o in row["occurrences"]:
                    counts[o["source"]] += 1
                    if o["source"] != "SC022":
                        continue
                    if o["run"] not in old:
                        old[o["run"]] = np.load(ad.BASE / o["run"] / "atlas.npz")
                    a = old[o["run"]]
                    n, = np.flatnonzero((a["stage"] == o["stage"]) & (a["iteration"] == o["iteration"]))
                    for name, value in (("gauss_newton", np.einsum("fri,frj->fij", J[i], J[i])),
                                        ("gradient", np.einsum("fri,fr->fi", J[i], residual[i])),
                                        ("loss", cells["loss"][i])):
                        relative = np.linalg.norm(value-a[name][n]) / max(np.linalg.norm(a[name][n]), 1e-300)
                        worst[name] = max(worst[name], float(relative))
            cases[case] = dict(states=len(keys), occurrences=sum(len(r["occurrences"]) for r in members),
                rough_radius_lt_4mm=int(np.sum(ev["tightest_radius_m"] < .004)),
                ray_coverage_min=float(ev["normal_ray_coverage"].min()),
                ray_coverage_below_99pct=int(np.sum(ev["normal_ray_coverage"] < .99)),
                ray_misaligned_max=float(ev["normal_ray_misaligned"].max()))
    assert max(worst.values()) < 1e-12
    steps = sc.read(source / "analysis_steps.json")
    unique = {}
    for row in steps:
        run, stage, it = row["run"], row["stage"], row["iteration"]
        previous = max(i for r, s, i in occurrences if r == run and s == stage and i < it)
        signature = (row["case"], stage, row["band"], occurrences[run, stage, previous], occurrences[run, stage, it])
        unique.setdefault(signature, row)
    by_case = {}
    for case in cases:
        rows = [r for r in unique.values() if r["case"] == case]
        bad = [r for r in rows if r["pathological_sharpening"]]
        by_case[case] = dict(unique_steps=len(rows), pathological=len(bad),
            pathological_by_stage=dict(Counter(r["stage"] for r in bad)))
    ratio = [r["distance_after_mm"]/r["distance_before_mm"] for r in unique.values()]
    rho = [r["relative_sensitivity"] for r in unique.values()]
    nexts = sc.read(source / "analysis_next_frequency.json")
    agreements = {c: float(np.mean([r["cosine"] >= 0 for r in nexts if r["case"] == c])) for c in cases}
    report = dict(dataset_commit="9b8918c54928ed492b479f7f693fcbeb4c113237", passed=True,
        artifact_hashes=checks, input_hashes=inputs, unique_states=len(index),
        state_records=sum(counts.values()), records_by_source=dict(counts),
        cases=cases, independently_recomputed_SC022_relative_error=worst,
        steps_occurrences=len(steps), unique_transitions=len(unique), unique_transition_by_case=by_case,
        unique_transition_spearman_sensitivity_vs_error_ratio=float(spearmanr(rho, ratio).statistic),
        next_frequency_agreement_by_case=agreements,
        next_frequency_agreement_case_mean=float(np.mean(list(agreements.values()))),
        notes=["No p-values: repeated states and related trajectories are not independent observations.",
               "Frontier uses individual Jacobian column norms, not conditional joint identifiability.",
               "Original noise threshold is sigma=0.001 per real normalized component, not per-channel relative noise.",
               "Ray-layer shares need coverage/misalignment checks; geometric endpoint metrics remain primary."])
    sc.write(Path(__file__).with_name("audit.json"), report)
    print(json.dumps({k:v for k,v in report.items() if k not in ("artifact_hashes", "input_hashes")}))
    for a in old.values():
        a.close()


if __name__ == "__main__":
    main()
