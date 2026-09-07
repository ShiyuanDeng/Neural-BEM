#!/usr/bin/env python3
"""Build and render the automatic one-to-two-component extraction demo.

Every regular outline in the video is produced by the same automatic
SDF-to-``OrderedBoundary2D`` builder.  The single critical frame is different
on purpose: its Bernoulli-lemniscate zero set has a zero gradient at the pinch,
so it is stored as exact raw plotting polylines and is never sent to Method B
or Kress.

The resulting ``split_trajectory.npz`` uses ragged frame/component offsets;
it does not invent a dense one-curve correspondence across the topology
change.  The exact two-circle endpoint is also solved through the direct
``OrderedBoundary2D`` multi-Kress seam as an end-to-end smoke check.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Sequence


for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/neural_sdf_bem_ad_matplotlib")

REPOSITORY_ROOT = Path(__file__).resolve().parent
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
for _root in (REPOSITORY_ROOT, SOLVERS_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

import numpy as np  # noqa: E402

from sdf_bem_multicomponent import (  # noqa: E402
    CassiniSplitStage,
    CassiniSplitTopology,
    CassiniSplitTrajectory2D,
    MaterialSpec,
    MultiComponentOrderedSDFGeometryConfig,
    PairedForwardProblem,
    build_cassini_split_geometry,
    predict_multicomponent_kress_paired_boundary_response,
)
from sdf_bem_multicomponent.trajectory import (  # noqa: E402
    BoundaryTrajectoryFrame,
    RaggedBoundaryTrajectory,
    TOPOLOGY_TRANSITION,
)


DEFAULT_OUTPUT = REPOSITORY_ROOT / "results" / "multicomponent_split_demo"
GENERATED_NAMES = (
    "split_trajectory.npz",
    "metrics.json",
    "summary.md",
    "one_to_two_split.mp4",
)


def _integer_at_least(value: str, *, minimum: int) -> int:
    result = int(value)
    if result < minimum:
        raise argparse.ArgumentTypeError(f"expected an integer at least {minimum}")
    return result


def _positive_int(value: str) -> int:
    return _integer_at_least(value, minimum=1)


def _frame_count(value: str) -> int:
    return _integer_at_least(value, minimum=5)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Auto-extract a large circle as it splits into two circles and "
            "render a component-aware video."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frames", type=_frame_count, default=60)
    parser.add_argument("--fps", type=_positive_int, default=20)
    parser.add_argument("--dpi", type=_positive_int, default=130)
    parser.add_argument("--grid-size", type=_positive_int, default=257)
    parser.add_argument("--projected-samples", type=_positive_int, default=128)
    parser.add_argument("--bandwidth", type=_positive_int, default=24)
    parser.add_argument("--num-nodes", type=_positive_int, default=192)
    parser.add_argument("--validation-resolution", type=_positive_int, default=512)
    parser.add_argument(
        "--artifact-only",
        action="store_true",
        help="Build and validate the ragged archive without rendering MP4.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only the known artifacts in the output directory.",
    )
    args = parser.parse_args(argv)
    if args.grid_size < 33:
        parser.error("--grid-size must be at least 33")
    if args.projected_samples < 2 * args.bandwidth + 1:
        parser.error("--projected-samples must be at least 2 * bandwidth + 1")
    if args.num_nodes % 2:
        parser.error("--num-nodes must be even for Kress quadrature")
    if args.num_nodes < 2 * args.bandwidth + 2:
        parser.error("--num-nodes must be at least 2 * bandwidth + 2")
    if args.validation_resolution < 2 * args.bandwidth + 2:
        parser.error("--validation-resolution must be at least 2 * bandwidth + 2")
    return args


def split_progress_schedule(
    frame_count: int,
    critical_progress: float,
) -> np.ndarray:
    """Return a monotone schedule containing the critical value exactly once."""

    count = int(frame_count)
    critical = float(critical_progress)
    if count < 5:
        raise ValueError("frame_count must be at least five.")
    if not math.isfinite(critical) or not 0.0 < critical < 1.0:
        raise ValueError("critical_progress must lie strictly between zero and one.")
    intervals = count - 1
    pre_intervals = max(2, min(intervals - 2, round(intervals * critical)))
    post_intervals = intervals - pre_intervals
    progress = np.concatenate(
        (
            np.linspace(0.0, critical, pre_intervals + 1, dtype=np.float64),
            np.linspace(critical, 1.0, post_intervals + 1, dtype=np.float64)[1:],
        )
    )
    if progress.shape != (count,) or np.count_nonzero(progress == critical) != 1:
        raise RuntimeError("Failed to construct an exact split-frame schedule.")
    progress.setflags(write=False)
    return progress


def _prepare_output(path: Path, *, overwrite: bool) -> Path:
    output = path.resolve()
    output.mkdir(parents=True, exist_ok=True)
    existing = [output / name for name in GENERATED_NAMES if (output / name).exists()]
    if existing and not overwrite:
        names = ", ".join(item.name for item in existing)
        raise FileExistsError(
            f"Refusing to replace existing artifacts ({names}); pass --overwrite."
        )
    if overwrite:
        for artifact in existing:
            if artifact.is_file() or artifact.is_symlink():
                artifact.unlink()
    return output


def _geometry_config(args: argparse.Namespace) -> MultiComponentOrderedSDFGeometryConfig:
    return MultiComponentOrderedSDFGeometryConfig(
        bounds=((0.20, 0.20), (0.80, 0.80)),
        # None is the essential production behavior: the field, not a caller,
        # determines M independently at every regular frame.
        expected_num_components=None,
        grid_shape=(args.grid_size, args.grid_size),
        projected_samples=args.projected_samples,
        bandwidth=args.bandwidth,
        num_nodes=args.num_nodes,
        arclength_dense_resolution=max(512, args.validation_resolution),
        validation_resolution=args.validation_resolution,
        minimum_intercomponent_clearance=0.0,
        maximum_num_components=8,
        maximum_total_nodes=8 * args.num_nodes,
        minimum_component_perimeter=4.0 / args.grid_size,
        minimum_component_area=4.0 / (args.grid_size * args.grid_size),
        minimum_boundary_gradient_norm=1.0e-8,
        maximum_normalized_curve_residual=1.0e-3,
    )


def _component_lineage(
    topology: CassiniSplitTopology,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if topology is CassiniSplitTopology.ONE_COMPONENT:
        return ("object",), ("",)
    return ("object.left", "object.right"), ("object", "object")


def build_demo_trajectory(
    trajectory: CassiniSplitTrajectory2D,
    progress_values: Sequence[float],
    geometry_config: MultiComponentOrderedSDFGeometryConfig,
) -> tuple[RaggedBoundaryTrajectory, list[dict[str, Any]], Any]:
    """Auto-extract all regular frames and retain the exact raw pinch frame.

    Failure of any regular extraction aborts the demo.  This is intentional:
    the video is validation evidence, not a renderer that silently substitutes
    an approximate contour when the production readiness gates fail.
    """

    frames: list[BoundaryTrajectoryFrame] = []
    diagnostics: list[dict[str, Any]] = []
    endpoint_boundary = None
    for index, progress in enumerate(progress_values):
        metadata = trajectory.frame(float(progress))
        component_ids, parent_ids = _component_lineage(metadata.topology)
        if metadata.topology is CassiniSplitTopology.CRITICAL_PINCH:
            message = (
                "Exact topology event: the zero set self-touches and its field "
                "gradient vanishes at the pinch; plotting only, BEM skipped."
            )
            raw = tuple(
                sorted(
                    trajectory.critical_raw_contours(num_points_per_lobe=257),
                    key=lambda points: float(np.mean(points[:, 0])),
                )
            )
            frame = BoundaryTrajectoryFrame(
                parameter=metadata.progress,
                status=TOPOLOGY_TRANSITION,
                components=raw,
                component_ids=component_ids,
                parent_ids=parent_ids,
                message=message,
            )
            diagnostics.append(
                {
                    "frame": index,
                    **trajectory.model(metadata.progress).physical_geometry(),
                    "detected_num_components": None,
                    "status": frame.status,
                    "message": message,
                }
            )
        else:
            result = build_cassini_split_geometry(
                trajectory,
                metadata.progress,
                geometry_config,
            )
            build = result.geometry
            if build.num_components != len(component_ids):
                raise RuntimeError(
                    "Automatic extraction disagrees with analytic topology at "
                    f"progress {metadata.progress:.9f}."
                )
            frame = BoundaryTrajectoryFrame.from_boundary(
                build.boundary,
                parameter=metadata.progress,
                component_ids=component_ids,
                parent_ids=parent_ids,
            )
            diagnostics.append(
                {
                    "frame": index,
                    **result.model.physical_geometry(),
                    "detected_num_components": build.num_components,
                    "status": frame.status,
                    "component_offsets": build.boundary.component_offsets.tolist(),
                    "resolved_node_counts": list(build.resolved_node_counts),
                    "maximum_normalized_curve_residual_m": (
                        build.maximum_normalized_curve_residual
                    ),
                    "minimum_boundary_gradient_norm": (
                        build.minimum_field_gradient_norm
                    ),
                    "minimum_intercomponent_clearance_m": (
                        build.topology_report.minimum_intercomponent_clearance
                    ),
                    "required_intercomponent_clearance_m": (
                        build.resolved_required_intercomponent_clearance
                    ),
                    "grid_parity_confirmation": (
                        None
                        if build.grid_parity_confirmation is None
                        else asdict(build.grid_parity_confirmation)
                    ),
                }
            )
            if metadata.stage is CassiniSplitStage.EXACT_TWO_CIRCLES:
                endpoint_boundary = build.boundary
        frames.append(frame)

    if endpoint_boundary is None:
        raise RuntimeError("The progress schedule must include the exact endpoint.")
    artifact = RaggedBoundaryTrajectory.from_frames(
        frames,
        parameter_name="split_progress",
    )
    return artifact, diagnostics, endpoint_boundary


def _endpoint_problem() -> PairedForwardProblem:
    center = np.asarray((0.5, 0.5), dtype=np.float64)
    source_angles = np.asarray((0.10, 2.20, 4.30))
    receiver_angles = np.asarray((0.70, 2.80, 4.90))
    return PairedForwardProblem(
        source_points=center
        + 0.34
        * np.column_stack((np.cos(source_angles), np.sin(source_angles))),
        receiver_points=center
        + 0.31
        * np.column_stack((np.cos(receiver_angles), np.sin(receiver_angles))),
        angular_frequencies=np.asarray((2.0 * np.pi * 1.2e9,)),
        source_strengths=1.0,
        exterior=MaterialSpec(epsr=3.1),
        interior=MaterialSpec(epsr=2.2),
        eps0=8.8541878128e-12,
        mu0=1.25663706212e-6,
    )


def _closed(points: np.ndarray) -> np.ndarray:
    if np.array_equal(points[0], points[-1]):
        return points
    return np.vstack((points, points[:1]))


def render_split_video(
    artifact: RaggedBoundaryTrajectory,
    trajectory: CassiniSplitTrajectory2D,
    path: Path,
    *,
    fps: int,
    dpi: int,
) -> Path:
    """Render actual stored frames for this one-to-two Cassini fixture.

    The extraction and ragged-storage APIs support arbitrary component counts;
    this deliberately fixture-specific renderer draws at most the two lineages
    for which its target overlays and labels are defined.  Rejecting another
    arity is preferable to silently dropping a valid component.
    """

    maximum_components = max(
        artifact.frame(index).num_components
        for index in range(artifact.num_frames)
    )
    if maximum_components > 2:
        raise ValueError(
            "The one-to-two Cassini renderer accepts at most two components "
            "per frame; use the ragged artifact with a general renderer for "
            f"M={maximum_components}."
        )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import animation

    if not animation.writers.is_available("ffmpeg"):
        raise RuntimeError("Matplotlib's ffmpeg writer is required for MP4 output.")

    figure = plt.figure(figsize=(7.4, 7.8), constrained_layout=True)
    grid = figure.add_gridspec(2, 1, height_ratios=(8.0, 1.2))
    axis = figure.add_subplot(grid[0, 0])
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlim(0.27, 0.73)
    axis.set_ylim(0.30, 0.70)
    axis.set_xlabel("x (m)")
    axis.set_ylabel("y (m)")
    axis.grid(True, alpha=0.18)
    axis.set_title("Automatic SDF extraction: one material region splits in two")

    colors = ("#2364aa", "#f18f01")
    lines = tuple(
        axis.plot([], [], color=color, linewidth=3.0, zorder=4)[0]
        for color in colors
    )
    node_lines = tuple(
        axis.plot(
            [],
            [],
            linestyle="none",
            marker="o",
            markersize=1.8,
            color=color,
            alpha=0.55,
            zorder=5,
        )[0]
        for color in colors
    )

    config = trajectory.config
    angles = np.linspace(0.0, 2.0 * np.pi, 721)
    initial = np.asarray(config.center)[None, :] + config.cassini_radius * np.column_stack(
        (np.cos(angles), np.sin(angles))
    )
    axis.plot(
        initial[:, 0],
        initial[:, 1],
        color="0.65",
        linewidth=1.0,
        linestyle=":",
        label="initial circle",
    )
    for circle_index, center in enumerate(config.exact_circle_centers):
        target = np.asarray(center)[None, :] + config.final_circle_radius * np.column_stack(
            (np.cos(angles), np.sin(angles))
        )
        axis.plot(
            target[:, 0],
            target[:, 1],
            color="0.25",
            linewidth=1.1,
            linestyle="--",
            label="final circles" if circle_index == 0 else None,
        )
    axis.legend(loc="upper right", fontsize=8)
    annotation = axis.text(
        0.025,
        0.025,
        "",
        transform=axis.transAxes,
        verticalalignment="bottom",
        family="monospace",
        fontsize=9,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.88},
        zorder=7,
    )

    timeline = figure.add_subplot(grid[1, 0])
    timeline.set_xlim(0.0, 1.0)
    timeline.set_ylim(-0.7, 0.7)
    timeline.set_yticks(())
    timeline.set_xlabel("analytic split progress")
    timeline.axhline(0.0, color="0.35", linewidth=1.2)
    timeline.axvline(
        trajectory.critical_progress,
        color="#c1121f",
        linestyle="--",
        linewidth=1.2,
        label="singular pinch",
    )
    (timeline_marker,) = timeline.plot([], [], "o", color="#2364aa", markersize=8)
    timeline.legend(loc="upper left", fontsize=8)

    # Holding only repeats stored states.  It never synthesizes geometry.
    schedule = [0] * max(1, fps // 2)
    for frame_index in range(1, artifact.num_frames):
        schedule.append(frame_index)
        if artifact.statuses[frame_index] == TOPOLOGY_TRANSITION:
            schedule.extend([frame_index] * max(1, fps // 2))
    schedule.extend([artifact.num_frames - 1] * max(1, fps))
    writer = animation.FFMpegWriter(
        fps=fps,
        codec="libx264",
        bitrate=-1,
        extra_args=["-pix_fmt", "yuv420p"],
        metadata={
            "title": "Automatic one-to-two SDF boundary extraction",
            "comment": "Exact critical pinch is visual-only and not solved.",
        },
    )
    with writer.saving(figure, str(path), dpi):
        for frame_index in schedule:
            frame = artifact.frame(frame_index)
            critical = frame.status == TOPOLOGY_TRANSITION
            for artist_index, (line, nodes) in enumerate(zip(lines, node_lines)):
                if artist_index >= frame.num_components:
                    line.set_data([], [])
                    nodes.set_data([], [])
                    continue
                points = frame.components[artist_index]
                closed = _closed(points)
                color = "#c1121f" if critical else colors[artist_index]
                line.set_color(color)
                line.set_data(closed[:, 0], closed[:, 1])
                # Raw singular lobes have no solver nodes to claim.
                if critical:
                    nodes.set_data([], [])
                else:
                    nodes.set_color(color)
                    nodes.set_data(points[:, 0], points[:, 1])
            topology = trajectory.frame(frame.parameter).topology.value
            detected = "event" if critical else str(frame.num_components)
            readiness = "NO — visual only" if critical else "yes"
            annotation.set_text(
                f"progress: {frame.parameter:5.3f}\n"
                f"topology: {topology}\n"
                f"detected M: {detected}\n"
                f"solver-ready: {readiness}"
            )
            annotation.get_bbox_patch().set_edgecolor(
                "#c1121f" if critical else "0.6"
            )
            timeline_marker.set_color("#c1121f" if critical else "#2364aa")
            timeline_marker.set_data([frame.parameter], [0.0])
            writer.grab_frame()
    plt.close(figure)
    return path


def _write_summary(
    output: Path,
    *,
    artifact: RaggedBoundaryTrajectory,
    critical_index: int,
    endpoint_residual: float,
    elapsed: float,
    video_written: bool,
) -> None:
    video_line = (
        "- Video: `one_to_two_split.mp4`\n"
        if video_written
        else "- Video: skipped by `--artifact-only`\n"
    )
    text = (
        "# Automatic one-to-two component split\n\n"
        "All regular frames were extracted with unknown component count. The "
        "critical pinch is retained as an explicit visual-only frame because "
        "its zero set is singular and cannot enter Method B or BEM.\n\n"
        f"- Unique frames: {artifact.num_frames}\n"
        f"- Critical frame index: {critical_index}\n"
        f"- Component counts: 1 before the pinch, 2 after it\n"
        f"- Endpoint Kress relative residual: {endpoint_residual:.3e}\n"
        f"- Build/render wall time: {elapsed:.2f} s\n"
        f"- Ragged geometry: `split_trajectory.npz`\n"
        f"{video_line}"
    )
    (output / "summary.md").write_text(text, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    output = _prepare_output(args.output_dir, overwrite=args.overwrite)
    started = perf_counter()
    trajectory = CassiniSplitTrajectory2D()
    progress = split_progress_schedule(args.frames, trajectory.critical_progress)
    geometry_config = _geometry_config(args)

    print(
        f"Extracting {progress.size - 1} regular frames with automatic M "
        "and one explicit critical frame...",
        flush=True,
    )
    artifact, frame_diagnostics, endpoint_boundary = build_demo_trajectory(
        trajectory,
        progress,
        geometry_config,
    )
    archive_path = artifact.save_npz(output / "split_trajectory.npz")
    reloaded = RaggedBoundaryTrajectory.load_npz(archive_path)
    if reloaded.num_frames != artifact.num_frames or not np.array_equal(
        reloaded.points,
        artifact.points,
    ):
        raise RuntimeError("Ragged trajectory round-trip verification failed.")

    endpoint = predict_multicomponent_kress_paired_boundary_response(
        endpoint_boundary,
        _endpoint_problem(),
    )
    endpoint_residual = float(np.max(endpoint.linear_system_relative_residuals))
    if endpoint_residual > 1.0e-10:
        raise RuntimeError(
            "The exact two-circle endpoint failed the Kress residual gate: "
            f"{endpoint_residual:.3e}."
        )

    video_path = output / "one_to_two_split.mp4"
    if not args.artifact_only:
        print(f"Rendering component-aware MP4 -> {video_path}", flush=True)
        render_split_video(
            artifact,
            trajectory,
            video_path,
            fps=args.fps,
            dpi=args.dpi,
        )

    critical_indices = [
        index
        for index, status in enumerate(artifact.statuses)
        if status == TOPOLOGY_TRANSITION
    ]
    if len(critical_indices) != 1:
        raise RuntimeError("The artifact must contain exactly one transition frame.")
    elapsed = float(perf_counter() - started)
    metrics = {
        "schema_version": 1,
        "purpose": "automatic_unknown_M_one_to_two_extraction_validation",
        "component_count_policy": "automatic",
        "regular_frame_count": artifact.num_frames - 1,
        "transition_frame_count": 1,
        "critical_frame_index": critical_indices[0],
        "critical_frame_solver_policy": "visual_only_bem_skipped",
        "trajectory_config": asdict(trajectory.config),
        "geometry_config": asdict(geometry_config),
        "resolved_geometry_limits": {
            "minimum_component_area_m2": (
                geometry_config.resolved_minimum_component_area
            ),
            "minimum_component_perimeter_m": (
                geometry_config.resolved_minimum_component_perimeter
            ),
            "minimum_component_spans_m": list(
                geometry_config.resolved_minimum_component_spans
            ),
            "minimum_intercomponent_grid_clearance_m": (
                geometry_config.resolved_minimum_intercomponent_clearance
            ),
            "confirmation_grid_shape": list(
                geometry_config.resolved_confirmation_grid_shape or ()
            ),
            "grid_confirmation_geometry_tolerance_m": (
                geometry_config.resolved_grid_confirmation_geometry_tolerance
            ),
        },
        "ragged_layout": {
            "points": list(artifact.points.shape),
            "component_point_offsets": list(artifact.component_point_offsets.shape),
            "frame_component_offsets": list(artifact.frame_component_offsets.shape),
        },
        "endpoint": {
            "num_components": endpoint.num_components,
            "component_offsets": endpoint.component_offsets.tolist(),
            "kress_linear_system_relative_residual": endpoint_residual,
            "response_shape": list(endpoint.scattered_response.shape),
        },
        "frames": frame_diagnostics,
        "elapsed_seconds": elapsed,
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_summary(
        output,
        artifact=artifact,
        critical_index=critical_indices[0],
        endpoint_residual=endpoint_residual,
        elapsed=elapsed,
        video_written=not args.artifact_only,
    )
    print(
        f"Done: M=1 -> singular pinch (skipped) -> M=2; "
        f"endpoint Kress residual {endpoint_residual:.3e}; {elapsed:.2f} s.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
