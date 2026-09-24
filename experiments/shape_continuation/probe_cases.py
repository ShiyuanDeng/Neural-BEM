"""SC-024(b): execute rule-chosen steps at recorded states with real solves.

At four recorded states per SC-022 run (start, end of stage 1, end of stage
2, final), each rule's band from SC-023 (and the oracle band) gives one
conditional LM step at lambda=1e-3 with physical control, halved to the
first geometrically admissible trial under the as-run refit gate (G1). The
step is executed: production solves on the stage's frequencies give the
realized decrease of the stage objective against the Gauss-Newton model's
prediction, and refined solves give the backend's acceptance verdict. No
truth enters any step; the geometric gain comes from SC-023's
evaluation-only table.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time

import numpy as np

from . import atlas_cases as ac
from . import conditional_rules as cr
from . import conditional_study as cs
from . import spd_cases as sc
from .atlas_survey import band_coordinates, conditional_step, predicted_decrease
from .forward import solve
from .geometry import FourierCurve
from .lm_backend import BackendConfig, acceptance, normalize
from .updates import BorgesUpdate

DAMPING, CONTROL, GATE = 1e-3, "physical", "G1"
STAGE_F_MAX = {1: 0.5e9, 2: 0.75e9, 3: 1.0e9, 4: 1.25e9}


def probe_states(arm, case):
    states, _, _ = cs.run_states(arm, case)
    picks = dict(start=0)
    for number, label in ((1, "end_of_stage_1"), (2, "end_of_stage_2")):
        rows = [i for i, s in enumerate(states) if s["stage"] == number]
        if rows:
            picks[label] = rows[-1]
    picks["final"] = len(states) - 1
    return states, picks


def stage_loss(curve, observations, contrast, nodes):
    predictions = np.column_stack([solve(curve, o.wavenumber, contrast, o.acquisition, nodes).prediction
                                   for o in observations])
    observed = np.column_stack([o.scattered for o in observations])
    weights = np.ones(len(observations)) / len(observations)
    residual = normalize(predictions - observed, observed, weights, BackendConfig().residual_floor)
    return 0.5 * float(residual @ residual)


def probe(job):
    """One (run, state) with several bands; returns one row per distinct band."""
    arm, case, label, index, stage, band_sources = job
    states, _ = probe_states(arm, case)
    curve = FourierCurve(states[index]["coefficients"])  # `stage` is the label's stage, not the first occurrence's
    catalog, _ = ac.load_case(cs.SC022, case)
    contrast = ac.contrast()
    position = cs.catalog_index()
    members = [position[f] for f in cs.F_MAX_HZ if f <= STAGE_F_MAX[stage] + 1]
    observations = [catalog[j] for j in members]
    atlas = np.load(cs.SC022 / "runs" / arm / case / "atlas.npz")
    G = atlas["gauss_newton"][index, members].mean(0)
    g = atlas["gradient"][index, members].mean(0)
    update = BorgesUpdate(sc.LENGTH)  # the as-run gate, 1e-7
    config = BackendConfig()
    base_production = stage_loss(curve, observations, contrast, ac.NODES)
    base_refined = stage_loss(curve, observations, contrast, ac.REFINED)
    rows = []
    for band, sources in sorted(band_sources.items()):
        keep = band_coordinates(band, cs.P)
        q = conditional_step(G, g, keep, DAMPING)
        space = update.prepare(curve, band, curve.band)
        local = q[keep]
        size = update.measure(space, local)["maximum_normal_m"]
        proposal = local * min(1.0, cs.PHYSICAL_BOUND_M / size) if size > 0 else local
        row = dict(arm=arm, case=case, state=label, state_index=index, stage=stage, band=band, rules=sources,
                   frequencies_hz=[float(ac.CATALOG_HZ[j]) for j in members],
                   base_loss=base_production, base_refined_loss=base_refined)
        for halving in range(cs.HALVINGS + 1):
            step = 0.5 ** halving * proposal
            try:
                trial, geometry = update.trial(space, step)
            except Exception as exc:  # UpdateRefused: try the next halving, as the backend does
                continue
            full = np.zeros(2 * cs.P + 1)
            full[keep] = step
            predicted = predicted_decrease(G, g, full)
            production = stage_loss(trial, observations, contrast, ac.NODES)
            refined = stage_loss(trial, observations, contrast, ac.REFINED)
            verdict = acceptance(base_production, production, base_refined, refined, config)
            row.update(halving=halving, maximum_normal_m=geometry["maximum_normal_m"],
                       predicted_decrease=predicted, realized_decrease=base_production - production,
                       ratio=(base_production - production) / predicted if predicted > 0 else None,
                       strict_decrease=bool(production < base_production),
                       backend_accepts=bool(production < base_production and verdict["accepted"]),
                       refined_decrease=base_refined - refined)
            break
        else:
            row.update(halving=None, backend_accepts=False, note="no geometrically admissible halving")
        rows.append(row)
    return rows


def jobs_from(candidate_rows):
    results = cr.evaluate(candidate_rows, ladder_bands(candidate_rows))
    table = {}
    for r in results:
        if r["damping"] == DAMPING and r["control"] == CONTROL and r["gate"] == GATE:
            table[(r["arm"], r["case"], r["state"], r["f_max_hz"])] = r
    jobs = []
    for arm, case in cs.RUNS:
        _, picks = probe_states(arm, case)
        states, index, _ = cs.run_states(arm, case)
        first = {}
        for i, u in enumerate(index):
            first.setdefault(u, i)
        for label, i in picks.items():
            unique_index = first[index[i]]  # SC-023 evaluated the first occurrence of each curve
            decision = table[(arm, case, unique_index, STAGE_F_MAX[states[i]["stage"]])]
            sources = {}
            for name in [*cr.RULES, "oracle"]:
                band = decision["oracle_band"] if name == "oracle" else (decision[name] or {}).get("band")
                if band is not None:
                    sources.setdefault(band, []).append(name)
            jobs.append((arm, case, label, unique_index, states[i]["stage"], sources))
    return jobs


def ladder_bands(candidate_rows):
    catalog, _ = ac.load_case(cs.SC022, "wrong_circle")
    position = cs.catalog_index()
    contrast = ac.contrast()
    return {f: cs.ladder_band(catalog[position[f]].wavenumber, contrast) for f in cs.F_MAX_HZ}


def run(output, candidates_path, workers):
    folder = output / "probes"
    folder.mkdir(parents=True, exist_ok=False)
    jobs = jobs_from(cr.load(candidates_path))
    sc.write(folder / "manifest.json", dict(experiment="SC-024(b)", candidates=str(candidates_path),
             candidates_sha256=ac.digest(candidates_path), damping=DAMPING, control=CONTROL, gate=GATE,
             jobs=[dict(arm=a, case=c, state=l, state_index=i, stage=st, bands={str(k): v for k, v in s.items()})
                   for a, c, l, i, st, s in jobs],
             source_sha256=sc.source_hashes(), started=time.strftime("%Y-%m-%dT%H:%M:%S%z")))
    started = time.perf_counter()
    rows = []
    with ProcessPoolExecutor(workers) as pool:
        for result in pool.map(probe, jobs):
            rows += result
            print(json.dumps(dict(done=len(rows), seconds=time.perf_counter() - started)), flush=True)
    sc.write(folder / "rows.json", rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    run(args.output, args.candidates, args.workers)


if __name__ == "__main__":
    main()
