#!/usr/bin/env python3
"""Bounded H1 distance-contact/tangent-jet adaptation, not RFTA reproduction."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
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

from ordered_boundary import BoundaryValidationConfig
from sdf_to_ordered_boundary.arclength import ArcLengthConfig
from sdf_to_ordered_boundary.artifacts import write_metrics_csv, write_npz, write_strict_json
from sdf_to_ordered_boundary.distance_tangency import (
    DistanceTangencyConfig, fit_distance_tangency, make_offsurface_queries,
    projected_contact_samples, sample_distance_contacts,
)
from sdf_to_ordered_boundary.fields import CountedImplicitField2D, TorchImplicitField2D
from sdf_to_ordered_boundary.frontend import (
    FrontendConfig, ProjectionConfig, prepare_single_component, project_to_zero_set,
)
from sdf_to_ordered_boundary.method_b import MethodBConfig, fit_method_b_from_samples
from sdf_to_ordered_boundary.parameter_aware import closest_parameters
from sdf_to_ordered_boundary.representations import FourierBoundary
from run_parameterization_aware_comparison import (
    Case, _forward, _oracle, build_case, build_problem, geometry_metrics,
)


FROZEN_B = ROOT/"results/representation/smooth_distance_supervision/task-b-circle-star-refined-20260905"
GATES = {"geometry_m": 2e-4, "physical_maximum_relative_error": 1e-3,
         "physical_self_convergence": 1e-5, "oracle_self_convergence": 1e-6,
         "geometry_refinement_change_m": 2e-6, "maximum_system_condition": 1e8,
         "contact_zero_m": 1e-5, "contact_fit_m": 2e-4,
         "closest_contact_m": 2e-4, "meaningful_work_ratio": .9}


class ExactEllipseDistance:
    """Continuous ellipse signed distance evaluated by numerical closest contact.

    Geometry is the field-service definition, not an input to the converter.
    This evaluator uses analytic ellipse membership and analytic closest-point
    normals; dense multistart refinement is numerical, not a certified oracle.
    Its cost is included in timed field calls. Independent doubled localization
    and Eikonal checks are reported as evaluator audits, never fit acceptance.
    """
    name = "analytic_ellipse_numerically_refined_signed_distance"
    is_signed_distance = True
    sign_convention = "negative_inside_positive_outside"

    def __init__(self, case, localization_samples=512):
        self.case = case
        self.curve = case.native.to_parameterization()
        self.localization_samples = localization_samples

    def _evaluate(self, xy):
        points = np.asarray(xy, dtype=float)
        flat = points.reshape(-1, 2)
        parameters, distances = closest_parameters(flat, self.curve,
            localization_samples=self.localization_samples, candidates=8)
        evaluation = self.curve.evaluate(parameters)
        derivative = evaluation.first_derivatives
        normal = np.column_stack((derivative[:, 1], -derivative[:, 0]))
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        distances *= np.where(self.case.field.value(flat) < 0, -1., 1.)
        return distances.reshape(points.shape[:-1]), normal.reshape(points.shape)

    def value(self, xy):
        return self._evaluate(xy)[0]

    def gradient(self, xy):
        return self._evaluate(xy)[1]


class DistortedDistance:
    """Same zero/sign and unit interface gradient; intentionally nonmetric."""
    is_signed_distance = False
    sign_convention = "negative_inside_positive_outside"

    def __init__(self, field, amplitude=.4, scale_m=.02):
        self.field, self.amplitude, self.scale_m = field, amplitude, scale_m
        self.name = "same_zero_nonmetric_distance_distortion"

    def value(self, xy):
        distance = self.field.value(xy)
        return distance*(1+self.amplitude*np.tanh(distance/self.scale_m))

    def gradient(self, xy):
        distance = self.field.value(xy)
        u = distance/self.scale_m
        z = np.tanh(u)
        factor = 1+self.amplitude*z+self.amplitude*u*(1-z*z)
        return self.field.gradient(xy)*factor[..., None]


@dataclass(frozen=True)
class ExperimentCase:
    name: str
    field: object
    reference: Case
    definition: dict
    canonical_reference: Case | None = None
    frozen_model: object | None = None


def array_hash(values):
    value = np.ascontiguousarray(values)
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode()); digest.update(str(value.shape).encode())
    digest.update(value.tobytes())
    return digest.hexdigest()


def state_hash(model):
    return {key: array_hash(value.detach().cpu().numpy()) for key, value in model.state_dict().items()}


def build_cases(*, include_neural=True):
    cases = []
    for shape in ("circle", "ellipse"):
        analytic = build_case(shape)
        exact = analytic.field if shape == "circle" else ExactEllipseDistance(analytic)
        for variant, field in (("exact", exact), ("distorted", DistortedDistance(exact))):
            cases.append(ExperimentCase(f"{shape}_{variant}", field, analytic,
                {"shape": shape, "variant": variant, "physical_parameters": analytic.physical_parameters,
                 "field_definition": ("signed_distance" if variant == "exact"
                     else "d*(1+0.4*tanh(d/0.02)); same zero/sign, interface gradient norm one"),
                 "distance_evaluator": "closed_form" if shape == "circle" else "512_seed_8_candidate_local_refinement"}))
    if include_neural:
        import torch
        from sdf_inverse.neural import SmoothMLPSDF2D
        summary = json.loads((FROZEN_B/"summary.json").read_text())
        with np.load(FROZEN_B/"arrays.npz", allow_pickle=False) as archive:
            model = SmoothMLPSDF2D(bounds=((.35, .35), (.65, .65)), hidden_features=32,
                hidden_layers=2, geometric_center=(.5, .5), geometric_radius=.060, seed=2718).to(dtype=torch.float64)
            prefix = "star_smooth_curve_model_"
            state = {key[len(prefix):]: torch.from_numpy(np.array(archive[key], copy=True))
                     for key in archive.files if key.startswith(prefix)}
            model.load_state_dict(state, strict=True)
            model.eval()
            for parameter in model.parameters():
                parameter.requires_grad_(False)
            zero = FourierBoundary(archive["star_smooth_curve_extracted_cosine_grid513"],
                                   archive["star_smooth_curve_extracted_sine_grid513"], name="frozen_neural_zero_grid513")
        source = next(item for item in summary["cases"] if item["shape"] == "star")
        canonical = FourierBoundary(source["canonical_cartesian_cosine"], source["canonical_cartesian_sine"],
                                    name="independent_canonical_star")
        field = TorchImplicitField2D(model, dtype=torch.float64)
        cases.append(ExperimentCase("frozen_neural_star", field,
            Case("frozen_neural_zero", field, zero, {}),
            {"shape": "star", "variant": "frozen_neural", "training_repeated": False,
             "source_directory": str(FROZEN_B.relative_to(ROOT)), "source_policy": "smooth_curve",
             "model": model.initialization_metadata(), "initial_state_hashes": state_hash(model),
             "zero_reference": "saved grid513 K96 Fourier extraction, approximate not analytic truth",
             "zero_reference_limitation": "inherits saved extraction error; target error reported separately"},
            Case("canonical_star", None, canonical, {}), model))
    return cases


def chord_labels(points):
    distances = np.linalg.norm(np.roll(points, -1, axis=0)-points, axis=1)
    if np.any(distances <= 0):
        raise ValueError("Repeated contact points cannot define ordered labels.")
    return 2*np.pi*np.r_[0., np.cumsum(distances[:-1])]/np.sum(distances)


def add_counts(*counts):
    names = ("value_calls", "value_points", "gradient_calls", "gradient_points")
    return {name: sum(item[name] for item in counts) for name in names}


def _hash_files(paths):
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(paths)) if path.is_file()}


def provenance(include_neural):
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False).stdout.strip()
    sources = [Path(__file__), ROOT/"run_parameterization_aware_comparison.py",
               ROOT/"docs/codex_sdf_kress_priorities_2026-09-05.md"]
    for directory in ("ordered_boundary", "sdf_to_ordered_boundary", "gpr_bem_kress", "gpr_bem_ref", "nystrom_ref"):
        sources += list((ROOT/"solvers"/directory).rglob("*.py"))
    sources += [ROOT/"solvers/sdf_inverse"/name for name in
                ("models.py", "forward.py", "nystrom_oracle.py", "neural.py")]
    if include_neural:
        sources += [FROZEN_B/"summary.json", FROZEN_B/"arrays.npz"]
    return {"git_commit": git("rev-parse", "HEAD"), "dirty_paths": git("status", "--short").splitlines(),
            "sha256": _hash_files(sources), "python": sys.version, "numpy": np.__version__,
            "scipy": scipy.__version__, "platform": platform.platform(),
            "thread_caps": {key: os.environ.get(key) for key in
                ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "command": shlex.join([sys.executable, *sys.argv]),
            "utc_started": datetime.now(timezone.utc).isoformat()}


def analyze_curve(curve, case, problem, oracle_response, oracle_report, canonical_response, nodes,
                  arrays, prefix, *, audit_samples):
    geometry, spectra = geometry_metrics(curve, case.reference.native.to_parameterization(),
                                        audit_samples=audit_samples, localization_samples=512)
    for key, value in spectra.items():
        arrays[f"{prefix}_{key}"] = value
    canonical_geometry = None
    if case.canonical_reference is not None:
        canonical_geometry, _ = geometry_metrics(curve, case.canonical_reference.native.to_parameterization(),
                                                  audit_samples=audit_samples, localization_samples=512)
    evaluations = []
    for count in nodes:
        response, diagnostic = _forward(curve, problem, count)
        arrays[f"{prefix}_response_N{count}"] = response
        errors = np.linalg.norm(response-oracle_response, axis=0)/np.linalg.norm(oracle_response, axis=0)
        canonical_errors = (None if canonical_response is None else
            (np.linalg.norm(response-canonical_response, axis=0)/np.linalg.norm(canonical_response, axis=0)).tolist())
        evaluations.append({"nodes": count, "maximum_relative_field_error": float(np.max(errors)),
                            "per_frequency_relative_field_error": errors.tolist(),
                            "canonical_per_frequency_relative_field_error": canonical_errors,
                            "self_convergence_to_next_nodes": None, **diagnostic})
    for index, entry in enumerate(evaluations[:-1]):
        coarse = arrays[f"{prefix}_response_N{nodes[index]}"]
        fine = arrays[f"{prefix}_response_N{nodes[index+1]}"]
        entry["self_convergence_to_next_nodes"] = float(np.max(
            np.linalg.norm(fine-coarse, axis=0)/np.linalg.norm(fine, axis=0)))
    qualifying = [entry for entry in evaluations if oracle_report["passed"]
        and geometry["symmetric_set_distance_m"] <= GATES["geometry_m"]
        and geometry["set_distance_refinement_change_m"] <= GATES["geometry_refinement_change_m"]
        and geometry["closest_point_localization_refinement_agreement_m"] <= GATES["geometry_refinement_change_m"]
        and entry["maximum_system_condition"] <= GATES["maximum_system_condition"]
        and entry["maximum_relative_field_error"] <= GATES["physical_maximum_relative_error"]
        and entry["self_convergence_to_next_nodes"] is not None
        and entry["self_convergence_to_next_nodes"] <= GATES["physical_self_convergence"]]
    return {"geometry": geometry, "canonical_geometry": canonical_geometry,
            "physical": evaluations, "lowest_qualified_nodes": min((x["nodes"] for x in qualifying), default=None)}


def decisions(records):
    result = []
    for name in sorted({record["case"] for record in records}):
        subset = [record for record in records if record["case"] == name]
        best = {}
        for arm in sorted({record["arm"] for record in subset}):
            qualified = [record for record in subset if record["arm"] == arm
                         and record["status"] == "success" and record["returned_audit"]["lowest_qualified_nodes"] is not None]
            if not qualified:
                best[arm] = None
                continue
            selected = min(qualified, key=lambda record: record["conversion_seconds"]+next(
                x["bem_seconds"] for x in record["returned_audit"]["physical"]
                if x["nodes"] == record["returned_audit"]["lowest_qualified_nodes"]))
            forward = next(x for x in selected["returned_audit"]["physical"]
                           if x["nodes"] == selected["returned_audit"]["lowest_qualified_nodes"])
            best[arm] = {"bandwidth": selected["bandwidth"], "nodes": forward["nodes"],
                "minimum_qualified_bandwidth": min(record["bandwidth"] for record in qualified),
                "whole_work_seconds": selected["conversion_seconds"]+forward["bem_seconds"],
                "field_queries": selected["field_queries"],
                "geometry_m": selected["returned_audit"]["geometry"]["symmetric_set_distance_m"],
                "maximum_relative_field_error": forward["maximum_relative_field_error"]}
        comparisons = []
        for arm in ("distance_contacts", "distance_tangent_jet", "projected_tangent_jet"):
            controls = ("shared_zero_method_b", "offsurface_zero_method_b")
            if arm.startswith("distance_"):
                controls += ("projected_tangent_jet",)
            for baseline in controls:
                candidate, control = best.get(arm), best.get(baseline)
                ratio = None if candidate is None or control is None else candidate["whole_work_seconds"]/control["whole_work_seconds"]
                comparisons.append({"candidate": arm, "baseline": baseline, "work_ratio": ratio,
                    "matched_error_work_win": ratio is not None and ratio < GATES["meaningful_work_ratio"],
                    "lower_usable_bandwidth": (None if candidate is None or control is None else
                        candidate["minimum_qualified_bandwidth"] < control["minimum_qualified_bandwidth"]),
                    "comparison_missing_reason": ("candidate or baseline unqualified within bounded K/N ladder" if ratio is None else None)})
        result.append({"case": name, "best_qualified": best, "comparisons": comparisons})
    return result


def summarize_existing(output):
    """Correct/extend derived decisions without changing frozen measurements."""
    metrics_path = output/"metrics.json"
    original_bytes = metrics_path.read_bytes()
    metrics = json.loads(original_bytes)
    destination = output/"decision_supplement.json"
    if destination.exists():
        raise FileExistsError("Do not overwrite an existing decision supplement.")
    supplement = {"measurement_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "postprocessing_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "postprocessing_command": shlex.join([sys.executable, *sys.argv]),
        "utc_created": datetime.now(timezone.utc).isoformat(),
        "supersedes": "metrics.json decisions only; measurements remain byte-identical",
        "correction": "Lower usable bandwidth compares minimum qualified K, not K of the fastest single timed record. Original circle flags incorrectly suggested a K reduction when all methods qualify at K1.",
        "added_control": "Distance-contact arms also compared directly with the distance-free projected+tangent arm to isolate metric information from ordered-label/tangent fitting.",
        "decisions": decisions(metrics["records"])}
    write_strict_json(destination, supplement)
    if metrics_path.read_bytes() != original_bytes:
        raise RuntimeError("Frozen measurements changed during postprocessing.")
    return supplement


def run(args):
    if args.output.exists():
        raise FileExistsError("Use a fresh output directory; prior artifacts are immutable.")
    if len(args.nodes) < 2 or any(n % 2 or n < 16 for n in args.nodes) or sorted(set(args.nodes)) != args.nodes:
        raise ValueError("Need increasing distinct even BEM nodes, at least two resolutions.")
    if any(k < 1 or 2*k+1 > args.samples for k in args.bandwidths):
        raise ValueError("Bandwidths must be positive with enough samples.")
    started = perf_counter()
    args.output.mkdir(parents=True)
    manifest = {"provenance": provenance(not args.no_neural),
        "configuration": {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items()},
        "gates_frozen_before_measurement": GATES,
        "method_scope": "continuous distance-contact/tangent-jet adaptation; not RFTA sparse-distance reconstruction",
        "source": "https://odedstein.com/projects/reach-for-the-arcs/",
        "metric_contact_formula": "x-phi(x)*gradient(phi)/norm(gradient(phi)); exact SDF also one Newton step",
        "gradient_access": "continuous analytic/autodiff spatial gradient, not supplied sparse signed distances",
        "optimization": "positive ordered labels plus unregularized Cartesian Fourier coefficients; eta 0 or 0.1",
        "cost_policy": "Each arm pays its shared frontend and provisioned original Method-B fallback; proposal and arm-specific queries counted in full. Geometry/reference/BEM-refinement audits itemized separately.",
        "query_count_definition": "External continuous-field interface point queries. Gradient callbacks can internally evaluate values (including distorted analytic fields); elapsed query time includes those internals, so counts are not universal primitive-operation costs.",
        "decision_work_definition": "whole_work_seconds is audit-excluded selected pipeline conversion plus one lowest-qualified-N forward. K/N are selected posthoc within a frozen ladder; this is not the total experiment/search/oracle work, which is separately reported.",
        "no_truth_leakage": "Converters receive only field-derived samples, configured thresholds and original Method-B fallback. References and physical responses used only after fitting; no error-selected reruns."}
    manifest["configuration_and_gates_sha256"] = hashlib.sha256(json.dumps(
        {"configuration": manifest["configuration"], "gates": GATES}, sort_keys=True).encode()).hexdigest()
    write_strict_json(args.output/"manifest.json", manifest)
    problem = build_problem()
    arrays = {"source_points": problem.source_points, "receiver_points": problem.receiver_points,
              "angular_frequencies": problem.angular_frequencies, "source_strengths": problem.source_strengths}
    physics = {"exterior": asdict(problem.exterior), "interior": asdict(problem.interior),
               "eps0": problem.eps0, "mu0": problem.mu0, "noise": {"kind": "none", "added": False}}
    records, case_reports = [], []
    for case in build_cases(include_neural=not args.no_neural):
        print(f"Starting {case.name}", flush=True)
        prefix = case.name
        reference = case.reference.native
        arrays[f"{prefix}_reference_cosine"] = reference.cosine_coefficients
        arrays[f"{prefix}_reference_sine"] = reference.sine_coefficients
        oracle_response, oracle_report = _oracle(case.reference, problem, initial_nodes=128,
            maximum_nodes=args.oracle_max_nodes, tolerance=GATES["oracle_self_convergence"])
        arrays[f"{prefix}_oracle_response"] = oracle_response
        canonical_response = None
        canonical_report = None
        if case.canonical_reference is not None:
            canonical_response, canonical_report = _oracle(case.canonical_reference, problem, initial_nodes=128,
                maximum_nodes=args.oracle_max_nodes, tolerance=GATES["oracle_self_convergence"])
            arrays[f"{prefix}_canonical_oracle_response"] = canonical_response
            arrays[f"{prefix}_canonical_cosine"] = case.canonical_reference.native.cosine_coefficients
            arrays[f"{prefix}_canonical_sine"] = case.canonical_reference.native.sine_coefficients
        frontend_field = CountedImplicitField2D(case.field)
        phase = perf_counter()
        frontend_config = FrontendConfig(bounds=((.35, .35), (.65, .65)),
            grid_shape=(args.grid, args.grid), projected_samples=args.samples, maximum_num_components=1)
        frontend = prepare_single_component(frontend_field, frontend_config)
        frontend_seconds = perf_counter()-phase
        seed_counts = asdict(frontend_field.counts)
        seed_points = np.array(frontend.projected_points, copy=True); seed_points.setflags(write=False)
        seed_labels = np.array(frontend.parameters, copy=True); seed_labels.setflags(write=False)
        arrays[f"{prefix}_seed_points"] = seed_points
        arrays[f"{prefix}_seed_labels"] = seed_labels
        proposal_field = CountedImplicitField2D(case.field)
        phase = perf_counter()
        sources = make_offsurface_queries(proposal_field, seed_points, offset_m=args.offset_m)
        sources.setflags(write=False)
        proposal_seconds = perf_counter()-phase
        proposal_counts = asdict(proposal_field.counts)
        arrays[f"{prefix}_offsurface_sources"] = sources
        projected_field = CountedImplicitField2D(case.field)
        phase = perf_counter()
        projected = project_to_zero_set(projected_field, sources, grid_spacing=2*args.offset_m,
                                       config=ProjectionConfig())
        projected_labels = chord_labels(projected.points)
        projection_seconds = perf_counter()-phase
        projection_counts = asdict(projected_field.counts)
        arrays[f"{prefix}_ordinary_zero_projection"] = projected.points
        distance_field = CountedImplicitField2D(case.field)
        phase = perf_counter()
        distance_samples = sample_distance_contacts(distance_field, sources)
        distance_seconds = perf_counter()-phase
        distance_counts = asdict(distance_field.counts)
        tangent_field = CountedImplicitField2D(case.field)
        phase = perf_counter()
        tangent_samples = projected_contact_samples(tangent_field, sources, projected.points)
        tangent_seconds = perf_counter()-phase
        tangent_counts = asdict(tangent_field.counts)
        for name, sample in (("distance", distance_samples), ("projected", tangent_samples)):
            for key in ("source_points", "signed_values", "contacts", "normals", "contact_normalized_zero_residual_m"):
                arrays[f"{prefix}_{name}_{key}"] = getattr(sample, key)
        audit_field = CountedImplicitField2D(case.field)
        audit_started = perf_counter()
        evaluator_audit = {"maximum_contact_zero_residual_m": float(np.max(distance_samples.contact_normalized_zero_residual_m)),
                           "gradient_norm_on_seed_maximum_error": float(np.max(np.abs(np.linalg.norm(audit_field.gradient(seed_points), axis=1)-1)))}
        reference_curve = case.reference.native.to_parameterization()
        closest, distances = closest_parameters(sources, reference_curve, localization_samples=1024, candidates=8)
        nearest = reference_curve.evaluate(closest)
        normal = np.column_stack((nearest.first_derivatives[:, 1], -nearest.first_derivatives[:, 0]))
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        true_distance = distances*np.where(np.sum((sources-nearest.points)*normal, axis=1) < 0, -1., 1.)
        arrays[f"{prefix}_independent_source_signed_distance_audit"] = true_distance
        evaluator_audit["offsurface_signed_distance_rms_error_m"] = float(np.sqrt(np.mean((distance_samples.signed_values-true_distance)**2)))
        evaluator_audit["offsurface_signed_distance_maximum_error_m"] = float(np.max(np.abs(distance_samples.signed_values-true_distance)))
        if case.name.startswith("ellipse"):
            exact = case.field.field if isinstance(case.field, DistortedDistance) else case.field
            tighter = ExactEllipseDistance(exact.case, localization_samples=1024)
            evaluator_audit["distance_localization_doubling_maximum_change_m"] = float(np.max(np.abs(exact.value(sources)-tighter.value(sources))))
            evaluator_audit["independent_evaluator_comparison_value_points"] = 2*len(sources)
        evaluator_audit["field_queries"] = asdict(audit_field.counts)
        evaluator_audit["seconds"] = perf_counter()-audit_started
        case_report = {"case": case.name, "definition": case.definition, "reference_oracle": oracle_report,
            "canonical_oracle": canonical_report, "frontend_config": asdict(frontend_config),
            "projection_config": asdict(ProjectionConfig()), "projection_grid_spacing_m": 2*args.offset_m,
            "projection_maximum_iterations": int(np.max(projected.iteration_counts)),
            "shared_stage_seconds": {"frontend": frontend_seconds, "proposal": proposal_seconds,
                "ordinary_projection": projection_seconds, "distance_contact_queries": distance_seconds,
                "projected_tangent_queries": tangent_seconds},
            "shared_stage_queries": {"frontend": seed_counts, "proposal": proposal_counts,
                "ordinary_projection": projection_counts, "distance_contact_queries": distance_counts,
                "projected_tangent_queries": tangent_counts},
            "evaluator_audit_not_acceptance_truth": evaluator_audit,
            "frozen_input_hashes": {"seed_points": array_hash(seed_points), "seed_labels": array_hash(seed_labels),
                "offsurface_sources": array_hash(sources), "oracle_response": array_hash(oracle_response)}}
        for bandwidth in args.bandwidths:
            method_config = MethodBConfig(bandwidth=bandwidth, arclength=ArcLengthConfig(refit_sample_count=args.samples),
                validation=BoundaryValidationConfig(num_samples_per_component=512))
            phase = perf_counter()
            baseline = fit_method_b_from_samples(seed_labels, seed_points, config=method_config)
            baseline_seconds = perf_counter()-phase
            phase = perf_counter()
            zero_b = fit_method_b_from_samples(projected_labels, projected.points, config=method_config)
            zero_b_seconds = perf_counter()-phase
            arms = [("shared_zero_method_b", baseline, baseline.representation, baseline_seconds,
                     seed_counts, frontend_seconds+baseline_seconds),
                    ("offsurface_zero_method_b", zero_b, zero_b.representation, zero_b_seconds,
                     add_counts(seed_counts, proposal_counts, projection_counts),
                     frontend_seconds+baseline_seconds+proposal_seconds+projection_seconds+zero_b_seconds)]
            for arm, sample, weight in (("distance_contacts", distance_samples, 0.),
                                        ("distance_tangent_jet", distance_samples, .1),
                                        ("projected_tangent_jet", tangent_samples, .1)):
                config = DistanceTangencyConfig(bandwidth=bandwidth, max_iterations=args.iterations,
                    tangency_weight=weight, spectral_penalty=0., contact_zero_tolerance_m=GATES["contact_zero_m"],
                    contact_fit_tolerance_m=GATES["contact_fit_m"], closest_contact_tolerance_m=GATES["closest_contact_m"])
                phase = perf_counter()
                fitted, raw = fit_distance_tangency(sample, chord_labels(sample.contacts), fallback=baseline, config=config)
                fit_seconds = perf_counter()-phase
                if arm == "projected_tangent_jet":
                    counts = add_counts(seed_counts, proposal_counts, projection_counts, tangent_counts)
                    query_seconds = proposal_seconds+projection_seconds+tangent_seconds
                else:
                    counts = add_counts(seed_counts, proposal_counts, distance_counts)
                    query_seconds = proposal_seconds+distance_seconds
                arms.append((arm, fitted, raw, fit_seconds, counts,
                             frontend_seconds+baseline_seconds+query_seconds+fit_seconds))
            for arm, fitted, raw, fit_seconds, counts, conversion_seconds in arms:
                key = f"{prefix}_{arm}_K{bandwidth}"
                arrays[f"{key}_returned_cosine"] = fitted.representation.cosine_coefficients
                arrays[f"{key}_returned_sine"] = fitted.representation.sine_coefficients
                arrays[f"{key}_raw_cosine"] = raw.cosine_coefficients
                arrays[f"{key}_raw_sine"] = raw.sine_coefficients
                audit = analyze_curve(fitted.parameterization, case, problem, oracle_response, oracle_report,
                    canonical_response, args.nodes, arrays, key, audit_samples=args.audit_samples)
                raw_audit = None
                if fitted.status == "fallback" and fitted.diagnostics["raw_candidate_validation"]["valid"]:
                    raw_audit = analyze_curve(raw.to_parameterization(), case, problem, oracle_response, oracle_report,
                        canonical_response, args.nodes, arrays, key+"_raw", audit_samples=args.audit_samples)
                records.append({"case": case.name, "arm": arm, "bandwidth": bandwidth, "status": fitted.status,
                    "failure_reason": fitted.failure_reason, "fit_seconds": fit_seconds,
                    "conversion_seconds": conversion_seconds, "field_queries": counts,
                    "fallback_provisioning_seconds": 0. if arm == "shared_zero_method_b" else baseline_seconds,
                    "diagnostics": fitted.diagnostics, "returned_audit": audit, "raw_rejected_audit": raw_audit,
                    "raw_not_audited_reason": ("invalid raw topology/derivatives" if fitted.status == "fallback" and raw_audit is None else None)})
            print(f"  K={bandwidth}: "+", ".join(f"{arm}={fitted.status}" for arm, fitted, *_ in arms), flush=True)
        if case.frozen_model is not None:
            final = state_hash(case.frozen_model)
            case_report["final_state_hashes"] = final
            case_report["frozen_model_unchanged"] = final == case.definition["initial_state_hashes"]
            if not case_report["frozen_model_unchanged"]:
                raise RuntimeError("Frozen model state changed.")
        case_report["input_arrays_unchanged"] = all(array_hash(arrays[f"{prefix}_{key}"]) == value
            for key, value in case_report["frozen_input_hashes"].items())
        case_reports.append(case_report)
    result = {"manifest": "manifest.json", "physics": physics, "cases": case_reports, "records": records,
              "decisions": decisions(records), "elapsed_seconds": perf_counter()-started,
              "neural_tested": not args.no_neural}
    result["actual_field_interface_queries_during_batch"] = add_counts(*[
        counts for case in case_reports for counts in (
            *case["shared_stage_queries"].values(), case["evaluator_audit_not_acceptance_truth"]["field_queries"])])
    result["independent_fixture_distance_value_points"] = sum(
        case["evaluator_audit_not_acceptance_truth"].get("independent_evaluator_comparison_value_points", 0)
        for case in case_reports)
    result["physical_audit_bem_solve_count"] = sum(physical["bem_solve_count"]
        for record in records for audit in (record["returned_audit"], record["raw_rejected_audit"])
        if audit is not None for physical in audit["physical"])
    result["standalone_arm_query_totals_are_not_summed_as_actual_batch_work"] = True
    final_hashes = _hash_files([ROOT/path for path in manifest["provenance"]["sha256"]])
    result["source_hash_changes_during_run"] = {path: {"before": before, "after": final_hashes.get(path)}
        for path, before in manifest["provenance"]["sha256"].items() if final_hashes.get(path) != before}
    write_strict_json(args.output/"metrics.json", result)
    rows = [{"case": r["case"], "arm": r["arm"], "bandwidth": r["bandwidth"], "status": r["status"],
        "failure_reason": r["failure_reason"], "conversion_seconds": r["conversion_seconds"],
        **r["field_queries"], "returned_geometry_m": r["returned_audit"]["geometry"]["symmetric_set_distance_m"],
        "raw_geometry_m": (None if r["raw_rejected_audit"] is None else r["raw_rejected_audit"]["geometry"]["symmetric_set_distance_m"]),
        **physical} for r in records for physical in r["returned_audit"]["physical"]]
    write_metrics_csv(args.output/"metrics.csv", rows)
    write_npz(args.output/"arrays.npz", arrays)
    print(f"Saved {len(records)} arms in {result['elapsed_seconds']:.2f}s to {args.output}", flush=True)
    return result


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--bandwidths", type=int, nargs="+", default=[1, 4, 8])
    result.add_argument("--nodes", type=int, nargs="+", default=[64, 128, 256])
    result.add_argument("--oracle-max-nodes", type=int, default=1024)
    result.add_argument("--grid", type=int, default=65)
    result.add_argument("--samples", type=int, default=96)
    result.add_argument("--iterations", type=int, default=80)
    result.add_argument("--audit-samples", type=int, default=128)
    result.add_argument("--offset-m", type=float, default=.003)
    result.add_argument("--no-neural", action="store_true")
    result.add_argument("--summarize-existing", action="store_true")
    return result


if __name__ == "__main__":
    options = parser().parse_args()
    if options.summarize_existing:
        summarize_existing(options.output)
    else:
        run(options)
