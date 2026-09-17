#!/usr/bin/env python3
"""Opt-in C1/C2 parameterization experiment; no production defaults change.

C1 keeps the exact ellipse set while changing its parameter. C2 shares one
frozen extraction between Method B, skip-refit and ordered-label Fourier fits.
The latter is not an implementation of Zhao--Serkh (arXiv:2301.04241).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
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
sys.path.insert(0, str(ROOT / "solvers"))

import numpy as np
import scipy

from ordered_boundary import BoundaryValidationConfig, validate_periodic_parameterization
from sdf_to_ordered_boundary.arclength import ArcLengthConfig
from sdf_to_ordered_boundary.artifacts import write_metrics_csv, write_npz, write_strict_json
from sdf_to_ordered_boundary.fields import (
    CallableImplicitField2D, CircleSDF, CountedImplicitField2D, EllipseLevelSet,
    RadialFourierLevelSet,
)
from sdf_to_ordered_boundary.frontend import FrontendConfig, prepare_single_component
from sdf_to_ordered_boundary.method_b import MethodBConfig, fit_method_b
from sdf_to_ordered_boundary.parameter_aware import (
    ParameterAwareConfig, closest_parameters, exact_arclength_ellipse,
    fit_parameter_aware, fit_without_arclength,
)
from sdf_to_ordered_boundary.representations import FourierBoundary
from sdf_inverse import MaterialSpec, PairedForwardProblem
from sdf_inverse.nystrom_oracle import nystrom_paired_response
from gpr_bem_kress import KressSolveConfig, Material, solve_kress_tmz_total_field_batch


@dataclass(frozen=True)
class Case:
    name: str
    field: object
    native: FourierBoundary
    physical_parameters: dict


def build_case(name):
    center = (0.5, 0.5)
    if name == "circle":
        field = CircleSDF(center, .05)
        cosine = np.array([[.5, .5], [.05, 0]])
        sine = np.array([[0., 0.], [0., .05]])
        parameters = {"center_m": center, "radius_m": .05}
    elif name == "ellipse":
        field = EllipseLevelSet(center, .07, .035, rotation=.4)
        rotation = np.array([[np.cos(.4), -np.sin(.4)], [np.sin(.4), np.cos(.4)]])
        cosine = np.vstack((center, rotation @ [.07, 0]))
        sine = np.vstack(([0., 0.], rotation @ [0, .035]))
        parameters = {"center_m": center, "semi_major_m": .07,
                      "semi_minor_m": .035, "rotation_rad": .4}
    elif name == "star":
        field = RadialFourierLevelSet.star(center, .05, .25, 5)
        cosine = np.zeros((7, 2)); sine = np.zeros_like(cosine)
        cosine[0] = center; cosine[1, 0] = sine[1, 1] = .05
        cosine[[4, 6], 0] = .05 * .25 / 2
        sine[4, 1] = -.05 * .25 / 2; sine[6, 1] = .05 * .25 / 2
        parameters = {"center_m": center, "mean_radius_m": .05,
                      "amplitude": .25, "lobes": 5, "rotation_rad": 0.0}
    elif name == "nonstar":
        # A diffeomorphic parabolic shear of the unit disk is simple and smooth.
        # In normalized coordinates y=v+a*u^2, symmetry makes any nonempty
        # visibility kernel contain x=0. Its tangent halfplanes require
        # y>=-1 and y<=3*a^(1/3)/2^(2/3)-a. At a=5 these are incompatible.
        a, rx, ry = 5.0, .04, .02
        def value(points):
            u = (points[..., 0] - .5) / rx
            v = (points[..., 1] - .5) / ry - a * (u*u - .5)
            return u*u + v*v - 1
        def gradient(points):
            u = (points[..., 0] - .5) / rx
            v = (points[..., 1] - .5) / ry - a * (u*u - .5)
            return np.stack(((2*u - 4*a*u*v) / rx, 2*v / ry), axis=-1)
        field = CallableImplicitField2D(value, gradient, name="nonstar_parabolic_shear")
        cosine = np.array([[.5, .5], [rx, 0.], [0., a*ry/2]])
        sine = np.array([[0., 0.], [0., ry], [0., 0.]])
        parameters = {"center_m": center, "x_scale_m": rx, "y_scale_m": ry,
                      "shear": a, "simple_by": "invertible_parabolic_shear_of_unit_circle",
                      "visibility_kernel_lower_y": -1.0,
                      "visibility_kernel_upper_y": 3*a**(1/3)/2**(2/3)-a,
                      "non_star_shaped_about_any_point": True}
    else:
        raise ValueError(f"Unknown case {name!r}.")
    return Case(name, field, FourierBoundary(cosine, sine, name=f"analytic_{name}"), parameters)


def build_problem(frequencies_ghz=(.5, 1.5), num_pairs=12):
    angles = 2*np.pi*np.arange(num_pairs) / num_pairs
    sources = .5 + .30 * np.column_stack((np.cos(angles), np.sin(angles)))
    receivers = .5 + .30 * np.column_stack((np.cos(angles+.10), np.sin(angles+.10)))
    return PairedForwardProblem(sources, receivers, 2*np.pi*1e9*np.array(frequencies_ghz),
                                1e-6 + .2e-6j, MaterialSpec(6.), MaterialSpec(3.),
                                8.8541878128e-12, 1.25663706212e-6)


def _oracle(case, problem, *, initial_nodes, maximum_nodes, tolerance):
    started = perf_counter()
    reference = case.native.to_parameterization()
    def evaluator(t):
        values = reference.evaluate(t)
        return values.points, values.first_derivatives
    records = []
    coarse = nystrom_paired_response(problem, evaluator, num_nodes=initial_nodes,
                                      curve_name=case.name)
    nodes = initial_nodes
    while nodes * 2 <= maximum_nodes:
        nodes *= 2
        fine = nystrom_paired_response(problem, evaluator, num_nodes=nodes, curve_name=case.name)
        error = np.linalg.norm(fine.scattered_response - coarse.scattered_response, axis=0) / np.maximum(
            np.linalg.norm(fine.scattered_response, axis=0), np.finfo(float).tiny)
        records.append({"coarse_nodes": coarse.num_nodes, "fine_nodes": nodes,
                        "per_frequency_relative_difference": error.tolist()})
        coarse = fine
        if np.max(error) <= tolerance:
            break
    self_error = float(np.max(error))
    response = coarse.scattered_response
    identity = "nystrom_ref_native_exact_curve"
    if case.name == "circle":
        import gpr_bem_ref
        response = gpr_bem_ref.penetrable_cylinder_frequency_response(
            problem.receiver_points, problem.source_points, problem.angular_frequencies,
            problem.source_strengths, exterior=gpr_bem_ref.Material(**asdict(problem.exterior)),
            interior=gpr_bem_ref.Material(**asdict(problem.interior)), eps0=problem.eps0,
            mu0=problem.mu0, radius=.05, center=(.5, .5), include_incident=False)
        identity = "analytic_mie_with_independent_nystrom_crosscheck"
    independent_error = float(np.linalg.norm(response-coarse.scattered_response)
                              / max(np.linalg.norm(response), np.finfo(float).tiny))
    return response, {"identity": identity, "passed": self_error <= tolerance and independent_error <= tolerance,
                      "tolerance": tolerance, "maximum_self_convergence_difference": self_error,
                      "independent_mie_difference": independent_error if case.name == "circle" else None,
                      "final_nodes": nodes, "history": records, "seconds": perf_counter()-started,
                      "nystrom_solve_count": (1+len(records))*problem.num_frequencies,
                      "mie_frequency_evaluations": problem.num_frequencies if case.name == "circle" else 0,
                      "limitation": "same mathematical Muller family; independently implemented kernels"}


def _unit_geometry(evaluation):
    speed = np.linalg.norm(evaluation.first_derivatives, axis=-1)
    tangent = evaluation.first_derivatives / speed[..., None]
    normal = np.stack((tangent[..., 1], -tangent[..., 0]), axis=-1)
    first, second = evaluation.first_derivatives, evaluation.second_derivatives
    curvature = (first[..., 0]*second[..., 1] - first[..., 1]*second[..., 0]) / speed**3
    return speed, tangent, normal, curvature


def geometry_metrics(curve, reference, *, audit_samples=512, localization_samples=1024):
    started = perf_counter()
    def compare(count, localization):
        parameter = 2*np.pi*np.arange(count)/count
        actual = curve.evaluate(parameter)
        target = reference.evaluate(parameter)
        nearest_parameter, distances = closest_parameters(actual.points, reference,
                                                            localization_samples=localization)
        _, reverse = closest_parameters(target.points, curve, localization_samples=localization)
        return actual, nearest_parameter, distances, reverse
    coarse, _, coarse_distances, coarse_reverse = compare(audit_samples, localization_samples)
    actual, nearest, distances, reverse = compare(2*audit_samples, 2*localization_samples)
    matched = reference.evaluate(nearest)
    speed, tangent, normals, curvature = _unit_geometry(actual)
    _, reference_tangent, reference_normal, reference_curvature = _unit_geometry(matched)
    dots = np.clip(np.sum(normals*reference_normal, axis=-1), -1, 1)
    spectrum_count = max(2048, 4*audit_samples)
    samples = curve.evaluate(2*np.pi*np.arange(spectrum_count)/spectrum_count).points
    coefficients = np.fft.rfft(samples-np.mean(samples, axis=0), axis=0)/spectrum_count
    spectrum = np.sqrt(np.sum(np.abs(coefficients)**2, axis=-1))
    modes = np.arange(len(spectrum))
    tails = {f"derivative_{order}": {
        str(cutoff): float(np.sqrt(2*np.sum((spectrum[modes > cutoff]
                            * modes[modes > cutoff]**order)**2)))
        for cutoff in (1, 2, 4, 8, 16, 32)} for order in (0, 1, 2)}
    maximum = max(float(np.max(distances)), float(np.max(reverse)))
    coarse_maximum = max(float(np.max(coarse_distances)), float(np.max(coarse_reverse)))
    return {"symmetric_set_distance_m": maximum,
            "set_distance_refinement_change_m": abs(maximum-coarse_maximum),
            "closest_point_localization_refinement_agreement_m": max(
                float(np.max(np.abs(distances[::2]-coarse_distances))),
                float(np.max(np.abs(reverse[::2]-coarse_reverse)))),
            "set_sampling_refinement_change_m": abs(maximum-max(
                float(np.max(distances[::2])), float(np.max(reverse[::2])))),
            "point_to_reference_rms_m": float(np.sqrt(np.mean(distances**2))),
            "normal_angle_maximum_rad": float(np.max(np.arccos(dots))),
            "normal_angle_rms_rad": float(np.sqrt(np.mean(np.arccos(dots)**2))),
            "unit_tangent_rms_error": float(np.sqrt(np.mean(np.sum((tangent-reference_tangent)**2, axis=-1)))),
            "arclength_second_derivative_rms_error_per_m": float(np.sqrt(np.mean(np.sum(
                (curvature[:, None]*normals-reference_curvature[:, None]*reference_normal)**2, axis=-1)))),
            "minimum_speed": float(np.min(speed)), "maximum_speed": float(np.max(speed)),
            "minimum_over_mean_speed": float(np.min(speed)/np.mean(speed)),
            "speed_ratio": float(np.max(speed)/np.min(speed)),
            "spectral_tails_rms": tails, "spectrum_resolution": spectrum_count,
            "audit_samples": 2*audit_samples, "closest_point_localization_samples": 2*localization_samples,
            "closest_point_policy": "multistart_safeguarded_local_refinement_not_certificate",
            "audit_seconds": perf_counter()-started}, {"spectrum_modes": modes, "coordinate_spectrum": spectrum}


def _forward(curve, problem, nodes):
    started = perf_counter()
    sampled = curve.discretize(nodes, require_even=True)
    forwards = []
    for frequency, strength in zip(problem.angular_frequencies, problem.source_strengths):
        forwards.append(solve_kress_tmz_total_field_batch(
            sampled, problem.source_points, problem.receiver_points, float(frequency), complex(strength),
            exterior=Material(**asdict(problem.exterior)), interior=Material(**asdict(problem.interior)),
            eps0=problem.eps0, mu0=problem.mu0))
    elapsed = perf_counter()-started
    condition_started = perf_counter()
    conditions = [float(np.linalg.cond(item.system.system_matrix)) for item in forwards]
    return np.column_stack([np.diag(item.scattered_receiver) for item in forwards]), {
        "bem_seconds": elapsed, "bem_solve_count": len(forwards),
        "maximum_system_condition": max(conditions),
        "conditioning_audit_seconds": perf_counter()-condition_started,
        "maximum_system_residual": max(item.linear_system_relative_residual for item in forwards),
    }


def _provenance():
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=False).stdout.strip()
    relevant = [Path(__file__)]
    relevant.extend(sorted((ROOT/"config").glob("*.py")))
    relevant.append(ROOT/"docs"/"codex_sdf_kress_priorities_2026-09-05.md")
    for package in ("sdf_to_ordered_boundary", "ordered_boundary", "gpr_bem_kress",
                    "nystrom_ref", "gpr_bem_ref", "sdf_inverse"):
        relevant.extend(sorted((ROOT/"solvers"/package).glob("*.py")))
    return {"git_commit": git("rev-parse", "HEAD"), "git_dirty_paths": git("status", "--porcelain").splitlines(),
            "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in relevant},
            "python": sys.version, "executable": sys.executable, "numpy": np.__version__,
            "scipy": scipy.__version__, "platform": platform.platform(),
            "thread_environment": {name: os.environ.get(name) for name in (
                "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}}


def _integer_list(value):
    try:
        values = tuple(int(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected comma-separated positive integers.") from exc
    if not values or any(item < 1 for item in values) or len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("Expected unique positive integers.")
    return tuple(sorted(values))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summarize-existing", action="store_true",
                        help="Add decision-only supplements to a completed bundle without rerunning fits or fields.")
    parser.add_argument("--cases", default="circle,ellipse,star,nonstar")
    parser.add_argument("--bandwidths", type=_integer_list, default=(1, 2, 4, 8, 16))
    parser.add_argument("--bem-nodes", type=_integer_list, default=(32, 64, 128))
    parser.add_argument("--grid-size", type=int, default=257)
    parser.add_argument("--projected-samples", type=int, default=128)
    parser.add_argument("--audit-samples", type=int, default=256)
    parser.add_argument("--localization-samples", type=int, default=1024)
    parser.add_argument("--fit-iterations", type=int, default=100)
    parser.add_argument("--spectral-penalty", type=float, default=1e-8)
    parser.add_argument("--oracle-initial-nodes", type=int, default=128)
    parser.add_argument("--oracle-maximum-nodes", type=int, default=1024)
    parser.add_argument("--oracle-tolerance", type=float, default=1e-7)
    parser.add_argument("--geometry-tolerance-m", type=float, default=2e-4)
    parser.add_argument("--field-tolerance", type=float, default=1e-3)
    args = parser.parse_args(argv)
    args.cases = tuple(args.cases.split(","))
    if not args.cases or set(args.cases)-{"circle", "ellipse", "star", "nonstar"}:
        parser.error("cases must be circle,ellipse,star,nonstar subsets")
    if len(set(args.cases)) != len(args.cases):
        parser.error("cases must be unique")
    if any(item < 16 or item % 2 for item in args.bem_nodes):
        parser.error("BEM node counts must be even and at least 16")
    if args.projected_samples < 2*max(args.bandwidths)+1:
        parser.error("projected samples must resolve 2K+1 coefficients")
    if args.grid_size < 33 or args.audit_samples < 32 or args.localization_samples < 64:
        parser.error("grid/audit/localization resolutions are too small")
    if args.oracle_initial_nodes < 16 or args.oracle_initial_nodes % 2 or args.oracle_maximum_nodes < 2*args.oracle_initial_nodes:
        parser.error("oracle requires an even initial count and at least one doubling")
    for name in ("oracle_tolerance", "geometry_tolerance_m", "field_tolerance"):
        if not np.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error(f"{name} must be finite and positive")
    if not np.isfinite(args.spectral_penalty) or args.spectral_penalty < 0:
        parser.error("spectral penalty must be finite and nonnegative")
    if args.fit_iterations < 1:
        parser.error("fit iterations must be positive")
    return args


def decision_records(rows, args):
    decisions = []
    for case in args.cases:
        usable = [r for r in rows if r["comparison"] == "C2" and r["case"] == case
                  and r.get("accuracy_gate_passed", False) and r["status"] == "success"]
        baselines = [r for r in usable if r["arm"] == "B-arclength"]
        baseline = min(baselines, key=lambda r: r["total_work_seconds"], default=None)
        for arm in ("skip-arclength", "ordered-label-unregularized", "ordered-label-penalized"):
            options = [r for r in usable if r["arm"] == arm]
            best = min(options, key=lambda r: r["total_work_seconds"], default=None)
            baseline_bandwidth = min(baselines, key=lambda r: (r["bandwidth"], r["bem_nodes"]), default=None)
            candidate_bandwidth = min(options, key=lambda r: (r["bandwidth"], r["bem_nodes"]), default=None)
            lower_bandwidth = bool(baseline_bandwidth and candidate_bandwidth
                and candidate_bandwidth["bandwidth"] < baseline_bandwidth["bandwidth"])
            node_ratio = (None if not baseline_bandwidth or not candidate_bandwidth else
                          candidate_bandwidth["bem_nodes"] / baseline_bandwidth["bem_nodes"])
            condition_ratio = (None if not baseline_bandwidth or not candidate_bandwidth else
                candidate_bandwidth["maximum_system_condition"] / baseline_bandwidth["maximum_system_condition"])
            win = bool(baseline and best and best["total_work_seconds"] < .9*baseline["total_work_seconds"])
            decisions.append({"case": case, "arm": arm, "matched_work_win_observed": win,
                              "baseline_eligible": baseline is not None, "candidate_eligible": best is not None,
                              "baseline": None if baseline is None else {key: baseline[key] for key in (
                                  "bandwidth", "bem_nodes", "total_work_seconds", "field_relative_l2")},
                              "candidate": None if best is None else {key: best[key] for key in (
                                  "bandwidth", "bem_nodes", "total_work_seconds", "field_relative_l2")},
                              "bandwidth_comparison": {
                                  "scope": "only the sampled K/N ladder and declared geometry/field gates",
                                  "baseline_minimum_usable": None if baseline_bandwidth is None else {
                                      key: baseline_bandwidth[key] for key in ("bandwidth", "bem_nodes", "maximum_system_condition")},
                                  "candidate_minimum_usable": None if candidate_bandwidth is None else {
                                      key: candidate_bandwidth[key] for key in ("bandwidth", "bem_nodes", "maximum_system_condition")},
                                  "baseline_unqualified_within_ladder": baseline_bandwidth is None,
                                  "swept_bandwidths": list(args.bandwidths),
                                  "swept_bem_nodes": list(args.bem_nodes),
                                  "lower_usable_bandwidth_observed": lower_bandwidth,
                                  "bem_node_count_ratio": node_ratio,
                                  "system_condition_ratio": condition_ratio,
                                  "lower_bandwidth_without_observed_node_or_condition_increase": bool(
                                      lower_bandwidth and node_ratio <= 1 and condition_ratio <= 1),
                                  "condition_interpretation": "raw matrix condition on the same physical problem; ratios reported without a universal threshold",
                              },
                              "production_default_promoted": False,
                              "timing_limit": "single bounded timing; not a statistical speedup claim"})
    return decisions


def _bandwidth_summary_lines(decisions):
    lines = ["", "| Case | Arm | B minimum usable K / N | Candidate K / N | Lower K without increased N or condition |",
             "|---|---|---|---|---:|"]
    for decision in decisions:
        comparison = decision["bandwidth_comparison"]
        def cell(value):
            return "none in bounded ladder" if value is None else f"{value['bandwidth']} / {value['bem_nodes']}"
        lines.append(f"| {decision['case']} | {decision['arm']} | "
                     f"{cell(comparison['baseline_minimum_usable'])} | "
                     f"{cell(comparison['candidate_minimum_usable'])} | "
                     f"{comparison['lower_bandwidth_without_observed_node_or_condition_increase']} |")
    lines += ["", "Minimum usable bandwidth is evaluated only on this bounded K/N ladder. "
              "When B has no qualifying row, there is no matched-accuracy B work or conditioning comparison; "
              "the candidate's success is reported without treating the unqualified baseline as an equal-accuracy competitor.",
              "", "A lower usable bandwidth is separate from a measured speed advantage. "
              "The node and raw matrix-condition ratios are retained explicitly; no production default is promoted."]
    return lines


def summarize_existing(output, *, command):
    """Derive new decision views while leaving all measured artifacts untouched."""
    import json
    from types import SimpleNamespace
    manifest_path, metrics_path = output/"manifest.json", output/"metrics.json"
    manifest = json.loads(manifest_path.read_text())
    if not manifest.get("completed", False):
        raise ValueError("Decision postprocessing requires a completed bundle.")
    settings = SimpleNamespace(**manifest["configuration"])
    payload = json.loads(metrics_path.read_text())
    decisions = decision_records(payload["rows"], settings)
    destinations = (output/"decision_supplement.json", output/"decision_summary.md")
    if any(path.exists() for path in destinations):
        raise FileExistsError("Decision supplements already exist; refusing to overwrite them.")
    supplement = {"schema": "parameterization-aware-decision-supplement-v1",
                  "created_utc": datetime.now(timezone.utc).isoformat(),
                  "command": command, "measurements_changed": False,
                  "source_metrics_sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
                  "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  "postprocessing_driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "decisions": decisions}
    write_strict_json(destinations[0], supplement)
    work_wins = sum(item["matched_work_win_observed"] for item in decisions
                    if item["arm"].startswith("ordered-label"))
    lines = ["# Supplemental bandwidth decision from frozen C1/C2 measurements", "",
             "This view adds the brief's lower-usable-bandwidth criterion. It reruns no extraction, fitting, oracle or BEM solve and changes no measured artifact.",
             "", f"The original matched-work findings are preserved: {work_wins} ordered-label case/arm comparisons exceed the declared 10% work reduction threshold. "
             "The table separately identifies lower usable bandwidth at the same declared geometry/field gates, "
             "without an observed increase in BEM node count or raw matrix condition. "
             "A bounded bandwidth benefit is not a general runtime or reconstruction claim."]
    lines += _bandwidth_summary_lines(decisions)
    lines += ["", f"Postprocessing command: `{command}`.",
              "", "The supplemental JSON records input/source hashes, exact N and matrix-condition ratios, and the original timing decisions."]
    destinations[1].write_text("\n".join(lines)+"\n", encoding="utf-8")
    return 0


def main(argv=None):
    args = parse_args(argv)
    output = args.output
    if args.summarize_existing:
        return summarize_existing(output, command=shlex.join([sys.executable, str(Path(__file__).resolve()),
                                   *(argv if argv is not None else sys.argv[1:])]))
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing nonempty experiment directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    problem = build_problem()
    frontend_config = FrontendConfig(bounds=((.3, .3), (.7, .7)),
                                     grid_shape=(args.grid_size, args.grid_size),
                                     projected_samples=args.projected_samples)
    validation = BoundaryValidationConfig(num_samples_per_component=max(512, args.audit_samples))
    manifest = {"schema": "parameterization-aware-c1-c2-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                "command": shlex.join([sys.executable, str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:])]),
                "configuration": vars(args), "frontend_config": asdict(frontend_config),
                "kress_solve_config": asdict(KressSolveConfig()),
                "provenance": _provenance(), "experiment": asdict(problem), "observation_noise": "none",
                "cases": {}, "references": {},
                "literature": {"url": "https://arxiv.org/abs/2301.04241", "relationship":
                    "intuition only; this is variable projection of Cartesian coefficients and ordered labels, not Zhao-Serkh filtering"},
                "defaults_changed": False, "densities_compared": False,
                "distance_target_resolution": "not_applicable_no_neural_distillation",
                "fit_weights": "uniform fixed 1/M; B and skip unregularized",
                "shared_reference_cost_policy": "oracle generation is measured separately and excluded from per-arm work",
                "regularizer": "lambda sum k^(2q)(cos_k^2+sin_k^2), q=2; parameterization-dependent",
                "decision": "same declared geometry and field accuracy; at least 10% observed total-work reduction; no automatic promotion"}
    write_strict_json(output/"manifest.json", manifest)
    rows = []; method_records = []

    def evaluate_arm(case, reference, truth, oracle, comparison, arm, bandwidth,
                     curve, representation, status, failure_reason, fit_seconds,
                     diagnostics, extraction_seconds, frontend_hash):
        key = f"{comparison}-{case.name}-{arm}-k{bandwidth}"
        record = {"id": key, "case": case.name, "comparison": comparison, "arm": arm,
                  "bandwidth": bandwidth, "status": status, "failure_reason": failure_reason,
                  "fit_seconds": fit_seconds, "extraction_seconds": extraction_seconds,
                  "frozen_projected_points_sha256": frontend_hash, "fit_diagnostics": diagnostics}
        if curve is None:
            rows.append({**record, "bem_nodes": None, "accuracy_gate_passed": False})
            method_records.append(record)
            return
        audit_started = perf_counter()
        report = validate_periodic_parameterization(curve, validation, raise_on_error=False)
        if not report.valid:
            record.update(status="failed", failure_reason="; ".join(report.issues))
            rows.append({**record, "bem_nodes": None, "accuracy_gate_passed": False})
            method_records.append(record)
            return
        geometry, spectra = geometry_metrics(curve, reference, audit_samples=args.audit_samples,
                                              localization_samples=args.localization_samples)
        audit_seconds = perf_counter()-audit_started
        record.update(geometry=geometry, validation=report.to_dict())
        arrays = dict(spectra)
        if representation is not None:
            arrays.update(cosine_coefficients=representation.cosine_coefficients,
                          sine_coefficients=representation.sine_coefficients)
            record["representation_kind"] = "Cartesian_Fourier"
        else:
            record["representation_kind"] = "analytic_ellipse_elliptic_integral_arclength"
            record["analytic_parameters"] = case.physical_parameters
        if "parameter_labels" in diagnostics and isinstance(diagnostics["parameter_labels"], list):
            arrays["optimized_labels"] = np.asarray(diagnostics["parameter_labels"])
        sample = curve.discretize(2*args.audit_samples)
        arrays.update(audit_parameters=sample.parameters, audit_points=sample.points,
                      audit_first_derivatives=sample.first_derivatives,
                      audit_second_derivatives=sample.second_derivatives,
                      reference_response=truth)
        predictions = []
        for nodes in args.bem_nodes:
            row = {**record, "bem_nodes": nodes, "geometry_audit_seconds": audit_seconds}
            try:
                response, forward_metrics = _forward(curve, problem, nodes)
                relative_by_frequency = np.linalg.norm(response-truth, axis=0)/np.linalg.norm(truth, axis=0)
                row.update(forward_metrics, field_relative_l2=float(np.linalg.norm(response-truth)/np.linalg.norm(truth)),
                           field_per_frequency_relative_l2=relative_by_frequency.tolist(),
                           field_maximum_frequency_relative_l2=float(np.max(relative_by_frequency)))
                row["accuracy_gate_passed"] = bool(oracle["passed"] and geometry["symmetric_set_distance_m"] <= args.geometry_tolerance_m
                    and geometry["set_distance_refinement_change_m"] <= .1*args.geometry_tolerance_m
                    and row["field_maximum_frequency_relative_l2"] <= args.field_tolerance)
                row["total_work_seconds"] = extraction_seconds+fit_seconds+audit_seconds+row["bem_seconds"]+row["conditioning_audit_seconds"]
                predictions.append(response)
                if len(predictions)>1:
                    row["frozen_curve_difference_previous_N_relative_l2"] = float(np.linalg.norm(predictions[-1]-predictions[-2])/np.linalg.norm(predictions[-1]))
            except (ValueError, np.linalg.LinAlgError) as error:
                row.update(status="failed", failure_reason=f"BEM N={nodes}: {type(error).__name__}: {error}", accuracy_gate_passed=False)
                predictions.append(np.full(truth.shape, np.nan+1j*np.nan))
            rows.append(row)
        arrays["bem_node_counts"] = np.array(args.bem_nodes)
        arrays["predictions"] = np.asarray(predictions)
        write_npz(output/"curves"/f"{key}.npz", arrays)
        method_records.append(record)

    for name in args.cases:
        case = build_case(name)
        reference = case.native.to_parameterization()
        manifest["cases"][name] = case.physical_parameters
        truth, oracle = _oracle(case, problem, initial_nodes=args.oracle_initial_nodes,
                                maximum_nodes=args.oracle_maximum_nodes, tolerance=args.oracle_tolerance)
        manifest["references"][name] = oracle
        write_npz(output/"observations"/f"{name}.npz", {
            "response": truth, "source_points": problem.source_points, "receiver_points": problem.receiver_points,
            "angular_frequencies": problem.angular_frequencies, "source_strengths": problem.source_strengths,
            "native_cosine_coefficients": case.native.cosine_coefficients,
            "native_sine_coefficients": case.native.sine_coefficients})
        if name == "ellipse":
            for arm in ("native-angle", "exact-arclength"):
                c1_start = perf_counter()
                curve = reference if arm == "native-angle" else exact_arclength_ellipse()
                evaluate_arm(case, reference, truth, oracle, "C1", arm, None, curve,
                             case.native if arm == "native-angle" else None, "success", None,
                             perf_counter()-c1_start, {"finite_band_refit": False,
                                 "arc_inverse_relative_tolerance": 2e-14 if arm == "exact-arclength" else None}, 0.0, None)
        extraction_start = perf_counter()
        counted = CountedImplicitField2D(case.field)
        frontend = prepare_single_component(counted, frontend_config)
        extraction_seconds = perf_counter()-extraction_start
        frozen_hash = hashlib.sha256(frontend.projected_points.tobytes()+frontend.parameters.tobytes()).hexdigest()
        manifest["cases"][name]["frontend_counts"] = asdict(counted.counts)
        manifest["cases"][name]["frozen_projected_points_sha256"] = frozen_hash
        write_npz(output/"frontends"/f"{name}.npz", {"parameters": frontend.parameters,
            "projected_points": frontend.projected_points, "raw_contour": frontend.single_component.raw_contour})
        for bandwidth in args.bandwidths:
            fits = {}
            for arm in ("B-arclength", "skip-arclength", "ordered-label-unregularized", "ordered-label-penalized"):
                fit_start = perf_counter()
                dependency_seconds = 0.0
                try:
                    if arm == "B-arclength":
                        fit = fit_method_b(frontend, config=MethodBConfig(bandwidth=bandwidth,
                            arclength=ArcLengthConfig(dense_resolution=4096, validation_resolution=1024), validation=validation))
                    elif arm == "skip-arclength":
                        fit = fit_without_arclength(frontend.parameters, frontend.projected_points,
                                                   bandwidth=bandwidth, validation_resolution=512)
                    else:
                        fallback = fits.get("B-arclength") or fits.get("skip-arclength")
                        if fallback is None:
                            raise ValueError("Neither linear baseline supplies a valid fallback")
                        dependency_seconds = fallback.runtime_seconds
                        fit = fit_parameter_aware(frontend.parameters, frontend.projected_points,
                            fallback=fallback, config=ParameterAwareConfig(bandwidth=bandwidth,
                                max_iterations=args.fit_iterations,
                                spectral_penalty=0.0 if arm.endswith("unregularized") else args.spectral_penalty))
                    fits[arm] = fit
                    intrinsic_fit_seconds = perf_counter()-fit_start
                    evaluate_arm(case, reference, truth, oracle, "C2", arm, bandwidth,
                                 fit.parameterization, fit.representation, fit.status, fit.failure_reason,
                                 intrinsic_fit_seconds+dependency_seconds,
                                 {**dict(fit.diagnostics), "intrinsic_fit_seconds": intrinsic_fit_seconds,
                                  "baseline_fit_dependency_seconds": dependency_seconds},
                                 extraction_seconds, frozen_hash)
                except (ValueError, np.linalg.LinAlgError) as error:
                    evaluate_arm(case, reference, truth, oracle, "C2", arm, bandwidth, None, None,
                                 "failed", f"{type(error).__name__}: {error}", perf_counter()-fit_start,
                                 {}, extraction_seconds, frozen_hash)
            print(f"{name} K={bandwidth}: " + ", ".join(f"{arm}={fit.status}" for arm, fit in fits.items()), flush=True)
        write_strict_json(output/"manifest.json", manifest)
        write_strict_json(output/"metrics.json", {"rows": rows, "methods": method_records})
        write_metrics_csv(output/"metrics.csv", rows)
    decisions = decision_records(rows, args)
    manifest.update(total_seconds=perf_counter()-started,
                    completed=True, method_count=len(method_records), row_count=len(rows))
    write_strict_json(output/"manifest.json", manifest)
    write_strict_json(output/"metrics.json", {"rows": rows, "methods": method_records, "decisions": decisions})
    write_metrics_csv(output/"metrics.csv", rows)
    lines = ["# Parameterization-aware fitting: bounded C1/C2 experiment", "",
             "C1 changes only the exact ellipse parameterization. C2 shares frozen projected points and varies Cartesian bandwidth independently of BEM nodes.", "",
             "The new ordered-label variable-projection method is a simpler experiment inspired by [Zhao–Serkh](https://arxiv.org/abs/2301.04241), not their speed/tangent-angle algorithm.", "",
             f"Geometry gate: {args.geometry_tolerance_m:g} m; maximum per-frequency field gate: {args.field_tolerance:g}. The source is noiseless homogeneous full-space TMz.", "",
             "| Case | Arm | Accuracy-eligible | Observed matched-work win |", "|---|---|---:|---:|"]
    for decision in decisions:
        lines.append(f"| {decision['case']} | {decision['arm']} | {decision['candidate_eligible']} | {decision['matched_work_win_observed']} |")
    lines += _bandwidth_summary_lines(decisions)
    lines += ["", f"Methods: {len(method_records)}; rows: {len(rows)}; wall time: {manifest['total_seconds']:.2f} s.",
              "", "Fit failures and baseline fallbacks remain in metrics. Timings are one bounded sample, not a statistical speedup claim. No production default was changed. Conditioning, derivative/normal errors, spectra, closest-point refinement agreement, oracle convergence and full source provenance are in the JSON/CSV bundle.",
              "", "The non-star reference is an invertible parabolic shear of the unit circle. Its visibility-kernel tangent halfplanes are inconsistent, so it is not star-shaped about any point. Its native Cartesian bandwidth is two."]
    (output/"summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
