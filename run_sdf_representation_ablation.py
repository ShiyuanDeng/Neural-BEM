#!/usr/bin/env python3
"""Opt-in Task-A policy ablation; historical MLP driver defaults are unchanged.

Profiles reuse the existing driver configuration and continuation helpers.
The short profile is a deterministic contract experiment. The saved-star
profile reuses the recorded 2026-09-04 benchmark's numerical arguments.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import ExitStack
import csv
from dataclasses import asdict, fields, is_dataclass, replace
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import sys
from time import perf_counter
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "solvers"))

import run_mlp_sdf_inverse_comparison as legacy
import sdf_inverse.forward as forward
import sdf_inverse.geometry as geometry
import sdf_inverse.neural as neural
import sdf_inverse.neural_optimization as inverse
from sdf_inverse.curve_updates import (
    fit_radial_fourier_curve_state,
    radial_fourier_parameterization,
    radial_fourier_state_curve,
)
from sdf_inverse.optimization import ComplexScatteredData, normalized_complex_residual


POLICIES = ("legacy_strict", "curve_only", "export_only")
SAVED = ROOT / "results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/metrics.json"


def _jsonable(value):
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return legacy._jsonable(value)


def _write_json(path, payload):
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _fresh_output(path):
    path = Path(path).resolve()
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"Ablation output must be new or empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _profile_arguments(profile, output):
    if profile == "saved-star":
        recorded = json.loads(SAVED.read_text(encoding="utf-8"))
        argv = shlex.split(recorded["command"])[1:]
        index = argv.index("--output-dir")
        argv[index + 1] = str(output)
        argv = [value for value in argv if value != "--overwrite"]
    else:
        argv = [
            "--target", "circle", "--initial-shape", "ellipse", "--solvers", "kress",
            "--train-ghz", "0.5,1.5", "--holdout-ghz", "0.25,1.0",
            "--num-pairs", "8", "--num-nodes", "64", "--maximum-mode", "3",
            "--outer-iterations", "4", "--redistance-steps", "1200",
            "--redistance-samples", "512", "--output-dir", str(output),
        ]
    return legacy._parse_args(argv)


class PipelineWork:
    """Serial diagnostic instrumentation, restored after every measured phase.

    Explicit autograd.grad invocations are counted as spatial-gradient calls;
    Adam's parameter backward is separate. Model forwards include training,
    distance audits and extraction. These counters are not wall-time estimates.
    """

    def __init__(self, model):
        self.model = model
        self.counts = dict(
            sdf_value_calls=0, sdf_query_points=0, spatial_gradient_calls=0,
            extraction_calls=0, neural_training_calls=0, neural_training_steps=0,
            field_audit_calls=0, paired_forward_calls=0,
            finite_difference_forward_calls=0, line_search_forward_calls=0,
            other_forward_calls=0, finite_difference_seconds=0.0,
            line_search_probe_seconds=0.0,
        )
        self.in_jacobian = self.in_modal_probe = False

    def _wrapper(self, function, name):
        @wraps(function)
        def counted(*args, **kwargs):
            self.counts[name] += 1
            if name == "paired_forward_calls":
                kind = ("finite_difference" if self.in_jacobian else
                        "line_search" if self.in_modal_probe else "other")
                self.counts[kind + "_forward_calls"] += 1
            result = function(*args, **kwargs)
            if name == "neural_training_calls":
                self.counts["neural_training_steps"] += int(result.steps)
            return result
        return counted

    def __enter__(self):
        self.stack = ExitStack()

        def model_called(module, inputs):
            self.counts["sdf_value_calls"] += 1
            if inputs and isinstance(inputs[0], torch.Tensor):
                self.counts["sdf_query_points"] += int(inputs[0].shape[0])

        self.hook = self.model.register_forward_pre_hook(model_called)
        self.stack.callback(self.hook.remove)
        targets = [
            (torch.autograd, "grad", "spatial_gradient_calls"),
            (geometry, "build_ordered_sdf_geometry", "extraction_calls"),
            (forward, "build_ordered_sdf_geometry", "extraction_calls"),
            (inverse, "build_ordered_sdf_geometry", "extraction_calls"),
            (neural, "redistance_neural_sdf_to_curve", "neural_training_calls"),
            (inverse, "redistance_neural_sdf_to_curve", "neural_training_calls"),
            (inverse, "_field_audit", "field_audit_calls"),
            (forward, "predict_paired_curve_response", "paired_forward_calls"),
        ]
        for module, name, counter in targets:
            original = getattr(module, name)
            self.stack.enter_context(patch.object(module, name, self._wrapper(original, counter)))
        original_jacobian = inverse._modal_jacobian
        original_probe = inverse._ModalEvaluator.evaluate

        def jacobian(*args, **kwargs):
            started = perf_counter()
            self.in_jacobian = True
            try:
                return original_jacobian(*args, **kwargs)
            finally:
                self.in_jacobian = False
                self.counts["finite_difference_seconds"] += perf_counter() - started

        def probe(*args, **kwargs):
            started = perf_counter()
            self.in_modal_probe = True
            try:
                return original_probe(*args, **kwargs)
            finally:
                self.in_modal_probe = False
                if not self.in_jacobian:
                    self.counts["line_search_probe_seconds"] += perf_counter() - started

        self.stack.enter_context(patch.object(inverse, "_modal_jacobian", jacobian))
        self.stack.enter_context(patch.object(inverse._ModalEvaluator, "evaluate", probe))
        self.started = perf_counter()
        return self

    def __exit__(self, *exception):
        self.seconds = perf_counter() - self.started
        return self.stack.__exit__(*exception)

    def metrics(self):
        return {**self.counts, "seconds": self.seconds}


def _state_arrays(state):
    return dict(
        center_m=np.array(state.center),
        radius_cosine_coefficients_m=np.array(state.radius_cosine_coefficients),
        radius_sine_coefficients_m=np.array(state.radius_sine_coefficients),
    )


def _state_vector(state):
    values = [state.mean_radius_m, *state.center]
    for mode in range(2, state.maximum_mode + 1):
        values.extend((state.radius_cosine_coefficients[mode], state.radius_sine_coefficients[mode]))
    return np.asarray(values)


def _write_trajectory(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _response_metrics(response, truth, train_count):
    residual, training_error = normalized_complex_residual(response[:, :train_count], truth[:, :train_count])
    _, holdout_error = normalized_complex_residual(response[:, train_count:], truth[:, train_count:])
    return dict(training_loss=0.5 * float(residual @ residual),
                training_relative_l2=training_error, holdout_relative_l2=holdout_error)


def _policy_summary_row(policy, values):
    field_metrics = values.get("canonical_fields") or {}
    holdout = field_metrics.get("holdout_relative_l2")
    holdout_text = "n/a" if holdout is None else f"{holdout:.4e}"
    def phase_time(name):
        phase = values.get(name)
        return "n/a" if phase is None else f"{phase['seconds']:.2f}"
    return (
        f"| {policy} | {values['reconstruction_stop_reason']} | {values['representation_status']} | "
        f"{holdout_text} | {phase_time('reconstruction')} | {phase_time('export')} | "
        f"{values['end_to_end_seconds']:.2f} |"
    )


def _policy_run(policy, args, target, initial_state, initial_curve, problem, truth,
                geometry_config, base_redistance, plan, output):
    directory = output / policy
    directory.mkdir()
    started = perf_counter()
    model = neural.SmoothMLPSDF2D(
        bounds=geometry_config.bounds, hidden_features=args.hidden_features,
        hidden_layers=args.hidden_layers, seed=args.mlp_seed,
        geometric_center=legacy.DEFAULT_INITIAL_CENTER,
        geometric_radius=legacy.DEFAULT_INITIAL_RADIUS, dtype=torch.float64,
    )
    model.eval()
    representation_curve = None
    initial_fit = None
    initialization_failure = None
    with PipelineWork(model) as initialization:
        if policy == "legacy_strict":
            initial_fit = neural.redistance_neural_sdf_to_curve(model, initial_curve, base_redistance)
            if initial_fit.converged:
                try:
                    representation_curve = geometry.build_ordered_sdf_geometry(model, geometry_config).curve
                except geometry.OrderedSDFGeometryError as exc:
                    initialization_failure = f"strict_initialization_extraction_failure: {exc}"
    summary = dict(policy=policy, initialization=initialization.metrics(),
                   initial_training_status=None if initial_fit is None else initial_fit.stop_reason,
                   reconstruction=None, export=None, final_audit=None,
                   canonical_fields=None, representation_fields=None,
                   canonical_maximum_sampled_boundary_error_m=None,
                   representation_maximum_sampled_boundary_error_m=None,
                   representation_drift_m=None, forward_refinement=None,
                   maximum_system_residual=None, requested_delivery_complete=False,
                   final_audit_status="not_evaluated", final_audit_failure_reason=None,
                   inverse_config=None,
                   model_initialization=dict(seed=args.mlp_seed, hidden_features=args.hidden_features,
                                             hidden_layers=args.hidden_layers),
                   accepted_updates=0, stages=[])
    if initialization_failure is not None or (initial_fit is not None and not initial_fit.converged):
        reason = initialization_failure or initial_fit.stop_reason
        summary.update(reconstruction_converged=False, reconstruction_stop_reason="strict_initialization_failed",
                       representation_status="failed", representation_stop_reason=reason,
                       legacy_converged=False, legacy_stop_reason="strict_initialization_failed",
                       representation_evaluated=True, end_to_end_seconds=perf_counter() - started)
        np.savez_compressed(directory / "canonical.npz", **_state_arrays(initial_state), points=initial_curve.points)
        _write_json(directory / "metrics.json", summary)
        return summary, None

    inner_redistance = legacy._incremental_redistance_config(base_redistance)
    settings = inverse.AlternatingNeuralInverseConfig(
        redistance=inner_redistance, max_iterations=args.outer_iterations,
        maximum_mode=initial_state.maximum_mode, direct_curve_retraction="radial_fourier",
        maximum_modal_field_update_m=args.maximum_modal_update_mm * 1.0e-3,
        maximum_redistance_curve_drift_m=args.maximum_redistance_drift_mm * 1.0e-3,
        geometry_change_tolerance_m=args.geometry_convergence_tolerance_mm * 1.0e-3,
        distillation_policy="legacy_strict" if policy == "legacy_strict" else "curve_only",
    )
    state, curve = initial_state, initial_curve
    rows, coordinates, coefficients, stage_results = [], [], [], []
    accepted = seed_offset = 0
    with PipelineWork(model) as reconstruction:
        for stage in plan:
            budget = legacy._effective_stage_budget(
                stage=stage.stage, stage_count=len(plan), planned_max_iterations=stage.max_iterations,
                total_iterations=args.outer_iterations, accepted_updates_before_stage=accepted,
            )
            count = len(stage.train_frequencies_ghz)
            stage_problem = replace(problem, angular_frequencies=problem.angular_frequencies[:count],
                                    source_strengths=problem.source_strengths[:count])
            automatic_mode = legacy._mode_budget(stage_problem, curve.points, requested=None)["maximum_mode"]
            maximum_mode = legacy._continuation_stage_maximum_mode(
                stage.stage, len(plan), final_maximum_mode=initial_state.maximum_mode,
                automatic_maximum_mode=automatic_mode, strategy=args.continuation_strategy,
            )
            stage_config = legacy._stage_inverse_config(
                settings, redistance_config=replace(inner_redistance, seed=inner_redistance.seed + seed_offset),
                max_iterations=budget, maximum_mode=maximum_mode,
                spectral_tail_reference_rms_m=inverse.radial_spectral_tail_rms(initial_curve.points, maximum_mode),
                audit_seed=settings.audit_seed + seed_offset,
            )
            recorded_state = state

            def progress(item):
                nonlocal recorded_state
                if item.iteration:
                    recorded_state = recorded_state.incremented(item.modal_step, maximum_mode=maximum_mode)
                rows.append(dict(
                    stage=stage.stage, stage_iteration=item.iteration,
                    training_frequency_count=count, maximum_mode=maximum_mode,
                    loss=item.loss, relative_l2_error=item.relative_l2_error,
                    representation_evaluated=item.representation_evaluated,
                    redistance_curve_drift_m=item.redistance_curve_drift_m,
                    redistance_steps=item.redistance_steps,
                    redistance_stop_reason=item.redistance_stop_reason,
                    evaluation_count=item.evaluation_count,
                ))
                coordinates.append(np.array(item.geometry_points))
                coefficients.append(_state_vector(recorded_state))
                if item.iteration % 5 == 0:
                    print(f"[{policy}] stage={stage.stage} iteration={item.iteration} loss={item.loss:.4e}", flush=True)

            result = inverse.run_alternating_neural_inverse(
                model, ComplexScatteredData(stage_problem, truth[:, :count]), geometry_config,
                solver="kress", config=stage_config, initial_curve=curve,
                initial_representation_curve=representation_curve,
                initial_radial_curve_state=state, progress_callback=progress,
            )
            state, curve = result.final_radial_curve_state, result.final_curve
            representation_curve = result.final_representation_curve
            np.testing.assert_allclose(_state_vector(recorded_state), _state_vector(state), rtol=0.0, atol=1.0e-14)
            stage_results.append(result)
            accepted += len(result.iterations) - 1
            seed_offset += stage.max_iterations
    summary["reconstruction"] = reconstruction.metrics()
    summary["reconstruction"].update(
        optimizer_evaluations=sum(value.total_evaluation_count for value in stage_results),
        infeasible_evaluations=sum(value.infeasible_evaluation_count for value in stage_results),
        bem_seconds=sum(value.total_bem_seconds for value in stage_results),
        geometry_audit_seconds=sum(value.total_geometry_audit_seconds for value in stage_results),
        accepted_backtracks=sum(record.accepted_backtrack_count
                                for value in stage_results for record in value.iterations),
        full_validation_rejections=sum(value.full_validation_rejection_count for value in stage_results),
    )
    summary.update(
        accepted_updates=accepted,
        reconstruction_converged=stage_results[-1].reconstruction_converged,
        reconstruction_stop_reason=stage_results[-1].reconstruction_stop_reason,
        legacy_converged=stage_results[-1].converged if policy == "legacy_strict" else None,
        legacy_stop_reason=stage_results[-1].stop_reason if policy == "legacy_strict" else None,
        stages=[dict(stage=index + 1, accepted_updates=len(value.iterations) - 1,
                     reconstruction_converged=value.reconstruction_converged,
                     reconstruction_stop_reason=value.reconstruction_stop_reason,
                     legacy_stop_reason=value.stop_reason) for index, value in enumerate(stage_results)],
    )
    canonical_before_export = _state_vector(state).copy()
    canonical_points_before_export = np.array(curve.points)
    export_result = None
    with PipelineWork(model) as export:
        if policy == "export_only":
            export_result = inverse.export_neural_sdf_representation(
                model, curve, geometry_config, config=replace(settings, redistance=base_redistance),
                continuous_curve=radial_fourier_parameterization(state),
            )
            representation_curve = export_result.curve if export_result.status == "passed" else None
    summary["export"] = export.metrics()
    np.testing.assert_array_equal(_state_vector(state), canonical_before_export)
    np.testing.assert_array_equal(curve.points, canonical_points_before_export)
    if export_result is None:
        summary.update(
            representation_evaluated=policy == "legacy_strict",
            representation_status=stage_results[-1].representation_status,
            representation_stop_reason=stage_results[-1].representation_stop_reason,
            representation_drift_m=stage_results[-1].final_iteration.redistance_curve_drift_m,
        )
    else:
        summary.update(
            representation_evaluated=export_result.representation_evaluated,
            representation_status=export_result.status,
            representation_stop_reason=export_result.stop_reason,
            representation_drift_m=export_result.drift_m,
        )
        summary["export_diagnostics"] = {
            field.name: getattr(export_result, field.name)
            for field in fields(export_result) if field.name != "curve"
        }
        summary["export_config"] = asdict(replace(settings, redistance=replace(base_redistance, distance_target="smooth_curve")))
    # Persist the authoritative reconstruction before optional representation
    # diagnostics. Even an unexpected diagnostic programming error must leave
    # recoverable canonical coefficients, trajectory, and reconstruction status.
    arrays = dict(**_state_arrays(state), points=curve.points, trajectory_points=np.stack(coordinates),
                  trajectory_coefficients=np.stack(coefficients))
    np.savez_compressed(directory / "canonical.npz", **arrays)
    _write_trajectory(directory / "trajectory.csv", rows)
    summary["inverse_config"] = asdict(settings)
    summary["model_initialization"] = dict(seed=args.mlp_seed, hidden_features=args.hidden_features,
                                           hidden_layers=args.hidden_layers)
    summary["end_to_end_seconds"] = perf_counter() - started
    summary["final_audit_status"] = "pending"
    summary["final_audit_failure_reason"] = None
    _write_json(directory / "metrics.json", summary)
    predicted = refined_prediction = representation = representation_refinement = None
    refined_config = replace(geometry_config, num_nodes=2 * geometry_config.num_nodes)
    expected_diagnostic_errors = (
        geometry.OrderedSDFGeometryError, FloatingPointError, np.linalg.LinAlgError,
    )
    with PipelineWork(model) as final_audit:
        try:
            predicted = forward.predict_paired_curve_response(curve, problem, geometry_config, solver="kress")
            refined_curve = radial_fourier_parameterization(state).discretize(refined_config.num_nodes, require_even=True)
            refined_prediction = forward.predict_paired_curve_response(refined_curve, problem, refined_config, solver="kress")
        except expected_diagnostic_errors as exc:
            summary["final_audit_status"] = "failed"
            summary["final_audit_failure_reason"] = f"canonical_forward_audit_failure: {type(exc).__name__}: {exc}"
        else:
            summary["canonical_fields"] = _response_metrics(predicted.scattered_response, truth, len(args.train_ghz))
            np.savez_compressed(directory / "responses.npz", canonical=predicted.scattered_response)
            summary["final_audit_status"] = "canonical_passed_representation_pending" if representation_curve is not None else "passed"
            _write_json(directory / "metrics.json", summary)
            if representation_curve is not None:
                try:
                    representation = forward.predict_paired_curve_response(
                        representation_curve, problem, replace(geometry_config, num_nodes=representation_curve.num_nodes), solver="kress")
                    refined_representation = geometry.build_ordered_sdf_geometry(model, refined_config).curve
                    representation_refinement = forward.predict_paired_curve_response(
                        refined_representation, problem, refined_config, solver="kress")
                except expected_diagnostic_errors as exc:
                    reason = f"representation_final_audit_failure: {type(exc).__name__}: {exc}"
                    summary.update(final_audit_status="failed", final_audit_failure_reason=reason,
                                   representation_status="failed", representation_stop_reason=reason)
                    representation = representation_refinement = None
                    representation_curve = None
                else:
                    summary["final_audit_status"] = "passed"
    summary["final_audit"] = final_audit.metrics()
    def relative_difference(coarse, fine):
        return float(np.linalg.norm(coarse - fine) / max(np.linalg.norm(fine), np.finfo(float).tiny))
    summary["forward_refinement"] = dict(
        coarse_num_nodes=geometry_config.num_nodes, fine_num_nodes=refined_config.num_nodes,
        canonical_relative_difference=None if predicted is None or refined_prediction is None else relative_difference(
            predicted.scattered_response, refined_prediction.scattered_response),
        representation_relative_difference=None if representation is None else relative_difference(
            representation.scattered_response, representation_refinement.scattered_response),
        note="Canonical coefficients frozen; representation extraction/fit settings frozen while output node count doubles.",
    )
    summary["canonical_fields"] = None if predicted is None else _response_metrics(predicted.scattered_response, truth, len(args.train_ghz))
    summary["canonical_maximum_sampled_boundary_error_m"] = float(np.max(target.boundary_distances(curve.points)))
    summary["representation_fields"] = None if representation is None else _response_metrics(
        representation.scattered_response, truth, len(args.train_ghz))
    summary["representation_maximum_sampled_boundary_error_m"] = None if representation_curve is None else float(
        np.max(target.boundary_distances(representation_curve.points)))
    summary["maximum_system_residual"] = max(value.maximum_system_residual for value in stage_results)
    summary["end_to_end_seconds"] = perf_counter() - started
    summary["requested_delivery_complete"] = summary["final_audit_status"] == "passed" and bool(summary["reconstruction_converged"]) and (
        policy == "curve_only" or summary["representation_status"] == "passed")
    if representation_curve is not None:
        arrays["representation_points"] = representation_curve.points
    np.savez_compressed(directory / "canonical.npz", **arrays)
    responses = {} if predicted is None else dict(canonical=predicted.scattered_response)
    if representation is not None:
        responses["representation"] = representation.scattered_response
    np.savez_compressed(directory / "responses.npz", **responses)
    if policy != "curve_only":
        np.savez_compressed(directory / "model_state.npz", **{
            name: value.detach().cpu().numpy() for name, value in model.state_dict().items()})
    _write_json(directory / "metrics.json", summary)
    return summary, np.stack(coefficients)


def _trajectory_comparison(first, second, *, atol=1.0e-13):
    if first is None or second is None:
        return dict(evaluated=False, passed=None, reason="trajectory_unavailable")
    shape_matches = first.shape == second.shape
    maximum = float(np.max(np.abs(first - second))) if shape_matches else None
    return dict(evaluated=True, passed=bool(shape_matches and maximum <= atol),
                absolute_coefficient_tolerance=atol, shape_matches=shape_matches,
                maximum_coefficient_difference=maximum)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=("short", "saved-star"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=POLICIES)
    options = parser.parse_args(argv)
    if len(set(options.policies)) != len(options.policies):
        parser.error("policies must not contain duplicates")
    output = _fresh_output(options.output_dir)
    args = _profile_arguments(options.profile, output)
    common_started = perf_counter()
    target = legacy._build_target(args.target)
    geometry_config = target.geometry_config(args.num_nodes)
    teacher = legacy._initial_teacher(args.initial_shape)
    with PipelineWork(teacher) as common_geometry:
        raw_curve = geometry.build_ordered_sdf_geometry(teacher, geometry_config).curve
    sources, receivers = legacy._ring_scan(center=target.center, standoff=0.30, num_pairs=args.num_pairs)
    problem = legacy._build_problem(tuple(args.train_ghz) + tuple(args.holdout_ghz), sources, receivers)
    train_problem = replace(problem, angular_frequencies=problem.angular_frequencies[:len(args.train_ghz)],
                            source_strengths=problem.source_strengths[:len(args.train_ghz)])
    mode_budget = legacy._mode_budget(train_problem, raw_curve.points, args.maximum_mode)
    state = fit_radial_fourier_curve_state(raw_curve, maximum_mode=mode_budget["maximum_mode"])
    curve = radial_fourier_state_curve(state, geometry_config=geometry_config, full_validation=True)
    truth = target.observations(problem)
    truth.setflags(write=False)
    reference = target.oracle_diagnostics(problem)
    if reference is not None and reference["maximum_relative_difference"] > 1.0e-6:
        raise RuntimeError("Observation oracle did not pass its declared 1e-6 self-convergence gate")
    plan = legacy._frequency_continuation_plan(args.train_ghz, args.outer_iterations,
                                              strategy=args.continuation_strategy)
    redistance = legacy._redistance_config(args, geometry_config.bounds)
    source_paths = [Path(__file__).resolve(), ROOT / "run_mlp_sdf_inverse_comparison.py",
                    ROOT / "run_sdf_inverse_comparison.py", ROOT / "docs/codex_sdf_kress_priorities_2026-09-05.md"]
    for package in ("sdf_inverse", "gpr_bem_kress", "ordered_boundary", "sdf_to_ordered_boundary"):
        source_paths.extend(sorted((ROOT / "solvers" / package).glob("*.py")))
    source_paths.extend(sorted((ROOT / "config").glob("*.py")))
    manifest = dict(
        schema="sdf-reconstruction-representation-ablation-v1", profile=options.profile,
        created_utc=datetime.now(timezone.utc).isoformat(),
        command=shlex.join([sys.executable, str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]),
        provenance=legacy._git_state(), experiment=legacy._experiment_snapshot(problem, target),
        source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
        python=platform.python_version(), numpy=np.__version__, torch=torch.__version__,
        environment={name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "PYTHONPATH")},
        saved_profile_source=str(SAVED.relative_to(ROOT)) if options.profile == "saved-star" else None,
        observations_sha256=hashlib.sha256(truth.tobytes()).hexdigest(),
        oracle_identity=target.truth_oracle, oracle_convergence=reference,
        geometry_config=asdict(geometry_config), initial_redistance_config=asdict(redistance),
        initial_state=_state_arrays(state), initial_geometry=common_geometry.metrics(),
        initial_projection_rms_m=state.initial_projection_rms_m,
        continuation_plan=[asdict(stage) for stage in plan],
        common_preparation_seconds=perf_counter() - common_started,
        accuracy_policy=dict(trajectory_coefficient_absolute_tolerance=1.0e-13,
                             representation_tolerance_m=args.geometry_convergence_tolerance_mm * 1.0e-3),
        phase_timing_note="Per-policy end-to-end includes model initialization, strict warm start, reconstruction, export and final audits. Shared teacher extraction/oracle preparation is reported separately.",
        comparisons={}, policies={},
    )
    np.savez_compressed(output / "common.npz", truth=truth, sources=sources, receivers=receivers,
                        angular_frequencies=problem.angular_frequencies, source_strengths=problem.source_strengths,
                        initial_points=curve.points, **_state_arrays(state))
    _write_json(output / "metrics.json", manifest)
    trajectories = {}
    for policy in options.policies:
        print(f"Starting {options.profile}/{policy}", flush=True)
        values, trajectory = _policy_run(policy, args, target, state, curve, problem, truth,
                                         geometry_config, redistance, plan, output)
        manifest["policies"][policy] = values
        trajectories[policy] = trajectory
        _write_json(output / "metrics.json", manifest)
    for first, second in (("curve_only", "export_only"), ("legacy_strict", "curve_only")):
        if first in trajectories and second in trajectories:
            manifest["comparisons"][f"{first}_vs_{second}"] = _trajectory_comparison(trajectories[first], trajectories[second])
    checks = []
    if "curve_only_vs_export_only" in manifest["comparisons"]:
        checks.append(manifest["comparisons"]["curve_only_vs_export_only"]["passed"] is True)
    for policy in ("curve_only", "export_only"):
        if policy in manifest["policies"]:
            counts = manifest["policies"][policy]["reconstruction"]
            checks.append(all(counts[name] == 0 for name in (
                "sdf_value_calls", "spatial_gradient_calls", "extraction_calls", "neural_training_calls", "field_audit_calls")))
    manifest["policy_contract_evaluated"] = bool(checks)
    manifest["policy_contract_passed"] = all(checks) if checks else None
    _write_json(output / "metrics.json", manifest)
    lines = ["# Reconstruction / representation policy ablation", "", f"Profile: `{options.profile}`.", "",
             "Each policy uses identical immutable observations and initial canonical coefficients.",
             "Strict initialization and every optional phase are timed explicitly; no historical result is rewritten.", "",
             "| Policy | Reconstruction status | Representation | Holdout error | Reconstruction s | Export s | End-to-end s |",
             "|---|---|---|---:|---:|---:|---:|"]
    for policy, values in manifest["policies"].items():
        lines.append(_policy_summary_row(policy, values))
    lines.extend(["", f"Policy contract passed: `{manifest['policy_contract_passed']}`.",
                  "Reconstruction convergence, field accuracy, and successful SDF delivery are separate outcomes."])
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Artifacts: {output}", flush=True)
    return 2 if manifest["policy_contract_passed"] is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
