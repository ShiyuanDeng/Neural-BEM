"""Reproducible, degree/offset-matched information and recovery experiment.

Example (single-thread CPU):
  PYTHONPATH=solvers:. python -m experiments.laurent_calibration.run --stage all
"""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.spatial import cKDTree

from .model import Fixture, Evaluator, PARAMETERS, TARGET, apply_gains, fit, oracle
from .design import (graph_record, offset_categories, optimize_plan, random_plan,
                     shape_information, uniform_plan)


DEFAULT_OUTPUT = Path("results/experiments/laurent_calibration_20260916")
PRIOR_POINTS = np.array([
    np.zeros(8),
    [.2, -.15, .1, .3, -.2, .25, .15, .3],
    [-.2, .15, -.1, -.25, .2, -.15, .3, -.3],
])
# Fixed before any recoveries; neither truth enters measurement selection.
TRUTHS = np.array([
    [.25, -.20, .30, .65, -.35, .55, .30, .60],
    [-.30, .25, -.15, -.50, .65, -.25, .55, -.60],
])
INITIALS = np.array([np.zeros(8), [-.3, .25, -.25, -.2, .15, -.15, .2, -.4]])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def relative(a, b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-300))


def information_record(y, j, mask, sigma):
    result = shape_information(y, j, mask, sigma)
    eig = result["eigenvalues"]
    gram = result["gram"]
    cov = np.linalg.inv(gram)
    return dict(eigenvalues=eig.tolist(), gram=gram.tolist(),
                coefficient_std_mm=(2*np.sqrt(np.diag(cov))).tolist(),
                radial_rms_crlb_mm=float(np.sqrt(2*np.trace(cov))),
                weakest_shape_direction=np.linalg.eigh(gram)[1][:, 0].tolist(),
                calibration_complex_ranks=result["calibration_complex_ranks"],
                other_nuisance_rank=result["other_nuisance_rank"])


def qualify(f, output):
    rows = []
    for point in [PRIOR_POINTS[0], PRIOR_POINTS[1], *TRUTHS]:
        low, high = oracle(f, point, 192), oracle(f, point, 256)
        nodal, native = Evaluator(f), Evaluator(f, backend="native")
        yn, ynative = nodal.forward(point), native.forward(point)
        jn, jnative = nodal.jacobian(point), native.jacobian(point)
        finite = []
        h = 2e-4
        for k in range(8):
            d = np.eye(8)[k]*h
            finite.append((nodal.forward(point+d)-nodal.forward(point-d))/(2*h))
        finite = np.stack(finite, axis=-1)
        col = np.linalg.norm((jn-finite).reshape(-1, 8), axis=0)/np.linalg.norm(finite.reshape(-1, 8), axis=0)
        row = dict(parameters=point.tolist(), oracle_192_256_error=relative(low, high),
                   compiled_nodal_error=relative(yn, high), compiled_native_error=relative(ynative, high),
                   native_nodal_jacobian_error=relative(jnative, jn),
                   finite_difference_column_errors=col.tolist())
        rows.append(row)
    passed = all(max(r["oracle_192_256_error"], r["compiled_nodal_error"], r["compiled_native_error"]) < 1e-8
                 and r["native_nodal_jacobian_error"] < 1e-7
                 and max(r["finite_difference_column_errors"]) < 2e-6 for r in rows)
    save(output/"qualification.json", dict(passed=passed, rows=rows))
    print("qualification", passed, flush=True)
    if not passed:
        raise RuntimeError("Numerical qualification failed; do not run inverse comparisons")


def design(f, output, proposals):
    tick = perf_counter()
    nominal = Evaluator(f).forward(PRIOR_POINTS[0])
    # Fixed design noise, from nominal prediction, not a truth field or a selected subset.
    sigma = .01*np.sqrt(np.mean(abs(nominal)**2, axis=(1, 2)))/np.sqrt(2)
    prior = []
    for x in PRIOR_POINTS:
        e = Evaluator(f)
        prior.append((e.forward(x), e.jacobian(x), sigma))
    bins = offset_categories(f)
    uniform = uniform_plan(f.count)
    randoms = [random_plan(uniform, bins, 4100+i) for i in range(20)]
    starts = [uniform, randoms[0], randoms[1]]
    plans, searches = {"uniform": uniform}, {}
    for name, calibrate in [("known_gain_design", False), ("quotient_design", True)]:
        plan, details = optimize_plan(starts, bins, prior, calibrate, 951, proposals)
        plans[name], searches[name] = plan, details
        print("design", name, details["score"], flush=True)
    record = dict(
        prior_points=PRIOR_POINTS.tolist(), sigma=sigma.tolist(), design_uses_truth=False,
        parameter_names=PARAMETERS, target_indices=TARGET.tolist(),
        plans={name: np.argwhere(mask).tolist() for name, mask in plans.items()},
        random_plans=[np.argwhere(mask).tolist() for mask in randoms],
        graph_records={name: graph_record(mask, bins) for name, mask in plans.items()},
        random_graph_records=[graph_record(mask, bins) for mask in randoms],
        offset_bin_edges_m=[.06, .14, .26], searches=searches,
        nominal_information={name: information_record(*prior[0][:2], mask, sigma) for name, mask in plans.items()},
        random_nominal_information=[information_record(*prior[0][:2], mask, sigma) for mask in randoms],
        seconds=perf_counter()-tick,
        criterion="Mean log determinant of four shape-mode Fisher matrix across three fixed prior scenarios",
        nuisance="Independent complex Tx/Rx gains at each frequency, center, radius, uniform real permittivity",
        constraints="Same edge count, connected graph, endpoint degrees, and physical-offset-bin counts",
        measurement_count_per_frequency=int(uniform.sum()),
        frequencies_hz=list(f.frequencies), sources=f.sources.tolist(), receivers=f.receivers.tolist(),
        truth_points_for_later_recovery=TRUTHS.tolist(), initial_points=INITIALS.tolist(),
        declared_recovery_threshold_radial_rms_mm=.5,
    )
    save(output/"design.json", record)


def mask_from_edges(edges, n):
    mask = np.zeros((n, n), bool)
    rows = np.array(edges, int)
    mask[rows[:, 0], rows[:, 1]] = True
    return mask


def recovery_metrics(f, fitted, truth, clean, clean_corrupted, mask):
    x = np.array(fitted["parameters"])
    actual, reference = f.boundary(x), f.boundary(truth)
    a, b = np.c_[actual.real, actual.imag], np.c_[reference.real, reference.imag]
    d1, d2 = cKDTree(a).query(b)[0], cKDTree(b).query(a)[0]
    prediction = Evaluator(f, nodes=128).forward(x)
    if fitted["gains"]:
        gains = np.array(fitted["gains"]).reshape(len(f.frequencies), 2, 2*f.count-1)
        calibrated = apply_gains(prediction, gains)
    else:
        calibrated = prediction
    delta = x-truth
    return dict(shape_harmonic_radial_rms_mm=float(np.sqrt(2)*np.linalg.norm(delta[3:7])),
                shape_coefficients_mm=(2*x[3:7]).tolist(),
                center_error_mm=float(10*np.linalg.norm(delta[:2])),
                radius_error_mm=float(2*abs(delta[2])),
                permittivity_error=float(.5*abs(delta[7])),
                symmetric_boundary_rms_mm=float(1000*np.sqrt((np.mean(d1*d1)+np.mean(d2*d2))/2)),
                clean_field_error=relative(prediction, clean),
                unmeasured_calibrated_field_error=relative(calibrated[:, ~mask], clean_corrupted[:, ~mask]))


def recover(f, output, seeds, noise_levels, starts, max_nfev):
    design_record = json.loads((output/"design.json").read_text())
    plans = {k: mask_from_edges(v, f.count) for k, v in design_record["plans"].items()}
    randoms = [mask_from_edges(v, f.count) for v in design_record["random_plans"]]
    records = []
    for scene_index, truth in enumerate(TRUTHS):
        clean = oracle(f, truth, 256)
        truth_ev = Evaluator(f)
        y, jac = truth_ev.forward(truth), truth_ev.jacobian(truth)
        for noise in noise_levels:
            # One fixed per-frequency absolute variance shared by all plans.
            sigma = noise*np.sqrt(np.mean(abs(clean)**2, axis=(1, 2)))/np.sqrt(2)
            for seed_index in range(seeds):
                seed = 7200 + 100*scene_index + seed_index
                rng = np.random.default_rng(seed)
                gains = rng.normal(size=(len(f.frequencies), 2, 2*f.count-1))
                gains[:, 0] *= .15
                gains[:, 1] *= .25
                clean_corrupted = apply_gains(clean, gains)
                data = clean_corrupted + sigma[:, None, None]*(rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape))
                current = dict(plans, random=randoms[seed_index % len(randoms)])
                for name, mask in current.items():
                    trials = [fit(f, mask, data, sigma, initial, max_nfev=max_nfev)
                              for initial in INITIALS[:starts]]
                    # Selection uses training likelihood ONLY, never shape truth.
                    best_index = int(np.argmin([r["cost"] for r in trials]))
                    best = trials[best_index]
                    metrics = recovery_metrics(f, best, truth, clean, clean_corrupted, mask)
                    # Evaluate information at actual gains for post-hoc diagnostics only.
                    gained_jac = np.stack([apply_gains(jac[..., k], gains) for k in range(8)], axis=-1)
                    info = information_record(apply_gains(y, gains), gained_jac, mask, sigma)
                    record = dict(scene=scene_index, seed=seed, noise_fraction=noise, method=name,
                                  selected_start=best_index, trials=trials, metrics=metrics,
                                  truth_information=info, truth=truth.tolist(), true_gains=gains.tolist(),
                                  mask_edges=np.argwhere(mask).tolist(),
                                  recovered=bool(best["success"] and metrics["shape_harmonic_radial_rms_mm"] < .5))
                    records.append(record)
                    save(output/"recoveries.json", records)
                    print("recover", scene_index, noise, seed_index, name,
                          round(metrics["shape_harmonic_radial_rms_mm"], 4), best["success"],
                          best["nfev"], flush=True)
                # Oracle calibration reference on the exact quotient-selected data.
                mask = plans["quotient_design"]
                trials = [fit(f, mask, data, sigma, initial, known_gains=gains, max_nfev=max_nfev)
                          for initial in INITIALS[:starts]]
                selected = int(np.argmin([r["cost"] for r in trials]))
                best = trials[selected]
                # Store supplied gains so held-out prediction uses the oracle calibration.
                best["gains"] = gains.ravel().tolist()
                metrics = recovery_metrics(f, best, truth, clean, clean_corrupted, mask)
                records.append(dict(scene=scene_index, seed=seed, noise_fraction=noise,
                    method="oracle_calibration", selected_start=selected, trials=trials, metrics=metrics,
                    truth=truth.tolist(), recovered=bool(best["success"] and metrics["shape_harmonic_radial_rms_mm"] < .5)))
                save(output/"recoveries.json", records)
    summary = []
    for noise in noise_levels:
        for name in [*plans, "random", "oracle_calibration"]:
            rows = [r for r in records if r["method"] == name and r["noise_fraction"] == noise]
            error = np.array([r["metrics"]["shape_harmonic_radial_rms_mm"] for r in rows])
            selected = [r["trials"][r["selected_start"]] for r in rows]
            summary.append(dict(method=name, noise_fraction=noise, cases=len(rows),
                recovered=sum(r["recovered"] for r in rows),
                converged=sum(r["success"] for r in selected),
                median_shape_radial_rms_mm=float(np.median(error)),
                min_shape_radial_rms_mm=float(error.min()), max_shape_radial_rms_mm=float(error.max()),
                median_boundary_rms_mm=float(np.median([r["metrics"]["symmetric_boundary_rms_mm"] for r in rows])),
                median_unmeasured_field_error=float(np.median([r["metrics"]["unmeasured_calibrated_field_error"] for r in rows])),
                median_total_seconds=float(np.median([sum(t["seconds"] for t in r["trials"]) for r in rows])),
                physical_bound_hits=sum(any(k < 8 for k in r["active_bounds"]) for r in selected),
                calibration_bound_hits=sum(any(k >= 8 for k in r["active_bounds"]) for r in selected)))
    save(output/"summary.json", dict(rows=summary, seeds_per_scene=seeds, starts=starts,
        noise_levels=noise_levels, max_nfev=max_nfev,
        threshold_radial_rms_mm=.5, independent_scenes=len(TRUTHS),
        caveat="Small synthetic local feasibility experiment, not field-GPR validation or a new-information claim."))
    print(json.dumps(summary, indent=2), flush=True)


def manifest(output):
    import subprocess
    import scipy
    roots = [Path("experiments/laurent_calibration"), Path("experiments/modal_muller_research"),
             Path("solvers/gpr_bem_kress"), Path("solvers/ordered_boundary")]
    paths = sorted(p for root in roots for p in root.glob("*.py"))
    save(output/"manifest.json", dict(
        git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        branch=subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        thread_environment={k: os.environ.get(k) for k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]},
        source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        source_note="Workspace contains pre-existing uncommitted experimental dependencies; hashes identify the measured source state."))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stage", choices=["design", "recover", "all"], default="all")
    parser.add_argument("--proposals", type=int, default=1800)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--noise", type=float, nargs="+", default=[.01])
    parser.add_argument("--starts", type=int, choices=[1, 2], default=2)
    parser.add_argument("--max-nfev", type=int, default=160)
    args = parser.parse_args()
    f = Fixture()
    if args.stage in ("design", "all"):
        qualify(f, args.output)
        design(f, args.output, args.proposals)
    if args.stage in ("recover", "all"):
        recover(f, args.output, args.seeds, args.noise, args.starts, args.max_nfev)
    manifest(args.output)


if __name__ == "__main__":
    main()
