#!/usr/bin/env python3
"""Execute radial-Fourier topology iteration 01 and render its evidence.

The frozen experiment is defined in
``docs/iterations/radial_fourier_topology/iteration_01/03_plan.md``.  This
driver stops at the first failed hard gate (G0--G4); G5 is reported as an
optional robustness qualification.  Independent cylindrical-harmonic data is
used throughout, while every candidate/current state is evaluated by Kress.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "solvers"))

import config.two_circle_config as cfg  # noqa: E402
from gpr_bem_kress.multicomponent import adapt_multicomponent_boundary  # noqa: E402
from gpr_bem_ref import penetrable_cylinder_scattered_field  # noqa: E402
from multicylinder_ref import (  # noqa: E402
    CircularCylinder2D,
    solve_multicylinder_line_sources,
)
from sdf_bem_multicomponent import (  # noqa: E402
    MaterialSpec,
    PairedForwardProblem,
    predict_multicomponent_kress_paired_boundary_response,
)
from sdf_inverse import (  # noqa: E402
    ComplexScatteredData,
    MultiRadialFDResult,
    MultiRadialFourierState,
    OrderedSDFGeometryConfig,
    build_td_raster,
    circle_radial_fourier_state,
    evaluate_birth_ladder,
    evaluate_current_domain_topological_derivative,
    evaluate_multiradial_objective,
    iteration01_optimizer_config,
    iteration01_solve_config,
    normalized_complex_residual,
    run_multiradial_fd_inverse,
)


FREQUENCIES_HZ = np.asarray((0.50e9, 1.50e9, 2.50e9), dtype=np.float64)
TRAINING_INDEX = 0
PRODUCTION_NODES = 64
REFINED_NODES = 128
PRODUCTION_RASTER = 121
REFINED_RASTER = 241
ORACLE_TD = np.asarray((-159.268698, -53.3368618, 37.8091661))
TD_PROBES = np.asarray(((0.57, 0.50), (0.50, 0.62), (0.66, 0.66)))
SOURCE_STRENGTH = 1.0e-6 + 0.0j
SCENE_CENTER = np.asarray((0.50, 0.50))
TRUTH_CENTERS = np.asarray(cfg.TARGET_CIRCLE_CENTERS, dtype=np.float64)
TRUTH_RADII = np.asarray(cfg.TARGET_CIRCLE_RADII, dtype=np.float64)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Result directory (default: a timestamped iteration-01 bundle).",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _output_path(args: argparse.Namespace) -> Path:
    if args.output is not None:
        return args.output.resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ROOT / "results" / "inverse" / "radial_fourier" / "topology_birth" / f"iteration-01-{stamp}"


def _write_json(path: Path, value: Any) -> None:
    def default(item: Any):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, (np.floating, np.integer, np.bool_)):
            return item.item()
        if isinstance(item, complex):
            return {"real": item.real, "imag": item.imag}
        raise TypeError(type(item).__name__)

    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=default) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    records = list(rows)
    if not records:
        path.write_text("\n", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for record in records:
        for name in record:
            if name not in fieldnames:
                fieldnames.append(name)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def _geometry_config(nodes: int) -> OrderedSDFGeometryConfig:
    return OrderedSDFGeometryConfig(
        bounds=((0.20, 0.20), (0.80, 0.80)),
        grid_shape=(16, 16),
        projected_samples=8,
        bandwidth=1,
        num_nodes=nodes,
        arclength_dense_resolution=256,
        validation_resolution=256,
    )


def _ring_scan() -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0.0, 2.0 * np.pi, 24, endpoint=False)
    standoff = 0.30
    offset = float(cfg.TX_RX_OFFSET) / standoff
    sources = np.column_stack(
        (SCENE_CENTER[0] + standoff * np.cos(angles), SCENE_CENTER[1] + standoff * np.sin(angles))
    )
    receivers = np.column_stack(
        (SCENE_CENTER[0] + standoff * np.cos(angles + offset), SCENE_CENTER[1] + standoff * np.sin(angles + offset))
    )
    return sources, receivers


def _problem(frequencies: np.ndarray, strength: complex = SOURCE_STRENGTH) -> PairedForwardProblem:
    sources, receivers = _ring_scan()
    return PairedForwardProblem(
        source_points=sources,
        receiver_points=receivers,
        angular_frequencies=2.0 * np.pi * frequencies,
        source_strengths=strength,
        exterior=MaterialSpec(cfg.SAND_EPSR, cfg.SAND_SIGMA, 1.0),
        interior=MaterialSpec(cfg.PLASTIC_EPSR, cfg.PLASTIC_SIGMA, 1.0),
        eps0=cfg.EPS0,
        mu0=cfg.MU0,
    )


def _wavenumbers(frequency_hz: float) -> tuple[complex, complex]:
    omega = 2.0 * np.pi * frequency_hz
    return (
        complex(omega * np.sqrt(cfg.MU0 * cfg.EPS0 * cfg.SAND_EPSR)),
        complex(omega * np.sqrt(cfg.MU0 * cfg.EPS0 * cfg.PLASTIC_EPSR)),
    )


def _oracle_response(
    centers: np.ndarray,
    radii: np.ndarray,
    frequencies: np.ndarray,
    *,
    component_ids: tuple[str, ...],
    strength: complex = SOURCE_STRENGTH,
) -> np.ndarray:
    sources, receivers = _ring_scan()
    columns = []
    cylinders = [
        CircularCylinder2D(tuple(center), float(radius), component_id)
        for center, radius, component_id in zip(centers, radii, component_ids)
    ]
    for frequency in frequencies:
        k_exterior, k_interior = _wavenumbers(float(frequency))
        solution = solve_multicylinder_line_sources(
            cylinders,
            sources,
            k_exterior=k_exterior,
            k_interior=k_interior,
            source_strength=strength,
        )
        columns.append(np.diag(solution.scattered_field(receivers)))
    return np.stack(columns, axis=1)


def _state_a(*, wrong: bool = False) -> MultiRadialFourierState:
    center = np.asarray((0.42, 0.50)) if wrong else TRUTH_CENTERS[0]
    component_id = "A_wrong" if wrong else "A"
    return MultiRadialFourierState((circle_radial_fourier_state(center, TRUTH_RADII[0], component_id),))


def _truth_state() -> MultiRadialFourierState:
    return MultiRadialFourierState(
        tuple(
            circle_radial_fourier_state(center, radius, component_id)
            for center, radius, component_id in zip(TRUTH_CENTERS, TRUTH_RADII, ("A", "B"))
        )
    )


def _training_data(observed_all: np.ndarray) -> ComplexScatteredData:
    return ComplexScatteredData(
        _problem(FREQUENCIES_HZ[[TRAINING_INDEX]]),
        observed_all[:, [TRAINING_INDEX]],
    )


def _relative_error(predicted: np.ndarray, observed: np.ndarray) -> float:
    return float(np.linalg.norm(predicted - observed) / np.linalg.norm(observed))


def _state_geometry_metrics(state: MultiRadialFourierState, truth_tolerance_m: float) -> tuple[list[dict[str, Any]], bool]:
    rows = []
    passed = True
    for index, component in enumerate(state.components):
        truth_index = min(index, 1)
        center_error = float(np.linalg.norm(component.center - TRUTH_CENTERS[truth_index]))
        radius_error = abs(component.mean_radius_m - float(TRUTH_RADII[truth_index]))
        row_pass = center_error <= truth_tolerance_m and radius_error <= truth_tolerance_m
        passed &= row_pass
        rows.append(
            {
                "component_id": component.component_id,
                "truth_component": ("A", "B")[truth_index],
                "center_x_m": component.center[0],
                "center_y_m": component.center[1],
                "radius_m": component.mean_radius_m,
                "center_error_m": center_error,
                "radius_error_m": radius_error,
                "tolerance_m": truth_tolerance_m,
                "pass": row_pass,
            }
        )
    return rows, bool(passed and len(rows) == 2)


def _trajectory_rows(result: MultiRadialFDResult, *, phase: str) -> list[dict[str, Any]]:
    rows = []
    for item in result.iterations:
        row: dict[str, Any] = {
            "phase": phase,
            "iteration": item.iteration,
            "loss": item.loss,
            "relative_l2_error": item.relative_l2_error,
            "damping": item.damping,
            "evaluation_count": item.evaluation_count,
            "maximum_system_residual": item.maximum_system_residual,
            "component_count": len(item.state.components),
        }
        for component_index, component in enumerate(item.state.components):
            row.update(
                {
                    f"component_{component_index}_id": component.component_id,
                    f"component_{component_index}_radius_m": component.mean_radius_m,
                    f"component_{component_index}_center_x_m": component.center[0],
                    f"component_{component_index}_center_y_m": component.center[1],
                }
            )
        rows.append(row)
    return rows


def _plot_artifacts(output: Path, raster_prod, raster_ref, birth, t3, t4) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def draw_truth(ax):
        for center, radius in zip(TRUTH_CENTERS, TRUTH_RADII):
            ax.add_patch(plt.Circle(center, radius, fill=False, color="black", linestyle="--", linewidth=1.5))

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    image = ax.imshow(
        raster_prod.values,
        origin="lower",
        extent=(raster_prod.axis_x[0], raster_prod.axis_x[-1], raster_prod.axis_y[0], raster_prod.axis_y[-1]),
        cmap="coolwarm",
        aspect="equal",
    )
    ax.contour(raster_prod.axis_x, raster_prod.axis_y, raster_prod.threshold_mask, levels=(0.5,), colors="yellow")
    ax.scatter(*raster_prod.minimum_point, marker="x", color="black", label="TD minimum")
    ax.scatter(*raster_prod.selected_centroid, marker="+", color="lime", label="region centroid")
    draw_truth(ax)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Current-domain topological derivative, 0.50 GHz")
    fig.colorbar(image, ax=ax, label=r"$D_TJ$")
    fig.tight_layout()
    fig.savefig(output / "td_heatmap.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    for ax, raster, label in zip(axes, (raster_prod, raster_ref), ("121 × 121", "241 × 241")):
        ax.imshow(raster.values, origin="lower", extent=(raster.axis_x[0], raster.axis_x[-1], raster.axis_y[0], raster.axis_y[-1]), cmap="coolwarm", aspect="equal")
        ax.contour(raster.axis_x, raster.axis_y, raster.selected_region, levels=(0.5,), colors="yellow")
        ax.scatter(*raster.selected_centroid, marker="+", color="lime")
        draw_truth(ax)
        ax.set_title(f"{label}; centroid = ({raster.selected_centroid[0]:.4f}, {raster.selected_centroid[1]:.4f})")
    fig.savefig(output / "td_refinement_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    draw_truth(ax)
    for component in birth.initial_state.components:
        ax.add_patch(plt.Circle(component.center, component.mean_radius_m, fill=False, color="#1f77b4", linewidth=2))
    if birth.selected_state is not None:
        component = birth.selected_state.components[-1]
        ax.add_patch(plt.Circle(component.center, component.mean_radius_m, fill=False, color="#e45756", linewidth=2))
    ax.set(xlim=(0.36, 0.64), ylim=(0.40, 0.60), aspect="equal", title="Accepted topology birth (truth dashed)")
    fig.tight_layout()
    fig.savefig(output / "topology_birth.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.5))
    ax.semilogy([item.iteration for item in t3.iterations], [item.loss for item in t3.iterations], "o-", label="T3")
    if t4 is not None:
        ax.semilogy(np.arange(len(t4[0])), [item.loss for item in t4[0]], "s--", label="T4 pre-stage")
        if t4[1] is not None:
            ax.semilogy(np.arange(len(t4[1].iterations)), [item.loss for item in t4[1].iterations], "d-", label="T4 two-component")
    ax.set(xlabel="Accepted iterate", ylabel="Training objective", title="Monotone accepted-state objectives")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "objective_trajectory.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    draw_truth(ax)
    for component in t3.final_state.components:
        ax.add_patch(plt.Circle(component.center, component.mean_radius_m, fill=False, color="#e45756", linewidth=2.2))
    ax.set(xlim=(0.36, 0.64), ylim=(0.40, 0.60), aspect="equal", title="Final recovered geometry (truth dashed)")
    fig.tight_layout()
    fig.savefig(output / "final_geometry.png", dpi=180)
    plt.close(fig)


def _render_video(path: Path, states: list[MultiRadialFourierState], labels: list[str], losses: list[float]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    writer = FFMpegWriter(fps=12, bitrate=2200, metadata={"title": "One-circle to two-circle topology inversion"})
    with writer.saving(fig, str(path), dpi=140):
        for frame_index, (state, label, loss) in enumerate(zip(states, labels, losses)):
            hold = 30 if frame_index in (0, len(states) - 1) else 14
            for _ in range(hold):
                ax.clear()
                for center, radius in zip(TRUTH_CENTERS, TRUTH_RADII):
                    ax.add_patch(plt.Circle(center, radius, fill=False, color="black", linestyle="--", linewidth=2, label="truth" if np.array_equal(center, TRUTH_CENTERS[0]) else None))
                colors = ("#1f77b4", "#e45756")
                for index, component in enumerate(state.components):
                    ax.add_patch(plt.Circle(component.center, component.mean_radius_m, fill=False, color=colors[index], linewidth=3, label=f"recovered {component.component_id}"))
                    ax.scatter(*component.center, color=colors[index], s=22)
                ax.set(xlim=(0.34, 0.66), ylim=(0.39, 0.61), aspect="equal", xlabel="x (m)", ylabel="y (m)")
                ax.set_title(f"One circle → two circles\n{label}\nJ = {loss:.3e}")
                ax.legend(loc="upper right", fontsize=8)
                ax.grid(alpha=0.18)
                writer.grab_frame()
    plt.close(fig)


def _raster_npz(path: Path, raster) -> None:
    np.savez_compressed(
        path,
        axis_x=raster.axis_x,
        axis_y=raster.axis_y,
        points=raster.points,
        values=raster.values,
        valid_mask=raster.valid_mask,
        threshold_mask=raster.threshold_mask,
        labels=raster.labels,
        selected_region=raster.selected_region,
    )


def main() -> int:
    args = _parse_args()
    output = _output_path(args)
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"Output exists and is non-empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    solve_config = iteration01_solve_config()
    production_geometry = _geometry_config(PRODUCTION_NODES)
    refined_geometry = _geometry_config(REFINED_NODES)
    observations = _oracle_response(TRUTH_CENTERS, TRUTH_RADII, FREQUENCIES_HZ, component_ids=("A", "B"))
    training_data = _training_data(observations)
    metrics: dict[str, Any] = {"gates": {}, "outcome": None, "run_root": str(output.relative_to(ROOT))}
    config_document = {
        "frequencies_hz": FREQUENCIES_HZ,
        "training_frequency_hz": FREQUENCIES_HZ[0],
        "production_nodes_per_component": PRODUCTION_NODES,
        "refined_nodes_per_component": REFINED_NODES,
        "production_raster": PRODUCTION_RASTER,
        "refined_raster": REFINED_RASTER,
        "inspection_center_m": SCENE_CENTER,
        "inspection_radius_m": 0.20,
        "boundary_mask_buffer_m": 0.010,
        "threshold_c0": 0.15,
        "birth_radius_factors": (1.0, 0.75, 0.5, 0.35),
        "minimum_birth_radius_m": 0.005,
        "minimum_absolute_clearance_m": 0.010,
        "source_strength": SOURCE_STRENGTH,
        "num_paired_measurements": 24,
        "optimizer": iteration01_optimizer_config().__dict__,
    }
    _write_json(output / "config.json", config_document)

    # G0: independent one-/two-cylinder forward qualification.
    g0_rows: list[dict[str, Any]] = []
    g0_pass = True
    sources, receivers = _ring_scan()
    states = {"one_circle": _state_a(), "two_circles": _truth_state()}
    responses: dict[tuple[str, int], np.ndarray] = {}
    for topology, state in states.items():
        problem_all = _problem(FREQUENCIES_HZ)
        if topology == "one_circle":
            exact_columns = []
            for frequency in FREQUENCIES_HZ:
                k_exterior, k_interior = _wavenumbers(float(frequency))
                exact_columns.append(
                    penetrable_cylinder_scattered_field(
                        receivers,
                        sources,
                        k_exterior=k_exterior,
                        k_interior=k_interior,
                        radius=TRUTH_RADII[0],
                        center=tuple(TRUTH_CENTERS[0]),
                        source_strength=SOURCE_STRENGTH,
                    )
                )
            exact = np.stack(exact_columns, axis=1)
        else:
            exact = observations
        for nodes, geometry in ((PRODUCTION_NODES, production_geometry), (REFINED_NODES, refined_geometry)):
            boundary = state.boundary(geometry)
            forward = predict_multicomponent_kress_paired_boundary_response(boundary, problem_all, solve_config=solve_config)
            responses[(topology, nodes)] = forward.scattered_response
            adapter = adapt_multicomponent_boundary(boundary, config=solve_config.assembly)
            for frequency_index, frequency in enumerate(FREQUENCIES_HZ):
                error = _relative_error(forward.scattered_response[:, frequency_index], exact[:, frequency_index])
                tolerance = 1.0e-4 if nodes == PRODUCTION_NODES else 1.0e-6
                residual = float(forward.linear_system_relative_residuals[frequency_index])
                row_pass = error <= tolerance and residual <= 1.0e-12
                g0_pass &= row_pass
                g0_rows.append({"topology": topology, "nodes_per_component": nodes, "frequency_hz": frequency, "relative_oracle_error": error, "oracle_tolerance": tolerance, "linear_system_relative_residual": residual, "pass": row_pass})
            if topology == "two_circles":
                required = adapter.component_pair_reports[0].required_clearance
                g0_pass &= abs(required - 0.010) <= 1.0e-15
    for topology in states:
        change = _relative_error(responses[(topology, PRODUCTION_NODES)], responses[(topology, REFINED_NODES)])
        g0_pass &= change <= 1.0e-4
        for row in g0_rows:
            if row["topology"] == topology:
                row["production_to_refined_relative_change"] = change
    _write_csv(output / "g0_forward_oracle.csv", g0_rows)
    metrics["gates"]["G0"] = {"pass": bool(g0_pass), "rows": g0_rows}
    if not g0_pass:
        metrics["outcome"] = "early_hard_gate_failure_G0"
        _write_json(output / "metrics.json", metrics)
        return 2

    # G1: production Kress TD against the saved independent regression values.
    g1_rows: list[dict[str, Any]] = []
    g1_pass = True
    for nodes, geometry, tolerance in ((64, production_geometry, 0.01), (128, refined_geometry, 0.002)):
        result = evaluate_current_domain_topological_derivative(_state_a(), training_data, TD_PROBES, geometry_config=geometry, solve_config=solve_config)
        for name, point, observed_value, expected in zip(("true_B_center", "background_1", "background_2"), TD_PROBES, result.values, ORACLE_TD):
            relative = abs(observed_value - expected) / abs(expected)
            row_pass = relative <= tolerance and np.sign(observed_value) == np.sign(expected)
            g1_pass &= row_pass
            g1_rows.append({"nodes_per_component": nodes, "probe": name, "x_m": point[0], "y_m": point[1], "implemented_td": observed_value, "oracle_td": expected, "relative_error": relative, "tolerance": tolerance, "sign_agrees": np.sign(observed_value) == np.sign(expected), "pass": row_pass})
    empty_truth = _oracle_response(TRUTH_CENTERS[:1], TRUTH_RADII[:1], FREQUENCIES_HZ[[0]], component_ids=("A",))
    empty_data = ComplexScatteredData(_problem(FREQUENCIES_HZ[[0]]), empty_truth)
    empty = evaluate_current_domain_topological_derivative(None, empty_data, TRUTH_CENTERS[:1], solve_config=solve_config)
    empty_error = abs(empty.values[0] - (-407.673430)) / 407.673430
    chunked = evaluate_current_domain_topological_derivative(_state_a(), training_data, TD_PROBES, geometry_config=production_geometry, solve_config=solve_config, chunk_size=1)
    unchunked = evaluate_current_domain_topological_derivative(_state_a(), training_data, TD_PROBES, geometry_config=production_geometry, solve_config=solve_config, chunk_size=4096)
    chunk_error = float(np.max(np.abs(chunked.values - unchunked.values)))
    weighted_data = ComplexScatteredData(training_data.forward_problem, training_data.observed_scattered_response, np.asarray((2.0,)))
    weighted = evaluate_current_domain_topological_derivative(_state_a(), weighted_data, TD_PROBES, geometry_config=production_geometry, solve_config=solve_config)
    weight_error = float(np.max(np.abs(weighted.values - 2.0 * unchunked.values)))
    scaled_problem = _problem(FREQUENCIES_HZ[[0]], 2.0 * SOURCE_STRENGTH)
    scaled_observations = _oracle_response(TRUTH_CENTERS, TRUTH_RADII, FREQUENCIES_HZ[[0]], component_ids=("A", "B"), strength=2.0 * SOURCE_STRENGTH)
    scaled = evaluate_current_domain_topological_derivative(_state_a(), ComplexScatteredData(scaled_problem, scaled_observations), TD_PROBES, geometry_config=production_geometry, solve_config=solve_config)
    scale_error = float(np.max(np.abs(scaled.values - unchunked.values)))
    auxiliary_pass = empty_error <= 0.01 and chunk_error <= 1.0e-11 and weight_error <= 1.0e-11 and scale_error <= 1.0e-10
    g1_pass &= auxiliary_pass
    metrics["gates"]["G1"] = {"pass": bool(g1_pass), "empty_domain_relative_error": empty_error, "chunked_maximum_absolute_difference": chunk_error, "objective_weight_scaling_maximum_error": weight_error, "source_strength_scaling_maximum_error": scale_error, "paired_indices": "declared diagonal only", "reciprocal_source_strength": 1.0}
    _write_csv(output / "g1_td_regression.csv", g1_rows)
    if not g1_pass:
        metrics["outcome"] = "early_hard_gate_failure_G1"
        _write_json(output / "metrics.json", metrics)
        return 2

    # G2: frozen production/refined rasters and connected-region qualification.
    raster_prod, _ = build_td_raster(_state_a(), training_data, num_points=PRODUCTION_RASTER, geometry_config=production_geometry, solve_config=solve_config)
    raster_ref, _ = build_td_raster(_state_a(), training_data, num_points=REFINED_RASTER, geometry_config=refined_geometry, solve_config=solve_config)
    _raster_npz(output / "td_grid_production.npz", raster_prod)
    _raster_npz(output / "td_grid_refined.npz", raster_ref)
    region_records = []
    for name, raster in (("production", raster_prod), ("refined", raster_ref)):
        region_records.append({"resolution": name, "grid_points": len(raster.axis_x), "global_minimum": raster.minimum_value, "minimum_point_m": raster.minimum_point, "minimum_localization_error_m": np.linalg.norm(raster.minimum_point - TRUTH_CENTERS[1]), "region_count": raster.region_count, "centroid_m": raster.selected_centroid, "centroid_error_m": np.linalg.norm(raster.selected_centroid - TRUTH_CENTERS[1]), "area_m2": raster.selected_area_m2, "equivalent_radius_m": raster.equivalent_radius_m, "touches_inspection_boundary": raster.selected_touches_inspection_boundary, "minimum_station_distance_m": raster.minimum_station_distance_m})
    centroid_shift = float(np.linalg.norm(raster_prod.selected_centroid - raster_ref.selected_centroid))
    g2_pass = all(record["region_count"] == 1 and record["minimum_localization_error_m"] <= 0.005 and record["centroid_error_m"] <= 0.005 and record["minimum_station_distance_m"] >= 0.10 - 1.0e-12 and not record["touches_inspection_boundary"] for record in region_records) and centroid_shift <= 0.005
    metrics["gates"]["G2"] = {"pass": bool(g2_pass), "production_refined_centroid_shift_m": centroid_shift, "rasters": region_records}
    _write_json(output / "td_regions.json", metrics["gates"]["G2"])
    if not g2_pass:
        metrics["outcome"] = "early_hard_gate_failure_G2"
        _write_json(output / "metrics.json", metrics)
        return 2

    # G3: a finite TD-only birth scored by the real objective at both grids.
    birth = evaluate_birth_ladder(_state_a(), training_data, seed_center=raster_prod.selected_centroid, equivalent_radius_m=raster_prod.equivalent_radius_m, production_geometry_config=production_geometry, refined_geometry_config=refined_geometry, solve_config=solve_config)
    birth_rows = [trial.__dict__ | {"state": None if trial.state is None else trial.state.parameter_vector().tolist()} for trial in birth.trials]
    _write_csv(output / "birth_trials.csv", birth_rows)
    g3_pass = birth.selected_state is not None and g2_pass
    metrics["gates"]["G3"] = {"pass": bool(g3_pass), "stop_reason": birth.stop_reason, "trials": birth_rows}
    if not g3_pass:
        metrics["outcome"] = "early_hard_gate_failure_G3"
        _write_json(output / "metrics.json", metrics)
        return 2

    # G4: restart and optimize both K=1 components at training frequency only.
    assert birth.selected_state is not None
    t3 = run_multiradial_fd_inverse(birth.selected_state, training_data, production_geometry, solve_config=solve_config, config=iteration01_optimizer_config(), progress_callback=lambda item: print(f"T3 accepted {item.iteration:02d}: J={item.loss:.6e}, rel={item.relative_l2_error:.6e}"))
    _write_csv(output / "t3_trajectory.csv", _trajectory_rows(t3, phase="two_component_refinement"))
    final_prod = evaluate_multiradial_objective(t3.final_state, training_data, production_geometry, solve_config=solve_config)
    final_ref = evaluate_multiradial_objective(t3.final_state, training_data, refined_geometry, solve_config=solve_config)
    final_boundary = t3.final_state.boundary(production_geometry)
    final_all = predict_multicomponent_kress_paired_boundary_response(final_boundary, _problem(FREQUENCIES_HZ), solve_config=solve_config).scattered_response
    holdouts = {f"{frequency / 1e9:.2f}_GHz": _relative_error(final_all[:, index], observations[:, index]) for index, frequency in enumerate(FREQUENCIES_HZ[1:], start=1)}
    geometry_rows, geometry_pass = _state_geometry_metrics(t3.final_state, 0.002)
    monotone = all(later.loss < earlier.loss for earlier, later in zip(t3.iterations, t3.iterations[1:]))
    objective_resolution_difference = abs(final_prod.loss - final_ref.loss) / max(abs(final_ref.loss), 1.0e-12)
    g4_pass = monotone and final_prod.relative_l2_error <= 0.02 and geometry_pass and all(value <= 0.05 for value in holdouts.values()) and objective_resolution_difference <= 1.0e-3
    metrics["gates"]["G4"] = {"pass": bool(g4_pass), "stop_reason": t3.stop_reason, "accepted_objective_monotone": monotone, "training_relative_l2": final_prod.relative_l2_error, "refined_training_relative_l2": final_ref.relative_l2_error, "production_refined_objective_relative_difference": objective_resolution_difference, "holdout_relative_l2": holdouts, "geometry": geometry_rows}
    if not g4_pass:
        metrics["outcome"] = "early_hard_gate_failure_G4"
        _write_csv(output / "field_metrics.csv", [{"stage": "T3", "training_relative_l2": final_prod.relative_l2_error, **holdouts}])
        _write_csv(output / "geometry_metrics.csv", geometry_rows)
        _write_json(output / "metrics.json", metrics)
        return 2

    # G5: the one predeclared 10-mm wrong-A robustness qualification.
    t4_pre = run_multiradial_fd_inverse(_state_a(wrong=True), training_data, production_geometry, solve_config=solve_config, config=iteration01_optimizer_config(), progress_callback=lambda item: print(f"T4 pre accepted {item.iteration:02d}: J={item.loss:.6e}, rel={item.relative_l2_error:.6e}"))
    t4_raster, _ = build_td_raster(t4_pre.final_state, training_data, num_points=PRODUCTION_RASTER, geometry_config=production_geometry, solve_config=solve_config)
    t4_centroid_in_b = float(np.linalg.norm(t4_raster.selected_centroid - TRUTH_CENTERS[1])) <= TRUTH_RADII[1]
    t4_birth = evaluate_birth_ladder(t4_pre.final_state, training_data, seed_center=t4_raster.selected_centroid, equivalent_radius_m=t4_raster.equivalent_radius_m, production_geometry_config=production_geometry, refined_geometry_config=refined_geometry, solve_config=solve_config, component_id="td_birth_001")
    t4_refinement = None
    t4_geometry_rows: list[dict[str, Any]] = []
    t4_holdouts: dict[str, float] = {}
    g5_pass = False
    if t4_birth.selected_state is not None:
        t4_refinement = run_multiradial_fd_inverse(t4_birth.selected_state, training_data, production_geometry, solve_config=solve_config, config=iteration01_optimizer_config(), progress_callback=lambda item: print(f"T4 post accepted {item.iteration:02d}: J={item.loss:.6e}, rel={item.relative_l2_error:.6e}"))
        t4_final = evaluate_multiradial_objective(t4_refinement.final_state, training_data, production_geometry, solve_config=solve_config)
        t4_all = predict_multicomponent_kress_paired_boundary_response(t4_refinement.final_state.boundary(production_geometry), _problem(FREQUENCIES_HZ), solve_config=solve_config).scattered_response
        t4_holdouts = {f"{frequency / 1e9:.2f}_GHz": _relative_error(t4_all[:, index], observations[:, index]) for index, frequency in enumerate(FREQUENCIES_HZ[1:], start=1)}
        t4_geometry_rows, t4_geometry_pass = _state_geometry_metrics(t4_refinement.final_state, 0.003)
        g5_pass = t4_centroid_in_b and t4_raster.region_count == 1 and t4_final.relative_l2_error <= 0.02 and t4_geometry_pass and all(value <= 0.05 for value in t4_holdouts.values())
    t4_rows = _trajectory_rows(t4_pre, phase="one_component_pre_stage")
    if t4_refinement is not None:
        t4_rows.extend(_trajectory_rows(t4_refinement, phase="two_component_refinement"))
    _write_csv(output / "t4_trajectory.csv", t4_rows)
    metrics["gates"]["G5"] = {"pass": bool(g5_pass), "centroid_inside_true_B": bool(t4_centroid_in_b), "threshold_region_count": t4_raster.region_count, "birth_stop_reason": t4_birth.stop_reason, "pre_stage_stop_reason": t4_pre.stop_reason, "post_stage_stop_reason": None if t4_refinement is None else t4_refinement.stop_reason, "holdout_relative_l2": t4_holdouts, "geometry": t4_geometry_rows}
    metrics["outcome"] = "full_pass" if g5_pass else "core_pass_robustness_failure"

    field_rows = [{"stage": "T3", "training_relative_l2": final_prod.relative_l2_error, **holdouts}]
    if t4_refinement is not None:
        field_rows.append({"stage": "T4", "training_relative_l2": t4_refinement.iterations[-1].relative_l2_error, **t4_holdouts})
    _write_csv(output / "field_metrics.csv", field_rows)
    _write_csv(output / "geometry_metrics.csv", [dict(stage="T3", **row) for row in geometry_rows] + [dict(stage="T4", **row) for row in t4_geometry_rows])

    _plot_artifacts(output, raster_prod, raster_ref, birth, t3, (t4_pre.iterations, t4_refinement))
    t3_states = [_state_a(), birth.selected_state] + [item.state for item in t3.iterations[1:]]
    t3_labels = ["Initial current domain", "TD birth accepted"] + [f"Two-component LM iterate {item.iteration}" for item in t3.iterations[1:]]
    t3_losses = [birth.production_base_loss, birth.trials[0].production_loss] + [item.loss for item in t3.iterations[1:]]
    _render_video(output / "t3_one_circle_to_two_circles.mp4", t3_states, t3_labels, [float(value) for value in t3_losses])
    if t4_birth.selected_state is not None and t4_refinement is not None:
        t4_states = [item.state for item in t4_pre.iterations] + [t4_birth.selected_state] + [item.state for item in t4_refinement.iterations[1:]]
        t4_labels = [f"Wrong-A pre-stage iterate {item.iteration}" for item in t4_pre.iterations] + ["TD birth accepted"] + [f"Two-component LM iterate {item.iteration}" for item in t4_refinement.iterations[1:]]
        chosen = min((trial for trial in t4_birth.trials if trial.accepted), key=lambda item: float(item.production_loss))
        t4_losses = [item.loss for item in t4_pre.iterations] + [float(chosen.production_loss)] + [item.loss for item in t4_refinement.iterations[1:]]
        _render_video(output / "t4_wrong_circle_to_two_circles.mp4", t4_states, t4_labels, t4_losses)

    readme = f"""# Radial-Fourier topology birth — iteration 01 execution

Outcome: **{metrics['outcome']}**.

This bundle separates four evidence classes: the saved oracle-only TD values
used by G1; new direct multi-component Kress forward/TD evidence in G0--G3;
optimization evidence in the T3/T4 trajectories; and truth-based qualification
metrics in `field_metrics.csv` and `geometry_metrics.csv`.  Only 0.50 GHz was
used for training and topology decisions.  The 1.50/2.50 GHz values are
holdouts and were not fed back into the inversion.

G0--G4 passed.  T4 ran and {'passed' if g5_pass else 'did not pass'} G5.  See
`metrics.json` for the exact gate record and the two MP4 files for the accepted
one-circle-to-two-circle inversion trajectories.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    _write_json(output / "metrics.json", metrics)
    print(f"Outcome: {metrics['outcome']}")
    print(f"Artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
