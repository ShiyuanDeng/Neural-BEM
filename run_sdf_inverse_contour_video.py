#!/usr/bin/env python3
"""Animate the accepted contour trajectories of one checked inverse bundle.

This entry point is pure post-processing.  It re-renders no physics and
touches no solver: it reads the artifacts already written by
[`run_sdf_inverse_comparison.py`](run_sdf_inverse_comparison.py)
(``metrics.json``, ``<solver>_trajectory.csv``, ``<solver>_responses.npz``)
and draws the stored accepted boundary iterates of MOD and Kress side by side
against the analytic target circle, with the shared training objective below.

Only accepted iterates are stored by the driver, so the honest animation is a
step sequence.  Intermediate frames are optional visual interpolation between
two stored contours; they are labelled as such in the frame and never change
any reported number.

Usage:

    PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
      run_sdf_inverse_contour_video.py \
        results/inverse_solver_comparison/wrong-circle-mie-20260902
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parent
DEFAULT_BUNDLE = (
    REPOSITORY_ROOT
    / "results"
    / "inverse_solver_comparison"
    / "wrong-circle-mie-20260902"
)
DEFAULT_SOLVERS = ("mod", "kress")
SOLVER_COLORS = {"mod": "#1f77b4", "kress": "#d62728"}
SOLVER_LABELS = {"mod": "MOD", "kress": "Kress"}
REQUIRED_TRAJECTORY_COLUMNS = (
    "iteration",
    "loss",
    "relative_l2_error",
    "center_x_m",
    "center_y_m",
    "radius_m",
)
# Raw controls that are already physical values, shown when the target has them.
OPTIONAL_TRAJECTORY_COLUMNS = ("raw_amplitude", "raw_rotation")
VIDEO_SUFFIXES = {".mp4": "ffmpeg", ".gif": "pillow"}


class BundleError(RuntimeError):
    """The requested artifact bundle is missing or internally inconsistent."""


def _positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return result


def _nonnegative_int(value: str) -> int:
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer")
    return result


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a side-by-side MOD/Kress contour-convergence video from an "
            "existing inverse comparison bundle."
        )
    )
    parser.add_argument(
        "bundle",
        nargs="?",
        type=Path,
        default=DEFAULT_BUNDLE,
        help="Directory written by run_sdf_inverse_comparison.py.",
    )
    parser.add_argument(
        "--solvers",
        nargs="+",
        default=list(DEFAULT_SOLVERS),
        choices=sorted(DEFAULT_SOLVERS),
        help="Which stored solver trajectories to draw, in panel order.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output video path; '.mp4' uses ffmpeg and '.gif' uses Pillow. "
            "Default: <bundle>/contour_evolution.mp4."
        ),
    )
    parser.add_argument("--fps", type=_positive_int, default=20)
    parser.add_argument(
        "--hold-frames",
        type=_positive_int,
        default=14,
        help="Frames held on each stored accepted iterate.",
    )
    parser.add_argument(
        "--morph-frames",
        type=_nonnegative_int,
        default=6,
        help=(
            "Labelled interpolated frames drawn between consecutive stored "
            "iterates; 0 renders a pure step sequence."
        ),
    )
    parser.add_argument(
        "--final-hold-frames",
        type=_positive_int,
        default=45,
        help="Extra frames held on the converged state at the end.",
    )
    parser.add_argument("--dpi", type=_positive_int, default=140)
    parser.add_argument(
        "--zoom-margin",
        type=float,
        default=0.35,
        help="Fractional padding around the drawn geometry.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file.",
    )
    args = parser.parse_args(argv)
    if not math.isfinite(args.zoom_margin) or args.zoom_margin < 0.0:
        parser.error("--zoom-margin must be finite and non-negative")
    if len(set(args.solvers)) != len(args.solvers):
        parser.error("--solvers must not repeat a solver")
    return args


def _read_trajectory(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise BundleError(f"Missing trajectory CSV: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise BundleError(f"Trajectory CSV has no accepted iterates: {path}")
    missing = [name for name in REQUIRED_TRAJECTORY_COLUMNS if name not in rows[0]]
    if missing:
        raise BundleError(f"{path} is missing columns: {', '.join(missing)}")
    present = REQUIRED_TRAJECTORY_COLUMNS + tuple(
        name for name in OPTIONAL_TRAJECTORY_COLUMNS if name in rows[0]
    )
    columns = {
        name: np.asarray([float(row[name]) for row in rows], dtype=np.float64)
        for name in present
    }
    iterations = columns["iteration"]
    if not np.array_equal(iterations, np.arange(iterations.size, dtype=np.float64)):
        raise BundleError(f"{path} accepted iterations are not consecutive from zero.")
    return columns


def _read_geometry(path: Path, *, expected_iterates: int) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise BundleError(f"Missing response archive: {path}")
    with np.load(path) as archive:
        required = ("geometry_trajectory", "initial_curve_points", "target_curve_points")
        missing = [name for name in required if name not in archive.files]
        if missing:
            raise BundleError(f"{path} is missing arrays: {', '.join(missing)}")
        geometry = np.asarray(archive["geometry_trajectory"], dtype=np.float64)
        initial = np.asarray(archive["initial_curve_points"], dtype=np.float64)
        target = np.asarray(archive["target_curve_points"], dtype=np.float64)
        exact_boundary = (
            np.asarray(archive["exact_boundary_points"], dtype=np.float64)
            if "exact_boundary_points" in archive.files
            else None
        )
    if geometry.ndim != 3 or geometry.shape[2] != 2 or geometry.shape[0] < 1:
        raise BundleError(f"{path} geometry_trajectory must have shape (K, N, 2).")
    if geometry.shape[0] != expected_iterates:
        raise BundleError(
            f"{path} stores {geometry.shape[0]} contours but its trajectory CSV "
            f"records {expected_iterates} accepted iterates."
        )
    if not np.all(np.isfinite(geometry)):
        raise BundleError(f"{path} geometry_trajectory contains non-finite values.")
    if exact_boundary is not None and (
        exact_boundary.ndim != 2
        or exact_boundary.shape[1] != 2
        or not np.all(np.isfinite(exact_boundary))
    ):
        raise BundleError(f"{path} exact_boundary_points must be a finite (N, 2) array.")
    return {
        "geometry_trajectory": geometry,
        "initial_curve_points": initial,
        "target_curve_points": target,
        "exact_boundary_points": exact_boundary,
    }


def _load_bundle(bundle: Path, solvers: Sequence[str]) -> dict[str, Any]:
    if not bundle.is_dir():
        raise BundleError(f"Not a bundle directory: {bundle}")
    metrics_path = bundle / "metrics.json"
    if not metrics_path.is_file():
        raise BundleError(f"Missing metrics document: {metrics_path}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    target = metrics["target"]
    if "center_x_m" not in target or "center_y_m" not in target:
        raise BundleError(f"{metrics_path} has no target center.")
    # A circle records "radius_m"; a star records its mean radius instead.
    reference_radius = target.get("radius_m", target.get("mean_radius_m"))
    if reference_radius is None:
        raise BundleError(f"{metrics_path} has no target radius.")
    loaded: dict[str, dict[str, Any]] = {}
    for solver in solvers:
        trajectory = _read_trajectory(bundle / f"{solver}_trajectory.csv")
        geometry = _read_geometry(
            bundle / f"{solver}_responses.npz",
            expected_iterates=trajectory["iteration"].size,
        )
        solver_metrics = metrics.get("solvers", {}).get(solver)
        if solver_metrics is None:
            raise BundleError(f"{metrics_path} has no metrics for solver '{solver}'.")
        loaded[solver] = {
            "trajectory": trajectory,
            "geometry": geometry,
            "metrics": solver_metrics,
        }
    exact_boundaries = [
        record["geometry"]["exact_boundary_points"]
        for record in loaded.values()
        if record["geometry"]["exact_boundary_points"] is not None
    ]
    for other in exact_boundaries[1:]:
        if not np.array_equal(other, exact_boundaries[0]):
            raise BundleError(
                f"{bundle} stores different exact boundaries for different solvers."
            )
    return {
        "path": bundle,
        "metrics": metrics,
        "target_shape": str(metrics.get("target_shape", "circle")),
        "target_center": (float(target["center_x_m"]), float(target["center_y_m"])),
        "target_radius": float(reference_radius),
        "target_amplitude": (
            float(target["amplitude"]) if "amplitude" in target else None
        ),
        "target_rotation_radians": (
            float(target["rotation_radians"]) if "rotation_radians" in target else None
        ),
        # Older bundles predate the stored polyline; a circle is reconstructible.
        "exact_boundary": exact_boundaries[0] if exact_boundaries else None,
        "solvers": loaded,
    }


def _closed(points: np.ndarray) -> np.ndarray:
    """Repeat the first node so a periodic node list draws as a closed curve."""

    return np.vstack((points, points[:1]))


def _frame_schedule(
    *, stages: int, hold_frames: int, morph_frames: int, final_hold_frames: int
) -> list[tuple[int, float]]:
    """Return ``(stage, alpha)`` pairs; ``alpha > 0`` marks an interpolated frame."""

    schedule: list[tuple[int, float]] = []
    for stage in range(stages):
        schedule.extend((stage, 0.0) for _ in range(hold_frames))
        if stage + 1 < stages:
            schedule.extend(
                (stage, (index + 1) / (morph_frames + 1))
                for index in range(morph_frames)
            )
    schedule.extend((stages - 1, 0.0) for _ in range(final_hold_frames))
    return schedule


def _stage_contour(
    geometry: np.ndarray, *, stage: int, alpha: float
) -> tuple[np.ndarray, int]:
    """Contour at a global stage, clamped and optionally interpolated forward."""

    last = geometry.shape[0] - 1
    current_index = min(stage, last)
    next_index = min(stage + 1, last)
    current = geometry[current_index]
    if alpha <= 0.0 or next_index == current_index:
        return current, current_index
    return (1.0 - alpha) * current + alpha * geometry[next_index], current_index


def _view_limits(
    bundle: dict[str, Any], *, margin: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    stacked = [
        record["geometry"]["geometry_trajectory"].reshape(-1, 2)
        for record in bundle["solvers"].values()
    ]
    stacked.extend(
        record["geometry"]["initial_curve_points"]
        for record in bundle["solvers"].values()
    )
    if bundle["exact_boundary"] is not None:
        stacked.append(bundle["exact_boundary"])
    else:
        center = np.asarray(bundle["target_center"], dtype=np.float64)
        radius = bundle["target_radius"]
        stacked.append(np.asarray([center - radius, center + radius], dtype=np.float64))
    points = np.vstack(stacked)
    lower = points.min(axis=0)
    upper = points.max(axis=0)
    span = float(np.max(upper - lower))
    if span <= 0.0:
        raise BundleError("Stored geometry has zero extent.")
    pad = margin * span
    mid = 0.5 * (lower + upper)
    half = 0.5 * span + pad
    return (
        (float(mid[0] - half), float(mid[0] + half)),
        (float(mid[1] - half), float(mid[1] + half)),
    )


def _make_writer(path: Path, *, fps: int):
    from matplotlib import animation

    backend = VIDEO_SUFFIXES.get(path.suffix.lower())
    if backend is None:
        raise BundleError(
            f"Unsupported output suffix '{path.suffix}'; use "
            f"{' or '.join(sorted(VIDEO_SUFFIXES))}."
        )
    if not animation.writers.is_available(backend):
        raise BundleError(
            f"The '{backend}' animation writer required for {path.suffix} files is "
            "not available. Install it, or choose the other output suffix."
        )
    if backend == "ffmpeg":
        return animation.FFMpegWriter(
            fps=fps,
            codec="libx264",
            bitrate=-1,
            extra_args=["-pix_fmt", "yuv420p"],
            metadata={
                "title": "SDF inverse contour convergence",
                "comment": "Accepted iterates from run_sdf_inverse_comparison.py",
            },
        )
    return animation.PillowWriter(fps=fps)


def _render(bundle: dict[str, Any], args: argparse.Namespace, output: Path) -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    solvers = list(args.solvers)
    stages = max(
        bundle["solvers"][solver]["trajectory"]["iteration"].size for solver in solvers
    )
    schedule = _frame_schedule(
        stages=stages,
        hold_frames=args.hold_frames,
        morph_frames=args.morph_frames,
        final_hold_frames=args.final_hold_frames,
    )
    x_limits, y_limits = _view_limits(bundle, margin=args.zoom_margin)

    target_center = bundle["target_center"]
    target_radius = bundle["target_radius"]
    if bundle["exact_boundary"] is not None:
        truth_outline = _closed(bundle["exact_boundary"])
    else:
        truth_angles = np.linspace(0.0, 2.0 * np.pi, 721, dtype=np.float64)
        truth_outline = np.column_stack(
            (
                target_center[0] + target_radius * np.cos(truth_angles),
                target_center[1] + target_radius * np.sin(truth_angles),
            )
        )
    truth_x, truth_y = truth_outline[:, 0], truth_outline[:, 1]

    tiny = float(np.finfo(np.float64).tiny)
    all_losses = np.concatenate(
        [bundle["solvers"][solver]["trajectory"]["loss"] for solver in solvers]
    )
    # A converged run can reach an exact zero loss, which has no place on a
    # logarithmic axis; the floor is the smallest positive loss actually seen.
    positive_losses = all_losses[all_losses > 0.0]
    loss_floor = max(
        float(np.min(positive_losses)) if positive_losses.size else tiny, tiny
    )
    loss_ceiling = float(np.max(all_losses))

    figure = plt.figure(figsize=(11.0, 7.6), constrained_layout=True)
    grid = figure.add_gridspec(2, len(solvers), height_ratios=(2.15, 1.0))
    benchmark = str(bundle["metrics"].get("benchmark", bundle["path"].name))
    figure.suptitle(
        f"Accepted contour convergence  |  {benchmark}\n"
        f"{bundle['path'].name}  |  identical geometry, objective, and "
        "finite-difference policy; only the forward solver differs",
        fontsize=11,
    )

    panels: dict[str, dict[str, Any]] = {}
    for column, solver in enumerate(solvers):
        record = bundle["solvers"][solver]
        axis = figure.add_subplot(grid[0, column])
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlim(*x_limits)
        axis.set_ylim(*y_limits)
        axis.grid(True, alpha=0.2)
        axis.set_xlabel("x (m)")
        if column == 0:
            axis.set_ylabel("y (m)")
        axis.set_title(SOLVER_LABELS[solver], color=SOLVER_COLORS[solver])
        axis.plot(
            truth_x,
            truth_y,
            color="black",
            linestyle="--",
            linewidth=1.4,
            zorder=5,
            label="analytic target",
        )
        initial_points = _closed(record["geometry"]["geometry_trajectory"][0])
        axis.plot(
            initial_points[:, 0],
            initial_points[:, 1],
            color="0.65",
            linewidth=1.0,
            zorder=2,
            label="initial contour",
        )
        (curve_line,) = axis.plot(
            [],
            [],
            color=SOLVER_COLORS[solver],
            linewidth=2.2,
            zorder=3,
            label="accepted iterate",
        )
        (node_markers,) = axis.plot(
            [],
            [],
            linestyle="none",
            marker="o",
            markersize=2.4,
            color=SOLVER_COLORS[solver],
            alpha=0.75,
            zorder=4,
        )
        annotation = axis.text(
            0.03,
            0.03,
            "",
            transform=axis.transAxes,
            fontsize=8.5,
            family="monospace",
            verticalalignment="bottom",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.82},
        )
        axis.legend(loc="upper right", fontsize=8, framealpha=0.85)
        panels[solver] = {
            "axis": axis,
            "curve": curve_line,
            "nodes": node_markers,
            "annotation": annotation,
        }

    loss_axis = figure.add_subplot(grid[1, :])
    loss_axis.set_yscale("log")
    loss_axis.set_xlabel("accepted iteration")
    loss_axis.set_ylabel("training loss")
    loss_axis.grid(True, which="both", alpha=0.25)
    loss_axis.set_xlim(-0.3, stages - 0.7)
    loss_axis.set_ylim(0.25 * loss_floor, 4.0 * loss_ceiling)
    markers: dict[str, Any] = {}
    for solver in solvers:
        trajectory = bundle["solvers"][solver]["trajectory"]
        losses = np.maximum(trajectory["loss"], loss_floor)
        loss_axis.plot(
            trajectory["iteration"],
            losses,
            color=SOLVER_COLORS[solver],
            marker="o",
            markersize=4.0,
            linewidth=1.4,
            alpha=0.35,
        )
        (marker,) = loss_axis.plot(
            [],
            [],
            color=SOLVER_COLORS[solver],
            marker="o",
            markersize=8.0,
            linewidth=2.4,
            label=SOLVER_LABELS[solver],
        )
        markers[solver] = marker
    loss_axis.legend(loc="upper right", fontsize=9)

    writer = _make_writer(output, fps=args.fps)
    print(
        f"Rendering {len(schedule)} frames at {args.fps} fps "
        f"({len(schedule) / args.fps:.1f} s) -> {output}",
        flush=True,
    )
    with writer.saving(figure, str(output), args.dpi):
        for frame_index, (stage, alpha) in enumerate(schedule):
            for solver in solvers:
                record = bundle["solvers"][solver]
                trajectory = record["trajectory"]
                geometry = record["geometry"]["geometry_trajectory"]
                contour, iterate = _stage_contour(geometry, stage=stage, alpha=alpha)
                closed_contour = _closed(contour)
                panel = panels[solver]
                panel["curve"].set_data(closed_contour[:, 0], closed_contour[:, 1])
                panel["nodes"].set_data(contour[:, 0], contour[:, 1])
                center_error_mm = 1.0e3 * math.hypot(
                    trajectory["center_x_m"][iterate] - target_center[0],
                    trajectory["center_y_m"][iterate] - target_center[1],
                )
                radius_error_mm = 1.0e3 * abs(
                    trajectory["radius_m"][iterate] - target_radius
                )
                shape_lines = []
                if (
                    "raw_amplitude" in trajectory
                    and bundle["target_amplitude"] is not None
                ):
                    shape_lines.append(
                        "ampl err   "
                        f"{abs(trajectory['raw_amplitude'][iterate] - bundle['target_amplitude']):.3e}"
                    )
                if (
                    "raw_rotation" in trajectory
                    and bundle["target_rotation_radians"] is not None
                ):
                    shape_lines.append(
                        "rot err    "
                        f"{abs(trajectory['raw_rotation'][iterate] - bundle['target_rotation_radians']):.3e} rad"
                    )
                exhausted = iterate == trajectory["iteration"].size - 1
                if exhausted and stage > iterate:
                    status = (
                        "converged"
                        if bool(record["metrics"].get("converged", False))
                        else str(record["metrics"].get("stop_reason", "stopped"))
                    )
                    tag = f"  [{status}]"
                elif alpha > 0.0:
                    tag = "  [interpolated]"
                else:
                    tag = ""
                panel["annotation"].set_text(
                    "\n".join(
                        [
                            f"iteration {iterate:d}{tag}",
                            f"loss       {trajectory['loss'][iterate]:.3e}",
                            f"rel L2     {trajectory['relative_l2_error'][iterate]:.3e}",
                            f"center err {center_error_mm:.4f} mm",
                            f"radius err {radius_error_mm:.4f} mm",
                            *shape_lines,
                        ]
                    )
                )
                visited = trajectory["iteration"][: iterate + 1]
                markers[solver].set_data(
                    visited,
                    np.maximum(trajectory["loss"][: iterate + 1], loss_floor),
                )
            writer.grab_frame()
            if (frame_index + 1) % 25 == 0 or frame_index + 1 == len(schedule):
                print(f"  frame {frame_index + 1}/{len(schedule)}", flush=True)
    plt.close(figure)
    return len(schedule)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    bundle_path = args.bundle
    if not bundle_path.is_absolute():
        bundle_path = REPOSITORY_ROOT / bundle_path
    output = args.output
    if output is None:
        output = bundle_path / "contour_evolution.mp4"
    elif not output.is_absolute():
        output = REPOSITORY_ROOT / output
    if output.exists() and not args.overwrite:
        print(f"Refusing to replace {output} without --overwrite.", file=sys.stderr)
        return 1

    try:
        bundle = _load_bundle(bundle_path, args.solvers)
        output.parent.mkdir(parents=True, exist_ok=True)
        frames = _render(bundle, args, output)
    except BundleError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    size_mb = output.stat().st_size / 1.0e6
    print(f"\nWrote {output} ({frames} frames, {size_mb:.2f} MB)", flush=True)
    for solver in args.solvers:
        metrics = bundle["solvers"][solver]["metrics"]
        print(
            f"  {SOLVER_LABELS[solver]:>5}: "
            f"{bundle['solvers'][solver]['trajectory']['iteration'].size} accepted "
            f"iterates, stop_reason={metrics.get('stop_reason', 'unknown')}, "
            f"final rel L2={metrics.get('final_training_relative_l2', float('nan')):.3e}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
