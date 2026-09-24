"""SC-023: numerical qualification (Q0) and conditional band candidates offline.

Q0 reads SC-022's saved trajectories and atlas. Its refinement and
directional checks recompute a few cells (bounded solves). The candidate
study performs no physics solves: every candidate step is a conditional LM
solve on SC-022's stored per-frequency blocks, every finite trial is pure
geometry (the Borges move and arclength refit), and the labels compare trial
curves with the truth. Labels are EVALUATION ONLY: the rules read features
alone, and rules are applied afterwards to the stored table.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import re
import time

import numpy as np

from . import atlas_cases as ac
from . import spd_cases as sc
from .atlas_survey import (band_coordinates, cell, conditional_step, normal_ray_error, predicted_decrease,
                           rms_weights, symmetric_rms_distance)
from .forward import shape_jacobian, solve
from .geometry import FourierCurve, _refit_samples, curvature_tail, displaced, grid_size, normal_basis
from .lm_backend import BackendConfig
from .updates import BorgesUpdate, UpdateRefused, _refusal

ROOT = Path(__file__).resolve().parents[2]
SC022 = ROOT / "results/validation/shape_continuation/SC-022-atlas-survey"
RUNS = tuple((arm, case) for arm in ("borges", "fixed32") for case in ac.CASES)
P = ac.ATLAS_BAND
F_MAX_HZ = tuple(np.round(np.arange(0.5e9, 2.5e9 + 1, 0.25e9)))
DAMPINGS = (1e-4, 1e-3, 1e-2)
CONTROLS = ("coefficient", "physical")
GATES = dict(G1=1e-7, G2=1e-5)
PHYSICAL_BOUND_M = 0.006
HALVINGS = 7


def catalog_index():
    return {f: i for i, f in enumerate(ac.CATALOG_HZ)}


def frequency_sets():
    """Cumulative sets {0.5, ..., f_max} as catalog indices, and the next frequency up (or None)."""
    index = catalog_index()
    sets = []
    for n, f_max in enumerate(F_MAX_HZ):
        members = [index[f] for f in F_MAX_HZ[:n + 1]]
        following = index[F_MAX_HZ[n + 1]] if n + 1 < len(F_MAX_HZ) else None
        sets.append((float(f_max), members, following))
    return sets


def ladder_band(wavenumber, contrast):
    return int(np.floor(3 * max(wavenumber, wavenumber * np.sqrt(contrast))))


def bands(catalog, contrast):
    base = {2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 20, 24, 32, 40, 48}
    index = catalog_index()
    ladder = {ladder_band(catalog[index[f]].wavenumber, contrast) for f in F_MAX_HZ}
    return tuple(sorted(base | {m for m in ladder if m <= P}))


def run_states(arm, case):
    """SC-022 states of one run, in atlas order, with the unique-curve index."""
    folder = SC022 / "runs" / arm / case
    states = ac.atlas_states(folder)
    keys = [s["coefficients"].tobytes() for s in states]
    unique = list(dict.fromkeys(keys))
    return states, [unique.index(k) for k in keys], unique


def tightest_radius_m(curve):
    return float(sc.LENGTH / np.max(np.abs(curve.nodes(8192).curvatures)))


def refit_relative(curve, band):
    count = grid_size(max(curve.band, band))
    if curve.band < band:
        curve = FourierCurve(np.pad(curve.coefficients, (band - curve.band, band - curve.band)))
    _, error = _refit_samples(curve, band, count, 1.0)
    return float(error / (curve.nodes(count).perimeter / (2 * np.pi)))


# --- Q0: numerical qualification ------------------------------------------

def gate_record():
    """Refit-gate diagnosis on every recorded state and refused trial (geometry only)."""
    rows = {}
    for arm, case in RUNS:
        states, _, _ = run_states(arm, case)
        per_state = []
        for s in states:
            curve = FourierCurve(s["coefficients"])
            top = np.abs(curve.coefficients[np.abs(curve.modes) >= curve.band - 16]).max()
            per_state.append(dict(stage=s["stage"], iteration=s["iteration"],
                                  refit_relative_K192=refit_relative(curve, 192),
                                  refit_relative_K384=refit_relative(curve, 384),
                                  top16_fraction=float(top / np.abs(curve.coefficients).max()),
                                  tightest_radius_m=tightest_radius_m(curve),
                                  curvature_tail_above_96=curvature_tail(curve, 96)))
        refused = []
        for number in (1, 2, 3, 4):
            path = SC022 / "runs" / arm / case / f"stage_{number}_history.json"
            if not path.exists():
                continue
            for trial in sc.read(path)["trials"]:
                if trial.get("reason") == "unresolved_projection":
                    refused.append(dict(stage=number, backtrack=trial["backtrack"],
                                        relative=float(re.search(r"([0-9.eE+-]+) relative", trial["detail"]).group(1))))
        counts = {}
        for number in (1, 2, 3, 4):
            path = SC022 / "runs" / arm / case / f"stage_{number}_history.json"
            if path.exists():
                for trial in sc.read(path)["trials"]:
                    key = trial.get("reason") or trial.get("status")
                    counts[key] = counts.get(key, 0) + 1
        rel = np.array([r["relative"] for r in refused]) if refused else np.zeros(0)
        rows[f"{arm}/{case}"] = dict(
            states=per_state, trial_outcomes=counts, refused_projection=refused,
            refused_relative_quantiles=(np.quantile(rel, [0, .1, .5, .9, 1]).tolist() if len(rel) else None),
            refused_at_last_halving_median=(float(np.median([r["relative"] for r in refused
                                                             if r["backtrack"] == HALVINGS]))
                                            if any(r["backtrack"] == HALVINGS for r in refused) else None))
    return rows


QUALIFICATION_STATES = (("borges", "circle_to_c", "end_of_stage_3"), ("borges", "circle_to_star", "final"),
                        ("fixed32", "circle_to_star", "after_first_step"), ("borges", "wrong_circle", "final"))
QUALIFICATION_HZ = (0.5e9, 1.25e9, 2.5e9)


def qualification_state(arm, case, label):
    states, _, _ = run_states(arm, case)
    if label == "final":
        i = len(states) - 1
    elif label == "end_of_stage_3":
        i = max(j for j, s in enumerate(states) if s["stage"] == 3)
    elif label == "after_first_step":
        i = next(j for j, s in enumerate(states) if s["stage"] == 1 and s["iteration"] == 1)
    return i, FourierCurve(states[i]["coefficients"])


def refinement(job):
    """Stored N=512 cell against a fresh N=1024 cell at one state and frequency."""
    arm, case, label, hz = job
    i, curve = qualification_state(arm, case, label)
    catalog, _ = ac.load_case(SC022, case)
    j = catalog_index()[hz]
    atlas = np.load(SC022 / "runs" / arm / case / "atlas.npz")
    stored_G, stored_g = atlas["gauss_newton"][i, j], atlas["gradient"][i, j]
    fine = cell(curve, catalog[j], ac.contrast(), ac.REFINED, P, sc.LENGTH)
    s_stored, s_fine = np.sqrt(np.clip(np.diag(stored_G), 0, None)), fine.sensitivity
    resolved = s_fine >= 1e-6 * s_fine.max()
    steps = {}
    for M in (9, 16, 32, 48):
        keep = band_coordinates(M, P)
        a = conditional_step(stored_G, stored_g, keep, 1e-3)
        b = conditional_step(fine.gauss_newton, fine.gradient, keep, 1e-3)
        steps[str(M)] = float(np.linalg.norm(a - b) / np.linalg.norm(b))
    return dict(arm=arm, case=case, state=label, state_index=i, frequency_hz=hz,
                sensitivity_max_relative_difference_resolved=float(np.max(np.abs(s_stored - s_fine)[resolved]
                                                                         / s_fine[resolved])),
                resolved_coordinates=int(resolved.sum()),
                gradient_relative_difference=float(np.linalg.norm(stored_g - fine.gradient) / np.linalg.norm(fine.gradient)),
                loss_relative_difference=float(abs(atlas["loss"][i, j] - fine.loss) / fine.loss),
                conditional_step_relative_difference=steps,
                passes=bool(np.max(np.abs(s_stored - s_fine)[resolved] / s_fine[resolved]) <= 1e-3
                            and max(steps.values()) <= 1e-2))


def directional(job):
    """Jacobian column against central differences through the actual Borges trial."""
    arm, case, label = job
    i, curve = qualification_state(arm, case, label)
    catalog, _ = ac.load_case(SC022, case)
    observation = catalog[catalog_index()[1.25e9]]
    contrast = ac.contrast()
    update = BorgesUpdate(sc.LENGTH, projection_tolerance=1.0)
    space = update.prepare(curve, P, curve.band)
    state = solve(curve, observation.wavenumber, contrast, observation.acquisition, ac.NODES)
    jacobian = shape_jacobian(state, update.velocities(space, state.curve))  # per metre
    data = np.linalg.norm(observation.scattered)
    epsilon = 1e-6
    rows = []
    for p in (1, 9, 15, 20, 32, 48):
        direction = np.zeros(2 * P + 1)
        direction[p] = epsilon
        predictions = []
        for sign in (1, -1):
            trial, _ = update.trial(space, sign * direction)
            predictions.append(solve(trial, observation.wavenumber, contrast, observation.acquisition,
                                     ac.NODES).prediction)
        difference = (predictions[0] - predictions[1]) / (2 * epsilon)
        column = jacobian[:, p]
        change = np.linalg.norm(column) * epsilon / data
        error = float(np.linalg.norm(difference - column) / np.linalg.norm(column))
        rows.append(dict(harmonic=p, relative_error=error, data_change_relative=float(change),
                         resolvable=bool(change >= 1e-6), passes=bool(change < 1e-6 or error <= 1e-3)))
    return dict(arm=arm, case=case, state=label, state_index=i, frequency_hz=1.25e9, epsilon_m=epsilon, rows=rows)


def run_qualification(output, workers):
    folder = output / "qualification"
    folder.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    sc.write(folder / "gate_record.json", gate_record())
    jobs = [(a, c, s, f) for a, c, s in QUALIFICATION_STATES for f in QUALIFICATION_HZ]
    with ProcessPoolExecutor(workers) as pool:
        refined = list(pool.map(refinement, jobs))
        directions = list(pool.map(directional, QUALIFICATION_STATES))
    sc.write(folder / "refinement.json", refined)
    sc.write(folder / "directional.json", directions)
    summary = dict(seconds=time.perf_counter() - started,
                   refinement_passes=sum(r["passes"] for r in refined), refinement_cells=len(refined),
                   directional_passes=sum(r["passes"] for d in directions for r in d["rows"]),
                   directional_checks=sum(len(d["rows"]) for d in directions))
    sc.write(folder / "summary.json", summary)
    print(json.dumps(summary), flush=True)


# --- SC-023: conditional candidates -----------------------------------------

_W = {}


def _init():
    _W.update(contrast=ac.contrast(), update=BorgesUpdate(sc.LENGTH, projection_tolerance=1.0),
              config=BackendConfig(), atlases={}, truths={}, catalogs={})


def _case_data(arm, case):
    key = (arm, case)
    if key not in _W["atlases"]:
        atlas = np.load(SC022 / "runs" / arm / case / "atlas.npz")
        _W["atlases"][key] = {k: atlas[k] for k in ("gauss_newton", "gradient", "loss")}
        catalog, truth = ac.load_case(SC022, case)
        _W["catalogs"][case] = catalog
        # Normal rays use the fine polygon; distances use 8192 points (chord error ~4e-9 m).
        _W["truths"][case] = (truth.values(16384), truth.values(8192))
    return _W["atlases"][key], _W["catalogs"][case], _W["truths"][case]


def _trial(space, step):
    """Geometry of one finite trial: (curve or None, refusal reason, projection relative error)."""
    try:
        moved = displaced(space.curve, step / sc.LENGTH, space.curve_modes, projection_tolerance=1.0)
    except ValueError as exc:
        return None, _refusal(exc).reason, float("nan")
    # As the gate in `geometry._refit_samples`: relative to the moved curve's perimeter / 2 pi.
    scale = moved.shape.nodes(grid_size(moved.shape.band)).perimeter / (2 * np.pi)
    return moved.shape, None, float(moved.projection_error / scale)


def candidates(job):
    """All candidates at one unique state of one run. Returns flat rows (features + labels)."""
    arm, case, state_index = job
    atlas, catalog, (truth, coarse) = _case_data(arm, case)
    states, _, _ = run_states(arm, case)
    curve = FourierCurve(states[state_index]["coefficients"])
    update, config, contrast = _W["update"], _W["config"], _W["contrast"]
    error, error_summary = normal_ray_error(curve, truth, P, sc.LENGTH)
    before = symmetric_rms_distance(curve, coarse, sc.LENGTH, 2048)
    radius_before = tightest_radius_m(curve)
    weights = rms_weights(P)
    beyond2 = error_summary["beyond_band_rms_m"] ** 2
    error_norm = np.sqrt(np.sum(weights * error ** 2) + beyond2)
    G_all, g_all, loss_all = atlas["gauss_newton"][state_index], atlas["gradient"][state_index], atlas["loss"][state_index]
    band_list = bands(catalog, contrast)
    rows, distance_cache = [], {}

    def distance(shape):
        key = shape.coefficients.tobytes()
        if key not in distance_cache:
            distance_cache[key] = (symmetric_rms_distance(shape, coarse, sc.LENGTH, 2048), tightest_radius_m(shape))
        return distance_cache[key]

    for f_max, members, following in frequency_sets():
        G, g, loss = G_all[members].mean(0), g_all[members].mean(0), float(loss_all[members].mean())
        for damping in DAMPINGS:
            full = conditional_step(G, g, band_coordinates(P, P), damping)
            full_decrease = predicted_decrease(G, g, full)
            for M in band_list:
                keep = band_coordinates(M, P)
                q = conditional_step(G, g, keep, damping)
                H = G[np.ix_(keep, keep)]
                D = np.diag(np.maximum(np.diag(H), 1.0))
                dof = float(np.trace(np.linalg.solve(H + damping * D, H)) / len(keep))
                decrease = predicted_decrease(G, g, q)
                validation = (None if following is None else
                              predicted_decrease(G_all[following], g_all[following], q) / float(loss_all[following]))
                first_order = 1 - np.sqrt(np.sum(weights * (error - q) ** 2) + beyond2) / error_norm
                space = update.prepare(curve, M, curve.band)
                local = q[keep]
                size = update.measure(space, local)
                base = dict(arm=arm, case=case, state=state_index, stage=states[state_index]["stage"],
                            f_max_hz=f_max, frequencies=len(members), band=M, damping=damping,
                            loss=loss, predicted_fraction=decrease / loss, capture=decrease / full_decrease,
                            validation_fraction=validation, dof_ratio=dof,
                            raw_maximum_normal_m=size["maximum_normal_m"], raw_rms_normal_m=size["rms_normal_m"],
                            first_order_gain=float(first_order), distance_before_m=before,
                            radius_before_m=radius_before, normal_ray_coverage=error_summary["coverage"])
                for control in CONTROLS:
                    if control == "coefficient":
                        bound = config.bounds(space.orders)
                        proposal = np.clip(local, -bound, bound)
                    else:
                        proposal = local * min(1.0, PHYSICAL_BOUND_M / size["maximum_normal_m"]) \
                            if size["maximum_normal_m"] > 0 else local
                    first = {name: None for name in GATES}
                    reasons = []
                    for halving in range(HALVINGS + 1):
                        shape, reason, relative = _trial(space, 0.5 ** halving * proposal)
                        reasons.append(reason or ("projection" if relative > GATES["G1"] else "ok"))
                        for name, tolerance in GATES.items():
                            if first[name] is None and shape is not None and relative <= tolerance:
                                first[name] = (halving, shape)
                        if first["G1"] is not None:
                            break
                    for name in GATES:
                        row = dict(base, control=control, gate=name, trial_reasons=reasons)
                        if first[name] is None:
                            row.update(admissible=False, halving=None, gain=0.0, distance_after_m=before,
                                       radius_after_m=radius_before)
                        else:
                            after, radius = distance(first[name][1])
                            row.update(admissible=True, halving=first[name][0], gain=1 - after / before,
                                       distance_after_m=after, radius_after_m=radius)
                        rows.append(row)
    return rows


def run_candidates(output, workers):
    folder = output / "candidates"
    folder.mkdir(parents=True, exist_ok=True)
    jobs = []
    for arm, case in RUNS:
        states, index, unique = run_states(arm, case)
        first = {}
        for i, u in enumerate(index):
            first.setdefault(u, i)
        jobs += [(arm, case, i) for i in sorted(first.values())]
    started = time.perf_counter()
    with ProcessPoolExecutor(workers, initializer=_init) as pool, \
            gzip.open(folder / "rows.jsonl.gz", "wt") as sink:
        for done, rows in enumerate(pool.map(candidates, jobs, chunksize=1), 1):
            for row in rows:
                sink.write(json.dumps(row) + "\n")
            if done % 10 == 0:
                print(json.dumps(dict(done=done, of=len(jobs), seconds=time.perf_counter() - started)), flush=True)
    sc.write(folder / "summary.json", dict(states=len(jobs), seconds=time.perf_counter() - started, workers=workers,
                                           rows_sha256=ac.digest(folder / "rows.jsonl.gz")))


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    reference = sc.read(SC022 / "manifest.json")
    summaries = {f"{a}/{c}": sc.read(SC022 / "runs" / a / c / "atlas_summary.json") for a, c in RUNS}
    for key, summary in summaries.items():
        arm, case = key.split("/")
        for name, field in (("atlas.npz", "atlas_sha256"), ("true_error_EVALUATION_ONLY.npz", "true_error_sha256")):
            if ac.digest(SC022 / "runs" / arm / case / name) != summary[field]:
                raise RuntimeError(f"SC-022 artifact changed: {key}/{name}")
    sc.write(output / "manifest.json", dict(
        experiment="SC-023", plan="docs/iterations/shape_frequency_continuation/iteration_08/03_plan.md",
        reads="SC-022-atlas-survey (atlas and evaluation files, hashes verified)",
        sc022_input_sha256=reference["inputs"],
        sc022_atlas_sha256={k: v["atlas_sha256"] for k, v in summaries.items()},
        factors=dict(f_max_hz=F_MAX_HZ, dampings=DAMPINGS, controls=CONTROLS, gates=GATES,
                     physical_step_bound_m=PHYSICAL_BOUND_M, halvings=HALVINGS),
        source_sha256=sc.source_hashes(), prepared=time.strftime("%Y-%m-%dT%H:%M:%S%z")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--qualification", action="store_true")
    parser.add_argument("--candidates", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.output)
    if args.qualification:
        run_qualification(args.output, args.workers)
    if args.candidates:
        run_candidates(args.output, args.workers)


if __name__ == "__main__":
    main()
