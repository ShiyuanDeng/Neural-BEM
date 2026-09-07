#!/usr/bin/env python3
"""Bounded robustness controls for fixed-topology shape/interior-epsr inversion.

Historical circle data are loaded, never regenerated. All workflow selection
finishes and is checkpointed before holdout/geometry qualification begins.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
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

from gpr_bem_kress import KressSolveConfig
from sdf_inverse import MaterialSpec, PairedForwardProblem
from sdf_inverse.curve_updates import radial_fourier_parameterization
from sdf_inverse.material_inverse import (
    MaterialCurveEvaluator, PARAMETER_NAMES, PARAMETER_ORIGIN, PARAMETER_SCALES,
    PHYSICAL_LOWER, PHYSICAL_UPPER, candidate_state, scaled_parameters,
)
from sdf_inverse.nystrom_oracle import nystrom_paired_response
from sdf_to_ordered_boundary.artifacts import write_metrics_csv, write_npz, write_strict_json
from run_parameterization_aware_comparison import geometry_metrics
from run_material_inverse_comparison import relative_error, snapshot


FROZEN_D = ROOT/"results/material_inverse/bounded-20260906"
NONCIRCULAR_TRUTH = np.array([.052, .503, .497, .0025, -.0015, 8.4])
NONCIRCULAR_TRUTH.setflags(write=False)
GATES = {"oracle_self_convergence": 1e-8, "forward_self_convergence": 1e-5,
    "geometry_symmetric_distance_m": 2e-4, "geometry_refinement_change_m": 2e-6,
    "material_absolute_error": .1, "clean_holdout_relative_field_error": 1e-4,
    "noisy_clean_holdout_relative_field_error": .02,
    "stationarity_scaled_projected_gradient_inf": 1e-7}


def readonly(values, dtype=None):
    result = np.array(values, dtype=dtype, copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError("Frozen numeric data must be finite.")
    result.setflags(write=False)
    return result


def value_hash(values):
    """Content hash compatible with historical D observation hashes."""
    return hashlib.sha256(np.asarray(values).tobytes()).hexdigest()


@dataclass(frozen=True)
class Dataset:
    name: str
    train_problem: PairedForwardProblem
    holdout_problem: PairedForwardProblem
    train_clean: np.ndarray
    train_noisy: np.ndarray
    train_noise: np.ndarray
    holdout_clean: np.ndarray
    holdout_noisy: np.ndarray
    holdout_noise: np.ndarray
    truth_physical: np.ndarray
    provenance: dict

    def arrays(self):
        return {key: getattr(self, key) for key in ("train_clean", "train_noisy", "train_noise",
            "holdout_clean", "holdout_noisy", "holdout_noise", "truth_physical")}


def problem_from_frozen_snapshot(metadata, archive, prefix):
    arrays = {}
    for key in ("source_points", "receiver_points", "angular_frequencies", "source_strengths"):
        arrays[key] = readonly(archive[prefix+"_"+key])
        expected = (np.asarray(metadata["source_strengths_real"])+1j*np.asarray(metadata["source_strengths_imag"])
                    if key == "source_strengths" else np.asarray(metadata[key]))
        if not np.array_equal(arrays[key], expected):
            raise ValueError(f"Historical {prefix}/{key} arrays and manifest disagree.")
    return PairedForwardProblem(**arrays, exterior=MaterialSpec(**metadata["exterior"]),
        interior=MaterialSpec(**metadata["interior_template_not_candidate"]),
        eps0=metadata["eps0"], mu0=metadata["mu0"])


def load_frozen_circle(directory=FROZEN_D):
    """Replay exact D values and acquisition; this function has no solver call."""
    directory = Path(directory)
    manifest = json.loads((directory/"manifest.json").read_text())
    with np.load(directory/"arrays.npz", allow_pickle=False) as archive:
        train = problem_from_frozen_snapshot(manifest["train_acquisition"], archive, "train")
        holdout = problem_from_frozen_snapshot(manifest["holdout_acquisition"], archive, "holdout")
        arrays = {key: readonly(archive[key]) for key in ("train_clean", "train_noisy", "train_noise",
            "holdout_clean", "holdout_noisy", "holdout_noise", "truth_physical")}
    for cohort in ("train", "holdout"):
        for kind in ("clean", "noisy"):
            if value_hash(arrays[cohort+"_"+kind]) != manifest[cohort+"_observations"][kind+"_sha256"]:
                raise ValueError(f"Historical {cohort}/{kind} observation hash mismatch.")
        if not np.array_equal(arrays[cohort+"_clean"]+arrays[cohort+"_noise"], arrays[cohort+"_noisy"]):
            raise ValueError("Historical clean/noise/noisy cohort relation failed.")
    return Dataset("circle", train, holdout, **arrays, provenance={
        "identity": "verbatim_frozen_D_Mie_observations", "regenerated": False,
        "source_directory": str(directory), "source_sha256": {
            name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
            for name in ("manifest.json", "arrays.npz", "metrics.json")},
        "train_reference": manifest["train_observations"], "holdout_reference": manifest["holdout_observations"],
        "historical_initial_joint_high_eps": next(arm["initial"] for arm in manifest["arms"] if arm["name"] == "joint_clean_start2"),
        "historical_initial_fixed_high_eps": next(arm["initial"] for arm in manifest["arms"] if arm["name"] == "fixed_clean_eps9")})


def refined_native_oracle(problem, truth, *, nodes=(128, 256, 512, 1024)):
    """Independent numerical kernels on the analytic radial curve, never Kress."""
    if len(nodes) < 2 or list(nodes) != sorted(set(nodes)) or any(n < 16 or n%2 for n in nodes):
        raise ValueError("Need increasing even independent oracle resolutions.")
    _, state = candidate_state(scaled_parameters(truth))
    curve = radial_fourier_parameterization(state)
    target_problem = replace(problem, interior=MaterialSpec(float(truth[5])))
    def parameterization(t):
        evaluation = curve.evaluate(t)
        return evaluation.points, evaluation.first_derivatives
    started = perf_counter()
    previous, history, solves = None, [], 0
    for count in nodes:
        response = nystrom_paired_response(target_problem, parameterization, num_nodes=count,
                                          curve_name="independent_noncircular_radial_k2")
        solves += problem.num_frequencies
        if previous is not None:
            difference = relative_error(response.scattered_response, previous.scattered_response)
            history.append({"coarse_nodes": previous.num_nodes, "fine_nodes": response.num_nodes,
                            "maximum_per_frequency_relative_difference": difference})
            if difference <= GATES["oracle_self_convergence"]:
                return readonly(response.scattered_response), {"identity": "independent_nystrom_ref_native_radial_k2",
                    "history": history, "passed": True, "final_nodes": count, "frequency_solves": solves,
                    "seconds": perf_counter()-started,
                    "maximum_linear_system_relative_residual": response.maximum_linear_system_relative_residual,
                    "limitation": "separately implemented kernels/quadrature; same Muller/Nystrom mathematical family"}
        previous = response
    raise RuntimeError(f"Independent noncircular observations failed frozen refinement gate: {history}")


def noisy_copy(clean, *, seed):
    generator = np.random.default_rng(seed)
    sigma = .01*np.linalg.norm(clean, axis=0)/np.sqrt(len(clean))
    noise = sigma[None, :]*(generator.standard_normal(clean.shape)+1j*generator.standard_normal(clean.shape))/np.sqrt(2.)
    return readonly(clean+noise), readonly(noise), {"seed": seed, "fraction_of_per_frequency_pair_rms": .01,
        "complex_standard_deviation_per_frequency": sigma.tolist(), "distribution": "circular_complex_Gaussian"}


def independent_noncircular(circle, *, oracle_nodes=(128, 256, 512, 1024)):
    clean_train, train_report = refined_native_oracle(circle.train_problem, NONCIRCULAR_TRUTH, nodes=oracle_nodes)
    clean_holdout, holdout_report = refined_native_oracle(circle.holdout_problem, NONCIRCULAR_TRUTH, nodes=oracle_nodes)
    train_noisy, train_noise, train_noise_report = noisy_copy(clean_train, seed=4306)
    holdout_noisy, holdout_noise, holdout_noise_report = noisy_copy(clean_holdout, seed=4316)
    return Dataset("noncircular", circle.train_problem, circle.holdout_problem, clean_train, train_noisy,
        train_noise, clean_holdout, holdout_noisy, holdout_noise, NONCIRCULAR_TRUTH,
        {"identity": "independently_specified_radial_K2_target", "train_reference": train_report,
         "holdout_reference": holdout_report, "train_noise": train_noise_report,
         "holdout_noise": holdout_noise_report,
         "training_problem_interior_template": "historical D template retained; candidate material always rebuilt; truth epsr is only passed to independent oracle/qualification"})


def provenance(frozen_directory):
    paths = [Path(__file__), ROOT/"run_material_inverse_comparison.py", ROOT/"run_parameterization_aware_comparison.py",
             ROOT/"docs/codex_sdf_kress_priorities_2026-09-05.md"]
    for package in ("sdf_inverse", "sdf_to_ordered_boundary", "ordered_boundary", "gpr_bem_kress", "gpr_bem_ref", "periodic_kress", "nystrom_ref"):
        paths.extend(sorted((ROOT/"solvers"/package).glob("*.py")))
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    return {"git_commit": git("rev-parse", "HEAD"), "dirty_state": git("status", "--short"),
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        "frozen_D_sha256": {name: hashlib.sha256((frozen_directory/name).read_bytes()).hexdigest()
                            for name in ("manifest.json", "arrays.npz", "metrics.json")},
        "python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform(),
        "thread_caps": {name: os.environ.get(name) for name in
            ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}}


def workflow_definitions(circle):
    """Declared high-material controls; seeds are entirely owned by the core."""
    joint_initial = readonly(circle.provenance["historical_initial_joint_high_eps"])
    fixed_initial = readonly(circle.provenance["historical_initial_fixed_high_eps"])
    result = []
    for case_name in ("circle", "noncircular"):
        for noisy in (False, True):
            for policy in ("full_band", "continuation", "multistart"):
                result.append({"name": f"{case_name}_joint_{'noisy' if noisy else 'clean'}_{policy}",
                    "case": case_name, "joint_shape": True, "noisy": noisy, "policy": policy,
                    "initial_physical": joint_initial})
    for policy in ("full_band", "continuation", "multistart"):
        result.append({"name": f"circle_fixed_clean_{policy}", "case": "circle", "joint_shape": False,
                       "noisy": False, "policy": policy, "initial_physical": fixed_initial})
    return result


def save_nested_arrays(value, prefix, arrays):
    """Retain all numeric diagnostics without pickling arbitrary report state."""
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise ValueError("Object arrays are forbidden in workflow diagnostics.")
        arrays[prefix] = value
    elif isinstance(value, dict):
        for key, item in value.items():
            save_nested_arrays(item, prefix+"_"+str(key), arrays)
    elif isinstance(value, (tuple, list)):
        if "physical" in prefix and len(value) == 6 and all(isinstance(item, (int, float, np.number)) for item in value):
            arrays[prefix] = np.asarray(value, dtype=float)
        else:
            for index, item in enumerate(value):
                save_nested_arrays(item, prefix+f"_{index}", arrays)


def qualify_selected(case, definition, selected, report, args, arrays):
    """Post-selection audit only; this function never chooses/restarts a fit."""
    if selected is None:
        return {"status": "no_selected_candidate", "physical_recovery_passed": False,
                "seconds": 0., "forward_audits": [], "work": {}}
    started = perf_counter()
    prefix = definition["name"]
    observed = case.train_noisy if definition["noisy"] else case.train_clean
    arrays[prefix+"_selected_physical"] = selected.physical
    arrays[prefix+"_selected_radial_cosine"] = selected.state.radius_cosine_coefficients
    arrays[prefix+"_selected_radial_sine"] = selected.state.radius_sine_coefficients
    arrays[prefix+"_selected_center"] = selected.state.center
    truth_curve = radial_fourier_parameterization(candidate_state(scaled_parameters(case.truth_physical))[1])
    geometry, spectrum = geometry_metrics(radial_fourier_parameterization(selected.state), truth_curve,
                                          audit_samples=128, localization_samples=512)
    for key, value in spectrum.items():
        arrays[prefix+"_"+key] = value
    audit_records, work_records = [], []
    replay_difference = None
    for nodes in args.audit_nodes:
        predictions, conditions, stage_work = {}, [], {}
        for name, problem, normalization_data in (("train", case.train_problem, observed),
                                                  ("holdout", case.holdout_problem, case.holdout_clean)):
            evaluator = MaterialCurveEvaluator(problem, normalization_data, nodes=nodes)
            actual = evaluator.evaluate(selected.scaled)
            predictions[name] = actual.prediction
            arrays[f"{prefix}_{name}_prediction_N{nodes}"] = actual.prediction
            stage_work[name] = dict(evaluator.work)
            condition_started = perf_counter()
            conditions.extend(float(np.linalg.cond(value.system.system_matrix)) for value in actual.forward_results)
            stage_work[name]["conditioning_audit_seconds"] = perf_counter()-condition_started
            work_records.append(stage_work[name])
            if name == "train" and nodes == args.nodes:
                loss = .5*float(actual.residual@actual.residual)
                replay_difference = abs(loss-float(report["selected_training_loss"]))
                if replay_difference > 1e-10*(1+abs(loss)):
                    raise RuntimeError("Selected full-band objective does not replay under immutable weighting.")
        audit_records.append({"nodes": nodes, "maximum_system_condition": max(conditions),
            "train_clean_relative_error": relative_error(predictions["train"], case.train_clean),
            "train_observed_relative_error": relative_error(predictions["train"], observed),
            "holdout_clean_relative_error": relative_error(predictions["holdout"], case.holdout_clean),
            "holdout_noisy_relative_error": relative_error(predictions["holdout"], case.holdout_noisy),
            "self_convergence_to_next_nodes": None, "work": stage_work})
    for index, audit in enumerate(audit_records[:-1]):
        audit["self_convergence_to_next_nodes"] = max(relative_error(
            arrays[f"{prefix}_{name}_prediction_N{args.audit_nodes[index]}"],
            arrays[f"{prefix}_{name}_prediction_N{args.audit_nodes[index+1]}"])
            for name in ("train", "holdout"))
    resolved = audit_records[-2]["self_convergence_to_next_nodes"] <= GATES["forward_self_convergence"]
    material_error = abs(float(selected.physical[5]-case.truth_physical[5]))
    tolerance = GATES["noisy_clean_holdout_relative_field_error"] if definition["noisy"] else GATES["clean_holdout_relative_field_error"]
    passed = (resolved and material_error <= GATES["material_absolute_error"]
        and geometry["symmetric_set_distance_m"] <= GATES["geometry_symmetric_distance_m"]
        and geometry["set_distance_refinement_change_m"] <= GATES["geometry_refinement_change_m"]
        and geometry["closest_point_localization_refinement_agreement_m"] <= GATES["geometry_refinement_change_m"]
        and audit_records[-1]["holdout_clean_relative_error"] <= tolerance)
    return {"status": "audited", "physical_recovery_passed": bool(passed),
        "material_absolute_error": material_error, "geometry": geometry,
        "radius_absolute_error_m": abs(float(selected.physical[0]-case.truth_physical[0])),
        "center_error_m": float(np.linalg.norm(selected.physical[1:3]-case.truth_physical[1:3])),
        "radial_mode2_error_m": float(np.linalg.norm(selected.physical[3:5]-case.truth_physical[3:5])),
        "forward_self_converged": bool(resolved), "selected_training_loss_replay_absolute_difference": replay_difference,
        "forward_audits": audit_records, "seconds": perf_counter()-started,
        "work": {key: sum(work.get(key, 0) for work in work_records)
            for key in ("candidate_builds", "forward_solves", "forward_seconds", "conditioning_audit_seconds")}}


def run(args):
    from sdf_inverse.robust_material_inverse import RobustMaterialConfig, solve_robust_material
    if args.output.exists():
        raise FileExistsError("Use a fresh output directory; historical artifacts are immutable.")
    if len(args.audit_nodes) < 2 or args.audit_nodes != sorted(set(args.audit_nodes)) or args.nodes not in args.audit_nodes:
        raise ValueError("Increasing distinct audit nodes must include optimization N and at least one refinement.")
    if any(n < 16 or n%2 for n in args.audit_nodes):
        raise ValueError("Audit node counts must be even and at least sixteen.")
    configs = {policy: RobustMaterialConfig(policy=policy, nodes=args.nodes,
        stage_max_evaluations=tuple(args.stage_max_evaluations), maximum_forward_solves=args.maximum_forward_solves,
        maximum_direction_evaluations=args.maximum_direction_evaluations, screening_keep=2)
        for policy in ("full_band", "continuation", "multistart")}
    started = perf_counter()
    args.output.mkdir(parents=True)
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "provenance": provenance(args.frozen_d),
        "command": shlex.join([sys.executable, *sys.argv]),
        "configuration": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "robust_configs": {key: asdict(value) for key, value in configs.items()}, "gates": GATES,
        "parameter_names": PARAMETER_NAMES, "parameter_origin": PARAMETER_ORIGIN, "parameter_scales": PARAMETER_SCALES,
        "physical_lower_bounds": PHYSICAL_LOWER, "physical_upper_bounds": PHYSICAL_UPPER,
        "kress_solve_config": asdict(KressSolveConfig()), "new_noncircular_truth_physical": NONCIRCULAR_TRUTH,
        "scope": "fixed count, gauge-fixed radial K2 shape plus one positive lossless interior epsr; known exterior/acquisition/sources; no production default change",
        "selection_policy": "all policies use training observations only; continuation is cumulative low/full band; deterministic contrast-stratified screening; final common full-band training objective only",
        "phase_barrier": "all 15 workflow selections and selected-parameter hashes checkpointed before any holdout/geometry qualification",
        "budget_policy": "bounded but not matched-cost policies; every screening/failed/stage/selection derivative and solve counted; workflow versus qualification costs separate",
        "observations_policy": "circle data and acquisitions loaded verbatim from frozen D, never regenerated; new opposite-contrast noncircular truth from independently refined Nyström kernels"}
    write_strict_json(args.output/"manifest.json", manifest)
    data_started = perf_counter()
    circle = load_frozen_circle(args.frozen_d)
    noncircular = independent_noncircular(circle, oracle_nodes=tuple(args.oracle_nodes))
    datasets = {case.name: case for case in (circle, noncircular)}
    data_seconds = perf_counter()-data_started
    definitions = workflow_definitions(circle)
    arrays = {case.name+"_"+key: value for case in datasets.values() for key, value in case.arrays().items()}
    for cohort, problem in (("train", circle.train_problem), ("holdout", circle.holdout_problem)):
        for key in ("source_points", "receiver_points", "angular_frequencies", "source_strengths"):
            arrays[cohort+"_"+key] = getattr(problem, key)
    original_hashes = {key: value_hash(value) for key, value in arrays.items()}
    data_report = {"datasets": {name: case.provenance for name, case in datasets.items()},
        "acquisition": {"train": snapshot(circle.train_problem), "holdout": snapshot(circle.holdout_problem)},
        "input_hashes": original_hashes, "data_preparation_seconds": data_seconds, "workflows": definitions}
    write_strict_json(args.output/"data_manifest.json", data_report)
    write_npz(args.output/"arrays.npz", arrays)
    selections, records = [], []
    for definition in definitions:
        case = datasets[definition["case"]]
        observed = case.train_noisy if definition["noisy"] else case.train_clean
        print(f"Robust D selecting {definition['name']}", flush=True)
        workflow_started = perf_counter()
        selected, report = solve_robust_material(case.train_problem, observed, definition["initial_physical"],
            joint_shape=definition["joint_shape"], config=configs[definition["policy"]])
        seconds = perf_counter()-workflow_started
        record = {"definition": definition, "workflow": report, "workflow_seconds": seconds,
                  "selected_physical_sha256": None if selected is None else value_hash(selected.physical)}
        save_nested_arrays(report, definition["name"]+"_workflow", arrays)
        if selected is not None:
            arrays[definition["name"]+"_selected_physical"] = selected.physical
        records.append(record); selections.append(selected)
        write_strict_json(args.output/"selections.json", {"phase_complete": False, "records": records})
        write_npz(args.output/"arrays.npz", arrays)
        print(f"  selected={report.get('selected_physical')}, status={report.get('status')}", flush=True)
    selection_hashes = {record["definition"]["name"]: record["selected_physical_sha256"] for record in records}
    write_strict_json(args.output/"selections.json", {"phase_complete": True, "selected_parameter_hashes": selection_hashes,
        "records": records, "qualification_started": False})
    selection_file_hash = hashlib.sha256((args.output/"selections.json").read_bytes()).hexdigest()
    # This is the first boundary at which predictions may meet held-out data
    # or target geometry. No later fitting/restart/selection calls exist below.
    for record, selected in zip(records, selections):
        definition = record["definition"]
        record["qualification"] = qualify_selected(datasets[definition["case"]], definition, selected,
            record["workflow"], args, arrays)
        if selected is not None and value_hash(selected.physical) != record["selected_physical_sha256"]:
            raise RuntimeError("Selected candidate changed during qualification.")
        print(f"Robust D qualified {definition['name']}: {record['qualification']['physical_recovery_passed']}", flush=True)
        write_strict_json(args.output/"metrics.json", {"records": records, "selection_file_sha256": selection_file_hash})
        write_npz(args.output/"arrays.npz", arrays)
    unchanged = all(value_hash(arrays[key]) == digest for key, digest in original_hashes.items())
    if not unchanged or hashlib.sha256((args.output/"selections.json").read_bytes()).hexdigest() != selection_file_hash:
        raise RuntimeError("Frozen input data or sealed selection checkpoint changed.")
    result = {"records": records, "observations_and_acquisition_unchanged": unchanged,
        "selection_file_sha256": selection_file_hash, "selection_checkpoint_unchanged": True,
        "qualification_only_after_all_selections": True, "data_preparation_seconds": data_seconds,
        "workflow_seconds": sum(record["workflow_seconds"] for record in records),
        "qualification_seconds": sum(record["qualification"]["seconds"] for record in records),
        "elapsed_seconds": perf_counter()-started,
        "source_hash_changes_during_run": {name: {"before": before, "after": hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}
            for name, before in manifest["provenance"]["source_sha256"].items()
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != before}}
    result["workflow_work_totals"] = {key: sum(record["workflow"]["work"].get(key, 0) for record in records)
        for key in ("forward_solves", "analytic_direction_evaluations", "candidate_builds", "cache_hits",
                    "invalid_candidate_probes", "failed_forward_solves", "failed_direction_evaluations",
                    "forward_seconds", "jacobian_seconds")}
    result["qualification_work_totals"] = {key: sum(record["qualification"]["work"].get(key, 0) for record in records)
        for key in ("forward_solves", "candidate_builds", "forward_seconds", "conditioning_audit_seconds")}
    result["new_independent_oracle_frequency_solves"] = sum(
        noncircular.provenance[cohort+"_reference"].get("frequency_solves", 0) for cohort in ("train", "holdout"))
    result["historical_circle_observation_generation_solves"] = 0
    write_strict_json(args.output/"metrics.json", result)
    rows = []
    for record in records:
        definition, workflow, qualification = record["definition"], record["workflow"], record["qualification"]
        row = {key: definition[key] for key in ("name", "case", "policy", "joint_shape", "noisy")}
        row.update({"workflow_status": workflow.get("status"), "verified_stationarity": workflow.get("verified_stationarity"),
            "search_completed": workflow.get("search_completed"), "budget_exhausted": workflow.get("budget_exhausted"),
            "selected_training_loss": workflow.get("selected_training_loss"), "workflow_seconds": record["workflow_seconds"],
            "qualification_seconds": qualification["seconds"], "physical_recovery_passed": qualification["physical_recovery_passed"],
            "forward_solves": workflow["work"].get("forward_solves"),
            "analytic_direction_evaluations": workflow["work"].get("analytic_direction_evaluations")})
        if qualification["status"] == "audited":
            row.update({"material_absolute_error": qualification["material_absolute_error"],
                "geometry_symmetric_distance_m": qualification["geometry"]["symmetric_set_distance_m"],
                "holdout_clean_relative_error": qualification["forward_audits"][-1]["holdout_clean_relative_error"]})
        rows.append(row)
    write_metrics_csv(args.output/"metrics.csv", rows)
    print(f"Robust D saved {len(records)} workflows in {result['elapsed_seconds']:.2f}s to {args.output}", flush=True)
    return result


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--frozen-d", type=Path, default=FROZEN_D)
    result.add_argument("--nodes", type=int, default=64)
    result.add_argument("--audit-nodes", type=int, nargs="+", default=[64, 128, 256])
    result.add_argument("--oracle-nodes", type=int, nargs="+", default=[128, 256, 512, 1024])
    result.add_argument("--stage-max-evaluations", type=int, nargs=2, default=[40, 40])
    result.add_argument("--maximum-forward-solves", type=int, default=400)
    result.add_argument("--maximum-direction-evaluations", type=int, default=2400)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
