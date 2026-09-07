#!/usr/bin/env python3
"""Task D: fixed-circle and joint radial-K2/interior-epsr bounded controls."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from time import perf_counter

for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"solvers"))

import numpy as np
import scipy
from scipy.special import hankel1

import gpr_bem_ref
from gpr_bem_kress import KressSolveConfig
from sdf_inverse import MaterialSpec, PairedForwardProblem
from sdf_inverse.curve_updates import radial_fourier_parameterization
from sdf_inverse.material_inverse import (
    MaterialCurveEvaluator, PARAMETER_NAMES, PARAMETER_ORIGIN, PARAMETER_SCALES,
    PHYSICAL_LOWER, PHYSICAL_UPPER, candidate_state, fit_material_curve, scaled_parameters,
)
from sdf_to_ordered_boundary.artifacts import write_metrics_csv, write_npz, write_strict_json
from run_parameterization_aware_comparison import geometry_metrics


TRUTH = np.array([.05, .5, .5, 0., 0., 3.]); TRUTH.setflags(write=False)
GATES = {"stationarity_scaled_projected_gradient_inf": 1e-7,
         "clean_relative_field_error": 1e-4, "noisy_clean_holdout_relative_field_error": .02,
         "material_absolute_error": .1, "geometry_symmetric_distance_m": 2e-4,
         "geometry_refinement_change_m": 2e-6,
         "material_jvp_relative_error_to_Mie_FD": 1e-5,
         "material_Mie_FD_self_agreement": 1e-5, "material_forward_error_to_Mie": 1e-6,
         "material_best_production_FD_relative_error": 1e-5,
         "forward_self_convergence": 1e-5, "mie_self_convergence": 1e-10}


def acquisition(*, holdout=False, pairs=12):
    angles = .13+2*np.pi*(np.arange(pairs)+(0.5 if holdout else 0.))/pairs
    sources = .5+.30*np.column_stack((np.cos(angles), np.sin(angles)))
    receiver_angles = angles+.18+.03*np.cos(2*angles)
    receiver_radii = .28+.01*np.sin(angles)
    receivers = .5+receiver_radii[:, None]*np.column_stack((np.cos(receiver_angles), np.sin(receiver_angles)))
    return PairedForwardProblem(sources, receivers, 2*np.pi*1e9*np.array([.5, 1.5]),
        np.array([1e-6+.2e-6j, .8e-6-.35e-6j]), MaterialSpec(6.), MaterialSpec(3.),
        8.8541878128e-12, 1.25663706212e-6)


def mie_response(problem, *, interior_epsr, radius=.05, center=(.5, .5), maximum_mode=64):
    """Independent fixed-mode circle data; no production Kress call."""
    modes = np.arange(-maximum_mode, maximum_mode+1)
    source_delta = problem.source_points-np.asarray(center)
    receiver_delta = problem.receiver_points-np.asarray(center)
    phase = np.arctan2(receiver_delta[:, 1], receiver_delta[:, 0])-np.arctan2(source_delta[:, 1], source_delta[:, 0])
    results = []
    for omega, strength in zip(problem.angular_frequencies, problem.source_strengths):
        ke = float(omega)*np.sqrt(problem.eps0*problem.mu0*problem.exterior.epsr)
        ki = float(omega)*np.sqrt(problem.eps0*problem.mu0*interior_epsr)
        if max(ke, ki)*radius > 8.:
            raise ValueError("Outside the fixed-mode Mie audit's bounded electrical size.")
        ratio = gpr_bem_ref.penetrable_cylinder_scattering_coefficient_ratio(modes, ke, ki, radius)
        response = .25j*strength*np.sum(
            hankel1(modes[None], ke*np.linalg.norm(source_delta, axis=1)[:, None])
            *hankel1(modes[None], ke*np.linalg.norm(receiver_delta, axis=1)[:, None])
            *ratio[None]*np.exp(1j*phase[:, None]*modes[None]), axis=1)
        results.append(response)
    return np.column_stack(results)


def relative_error(prediction, reference):
    return float(np.max(np.linalg.norm(prediction-reference, axis=0)/np.linalg.norm(reference, axis=0)))


def frozen_observations(problem, *, noise_fraction=.01, seed=4206):
    coarse = mie_response(problem, interior_epsr=TRUTH[5], maximum_mode=32)
    clean = mie_response(problem, interior_epsr=TRUTH[5], maximum_mode=64)
    discrepancy = relative_error(coarse, clean)
    if discrepancy > GATES["mie_self_convergence"]:
        raise RuntimeError("Independent Mie data failed its fixed-mode refinement gate.")
    generator = np.random.default_rng(seed)
    sigma = noise_fraction*np.linalg.norm(clean, axis=0)/np.sqrt(problem.num_pairs)
    noise = sigma[None, :]*(generator.standard_normal(clean.shape)+1j*generator.standard_normal(clean.shape))/np.sqrt(2.)
    noisy = clean+noise
    for value in (clean, noise, noisy):
        value.setflags(write=False)
    return clean, noisy, noise, {"identity": "independent_fixed_mode_Mie", "modes": [32, 64],
        "Mie_frequency_evaluations": 2*problem.num_frequencies,
        "maximum_per_frequency_refinement_difference": discrepancy, "passed": True,
        "noise": {"fraction_of_per_frequency_pair_rms": noise_fraction,
                  "complex_standard_deviation_per_frequency": sigma.tolist(), "seed": seed,
                  "distribution": "independent circular complex Gaussian; real/imag sigma/sqrt(2)"},
        "clean_sha256": hashlib.sha256(clean.tobytes()).hexdigest(),
        "noisy_sha256": hashlib.sha256(noisy.tobytes()).hexdigest()}


def arm_definitions():
    arms = []
    for epsilon in (2., 5., 9.):
        initial = TRUTH.copy(); initial[5] = epsilon
        arms.append({"name": f"fixed_clean_eps{int(epsilon)}", "joint": False, "noisy": False, "initial": initial})
    initial = TRUTH.copy(); initial[5] = 5.
    arms.append({"name": "fixed_noisy_eps5", "joint": False, "noisy": True, "initial": initial})
    for number, initial in enumerate((np.array([.057, .494, .505, .002, -.001, 2.]),
                                     np.array([.043, .505, .495, -.002, .001, 9.]))):
        for noisy in (False, True):
            arms.append({"name": f"joint_{'noisy' if noisy else 'clean'}_start{number+1}",
                         "joint": True, "noisy": noisy, "initial": initial.copy()})
    return arms


def sensitivity_audit(problem, observed, *, nodes=64):
    records, arrays = [], {}
    for epsilon in (2., 3., 9.):
        physical = TRUTH.copy(); physical[5] = epsilon
        evaluator = MaterialCurveEvaluator(problem, observed, nodes=nodes)
        scaled = scaled_parameters(physical)
        base = evaluator.evaluate(scaled)
        jacobian = evaluator.jacobian(scaled, active_indices=(5,))[:, 0]
        count = problem.num_pairs*problem.num_frequencies
        analytic = (jacobian[:count].reshape(base.prediction.shape)
                    +1j*jacobian[count:].reshape(base.prediction.shape))*evaluator.frequency_scales[None, :]
        mie = mie_response(problem, interior_epsr=epsilon)
        label = f"eps{int(epsilon)}"
        arrays[label+"_analytic_scaled_material_jvp"] = analytic
        step_records = []
        for step in (1e-2, 1e-3, 1e-4, 1e-5):
            direction = np.zeros(6); direction[5] = step
            minus = evaluator.evaluate(scaled-direction).prediction
            plus = evaluator.evaluate(scaled+direction).prediction
            finite = (plus-minus)/(2*step)
            step_records.append({"scaled_step": step, "production_fd_relative_error": relative_error(finite, analytic)})
        mie_jvps = []
        for step in (1e-4, 5e-5):
            delta = PARAMETER_SCALES[5]*step
            mie_jvps.append((mie_response(problem, interior_epsr=epsilon+delta)
                             -mie_response(problem, interior_epsr=epsilon-delta))/(2*step))
        record = {"interior_epsr": epsilon, "nodes": nodes,
            "forward_relative_error_to_Mie": relative_error(base.prediction, mie),
            "analytic_material_jvp_relative_error_to_Mie_FD": relative_error(analytic, mie_jvps[-1]),
            "Mie_FD_step_refinement_difference": relative_error(mie_jvps[0], mie_jvps[1]),
            "production_fd_steps": step_records, "work": evaluator.work,
            "Mie_frequency_evaluations": 5*problem.num_frequencies}
        record["passed"] = bool(
            record["forward_relative_error_to_Mie"] <= GATES["material_forward_error_to_Mie"]
            and record["analytic_material_jvp_relative_error_to_Mie_FD"] <= GATES["material_jvp_relative_error_to_Mie_FD"]
            and record["Mie_FD_step_refinement_difference"] <= GATES["material_Mie_FD_self_agreement"]
            and min(item["production_fd_relative_error"] for item in step_records) <= GATES["material_best_production_FD_relative_error"])
        records.append(record)
        arrays[label+"_Mie_scaled_material_jvp"] = mie_jvps[-1]
    return records, arrays


def snapshot(problem):
    return {"source_points": problem.source_points.tolist(), "receiver_points": problem.receiver_points.tolist(),
        "angular_frequencies": problem.angular_frequencies.tolist(),
        "source_strengths_real": problem.source_strengths.real.tolist(),
        "source_strengths_imag": problem.source_strengths.imag.tolist(),
        "exterior": asdict(problem.exterior), "interior_template_not_candidate": asdict(problem.interior),
        "eps0": problem.eps0, "mu0": problem.mu0}


def provenance():
    paths = [Path(__file__), ROOT/"run_parameterization_aware_comparison.py",
             ROOT/"docs/codex_sdf_kress_priorities_2026-09-05.md"]
    for package in ("sdf_inverse", "sdf_to_ordered_boundary", "ordered_boundary", "gpr_bem_kress", "gpr_bem_ref", "periodic_kress"):
        paths += sorted((ROOT/"solvers"/package).glob("*.py"))
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    return {"git_commit": git("rev-parse", "HEAD"), "dirty_state": git("status", "--short"),
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        "python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform(),
        "thread_caps": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}}


def run(args):
    if args.output.exists():
        raise FileExistsError("Use a fresh output directory; measured artifacts are immutable.")
    if len(args.audit_nodes) < 2 or args.audit_nodes != sorted(set(args.audit_nodes)) or any(n < 16 or n%2 for n in args.audit_nodes):
        raise ValueError("Need increasing distinct even audit nodes, at least two.")
    args.output.mkdir(parents=True)
    started = perf_counter()
    observation_started = perf_counter()
    train, holdout = acquisition(), acquisition(holdout=True)
    train_clean, train_noisy, train_noise, train_report = frozen_observations(train)
    holdout_clean, holdout_noisy, holdout_noise, holdout_report = frozen_observations(holdout, seed=4216)
    observation_preparation_seconds = perf_counter()-observation_started
    arms = arm_definitions()
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "provenance": provenance(),
        "command": shlex.join([sys.executable, *sys.argv]),
        "configuration": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "gates": GATES, "parameter_names": PARAMETER_NAMES, "parameter_origin": PARAMETER_ORIGIN,
        "parameter_scales": PARAMETER_SCALES, "physical_lower_bounds": PHYSICAL_LOWER, "physical_upper_bounds": PHYSICAL_UPPER,
        "truth_physical": TRUTH, "kress_solve_config": asdict(KressSolveConfig()),
        "train_acquisition": snapshot(train), "holdout_acquisition": snapshot(holdout),
        "train_observations": train_report, "holdout_observations": holdout_report,
        "observation_preparation_seconds": observation_preparation_seconds,
        "arms": arms, "scope": "Mie-circle target, fixed geometry or radial K2 jointly with one positive lossless interior epsr; known exterior and sources; no SDF/neural/material/topology defaults changed",
        "weighting": "real then imaginary paired residuals divided by immutable cohort-observation column norms; dimensionless declared parameter scales; no regularization",
        "data_policy": "independent immutable Mie data generated once before candidates; noisy/clean cohorts shared unchanged across starts; unseen-angle holdout never used by optimizer",
        "geometry_policy": "global positive radial lower bound over declared box; coherent phase-fixed radial graph, no per-candidate refit; Cartesian bandwidth3",
        "cache_policy": "one entry with full geometry/material/acquisition/frequency/constants/source calibration/numerical config/chart/observation identity"}
    write_strict_json(args.output/"manifest.json", manifest)
    arrays = {"truth_physical": TRUTH, "train_clean": train_clean, "train_noisy": train_noisy,
              "train_noise": train_noise, "holdout_clean": holdout_clean, "holdout_noisy": holdout_noisy,
              "holdout_noise": holdout_noise}
    for name, problem in (("train", train), ("holdout", holdout)):
        for key in ("source_points", "receiver_points", "angular_frequencies", "source_strengths"):
            arrays[name+"_"+key] = getattr(problem, key)
    write_npz(args.output/"arrays.npz", arrays)
    sensitivity_started = perf_counter()
    sensitivity, sensitivity_arrays = sensitivity_audit(train, train_clean, nodes=args.nodes)
    sensitivity_seconds = perf_counter()-sensitivity_started
    arrays.update({"sensitivity_"+key: value for key, value in sensitivity_arrays.items()})
    reference_curve = radial_fourier_parameterization(candidate_state(scaled_parameters(TRUTH))[1])
    records = []
    for definition in arms:
        arm_started = perf_counter()
        print(f"D starting {definition['name']}", flush=True)
        observed = train_noisy if definition["noisy"] else train_clean
        evaluator = MaterialCurveEvaluator(train, observed, nodes=args.nodes)
        record = {"name": definition["name"], "joint_shape": definition["joint"], "noisy_training": definition["noisy"]}
        try:
            final, fit = fit_material_curve(evaluator, definition["initial"], joint_shape=definition["joint"],
                                           max_evaluations=args.max_evaluations)
            qualification_started = perf_counter()
            arrays[definition["name"]+"_weighted_real_jacobian"] = fit.pop("scaled_weighted_real_jacobian")
            record["fit"] = fit
            arrays[definition["name"]+"_final_physical"] = final.physical
            arrays[definition["name"]+"_final_radial_cosine"] = final.state.radius_cosine_coefficients
            arrays[definition["name"]+"_final_radial_sine"] = final.state.radius_sine_coefficients
            arrays[definition["name"]+"_final_center"] = final.state.center
            geometry, spectrum = geometry_metrics(radial_fourier_parameterization(final.state), reference_curve,
                                                  audit_samples=128, localization_samples=512)
            for key, value in spectrum.items():
                arrays[definition["name"]+"_"+key] = value
            record["geometry"] = geometry
            record["material_absolute_error"] = abs(float(final.physical[5]-TRUTH[5]))
            record["radius_absolute_error_m"] = abs(float(final.physical[0]-TRUTH[0]))
            record["center_error_m"] = float(np.linalg.norm(final.physical[1:3]-TRUTH[1:3]))
            record["spurious_radial_mode2_amplitude_m"] = float(np.hypot(*final.physical[3:5]))
            audits = []
            for count in args.audit_nodes:
                predictions, work, conditions = {}, {}, []
                for name, problem, reference in (("train", train, train_clean), ("holdout", holdout, holdout_clean)):
                    audit = MaterialCurveEvaluator(problem, reference, nodes=count)
                    actual = audit.evaluate(final.scaled)
                    predictions[name] = actual.prediction
                    arrays[f"{definition['name']}_{name}_prediction_N{count}"] = actual.prediction
                    work[name] = dict(audit.work)
                    condition_started = perf_counter()
                    conditions.extend(float(np.linalg.cond(value.system.system_matrix)) for value in actual.forward_results)
                    work[name]["conditioning_audit_seconds"] = perf_counter()-condition_started
                audits.append({"nodes": count, "train_clean_relative_error": relative_error(predictions["train"], train_clean),
                    "train_observed_relative_error": relative_error(predictions["train"], observed),
                    "holdout_clean_relative_error": relative_error(predictions["holdout"], holdout_clean),
                    "holdout_noisy_relative_error": relative_error(predictions["holdout"], holdout_noisy),
                    "maximum_system_condition": max(conditions),
                    "self_convergence_to_next_nodes": None, "work": work})
            for index, audit in enumerate(audits[:-1]):
                audit["self_convergence_to_next_nodes"] = max(relative_error(
                    arrays[f"{definition['name']}_{name}_prediction_N{args.audit_nodes[index]}"],
                    arrays[f"{definition['name']}_{name}_prediction_N{args.audit_nodes[index+1]}"])
                    for name in ("train", "holdout"))
            record["forward_audits"] = audits
            resolved = audits[-2]["self_convergence_to_next_nodes"] <= GATES["forward_self_convergence"]
            field_gate = GATES["noisy_clean_holdout_relative_field_error"] if definition["noisy"] else GATES["clean_relative_field_error"]
            record["physical_recovery_passed"] = bool(resolved and record["material_absolute_error"] <= GATES["material_absolute_error"]
                and geometry["symmetric_set_distance_m"] <= GATES["geometry_symmetric_distance_m"]
                and geometry["set_distance_refinement_change_m"] <= GATES["geometry_refinement_change_m"]
                and geometry["closest_point_localization_refinement_agreement_m"] <= GATES["geometry_refinement_change_m"]
                and audits[-1]["holdout_clean_relative_error"] <= field_gate)
            record["forward_self_converged"] = resolved
            record["status"] = "completed"
            record["failure_reason"] = None
            record["qualification_seconds"] = perf_counter()-qualification_started
            print(f"  eps={final.physical[5]:.7f}, stationary={fit['verified_stationarity']}, physical={record['physical_recovery_passed']}", flush=True)
        except (FloatingPointError, np.linalg.LinAlgError) as error:
            record.update({"status": "failed", "failure_reason": f"{type(error).__name__}: {error}",
                           "work": dict(evaluator.work), "candidate_history": evaluator.history,
                           "physical_recovery_passed": False})
            print(f"  failed: {record['failure_reason']}", flush=True)
        record["total_seconds"] = perf_counter()-arm_started
        records.append(record)
        write_strict_json(args.output/"metrics.json", {"records": records, "sensitivity_audit": sensitivity})
        write_npz(args.output/"arrays.npz", arrays)
    unchanged = (hashlib.sha256(train_clean.tobytes()).hexdigest() == train_report["clean_sha256"]
        and hashlib.sha256(train_noisy.tobytes()).hexdigest() == train_report["noisy_sha256"]
        and hashlib.sha256(holdout_clean.tobytes()).hexdigest() == holdout_report["clean_sha256"]
        and hashlib.sha256(holdout_noisy.tobytes()).hexdigest() == holdout_report["noisy_sha256"])
    result = {"records": records, "sensitivity_audit": sensitivity, "observations_unchanged": unchanged,
        "material_sensitivity_validation_passed": all(record["passed"] for record in sensitivity),
        "observation_preparation_seconds": observation_preparation_seconds,
        "sensitivity_audit_seconds": sensitivity_seconds,
        "elapsed_seconds": perf_counter()-started,
        "source_hash_changes_during_run": {name: {"before": before,
            "after": hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}
            for name, before in manifest["provenance"]["source_sha256"].items()
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != before}}
    counted_work = [record["work"] for record in sensitivity]
    for record in records:
        counted_work.append(record["fit"]["work"] if "fit" in record else record["work"])
        counted_work.extend(work for audit in record.get("forward_audits", ()) for work in audit["work"].values())
    result["work_totals"] = {name: sum(work.get(name, 0) for work in counted_work)
        for name in ("candidate_builds", "forward_solves", "failed_forward_solves", "invalid_candidate_probes",
                     "analytic_direction_evaluations", "forward_seconds", "jacobian_seconds", "conditioning_audit_seconds")}
    result["work_totals"]["Mie_frequency_evaluations"] = (
        train_report["Mie_frequency_evaluations"]+holdout_report["Mie_frequency_evaluations"]
        +sum(record["Mie_frequency_evaluations"] for record in sensitivity))
    if not unchanged:
        raise RuntimeError("Frozen observations changed.")
    write_strict_json(args.output/"metrics.json", result)
    write_metrics_csv(args.output/"metrics.csv", [{key: value for key, value in record.items()
        if key not in {"fit", "geometry", "forward_audits", "candidate_history"}} for record in records])
    print(f"D saved {len(records)} arms in {result['elapsed_seconds']:.2f}s to {args.output}", flush=True)
    return result


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--nodes", type=int, default=64)
    result.add_argument("--audit-nodes", type=int, nargs="+", default=[64, 128, 256])
    result.add_argument("--max-evaluations", type=int, default=40)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
