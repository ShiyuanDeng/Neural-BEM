"""Run the canonical single-circle IBIM inverse case on a rectangular scan loop."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover - fallback for minimal environments
    tqdm = None

import sys
from pathlib import Path

# Pick the solver before importing it: `gpr_bem` below is whichever package
# --solver selects out of solvers/. Defaults to the frozen reference.
sys.path.insert(0, str(Path(__file__).resolve().parent / "solvers"))
import solver_select

SELECTED_SOLVER = solver_select.resolve_from_argv()
SELECTED_SOLVER_PACKAGE = solver_select.alias_as_gpr_bem(SELECTED_SOLVER)

from config import simulation_config as cfg
from gpr_bem import (
    Material,
    RectangularLoopScan2D,
    SirenSDF2D,
    bscan_from_frequency_response,
    build_implicit_boundary_samples,
    build_rectangular_bistatic_scan,
    circle_signed_distance,
    solve_ibim_tmz_total_field_batch,
    subset_rectangular_loop_scan,
)
from gpr_bem.ibim_inverse import (
    build_single_circle_bscan_benchmark_config,
    build_single_circle_bscan_benchmark_stage_schedule,
    compute_boundary_geometry_metrics,
    compute_bscan_quality_metrics,
    run_ibim_bscan_inverse,
)
from gpr_bem_mod.ibim_inverse import resolve_ibim_assembly_backend
from gpr_bem.waveforms import gprmax_gaussian_spectrum

TRUTH_CACHE_NAME = "rectangular_loop_truth.npz"
OVERVIEW_FIGURE_NAME = "ibim_circle_inverse_rectangular_scan_overview.png"
TRAJECTORY_FIGURE_NAME = "ibim_circle_inverse_rectangular_scan_trajectory.png"
TIMING_FIGURE_NAME = "ibim_circle_inverse_rectangular_scan_timing.png"
DATA_BUNDLE_NAME = "ibim_circle_inverse_rectangular_scan_data.npz"


def _build_scan() -> RectangularLoopScan2D:
    return build_rectangular_bistatic_scan(
        left=float(cfg.SCAN_RECT_LEFT),
        right=float(cfg.SCAN_RECT_RIGHT),
        top=float(cfg.SCAN_RECT_TOP),
        bottom=float(cfg.SCAN_RECT_BOTTOM),
        separation=float(cfg.TX_RX_OFFSET),
        top_count=int(cfg.SCAN_RECT_TOP_COUNT),
        right_count=int(cfg.SCAN_RECT_RIGHT_COUNT),
        bottom_count=int(cfg.SCAN_RECT_BOTTOM_COUNT),
        left_count=int(cfg.SCAN_RECT_LEFT_COUNT),
    )


def _build_time_vector() -> np.ndarray:
    return np.linspace(0.0, float(cfg.TIME_WINDOW), int(cfg.NUM_TIME_SAMPLES), dtype=float)


def _build_angular_frequencies() -> np.ndarray:
    frequencies_hz = np.linspace(float(cfg.FREQ_MIN), float(cfg.FREQ_MAX), int(cfg.NUM_FREQS), dtype=float)
    return 2.0 * np.pi * frequencies_hz


def _build_frequency_window(num_frequencies: int) -> np.ndarray:
    window_kind = str(cfg.FREQUENCY_WINDOW).strip().lower()
    if window_kind == "none":
        return np.ones(int(num_frequencies), dtype=float)
    if window_kind == "hann":
        return np.hanning(int(num_frequencies))
    if window_kind == "tukey":
        return _tukey_window(int(num_frequencies), alpha=float(cfg.FREQUENCY_WINDOW_ALPHA))
    raise ValueError(f"Unsupported FREQUENCY_WINDOW={cfg.FREQUENCY_WINDOW!r}")


def _tukey_window(num_frequencies: int, *, alpha: float) -> np.ndarray:
    count = int(num_frequencies)
    if count < 1:
        raise ValueError("num_frequencies must be positive.")
    if alpha <= 0.0:
        return np.ones(count, dtype=float)
    if alpha >= 1.0:
        return np.hanning(count)
    window = np.ones(count, dtype=float)
    points = np.linspace(0.0, 1.0, count, dtype=float)
    head = points < 0.5 * alpha
    tail = points > 1.0 - 0.5 * alpha
    window[head] = 0.5 * (1.0 + np.cos(np.pi * ((2.0 * points[head] / alpha) - 1.0)))
    window[tail] = 0.5 * (1.0 + np.cos(np.pi * ((2.0 * points[tail] / alpha) - (2.0 / alpha) + 1.0)))
    return window


def _build_source_strengths(angular_frequencies: np.ndarray) -> np.ndarray:
    frequencies = np.asarray(angular_frequencies, dtype=float)
    return (
        1j
        * frequencies
        * float(cfg.MU0)
        * gprmax_gaussian_spectrum(frequencies, center_frequency=float(cfg.CENTER_FREQ))
    ).astype(np.complex128)


def _build_truth_boundary():
    return build_implicit_boundary_samples(
        lambda points: circle_signed_distance(
            points,
            center=(float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y)),
            radius=float(cfg.TARGET_RADIUS),
        ),
        ((0.0, 0.0), (float(cfg.DOMAIN_WIDTH), float(cfg.DOMAIN_HEIGHT))),
        grid_shape=(257, 257),
        band_half_width=0.06,
        delta_half_width=0.03,
        merge_distance=0.01,
        dtype=torch.float64,
    )


def _compute_frequency_response(
    boundary,
    scan: RectangularLoopScan2D,
    angular_frequencies: np.ndarray,
    source_strengths: np.ndarray,
    *,
    exterior: Material,
    interior: Material,
    offset_distance: float | None,
    use_strict_quadrature: bool,
    backend: str,
    progress_label: str | None = None,
) -> np.ndarray:
    frequency_array = np.asarray(angular_frequencies, dtype=float).reshape(-1)
    strength_array = np.asarray(source_strengths, dtype=np.complex128).reshape(-1)
    if strength_array.shape != frequency_array.shape:
        raise ValueError("source_strengths must contain one value per angular frequency.")

    iterator = range(frequency_array.size)
    progress = None
    if tqdm is not None and frequency_array.size > 1:
        progress = tqdm(iterator, desc=progress_label or "frequency solve", leave=False, dynamic_ncols=True)
        iterator = progress

    responses = []
    try:
        for index in iterator:
            forward = solve_ibim_tmz_total_field_batch(
                boundary,
                scan.source_points,
                scan.receiver_points,
                float(frequency_array[index]),
                complex(strength_array[index]),
                exterior=exterior,
                interior=interior,
                eps0=float(cfg.EPS0),
                mu0=float(cfg.MU0),
                offset_distance=offset_distance,
                use_strict_quadrature=use_strict_quadrature,
                backend=backend,
            )
            responses.append(np.asarray(forward.total_receiver, dtype=np.complex128))
    finally:
        if progress is not None:
            progress.close()
    return np.stack(responses, axis=1).astype(np.complex128)


def _load_truth_cache(
    cache_path: Path,
    *,
    scan: RectangularLoopScan2D,
    angular_frequencies: np.ndarray,
    time_vector: np.ndarray,
    frequency_window: np.ndarray,
) -> dict[str, np.ndarray] | None:
    if not cache_path.exists():
        return None
    with np.load(cache_path) as cached:
        required_keys = {
            "source_points",
            "receiver_points",
            "angular_frequencies",
            "time_vector",
            "frequency_window",
            "frequency_response_raw",
        }
        if not required_keys.issubset(set(cached.files)):
            return None
        if not _allclose_or_same(cached["source_points"], scan.source_points):
            return None
        if not _allclose_or_same(cached["receiver_points"], scan.receiver_points):
            return None
        if not _allclose_or_same(cached["angular_frequencies"], angular_frequencies):
            return None
        if not _allclose_or_same(cached["time_vector"], time_vector):
            return None
        if not _allclose_or_same(cached["frequency_window"], frequency_window):
            return None
        return {
            "time_vector": np.asarray(cached["time_vector"], dtype=float),
            "angular_frequencies": np.asarray(cached["angular_frequencies"], dtype=float),
            "frequency_window": np.asarray(cached["frequency_window"], dtype=float),
            "frequency_response_raw": np.asarray(cached["frequency_response_raw"], dtype=np.complex128),
        }


def _allclose_or_same(left: np.ndarray, right: np.ndarray) -> bool:
    return bool(np.shape(left) == np.shape(right) and np.allclose(left, right, rtol=0.0, atol=1.0e-12))


def _load_or_build_truth(
    *,
    output_dir: Path,
    scan: RectangularLoopScan2D,
    angular_frequencies: np.ndarray,
    time_vector: np.ndarray,
    frequency_window: np.ndarray,
    source_strengths: np.ndarray,
    exterior: Material,
    interior: Material,
    offset_distance: float | None,
    use_strict_quadrature: bool,
    backend: str,
) -> dict[str, np.ndarray]:
    cache_path = output_dir / TRUTH_CACHE_NAME
    cached = _load_truth_cache(
        cache_path,
        scan=scan,
        angular_frequencies=angular_frequencies,
        time_vector=time_vector,
        frequency_window=frequency_window,
    )
    if cached is not None:
        print(f"loaded cached rectangular-loop truth from {cache_path}", flush=True)
        return cached

    truth_boundary = _build_truth_boundary()
    frequency_response_raw = _compute_frequency_response(
        truth_boundary,
        scan,
        angular_frequencies,
        source_strengths,
        exterior=exterior,
        interior=interior,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        backend=backend,
        progress_label="truth data",
    )
    np.savez(
        cache_path,
        source_points=scan.source_points,
        receiver_points=scan.receiver_points,
        center_points=scan.center_points,
        tangents=scan.tangents,
        path_coordinate=scan.path_coordinate,
        edge_index=scan.edge_index,
        edge_boundaries=scan.edge_boundaries,
        rectangle_vertices=scan.rectangle_vertices,
        time_vector=time_vector,
        angular_frequencies=angular_frequencies,
        frequency_window=frequency_window,
        frequency_response_raw=frequency_response_raw,
    )
    print(f"built rectangular-loop truth and cached it at {cache_path}", flush=True)
    return {
        "time_vector": np.asarray(time_vector, dtype=float),
        "angular_frequencies": np.asarray(angular_frequencies, dtype=float),
        "frequency_window": np.asarray(frequency_window, dtype=float),
        "frequency_response_raw": np.asarray(frequency_response_raw, dtype=np.complex128),
    }


def _sort_boundary_points(points: np.ndarray) -> np.ndarray:
    point_array = np.asarray(points, dtype=float)
    center = np.mean(point_array, axis=0)
    angles = np.arctan2(point_array[:, 1] - center[1], point_array[:, 0] - center[0])
    order = np.argsort(angles)
    ordered = point_array[order]
    return np.vstack((ordered, ordered[0]))


def _build_late_time_weights(
    time_vector: np.ndarray,
    *,
    gate_start: float,
    late_weight_max: float = 4.0,
) -> np.ndarray:
    time_values = np.asarray(time_vector, dtype=float)
    weights = np.ones_like(time_values)
    gate_mask = time_values >= float(gate_start)
    if np.any(gate_mask):
        gate_fraction = np.linspace(0.0, 1.0, int(np.count_nonzero(gate_mask)), dtype=float)
        weights[gate_mask] = 1.0 + (float(late_weight_max) - 1.0) * gate_fraction
    return weights


def _build_frequency_indices(num_frequencies: int, num_selected: int) -> np.ndarray:
    return np.linspace(0, num_frequencies - 1, num_selected, dtype=int)


def _sample_edges(values: np.ndarray) -> np.ndarray:
    samples = np.asarray(values, dtype=float).reshape(-1)
    if samples.size == 0:
        raise ValueError("values must not be empty.")
    if samples.size == 1:
        return np.array([samples[0] - 0.5, samples[0] + 0.5], dtype=float)
    edges = np.empty(samples.size + 1, dtype=float)
    edges[1:-1] = 0.5 * (samples[:-1] + samples[1:])
    edges[0] = samples[0] - 0.5 * (samples[1] - samples[0])
    edges[-1] = samples[-1] + 0.5 * (samples[-1] - samples[-2])
    return edges


def _late_time_slice(bscan: np.ndarray, time_vector: np.ndarray, *, gate_start: float) -> tuple[np.ndarray, np.ndarray]:
    mask = np.asarray(time_vector, dtype=float) >= float(gate_start)
    if not np.any(mask):
        raise ValueError("The late-time gate removed all samples.")
    return np.asarray(bscan, dtype=float)[:, mask], np.asarray(time_vector, dtype=float)[mask]


def _plot_bscan(
    ax,
    bscan: np.ndarray,
    scan_coordinate: np.ndarray,
    time_vector: np.ndarray,
    title: str,
    *,
    amplitude: float,
    label: str,
    edge_boundaries: np.ndarray,
    gate_start: float,
) -> None:
    x_edges = _sample_edges(scan_coordinate)
    y_values_ns = np.asarray(time_vector, dtype=float) * 1.0e9
    y_edges = _sample_edges(y_values_ns)
    mesh = ax.pcolormesh(
        x_edges,
        y_edges,
        np.asarray(bscan, dtype=float).T,
        shading="auto",
        cmap="seismic",
        vmin=-float(amplitude),
        vmax=float(amplitude),
    )
    for boundary in np.asarray(edge_boundaries, dtype=float).reshape(-1):
        ax.axvline(boundary, color="0.1", linestyle="--", linewidth=0.9, alpha=0.65)
    ax.axhline(float(gate_start) * 1.0e9, color="k", linestyle="--", linewidth=1.0, alpha=0.85)
    ax.set_title(title)
    ax.set_xlabel("Scan coordinate s (m)")
    ax.set_ylabel("Time (ns)")
    ax.invert_yaxis()
    plt.colorbar(mesh, ax=ax, label=label)


def _plot_scan_trajectory(
    ax,
    *,
    scan: RectangularLoopScan2D,
    true_curve: list[np.ndarray],
    reconstructed_curve: list[np.ndarray] | None,
    title: str,
) -> None:
    ax.plot(
        scan.rectangle_vertices[:, 0],
        scan.rectangle_vertices[:, 1],
        linestyle="--",
        color="0.35",
        linewidth=1.8,
        label="scan path",
    )
    for curve in true_curve:
        ax.plot(curve[:, 0], curve[:, 1], color="#111111", linewidth=2.4, label="true geometry")
    if reconstructed_curve is not None:
        for index, curve in enumerate(reconstructed_curve):
            ax.plot(
                curve[:, 0],
                curve[:, 1],
                color="#D55E00",
                linewidth=2.0,
                alpha=0.9,
                label="reconstructed" if index == 0 else None,
            )
    scatter = ax.scatter(
        scan.center_points[:, 0],
        scan.center_points[:, 1],
        c=scan.path_coordinate,
        cmap="viridis",
        s=22,
        zorder=3,
        label="scan centers",
    )
    marker_stride = max(1, scan.center_points.shape[0] // 12)
    ax.scatter(
        scan.source_points[::marker_stride, 0],
        scan.source_points[::marker_stride, 1],
        marker="^",
        s=38,
        color="#D55E00",
        zorder=4,
        label="Tx",
    )
    ax.scatter(
        scan.receiver_points[::marker_stride, 0],
        scan.receiver_points[::marker_stride, 1],
        marker="s",
        s=34,
        color="#0072B2",
        zorder=4,
        label="Rx",
    )
    ax.quiver(
        scan.center_points[::marker_stride, 0],
        scan.center_points[::marker_stride, 1],
        scan.tangents[::marker_stride, 0],
        scan.tangents[::marker_stride, 1],
        angles="xy",
        scale_units="xy",
        scale=18.0,
        width=0.004,
        color="0.2",
        alpha=0.55,
        zorder=2,
    )
    ax.scatter(
        scan.center_points[0, 0],
        scan.center_points[0, 1],
        marker="*",
        s=120,
        color="#009E73",
        edgecolors="white",
        linewidths=0.9,
        zorder=5,
        label="start",
    )
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal", adjustable="box")
    x_pad = 0.08
    y_pad = 0.08
    ax.set_xlim(float(cfg.SCAN_RECT_LEFT) - x_pad, float(cfg.SCAN_RECT_RIGHT) + x_pad)
    ax.set_ylim(float(cfg.SCAN_RECT_BOTTOM) + y_pad, float(cfg.SCAN_RECT_TOP) - y_pad)
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.legend(loc="upper right", fontsize=8)
    plt.colorbar(scatter, ax=ax, label="Scan coordinate s (m)")


def _plot_loss_panel(
    ax,
    *,
    iterations,
    quality_metrics: dict[str, float],
    geometry_metrics: dict[str, float],
    stage_schedule: tuple[tuple[int, int, float], ...],
    stage_boundaries: np.ndarray,
    initial_boundary_count: int,
    final_boundary_count: int,
    position_stride: int,
    inverse_scan_count: int,
    display_scan_count: int,
    device_label: str,
) -> None:
    losses = np.asarray([iteration.bscan_loss for iteration in iterations], dtype=float)
    ax.plot(np.arange(losses.size), losses, linewidth=2.0, color="#0072B2")
    for boundary in np.asarray(stage_boundaries, dtype=int).reshape(-1):
        ax.axvline(boundary, color="0.5", linestyle="--", linewidth=1.0, alpha=0.75)
    ax.set_title("Inverse Loss")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("B-scan loss")
    ax.set_yscale("log")
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.text(
        0.03,
        0.03,
        "\n".join(
            [
                f"rel err all: {quality_metrics['relative_error_all']:.3e}",
                f"rel err >=2ns: {quality_metrics['relative_error_gate']:.3e}",
                f"corr all: {quality_metrics['correlation_all']:.3e}",
                f"corr >=2ns: {quality_metrics['correlation_gate']:.3e}",
                f"boundary pts init/final: {initial_boundary_count}/{final_boundary_count}",
                f"mean radius: {geometry_metrics['mean_radius']:.4f}",
                f"perimeter: {geometry_metrics['perimeter']:.4f}",
                f"device: {device_label}",
                f"inverse scan count: {inverse_scan_count}",
                f"display scan count: {display_scan_count}",
                f"inverse scan stride: {position_stride}",
                f"schedule: {','.join(str(item[0]) for item in stage_schedule)} freqs",
            ]
        ),
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "0.7"},
    )


def _plot_timing_breakdown(ax, iterations) -> None:
    iteration_ids = np.arange(len(iterations), dtype=int)
    ax.plot(iteration_ids, [it.timing["iteration_time_s"] for it in iterations], label="iteration", linewidth=2.0)
    ax.plot(iteration_ids, [it.timing["ibim_total_time_s"] for it in iterations], label="ibim total", linewidth=2.0)
    ax.plot(iteration_ids, [it.timing["geometry_time_s"] for it in iterations], label="geometry", linewidth=1.8)
    ax.plot(iteration_ids, [it.timing["adjoint_context_time_s"] for it in iterations], label="forward", linewidth=1.8)
    ax.plot(iteration_ids, [it.timing["shape_gradient_time_s"] for it in iterations], label="gradient", linewidth=1.8)
    ax.plot(iteration_ids, [it.timing["regularization_time_s"] for it in iterations], label="regularization", linewidth=1.8)
    ax.plot(iteration_ids, [it.timing["nn_update_time_s"] for it in iterations], label="update", linewidth=1.8)
    ax.set_title("Timing Breakdown")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Seconds")
    ax.set_yscale("log")
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.legend(loc="best", fontsize=8)


def _plot_results(
    *,
    output_dir: Path,
    scan: RectangularLoopScan2D,
    time_vector: np.ndarray,
    gate_start: float,
    true_bscan: np.ndarray,
    predicted_bscan: np.ndarray,
    true_curve: list[np.ndarray],
    reconstructed_curve: list[np.ndarray],
    iterations,
    quality_metrics: dict[str, float],
    geometry_metrics: dict[str, float],
    stage_schedule: tuple[tuple[int, int, float], ...],
    stage_boundaries: np.ndarray,
    initial_boundary_count: int,
    final_boundary_count: int,
    position_stride: int,
    inverse_scan_count: int,
    device_label: str,
    timing_path: Path,
) -> None:
    error_bscan = np.asarray(predicted_bscan, dtype=float) - np.asarray(true_bscan, dtype=float)
    amplitude = max(float(np.percentile(np.abs(true_bscan), 99.5)), 1.0e-6)
    error_amplitude = max(float(np.percentile(np.abs(error_bscan), 99.5)), 1.0e-6)
    true_bscan_late, time_vector_late = _late_time_slice(true_bscan, time_vector, gate_start=gate_start)
    predicted_bscan_late, _ = _late_time_slice(predicted_bscan, time_vector, gate_start=gate_start)
    error_bscan_late, _ = _late_time_slice(error_bscan, time_vector, gate_start=gate_start)

    overview, axes = plt.subplots(2, 4, figsize=(22, 10), constrained_layout=True)
    _plot_scan_trajectory(
        axes[0, 0],
        scan=scan,
        true_curve=true_curve,
        reconstructed_curve=reconstructed_curve,
        title="Rectangular Scan Trajectory",
    )
    _plot_bscan(
        axes[0, 1],
        true_bscan,
        scan.path_coordinate,
        time_vector,
        "True B-scan",
        amplitude=amplitude,
        label="Ez amplitude",
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        axes[0, 2],
        predicted_bscan,
        scan.path_coordinate,
        time_vector,
        "Predicted B-scan",
        amplitude=amplitude,
        label="Ez amplitude",
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        axes[0, 3],
        error_bscan,
        scan.path_coordinate,
        time_vector,
        "B-scan Error",
        amplitude=error_amplitude,
        label="Prediction - truth",
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_loss_panel(
        axes[1, 0],
        iterations=iterations,
        quality_metrics=quality_metrics,
        geometry_metrics=geometry_metrics,
        stage_schedule=stage_schedule,
        stage_boundaries=stage_boundaries,
        initial_boundary_count=initial_boundary_count,
        final_boundary_count=final_boundary_count,
        position_stride=position_stride,
        inverse_scan_count=inverse_scan_count,
        display_scan_count=scan.center_points.shape[0],
        device_label=device_label,
    )
    _plot_bscan(
        axes[1, 1],
        true_bscan_late,
        scan.path_coordinate,
        time_vector_late,
        "True B-scan (t >= 2 ns)",
        amplitude=amplitude,
        label="Ez amplitude",
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        axes[1, 2],
        predicted_bscan_late,
        scan.path_coordinate,
        time_vector_late,
        "Predicted B-scan (t >= 2 ns)",
        amplitude=amplitude,
        label="Ez amplitude",
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        axes[1, 3],
        error_bscan_late,
        scan.path_coordinate,
        time_vector_late,
        "B-scan Error (t >= 2 ns)",
        amplitude=error_amplitude,
        label="Prediction - truth",
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    overview.savefig(output_dir / OVERVIEW_FIGURE_NAME, dpi=180)
    plt.close(overview)

    trajectory_figure, trajectory_ax = plt.subplots(figsize=(8.5, 7.0), constrained_layout=True)
    _plot_scan_trajectory(
        trajectory_ax,
        scan=scan,
        true_curve=true_curve,
        reconstructed_curve=reconstructed_curve,
        title="Rectangular Scan and Reconstructed Geometry",
    )
    trajectory_figure.savefig(output_dir / TRAJECTORY_FIGURE_NAME, dpi=180)
    plt.close(trajectory_figure)

    timing_figure, timing_ax = plt.subplots(figsize=(12, 6))
    _plot_timing_breakdown(timing_ax, iterations)
    timing_ax.set_title("Rectangular Scan Timing Breakdown")
    timing_figure.tight_layout()
    timing_figure.savefig(timing_path, dpi=180)
    plt.close(timing_figure)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the single-circle IBIM inverse on the rectangular-loop scan case.")
    parser.add_argument(
        "--solver",
        choices=sorted(solver_select.SOLVER_NAMES),
        default=SELECTED_SOLVER,
        help="Which solver package under solvers/ to run. Resolved at import time.",
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="PyTorch device to use. Defaults to cuda when available.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/ibim_circle_inverse_rectangular_scan",
        help="Directory where figures, cached truth data, and npz artifacts will be written.",
    )
    parser.add_argument(
        "--scan-stride",
        type=int,
        default=None,
        help="Override the inverse-loop down-sampling stride. Display figures always use the full rectangular scan.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    full_scan = _build_scan()
    time_vector = _build_time_vector()
    angular_frequencies_full = _build_angular_frequencies()
    frequency_window_full = _build_frequency_window(angular_frequencies_full.size)
    source_strength_full = _build_source_strengths(angular_frequencies_full)

    requested_device = torch.device(args.device)
    resolved_device = requested_device
    if requested_device.type == "cuda" and not torch.cuda.is_available():
        resolved_device = torch.device("cpu")
        print("requested cuda device unavailable; falling back to cpu", flush=True)

    base_config = build_single_circle_bscan_benchmark_config(device=resolved_device.type)
    position_stride = max(1, int(args.scan_stride or base_config.scan_position_stride))
    position_indices = np.arange(0, full_scan.center_points.shape[0], position_stride, dtype=int)
    inverse_scan = subset_rectangular_loop_scan(full_scan, position_indices)

    config = replace(
        base_config,
        bscan_time_weights=_build_late_time_weights(
            time_vector,
            gate_start=float(cfg.SCAN_GATE_START),
            late_weight_max=4.0,
        ),
        scan_position_stride=position_stride,
    )
    model = SirenSDF2D(hidden_features=64, hidden_layers=2)

    exterior = Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    device = torch.device(config.device)
    backend = resolve_ibim_assembly_backend(device)
    if device.type == "cuda" and backend == "numpy":
        print(
            "PyTorch is using CUDA, but CuPy could not be imported; "
            "BEM assembly and solves will use NumPy on CPU.",
            flush=True,
        )

    truth = _load_or_build_truth(
        output_dir=output_dir,
        scan=full_scan,
        angular_frequencies=angular_frequencies_full,
        time_vector=time_vector,
        frequency_window=frequency_window_full,
        source_strengths=source_strength_full,
        exterior=exterior,
        interior=interior,
        offset_distance=config.offset_distance,
        use_strict_quadrature=config.use_strict_quadrature,
        backend=backend,
    )

    stage_schedule = build_single_circle_bscan_benchmark_stage_schedule()
    print(
        f"rectangular scan device={device} backend={backend} total_positions={full_scan.center_points.shape[0]} "
        f"inverse_positions={inverse_scan.center_points.shape[0]} stride={position_stride} "
        f"schedule={[item[0] for item in stage_schedule]} num_freqs={angular_frequencies_full.size}",
        flush=True,
    )

    all_iterations = []
    current_config = config
    stage_frequency_indices = []
    stage_truth_bscans = []
    stage_result = None
    first_stage_result = None
    total_iterations = int(sum(step_count for _freqs, step_count, _lr in stage_schedule))
    progress_bar = tqdm(total=total_iterations, desc="IBIM inverse", dynamic_ncols=True) if tqdm is not None else None

    def _progress_callback(current_step: int, total_step: int, stage_label: str, timing: dict[str, float]) -> None:
        if progress_bar is None:
            return
        progress_bar.update(1)
        progress_bar.set_postfix(
            stage=stage_label,
            step=f"{current_step}/{total_step}",
            iteration=f"{timing['iteration_time_s']:.1f}s",
            shape=f"{timing['shape_gradient_time_s']:.1f}s",
        )

    try:
        for stage_index, (num_freqs, num_steps, learning_rate) in enumerate(stage_schedule):
            freq_indices = _build_frequency_indices(angular_frequencies_full.size, num_freqs)
            stage_frequency_indices.append(freq_indices)
            stage_truth_frequency_response = truth["frequency_response_raw"][position_indices][:, freq_indices]
            stage_truth_bscan = bscan_from_frequency_response(
                stage_truth_frequency_response,
                angular_frequencies_full[freq_indices],
                time_vector,
                frequency_window=frequency_window_full[freq_indices],
            )
            stage_truth_bscans.append(stage_truth_bscan)
            stage_config = replace(
                current_config,
                num_inverse_steps=num_steps,
                inverse_learning_rate=learning_rate,
                reinitialize_model=(stage_index == 0),
            )
            stage_label = f"stage {stage_index + 1}/{len(stage_schedule)} | {num_freqs} freqs"
            stage_result = run_ibim_bscan_inverse(
                model,
                source_points=inverse_scan.source_points,
                receiver_points=inverse_scan.receiver_points,
                angular_frequencies=angular_frequencies_full[freq_indices],
                source_strength=source_strength_full[freq_indices],
                observed_bscan=stage_truth_bscan,
                time_vector=time_vector,
                config=stage_config,
                exterior=exterior,
                interior=interior,
                eps0=cfg.EPS0,
                mu0=cfg.MU0,
                frequency_window=frequency_window_full[freq_indices],
                initial_circle_center=(cfg.TARGET_CENTER_X, cfg.TARGET_CENTER_Y),
                initial_circle_radius=cfg.TARGET_RADIUS * 1.02,
                progress_callback=_progress_callback,
                progress_label=stage_label,
            )
            if first_stage_result is None:
                first_stage_result = stage_result
            offset = len(all_iterations)
            for iteration in stage_result.iterations:
                all_iterations.append(replace(iteration, iteration=offset + iteration.iteration))
            current_config = replace(current_config, reinitialize_model=False)
    finally:
        if progress_bar is not None:
            progress_bar.close()

    assert stage_result is not None
    assert first_stage_result is not None

    display_stage_index = len(stage_frequency_indices) - 1
    final_freq_indices = stage_frequency_indices[display_stage_index]
    display_truth_bscan = bscan_from_frequency_response(
        truth["frequency_response_raw"][:, final_freq_indices],
        angular_frequencies_full[final_freq_indices],
        time_vector,
        frequency_window=frequency_window_full[final_freq_indices],
    )

    final_boundary = build_final_boundary(stage_result, merge_distance=current_config.merge_distance or 0.018)
    predicted_frequency = _compute_frequency_response(
        final_boundary,
        full_scan,
        angular_frequencies_full[final_freq_indices],
        source_strength_full[final_freq_indices],
        exterior=exterior,
        interior=interior,
        offset_distance=current_config.offset_distance,
        use_strict_quadrature=current_config.use_strict_quadrature,
        backend=backend,
        progress_label="display forward",
    )
    predicted_bscan = bscan_from_frequency_response(
        predicted_frequency,
        angular_frequencies_full[final_freq_indices],
        time_vector,
        frequency_window=frequency_window_full[final_freq_indices],
    )

    quality_metrics = compute_bscan_quality_metrics(
        display_truth_bscan,
        predicted_bscan,
        time_vector,
        gate_start=float(cfg.SCAN_GATE_START),
    )
    geometry_metrics = compute_boundary_geometry_metrics(final_boundary.points.detach().cpu().numpy())
    true_curve = [
        np.column_stack(
            (
                cfg.TARGET_CENTER_X + cfg.TARGET_RADIUS * np.cos(np.linspace(0.0, 2.0 * np.pi, 257)),
                cfg.TARGET_CENTER_Y + cfg.TARGET_RADIUS * np.sin(np.linspace(0.0, 2.0 * np.pi, 257)),
            )
        )
    ]
    reconstructed_curve = [_sort_boundary_points(final_boundary.points.detach().cpu().numpy())]
    timing_path = output_dir / TIMING_FIGURE_NAME

    _plot_results(
        output_dir=output_dir,
        scan=full_scan,
        time_vector=time_vector,
        gate_start=float(cfg.SCAN_GATE_START),
        true_bscan=display_truth_bscan,
        predicted_bscan=predicted_bscan,
        true_curve=true_curve,
        reconstructed_curve=reconstructed_curve,
        iterations=all_iterations,
        quality_metrics=quality_metrics,
        geometry_metrics=geometry_metrics,
        stage_schedule=stage_schedule,
        stage_boundaries=np.cumsum([count for _freqs, count, _lr in stage_schedule])[:-1],
        initial_boundary_count=first_stage_result.initial_boundary_points.shape[0],
        final_boundary_count=stage_result.final_boundary_points.shape[0],
        position_stride=position_stride,
        inverse_scan_count=inverse_scan.center_points.shape[0],
        device_label=str(device),
        timing_path=timing_path,
    )

    np.savez(
        output_dir / DATA_BUNDLE_NAME,
        true_bscan=display_truth_bscan,
        predicted_bscan=predicted_bscan,
        error_bscan=predicted_bscan - display_truth_bscan,
        truth_frequency_response=truth["frequency_response_raw"][:, final_freq_indices],
        predicted_frequency_response=predicted_frequency,
        time_vector=time_vector,
        scan_coordinate=full_scan.path_coordinate,
        scan_edge_index=full_scan.edge_index,
        scan_edge_boundaries=full_scan.edge_boundaries,
        scan_center_points=full_scan.center_points,
        source_points=full_scan.source_points,
        receiver_points=full_scan.receiver_points,
        scan_rectangle_vertices=full_scan.rectangle_vertices,
        inverse_position_indices=position_indices,
        stage_frequency_indices=np.array(stage_frequency_indices, dtype=object),
        stage_truth_bscans=np.stack(stage_truth_bscans, axis=0),
        initial_boundary_points=first_stage_result.initial_boundary_points,
        final_boundary_points=stage_result.final_boundary_points,
        losses=np.asarray([iteration.bscan_loss for iteration in all_iterations], dtype=float),
        relative_error_all=np.asarray(quality_metrics["relative_error_all"]),
        relative_error_gate=np.asarray(quality_metrics["relative_error_gate"]),
        correlation_all=np.asarray(quality_metrics["correlation_all"]),
        correlation_gate=np.asarray(quality_metrics["correlation_gate"]),
        initial_boundary_measure=np.asarray(first_stage_result.initial_boundary_points.shape[0], dtype=float),
        final_boundary_measure=np.asarray(stage_result.final_boundary_points.shape[0], dtype=float),
        geometry_center_x=np.asarray(geometry_metrics["center_x"]),
        geometry_center_y=np.asarray(geometry_metrics["center_y"]),
        geometry_mean_radius=np.asarray(geometry_metrics["mean_radius"]),
        geometry_radius_std=np.asarray(geometry_metrics["radius_std"]),
        geometry_perimeter=np.asarray(geometry_metrics["perimeter"]),
        geometry_area=np.asarray(geometry_metrics["area"]),
        stage_schedule=np.asarray(stage_schedule, dtype=float),
        stage_boundaries=np.asarray(np.cumsum([count for _freqs, count, _lr in stage_schedule])[:-1], dtype=int),
        timing_iteration_time=np.asarray([it.timing["iteration_time_s"] for it in all_iterations], dtype=float),
        timing_ibim_total_time=np.asarray([it.timing["ibim_total_time_s"] for it in all_iterations], dtype=float),
        timing_geometry_time=np.asarray([it.timing["geometry_time_s"] for it in all_iterations], dtype=float),
        timing_forward_time=np.asarray([it.timing["adjoint_context_time_s"] for it in all_iterations], dtype=float),
        timing_shape_gradient_time=np.asarray([it.timing["shape_gradient_time_s"] for it in all_iterations], dtype=float),
        timing_regularization_time=np.asarray([it.timing["regularization_time_s"] for it in all_iterations], dtype=float),
        timing_update_time=np.asarray([it.timing["nn_update_time_s"] for it in all_iterations], dtype=float),
        shape_gradient_methods=np.asarray(
            [getattr(it, "shape_gradient_method", "legacy_implicit") for it in all_iterations],
            dtype="U32",
        ),
    )
    print(
        f"relative_error_all={quality_metrics['relative_error_all']:.4e} "
        f"relative_error_gate={quality_metrics['relative_error_gate']:.4e} "
        f"corr_all={quality_metrics['correlation_all']:.4e} "
        f"corr_gate={quality_metrics['correlation_gate']:.4e} "
        f"mean_radius={geometry_metrics['mean_radius']:.4f} "
        f"num_points={stage_result.final_boundary_points.shape[0]} "
        f"stride={position_stride} "
        f"device={device}",
        flush=True,
    )
    print(output_dir / OVERVIEW_FIGURE_NAME, flush=True)
    print(output_dir / TRAJECTORY_FIGURE_NAME, flush=True)


def build_final_boundary(result, *, merge_distance: float):
    from gpr_bem import ImplicitBoundarySamples2D

    return ImplicitBoundarySamples2D(
        points=torch.tensor(result.final_boundary_points, dtype=torch.float32),
        normals=torch.tensor(result.final_boundary_normals, dtype=torch.float32),
        quadrature_weights=torch.tensor(result.final_boundary_weights[:, None], dtype=torch.float32),
        strict_quadrature_weights=torch.tensor(result.final_boundary_strict_weights[:, None], dtype=torch.float32),
        merge_distance=float(merge_distance),
        source_num_samples=result.final_boundary_points.shape[0],
        bounds=((0.0, 0.0), (cfg.DOMAIN_WIDTH, cfg.DOMAIN_HEIGHT)),
        level=0.0,
    )


if __name__ == "__main__":
    main()
