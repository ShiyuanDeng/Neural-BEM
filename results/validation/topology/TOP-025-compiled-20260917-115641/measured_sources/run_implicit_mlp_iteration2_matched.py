#!/usr/bin/env python3
"""Bounded iteration-2 neural comparisons; default prints a plan, never trains.

``qualify`` performs frozen numerical integration gates. ``run`` requires that
exact qualification. The default short experiment permits five accepted updates;
the evidence-gated long acquisition experiment permits at most sixty. All
3 GHz scores are computed after both training trajectories have been fixed.
``all`` runs qualification and then both actual inverse arms in one command.
"""

from __future__ import annotations

import argparse
import copy
from contextlib import redirect_stderr, redirect_stdout
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

import numpy as np
import torch

import run_sdf_inverse_comparison as driver
from sdf_inverse.forward import (
    IndexedForwardProblem, PairedForwardProblem, predict_indexed_curve_response,
    predict_indexed_response, predict_paired_response,
)
from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from sdf_inverse.geometry import build_ordered_sdf_geometry
from sdf_inverse.implicit_adjoint import (
    ImplicitMLPAdjointConfig, implicit_mlp_data_gradient, run_implicit_mlp_adjoint_inverse,
)
from sdf_inverse.models import SirenImplicitField2D, build_siren_parameter_controller
from sdf_inverse.nystrom_oracle import nystrom_paired_response
from sdf_inverse.optimization import ComplexScatteredData, normalized_complex_residual


ROOT = Path(__file__).resolve().parent
DEFAULT_BUNDLE = ROOT / "results/inverse/implicit_mlp/2026-09-08/star"
DEFAULT_OUTPUT = ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final/matched"
NORMALIZATION = "0.5 * sum_f ||prediction_f-observed_f||^2 / fixed_observed_column_norm_f^2; unit frequency weights; no entry-count divisor"
EXPERIMENT_DEFAULTS = {"short": (5, 120, 600.), "long": (60, 1440, 3600.)}


def reporting_policy(experiment):
    return {
        "accepted_geometry": "every accepted state, including initialization and final state",
        "optimizer_proposals": "every true optimizer record, including rejected proposals",
        "optimizer_checkpoints": ("one file per fresh optimizer record" if experiment == "long"
                                  else "cumulative optimizer_records.pt"),
        "finite_proposal_geometry": ("optimizer iteration 0, every 10th index, and final available optimizer iteration"
                                     if experiment == "long" else "every optimizer iteration"),
        "proposal_selection_uses_target_or_evaluation": False,
        "posthoc_timing": "after both serialized inverse results; excluded from per-arm inverse wall cap",
    }


def caps_per_arm(args):
    return {"accepted_updates": args.accepted_updates, "attempted_candidates": args.candidate_cap,
            "wall_seconds": args.wall_seconds}


def selected_proposal_iterations(records, experiment):
    """Predeclared index selection, independent of loss, target, and holdout."""
    iterations = sorted({int(record["iteration"]) for record in records})
    if experiment == "short" or not iterations:
        return iterations
    return sorted({iterations[0], iterations[-1]} | {i for i in iterations if i % 10 == 0})


def reviewed_initialization(args):
    return {"checkpoint_sha256": sha256(args.bundle / "kress_model.pt"),
            "trajectory_sha256": sha256(args.bundle / "kress_trajectory.csv"),
            "state": args.state}


def write_json(path, value):
    def finite_json(value):
        if isinstance(value, dict):
            return {key: finite_json(item) for key, item in value.items()}
        if isinstance(value, list):
            return [finite_json(item) for item in value]
        if isinstance(value, complex):
            return {"real": finite_json(value.real), "imag": finite_json(value.imag)}
        return None if isinstance(value, float) and not np.isfinite(value) else value
    Path(path).write_text(json.dumps(finite_json(driver._jsonable(value)), indent=2, allow_nan=False) + "\n")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def comparison_arms(comparison, sampling="uniform_box"):
    if comparison == "sampling":
        return [("S0", "paired12", (0.5, 1.5), "uniform_box"),
                ("S1", "paired12", (0.5, 1.5), "contour_band")]
    if comparison == "acquisition":
        return [("E0", "paired", (0.5, 1.5), sampling),
                ("E1", "multistatic", (0.5, 1.5), sampling)]
    if comparison == "high_band":
        return [("F0", "multistatic", (0.5, 1.5), sampling),
                ("F1", "multistatic", (1.5, 2.5), sampling)]
    raise ValueError(f"Unknown comparison: {comparison}")


def required_evidence(args):
    requirements = []
    if args.comparison == "sampling" or args.sampling == "contour_band":
        requirements.append("stage4_supports_field_conditioning")
    if args.comparison == "high_band":
        requirements.append("stage7_original_band_multistatic_conditioning_limited")
    if args.experiment == "long":
        requirements.append("stage7_supports_long_acquisition")
    return requirements


def validate_evidence(args):
    """Require review decisions with hash-bound measured reports, not a flag."""
    required = required_evidence(args)
    if not required:
        return {}
    if args.evidence is None:
        raise ValueError(f"--evidence is required for {', '.join(required)}")
    evidence = json.loads(args.evidence.read_text())
    for key in required:
        decision = evidence.get(key, {})
        if decision.get("supported") is not True or not str(decision.get("reason", "")).strip():
            raise ValueError(f"Evidence must explicitly support {key} and explain the measured reason")
        report = args.evidence.parent / decision.get("report", "")
        if not report.is_file() or decision.get("report_sha256") != sha256(report):
            raise ValueError(f"Evidence for {key} must reference an existing report and its SHA256")
        if key == "stage7_supports_long_acquisition":
            promotion = json.loads(report.read_text())
            if report.name != "promotion.json":
                raise ValueError("Long acquisition evidence must reference the reviewed promotion.json")
            if promotion.get("reviewed_initialization") != reviewed_initialization(args):
                raise ValueError("Long acquisition evidence reviewed_initialization does not match the requested checkpoint, trajectory and state")
            if (promotion.get("selected_principal_factor") != "acquisition"
                    or promotion.get("status") != "supports_long_controlled_comparison"):
                raise ValueError("promotion.json must support a long controlled comparison with acquisition as the single principal factor")
    return {"path": str(args.evidence.resolve()), "sha256": sha256(args.evidence), "decisions": evidence}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("plan", "qualify", "run", "all"), default="plan")
    parser.add_argument("--experiment", choices=("short", "long"), default="short")
    parser.add_argument("--comparison", choices=("sampling", "acquisition", "high_band"), default="acquisition")
    parser.add_argument("--sampling", choices=("uniform_box", "contour_band"), default="uniform_box")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--state", type=int, default=0)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--accepted-updates", type=int, default=None)
    parser.add_argument("--candidate-cap", type=int, default=None)
    parser.add_argument("--wall-seconds", type=float, default=None)
    args = parser.parse_args(argv)
    max_updates, max_candidates, default_seconds = EXPERIMENT_DEFAULTS[args.experiment]
    if args.accepted_updates is None:
        args.accepted_updates = max_updates
    if args.candidate_cap is None:
        args.candidate_cap = max_candidates
    if args.wall_seconds is None:
        args.wall_seconds = default_seconds
    if args.output_dir is None:
        prefix = "long-acquisition-" if args.experiment == "long" else "inverse-"
        args.output_dir = (DEFAULT_OUTPUT.parent / (prefix + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
                           if args.action == "all" else DEFAULT_OUTPUT)
        if args.experiment == "long" and args.action != "all":
            args.output_dir = DEFAULT_OUTPUT.with_name("matched-long-acquisition")
    if not 1 <= args.accepted_updates <= max_updates or not 1 <= args.candidate_cap <= max_candidates:
        parser.error(f"The {args.experiment} experiment permits 1..{max_updates} accepted updates and 1..{max_candidates} attempted candidates per arm")
    if args.experiment == "long" and (args.comparison != "acquisition" or args.sampling != "uniform_box" or args.state != 0):
        parser.error("The long experiment supports only acquisition with uniform_box sampling from the shared saved wrong-start state 0")
    if not np.isfinite(args.wall_seconds) or args.wall_seconds <= 0:
        parser.error("--wall-seconds must declare a finite positive per-arm wall-time cap")
    if args.state < 0:
        parser.error("--state must be nonnegative")
    return args


def optimizer_config(args, sampling):
    return ImplicitMLPAdjointConfig(
        max_iterations=args.accepted_updates,
        max_candidate_evaluations=args.candidate_cap,
        max_wall_seconds=args.wall_seconds,
        eikonal_weight=.01, regularization_samples=512,
        eikonal_sampling=sampling,
    )


def load_initial(args):
    """Restore actual saved weights, never rerun initialization/pretraining."""
    checkpoint = torch.load(args.bundle / "kress_model.pt", map_location="cpu", weights_only=False)
    constructor = dict(checkpoint["constructor"])
    constructor["dtype"] = torch.float64
    model = SirenImplicitField2D(**constructor)
    model.load_state_dict(checkpoint["state_dict"])
    controller = build_siren_parameter_controller(model)
    with (args.bundle / "kress_trajectory.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        names = ["raw_" + name for name in controller.names]
        if not set(names).issubset(reader.fieldnames):
            raise ValueError("Saved trajectory is missing named neural-weight columns")
        rows = [row for row in reader if int(float(row["iteration"])) == args.state]
    if len(rows) != 1 or len(names) != controller.num_parameters:
        raise ValueError("Saved trajectory must contain exactly one requested state and all neural weights")
    controller.assign(np.asarray([float(rows[0][name]) for name in names]))
    source_geometry = OrderedSDFGeometryConfig(**checkpoint["geometry_config"])
    geometry = matched_geometry_config(source_geometry)
    # Historical moments were not logged. A single explicit fresh Adam state
    # is persisted here and supplied unchanged to both arms, including late starts.
    initial_optimizer = torch.optim.Adam(model.parameters(), lr=.001).state_dict()
    return model, controller, geometry, {
        "constructor": checkpoint["constructor"],
        "state_dict": copy.deepcopy(model.state_dict()),
        "optimizer_state_dict": initial_optimizer,
        "optimizer_initialization": "identical fresh Adam; historical moments unavailable",
        "parameter_vector": controller.parameter_vector(),
        "source_state": args.state,
        "geometry_config": asdict(geometry),
        "source_geometry_config": asdict(source_geometry),
        "geometry_policy": "same saved production map; independently denser conversion audit shared by both arms",
    }


def matched_geometry_config(source):
    """Use the saved production map with an independently resolved common audit.

    Saved late-star audits show 512 samples produce a 9.98 um refinement
    difference while 1024 produce 0.357 um. Keep both physical limits fixed;
    change the audit sampling identically in both acquisition arms.
    """
    return replace(source, conversion_tolerance_m=2e-4,
                   conversion_audit_grid_shape=tuple(max(513, n) for n in source.grid_shape),
                   conversion_audit_samples=max(1024, 4 * source.bandwidth + 4))


def settings_signature(args, evidence):
    # Qualification covers the numerical implementations behind these wrappers,
    # including the indexed adjoint, oracle, geometry reverse and SIREN backend.
    # Hash their packages so a dependency edit cannot reuse stale qualification.
    sources = [Path(__file__), ROOT / "run_sdf_inverse_comparison.py"]
    sources.extend((ROOT / "config").glob("*.py"))
    for package in ("sdf_inverse", "sdf_to_ordered_boundary", "ordered_boundary",
                    "gpr_bem_kress", "gpr_bem_ref", "nystrom_ref"):
        sources.extend((ROOT / "solvers" / package).rglob("*.py"))
    sources = sorted(set(sources))
    return {
        **reviewed_initialization(args), "arms": comparison_arms(args.comparison, args.sampling),
        "experiment": args.experiment, "caps_per_arm": caps_per_arm(args),
        "reporting_policy": reporting_policy(args.experiment),
        "conversion_audit_policy": "explicit grid floor 513, samples max(1024,4*bandwidth+4); distance 0.2mm, refinement 0.01mm",
        "configs": [asdict(optimizer_config(args, arm[3]))
                    for arm in comparison_arms(args.comparison, args.sampling)],
        "evidence": evidence, "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in sources},
    }


def build_problem(acquisition, frequencies):
    target = driver.StarTarget()
    sources, receivers = driver._ring_scan(center=target.center, standoff=.30,
                                          num_pairs=12 if acquisition == "paired12" else 8)
    paired = driver._build_problem(frequencies, sources, receivers)
    return IndexedForwardProblem.from_paired(paired, multistatic=acquisition == "multistatic")


def expanded_oracle_problem(problem):
    """Independent oracle sees explicitly ordered physical pairs, no indexed selector."""
    return PairedForwardProblem(
        source_points=problem.source_points[problem.source_indices],
        receiver_points=problem.receiver_points[problem.receiver_indices],
        **{name: getattr(problem, name) for name in (
            "angular_frequencies", "source_strengths", "exterior", "interior", "eps0", "mu0")},
    )


def relative_difference(left, right):
    return float(np.max(np.linalg.norm(left - right, axis=0)
                        / np.maximum(np.linalg.norm(right, axis=0), np.finfo(float).tiny)))


def validated_observations(problem):
    exact = driver.StarTarget().shape.parameterization()
    oracle_problem = expanded_oracle_problem(problem)
    # Includes a reserved, independent 512/1024-node 3 GHz check.
    coarse = nystrom_paired_response(oracle_problem, exact, num_nodes=512).scattered_response
    fine = nystrom_paired_response(oracle_problem, exact, num_nodes=1024).scattered_response
    error = relative_difference(coarse, fine)
    return fine, {"coarse_nodes": 512, "fine_nodes": 1024,
                  "relative_difference": error, "passed": error <= 1e-8}


def data_loss(model, data, geometry):
    prediction = predict_indexed_response(model, data.forward_problem, geometry).scattered_response
    residual, _ = normalized_complex_residual(prediction, data.observed_scattered_response, data.frequency_weights)
    return .5 * float(residual @ residual)


def directional_gate(model, controller, data, geometry):
    """Resolved central differences through weights/extraction/Method B/Kress."""
    vector = controller.parameter_vector()
    gradient, diagnostic = implicit_mlp_data_gradient(model, data, geometry)
    direction = np.random.default_rng(724).normal(size=vector.size)
    direction /= np.linalg.norm(direction)
    derivative = float(gradient @ direction)
    rows = []
    try:
        for step in (2e-5, 1e-5, 5e-6):
            controller.assign(vector + step * direction)
            high = data_loss(model, data, geometry)
            controller.assign(vector - step * direction)
            low = data_loss(model, data, geometry)
            fd = (high - low) / (2 * step)
            rows.append({"step": step, "analytic": derivative, "finite_difference": fd,
                         "relative_error": abs(fd - derivative) / max(abs(fd), abs(derivative), 1e-12)})
    finally:
        controller.assign(vector)
    return gradient, {"probes": rows, "diagnostics": diagnostic,
                      "passed": all(row["relative_error"] <= 3e-3 for row in rows[-2:])}


def rollback_gate(model, controller, data, geometry, initial_optimizer):
    import sdf_inverse.implicit_adjoint as module
    vector = controller.parameter_vector()
    original = module.predict_indexed_response
    calls = 0

    def reject(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OrderedSDFGeometryError("Qualification deliberately rejects candidate geometry")
        return original(*args, **kwargs)

    with patch.object(module, "predict_indexed_response", reject):
        result = run_implicit_mlp_adjoint_inverse(
            model, controller, data, geometry,
            config=ImplicitMLPAdjointConfig(max_iterations=1, max_candidate_evaluations=2,
                                            max_wall_seconds=120., regularization_samples=32),
            optimizer_state_dict=copy.deepcopy(initial_optimizer),
        )
    restored = np.array_equal(vector, controller.parameter_vector())
    state = result.diagnostics["optimizer_state_dict"]
    moments_restored = state["state"] == initial_optimizer["state"]
    return {"passed": restored and moments_restored and result.infeasible_trial_count > 0,
            "weights_restored": restored, "moments_restored": moments_restored,
            "rejected_candidates": result.infeasible_trial_count}


def qualify(args, evidence):
    output = args.output_dir
    if (output / "qualification.json").exists():
        raise ValueError("Qualification already exists; choose a fresh --output-dir")
    output.mkdir(parents=True, exist_ok=True)
    model, controller, geometry, initial = load_initial(args)
    torch.save(initial, output / "shared_initial.pt")
    report = {"signature": settings_signature(args, evidence), "normalization": NORMALIZATION,
              "initial_sha256": sha256(output / "shared_initial.pt"), "arms": {},
              "evaluation_use": "3 GHz, multistatic-8, posthoc only after both training trajectories"}
    observations = {}
    for name, acquisition, frequencies, _ in comparison_arms(args.comparison, args.sampling):
        print(f"[{name}] frozen indexed integration qualification", flush=True)
        problem = build_problem(acquisition, frequencies)
        observed, oracle = validated_observations(problem)
        observations[name] = observed
        data = ComplexScatteredData(problem, observed, np.ones(2))
        forward = predict_indexed_response(model, problem, geometry)
        refined_geometry = replace(geometry, num_nodes=2 * geometry.num_nodes)
        refined = predict_indexed_response(model, problem, refined_geometry)
        forward_error = relative_difference(forward.scattered_response, refined.scattered_response)
        gradient, derivative = directional_gate(model, controller, data, geometry)
        refined_gradient, refined_derivative = directional_gate(model, controller, data, refined_geometry)
        gradient_error = float(np.linalg.norm(gradient - refined_gradient)
                               / max(np.linalg.norm(refined_gradient), np.finfo(float).tiny))
        paired = driver._build_problem(frequencies, problem.source_points, problem.receiver_points)
        paired_forward = predict_paired_response(model, paired, geometry, solver="kress")
        diagonal = predict_indexed_response(model, IndexedForwardProblem.from_paired(paired), geometry)
        paired_equal = bool(np.array_equal(paired_forward.scattered_response, diagonal.scattered_response))
        # Forward ordering is compared to the independently expanded oracle on
        # the exact target at high resolution, not to synthetic production data.
        shape = driver.StarTarget().shape
        from ordered_boundary import star
        target_geometry = replace(geometry, num_nodes=512)
        target_curve = star(shape.center, shape.mean_radius, shape.amplitude, shape.lobes,
                            rotation=shape.rotation_radians).discretize(512)
        target_prediction = predict_indexed_curve_response(target_curve, problem, target_geometry).scattered_response
        ordering_error = relative_difference(target_prediction, observed)
        rollback = rollback_gate(model, controller, data, geometry, initial["optimizer_state_dict"])
        gates = {"oracle_refinement": oracle["passed"], "paired_selection_equivalence": paired_equal,
                 "independent_oracle_ordering": ordering_error <= 1e-7,
                 "normalized_neural_directional_derivative": derivative["passed"] and refined_derivative["passed"],
                 "rollback": rollback["passed"], "starting_curve_forward_refinement": forward_error <= 1e-4,
                 "starting_curve_derivative_refinement": gradient_error <= 1e-3,
                 "starting_curve_conversion_fidelity": (
                     forward.geometry_build.maximum_conversion_error_m <= 2e-4
                     and forward.geometry_build.conversion_refinement_change_m <= 1e-5)}
        report["arms"][name] = {"gates": gates, "oracle": oracle, "derivative": derivative,
                                "refined_derivative": refined_derivative, "rollback": rollback,
                                "ordering_relative_error": ordering_error,
                                "forward_refinement_relative_error": forward_error,
                                "gradient_refinement_relative_error": gradient_error,
                                "geometry_config": asdict(geometry),
                                "conversion_error_m": forward.geometry_build.maximum_conversion_error_m,
                                "conversion_refinement_change_m": forward.geometry_build.conversion_refinement_change_m,
                                "observed_column_norms": np.linalg.norm(observed, axis=0)}
        write_json(output / "qualification.partial.json", report)
    evaluation_problem = build_problem("multistatic", (3.0,))
    observations["evaluation"], report["evaluation_oracle"] = validated_observations(evaluation_problem)
    evaluation_base = predict_indexed_response(model, evaluation_problem, geometry).scattered_response
    evaluation_fine = predict_indexed_response(
        model, evaluation_problem, replace(geometry, num_nodes=2 * geometry.num_nodes)).scattered_response
    evaluation_error = relative_difference(evaluation_base, evaluation_fine)
    report["evaluation_starting_curve_refinement"] = {
        "relative_difference": evaluation_error, "passed": evaluation_error <= 1e-4,
        "use": "fixed numerical validation only; no evaluation residual used for optimization",
    }
    np.savez_compressed(output / "observations.npz", **observations)
    report["observations_sha256"] = sha256(output / "observations.npz")
    report["passed"] = (report["evaluation_oracle"]["passed"]
                        and report["evaluation_starting_curve_refinement"]["passed"]) and all(
        all(arm["gates"].values()) for arm in report["arms"].values())
    write_json(output / "qualification.json", report)
    return 0 if report["passed"] else 1


def require_qualification(args, evidence):
    path = args.output_dir / "qualification.json"
    if not path.is_file():
        raise ValueError("Run --action qualify first; no neural inverse starts without its integration gates")
    report = json.loads(path.read_text())
    signature = driver._jsonable(settings_signature(args, evidence))
    if report.get("passed") is not True or report.get("signature") != signature:
        raise ValueError("Qualification failed or settings/source/evidence changed; qualify a fresh output directory")
    for key, filename in (("initial_sha256", "shared_initial.pt"), ("observations_sha256", "observations.npz")):
        if report.get(key) != sha256(args.output_dir / filename):
            raise ValueError(f"Qualified {filename} changed")
    return report


def geometry_diagnostics(model, controller, geometry, result, directory, *, proposal_iterations=None):
    """Always return to accepted weights, even if a posthoc diagnostic fails."""
    try:
        if proposal_iterations is None:
            return _geometry_diagnostics_impl(model, controller, geometry, result, directory)
        return _geometry_diagnostics_impl(model, controller, geometry, result, directory,
                                          proposal_iterations=proposal_iterations)
    finally:
        controller.assign(result.final_iteration.parameter_vector)


def _geometry_diagnostics_impl(model, controller, geometry, result, directory, *, proposal_iterations=None):
    """Posthoc raw/converted trajectories and fresh, genuinely saved proposals."""
    from sdf_inverse.frozen_diagnostics import (
        field_quantities, field_statistics, normal_correspondence as polygon_correspondence,
        implicit_normal_correspondence, smooth_normal_correspondence,
        nearest_target_normal_correction,
        raw_contour, radial_spectrum, spectrum as finite_spectrum,
    )

    def motion_record(motion, method):
        return motion, {"missing_normal_intersections": int(np.sum(~np.isfinite(motion))),
                        "method": method}

    def raw_motion(reference, normals, polygon, zero):
        initial = polygon_correspondence(reference, normals, polygon)
        return motion_record(implicit_normal_correspondence(model, reference, normals, initial=initial) - zero,
                             "candidate zero-field roots on fixed reference normals; re-extracted polygon supplies local seeds")

    def converted_motion(reference, normals, polygon):
        zero = smooth_normal_correspondence(reference, normals, reference)
        return motion_record(smooth_normal_correspondence(reference, normals, polygon) - zero,
                             "fixed normals intersect smooth Method-B Fourier interpolant")

    score_definition = "nearest-target squared-distance descent: positive removes error at unique nearest points; not a normal-line target intersection"

    def spectrum(values, points, **kwargs):
        if not np.all(np.isfinite(values)):
            return {"interpretable": False, "reason": "nonfinite field quantity or missing normal correspondence"}
        measurement = finite_spectrum(values, points, **kwargs)
        if kwargs.get("target_correction") is not None:
            measurement["signed_effect_definition"] = score_definition
        return measurement
    target = driver.StarTarget().shape.sample_boundary(4096)
    geometry_rows = []
    previous_raw = previous_quantities = previous_curve = previous_zero = None
    for record in result.iterations:
        print(f"[{directory.name}] posthoc accepted geometry {record.iteration}/{result.final_iteration.iteration}", flush=True)
        controller.assign(record.parameter_vector)
        raw, branch = raw_contour(model, geometry)
        quantities = field_quantities(model, raw)
        zero = implicit_normal_correspondence(model, raw, quantities["normals"])
        row = {"iteration": record.iteration, "raw_contour": raw,
               "converted_contour": record.geometry_points, "branch": branch,
               "field_statistics": field_statistics(quantities, raw),
               "radial_spectrum": radial_spectrum(raw),
               "field_norm_spectrum": spectrum(quantities["G"], raw),
               "sample_set_hash": getattr(record, "sample_set_hash", None),
               "signed_target_score_definition": score_definition}
        if previous_raw is not None:
            displacement, match = raw_motion(previous_raw, previous_quantities["normals"], raw, previous_zero)
            target_correction = nearest_target_normal_correction(previous_raw, previous_quantities["normals"], target)
            row.update(raw_signed_normal_motion=displacement, raw_correspondence=match,
                       raw_motion_spectrum=spectrum(displacement, previous_raw, target_correction=target_correction))
            from sdf_inverse.frozen_diagnostics import interpolated_parameterization
            tangent = interpolated_parameterization(previous_curve).evaluate(
                np.arange(len(previous_curve)) * 2*np.pi/len(previous_curve)).first_derivatives
            normals = np.column_stack((tangent[:, 1], -tangent[:, 0])) / np.linalg.norm(tangent, axis=1)[:, None]
            converted, match = converted_motion(previous_curve, normals, record.geometry_points)
            correction = nearest_target_normal_correction(previous_curve, normals, target)
            row.update(converted_signed_normal_motion=converted, converted_correspondence=match,
                       converted_motion_spectrum=spectrum(converted, previous_curve, target_correction=correction))
        geometry_rows.append(row)
        previous_raw, previous_quantities, previous_curve = raw, quantities, record.geometry_points
        previous_zero = zero
    write_json(directory / "geometry_trajectory.json", geometry_rows)
    proposal_rows = []
    proposal_records = result.diagnostics["optimizer_records"]
    selected = ({record["iteration"] for record in proposal_records} if proposal_iterations is None
                else set(proposal_iterations))
    for record in proposal_records:
        if record["iteration"] not in selected:
            continue
        print(f"[{directory.name}] posthoc finite proposal geometry at optimizer iteration {record['iteration']}", flush=True)
        vector = record["parameter_vector"]
        controller.assign(vector)
        raw, _ = raw_contour(model, geometry)
        curve = build_ordered_sdf_geometry(model, geometry).curve
        base_quantities = field_quantities(model, raw)
        zero = implicit_normal_correspondence(model, raw, base_quantities["normals"])
        correction = nearest_target_normal_correction(raw, base_quantities["normals"], target)
        directions = {"data_steepest_descent": -record["data_gradient"],
                      "total_steepest_descent": -record["total_gradient"],
                      "raw_adam_proposal": record["raw_adam_proposal"],
                      "fallback": record["fallback_proposal"]}
        for name, direction in directions.items():
            controller.assign(vector)
            quantities = field_quantities(model, raw, direction)
            velocity_rms = spectrum(quantities["V"], raw).get("rms")
            if velocity_rms is None or velocity_rms == 0:
                proposal_rows.append({"iteration": record["iteration"], "direction": name,
                                      "N": quantities["N"], "G": quantities["G"], "V_n": quantities["V"],
                                      "interpretable": False, "reason": "zero or nonfinite predicted motion; no clipping"})
                continue
            scales = {"actual_proposal": 1., "common_predicted_rms_20um": 2e-5 / max(velocity_rms, 1e-30)}
            for label, scale in scales.items():
                row = {"iteration": record["iteration"], "direction": name, "scale_label": label, "scale": scale,
                       "signed_target_score_definition": score_definition,
                       "N": scale * quantities["N"], "G": quantities["G"], "inverse_G": quantities["inverse_G"],
                       "V_n": scale * quantities["V"], "raw_contour": raw,
                       "N_spectrum": spectrum(scale * quantities["N"], raw),
                       "G_spectrum": spectrum(quantities["G"], raw),
                       "inverse_G_spectrum": spectrum(quantities["inverse_G"], raw),
                       "V_n_spectrum": spectrum(scale * quantities["V"], raw, target_correction=correction)}
                try:
                    # Do not project/clamp a diagnostic direction: that would
                    # silently change the numerator being compared.
                    controller.assign(vector + scale * direction)
                    moved_raw, _ = raw_contour(model, geometry)
                    moved_curve = build_ordered_sdf_geometry(model, geometry).curve
                    motion, match = raw_motion(raw, quantities["normals"], moved_raw, zero)
                    converted, converted_match = converted_motion(curve.points, curve.normals, moved_curve.points)
                    row.update(actual_raw_motion=motion, actual_converted_motion=converted,
                               raw_correspondence=match, converted_correspondence=converted_match,
                               actual_raw_motion_spectrum=spectrum(motion, raw, target_correction=correction))
                except (OrderedSDFGeometryError, ValueError) as error:
                    row["finite_probe_failure"] = f"{type(error).__name__}: {error}"
                finally:
                    controller.assign(vector)
                proposal_rows.append(row)
    controller.assign(result.final_iteration.parameter_vector)
    write_json(directory / "fresh_proposal_geometry.json", proposal_rows)


def optimizer_checkpoint_writer(directory, experiment):
    """Long runs serialize each full optimizer record once, without prefix rewrites."""
    cumulative = []
    saved = []

    def save(record):
        if experiment == "long":
            filename = f"optimizer_{record['iteration']:04d}.pt"
            torch.save(record, directory / filename)
            saved.append({"iteration": record["iteration"], "file": filename})
        else:
            cumulative.append(copy.deepcopy(record))
            torch.save(cumulative, directory / "optimizer_records.pt")
    return save, saved


def run(args, evidence):
    report = require_qualification(args, evidence)
    if any((args.output_dir / arm[0]).exists() for arm in comparison_arms(args.comparison, args.sampling)):
        raise ValueError("An arm destination already exists; refusing to overwrite trajectories")
    initial = torch.load(args.output_dir / "shared_initial.pt", map_location="cpu", weights_only=False)
    observed = np.load(args.output_dir / "observations.npz")
    trained = []
    for name, acquisition, frequencies, sampling in comparison_arms(args.comparison, args.sampling):
        directory = args.output_dir / name
        directory.mkdir()
        model, controller, geometry, _ = load_initial(args)
        model.load_state_dict(initial["state_dict"])
        np.testing.assert_array_equal(controller.parameter_vector(), initial["parameter_vector"])
        data = ComplexScatteredData(build_problem(acquisition, frequencies), observed[name], np.ones(2))
        save_optimizer, optimizer_files = optimizer_checkpoint_writer(directory, args.experiment)

        def save_progress(record):
            torch.save({"state_dict": copy.deepcopy(model.state_dict()), "record": record},
                       directory / f"accepted_{record.iteration:03d}.pt")
            print(f"[{name}] accepted {record.iteration}: data={record.loss:.6g}", flush=True)

        with (directory / "trials.jsonl").open("w") as stream:
            def save_trial(record):
                stream.write(json.dumps(driver._jsonable(record), allow_nan=False) + "\n")
                stream.flush()

            result = run_implicit_mlp_adjoint_inverse(
                model, controller, data, geometry, config=optimizer_config(args, sampling),
                optimizer_state_dict=copy.deepcopy(initial["optimizer_state_dict"]),
                optimizer_callback=save_optimizer, progress_callback=save_progress,
                trial_callback=save_trial,
            )
        torch.save(result, directory / "inverse_result.pt")
        if args.experiment == "long":
            write_json(directory / "optimizer_manifest.json", {
                "optimizer_record_count": len(optimizer_files), "records": optimizer_files,
                "policy": reporting_policy(args.experiment)["optimizer_checkpoints"],
                "full_inverse_result_retains_all_states_and_optimizer_records": True,
            })
        assert len(result.iterations) - 1 <= args.accepted_updates
        assert len(result.diagnostics["trial_records"]) <= args.candidate_cap
        trained.append((name, model, controller, geometry, result))
    # This phase starts only when both inverse results are already serialized.
    print("Both inverse trajectories are saved. Starting posthoc 3 GHz evaluation and geometry diagnostics.", flush=True)
    summaries = {}
    posthoc_errors = []
    evaluation = build_problem("multistatic", (3.0,))
    target = driver.StarTarget()
    for name, model, controller, geometry, result in trained:
        rows = []
        for record in result.iterations:
            print(f"[{name}] posthoc 3 GHz evaluation {record.iteration}/{result.final_iteration.iteration}", flush=True)
            controller.assign(record.parameter_vector)
            relative = None
            evaluation_error = None
            try:
                prediction = predict_indexed_response(model, evaluation, geometry).scattered_response
                _, relative = normalized_complex_residual(prediction, observed["evaluation"])
            except Exception as error:
                evaluation_error = f"{type(error).__name__}: {error}"
                posthoc_errors.append({"arm": name, "iteration": record.iteration, "evaluation_error": evaluation_error})
                (args.output_dir / name / f"evaluation_{record.iteration:03d}_traceback.txt").write_text(traceback.format_exc())
            rows.append({"iteration": record.iteration, "training_loss": record.loss,
                         "regularized_loss": record.objective, "eikonal_loss": record.eikonal_loss,
                         "evaluation_3ghz_relative_l2": relative,
                         "evaluation_error": evaluation_error,
                         "data_gradient_norm": record.data_gradient_norm,
                         "weighted_eikonal_gradient_norm": record.weighted_eikonal_gradient_norm,
                         "conversion_error_m": record.conversion_error_m,
                         "conversion_refinement_change_m": record.conversion_refinement_change_m,
                         "boundary_movement_m": record.boundary_movement_m,
                         **target.curve_distance_metrics(record.geometry_points)})
        controller.assign(result.final_iteration.parameter_vector)
        geometry_error = None
        optimizer_records = result.diagnostics.get("optimizer_records", [])
        selected_proposals = selected_proposal_iterations(optimizer_records, args.experiment)
        print(f"[{name}] posthoc geometry: {len(result.iterations)} accepted states; "
              f"{len(optimizer_records)} saved optimizer records; finite proposal indices {selected_proposals}", flush=True)
        if args.experiment == "long":
            write_json(args.output_dir / name / "proposal_geometry_selection.json", {
                "experiment": args.experiment, "optimizer_record_count": len(optimizer_records),
                "selected_optimizer_iterations": selected_proposals,
                "accepted_geometry_state_count": len(result.iterations),
                "reporting_policy": reporting_policy(args.experiment),
            })
        try:
            if args.experiment == "long":
                geometry_diagnostics(model, controller, geometry, result, args.output_dir / name,
                                     proposal_iterations=selected_proposals)
            else:
                geometry_diagnostics(model, controller, geometry, result, args.output_dir / name)
        except Exception as error:
            geometry_error = f"{type(error).__name__}: {error}"
            posthoc_errors.append({"arm": name, "geometry_diagnostic_error": geometry_error})
            (args.output_dir / name / "geometry_diagnostic_traceback.txt").write_text(traceback.format_exc())
        finally:
            controller.assign(result.final_iteration.parameter_vector)
        summaries[name] = {"accepted_updates": len(result.iterations) - 1,
                           "candidate_evaluations": len(result.diagnostics["trial_records"]),
                           "stop_reason": result.stop_reason, "inverse_seconds": result.total_seconds,
                           "rejection_reason_counts": result.diagnostics["rejection_reason_counts"],
                           "geometry_diagnostic_error": geometry_error,
                           "trajectory": rows}
        if args.experiment == "long":
            summaries[name].update(experiment=args.experiment, caps_per_arm=caps_per_arm(args),
                                   optimizer_record_count=len(optimizer_records),
                                   finite_proposal_optimizer_iterations=selected_proposals,
                                   accepted_geometry_state_count=len(result.iterations),
                                   reporting_policy=reporting_policy(args.experiment))
        write_json(args.output_dir / name / "metrics.json", summaries[name])
    write_json(args.output_dir / "metrics.json", {
        "arms": summaries, "matched_initial_sha256": report["initial_sha256"],
        "experiment": args.experiment, "caps_per_arm": caps_per_arm(args),
        "reporting_policy": reporting_policy(args.experiment),
        "posthoc_errors": posthoc_errors,
        "status": "complete" if not posthoc_errors else "inverses_complete_posthoc_incomplete",
        "normalization": NORMALIZATION, "regularized_objective": "iteration-local for contour_band; globally comparable data objective",
        "evaluation_use": "posthoc only after BOTH training trajectories; never acceptance, selection, or stopping",
        "promotion": ("This controlled acquisition experiment assesses long geometric recovery; report training/evaluation loss, raw and converted shape error, modal motion, field conditioning and work jointly"
                      if args.experiment == "long" else
                      "Requires review of signed neural geometric motion; lower training loss alone does not qualify"),
    })
    return 0 if not posthoc_errors else 2


class _Tee:
    def __init__(self, terminal, log):
        self.terminal, self.log = terminal, log

    def write(self, value):
        self.terminal.write(value)
        self.log.write(value)
        self.flush()
        return len(value)

    def flush(self):
        self.terminal.flush()
        self.log.flush()


def _qualify_and_run(args, evidence):
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Append neither to a prior run nor to an unreviewed transcript.
    with (args.output_dir / "run.log").open("x", buffering=1) as log:
        with redirect_stdout(_Tee(sys.stdout, log)), redirect_stderr(_Tee(sys.stderr, log)):
            phase = "qualification"
            try:
                print(f"Actual {args.experiment} inverse comparison: {args.comparison}. Results: {args.output_dir}", flush=True)
                print(f"Per-arm inverse caps: {caps_per_arm(args)}; reporting: {reporting_policy(args.experiment)}", flush=True)
                status = qualify(args, evidence)
                if status:
                    print(f"Numerical qualification failed; inverse not started. See {args.output_dir / 'qualification.json'}", flush=True)
                    return status
                phase = "inverse_and_posthoc"
                print("Qualification passed. Starting both inverse arms.", flush=True)
                status = run(args, evidence)
                print(f"Inverse command finished with exit {status}. Results: {args.output_dir / 'metrics.json'}", flush=True)
                return status
            except Exception as error:
                traceback.print_exc()
                write_json(args.output_dir / "failure.json", {"phase": phase, "error": f"{type(error).__name__}: {error}"})
                raise


def main(argv=None):
    args = parse_args(argv)
    if args.action == "plan":
        plan = {"experiment": args.experiment, "arms": comparison_arms(args.comparison, args.sampling),
                "caps_per_arm": caps_per_arm(args), "reporting_policy": reporting_policy(args.experiment),
                "initialization": {"bundle": str(args.bundle), "state": args.state,
                                   "policy": "identical saved neural weights and identical fresh Adam state in both arms"},
                "required_evidence": required_evidence(args), "normalization": NORMALIZATION,
                "evaluation": "disjoint multistatic-8 at 3 GHz; validated independently; posthoc only",
                "next_actions": ["--action qualify (frozen numerical gates)", "--action run (bounded neural comparisons)"]}
        print(json.dumps(plan, indent=2))
        return 0
    try:
        evidence = validate_evidence(args)
        if args.action == "all":
            return _qualify_and_run(args, evidence)
        return qualify(args, evidence) if args.action == "qualify" else run(args, evidence)
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    raise SystemExit(main())
