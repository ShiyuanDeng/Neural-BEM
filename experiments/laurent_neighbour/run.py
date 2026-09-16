"""Screen before observing truth; compare independent nonlinear recovery worlds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.linalg import eigvalsh

from experiments.laurent_calibration.model import apply_gains
from experiments.laurent_calibration.design import uniform_plan
from experiments.laurent_calibration.run import PRIOR_POINTS, TRUTHS, INITIALS, save, relative
from .model import Body, bodies_at, Evaluator, oracle, information, fit


OUTPUT = Path("results/experiments/laurent_neighbour_20260916")
NEIGHBOUR_PRIORS = np.array([
    np.zeros(8), [.1, -.15, .1, -.2, .15, .2, -.1, .3],
    [-.15, .1, -.1, .15, -.2, -.15, .2, -.3],
])
NEIGHBOUR_TRUTHS = np.array([
    [.15, -.15, .25, -.35, .25, .2, -.15, .4],
    [-.25, .15, -.2, .3, -.35, .25, .2, -.3],
])
ARMS = ("absent", "known_coupled", "unknown_coupled", "known_additive", "unknown_additive")


def compact(info):
    return dict(gram=info["gram"].tolist(), eigenvalues=info["eigenvalues"].tolist(),
                radial_rms_crlb_mm=info["radial_rms_crlb_mm"], nuisance_rank=info["nuisance_rank"])


def screen(output):
    tick = perf_counter()
    isolated = [Body()]
    y0 = Evaluator(isolated).forward(np.zeros(8))
    sigma = .01*np.sqrt(np.mean(abs(y0)**2, axis=(1, 2)))/np.sqrt(2)
    mask = uniform_plan()
    baselines = []
    for p in PRIOR_POINTS:
        e = Evaluator(isolated)
        baselines.append(information(e.forward(p), e.jacobian(p), mask, sigma))
    rows = []
    for distance in (.105, .14):
        for degrees in range(-180, 180, 30):
            angle = np.deg2rad(degrees)
            center = -.16j+distance*np.exp(1j*angle)
            if center.imag > -.05:
                continue
            for epsr in (3., 12., 24.):
                bodies = bodies_at(distance, angle, epsr)
                prior_rows = []
                for i, (target, neighbour) in enumerate(zip(PRIOR_POINTS, NEIGHBOUR_PRIORS)):
                    x = np.r_[target, neighbour]
                    coupled, additive = Evaluator(bodies), Evaluator(bodies, interactions=False)
                    y, j = coupled.forward(x), coupled.jacobian(x)
                    ya, ja = additive.forward(x), additive.jacobian(x)
                    infos = {}
                    for name, yy, jj, unknown in [
                        ("known_coupled", y, j, False), ("unknown_coupled", y, j, True),
                        ("known_additive", ya, ja, False), ("unknown_additive", ya, ja, True),
                    ]:
                        info = information(yy, jj, mask, sigma, neighbour_unknown=unknown)
                        record = compact(info)
                        record["rms_precision_gain_vs_absent"] = baselines[i]["radial_rms_crlb_mm"]/info["radial_rms_crlb_mm"]
                        record["generalized_information_eigenvalues_vs_absent"] = eigvalsh(info["gram"], baselines[i]["gram"]).tolist()
                        infos[name] = record
                    # Controls for calibration-reference effects versus physical illumination.
                    for name, yy, jj, unknown in [("known_coupled", y, j, False), ("unknown_coupled", y, j, True),
                                                  ("known_additive", ya, ja, False), ("unknown_additive", ya, ja, True)]:
                        calibrated = information(yy, jj, mask, sigma, neighbour_unknown=unknown, gains_unknown=False)
                        infos[name]["known_gain_radial_rms_crlb_mm"] = calibrated["radial_rms_crlb_mm"]
                    yisolated = Evaluator(isolated).forward(target)
                    prior_rows.append(dict(arms=infos,
                        coupled_to_isolated_signal_rms_ratio=float(np.linalg.norm(y[:, mask])/np.linalg.norm(yisolated[:, mask])),
                        additive_to_isolated_signal_rms_ratio=float(np.linalg.norm(ya[:, mask])/np.linalg.norm(yisolated[:, mask])),
                        interaction_field_relative_to_total=relative(y, ya)))
                score = min(r["arms"]["unknown_coupled"]["rms_precision_gain_vs_absent"] for r in prior_rows)
                rows.append(dict(distance_m=distance, angle_degrees=degrees, epsr=epsr,
                                 neighbour_center=[center.real, center.imag], robust_score=score, priors=prior_rows))
    best = max(rows, key=lambda r: r["robust_score"])
    result = dict(candidates=rows, selected={k: best[k] for k in ("distance_m", "angle_degrees", "epsr", "robust_score")},
        baseline_information=[compact(i) for i in baselines], prior_points=PRIOR_POINTS.tolist(),
        neighbour_prior_points=NEIGHBOUR_PRIORS.tolist(), sigma=sigma.tolist(), mask_edges=np.argwhere(mask).tolist(),
        selection_uses_truth=False, criterion="Maximize worst-prior reduction in local target-harmonic RMS CRLB, with all gains and neighbour coordinates unknown",
        noise_rule="Fixed absolute per-frequency noise from nominal isolated target at 1%; identical for all physical worlds",
        recovery_truths=TRUTHS.tolist(), neighbour_recovery_truths=NEIGHBOUR_TRUTHS.tolist(),
        target_starts=INITIALS.tolist(), seconds=perf_counter()-tick)
    save(output/"screen.json", result)
    print("screen", json.dumps(result["selected"]), "candidates", len(rows), flush=True)
    for name in ARMS[1:]:
        print(name, [round(r["arms"][name]["rms_precision_gain_vs_absent"], 3) for r in best["priors"]], flush=True)
    return result


def selected_bodies(record):
    s = record["selected"]
    return bodies_at(s["distance_m"], np.deg2rad(s["angle_degrees"]), s["epsr"])


def qualify(output, record):
    bodies = selected_bodies(record)
    rows = []
    for x in [np.zeros(16), np.r_[TRUTHS[0], NEIGHBOUR_TRUTHS[0]], np.r_[TRUTHS[1], NEIGHBOUR_TRUTHS[1]]]:
        y128, y192 = oracle(bodies, x, nodes=128), oracle(bodies, x, nodes=192)
        nodal, native = Evaluator(bodies), Evaluator(bodies, backend="native")
        yn, yv = nodal.forward(x), native.forward(x)
        jn, jv = nodal.jacobian(x), native.jacobian(x)
        row = dict(parameters=x.tolist(), oracle_refinement_error=relative(y128, y192),
                   compiled_nodal_error=relative(yn, y192), compiled_native_error=relative(yv, y192),
                   native_nodal_jacobian_error=relative(jv, jn))
        rows.append(row)
    passed = all(max(r[k] for k in ("oracle_refinement_error", "compiled_nodal_error", "compiled_native_error")) < 1e-8
                 and r["native_nodal_jacobian_error"] < 1e-7 for r in rows)
    save(output/"qualification.json", dict(passed=passed, rows=rows))
    print("qualification", passed, flush=True)
    if not passed:
        raise RuntimeError("Selected geometry requires better numerical resolution")


def recover(output, record, seeds=5, max_nfev=180):
    bodies = selected_bodies(record)
    mask = uniform_plan()
    sigma = np.array(record["sigma"])
    records = []
    for si, (target, neighbour) in enumerate(zip(TRUTHS, NEIGHBOUR_TRUTHS)):
        truth = np.r_[target, neighbour]
        clean = {"absent": oracle(bodies[:1], target), "coupled": oracle(bodies, truth),
                 "additive": oracle(bodies, truth, interactions=False)}
        for seed_index in range(seeds):
            seed = 8300 + 100*si + seed_index
            rng = np.random.default_rng(seed)
            gains = rng.normal(size=(2, 2, 23))
            gains[:, 0] *= .15
            gains[:, 1] *= .25
            noise = sigma[:, None, None]*(rng.normal(size=clean["absent"].shape)+1j*rng.normal(size=clean["absent"].shape))
            data = {k: apply_gains(v, gains)+noise for k,v in clean.items()}
            for name in ARMS:
                absent, known = name == "absent", name.startswith("known_")
                interactions = not name.endswith("additive")
                key = "absent" if absent else ("coupled" if interactions else "additive")
                actual_bodies = bodies[:1] if absent else bodies
                starts = []
                for ti, start in enumerate(INITIALS):
                    ns = neighbour if known else (np.zeros(8) if ti == 0 else np.array([-.2, .2, -.2, .2, -.2, .1, .2, -.4]))
                    initial = start if absent else np.r_[start, ns]
                    starts.append(fit(actual_bodies, mask, data[key], sigma, initial,
                        interactions=interactions, neighbour_known=known, max_nfev=max_nfev))
                selected = int(np.argmin([r["cost"] for r in starts]))
                best = starts[selected]
                p = np.array(best["parameters"])
                target_delta = p[:8]-target
                shape_error = float(np.sqrt(2)*np.linalg.norm(target_delta[3:7]))
                # Fresh independent final forward for every selected result.
                predicted = Evaluator(actual_bodies, interactions=interactions).forward(p)
                reference = oracle(actual_bodies, p, interactions=interactions)
                check = relative(predicted, reference)
                if check > 1e-8:
                    raise RuntimeError(f"Recovered state fails full-boundary check: {check}")
                fitted_gains = np.array(best["gains"]).reshape(2, 2, 23)
                heldout = relative(apply_gains(reference, fitted_gains)[:, ~mask], apply_gains(clean[key], gains)[:, ~mask])
                boundary = actual_bodies[0].chart.boundary(p[:8])-actual_bodies[0].chart.boundary(target)
                result = dict(scene=si, seed=seed, method=name, trials=starts, selected_start=selected,
                    shape_harmonic_radial_rms_mm=shape_error,
                    corresponding_boundary_rms_mm=float(1000*np.sqrt(np.mean(abs(boundary)**2))),
                    center_error_mm=float(10*np.linalg.norm(target_delta[:2])),
                    radius_error_mm=float(2*abs(target_delta[2])),
                    permittivity_error=float(abs(actual_bodies[0].permittivity(p[:8])-actual_bodies[0].permittivity(target))),
                    heldout_field_error=heldout, oracle_forward_error=check,
                    recovered=bool(best["success"] and shape_error < .5),
                    truth=truth.tolist(), true_gains=gains.tolist())
                records.append(result)
                save(output/"recoveries.json", records)
                print("recover", si, seed_index, name, round(shape_error, 4), best["success"], best["nfev"], flush=True)
    summary = []
    for name in ARMS:
        rows = [r for r in records if r["method"] == name]
        bests = [r["trials"][r["selected_start"]] for r in rows]
        error = np.array([r["shape_harmonic_radial_rms_mm"] for r in rows])
        summary.append(dict(method=name, cases=len(rows), recovered=sum(r["recovered"] for r in rows),
            converged=sum(b["success"] for b in bests), median_shape_rms_mm=float(np.median(error)),
            ensemble_shape_rms_mm=float(np.sqrt(np.mean(error**2))), max_shape_rms_mm=float(error.max()),
            median_heldout_field_error=float(np.median([r["heldout_field_error"] for r in rows])),
            physical_bound_hits=sum(any(k < b["active_physical_count"] for k in b["active_bounds"]) for b in bests),
            gain_bound_hits=sum(any(k >= b["active_physical_count"] for k in b["active_bounds"]) for b in bests)))
    save(output/"summary.json", dict(rows=summary, seeds_per_scene=seeds, target_shapes=2,
        initializations=2, same_mask_all_worlds=True, same_noise_all_worlds=True,
        fixed_absolute_noise=True, max_nfev=max_nfev,
        note="The additive control has its OWN correctly matched data and inverse; it is not a mismatched inverse of coupled observations."))
    print(json.dumps(summary, indent=2), flush=True)


def manifest(output):
    import platform, subprocess, scipy
    paths = sorted(p for root in ["experiments/laurent_neighbour", "experiments/laurent_calibration",
        "experiments/modal_muller_research", "solvers/gpr_bem_kress", "solvers/ordered_boundary"] for p in Path(root).glob("*.py"))
    save(output/"manifest.json", dict(git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        threads={k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        note="Source includes pre-existing uncommitted experimental dependencies."))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--stage", choices=("screen", "recover", "all"), default="all")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--max-nfev", type=int, default=180)
    args = parser.parse_args()
    if args.stage in ("screen", "all"):
        record = screen(args.output)
        qualify(args.output, record)
    else:
        record = json.loads((args.output/"screen.json").read_text())
        if not json.loads((args.output/"qualification.json").read_text())["passed"]:
            raise RuntimeError("Missing passing qualification")
    if args.stage in ("recover", "all"):
        recover(args.output, record, args.seeds, args.max_nfev)
    manifest(args.output)


if __name__ == "__main__":
    main()
