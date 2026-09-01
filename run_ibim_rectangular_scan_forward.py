"""Generate the canonical rectangular-loop IBIM forward B-scan case."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Pick the solver before importing it: `gpr_bem` below is whichever package
# --solver selects out of solvers/. Defaults to the frozen reference.
sys.path.insert(0, str(Path(__file__).resolve().parent / "solvers"))
import solver_select

SELECTED_SOLVER = solver_select.resolve_from_argv()
SELECTED_SOLVER_PACKAGE = solver_select.alias_as_gpr_bem(SELECTED_SOLVER)

import matplotlib.pyplot as plt
import numpy as np
import torch

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover - fallback for minimal environments
    tqdm = None

from config import simulation_config as cfg
from gpr_bem import (
    Material,
    RectangularLoopScan2D,
    bscan_error_metrics,
    build_implicit_boundary_samples,
    build_rectangular_bistatic_scan,
    bscan_from_frequency_response,
    circle_signed_distance,
    frequency_response_error_metrics,
    line_source_incident_field,
    penetrable_cylinder_frequency_response,
    solve_ibim_tmz_total_field_batch,
)
from gpr_bem.ibim_inverse import build_single_circle_bscan_benchmark_config
from gpr_bem.waveforms import gprmax_gaussian_spectrum

DATA_FILE_NAME = "rectangular_loop_forward_data.npz"
METADATA_FILE_NAME = "rectangular_loop_forward_metadata.json"
VALIDATION_FILE_NAME = "rectangular_loop_forward_validation.json"
VALIDATION_SUMMARY_FILE_NAME = "rectangular_loop_forward_validation.md"
OVERVIEW_FIGURE_NAME = "rectangular_loop_forward_overview.png"
TRAJECTORY_FIGURE_NAME = "rectangular_loop_forward_trajectory.png"
BSCAN_STACK_FIGURE_NAME = "rectangular_loop_forward_bscan_stack.png"
VALIDATION_FIGURE_NAME = "rectangular_loop_forward_validation.png"


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


def _solver_supports_mod_options() -> bool:
    return SELECTED_SOLVER_PACKAGE == "gpr_bem_mod"


def _solver_option_kwargs(
    *,
    formulation: str | None,
    normal_derivative_scheme: str | None,
) -> dict[str, str]:
    if not _solver_supports_mod_options():
        return {}
    kwargs = {}
    if formulation is not None:
        kwargs["formulation"] = formulation
    if normal_derivative_scheme is not None:
        kwargs["normal_derivative_scheme"] = normal_derivative_scheme
    return kwargs


def _requested_offset_distance(boundary, *, offset_scale: float | None) -> float | None:
    if offset_scale is not None:
        return float(offset_scale) * float(boundary.merge_distance)
    if _solver_supports_mod_options():
        return None
    return 2.0 * float(boundary.merge_distance)


def _system_settings_from_forward(forward) -> dict[str, object]:
    system = forward.system
    return {
        "offset_distance": float(system.offset_distance),
        "formulation": str(getattr(system, "formulation", "difference")),
        "normal_derivative_scheme": str(getattr(system, "normal_derivative_scheme", "finite_difference")),
        "backend_name": str(getattr(system, "backend_name", "")),
    }


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
    solve_strategy: str,
    formulation: str | None,
    normal_derivative_scheme: str | None,
    backend: str,
) -> tuple[np.ndarray, dict[str, object]]:
    frequency_array = np.asarray(angular_frequencies, dtype=float).reshape(-1)
    strength_array = np.asarray(source_strengths, dtype=np.complex128).reshape(-1)
    if strength_array.shape != frequency_array.shape:
        raise ValueError("source_strengths must contain one value per angular frequency.")

    iterator = range(frequency_array.size)
    progress = None
    if tqdm is not None and frequency_array.size > 1:
        progress = tqdm(iterator, desc="rectangular forward", leave=False, dynamic_ncols=True)
        iterator = progress

    responses = []
    system_settings: dict[str, object] | None = None
    try:
        for index in iterator:
            solve_kwargs = _solver_option_kwargs(
                formulation=formulation,
                normal_derivative_scheme=normal_derivative_scheme,
            )
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
                solve_strategy=solve_strategy,
                backend=backend,
                **solve_kwargs,
            )
            if system_settings is None:
                system_settings = _system_settings_from_forward(forward)
            responses.append(np.asarray(forward.total_receiver, dtype=np.complex128))
    finally:
        if progress is not None:
            progress.close()
    if system_settings is None:
        raise RuntimeError("No forward solves were run.")
    return np.stack(responses, axis=1).astype(np.complex128), system_settings


def _compute_exact_circle_responses(
    scan: RectangularLoopScan2D,
    angular_frequencies: np.ndarray,
    source_strengths: np.ndarray,
    *,
    exterior: Material,
    interior: Material,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scattered = penetrable_cylinder_frequency_response(
        scan.receiver_points,
        scan.source_points,
        angular_frequencies,
        source_strengths,
        exterior=exterior,
        interior=interior,
        eps0=float(cfg.EPS0),
        mu0=float(cfg.MU0),
        radius=float(cfg.TARGET_RADIUS),
        center=(float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y)),
        include_incident=False,
    )
    incident_responses = []
    for angular_frequency, source_strength in zip(angular_frequencies, source_strengths):
        k_exterior = exterior.wavenumber(float(angular_frequency), float(cfg.EPS0), float(cfg.MU0))
        incident_responses.append(
            line_source_incident_field(
                scan.receiver_points,
                scan.source_points,
                k_exterior=k_exterior,
                source_strength=complex(source_strength),
            )
        )
    incident = np.stack(incident_responses, axis=1).astype(np.complex128)
    return incident, scattered, incident + scattered


def _nearest_frequency_indices(frequencies_hz: np.ndarray, targets_hz: tuple[float, ...]) -> np.ndarray:
    frequency_array = np.asarray(frequencies_hz, dtype=float).reshape(-1)
    return np.asarray([int(np.argmin(np.abs(frequency_array - target))) for target in targets_hz], dtype=int)


def _state_vector_from_forward(forward) -> np.ndarray:
    return np.concatenate((forward.dirichlet_total, forward.neumann_total), axis=1)


def _compute_solve_strategy_diagnostics(
    boundary,
    scan: RectangularLoopScan2D,
    angular_frequencies: np.ndarray,
    source_strengths: np.ndarray,
    *,
    exterior: Material,
    interior: Material,
    offset_distance: float | None,
    use_strict_quadrature: bool,
    formulation: str | None,
    normal_derivative_scheme: str | None,
    backend: str,
) -> list[dict[str, float]]:
    if backend != "numpy":
        return []
    frequencies_hz = np.asarray(angular_frequencies, dtype=float) / (2.0 * np.pi)
    targets = (0.5e9, 1.5e9, 2.0e9, 2.5e9, 4.0e9, 8.0e9)
    diagnostics: list[dict[str, float]] = []
    solve_kwargs = _solver_option_kwargs(
        formulation=formulation,
        normal_derivative_scheme=normal_derivative_scheme,
    )
    for index in _nearest_frequency_indices(frequencies_hz, targets):
        direct = solve_ibim_tmz_total_field_batch(
            boundary,
            scan.source_points,
            scan.receiver_points,
            float(angular_frequencies[index]),
            complex(source_strengths[index]),
            exterior=exterior,
            interior=interior,
            eps0=float(cfg.EPS0),
            mu0=float(cfg.MU0),
            offset_distance=offset_distance,
            use_strict_quadrature=use_strict_quadrature,
            solve_strategy="direct",
            backend=backend,
            **solve_kwargs,
        )
        squared = solve_ibim_tmz_total_field_batch(
            boundary,
            scan.source_points,
            scan.receiver_points,
            float(angular_frequencies[index]),
            complex(source_strengths[index]),
            exterior=exterior,
            interior=interior,
            eps0=float(cfg.EPS0),
            mu0=float(cfg.MU0),
            offset_distance=offset_distance,
            use_strict_quadrature=use_strict_quadrature,
            solve_strategy="squared",
            backend=backend,
            **solve_kwargs,
        )
        direct_state = _state_vector_from_forward(direct)
        squared_state = _state_vector_from_forward(squared)
        state_diff = float(np.linalg.norm(direct_state - squared_state) / np.linalg.norm(direct_state))
        receiver_diff = float(
            np.linalg.norm(direct.total_receiver - squared.total_receiver) / np.linalg.norm(direct.total_receiver)
        )
        system_matrix = np.asarray(direct.system.system_matrix[0], dtype=np.complex128)
        system_matrix_squared = np.asarray(direct.system.system_matrix_squared[0], dtype=np.complex128)
        diagnostics.append(
            {
                "frequency_hz": float(frequencies_hz[index]),
                "direct_residual": float(direct.linear_system_relative_residual),
                "squared_residual": float(squared.linear_system_relative_residual),
                "relative_state_difference": state_diff,
                "relative_receiver_difference": receiver_diff,
                "cond_A": float(np.linalg.cond(system_matrix)),
                "cond_A_squared": float(np.linalg.cond(system_matrix_squared)),
            }
        )
    return diagnostics


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
    plt.colorbar(mesh, ax=ax, label="Ez amplitude")


def _plot_scan_trajectory(ax, *, scan: RectangularLoopScan2D) -> None:
    theta = np.linspace(0.0, 2.0 * np.pi, 257, dtype=float)
    circle = np.column_stack(
        (
            float(cfg.TARGET_CENTER_X) + float(cfg.TARGET_RADIUS) * np.cos(theta),
            float(cfg.TARGET_CENTER_Y) + float(cfg.TARGET_RADIUS) * np.sin(theta),
        )
    )
    ax.plot(scan.rectangle_vertices[:, 0], scan.rectangle_vertices[:, 1], linestyle="--", color="0.35", linewidth=1.8, label="scan path")
    ax.plot(circle[:, 0], circle[:, 1], color="#111111", linewidth=2.4, label="true cylinder")
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
    ax.text(
        0.03,
        0.03,
        "\n".join(
            [
                f"positions: {scan.center_points.shape[0]}",
                f"freqs: {int(cfg.NUM_FREQS)}",
                f"time window: {float(cfg.TIME_WINDOW) * 1.0e9:.1f} ns",
                f"gate start: {float(cfg.SCAN_GATE_START) * 1.0e9:.1f} ns",
                f"Tx-Rx offset: {float(cfg.TX_RX_OFFSET):.2f} m",
            ]
        ),
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "0.7"},
    )
    ax.set_title("Rectangular Scan Trajectory")
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


def _plot_outputs(
    *,
    output_dir: Path,
    scan: RectangularLoopScan2D,
    bscan: np.ndarray,
    time_vector: np.ndarray,
) -> None:
    gate_start = float(cfg.SCAN_GATE_START)
    bscan_late, time_vector_late = _late_time_slice(bscan, time_vector, gate_start=gate_start)
    amplitude = max(float(np.percentile(np.abs(bscan), 99.5)), 1.0e-6)

    overview, axes = plt.subplots(1, 3, figsize=(20, 5.8), constrained_layout=True)
    _plot_scan_trajectory(axes[0], scan=scan)
    _plot_bscan(
        axes[1],
        bscan,
        scan.path_coordinate,
        time_vector,
        "Forward B-scan",
        amplitude=amplitude,
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        axes[2],
        bscan_late,
        scan.path_coordinate,
        time_vector_late,
        "Forward B-scan (t >= 2 ns)",
        amplitude=amplitude,
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    overview.savefig(output_dir / OVERVIEW_FIGURE_NAME, dpi=180)
    plt.close(overview)

    bscan_stack, bscan_axes = plt.subplots(2, 1, figsize=(24, 10), constrained_layout=True)
    _plot_bscan(
        bscan_axes[0],
        bscan,
        scan.path_coordinate,
        time_vector,
        "Forward B-scan",
        amplitude=amplitude,
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        bscan_axes[1],
        bscan_late,
        scan.path_coordinate,
        time_vector_late,
        "Forward B-scan (t >= 2 ns)",
        amplitude=amplitude,
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    bscan_stack.savefig(output_dir / BSCAN_STACK_FIGURE_NAME, dpi=180)
    plt.close(bscan_stack)

    trajectory_figure, trajectory_ax = plt.subplots(figsize=(8.5, 7.0), constrained_layout=True)
    _plot_scan_trajectory(trajectory_ax, scan=scan)
    trajectory_figure.savefig(output_dir / TRAJECTORY_FIGURE_NAME, dpi=180)
    plt.close(trajectory_figure)


def _plot_validation_outputs(
    *,
    output_dir: Path,
    scan: RectangularLoopScan2D,
    bscan: np.ndarray,
    reference_bscan: np.ndarray,
    time_vector: np.ndarray,
    frequency_metrics: dict[str, np.ndarray | float],
) -> None:
    gate_start = float(cfg.SCAN_GATE_START)
    error_bscan = np.asarray(bscan, dtype=float) - np.asarray(reference_bscan, dtype=float)
    data_amplitude = max(
        float(np.percentile(np.abs(bscan), 99.5)),
        float(np.percentile(np.abs(reference_bscan), 99.5)),
        1.0e-6,
    )
    error_amplitude = max(float(np.percentile(np.abs(error_bscan), 99.5)), 1.0e-9)
    figure, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    _plot_bscan(
        axes[0, 0],
        reference_bscan,
        scan.path_coordinate,
        time_vector,
        "Exact Circular-Cylinder B-scan",
        amplitude=data_amplitude,
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        axes[0, 1],
        bscan,
        scan.path_coordinate,
        time_vector,
        "IBIM Forward B-scan",
        amplitude=data_amplitude,
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    _plot_bscan(
        axes[1, 0],
        error_bscan,
        scan.path_coordinate,
        time_vector,
        "IBIM minus Exact",
        amplitude=error_amplitude,
        edge_boundaries=scan.edge_boundaries,
        gate_start=gate_start,
    )
    frequency_axis_ghz = np.asarray(frequency_metrics["frequencies_hz"], dtype=float) / 1.0e9
    axes[1, 1].semilogy(
        frequency_axis_ghz,
        np.asarray(frequency_metrics["relative_error_by_frequency"], dtype=float),
        label="relative",
        linewidth=1.3,
    )
    axes[1, 1].semilogy(
        frequency_axis_ghz,
        np.asarray(frequency_metrics["mixed_error_by_frequency"], dtype=float),
        label="mixed floor",
        linewidth=1.3,
    )
    axes[1, 1].set_title("Scattered-Field Frequency Error")
    axes[1, 1].set_xlabel("Frequency (GHz)")
    axes[1, 1].set_ylabel("Relative error")
    axes[1, 1].grid(True, which="both", linestyle="--", alpha=0.3)
    axes[1, 1].legend(loc="best")
    figure.savefig(output_dir / VALIDATION_FIGURE_NAME, dpi=180)
    plt.close(figure)


def _validation_frequency_table_rows(
    frequency_metrics: dict[str, np.ndarray | float],
    *,
    targets_hz: tuple[float, ...] = (0.5e9, 1.5e9, 2.0e9, 2.5e9, 4.0e9, 8.0e9),
) -> list[dict[str, float]]:
    frequencies_hz = np.asarray(frequency_metrics["frequencies_hz"], dtype=float)
    rows = []
    for index in _nearest_frequency_indices(frequencies_hz, targets_hz):
        rows.append(
            {
                "frequency_ghz": float(frequencies_hz[index] / 1.0e9),
                "absolute_error": float(np.asarray(frequency_metrics["absolute_error_by_frequency"])[index]),
                "relative_error": float(np.asarray(frequency_metrics["relative_error_by_frequency"])[index]),
                "mixed_error": float(np.asarray(frequency_metrics["mixed_error_by_frequency"])[index]),
                "reference_norm": float(np.asarray(frequency_metrics["reference_norm_by_frequency"])[index]),
            }
        )
    return rows


def _json_ready(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_validation_summary(
    path: Path,
    *,
    frequency_metrics: dict[str, np.ndarray | float],
    bscan_metrics_total: dict[str, float],
    bscan_metrics_scattered: dict[str, float],
    solve_diagnostics: list[dict[str, float]],
    solve_strategy: str,
    system_settings: dict[str, object],
) -> None:
    rows = _validation_frequency_table_rows(frequency_metrics)
    lines = [
        "# Rectangular Forward Validation",
        "",
        f"- solve_strategy: `{solve_strategy}`",
        f"- formulation: `{system_settings['formulation']}`",
        f"- normal_derivative_scheme: `{system_settings['normal_derivative_scheme']}`",
        f"- offset_distance: {float(system_settings['offset_distance']):.6g}",
        f"- scattered broadband relative error: {float(frequency_metrics['broadband_relative_error']):.6g}",
        f"- total B-scan relative error, all samples: {bscan_metrics_total['relative_error_all']:.6g}",
        f"- total B-scan relative error, t >= {float(cfg.SCAN_GATE_START) * 1.0e9:.3g} ns: {bscan_metrics_total['relative_error_gate']:.6g}",
        f"- scattered B-scan relative error, t >= {float(cfg.SCAN_GATE_START) * 1.0e9:.3g} ns: {bscan_metrics_scattered['relative_error_gate']:.6g}",
        "",
        "## Frequency Error",
        "",
        "| f (GHz) | abs error | rel error | mixed error | reference norm |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['frequency_ghz']:.6g} | "
            f"{row['absolute_error']:.6e} | "
            f"{row['relative_error']:.6g} | "
            f"{row['mixed_error']:.6g} | "
            f"{row['reference_norm']:.6e} |"
        )
    if solve_diagnostics:
        lines.extend(
            [
                "",
                "## Direct vs Squared State Solve",
                "",
                "| f (GHz) | direct residual | squared residual | state diff | receiver diff | cond(A) | cond(A^2) |",
                "|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for item in solve_diagnostics:
            lines.append(
                "| "
                f"{item['frequency_hz'] / 1.0e9:.6g} | "
                f"{item['direct_residual']:.3e} | "
                f"{item['squared_residual']:.3e} | "
                f"{item['relative_state_difference']:.3e} | "
                f"{item['relative_receiver_difference']:.3e} | "
                f"{item['cond_A']:.3e} | "
                f"{item['cond_A_squared']:.3e} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metadata_payload(
    *,
    scan: RectangularLoopScan2D,
    boundary,
    angular_frequencies: np.ndarray,
    time_vector: np.ndarray,
    requested_offset_distance: float | None,
    system_settings: dict[str, object],
    backend: str,
    device: torch.device,
    solve_strategy: str,
    use_strict_quadrature: bool,
) -> dict[str, object]:
    return {
        "scene": "single circular penetrable cylinder in homogeneous full-space",
        "solver": SELECTED_SOLVER,
        "solver_package": SELECTED_SOLVER_PACKAGE,
        "device": str(device),
        "backend": backend,
        "solve_strategy": solve_strategy,
        "formulation": system_settings["formulation"],
        "normal_derivative_scheme": system_settings["normal_derivative_scheme"],
        "materials": {
            "exterior_epsr": float(cfg.SAND_EPSR),
            "exterior_sigma": float(cfg.SAND_SIGMA),
            "interior_epsr": float(cfg.PLASTIC_EPSR),
            "interior_sigma": float(cfg.PLASTIC_SIGMA),
        },
        "target": {
            "center": [float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y)],
            "radius": float(cfg.TARGET_RADIUS),
        },
        "scan": {
            "num_positions": int(scan.center_points.shape[0]),
            "tx_rx_offset": float(cfg.TX_RX_OFFSET),
            "rectangle": {
                "left": float(cfg.SCAN_RECT_LEFT),
                "right": float(cfg.SCAN_RECT_RIGHT),
                "top": float(cfg.SCAN_RECT_TOP),
                "bottom": float(cfg.SCAN_RECT_BOTTOM),
            },
        },
        "frequency": {
            "min_hz": float(np.min(angular_frequencies) / (2.0 * np.pi)),
            "max_hz": float(np.max(angular_frequencies) / (2.0 * np.pi)),
            "num_samples": int(angular_frequencies.size),
            "source_center_hz": float(cfg.CENTER_FREQ),
            "window": str(cfg.FREQUENCY_WINDOW),
        },
        "time": {
            "window_s": float(cfg.TIME_WINDOW),
            "num_samples": int(time_vector.size),
            "gate_start_s": float(cfg.SCAN_GATE_START),
        },
        "boundary": {
            "num_samples": int(boundary.points.shape[0]),
            "merge_distance": float(boundary.merge_distance),
            "requested_offset_distance": None if requested_offset_distance is None else float(requested_offset_distance),
            "offset_distance": float(system_settings["offset_distance"]),
            "use_strict_quadrature": bool(use_strict_quadrature),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical rectangular-loop IBIM forward case.")
    parser.add_argument(
        "--solver",
        choices=sorted(solver_select.SOLVER_NAMES),
        default=SELECTED_SOLVER,
        help="Which solver package under solvers/ to run. Resolved at import time.",
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="PyTorch device hint. The BEM backend uses cupy when cuda is available, otherwise numpy.",
    )
    parser.add_argument(
        "--output-dir",
        default=f"results/rectangular_loop_forward_{SELECTED_SOLVER}",
        help="Directory where forward data and figures will be written.",
    )
    parser.add_argument(
        "--solve-strategy",
        choices=("direct", "squared"),
        default="direct",
        help="State solve used after assembly. 'squared' preserves the old A^2 q = A b route.",
    )
    parser.add_argument(
        "--offset-scale",
        type=float,
        default=None,
        help=(
            "Explicit trace offset as this multiple of the compressed merge distance. "
            "Default: ref uses 2.0; mod defers to the selected formulation."
        ),
    )
    parser.add_argument(
        "--formulation",
        choices=("muller", "difference"),
        default=None,
        help="mod-only TMz block formulation. Default is the solver package default.",
    )
    parser.add_argument(
        "--normal-derivative-scheme",
        choices=("analytic_extrapolated", "analytic", "finite_difference"),
        default=None,
        help="mod-only K'/W normal-derivative trace scheme. Default is the solver package default.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip exact circular-cylinder validation outputs.",
    )
    parser.add_argument(
        "--skip-solve-diagnostics",
        action="store_true",
        help="Skip selected-frequency direct-vs-squared solve diagnostics.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not _solver_supports_mod_options() and (
        args.formulation is not None or args.normal_derivative_scheme is not None
    ):
        raise ValueError("--formulation and --normal-derivative-scheme are only supported by --solver=mod.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    requested_device = torch.device(args.device)
    resolved_device = requested_device
    if requested_device.type == "cuda" and not torch.cuda.is_available():
        resolved_device = torch.device("cpu")
        print("requested cuda device unavailable; falling back to cpu", flush=True)

    scan = _build_scan()
    time_vector = _build_time_vector()
    angular_frequencies = _build_angular_frequencies()
    frequency_window = _build_frequency_window(angular_frequencies.size)
    source_strengths = _build_source_strengths(angular_frequencies)

    forward_config = build_single_circle_bscan_benchmark_config(device=resolved_device.type)
    backend = "cupy" if resolved_device.type == "cuda" and torch.cuda.is_available() else "numpy"
    exterior = Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    boundary = _build_truth_boundary()

    offset_distance = _requested_offset_distance(boundary, offset_scale=args.offset_scale)
    offset_label = "solver default" if offset_distance is None else f"{offset_distance:.5g}"

    print(
        f"rectangular forward solver={SELECTED_SOLVER_PACKAGE} "
        f"device={resolved_device} backend={backend} "
        f"solve_strategy={args.solve_strategy} "
        f"num_positions={scan.center_points.shape[0]} num_freqs={angular_frequencies.size} "
        f"num_boundary_samples={boundary.points.shape[0]} "
        f"merge_distance={float(boundary.merge_distance):.5g} offset_distance={offset_label}",
        flush=True,
    )
    frequency_response_raw, system_settings = _compute_frequency_response(
        boundary,
        scan,
        angular_frequencies,
        source_strengths,
        exterior=exterior,
        interior=interior,
        offset_distance=offset_distance,
        use_strict_quadrature=forward_config.use_strict_quadrature,
        solve_strategy=args.solve_strategy,
        formulation=args.formulation,
        normal_derivative_scheme=args.normal_derivative_scheme,
        backend=backend,
    )
    print(
        "resolved "
        f"formulation={system_settings['formulation']} "
        f"normal_derivative_scheme={system_settings['normal_derivative_scheme']} "
        f"offset_distance={float(system_settings['offset_distance']):.5g}",
        flush=True,
    )
    bscan = bscan_from_frequency_response(
        frequency_response_raw,
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    validation_npz_entries: dict[str, np.ndarray] = {}
    validation_payload: dict[str, object] = {}
    validation_figure_written = False
    validation_summary_written = False
    if not args.skip_validation:
        incident_reference, scattered_reference, total_reference = _compute_exact_circle_responses(
            scan,
            angular_frequencies,
            source_strengths,
            exterior=exterior,
            interior=interior,
        )
        scattered_response_raw = frequency_response_raw - incident_reference
        frequencies_hz = angular_frequencies / (2.0 * np.pi)
        frequency_metrics = frequency_response_error_metrics(
            scattered_response_raw,
            scattered_reference,
            frequencies_hz=frequencies_hz,
        )
        reference_bscan = bscan_from_frequency_response(
            total_reference,
            angular_frequencies,
            time_vector,
            frequency_window=frequency_window,
        )
        scattered_bscan = bscan_from_frequency_response(
            scattered_response_raw,
            angular_frequencies,
            time_vector,
            frequency_window=frequency_window,
        )
        reference_scattered_bscan = bscan_from_frequency_response(
            scattered_reference,
            angular_frequencies,
            time_vector,
            frequency_window=frequency_window,
        )
        bscan_metrics_total = bscan_error_metrics(
            bscan,
            reference_bscan,
            time_vector=time_vector,
            time_gate_start=float(cfg.SCAN_GATE_START),
        )
        bscan_metrics_scattered = bscan_error_metrics(
            scattered_bscan,
            reference_scattered_bscan,
            time_vector=time_vector,
            time_gate_start=float(cfg.SCAN_GATE_START),
        )
        solve_diagnostics = [] if args.skip_solve_diagnostics else _compute_solve_strategy_diagnostics(
            boundary,
            scan,
            angular_frequencies,
            source_strengths,
            exterior=exterior,
            interior=interior,
            offset_distance=offset_distance,
            use_strict_quadrature=forward_config.use_strict_quadrature,
            formulation=args.formulation,
            normal_derivative_scheme=args.normal_derivative_scheme,
            backend=backend,
        )
        validation_npz_entries = {
            "incident_frequency_response_reference": incident_reference,
            "scattered_frequency_response_raw": scattered_response_raw,
            "scattered_frequency_response_reference": scattered_reference,
            "total_frequency_response_reference": total_reference,
            "bscan_reference_total": reference_bscan,
            "bscan_scattered": scattered_bscan,
            "bscan_reference_scattered": reference_scattered_bscan,
            "frequency_error_absolute": np.asarray(frequency_metrics["absolute_error_by_frequency"], dtype=float),
            "frequency_error_relative": np.asarray(frequency_metrics["relative_error_by_frequency"], dtype=float),
            "frequency_error_mixed": np.asarray(frequency_metrics["mixed_error_by_frequency"], dtype=float),
            "frequency_reference_norm": np.asarray(frequency_metrics["reference_norm_by_frequency"], dtype=float),
            "validation_broadband_relative_error": np.asarray(float(frequency_metrics["broadband_relative_error"])),
            "validation_bscan_relative_error_all": np.asarray(bscan_metrics_total["relative_error_all"]),
            "validation_bscan_relative_error_gate": np.asarray(bscan_metrics_total["relative_error_gate"]),
            "validation_scattered_bscan_relative_error_gate": np.asarray(
                bscan_metrics_scattered["relative_error_gate"]
            ),
        }
        validation_payload = {
            "system_settings": system_settings,
            "frequency_metrics": frequency_metrics,
            "frequency_table": _validation_frequency_table_rows(frequency_metrics),
            "bscan_metrics_total": bscan_metrics_total,
            "bscan_metrics_scattered": bscan_metrics_scattered,
            "solve_diagnostics": solve_diagnostics,
        }
        _plot_validation_outputs(
            output_dir=output_dir,
            scan=scan,
            bscan=bscan,
            reference_bscan=reference_bscan,
            time_vector=time_vector,
            frequency_metrics=frequency_metrics,
        )
        validation_figure_written = True
        _write_json(output_dir / VALIDATION_FILE_NAME, validation_payload)
        _write_validation_summary(
            output_dir / VALIDATION_SUMMARY_FILE_NAME,
            frequency_metrics=frequency_metrics,
            bscan_metrics_total=bscan_metrics_total,
            bscan_metrics_scattered=bscan_metrics_scattered,
            solve_diagnostics=solve_diagnostics,
            solve_strategy=args.solve_strategy,
            system_settings=system_settings,
        )
        validation_summary_written = True
        print(
            f"validation scattered broadband rel={float(frequency_metrics['broadband_relative_error']):.4g} "
            f"bscan_gate_rel={bscan_metrics_total['relative_error_gate']:.4g}",
            flush=True,
        )
    _plot_outputs(
        output_dir=output_dir,
        scan=scan,
        bscan=bscan,
        time_vector=time_vector,
    )
    metadata = _metadata_payload(
        scan=scan,
        boundary=boundary,
        angular_frequencies=angular_frequencies,
        time_vector=time_vector,
        requested_offset_distance=offset_distance,
        system_settings=system_settings,
        backend=backend,
        device=resolved_device,
        solve_strategy=args.solve_strategy,
        use_strict_quadrature=forward_config.use_strict_quadrature,
    )
    _write_json(output_dir / METADATA_FILE_NAME, metadata)
    np.savez(
        output_dir / DATA_FILE_NAME,
        bscan=bscan,
        frequency_response_raw=frequency_response_raw,
        time_vector=time_vector,
        angular_frequencies=angular_frequencies,
        frequency_window=frequency_window,
        scan_coordinate=scan.path_coordinate,
        scan_edge_index=scan.edge_index,
        scan_edge_boundaries=scan.edge_boundaries,
        scan_center_points=scan.center_points,
        source_points=scan.source_points,
        receiver_points=scan.receiver_points,
        scan_tangents=scan.tangents,
        scan_rectangle_vertices=scan.rectangle_vertices,
        gate_start=np.asarray(float(cfg.SCAN_GATE_START)),
        tx_rx_offset=np.asarray(float(cfg.TX_RX_OFFSET)),
        requested_offset_distance=np.asarray(float("nan") if offset_distance is None else float(offset_distance)),
        offset_distance=np.asarray(float(system_settings["offset_distance"])),
        merge_distance=np.asarray(float(boundary.merge_distance)),
        num_boundary_samples=np.asarray(int(boundary.points.shape[0])),
        use_strict_quadrature=np.asarray(bool(forward_config.use_strict_quadrature)),
        solve_strategy=np.asarray(str(args.solve_strategy)),
        formulation=np.asarray(str(system_settings["formulation"])),
        normal_derivative_scheme=np.asarray(str(system_settings["normal_derivative_scheme"])),
        **validation_npz_entries,
    )
    print(output_dir / DATA_FILE_NAME, flush=True)
    print(output_dir / METADATA_FILE_NAME, flush=True)
    print(output_dir / OVERVIEW_FIGURE_NAME, flush=True)
    print(output_dir / BSCAN_STACK_FIGURE_NAME, flush=True)
    print(output_dir / TRAJECTORY_FIGURE_NAME, flush=True)
    if validation_figure_written:
        print(output_dir / VALIDATION_FIGURE_NAME, flush=True)
    if validation_payload:
        print(output_dir / VALIDATION_FILE_NAME, flush=True)
    if validation_summary_written:
        print(output_dir / VALIDATION_SUMMARY_FILE_NAME, flush=True)


if __name__ == "__main__":
    main()
