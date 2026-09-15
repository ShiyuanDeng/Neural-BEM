#!/usr/bin/env python3
"""Run the post-iteration-01 topology challenge cases in either Fourier chart.

``--chart radial`` is the original radial-Fourier suite, unchanged.  ``--chart
cartesian`` runs the same three cases, observations, oracle, schedules and
budgets with every accepted component held as a polar-angle Cartesian Fourier
curve, gauge-fixed after every retraction.  Only the chart differs, so the two
bundles compare directly.

This is an experiment driver, not a unit-test shortcut.  It generates fresh
observations, runs the inverse without using the truth geometry for proposals,
checks every topology transition with the production and refined Kress
objectives, and writes one MP4 plus machine-readable evidence per case.

The two genuine split cases use a conservative replace-one-by-two proposal:
an empty-background TD seeds a temporary first component, a current-domain TD
seeds the second, and the replacement is accepted only if it improves on the
current one-component state at both boundary resolutions.  This is deliberately
reported as ``background_td_replacement`` rather than pretending that the
iteration-01 additive TD can remove material from an enclosing component.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime
import itertools
import json
import math
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "solvers"))

import run_radial_fourier_topology_inverse as iteration01  # noqa: E402
from ordered_boundary import (  # noqa: E402
    OrderedBoundary2D,
    PeriodicParameterization2D,
    circle,
    ellipse,
    star,
)
from sdf_bem_multicomponent import (  # noqa: E402
    predict_multicomponent_kress_paired_boundary_response,
)
from sdf_inverse import (  # noqa: E402
    CartesianFourierCurveState,
    ComplexScatteredData,
    MultiRadialFDResult,
    MultiRadialFourierState,
    ParameterFDConfig,
    RadialFourierCurveState,
    build_td_raster,
    circle_radial_fourier_state,
    evaluate_birth_ladder,
    evaluate_multiradial_objective,
    normalized_complex_residual,
    run_multiradial_fd_inverse,
)
from sdf_inverse.topology_controller import (  # noqa: E402
    circle_component, component_parameterization, state_in_chart,
)


CASE_NAMES = (
    "far-circle",
    "large-split",
    "ellipse-star",
)
CHARTS = ("radial", "cartesian")
FREQUENCIES_HZ = np.asarray((0.50e9, 1.50e9, 2.50e9), dtype=np.float64)
TRUTH_CIRCLE_CENTERS = np.asarray(((0.43, 0.50), (0.57, 0.50)), dtype=np.float64)
TRUTH_CIRCLE_RADII = np.asarray((0.035, 0.035), dtype=np.float64)


@dataclass(frozen=True)
class RunProfile:
    name: str
    production_nodes: int
    refined_nodes: int
    oracle_nodes: int
    production_raster: int
    refined_raster: int
    pre_iterations: int
    single_seed_iterations: int
    post_iterations: int
    mode_iterations: int
    frequency_iterations: int


@dataclass(frozen=True)
class CaseSpec:
    name: str
    title: str
    proposal_policy: str
    initial_state: MultiRadialFourierState
    truth_curves: tuple[PeriodicParameterization2D, ...]
    training_indices: tuple[int, ...]
    mode_schedule: tuple[int, ...]
    geometry_tolerance_m: float
    training_tolerance: float
    holdout_tolerance: float
    chart: str = "radial"


@dataclass
class VideoTrace:
    states: list[MultiRadialFourierState]
    labels: list[str]
    losses: list[float]

    def append(self, state: MultiRadialFourierState, label: str, loss: float) -> None:
        self.states.append(state)
        self.labels.append(str(label))
        self.losses.append(float(loss))


def _profile(name: str) -> RunProfile:
    if name == "quick":
        return RunProfile(name, 48, 64, 128, 61, 91, 2, 2, 2, 2, 2)
    if name == "full":
        return RunProfile(name, 64, 128, 256, 121, 241, 15, 10, 15, 15, 30)
    raise ValueError(f"Unknown profile: {name}")


def _radial_state(
    center: tuple[float, float],
    mean_radius: float,
    maximum_mode: int,
    component_id: str,
) -> RadialFourierCurveState:
    cosine = np.zeros(maximum_mode + 1, dtype=np.float64)
    sine = np.zeros(maximum_mode + 1, dtype=np.float64)
    cosine[0] = mean_radius
    return RadialFourierCurveState(
        center=np.asarray(center, dtype=np.float64),
        radius_cosine_coefficients=cosine,
        radius_sine_coefficients=sine,
        component_id=component_id,
        name=f"challenge_{component_id}",
        source_identifier=component_id,
    )


def _case_spec(name: str, chart: str = "radial") -> CaseSpec:
    """The case in the requested chart.

    Only the initial state changes: a radial component of band ``K`` is exactly
    a polar-angle Cartesian component of band ``K + 1``, so both charts start
    from the same geometry, see the same observations and are held to the same
    declared tolerances.
    """
    spec = _radial_case_spec(name)
    if chart == "radial":
        return spec
    return replace(spec, chart=chart,
                   initial_state=state_in_chart(spec.initial_state, chart))


def _radial_case_spec(name: str) -> CaseSpec:
    circle_truth = tuple(
        circle(tuple(center), float(radius), component_id=component_id)
        for center, radius, component_id in zip(
            TRUTH_CIRCLE_CENTERS,
            TRUTH_CIRCLE_RADII,
            ("truth_A", "truth_B"),
        )
    )
    if name == "far-circle":
        initial = MultiRadialFourierState(
            (circle_radial_fourier_state((0.50, 0.66), 0.035, "far_initial"),)
        )
        return CaseSpec(
            name=name,
            title="Far wrong circle to two circles",
            proposal_policy="background_td_replacement",
            initial_state=initial,
            truth_curves=circle_truth,
            training_indices=(0,),
            mode_schedule=(),
            geometry_tolerance_m=0.005,
            training_tolerance=0.02,
            holdout_tolerance=0.05,
        )
    if name == "large-split":
        initial = MultiRadialFourierState(
            (circle_radial_fourier_state((0.50, 0.50), 0.115, "large_initial"),)
        )
        return CaseSpec(
            name=name,
            title="Large enclosing circle split to two circles",
            proposal_policy="background_td_replacement",
            initial_state=initial,
            truth_curves=circle_truth,
            training_indices=(0,),
            mode_schedule=(),
            geometry_tolerance_m=0.005,
            training_tolerance=0.02,
            holdout_tolerance=0.05,
        )
    if name == "ellipse-star":
        truth = (
            ellipse(
                (0.445, 0.445),
                0.045,
                0.026,
                rotation=0.55,
                component_id="truth_ellipse",
            ),
            star(
                (0.555, 0.555),
                0.036,
                0.24,
                5,
                rotation=0.20,
                component_id="truth_star",
            ),
        )
        initial = MultiRadialFourierState(
            (circle_radial_fourier_state((0.50, 0.50), 0.050, "middle_initial"),)
        )
        return CaseSpec(
            name=name,
            title="Middle circle split to diagonal ellipse and star",
            proposal_policy="background_td_replacement",
            initial_state=initial,
            truth_curves=truth,
            training_indices=(0, 1),
            mode_schedule=(2, 5),
            geometry_tolerance_m=0.012,
            training_tolerance=0.08,
            holdout_tolerance=0.12,
        )
    raise ValueError(f"Unknown case: {name}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        choices=("all",) + CASE_NAMES,
        default="all",
        help="Challenge case to execute.",
    )
    parser.add_argument(
        "--profile",
        choices=("quick", "full"),
        default="full",
        help="Quick is a wiring smoke run; only full produces qualification claims.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Suite result root (default: a new timestamped directory).",
    )
    parser.add_argument(
        "--chart",
        choices=CHARTS,
        default="radial",
        help="Chart every accepted component is held in.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved cases and numerical budgets without solving.",
    )
    return parser.parse_args()


def _output_root(args: argparse.Namespace) -> Path:
    if args.output is not None:
        return args.output.resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    family = "cartesian_fourier" if args.chart == "cartesian" else "radial_fourier"
    return (
        ROOT
        / "results"
        / "inverse"
        / family
        / "topology_challenges"
        / f"challenge-suite-{stamp}"
    )


def _sample_component(component, count: int = 720) -> np.ndarray:
    """Sample either chart's component on its own uniform parameter."""
    return np.asarray(component_parameterization(component).discretize(count).points)


def _truth_points(spec: CaseSpec, count: int = 720) -> tuple[np.ndarray, ...]:
    return tuple(np.asarray(curve.discretize(count, require_even=True).points) for curve in spec.truth_curves)


def _promote(state: MultiRadialFourierState, maximum_mode: int) -> MultiRadialFourierState:
    """Open coefficients up to ``maximum_mode`` without moving the geometry.

    The schedule is declared in radial modes.  A Cartesian component carries
    the same shape content one band higher, so it is padded to
    ``maximum_mode + 1``: the two charts then reach the same shape space at the
    same schedule entry, which is what makes a continuation stage comparable
    across charts rather than a mode behind.
    """
    promoted = []
    for component in state.components:
        if isinstance(component, CartesianFourierCurveState):
            component_mode = max(maximum_mode + 1, component.maximum_mode)
            cosine = np.zeros((component_mode + 1, 2), dtype=np.float64)
            sine = np.zeros_like(cosine)
            cosine[: component.maximum_mode + 1] = component.cosine_coefficients
            sine[: component.maximum_mode + 1] = component.sine_coefficients
            promoted.append(
                CartesianFourierCurveState(
                    cosine,
                    sine,
                    component.component_id,
                    name=component.name,
                    source_identifier=component.source_identifier,
                )
            )
            continue
        component_mode = max(maximum_mode, component.maximum_mode)
        cosine = np.zeros(component_mode + 1, dtype=np.float64)
        sine = np.zeros(component_mode + 1, dtype=np.float64)
        cosine[: component.maximum_mode + 1] = component.radius_cosine_coefficients
        sine[: component.maximum_mode + 1] = component.radius_sine_coefficients
        promoted.append(
            RadialFourierCurveState(
                center=component.center,
                radius_cosine_coefficients=cosine,
                radius_sine_coefficients=sine,
                component_id=component.component_id,
                name=component.name,
                source_identifier=component.source_identifier,
            )
        )
    return MultiRadialFourierState(tuple(promoted))


def _optimizer_config(state: MultiRadialFourierState, iterations: int) -> ParameterFDConfig:
    maximum_steps = []
    fd_steps = []
    for name in state.parameter_names:
        fd_steps.append(1.0e-4)
        # The Cartesian names carry the same three roles: mode zero translates,
        # mode one scales, and the rest are shape. The shape bound is halved
        # because a radial mode-m amplitude appears in this chart as two
        # coefficient pairs of *half* that amplitude, so half the bound is what
        # reproduces the radial trust region rather than doubling it.
        if name.endswith("radius_m") or ".cos_1_" in name or ".sin_1_" in name:
            maximum_steps.append(0.012)
        elif ".center_" in name or ".cos_0_" in name:
            maximum_steps.append(0.025)
        elif ".cos_" in name or ".sin_" in name:
            maximum_steps.append(0.003)
        else:
            maximum_steps.append(0.006)
    return ParameterFDConfig(
        max_iterations=iterations,
        finite_difference_steps=np.asarray(fd_steps),
        max_steps=np.asarray(maximum_steps),
        initial_damping=1.0e-3,
        damping_increase=10.0,
        damping_decrease=0.3,
        max_damping_trials=6,
        max_backtracks=8,
        gradient_tolerance=1.0e-8,
        loss_tolerance=1.0e-12,
        relative_step_tolerance=1.0e-8,
        max_parameters=max(32, state.parameter_count),
        infeasible_trial_policy="reject",
    )


def _observations(spec: CaseSpec, profile: RunProfile, solve_config) -> tuple[np.ndarray, str]:
    if spec.name in {"far-circle", "large-split"}:
        values = iteration01._oracle_response(
            TRUTH_CIRCLE_CENTERS,
            TRUTH_CIRCLE_RADII,
            FREQUENCIES_HZ,
            component_ids=("truth_A", "truth_B"),
        )
        return values, "independent multicylinder cylindrical-harmonic oracle"
    boundary = OrderedBoundary2D(
        tuple(
            curve.discretize(profile.oracle_nodes, require_even=True)
            for curve in spec.truth_curves
        )
    )
    response = predict_multicomponent_kress_paired_boundary_response(
        boundary,
        iteration01._problem(FREQUENCIES_HZ),
        solve_config=solve_config,
    )
    return (
        response.scattered_response,
        f"independent analytic truth curves discretized at {profile.oracle_nodes} nodes/component",
    )


def _training_data(spec: CaseSpec, observations: np.ndarray) -> ComplexScatteredData:
    indices = np.asarray(spec.training_indices, dtype=np.int64)
    return ComplexScatteredData(
        iteration01._problem(FREQUENCIES_HZ[indices]),
        observations[:, indices],
    )


def _topology_data(observations: np.ndarray) -> ComplexScatteredData:
    """Frozen low-frequency data used for topology and shape continuation."""

    return ComplexScatteredData(
        iteration01._problem(FREQUENCIES_HZ[[0]]),
        observations[:, [0]],
    )


def _empty_loss(data: ComplexScatteredData) -> float:
    residual, _ = normalized_complex_residual(
        np.zeros_like(data.observed_scattered_response),
        data.observed_scattered_response,
        data.frequency_weights,
    )
    return 0.5 * float(np.dot(residual, residual))


def _run_optimizer(
    state: MultiRadialFourierState,
    data: ComplexScatteredData,
    geometry,
    solve_config,
    *,
    iterations: int,
    stage: str,
    chart: str = "radial",
) -> MultiRadialFDResult:
    return run_multiradial_fd_inverse(
        state,
        data,
        geometry,
        solve_config=solve_config,
        config=_optimizer_config(state, iterations),
        cartesian_gauge=chart == "cartesian",
        progress_callback=lambda item: print(
            f"[{stage}] accepted {item.iteration:02d}: "
            f"J={item.loss:.6e}, rel={item.relative_l2_error:.6e}",
            flush=True,
        ),
    )


def _trajectory_rows(result: MultiRadialFDResult, stage: str) -> list[dict[str, Any]]:
    rows = []
    for item in result.iterations:
        row: dict[str, Any] = {
            "stage": stage,
            "iteration": item.iteration,
            "loss": item.loss,
            "relative_l2_error": item.relative_l2_error,
            "damping": item.damping,
            "evaluation_count": item.evaluation_count,
            "maximum_system_residual": item.maximum_system_residual,
            "component_count": len(item.state.components),
            "maximum_mode": max(c.maximum_mode for c in item.state.components),
            "stage_total_seconds": result.total_seconds,
        }
        for index, component in enumerate(item.state.components):
            row[f"component_{index}_id"] = component.component_id
            row[f"component_{index}_parameters"] = json.dumps(
                item.parameter_vector[item.state.parameter_slices[index]].tolist()
            )
        rows.append(row)
    return rows


def _append_optimizer_trace(
    trace: VideoTrace,
    result: MultiRadialFDResult,
    stage: str,
) -> None:
    for item in result.iterations[1:]:
        trace.append(item.state, f"{stage}: accepted iterate {item.iteration}", item.loss)


def _background_seed_state(
    raster,
    data: ComplexScatteredData,
    production_geometry,
    refined_geometry,
    solve_config,
    chart: str = "radial",
) -> tuple[MultiRadialFourierState | None, list[dict[str, Any]]]:
    # Use the TD minimum itself rather than a possibly merged region centroid.
    # The finite radius remains TD-derived and truth-free.
    seed = np.asarray(raster.minimum_point)
    equivalent = float(np.clip(raster.equivalent_radius_m, 0.012, 0.060))
    radii = []
    for factor in (1.0, 0.75, 0.5, 0.35):
        radius = float(np.clip(factor * equivalent, 0.008, 0.060))
        if not any(abs(radius - previous) <= 1.0e-12 for previous in radii):
            radii.append(radius)
    base_loss = _empty_loss(data)
    rows: list[dict[str, Any]] = []
    accepted: list[tuple[float, MultiRadialFourierState]] = []
    for radius in radii:
        candidate = MultiRadialFourierState(
            (circle_component(seed, radius, "split_seed_000", chart),)
        )
        row: dict[str, Any] = {
            "seed_x_m": seed[0],
            "seed_y_m": seed[1],
            "equivalent_radius_m": raster.equivalent_radius_m,
            "trial_radius_m": radius,
            "empty_loss": base_loss,
            "accepted": False,
        }
        try:
            production = evaluate_multiradial_objective(
                candidate, data, production_geometry, solve_config=solve_config
            )
            refined = evaluate_multiradial_objective(
                candidate, data, refined_geometry, solve_config=solve_config
            )
            production_delta = production.loss - base_loss
            refined_delta = refined.loss - base_loss
            agreement = abs(production_delta - refined_delta)
            passes = (
                production_delta < 0.0
                and refined_delta < 0.0
                and min(-production_delta, -refined_delta) > 5.0 * agreement + 1.0e-12
            )
            row.update(
                production_loss=production.loss,
                refined_loss=refined.loss,
                production_delta=production_delta,
                refined_delta=refined_delta,
                accepted=passes,
                rejection_reason=None if passes else "cross_resolution_descent_failed",
            )
            if passes:
                accepted.append((production.loss, candidate))
        except Exception as exc:  # The row is evidence for an infeasible candidate.
            row["rejection_reason"] = f"invalid_geometry: {type(exc).__name__}: {exc}"
        rows.append(row)
    if not accepted:
        return None, rows
    return min(accepted, key=lambda item: item[0])[1], rows


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    iteration01._write_csv(path, rows)


def _write_json(path: Path, value: Any) -> None:
    iteration01._write_json(path, value)


def _state_loss(state, data, geometry, solve_config) -> float:
    return evaluate_multiradial_objective(
        state, data, geometry, solve_config=solve_config
    ).loss


def _additive_birth(
    current: MultiRadialFourierState,
    data: ComplexScatteredData,
    profile: RunProfile,
    production_geometry,
    refined_geometry,
    solve_config,
    output: Path,
    chart: str = "radial",
) -> tuple[MultiRadialFourierState | None, dict[str, Any]]:
    production, _ = build_td_raster(
        current,
        data,
        num_points=profile.production_raster,
        geometry_config=production_geometry,
        solve_config=solve_config,
    )
    refined, _ = build_td_raster(
        current,
        data,
        num_points=profile.refined_raster,
        geometry_config=refined_geometry,
        solve_config=solve_config,
    )
    iteration01._raster_npz(output / "td_current_production.npz", production)
    iteration01._raster_npz(output / "td_current_refined.npz", refined)
    birth = evaluate_birth_ladder(
        current,
        data,
        seed_center=production.selected_centroid,
        equivalent_radius_m=production.equivalent_radius_m,
        production_geometry_config=production_geometry,
        refined_geometry_config=refined_geometry,
        solve_config=solve_config,
        component_id="td_birth_001",
        chart=chart,
    )
    trial_rows = [
        {
            key: value
            for key, value in trial.__dict__.items()
            if key != "state"
        }
        for trial in birth.trials
    ]
    _write_csv(output / "birth_trials.csv", trial_rows)
    record = {
        "policy": "current_domain_additive_birth",
        "production_minimum_m": production.minimum_point,
        "production_centroid_m": production.selected_centroid,
        "refined_centroid_m": refined.selected_centroid,
        "centroid_shift_m": float(
            np.linalg.norm(production.selected_centroid - refined.selected_centroid)
        ),
        "production_region_count": production.region_count,
        "refined_region_count": refined.region_count,
        "stop_reason": birth.stop_reason,
        "trials": trial_rows,
    }
    return birth.selected_state, record


def _replacement_split(
    current: MultiRadialFourierState,
    data: ComplexScatteredData,
    profile: RunProfile,
    production_geometry,
    refined_geometry,
    solve_config,
    output: Path,
    *,
    seed_mode_schedule: tuple[int, ...] = (),
    chart: str = "radial",
) -> tuple[
    MultiRadialFourierState | None,
    dict[str, Any],
    tuple[tuple[str, MultiRadialFDResult], ...],
]:
    background_production, _ = build_td_raster(
        None,
        data,
        num_points=profile.production_raster,
        solve_config=solve_config,
    )
    background_refined, _ = build_td_raster(
        None,
        data,
        num_points=profile.refined_raster,
        solve_config=solve_config,
    )
    iteration01._raster_npz(
        output / "td_background_production.npz", background_production
    )
    iteration01._raster_npz(output / "td_background_refined.npz", background_refined)
    first, first_rows = _background_seed_state(
        background_production,
        data,
        production_geometry,
        refined_geometry,
        solve_config,
        chart,
    )
    _write_csv(output / "split_first_component_trials.csv", first_rows)
    record: dict[str, Any] = {
        "policy": "background_td_replacement",
        "background_production_minimum_m": background_production.minimum_point,
        "background_refined_minimum_m": background_refined.minimum_point,
        "background_minimum_shift_m": float(
            np.linalg.norm(
                background_production.minimum_point - background_refined.minimum_point
            )
        ),
        "first_component_trials": first_rows,
        "accepted": False,
    }
    if first is None:
        record["stop_reason"] = "no_cross_resolution_first_component"
        return None, record, ()

    first_fit = _run_optimizer(
        first,
        data,
        production_geometry,
        solve_config,
        iterations=profile.single_seed_iterations,
        stage="split-first-component",
        chart=chart,
    )
    first_state = first_fit.final_state
    first_optimization: list[tuple[str, MultiRadialFDResult]] = [
        ("split_proposal_first_k1", first_fit)
    ]
    # A non-circular target can leave a stronger residual beside the first
    # seed than at the missing object.  Explain the detected object in its
    # declared shape space before asking the TD to locate another component.
    for maximum_mode in seed_mode_schedule:
        promoted = _promote(first_state, maximum_mode)
        shape_fit = _run_optimizer(
            promoted,
            data,
            production_geometry,
            solve_config,
            iterations=profile.single_seed_iterations,
            stage=f"split-first-shape-k{maximum_mode}",
            chart=chart,
        )
        first_optimization.append(
            (f"split_proposal_first_k{maximum_mode}", shape_fit)
        )
        first_state = shape_fit.final_state
    second_production, _ = build_td_raster(
        first_state,
        data,
        num_points=profile.production_raster,
        boundary_buffer_m=0.025,
        geometry_config=production_geometry,
        solve_config=solve_config,
    )
    second_refined, _ = build_td_raster(
        first_state,
        data,
        num_points=profile.refined_raster,
        boundary_buffer_m=0.025,
        geometry_config=refined_geometry,
        solve_config=solve_config,
    )
    iteration01._raster_npz(output / "td_second_production.npz", second_production)
    iteration01._raster_npz(output / "td_second_refined.npz", second_refined)
    birth = evaluate_birth_ladder(
        first_state,
        data,
        seed_center=second_production.selected_centroid,
        equivalent_radius_m=second_production.equivalent_radius_m,
        production_geometry_config=production_geometry,
        refined_geometry_config=refined_geometry,
        solve_config=solve_config,
        component_id="td_birth_001",
        chart=chart,
    )
    second_rows = [
        {key: value for key, value in trial.__dict__.items() if key != "state"}
        for trial in birth.trials
    ]
    _write_csv(output / "split_second_component_trials.csv", second_rows)
    record.update(
        first_component_optimization=[
            {
                "stage": stage,
                "stop_reason": result.stop_reason,
                "accepted_iterations": len(result.iterations) - 1,
                "evaluation_count": result.evaluation_count,
                "seconds": result.total_seconds,
            }
            for stage, result in first_optimization
        ],
        second_search_boundary_buffer_m=0.025,
        second_production_centroid_m=second_production.selected_centroid,
        second_refined_centroid_m=second_refined.selected_centroid,
        second_centroid_shift_m=float(
            np.linalg.norm(
                second_production.selected_centroid - second_refined.selected_centroid
            )
        ),
        second_component_trials=second_rows,
    )
    if birth.selected_state is None:
        record["stop_reason"] = "no_cross_resolution_second_component"
        return None, record, tuple(first_optimization)

    replacement = birth.selected_state
    current_production = evaluate_multiradial_objective(
        current, data, production_geometry, solve_config=solve_config
    )
    current_refined = evaluate_multiradial_objective(
        current, data, refined_geometry, solve_config=solve_config
    )
    replacement_production = evaluate_multiradial_objective(
        replacement, data, production_geometry, solve_config=solve_config
    )
    replacement_refined = evaluate_multiradial_objective(
        replacement, data, refined_geometry, solve_config=solve_config
    )
    accepted = (
        replacement_production.loss < current_production.loss
        and replacement_refined.loss < current_refined.loss
    )
    record.update(
        current_production_loss=current_production.loss,
        current_refined_loss=current_refined.loss,
        replacement_production_loss=replacement_production.loss,
        replacement_refined_loss=replacement_refined.loss,
        accepted=accepted,
        stop_reason="accepted" if accepted else "replacement_did_not_improve_both_resolutions",
    )
    return (replacement if accepted else None), record, tuple(first_optimization)


def _directed_hausdorff(first: np.ndarray, second: np.ndarray) -> float:
    # 720 x 720 x 2 is bounded and avoids adding another geometry dependency.
    distances = np.linalg.norm(first[:, None, :] - second[None, :, :], axis=-1)
    return float(np.max(np.min(distances, axis=1)))


def _geometry_metrics(
    state: MultiRadialFourierState,
    spec: CaseSpec,
) -> tuple[list[dict[str, Any]], float]:
    recovered = tuple(_sample_component(component) for component in state.components)
    truths = _truth_points(spec)
    if len(recovered) != len(truths):
        return [], math.inf
    best = None
    for assignment in itertools.permutations(range(len(truths))):
        distances = []
        for recovered_index, truth_index in enumerate(assignment):
            forward = _directed_hausdorff(recovered[recovered_index], truths[truth_index])
            reverse = _directed_hausdorff(truths[truth_index], recovered[recovered_index])
            distances.append(max(forward, reverse))
        score = max(distances)
        if best is None or score < best[0]:
            best = (score, assignment, distances)
    assert best is not None
    rows = []
    for recovered_index, truth_index in enumerate(best[1]):
        component = state.components[recovered_index]
        rows.append(
            {
                "recovered_component": component.component_id,
                "truth_component": spec.truth_curves[truth_index].component_id,
                "symmetric_hausdorff_m": best[2][recovered_index],
                "center_distance_m": float(
                    np.linalg.norm(
                        np.mean(recovered[recovered_index], axis=0)
                        - np.mean(truths[truth_index], axis=0)
                    )
                ),
                "maximum_mode": component.maximum_mode,
            }
        )
    return rows, float(best[0])


def _render_video(
    path: Path,
    spec: CaseSpec,
    trace: VideoTrace,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter

    truth = _truth_points(spec)
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    writer = FFMpegWriter(
        fps=12,
        bitrate=2400,
        metadata={"title": spec.title},
    )
    colors = ("#1f77b4", "#e45756", "#59a14f")
    with writer.saving(fig, str(path), dpi=140):
        for frame_index, (state, label, loss) in enumerate(
            zip(trace.states, trace.labels, trace.losses)
        ):
            hold = 30 if frame_index in (0, len(trace.states) - 1) else 12
            for _ in range(hold):
                ax.clear()
                for index, points in enumerate(truth):
                    closed = np.vstack((points, points[0]))
                    ax.plot(
                        closed[:, 0],
                        closed[:, 1],
                        "k--",
                        linewidth=2,
                        label="truth" if index == 0 else None,
                    )
                for index, component in enumerate(state.components):
                    points = _sample_component(component)
                    closed = np.vstack((points, points[0]))
                    ax.plot(
                        closed[:, 0],
                        closed[:, 1],
                        color=colors[index % len(colors)],
                        linewidth=3,
                        label=f"recovered {component.component_id}",
                    )
                    ax.scatter(*component.center, color=colors[index % len(colors)], s=20)
                ax.set(
                    xlim=(0.30, 0.72),
                    ylim=(0.30, 0.72),
                    aspect="equal",
                    xlabel="x (m)",
                    ylabel="y (m)",
                    title=f"{spec.title}\n{label}\nJ = {loss:.3e}",
                )
                ax.grid(alpha=0.18)
                ax.legend(loc="upper right", fontsize=7)
                writer.grab_frame()
    plt.close(fig)


def _case_manifest(spec: CaseSpec, profile: RunProfile) -> dict[str, Any]:
    truth_separation = float(
        np.linalg.norm(
            np.mean(spec.truth_curves[0].discretize(64).points, axis=0)
            - np.mean(spec.truth_curves[1].discretize(64).points, axis=0)
        )
    )
    return {
        "case": spec.name,
        "title": spec.title,
        "chart": spec.chart,
        "profile": profile.__dict__,
        "proposal_policy": spec.proposal_policy,
        "topology_frequency_hz": FREQUENCIES_HZ[0],
        "training_frequencies_hz": FREQUENCIES_HZ[list(spec.training_indices)],
        "holdout_frequencies_hz": np.delete(FREQUENCIES_HZ, spec.training_indices),
        "mode_schedule": spec.mode_schedule,
        "initial_parameters": spec.initial_state.parameter_vector(),
        "truth_component_ids": [curve.component_id for curve in spec.truth_curves],
        "truth_center_separation_m": truth_separation,
        "qualification": {
            "geometry_tolerance_m": spec.geometry_tolerance_m,
            "training_relative_l2_tolerance": spec.training_tolerance,
            "holdout_relative_l2_tolerance": spec.holdout_tolerance,
            "required_component_count": 2,
            "requires_cross_resolution_topology_acceptance": True,
            "quick_profile_makes_qualification_claim": False,
        },
    }


def run_case(
    spec: CaseSpec,
    profile: RunProfile,
    output: Path,
    *,
    skip_video: bool,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    solve_config = iteration01.iteration01_solve_config()
    production_geometry = iteration01._geometry_config(profile.production_nodes)
    refined_geometry = iteration01._geometry_config(profile.refined_nodes)
    manifest = _case_manifest(spec, profile)
    _write_json(output / "config.json", manifest)
    observations, oracle_description = _observations(spec, profile, solve_config)
    data = _training_data(spec, observations)
    topology_data = _topology_data(observations)
    initial_evaluation = evaluate_multiradial_objective(
        spec.initial_state,
        topology_data,
        production_geometry,
        solve_config=solve_config,
    )
    trace = VideoTrace([], [], [])
    trace.append(spec.initial_state, "initial one-component state", initial_evaluation.loss)
    trajectory_rows: list[dict[str, Any]] = []

    pre = _run_optimizer(
        spec.initial_state,
        topology_data,
        production_geometry,
        solve_config,
        iterations=profile.pre_iterations,
        stage="pre-topology",
        chart=spec.chart,
    )
    trajectory_rows.extend(_trajectory_rows(pre, "pre_topology"))
    _append_optimizer_trace(trace, pre, "pre-topology")
    current = pre.final_state

    if spec.proposal_policy == "current_domain_additive_birth":
        proposed, topology = _additive_birth(
            current,
            topology_data,
            profile,
            production_geometry,
            refined_geometry,
            solve_config,
            output,
            spec.chart,
        )
        split_first_fit = None
    else:
        proposed, topology, split_first_fits = _replacement_split(
            current,
            topology_data,
            profile,
            production_geometry,
            refined_geometry,
            solve_config,
            output,
            seed_mode_schedule=spec.mode_schedule,
            chart=spec.chart,
        )
        for stage, split_first_fit in split_first_fits:
            trajectory_rows.extend(
                _trajectory_rows(split_first_fit, stage)
            )

    if proposed is None:
        elapsed = float(perf_counter() - started)
        metrics = {
            "case": spec.name,
            "chart": spec.chart,
            "profile": profile.name,
            "outcome": "topology_proposal_failed",
            "qualified": False if profile.name == "full" else None,
            "oracle": oracle_description,
            "topology": topology,
            "elapsed_seconds": elapsed,
        }
        _write_csv(output / "trajectory.csv", trajectory_rows)
        _write_json(output / "metrics.json", metrics)
        if not skip_video:
            _render_video(output / f"{spec.name}.mp4", spec, trace)
        (output / "README.md").write_text(
            f"# {spec.title}\n\nOutcome: **topology proposal failed**.\n\n"
            "See `metrics.json`, the TD grids, and the MP4 of the accepted states "
            "before the failed topology gate.\n",
            encoding="utf-8",
        )
        return metrics

    proposed_loss = _state_loss(
        proposed, topology_data, production_geometry, solve_config
    )
    trace.append(proposed, "cross-resolution topology proposal accepted", proposed_loss)
    post = _run_optimizer(
        proposed,
        topology_data,
        production_geometry,
        solve_config,
        iterations=profile.post_iterations,
        stage="post-topology-low-frequency",
        chart=spec.chart,
    )
    trajectory_rows.extend(_trajectory_rows(post, "post_topology_low_frequency"))
    _append_optimizer_trace(trace, post, "post-topology low frequency")
    current = post.final_state
    optimization_results = [pre, post]

    for maximum_mode in spec.mode_schedule:
        promoted = _promote(current, maximum_mode)
        promoted_loss = _state_loss(
            promoted, topology_data, production_geometry, solve_config
        )
        trace.append(promoted, f"activate radial modes through K={maximum_mode}", promoted_loss)
        result = _run_optimizer(
            promoted,
            topology_data,
            production_geometry,
            solve_config,
            iterations=profile.mode_iterations,
            stage=f"shape-k{maximum_mode}",
        chart=spec.chart,
        )
        trajectory_rows.extend(_trajectory_rows(result, f"shape_k{maximum_mode}"))
        _append_optimizer_trace(trace, result, f"shape K={maximum_mode}")
        optimization_results.append(result)
        current = result.final_state

    if len(spec.training_indices) > 1:
        full_band_start = _state_loss(current, data, production_geometry, solve_config)
        trace.append(
            current,
            "activate all declared training frequencies",
            full_band_start,
        )
        full_band = _run_optimizer(
            current,
            data,
            production_geometry,
            solve_config,
            iterations=profile.frequency_iterations,
            stage="full-training-band",
            chart=spec.chart,
        )
        trajectory_rows.extend(_trajectory_rows(full_band, "full_training_band"))
        _append_optimizer_trace(trace, full_band, "full training band")
        optimization_results.append(full_band)
        current = full_band.final_state

    final_production = evaluate_multiradial_objective(
        current, data, production_geometry, solve_config=solve_config
    )
    final_refined = evaluate_multiradial_objective(
        current, data, refined_geometry, solve_config=solve_config
    )
    all_response = predict_multicomponent_kress_paired_boundary_response(
        current.boundary(production_geometry),
        iteration01._problem(FREQUENCIES_HZ),
        solve_config=solve_config,
    ).scattered_response
    holdout_indices = [index for index in range(len(FREQUENCIES_HZ)) if index not in spec.training_indices]
    holdouts = {
        f"{FREQUENCIES_HZ[index] / 1.0e9:.2f}_GHz": iteration01._relative_error(
            all_response[:, index], observations[:, index]
        )
        for index in holdout_indices
    }
    geometry_rows, maximum_geometry_error = _geometry_metrics(current, spec)
    prediction_resolution_change = iteration01._relative_error(
        final_production.prediction,
        final_refined.prediction,
    )
    monotone = all(
        all(later.loss < earlier.loss for earlier, later in zip(result.iterations, result.iterations[1:]))
        for result in optimization_results
    )
    qualified = (
        len(current.components) == 2
        and bool(topology.get("accepted", topology.get("stop_reason") == "accepted"))
        and monotone
        and final_production.relative_l2_error <= spec.training_tolerance
        and all(value <= spec.holdout_tolerance for value in holdouts.values())
        and maximum_geometry_error <= spec.geometry_tolerance_m
        and prediction_resolution_change <= 0.01
    )
    elapsed = float(perf_counter() - started)
    metrics = {
        "case": spec.name,
        "chart": spec.chart,
        "profile": profile.name,
        "outcome": (
            "full_pass"
            if profile.name == "full" and qualified
            else "qualification_failure"
            if profile.name == "full"
            else "quick_smoke_complete"
        ),
        "qualified": bool(qualified) if profile.name == "full" else None,
        "oracle": oracle_description,
        "topology": topology,
        "final_component_count": len(current.components),
        "final_parameter_count": current.parameter_count,
        "final_maximum_modes": [component.maximum_mode for component in current.components],
        "training_relative_l2": final_production.relative_l2_error,
        "refined_training_relative_l2": final_refined.relative_l2_error,
        "production_refined_prediction_relative_change": prediction_resolution_change,
        "holdout_relative_l2": holdouts,
        "maximum_geometry_error_m": maximum_geometry_error,
        "geometry": geometry_rows,
        "accepted_objectives_monotone_within_stages": monotone,
        "optimizer_stages": [
            {
                "stop_reason": result.stop_reason,
                "accepted_iterations": len(result.iterations) - 1,
                "evaluation_count": result.evaluation_count,
                "infeasible_trial_count": result.infeasible_trial_count,
                "seconds": result.total_seconds,
            }
            for result in optimization_results
        ],
        "elapsed_seconds": elapsed,
    }
    _write_csv(output / "trajectory.csv", trajectory_rows)
    _write_csv(output / "geometry_metrics.csv", geometry_rows)
    _write_json(output / "metrics.json", metrics)
    if not skip_video:
        _render_video(output / f"{spec.name}.mp4", spec, trace)
    (output / "README.md").write_text(
        f"# {spec.title}\n\n"
        f"Outcome: **{metrics['outcome']}**.\n\n"
        f"Profile: `{profile.name}`. Chart: `{spec.chart}`. "
        f"Proposal policy: `{spec.proposal_policy}`. "
        f"Observation source: {oracle_description}. The inverse used only "
        f"{', '.join(f'{FREQUENCIES_HZ[i] / 1e9:.2f} GHz' for i in spec.training_indices)}; "
        "all other frequencies are holdouts. Truth geometry is used only for final "
        "qualification and the dashed video overlay.\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    args = _parse_args()
    profile = _profile(args.profile)
    case_names = CASE_NAMES if args.case == "all" else (args.case,)
    specs = tuple(_case_spec(name, args.chart) for name in case_names)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "profile": profile.__dict__,
                    "cases": [_case_manifest(spec, profile) for spec in specs],
                },
                indent=2,
                default=lambda value: value.tolist() if isinstance(value, np.ndarray) else value,
            )
        )
        return 0

    output = _output_root(args)
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"Output exists and is non-empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    suite_started = perf_counter()
    results = []
    for spec in specs:
        case_output = output / spec.name
        if case_output.exists():
            if not args.overwrite:
                raise FileExistsError(f"Case output already exists: {case_output}")
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            case_output = output / f"{spec.name}-rerun-{stamp}"
        print(f"Starting {spec.name}: {spec.title}", flush=True)
        try:
            result = run_case(
                spec,
                profile,
                case_output,
                skip_video=args.skip_video,
            )
        except Exception as exc:
            result = {
                "case": spec.name,
                "profile": profile.name,
                "outcome": "execution_error",
                "qualified": False if profile.name == "full" else None,
                "error": f"{type(exc).__name__}: {exc}",
            }
            _write_json(case_output / "metrics.json", result)
            print(f"{spec.name} failed with {result['error']}", flush=True)
        results.append(result)
        print(f"Finished {spec.name}: {result['outcome']}", flush=True)
    suite = {
        "chart": args.chart,
        "profile": profile.name,
        "cases": results,
        "elapsed_seconds": float(perf_counter() - suite_started),
        "all_full_cases_passed": (
            all(result.get("qualified") is True for result in results)
            if profile.name == "full"
            else None
        ),
    }
    _write_json(output / "suite_metrics.json", suite)
    print(f"Artifacts: {output}", flush=True)
    if any(result["outcome"] == "execution_error" for result in results):
        return 3
    if profile.name == "full" and not suite["all_full_cases_passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
