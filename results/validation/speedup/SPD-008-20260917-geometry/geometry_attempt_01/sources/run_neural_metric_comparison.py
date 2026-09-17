#!/usr/bin/env python3
"""Bounded F: frozen neural tangent metric versus explicit curve metrics.

No neural training, re-extraction, production inverse change or topology claim.
The independent observations, staged work limits and all hyperparameters are
declared before optimization. Held-out data are used only after every run.
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

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name, "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"solvers"))

import numpy as np
import scipy
import torch

from gpr_bem_kress import KressSolveConfig, Material, solve_kress_tmz_total_field_batch
from gpr_bem_kress.shape_derivative import build_paired_objective_adjoint
from sdf_inverse.curve_updates import (
    RadialFourierCurveState, apply_radial_fourier_update, radial_fourier_displacement_basis,
    radial_fourier_parameterization, radial_fourier_state_curve,
)
from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from sdf_inverse.neural import SmoothMLPSDF2D
from sdf_inverse.neural_metric import build_frozen_curve_metric, radial_chart_directions
from sdf_to_ordered_boundary.artifacts import write_metrics_csv, write_npz, write_strict_json


EPS0, MU0 = 8.8541878128e-12, 1.25663706212e-6
BOUNDS = ((.3, .3), (.7, .7))
INITIAL_CENTER, INITIAL_RADIUS = (.485, .510), .045
EXTERIOR, INTERIOR = Material(6.), Material(3.)
SEEDS = (0, 1, 2)


@dataclass(frozen=True)
class Stage:
    frequencies_ghz: tuple[float, ...]
    num_nodes: int
    active_mode: int
    maximum_accepted_steps: int


@dataclass(frozen=True)
class ComparisonConfig:
    stages: tuple[Stage, ...] = (Stage((.5,), 64, 3, 5), Stage((.5, 1.5), 128, 5, 10))
    forward_solve_cap: int = 160
    maximum_normal_step_m: float = .002
    armijo_coefficient: float = 1e-4
    backtrack_factor: float = .5
    maximum_backtracks: int = 12
    loss_tolerance: float = 1e-4
    gradient_tolerance: float = 1e-5
    eigenvalue_floor: float = 1e-3
    sobolev_angular_length: float = .35
    metric_nodes: int = 128
    normal_audit_nodes: int = 512
    observation_tolerance: float = 1e-8
    observation_maximum_nodes: int = 512
    circle_reference_maximum_mode: int = 64
    circle_reference_audit_mode: int = 72
    circle_reference_tolerance: float = 1e-12
    final_audit_nodes: tuple[int, ...] = (128, 256, 512)
    final_self_refinement_tolerance: float = 1e-6
    holdout_frequencies_ghz: tuple[float, ...] = (2.,)


class ForwardBudgetExceeded(RuntimeError):
    pass


def _initial_state():
    cosine = np.zeros(6)
    cosine[0] = INITIAL_RADIUS
    return RadialFourierCurveState(np.asarray(INITIAL_CENTER), cosine, np.zeros(6), "metric-canonical")


def _truth_state(name):
    cosine = np.zeros(6)
    cosine[0] = .05
    if name == "star":
        cosine[5] = .0125
    elif name != "circle":
        raise ValueError("Only the predeclared circle and star cases are supported.")
    return RadialFourierCurveState(np.asarray([.5, .5]), cosine, np.zeros(6), "metric-truth")


def _state_vector(state):
    result = [state.radius_cosine_coefficients[0], *state.center]
    for mode in range(2, 6):
        result.extend((state.radius_cosine_coefficients[mode], state.radius_sine_coefficients[mode]))
    return np.asarray(result)


def _acquisition(*, heldout=False):
    index = np.arange(12)
    angle = 2*np.pi*(index + (.5 if heldout else 0.0))/12
    sources = .5 + .30*np.column_stack((np.cos(angle), np.sin(angle)))
    receivers = .5 + .30*np.column_stack((np.cos(angle+.10), np.sin(angle+.10)))
    strengths = 1e-6*(1+.1*np.cos(index)) * np.exp(.2j*index)
    return sources, receivers, strengths


def _geometry_config(nodes):
    return OrderedSDFGeometryConfig(bounds=BOUNDS, num_nodes=nodes, bandwidth=6,
                                    projected_samples=64, validation_resolution=512)


def _forward(curve, frequencies_ghz, acquisition, work, *, cap=None):
    if cap is not None and work["forward_solves"] + len(frequencies_ghz) > cap:
        raise ForwardBudgetExceeded("The fixed per-frequency forward-solve budget is exhausted.")
    sources, receivers, strengths = acquisition
    results = []
    for frequency in frequencies_ghz:
        started = perf_counter()
        work["forward_solves"] += 1
        try:
            results.append(solve_kress_tmz_total_field_batch(
                curve, sources, receivers, 2*np.pi*frequency*1e9, strengths,
                exterior=EXTERIOR, interior=INTERIOR, eps0=EPS0, mu0=MU0,
                config=KressSolveConfig(),
            ))
        finally:
            work["forward_seconds"] += perf_counter()-started
    return tuple(results)


def _prediction(forwards):
    return np.column_stack([np.diag(value.scattered_receiver) for value in forwards])


def _transform(observed):
    # Same fixed observation-based normalization as normalized_complex_residual.
    norms = np.linalg.norm(observed, axis=0)
    reference = max(float(np.max(norms)), float(np.linalg.norm(observed))/np.sqrt(observed.shape[1]), 1.)
    scales = np.maximum(norms, 1e-12*reference)
    diagonal = np.broadcast_to(1/scales, observed.shape).ravel()
    return np.diag(np.r_[diagonal, diagonal])


def _loss(prediction, observed, transform):
    delta = prediction-observed
    real = transform @ np.r_[delta.real.ravel(), delta.imag.ravel()]
    loss = float(.5*np.dot(real, real))
    if not np.isfinite(loss):
        raise FloatingPointError("Non-finite normalized objective.")
    return loss


def _relative(prediction, observed):
    return float(np.linalg.norm(prediction-observed)/max(np.linalg.norm(observed), np.finfo(float).tiny))


def _independent_observations(name, frequencies_ghz, acquisition, config):
    started = perf_counter()
    sources, receivers, strengths = acquisition
    if name == "circle":
        from gpr_bem_ref import penetrable_cylinder_scattering_coefficient_ratio
        from scipy.special import hankel1
        def evaluate(maximum_mode):
            modes = np.arange(-maximum_mode, maximum_mode+1)
            source_delta, receiver_delta = sources-.5, receivers-.5
            phase = np.arctan2(receiver_delta[:, 1], receiver_delta[:, 0])-np.arctan2(source_delta[:, 1], source_delta[:, 0])
            columns = []
            for frequency in frequencies_ghz:
                ke = 2*np.pi*frequency*1e9*np.sqrt(EPS0*MU0*6)
                ki = 2*np.pi*frequency*1e9*np.sqrt(EPS0*MU0*3)
                ratio = penetrable_cylinder_scattering_coefficient_ratio(modes, ke, ki, .05)
                columns.append(strengths*.25j*np.sum(
                    hankel1(modes[None, :], ke*np.linalg.norm(source_delta, axis=1)[:, None])
                    * hankel1(modes[None, :], ke*np.linalg.norm(receiver_delta, axis=1)[:, None])
                    * ratio[None, :] * np.exp(1j*phase[:, None]*modes[None, :]), axis=1))
            return np.column_stack(columns)
        result = evaluate(config.circle_reference_maximum_mode)
        audit = evaluate(config.circle_reference_audit_mode)
        discrepancy = _relative(result, audit)
        if discrepancy > config.circle_reference_tolerance:
            raise RuntimeError("The fixed-mode Mie observations failed independent mode refinement.")
        information = dict(kind="independent_fixed_mode_Mie_circle", solves=0,
            evaluations=2*len(frequencies_ghz), maximum_mode=config.circle_reference_maximum_mode,
            audit_maximum_mode=config.circle_reference_audit_mode,
            refinement_relative_difference=discrepancy, refinement_tolerance=config.circle_reference_tolerance)
    else:
        from nystrom_ref import build_curve, solve_transmission
        producer = radial_fourier_parameterization(_truth_state(name))
        def evaluate(t):
            values = producer.evaluate(t)
            return values.points, values.first_derivatives
        previous, history, solves = None, [], 0
        count = 128
        while count <= config.observation_maximum_nodes:
            native = build_curve(evaluate, count, "independent_metric_star")
            columns = []
            for frequency in frequencies_ghz:
                omega = 2*np.pi*frequency*1e9
                solution = solve_transmission(native, sources, receivers,
                    complex(omega*np.sqrt(EPS0*MU0*6)), complex(omega*np.sqrt(EPS0*MU0*3)))
                columns.append(np.diag(solution.scattered)*strengths)
                solves += 1
            result = np.column_stack(columns)
            if previous is not None:
                error = _relative(result, previous)
                history.append(dict(coarse_nodes=count//2, fine_nodes=count, relative_difference=error))
                if error <= config.observation_tolerance:
                    break
            previous = result
            count *= 2
        else:
            raise RuntimeError("The independent star observations failed the predeclared refinement gate.")
        information = dict(kind="independent_nystrom_star", solves=solves, evaluations=0,
                           final_nodes=count, refinement=history)
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("Independent observations are non-finite.")
    result.setflags(write=False)
    information["seconds"] = float(perf_counter()-started)
    return result, information


def _work():
    return dict(forward_solves=0, forward_seconds=0.0, adjoint_solves=0,
                gradient_evaluations=0, directional_operator_assemblies=0,
                gradient_seconds=0.0, geometry_seconds=0.0,
                invalid_geometry_trials=0, numerical_trials=0)


def _normal_cap(state, direction, active_mode, config):
    parameters = 2*np.pi*np.arange(config.normal_audit_nodes)/config.normal_audit_nodes
    evaluation = radial_fourier_parameterization(state).evaluate(parameters)
    tangent = evaluation.first_derivatives
    tangent = tangent/np.linalg.norm(tangent, axis=1)[:, None]
    normals = np.column_stack((tangent[:, 1], -tangent[:, 0]))
    basis = radial_fourier_displacement_basis(parameters, maximum_mode=active_mode)
    velocity = np.einsum("npd,p->nd", basis, direction)
    maximum = float(np.max(np.abs(np.einsum("nd,nd->n", normals, velocity))))
    factor = min(1.0, config.maximum_normal_step_m/maximum) if maximum else 1.0
    return direction*factor, maximum*factor


def _run_arm(name, kind, seed, observed, acquisition, config):
    started = perf_counter()
    state = _initial_state()
    curve = radial_fourier_state_curve(state, geometry_config=_geometry_config(config.metric_nodes))
    model_started = perf_counter()
    model = (SmoothMLPSDF2D(bounds=BOUNDS, hidden_features=64, hidden_layers=2,
        geometric_center=INITIAL_CENTER, geometric_radius=INITIAL_RADIUS, seed=seed,
        dtype=torch.float64) if kind == "neural" else None)
    model_seconds = float(perf_counter()-model_started) if model is not None else 0.0
    metric = build_frozen_curve_metric(curve, kind=kind, model=model,
        eigenvalue_floor=config.eigenvalue_floor, sobolev_angular_length=config.sobolev_angular_length)
    del model  # No representation queries, refits or training during reconstruction.
    setup_seconds = float(perf_counter()-started)
    work, history, stages = _work(), [], []
    converged, final_reason, accepted_total = False, "not_started", 0
    final_forward = None
    for stage_index, stage in enumerate(config.stages):
        geometry_config = _geometry_config(stage.num_nodes)
        curve = radial_fourier_state_curve(state, geometry_config=geometry_config)
        selected_observations = observed[:, :len(stage.frequencies_ghz)]
        transform = _transform(selected_observations)
        indices = np.arange(selected_observations.shape[0])
        stage_reason, accepted = "iteration_budget", 0
        try:
            forwards = _forward(curve, stage.frequencies_ghz, acquisition, work, cap=config.forward_solve_cap)
        except ForwardBudgetExceeded:
            final_reason = "forward_budget"
            break
        loss = _loss(_prediction(forwards), selected_observations, transform)
        history.append(dict(stage=stage_index, accepted_step=accepted_total, stage_accepted_step=0,
            loss=loss, relative_l2=_relative(_prediction(forwards), selected_observations),
            forward_solves=work["forward_solves"], gradient_norm=None, maximum_normal_step_m=0.,
            backtracks=0, coefficients=_state_vector(state).tolist()))
        if loss <= config.loss_tolerance:
            stage_reason = "loss_tolerance"
        for _ in range(stage.maximum_accepted_steps):
            if stage_reason == "loss_tolerance":
                break
            gradient_started = perf_counter()
            context = build_paired_objective_adjoint(forwards, selected_observations, indices, indices,
                                                     residual_transform=transform)
            directions = radial_chart_directions(curve.parameters, stage.active_mode)
            gradient = np.asarray([context.directional_derivative(direction) for direction in directions])
            work["adjoint_solves"] += len(forwards)
            work["gradient_evaluations"] += 1
            work["directional_operator_assemblies"] += len(directions)*len(forwards)
            work["gradient_seconds"] += perf_counter()-gradient_started
            gradient_norm = metric.covector_norm(gradient, maximum_mode=stage.active_mode, curve=curve)
            if gradient_norm <= config.gradient_tolerance:
                stage_reason = "gradient_tolerance"
                break
            direction = metric.descent_direction(gradient, maximum_mode=stage.active_mode)
            direction, capped_maximum = _normal_cap(state, direction, stage.active_mode, config)
            slope = float(np.dot(gradient, direction))
            if not np.isfinite(slope) or slope >= 0:
                stage_reason = "non_descent_direction"
                break
            accepted_trial = False
            for backtrack in range(config.maximum_backtracks+1):
                fraction = config.backtrack_factor**backtrack
                geometry_started = perf_counter()
                try:
                    update = apply_radial_fourier_update(state, fraction*direction,
                        maximum_mode=stage.active_mode, geometry_config=geometry_config, full_validation=False)
                except OrderedSDFGeometryError:
                    work["invalid_geometry_trials"] += 1
                    continue
                finally:
                    work["geometry_seconds"] += perf_counter()-geometry_started
                try:
                    trial_forward = _forward(update.curve, stage.frequencies_ghz, acquisition,
                                             work, cap=config.forward_solve_cap)
                    trial_loss = _loss(_prediction(trial_forward), selected_observations, transform)
                except ForwardBudgetExceeded:
                    stage_reason = "forward_budget"
                    break
                except (FloatingPointError, np.linalg.LinAlgError):
                    work["numerical_trials"] += 1
                    continue
                if trial_loss > loss + config.armijo_coefficient*fraction*slope:
                    continue
                geometry_started = perf_counter()
                try:
                    validated = radial_fourier_state_curve(update.state, geometry_config=geometry_config)
                except OrderedSDFGeometryError:
                    work["invalid_geometry_trials"] += 1
                    continue
                finally:
                    work["geometry_seconds"] += perf_counter()-geometry_started
                np.testing.assert_array_equal(validated.points, update.curve.points)
                state, curve, forwards, loss = update.state, validated, trial_forward, trial_loss
                accepted += 1
                accepted_total += 1
                history.append(dict(stage=stage_index, accepted_step=accepted_total, stage_accepted_step=accepted,
                    loss=loss, relative_l2=_relative(_prediction(forwards), selected_observations),
                    forward_solves=work["forward_solves"], gradient_norm=gradient_norm,
                    maximum_normal_step_m=fraction*capped_maximum, backtracks=backtrack,
                    coefficients=_state_vector(state).tolist()))
                accepted_trial = True
                if loss <= config.loss_tolerance:
                    stage_reason = "loss_tolerance"
                break
            if not accepted_trial:
                if stage_reason != "forward_budget":
                    stage_reason = "line_search_failed"
                break
        final_forward, final_reason = forwards, stage_reason
        stages.append(dict(index=stage_index, configuration=asdict(stage), accepted_steps=accepted,
            stop_reason=stage_reason, final_loss=loss, metric=metric.active_diagnostics(stage.active_mode)))
        converged = stage_index == len(config.stages)-1 and stage_reason in ("loss_tolerance", "gradient_tolerance")
        if stage_reason in ("forward_budget", "non_descent_direction"):
            break
    result = dict(case=name, kind=kind, seed=seed, converged=converged, stop_reason=final_reason,
        accepted_steps=accepted_total, stages=stages, history=history,
        initial_coefficients=_state_vector(_initial_state()).tolist(), final_coefficients=_state_vector(state).tolist(),
        metric=dict(metric.diagnostics), model_construction_seconds=model_seconds,
        setup_seconds=setup_seconds, optimization_work=work,
        reconstruction_seconds=float(perf_counter()-started),
        model_training_steps=0, model_queries_after_initialization=0,
        final_stage_relative_l2=None if final_forward is None else _relative(_prediction(final_forward), observed[:, :len(final_forward)]),
    )
    metric_arrays = dict(mass_matrix=metric.mass_matrix)
    initial_curve = radial_fourier_parameterization(_initial_state()).discretize(config.metric_nodes, require_even=True)
    basis = radial_fourier_displacement_basis(initial_curve.parameters, maximum_mode=5)
    metric_arrays.update(initial_normal_basis=np.einsum("npd,nd->np", basis, initial_curve.normals),
                         initial_arc_weights=initial_curve.arc_length_weights,
                         initial_points=initial_curve.points)
    if metric.normal_feature_covariance is not None:
        metric_arrays["normal_feature_covariance"] = metric.normal_feature_covariance
    for stage in config.stages:
        coefficient, whitened, _ = metric.active_matrices(stage.active_mode)
        metric_arrays[f"K{stage.active_mode}_coefficient_metric"] = coefficient
        metric_arrays[f"K{stage.active_mode}_whitened_metric"] = whitened
    return state, result, metric_arrays


def _qualify(state, truth, observed, holdout, acquisition, holdout_acquisition, config):
    started = perf_counter()
    work, rows, previous = _work(), [], None
    for nodes in config.final_audit_nodes:
        curve = radial_fourier_state_curve(state, geometry_config=_geometry_config(nodes))
        prediction = _prediction(_forward(curve, config.stages[-1].frequencies_ghz, acquisition, work))
        rows.append(dict(num_nodes=nodes, training_relative_l2=_relative(prediction, observed),
            previous_node_relative_difference=None if previous is None else _relative(prediction, previous)))
        previous = prediction
    heldout_rows, heldout_previous = [], None
    for nodes in config.final_audit_nodes[-2:]:
        curve = radial_fourier_state_curve(state, geometry_config=_geometry_config(nodes))
        prediction = _prediction(_forward(curve, config.holdout_frequencies_ghz, holdout_acquisition, work))
        heldout_rows.append(dict(num_nodes=nodes, holdout_relative_l2=_relative(prediction, holdout),
            previous_node_relative_difference=None if heldout_previous is None else _relative(prediction, heldout_previous)))
        heldout_previous = prediction
    parameters = 2*np.pi*np.arange(2048)/2048
    points = radial_fourier_parameterization(state).evaluate(parameters).points
    target = radial_fourier_parameterization(truth).evaluate(parameters).points
    error = np.linalg.norm(points-target, axis=1)
    training_qualified = rows[-1]["previous_node_relative_difference"] is not None and rows[-1]["previous_node_relative_difference"] <= config.final_self_refinement_tolerance
    heldout_qualified = heldout_rows[-1]["previous_node_relative_difference"] is not None and heldout_rows[-1]["previous_node_relative_difference"] <= config.final_self_refinement_tolerance
    return dict(physical_refinement=rows, heldout_refinement=heldout_rows,
        physics_qualified=bool(training_qualified and heldout_qualified),
        training_physics_qualified=bool(training_qualified), heldout_physics_qualified=bool(heldout_qualified),
        self_refinement_tolerance=config.final_self_refinement_tolerance,
        correspondence_rms_m=float(np.sqrt(np.mean(error**2))), correspondence_maximum_m=float(np.max(error)),
        coefficient_error_m=(_state_vector(state)-_state_vector(truth)).tolist(),
        qualification_work=work, seconds=float(perf_counter()-started))


def _provenance():
    paths = [Path(__file__)] + [ROOT/"solvers"/"sdf_inverse"/name for name in (
        "__init__.py", "neural_metric.py", "neural.py", "curve_updates.py", "geometry.py")]
    for package in ("gpr_bem_kress", "ordered_boundary", "periodic_kress", "sdf_to_ordered_boundary", "gpr_bem_ref", "nystrom_ref"):
        paths.extend(sorted((ROOT/"solvers"/package).glob("*.py")))
    return dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        dirty_status=subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        source_hash_scope="Forward/geometry/reference packages plus explicitly used inverse modules; unrelated concurrent inverse experiments excluded.",
        source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})


def _summary(output, manifest):
    lines = ["# Frozen neural tangent metric comparison", "",
        "All arms reconstruct an explicit, gauge-fixed K5 radial Fourier curve with the verified full Kress objective derivative.",
        "The neural arms use frozen random-feature metrics from the wrong exact-circle initialization: 65 active output-head columns, not learned hidden-network or direct SDF optimization.",
        "No representation was trained, extracted or synchronized during reconstruction. Losses across frequency stages are different objectives.", "",
        "| Case | Metric | Accepted | Stop reason | Physics qualified | Refined training error | Held-out error | Geometry RMS (mm) | Forward solves | Reconstruction (s) |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|"]
    for result in manifest["runs"]:
        qualification = result["qualification"]
        label = result["kind"] + ("_seed"+str(result["seed"]) if result["seed"] is not None else "")
        lines.append(f"| {result['case']} | {label} | {result['accepted_steps']} | {result['stop_reason']} | {qualification['physics_qualified']} | "
            f"{qualification['physical_refinement'][-1]['training_relative_l2']:.4g} | "
            f"{qualification['heldout_refinement'][-1]['holdout_relative_l2']:.4g} | "
            f"{1e3*qualification['correspondence_rms_m']:.3f} | {result['optimization_work']['forward_solves']} | {result['reconstruction_seconds']:.2f} |")
    lines += ["", "Iteration/forward-budget exits and line-search failures are not reported as convergence.",
              "Physical refinement and held-out evaluation costs are separate from reconstruction; initial model/metric setup is charged to every run.",
              "The cap is 160 total frequency-specific forward calls per run, not 160 calls for each frequency. Adjoint/operator costs are separately counted.",
              "The explicit Sobolev length .35 is a predeclared moderate smoother. Beating it would not separate neural coupling from stronger smoothing; that needs an additional spectral-matched explicit control.",
              "The chart is fixed, finite-dimensional and star-shaped. This experiment does not test topology changes or prove an advantage for signed-distance values."]
    (output/"summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args(argv)
    output = options.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Output must be new or empty; prior evidence is never overwritten.")
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    config = ComparisonConfig()
    started = perf_counter()
    acquisition, heldout_acquisition = _acquisition(), _acquisition(heldout=True)
    manifest = dict(schema="frozen-neural-tangent-metric-v1", created_utc=datetime.now(timezone.utc).isoformat(),
        command=shlex.join([sys.executable, str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]),
        provenance=_provenance(), configuration=asdict(config), seeds=list(SEEDS),
        physics=dict(exterior_epsr=6., interior_epsr=3., eps0=EPS0, mu0=MU0, regularizer="R=0"),
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, torch=torch.__version__,
            threads={key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}),
        observations={}, runs=[], completed=False, status="generating_observations")
    write_strict_json(output/"metrics.json", manifest)
    arrays, pending = {}, []
    # Freeze both observation datasets before any metric/optimizer is evaluated.
    for name in ("circle", "star"):
        print(f"F immutable observations: {name}", flush=True)
        observed, information = _independent_observations(name, config.stages[-1].frequencies_ghz, acquisition, config)
        heldout, heldout_information = _independent_observations(name, config.holdout_frequencies_ghz, heldout_acquisition, config)
        manifest["observations"][name] = dict(training=information, heldout=heldout_information,
                                            truth_coefficients=_state_vector(_truth_state(name)).tolist())
        arrays[name+"_observed"], arrays[name+"_heldout"] = observed, heldout
    for label, values in (("training", acquisition), ("heldout", heldout_acquisition)):
        for field, value in zip(("sources", "receivers", "strengths"), values):
            arrays[label+"_"+field] = value
    write_npz(output/"arrays.npz", **arrays)
    manifest["status"] = "observations_frozen_before_optimization"
    write_strict_json(output/"metrics.json", manifest)
    for name in ("circle", "star"):
        for kind, seed in (("identity", None), ("sobolev", None), *(("neural", seed) for seed in SEEDS)):
            print(f"F reconstruction: {name}, {kind}, seed={seed}", flush=True)
            state, result, metric_arrays = _run_arm(name, kind, seed, arrays[name+"_observed"], acquisition, config)
            label = f"{name}_{kind}_{seed}"
            arrays.update({label+"_"+key: value for key, value in metric_arrays.items()})
            manifest["runs"].append(result)
            pending.append((state, result))
            manifest["status"] = "reconstructing"
            write_npz(output/"arrays.npz", **arrays)
            write_strict_json(output/"metrics.json", manifest)
    # Only now inspect held-out prediction errors. They never select a metric.
    for state, result in pending:
        name = result["case"]
        result["qualification"] = _qualify(state, _truth_state(name), arrays[name+"_observed"],
            arrays[name+"_heldout"], acquisition, heldout_acquisition, config)
        result["requested_reconstruction_completed"] = bool(result["converged"] and result["qualification"]["physics_qualified"])
        manifest["status"] = "qualifying_without_tuning"
        write_strict_json(output/"metrics.json", manifest)
    manifest["completed"] = True
    manifest["status"] = "completed"
    manifest["total_seconds"] = float(perf_counter()-started)
    write_strict_json(output/"metrics.json", manifest)
    write_npz(output/"arrays.npz", **arrays)
    rows = []
    for result in manifest["runs"]:
        for iteration in result["history"]:
            rows.append(dict(case=result["case"], kind=result["kind"], seed=result["seed"], **iteration))
    write_metrics_csv(output/"trajectories.csv", rows)
    _summary(output, manifest)
    print(f"F complete: {output}, {manifest['total_seconds']:.2f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
