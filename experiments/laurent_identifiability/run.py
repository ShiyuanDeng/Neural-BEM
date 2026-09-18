"""LAU-005: sweep calibration uncertainty through the Fisher bound and the inverse.

Stage A sweeps every configuration of the recorded neighbour screen, so the
crossover calibration precision is reported as a distribution rather than from
the two hand-selected cases. Stage B runs matched nonlinear recoveries at a few
calibration scales, plus one bridge arm that is literally the recorded study's
free-gain inverse.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy

from experiments.laurent_calibration.design import uniform_plan
from experiments.laurent_calibration.model import apply_gains
from experiments.laurent_calibration.run import INITIALS, PRIOR_POINTS, TRUTHS, relative, save
from experiments.laurent_neighbour.model import Body, Evaluator, bodies_at, oracle
from experiments.laurent_neighbour.run import ARMS, NEIGHBOUR_PRIORS, NEIGHBOUR_TRUTHS
from experiments.laurent_neighbour.run import qualify as neighbour_qualify
from .model import (DECIBELS_PER_TAU, DEGREES_PER_TAU, GAIN_SD, crossover_tau, fit,
                    marginal_gram, radial_rms_crlb_mm)

SCREEN = Path("results/experiments/laurent_neighbour_20260916/screen.json")
OUTPUT = Path("results/validation/laurent/LAU-005-20260918-calibration-sweep-01")
TAUS = np.r_[0., np.logspace(-3, 2, 26), np.inf]
# Calibration scales carried into the nonlinear stage, with the study's own
# free-gain inverse as the bridge back to its published medians.
SETTINGS = [(0., "matched"), (.03, "matched"), (.1, "matched"), (.3, "matched"),
            (1., "matched"), (1., "flat")]
BUDGET = dict(fits=1400, oracles=700, seconds=3600)


class Ledger:
    """Charge before the operation, as the track's budget rule requires."""
    def __init__(self, budget):
        self.budget, self.used = budget, dict(fits=0, oracles=0)
        self.tick = perf_counter()

    def charge(self, kind, count=1):
        self.used[kind] += count
        if self.used[kind] > self.budget[kind]:
            raise RuntimeError(f"Budget exhausted: {kind} {self.used[kind]}>{self.budget[kind]}")
        if perf_counter()-self.tick > self.budget["seconds"]:
            raise RuntimeError("Wall-clock budget exhausted")

    def record(self):
        return dict(self.used, seconds=perf_counter()-self.tick, budget=self.budget)


def fields(bodies, x):
    out = {}
    for name, interactions in (("coupled", True), ("additive", False)):
        ev = Evaluator(bodies, interactions=interactions)
        out[name] = (ev.forward(x), ev.jacobian(x))
    return out


def arm_curves(fields_by_world, absent, mask, sigma, taus):
    """One CRLB curve per arm of the recorded screen, over the calibration grid."""
    curves = {"absent": [radial_rms_crlb_mm(marginal_gram(*absent, mask, sigma, t)[0]) for t in taus]}
    for world, (y, jac) in fields_by_world.items():
        for known in (False, True):
            name = f"{'known' if known else 'unknown'}_{world}"
            curves[name] = [radial_rms_crlb_mm(
                marginal_gram(y, jac, mask, sigma, t, neighbour_unknown=not known)[0]) for t in taus]
    return curves


def sweep(output, ledger):
    """Stage A. Endpoints are checked against the recorded screen, one by one."""
    tick = perf_counter()
    record = json.loads(SCREEN.read_text())
    mask, sigma = uniform_plan(), np.array(record["sigma"])
    absent = []
    for p in PRIOR_POINTS:
        ev = Evaluator([Body()])
        absent.append((ev.forward(p), ev.jacobian(p)))
    rows, endpoint_errors, monotone_violations = [], [], []
    for candidate in record["candidates"]:
        bodies = bodies_at(candidate["distance_m"], np.deg2rad(candidate["angle_degrees"]), candidate["epsr"])
        priors = []
        for pi, (target, neighbour) in enumerate(zip(PRIOR_POINTS, NEIGHBOUR_PRIORS)):
            by_world = fields(bodies, np.r_[target, neighbour])
            curves = arm_curves(by_world, absent[pi], mask, sigma, TAUS)
            recorded = candidate["priors"][pi]["arms"]
            for name, values in curves.items():
                series = np.array(values)
                violation = float(np.min(np.diff(series)/np.maximum(series[:-1], 1e-300)))
                if violation < -1e-9:
                    monotone_violations.append(dict(candidate=candidate["neighbour_center"], prior=pi,
                                                    arm=name, relative_decrease=violation))
                if name == "absent":
                    continue
                endpoint_errors.append(dict(arm=name, prior=pi,
                    distance_m=candidate["distance_m"], angle_degrees=candidate["angle_degrees"],
                    epsr=candidate["epsr"],
                    free_gain=abs(series[-1]/recorded[name]["radial_rms_crlb_mm"]-1),
                    known_gain=abs(series[0]/recorded[name]["known_gain_radial_rms_crlb_mm"]-1)))

            def bound(tau, by_world=by_world):
                return tuple(radial_rms_crlb_mm(marginal_gram(*by_world[k], mask, sigma, tau)[0])
                             for k in ("coupled", "additive"))

            tau = crossover_tau(bound)
            priors.append(dict(curves={k: list(map(float, v)) for k, v in curves.items()},
                crossover_tau=tau,
                crossover_decibels=None if tau is None else tau*DECIBELS_PER_TAU,
                crossover_degrees=None if tau is None else tau*DEGREES_PER_TAU,
                coupled_over_additive_free=float(curves["unknown_additive"][-1]/curves["unknown_coupled"][-1]),
                coupled_over_additive_exact=float(curves["unknown_additive"][0]/curves["unknown_coupled"][0])))
        rows.append(dict(distance_m=candidate["distance_m"], angle_degrees=candidate["angle_degrees"],
                         epsr=candidate["epsr"], neighbour_center=candidate["neighbour_center"],
                         priors=priors))
    worst = dict(free_gain=max(e["free_gain"] for e in endpoint_errors),
                 known_gain=max(e["known_gain"] for e in endpoint_errors))
    crossings = [p["crossover_tau"] for r in rows for p in r["priors"] if p["crossover_tau"] is not None]
    missing = sum(1 for r in rows for p in r["priors"] if p["crossover_tau"] is None)
    result = dict(taus=[None if np.isinf(t) else float(t) for t in TAUS],
        free_gain_endpoint_is_last=True, gain_sd=GAIN_SD,
        decibels_per_tau=DECIBELS_PER_TAU, degrees_per_tau=DEGREES_PER_TAU,
        configurations=len(rows), priors_per_configuration=len(PRIOR_POINTS),
        worst_endpoint_relative_error=worst, monotone_violations=monotone_violations,
        crossover_summary=dict(count=len(crossings), missing=missing,
            median_tau=float(np.median(crossings)) if crossings else None,
            quartiles=[float(v) for v in np.percentile(crossings, [25, 75])] if crossings else None,
            range=[float(min(crossings)), float(max(crossings))] if crossings else None,
            median_decibels=float(np.median(crossings)*DECIBELS_PER_TAU) if crossings else None,
            median_degrees=float(np.median(crossings)*DEGREES_PER_TAU) if crossings else None),
        rows=rows, seconds=perf_counter()-tick,
        note="Local Fisher bounds on the recorded screen's configurations and prior shapes. "
             "Selection of the two named configurations is inherited from the neighbour study, not redone.")
    save(output/"sweep.json", result)
    print("sweep", json.dumps({k: result[k] for k in ("configurations", "worst_endpoint_relative_error")}),
          "crossover", json.dumps(result["crossover_summary"]), flush=True)
    if max(worst.values()) > 1e-8:
        raise RuntimeError(f"Endpoint reproduction failed: {worst}")
    if monotone_violations:
        raise RuntimeError(f"Non-monotone information curves: {len(monotone_violations)}")
    return result


def predicted(bodies, mask, sigma, tau):
    """Fisher ordering at the nominal prior point, for comparison with recovery."""
    by_world = fields(bodies, np.r_[PRIOR_POINTS[0], NEIGHBOUR_PRIORS[0]])
    ev = Evaluator([Body()])
    absent = (ev.forward(PRIOR_POINTS[0]), ev.jacobian(PRIOR_POINTS[0]))
    curves = arm_curves(by_world, absent, mask, sigma, [tau])
    return {k: float(v[0]) for k, v in curves.items()}


def recover(output, ledger, record, seeds=10, max_nfev=180):
    """Stage B. One standard-normal gain draw per seed, rescaled by each tau."""
    s = record["selected"]
    bodies = bodies_at(s["distance_m"], np.deg2rad(s["angle_degrees"]), s["epsr"])
    mask, sigma = uniform_plan(), np.array(record["sigma"])
    clean_by_scene = []
    for target, neighbour in zip(TRUTHS, NEIGHBOUR_TRUTHS):
        truth = np.r_[target, neighbour]
        ledger.charge("oracles", 3)
        clean_by_scene.append({"absent": oracle(bodies[:1], target), "coupled": oracle(bodies, truth),
                               "additive": oracle(bodies, truth, interactions=False)})
    records = []
    for tau, variant in SETTINGS:
        for si, (target, neighbour) in enumerate(zip(TRUTHS, NEIGHBOUR_TRUTHS)):
            clean = clean_by_scene[si]
            for seed_index in range(seeds):
                seed = 8300+100*si+seed_index
                rng = np.random.default_rng(seed)
                draw = rng.normal(size=(2, 2, 23))
                draw[:, 0] *= GAIN_SD[0]
                draw[:, 1] *= GAIN_SD[1]
                gains = tau*draw
                noise = sigma[:, None, None]*(rng.normal(size=clean["absent"].shape)
                                              + 1j*rng.normal(size=clean["absent"].shape))
                data = {k: apply_gains(v, gains)+noise for k, v in clean.items()}
                for name in ARMS:
                    absent, known = name == "absent", name.startswith("known_")
                    interactions = not name.endswith("additive")
                    key = "absent" if absent else ("coupled" if interactions else "additive")
                    actual = bodies[:1] if absent else bodies
                    prior = None if variant == "flat" else tau
                    starts = []
                    for ti, start in enumerate(INITIALS):
                        ns = neighbour if known else (np.zeros(8) if ti == 0
                             else np.array([-.2, .2, -.2, .2, -.2, .1, .2, -.4]))
                        ledger.charge("fits")
                        starts.append(fit(actual, mask, data[key], sigma,
                            start if absent else np.r_[start, ns], interactions=interactions,
                            neighbour_known=known, gain_prior=prior, max_nfev=max_nfev))
                    selected = int(np.argmin([r["cost"] for r in starts]))
                    best = starts[selected]
                    p = np.array(best["parameters"])
                    delta = p[:8]-target
                    error = float(np.sqrt(2)*np.linalg.norm(delta[3:7]))
                    ledger.charge("oracles")
                    reference = oracle(actual, p, interactions=interactions)
                    check = relative(Evaluator(actual, interactions=interactions).forward(p), reference)
                    if check > 1e-8:
                        raise RuntimeError(f"Recovered state fails full-boundary check: {check}")
                    fitted = np.array(best["gains"]).reshape(2, 2, 23)
                    heldout = relative(apply_gains(reference, fitted)[:, ~mask],
                                       apply_gains(clean[key], gains)[:, ~mask])
                    boundary = actual[0].chart.boundary(p[:8])-actual[0].chart.boundary(target)
                    records.append(dict(tau=tau, variant=variant, scene=si, seed=seed, method=name,
                        trials=starts, selected_start=selected, shape_harmonic_radial_rms_mm=error,
                        corresponding_boundary_rms_mm=float(1000*np.sqrt(np.mean(abs(boundary)**2))),
                        center_error_mm=float(10*np.linalg.norm(delta[:2])),
                        radius_error_mm=float(2*abs(delta[2])),
                        permittivity_error=float(abs(actual[0].permittivity(p[:8])-actual[0].permittivity(target))),
                        gain_rms=float(np.sqrt(np.mean(gains**2))), heldout_field_error=heldout,
                        oracle_forward_error=check, recovered=bool(best["success"] and error < .5)))
                print("recover", f"tau={tau}", variant, si, seed_index, name,
                      round(error, 4), best["success"], best["nfev"], flush=True)
            save(output/"recoveries.json", records)
    save(output/"recoveries.json", records)
    return records


def bootstrap(pairs, scenes, seed=20260918, draws=4000):
    """Resample seeds within each fixed shape pair, as the neighbour study does."""
    rng = np.random.default_rng(seed)
    pairs, scenes = np.asarray(pairs), np.asarray(scenes)
    means = []
    for _ in range(draws):
        picked = []
        for s in np.unique(scenes):
            idx = np.flatnonzero(scenes == s)
            picked.append(pairs[rng.choice(idx, len(idx))])
        means.append(np.concatenate(picked).mean())
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def summarise(output, record, records):
    s = record["selected"]
    bodies = bodies_at(s["distance_m"], np.deg2rad(s["angle_degrees"]), s["epsr"])
    mask, sigma = uniform_plan(), np.array(record["sigma"])
    rows, comparisons = [], []
    for tau, variant in SETTINGS:
        bound = predicted(bodies, mask, sigma, np.inf if variant == "flat" else tau)
        for name in ARMS:
            subset = [r for r in records if r["tau"] == tau and r["variant"] == variant and r["method"] == name]
            error = np.array([r["shape_harmonic_radial_rms_mm"] for r in subset])
            bests = [r["trials"][r["selected_start"]] for r in subset]
            rows.append(dict(tau=tau, variant=variant, method=name, cases=len(subset),
                decibels=tau*DECIBELS_PER_TAU, degrees=tau*DEGREES_PER_TAU,
                median_shape_rms_mm=float(np.median(error)),
                ensemble_shape_rms_mm=float(np.sqrt(np.mean(error**2))),
                max_shape_rms_mm=float(error.max()),
                recovered=int(sum(r["recovered"] for r in subset)),
                converged=int(sum(b["success"] for b in bests)),
                median_heldout_field_error=float(np.median([r["heldout_field_error"] for r in subset])),
                fisher_crlb_mm=bound[name],
                physical_bound_hits=int(sum(any(k < b["active_physical_count"] for k in b["active_bounds"])
                                            for b in bests))))
        for left, right in (("unknown_coupled", "unknown_additive"), ("unknown_additive", "absent"),
                            ("unknown_coupled", "absent")):
            def pick(arm):
                return {(r["scene"], r["seed"]): r["shape_harmonic_radial_rms_mm"] for r in records
                        if r["tau"] == tau and r["variant"] == variant and r["method"] == arm}
            a, b = pick(left), pick(right)
            keys = sorted(set(a) & set(b))
            diff = np.array([a[k]-b[k] for k in keys])
            comparisons.append(dict(tau=tau, variant=variant, comparison=f"{left} minus {right}",
                cases=len(keys), paired_mean_mm=float(diff.mean()),
                bootstrap_95=bootstrap(diff, [k[0] for k in keys]),
                lower_error_cases=int((diff < 0).sum()),
                fisher_ratio=float(bound[right]/bound[left])))
    summary = dict(rows=rows, comparisons=comparisons, settings=[list(x) for x in SETTINGS],
        arms=list(ARMS), seeds_per_scene=len({r["seed"] for r in records})//2, shape_pairs=2,
        initializations=2, selected_configuration=s,
        note="tau scales the study's own truth gain scale; the truth gains at every tau are the "
             "same standard-normal draw rescaled, so the sweep is paired across calibration levels. "
             "The flat variant is the recorded study's free-gain inverse, unchanged.")
    save(output/"summary.json", summary)
    print(json.dumps(rows, indent=2), flush=True)
    return summary


def source_hashes():
    paths = sorted(p for root in ["experiments/laurent_identifiability", "experiments/laurent_neighbour",
        "experiments/laurent_calibration", "experiments/modal_muller_research",
        "solvers/gpr_bem_kress", "solvers/ordered_boundary"] for p in Path(root).glob("*.py"))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def manifest(output, ledger, extra):
    save(output/"manifest.json", dict(
        experiment="LAU-005", git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        threads={k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        ledger=ledger.record(), source_sha256=source_hashes(), **extra))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--stage", choices=("sweep", "recover", "all"), default="all")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--max-nfev", type=int, default=180)
    args = parser.parse_args()
    ledger = Ledger(BUDGET)
    record = json.loads((Path("results/experiments/laurent_neighbour_20260916/coupling_control")/"screen.json").read_text())
    if args.stage in ("sweep", "all"):
        sweep(args.output, ledger)
    if args.stage in ("recover", "all"):
        neighbour_qualify(args.output, record)
        records = recover(args.output, ledger, record, args.seeds, args.max_nfev)
        summarise(args.output, record, records)
    manifest(args.output, ledger, dict(stage=args.stage, seeds=args.seeds, max_nfev=args.max_nfev))


if __name__ == "__main__":
    main()
