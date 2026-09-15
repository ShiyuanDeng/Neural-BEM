"""Opt-in frozen conversion, Eikonal, and one-update Method-B diagnostics.

No radial state, inverse loop, production-default changes, or automatic result
catalog promotion. See docs/implicit_mlp_diagnostics.md before interpreting.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import traceback

import numpy as np
import torch

from gpr_bem_kress import Material
from gpr_bem_kress.forward import solve_kress_tmz_total_field_batch
from ordered_boundary import BoundaryValidationConfig, validate_periodic_parameterization
from sdf_inverse.continuous_distance import signed_distance_to_continuous_curve
from sdf_inverse.method_b_diagnostics import (
    checkpoint, conversion_settings, fit_metrics, fit_steps, fork_checkpoint,
    model_from_metadata, prepare_fit_data, transfer_comparison,
)
from sdf_inverse.neural import NeuralRedistanceConfig
from sdf_to_ordered_boundary import (
    ArcLengthConfig, FourierBoundary, FrontendConfig, MethodBConfig,
    PeriodicSplineBoundary, TorchImplicitField2D, extract_frontend_components,
    fit_fourier_least_squares, fit_method_b,
)


ROOT = Path(__file__).resolve().parent
FROZEN = ROOT / "results/representation/smooth_distance_supervision/task-b-circle-star-refined-20260905"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, complex):
        return dict(real=value.real, imag=value.imag)
    return value


def write_json(path, value):
    # Strict JSON: a nonfinite result is a failure, never a silent NaN gate.
    payload = json.dumps(jsonable(value), indent=2, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload)
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(value, reference):
    return float(np.linalg.norm(value-reference)/max(np.linalg.norm(reference), np.finfo(float).tiny))


def objective(value, observations):
    return .5 * relative(value, observations)**2


def distance_audit(first, second, counts, tolerance):
    records = []
    for count in counts:
        directed = []
        for source, target in ((first, second), (second, first)):
            distances = signed_distance_to_continuous_curve(
                source.discretize(count).points, target, tolerance_m=1e-9,
                initial_samples=512, maximum_samples=8192,
            )
            directed.append(float(np.max(np.abs(distances))))
        records.append(dict(samples=count, first_to_second_max_m=directed[0],
                            second_to_first_max_m=directed[1], symmetric_max_m=max(directed)))
    change = max(abs(records[-1][key]-records[-2][key]) for key in
                 ("first_to_second_max_m", "second_to_first_max_m"))
    return dict(records=records, symmetric_max_m=records[-1]["symmetric_max_m"],
                refinement_change_m=change, resolved=change <= tolerance)


class Study:
    def __init__(self, args, frozen):
        self.args = args
        self.frozen = frozen
        self.output = args.output_dir
        self.work = dict(bem_batch_attempts=0, frontend_attempts=0, method_b_attempts=0)
        self.started = perf_counter()
        self.frontends = {}
        self.target_fields = {}
        self.acquisition = dict(frozen["acquisition"])
        strength = self.acquisition["source_strength"]
        self.acquisition["source_strength"] = complex(strength["real"], strength["imag"])
        for key in ("source_points", "receiver_points", "angular_frequencies"):
            self.acquisition[key] = np.asarray(self.acquisition[key])
        self.summary = dict(
            schema_version=1, experiment="strict_mlp_method_b_failure_isolation",
            status="running", started_utc=utc_now(), configuration=vars(args),
            acquisition=self.acquisition, cases=[], work=self.work,
            interpretation="Diagnostic only; no inverse acceptance or repair is implemented.",
            provenance=dict(
                command=[sys.executable, *sys.argv], python=platform.python_version(),
                numpy=np.__version__, torch=torch.__version__,
                commit=self.git("rev-parse", "HEAD"), dirty_status=self.git("status", "--short"),
                source_sha256=self.source_hashes(),
                input_sha256={name: digest(args.frozen / name) for name in ("summary.json", "arrays.npz")},
            ),
        )
        self.flush()

    @staticmethod
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

    @staticmethod
    def source_hashes():
        files = [Path(__file__), *sorted((ROOT / "solvers/sdf_inverse").glob("*.py")),
                 *sorted((ROOT / "solvers/sdf_to_ordered_boundary").glob("*.py")),
                 *sorted((ROOT / "solvers/ordered_boundary").glob("*.py")),
                 *sorted((ROOT / "solvers/gpr_bem_kress").glob("*.py"))]
        return {str(p.relative_to(ROOT)): digest(p) for p in files}

    def flush(self):
        self.summary["elapsed_seconds"] = perf_counter()-self.started
        write_json(self.output / "metrics.json", self.summary)

    def artifact(self, name, **arrays):
        path = self.output / (name + ".npz")
        np.savez_compressed(path, **arrays)
        return dict(path=path.name, sha256=digest(path))

    def save_checkpoint(self, name, model, optimizer):
        path = self.output / (name + ".pt")
        # Tensor/basic-container checkpoint; load with torch.load(..., weights_only=True).
        torch.save(checkpoint(model, optimizer), path)
        return dict(path=path.name, sha256=digest(path), model=model.initialization_metadata())

    def distance(self, first, second):
        return distance_audit(first, second, self.args.audit_samples, self.args.geometry_refinement_m)

    def forward(self, curve):
        a = self.acquisition
        records, previous = [], None
        start = perf_counter()
        for nodes in self.args.bem_nodes:
            values = []
            for omega in a["angular_frequencies"]:
                self.work["bem_batch_attempts"] += 1
                solved = solve_kress_tmz_total_field_batch(
                    curve.discretize(nodes, require_even=True), a["source_points"],
                    a["receiver_points"], omega, a["source_strength"],
                    exterior=Material(**a["exterior"]), interior=Material(**a["interior"]),
                    eps0=a["eps0"], mu0=a["mu0"],
                )
                values.append(np.diag(solved.scattered_receiver))
            response = np.column_stack(values)
            if not np.all(np.isfinite(response)):
                raise FloatingPointError("Nonfinite forward response.")
            records.append(dict(nodes=nodes, relative_change=None if previous is None else relative(response, previous)))
            previous = response
        return response, dict(records=records, seconds=perf_counter()-start,
                              resolved=records[-1]["relative_change"] <= self.args.field_refinement)

    def target_forward(self, curve):
        # Hold the object as well as its id so Python id reuse cannot alias a
        # later proposal. Only fixed target responses use this cache.
        key = id(curve)
        if key not in self.target_fields:
            self.target_fields[key] = (curve, *self.forward(curve))
        return self.target_fields[key][1:]

    def frontend(self, model, grid, samples):
        # Each model audit owns a fresh cache; never reuse extraction after fitting.
        key = (grid, samples)
        if key not in self.frontends:
            self.work["frontend_attempts"] += 1
            result = extract_frontend_components(
                TorchImplicitField2D(model, device="cpu", dtype=torch.float64),
                FrontendConfig(bounds=model.bounds, grid_shape=(grid, grid), projected_samples=samples),
            )
            if result.num_components != 1:
                raise ValueError(f"Expected one closed component, detected {result.num_components}.")
            self.frontends[key] = result.components[0]
        return self.frontends[key]

    def regularity(self, model, curve):
        field = TorchImplicitField2D(model, device="cpu", dtype=torch.float64)
        nodes = curve.discretize(max(self.args.audit_samples))
        points = np.array(nodes.points, copy=True)
        gradient, value = field.gradient(points), field.value(points)
        norm = np.linalg.norm(gradient, axis=1)
        alignment = np.einsum("ij,ij->i", gradient, nodes.normals)/np.maximum(norm, 1e-30)
        return dict(minimum_gradient_norm=float(norm.min()), maximum_abs_field_m=float(np.abs(value).max()),
                    maximum_linearized_zero_distance_m=float(np.max(np.abs(value)/np.maximum(norm, 1e-30))),
                    minimum_normal_alignment=float(alignment.min()),
                    negative_inside_regular=bool(np.all(norm > 1e-8) and np.all(alignment > 0)),
                    minimum_speed=float(nodes.speeds.min()), speed_ratio=float(nodes.speeds.max()/nodes.speeds.min()))

    def raw_reference(self, model, target, name):
        """Projected-loop cubic splines, independent of Cartesian Fourier fitting."""
        grids, samples = self.args.grids, self.args.projected_samples
        settings = [(grids[-1], samples[-1]), (grids[-2], samples[-1]), (grids[-1], samples[-2])]
        rows, curves, fields = [], [], []
        target_field, target_forward = self.target_forward(target)
        for index, (grid, count) in enumerate(settings):
            front = self.frontend(model, grid, count)
            spline = PeriodicSplineBoundary.interpolate(front.parameters, front.projected_points)
            curve = spline.to_parameterization()
            row = dict(status="running", grid=grid, projected_samples=count,
                       artifacts=self.artifact(f"{name}_raw{index}", raw_contour=front.raw_contour,
                           projected_points=front.projected_points, parameters=front.parameters,
                           spline_knots=spline.knots, spline_coefficients=spline.coefficients))
            rows.append(row)
            write_json(self.output / (name + "_raw_reference.json"), dict(refinements=rows))
            # Cubic splines have coherent C2 jets; use a fine derivative audit
            # independently of the quadratic topology sampling grid.
            validation = validate_periodic_parameterization(curve, BoundaryValidationConfig(
                num_samples_per_component=1024, derivative_samples_per_component=64*count,
            ), raise_on_error=True)
            field, forward = self.forward(curve)
            regularity = self.regularity(model, curve)
            row.update(status="completed", regularity=regularity,
                       validation=validation.to_dict(), forward=forward,
                       field_error_to_target=relative(field, target_field),
                       field_artifact=self.artifact(f"{name}_raw{index}_field", field=field))
            if curves:
                row["distance_to_finest"] = self.distance(curves[0], curve)
                row["field_change_to_finest"] = relative(field, fields[0])
            curves.append(curve)
            fields.append(field)
            write_json(self.output / (name + "_raw_reference.json"), dict(refinements=rows))
        resolved = all(row["forward"]["resolved"] and row["regularity"]["negative_inside_regular"]
                       and row["regularity"]["maximum_linearized_zero_distance_m"] <= self.args.geometry_refinement_m
                       for row in rows)
        resolved = resolved and all(row["distance_to_finest"]["resolved"]
                                   and row["distance_to_finest"]["symmetric_max_m"] <= self.args.geometry_refinement_m
                                   and row["field_change_to_finest"] <= self.args.field_refinement for row in rows[1:])
        target_distance = self.distance(curves[0], target)
        report = dict(reference="periodic cubic spline through projected zero-set points; numerical reference, not a certificate",
                      refinements=rows, resolved=bool(resolved and target_distance["resolved"] and target_forward["resolved"]),
                      raw_zero_set_to_target=target_distance, target_forward=target_forward)
        return curves[0], fields[0], report

    def converted(self, model, target, raw, raw_field, setting, name):
        grid, samples, bandwidth, dense = setting
        front = self.frontend(model, grid, samples)
        record = dict(status="running", setting=dict(grid=grid, projected_samples=samples, bandwidth=bandwidth,
                      arclength_dense=dense, arclength_refit_samples=max(self.args.projected_samples)), stages={},
                      projection_artifact=self.artifact(f"{name}_frontend", raw_contour=front.raw_contour,
                          initial_points=front.initial_points, projected_points=front.projected_points, parameters=front.parameters))
        record_path = self.output / (name + "_stages.json")
        write_json(record_path, record)
        initial = fit_fourier_least_squares(front.parameters, front.projected_points, bandwidth=bandwidth)
        initial_curve = initial.boundary.to_parameterization()

        def stage(label, curve, representation):
            # Persist coefficients before numerical validation/forward work.
            record["stages"][label] = dict(status="running", coefficients=self.artifact(
                f"{name}_{label}_curve", cosine=representation.cosine_coefficients, sine=representation.sine_coefficients))
            write_json(record_path, record)
            validate_periodic_parameterization(curve, BoundaryValidationConfig(
                num_samples_per_component=1024, fourier_bandwidth=bandwidth), raise_on_error=True)
            field, forward = self.forward(curve)
            target_field, target_forward = self.target_forward(target)
            record["stages"][label].update(
                status="completed", to_raw_zero_set=None if raw is None else self.distance(curve, raw),
                to_target=self.distance(curve, target), regularity=self.regularity(model, curve), forward=forward,
                field_error_to_raw=None if raw_field is None else relative(field, raw_field),
                field_error_to_target=relative(field, target_field), target_forward=target_forward,
                response=self.artifact(f"{name}_{label}_field", field=field))
            write_json(record_path, record)
            return field

        stage("initial_cartesian_fit", initial_curve, initial.boundary)
        self.work["method_b_attempts"] += 1
        result = fit_method_b(front, config=MethodBConfig(
            bandwidth=bandwidth,
            arclength=ArcLengthConfig(dense_resolution=dense, refit_sample_count=max(self.args.projected_samples),
                                      validation_resolution=1024),
            validation=BoundaryValidationConfig(num_samples_per_component=1024),
        ))
        if result.status != "success":
            raise ValueError(result.failure_reason)
        final_field = stage("arclength_refit", result.parameterization, result.representation)
        record.update(status="completed", initial_to_arclength=self.distance(initial_curve, result.parameterization),
                      method_b_diagnostics=result.diagnostics)
        write_json(record_path, record)
        return result.parameterization, final_field, record

    def audit(self, model, target, name, *, sweep=False):
        self.frontends = {}
        try:
            raw, raw_field, reference = self.raw_reference(model, target, name)
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as exc:
            raw, raw_field = None, None
            reference = dict(status="failed", resolved=False, error=str(exc), traceback=traceback.format_exc())
            partial = self.output / (name + "_raw_reference.json")
            if partial.is_file():
                reference["partial_refinements"] = partial.name
        settings = conversion_settings(self.args.grids, self.args.projected_samples,
                                       self.args.bandwidths, self.args.arclength_dense)
        anchor = tuple(max(values) for values in (self.args.grids, self.args.projected_samples,
                                                self.args.bandwidths, self.args.arclength_dense))
        if not sweep:
            settings = [anchor]
        records, final_curve, final_field = [], None, None
        for index, setting in enumerate(settings):
            try:
                curve, field, record = self.converted(model, target, raw, raw_field, setting, f"{name}_b{index}")
                if setting == anchor:
                    final_curve, final_field = curve, field
            except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as exc:
                record = dict(status="failed", setting=dict(zip(
                    ("grid", "projected_samples", "bandwidth", "arclength_dense"), setting)),
                    error=str(exc), traceback=traceback.format_exc())
                partial = self.output / f"{name}_b{index}_stages.json"
                if partial.is_file():
                    record["partial_stages"] = partial.name
            records.append(record)
            write_json(self.output / (name + "_audit.json"), dict(status="running", raw_reference=reference, conversions=records))
        anchor_record = next(r for r in records if tuple(r["setting"][k] for k in
                              ("grid", "projected_samples", "bandwidth", "arclength_dense")) == anchor)
        report = dict(raw_reference=reference, conversions=records, resolved=False,
                      geometry_gate=None, target_drift_m=None, conversion_drift_m=None)
        if anchor_record["status"] == "completed":
            final_stage = anchor_record["stages"]["arclength_refit"]
            resolved = reference["resolved"] and final_stage["forward"]["resolved"] and final_stage["to_raw_zero_set"]["resolved"]
            resolved = resolved and final_stage["to_target"]["resolved"] and final_stage["regularity"]["negative_inside_regular"]
            report.update(resolved=bool(resolved),
                          geometry_gate=final_stage["to_target"]["symmetric_max_m"] <= self.args.geometry_gate_m,
                          target_drift_m=final_stage["to_target"]["symmetric_max_m"],
                          conversion_drift_m=None if raw is None else final_stage["to_raw_zero_set"]["symmetric_max_m"])
        write_json(self.output / (name + "_audit.json"), report)
        return final_curve, final_field, report


def fitting_config(args, bounds):
    return NeuralRedistanceConfig(
        bounds=bounds, max_steps=args.warmup_steps+args.branch_steps,
        minimum_steps=1, warmup_steps=args.warmup_steps, sample_count=args.sample_count,
        heldout_sample_count=256, learning_rate=args.learning_rate,
        distance_target="smooth_curve", smooth_boundary_sampling="legacy_polygon",
        distance_rms_tolerance_m=1e-5, boundary_max_tolerance_m=1e-7,
        no_op_boundary_max_tolerance_m=1e-9, eikonal_weight=args.eikonal_current,
    )


def run_conversion(study, target, model, name):
    _, _, report = study.audit(model, target, name, sweep=True)
    return dict(status="failed" if any(r["status"] == "failed" for r in report["conversions"]) else "completed", geometry=report)


def run_eikonal(study, target, metadata, name):
    args = study.args
    model = model_from_metadata(metadata)  # Fresh original seeded initialization, not a fitted final state.
    config = fitting_config(args, model.bounds)
    data = prepare_fit_data(target, config)
    artifact = study.artifact(name + "_shared_training", **data.arrays)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    initial = fit_metrics(model, data, config)
    history = fit_steps(model, optimizer, data, config, steps=args.warmup_steps, weight=0.)
    shared = checkpoint(model, optimizer)
    shared_artifact = study.save_checkpoint(name + "_warmup", model, optimizer)
    _, warm_field, warm_audit = study.audit(model, target, name + "_warmup")
    truth, truth_forward = study.target_forward(target)
    report = dict(status="running", config=asdict(config), shared_data=artifact,
                  target_diagnostics=data.target_diagnostics, initial_fit=initial,
                  warmup=dict(checkpoint=shared_artifact, updates=len(history), losses=history,
                              fit=fit_metrics(model, data, config), geometry=warm_audit,
                              field_error=None if warm_field is None else relative(warm_field, truth)),
                  canonical_forward=truth_forward, arms=[])
    write_json(study.output / (name + ".json"), report)
    for weight in (0., args.eikonal_current/10., args.eikonal_current):
        label = name + f"_weight{weight:g}"
        branch, branch_optimizer = fork_checkpoint(model, shared, learning_rate=config.learning_rate)
        arm = dict(weight=weight, status="running", initial_fit=fit_metrics(branch, data, config))
        report["arms"].append(arm)
        try:
            losses = fit_steps(branch, branch_optimizer, data, config, steps=1, weight=weight)
            activation = dict(updates=1, checkpoint=study.save_checkpoint(label + "_activation", branch, branch_optimizer),
                              fit=fit_metrics(branch, data, config))
            _, activation_field, activation_geometry = study.audit(branch, target, label + "_activation")
            activation.update(geometry=activation_geometry,
                              field_error=None if activation_field is None else relative(activation_field, truth))
            arm["after_first_branch_update"] = activation
            write_json(study.output / (name + ".json"), report)
            losses += fit_steps(branch, branch_optimizer, data, config, steps=args.branch_steps-1, weight=weight)
            arm.update(checkpoint=study.save_checkpoint(label, branch, branch_optimizer), updates=len(losses), losses=losses,
                       fit=fit_metrics(branch, data, config))
            _, response, geometry = study.audit(branch, target, label)
            if response is None:
                arm["geometry"] = geometry
                raise ValueError("Final Method-B conversion or forward solve failed; fitting metrics/checkpoint retained.")
            arm.update(status="completed", geometry=geometry, field_error=relative(response, truth),
                       field_error_change_from_warmup=None if warm_field is None else relative(response, truth)-relative(warm_field, truth),
                       field_reference_resolved=truth_forward["resolved"] and geometry["resolved"])
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as exc:
            arm.update(status="failed", error=str(exc), traceback=traceback.format_exc())
        write_json(study.output / (name + ".json"), report)
    report["status"] = "completed" if all(arm["status"] == "completed" for arm in report["arms"]) else "failed"
    write_json(study.output / (name + ".json"), report)
    return report


def normal_proposal(curve, coefficients, bandwidth, sample_count):
    """Cartesian Fourier proposal driven by smooth normal modes of curve phase.

    Phase modes are deliberately local controls, not a radial geometry chart.
    """
    nodes = curve.discretize(sample_count)
    phase = 2*np.pi*(nodes.parameters-curve.parameter_origin)/curve.period
    maximum_mode = (len(coefficients)-1)//2
    basis = np.column_stack([np.ones(sample_count), *[term for k in range(1, maximum_mode+1)
                                                     for term in (np.cos(k*phase), np.sin(k*phase))]])
    requested = basis @ coefficients
    fitted = fit_fourier_least_squares(nodes.parameters, nodes.points+requested[:, None]*nodes.normals,
                                      bandwidth=bandwidth)
    proposal = fitted.boundary.to_parameterization()
    validate_periodic_parameterization(proposal, BoundaryValidationConfig(
        num_samples_per_component=1024, fourier_bandwidth=bandwidth,
    ), raise_on_error=True)
    realized = np.einsum("ij,ij->i", proposal.evaluate(nodes.parameters).points-nodes.points, nodes.normals)
    return proposal, dict(maximum_requested_motion_m=float(np.abs(requested).max()),
                          maximum_realized_motion_m=float(np.abs(realized).max()),
                          maximum_proposal_refit_error_m=float(np.max(np.abs(realized-requested))))


def run_transfer(study, target, model, name):
    args = study.args
    start, start_field, start_audit = study.audit(model, target, name + "_start")
    if start is None:
        return dict(status="blocked", reason="Frozen start cannot be converted and solved.", geometry=start_audit)
    truth, truth_forward = study.target_forward(target)
    start_objective = objective(start_field, truth)
    config = fitting_config(args, model.bounds)
    # The frozen result has no Adam state. All transfers deliberately begin
    # with the same empty optimizer state, which is saved and reported.
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    initial = checkpoint(model, optimizer)
    start_checkpoint = study.save_checkpoint(name + "_start", model, optimizer)
    dimension = 1+2*args.proposal_modes
    gradients = []
    probes = []
    for step in (args.fd_step_m, args.fd_step_m/2):
        gradient = []
        for index in range(dimension):
            pair = []
            for sign in (1., -1.):
                coefficients = np.zeros(dimension)
                coefficients[index] = sign*step
                proposal, motion = normal_proposal(start, coefficients, max(args.bandwidths), max(args.projected_samples))
                response, forward = study.forward(proposal)
                value = objective(response, truth)
                pair.append(value)
                probes.append(dict(step_m=step, mode_index=index, sign=sign, objective=value,
                                   forward=forward, motion=motion))
            gradient.append((pair[0]-pair[1])/(2*step))
        gradients.append(np.asarray(gradient))
    norm = float(np.linalg.norm(gradients[-1]))
    if not np.isfinite(norm) or norm < 1e-12:
        return dict(status="blocked", reason="No resolved nonzero local data gradient at frozen start.",
                    start_geometry=start_audit, start_objective=start_objective, probes=probes)
    direction = -gradients[-1]/norm
    derivative_change = relative(gradients[-1], gradients[0])
    basis_probe = np.column_stack([np.ones(4096), *[term for k in range(1, args.proposal_modes+1)
        for term in (np.cos(k*np.arange(4096)*2*np.pi/4096), np.sin(k*np.arange(4096)*2*np.pi/4096))]])
    direction /= np.max(np.abs(basis_probe @ direction))
    reference_resolved = bool(start_audit["resolved"] and truth_forward["resolved"]
                              and all(p["forward"]["resolved"] for p in probes)
                              and derivative_change <= args.fd_relative_tolerance)
    report = dict(status="running", start_checkpoint=start_checkpoint, optimizer_start="identical empty Adam state",
                  start_geometry=start_audit, start_objective=start_objective, canonical_forward=truth_forward,
                  observations=study.artifact(name + "_observations", observations=truth, start_field=start_field),
                  config=asdict(config), fd_probes=probes, fd_relative_change=derivative_change,
                  fd_gradients=gradients, direction=direction, references_resolved=reference_resolved, arms=[])
    no_op_objective, no_op_drift = None, None
    for scale_index, scale in enumerate((0., *args.step_scales_m)):
        label = name + f"_step{scale_index}_{scale:g}"
        # Exact zero-update target: do not introduce a gratuitous proposal refit.
        if scale == 0:
            proposal, motion = start, dict(maximum_requested_motion_m=0., maximum_realized_motion_m=0., maximum_proposal_refit_error_m=0.)
            direct_field, direct_forward = start_field, dict(resolved=start_audit["resolved"])
        else:
            proposal, motion = normal_proposal(start, scale*direction, max(args.bandwidths), max(args.projected_samples))
            direct_field, direct_forward = study.forward(proposal)
        direct_objective = objective(direct_field, truth)
        arm = dict(scale_m=scale, status="running", motion=motion, direct_objective=direct_objective,
                   direct_forward=direct_forward, predicted_change=float(gradients[-1] @ (scale*direction)))
        report["arms"].append(arm)
        if scale and direct_objective >= start_objective:
            arm.update(status="skipped_non_descent", reason="Direct proposal did not improve the fixed observed-data objective.")
            write_json(study.output / (name + ".json"), report)
            continue
        try:
            data = prepare_fit_data(proposal, config)
            branch, branch_optimizer = fork_checkpoint(model, initial, learning_rate=config.learning_rate)
            arm["training_data"] = study.artifact(label + "_training", **data.arrays)
            arm["target_diagnostics"] = data.target_diagnostics
            before = fit_metrics(branch, data, config)
            first = fit_steps(branch, branch_optimizer, data, config, steps=args.warmup_steps, weight=0.)
            second = fit_steps(branch, branch_optimizer, data, config, steps=args.branch_steps, weight=args.eikonal_current)
            arm.update(checkpoint=study.save_checkpoint(label, branch, branch_optimizer), updates=len(first)+len(second),
                       losses=first+second, before_fit=before, after_fit=fit_metrics(branch, data, config))
            actual, response, audit = study.audit(branch, proposal, label)
            if actual is None:
                arm["geometry"] = audit
                raise ValueError("Fitted candidate cannot be converted and solved; checkpoint retained.")
            actual_objective = objective(response, truth)
            drift = study.distance(start, actual)
            if scale == 0:
                no_op_objective, no_op_drift = actual_objective, drift["symmetric_max_m"]
            arm.update(status="completed", geometry=audit, actual_objective=actual_objective,
                       start_to_actual=drift, start_to_proposal=study.distance(start, proposal))
            # Set distances survive the phase change introduced by arc-length
            # refitting. Do not mistake parameter-index subtraction for motion.
            t = start.discretize(max(args.audit_samples)).points
            intended = -signed_distance_to_continuous_curve(t, proposal, tolerance_m=1e-9, initial_samples=512)
            realized = -signed_distance_to_continuous_curve(t, actual, tolerance_m=1e-9, initial_samples=512)
            arm["motion_samples"] = study.artifact(label + "_motion", start_points=t,
                                                   intended_signed_distance_m=intended, realized_signed_distance_m=realized)
            arm["motion_rms_discrepancy_m"] = float(np.sqrt(np.mean((intended-realized)**2)))
            if no_op_objective is None:
                arm["comparison_unavailable"] = "Zero-update round trip failed; no transfer conclusion."
            else:
                arm["comparison"] = transfer_comparison(
                    start_objective=start_objective, direct_objective=direct_objective,
                    actual_objective=actual_objective, no_op_objective=no_op_objective,
                    intended_motion_m=arm["start_to_proposal"]["symmetric_max_m"] if scale else 0.,
                    no_op_drift_m=no_op_drift, predicted_change=arm["predicted_change"],
                    references_resolved=reference_resolved and direct_forward["resolved"] and audit["resolved"]
                        and drift["resolved"] and arm["start_to_proposal"]["resolved"]
                        and report["arms"][0]["status"] == "completed"
                        and report["arms"][0]["geometry"]["resolved"],
                )
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as exc:
            arm.update(status="failed", error=str(exc), traceback=traceback.format_exc())
        write_json(study.output / (name + ".json"), report)
    report["status"] = "failed" if any(a["status"] == "failed" for a in report["arms"]) else "completed"
    report["verified_direct_descent_count"] = sum(reference_resolved and a["scale_m"] > 0 and a["direct_objective"] < start_objective
                                                 and a["direct_forward"]["resolved"] for a in report["arms"])
    if report["verified_direct_descent_count"] == 0 and report["status"] == "completed":
        report.update(status="blocked", reason="No verified direct descent at the requested scales; transfer remains untested.")
        if not reference_resolved:
            report["reason"] = "Unresolved starting geometry, forward reference, or finite-difference gradient; no transfer conclusion."
    write_json(study.output / (name + ".json"), report)
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, default=FROZEN)
    parser.add_argument("--experiments", nargs="+", choices=("conversion", "eikonal", "transfer"), default=["conversion"])
    parser.add_argument("--shapes", nargs="+", choices=("circle", "star"), default=["circle", "star"])
    parser.add_argument("--frozen-policies", nargs="+", choices=("legacy_polygon", "smooth_curve"), default=["smooth_curve"])
    parser.add_argument("--grids", type=int, nargs="+", default=[257, 513])
    parser.add_argument("--projected-samples", type=int, nargs="+", default=[512, 1024])
    parser.add_argument("--bandwidths", type=int, nargs="+", default=[24, 48, 96])
    parser.add_argument("--arclength-dense", type=int, nargs="+", default=[2048, 4096])
    parser.add_argument("--bem-nodes", type=int, nargs="+", default=[256, 512])
    parser.add_argument("--audit-samples", type=int, nargs="+", default=[512, 1024])
    parser.add_argument("--geometry-refinement-m", type=float, default=2e-6)
    parser.add_argument("--geometry-gate-m", type=float, default=2e-4)
    parser.add_argument("--field-refinement", type=float, default=1e-7)
    parser.add_argument("--warmup-steps", type=int, default=50)
    parser.add_argument("--branch-steps", type=int, default=550)
    parser.add_argument("--sample-count", type=int, default=768)
    parser.add_argument("--learning-rate", type=float, default=2e-3)
    parser.add_argument("--eikonal-current", type=float, default=.1)
    parser.add_argument("--proposal-modes", type=int, default=3)
    parser.add_argument("--fd-step-m", type=float, default=2e-5)
    parser.add_argument("--fd-relative-tolerance", type=float, default=.05)
    parser.add_argument("--step-scales-m", type=float, nargs="+", default=[5e-5, 2e-4, 8e-4])
    args = parser.parse_args(argv)
    for name in ("grids", "projected_samples", "bandwidths", "arclength_dense", "bem_nodes", "audit_samples"):
        values = getattr(args, name)
        if len(values) < 2 or values != sorted(set(values)) or min(values) < (1 if name == "bandwidths" else 2):
            parser.error(f"--{name.replace('_', '-')} needs at least two strictly increasing positive resolutions.")
    if min(args.grids) < 17 or min(args.audit_samples) < 16 or min(args.arclength_dense) < 2*max(args.bandwidths)+2:
        parser.error("Insufficient extraction, audit, or arc-length resolution.")
    if min(args.projected_samples) < 2*max(args.bandwidths)+1:
        parser.error("Every projected sample count must resolve the largest bandwidth.")
    if min(args.bem_nodes) < 2*max(args.bandwidths)+2 or any(n % 2 for n in args.bem_nodes):
        parser.error("All fixed BEM node counts must be even and resolve the largest bandwidth.")
    for key in ("geometry_refinement_m", "geometry_gate_m", "field_refinement", "learning_rate", "eikonal_current",
                "fd_step_m", "fd_relative_tolerance"):
        if not np.isfinite(getattr(args, key)) or getattr(args, key) <= 0:
            parser.error(f"{key} must be finite and positive.")
    if args.warmup_steps < 1 or args.branch_steps < 1 or args.sample_count < 1 or args.proposal_modes < 1:
        parser.error("Invalid fitting budget or proposal mode count.")
    if "transfer" in args.experiments and args.proposal_modes > max(args.bandwidths):
        parser.error("Proposal mode count must not exceed the Cartesian bandwidth.")
    if not all(np.isfinite(s) and s > 0 for s in args.step_scales_m) or args.step_scales_m != sorted(set(args.step_scales_m)):
        parser.error("Step scales must be finite, positive, and strictly increasing.")
    for key in ("experiments", "shapes", "frozen_policies"):
        if len(getattr(args, key)) != len(set(getattr(args, key))):
            parser.error(f"Duplicate {key} would overwrite artifacts.")
    if "eikonal" in args.experiments and args.frozen_policies != ["smooth_curve"]:
        parser.error("Eikonal study uses fresh initialization with smooth targets; select only smooth_curve.")
    return args


def write_readme(study):
    def number(value, factor=1.):
        return "unavailable" if value is None else f"{value*factor:.6g}"

    lines = ["# Strict MLP + Method B failure diagnostics", "",
             f"Run started (UTC): {study.summary['started_utc']}", "",
             "Pipeline: MLP zero set → projected contour → Cartesian Fourier fit → arc-length refit → Kress.", "",
             "Completed means the measurements ran, not that their accuracy gates passed. No inverse acceptance was performed.", "",
             "| Scene | Diagnostic | Frozen fitting policy | Execution |", "|---|---|---|---|"]
    lines += [f"| {r['shape']} | {r['experiment']} | {r['frozen_policy']} | {r['status']} |" for r in study.summary["cases"]]
    for row in study.summary["cases"]:
        result = row.get("result", {})
        lines += ["", f"## {row['name']}", ""]
        if "error" in row or "reason" in result:
            lines += [row.get("error", result.get("reason", "")), ""]
        if row["experiment"] == "conversion" and "geometry" in result:
            g = result["geometry"]
            raw = g["raw_reference"].get("raw_zero_set_to_target", {}).get("symmetric_max_m")
            lines += ["| Raw zero set → target, mm | Method B → target, mm | Method B → raw zero set, mm | Anchor measurements resolved |",
                      "|---:|---:|---:|---|",
                      f"| {number(raw, 1000)} | {number(g['target_drift_m'], 1000)} | {number(g['conversion_drift_m'], 1000)} | {g['resolved']} |",
                      "", "Read the one-factor sweep and initial/refit stage errors in the audit JSON. Set-distance errors are not additive."]
        elif row["experiment"] == "eikonal" and "arms" in result:
            lines += ["| Eikonal weight | Execution | Final contour drift, mm | Final field error | Fitting gates all pass | Field reference resolved |",
                      "|---:|---|---:|---:|---|---|"]
            for arm in result["arms"]:
                lines.append(f"| {arm['weight']:g} | {arm['status']} | {number(arm.get('geometry', {}).get('target_drift_m'), 1000)} | "
                             f"{number(arm.get('field_error'))} | {arm.get('fit', {}).get('combined_training_gate', 'unavailable')} | "
                             f"{arm.get('field_reference_resolved', False)} |")
            lines += ["", "Compare the shared warm-up and first-update audits before attributing a final-state difference to Eikonal activation."]
        elif row["experiment"] == "transfer" and "arms" in result:
            lines += ["| Scale, mm | Execution | Predicted ΔJ | Direct ΔJ | Actual ΔJ | No-op drift / intended motion | Resolved descent transferred |",
                      "|---:|---|---:|---:|---:|---:|---|"]
            for arm in result["arms"]:
                c = arm.get("comparison", {})
                direct = arm["direct_objective"]-result["start_objective"]
                actual = None if "actual_objective" not in arm else arm["actual_objective"]-result["start_objective"]
                lines.append(f"| {arm['scale_m']*1000:g} | {arm['status']} | {number(arm['predicted_change'])} | "
                             f"{number(direct)} | {number(actual)} | {number(c.get('no_op_drift_over_intended_motion'))} | "
                             f"{c.get('transfer_descent_observed', False)} |")
            lines += ["", "A negative ΔJ improves the fixed observed-data objective. Transfer descent is separate from fitting and strict inverse acceptance gates."]
    lines += ["", "Unresolved geometry, BEM or finite-difference references prohibit a transfer conclusion. "
              "Read `metrics.json`, per-arm audits and retained failures before adding a takeaway to the result catalogue.", ""]
    (study.output / "README.md").write_text("\n".join(lines))


def main(argv=None):
    args = parse_args(argv)
    for name in ("summary.json", "arrays.npz"):
        if not (args.frozen / name).is_file():
            raise FileNotFoundError(f"Required frozen artifact missing: {args.frozen / name}. Restore it; do not substitute a new run.")
    if args.output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {args.output_dir}")
    frozen = json.loads((args.frozen / "summary.json").read_text())
    args.output_dir.mkdir(parents=True)
    torch.set_num_threads(1)
    study = Study(args, frozen)
    with np.load(args.frozen / "arrays.npz", allow_pickle=False) as arrays:
        for shape in args.shapes:
            case = next(c for c in frozen["cases"] if c["shape"] == shape)
            target = FourierBoundary(np.asarray(case["canonical_cartesian_cosine"]),
                                     np.asarray(case["canonical_cartesian_sine"])).to_parameterization()
            for policy in args.frozen_policies:
                metadata = next(a["model"] for a in case["arms"] if a["distance_target"] == policy)
                for experiment in args.experiments:
                    name = f"{shape}_{policy}_{experiment}"
                    row = dict(shape=shape, frozen_policy=policy, experiment=experiment,
                               name=name, started_utc=utc_now(), status="running")
                    study.summary["cases"].append(row)
                    study.flush()
                    print(f"{name}: starting", flush=True)
                    started = perf_counter()
                    try:
                        model = model_from_metadata(metadata, arrays, prefix=f"{shape}_{policy}_model_")
                        if experiment == "conversion":
                            result = run_conversion(study, target, model, name)
                        elif experiment == "eikonal":
                            result = run_eikonal(study, target, metadata, name)
                        else:
                            result = run_transfer(study, target, model, name)
                        row.update(result=result, status=result["status"])
                    except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as exc:
                        row.update(status="failed", error=str(exc), traceback=traceback.format_exc())
                    row.update(finished_utc=utc_now(), seconds=perf_counter()-started)
                    study.flush()
                    print(f"{name}: {row['status']}", flush=True)
    study.summary.update(status="completed" if all(r["status"] == "completed" for r in study.summary["cases"]) else "incomplete",
                         finished_utc=utc_now())
    study.flush()
    write_readme(study)
    return 0 if study.summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
