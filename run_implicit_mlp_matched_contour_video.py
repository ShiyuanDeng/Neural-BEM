#!/usr/bin/env python3
"""Render stored paired/multistatic contour trajectories without rerunning physics.

The input is a directory created by ``run_implicit_mlp_iteration2_matched.py``.
It reads only saved ``geometry_trajectory.json`` and ``metrics.json`` files.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
DEFAULT_RUN = ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final/long-acquisition-20260908T174300326691Z"
COLORS = {"E0": "#2474ad", "E1": "#de7826"}
LABELS = {"E0": "Paired-8", "E1": "Multistatic-8"}


def closed(points):
    return np.vstack((points, points[:1]))


def target_star(samples=1024):
    theta = np.linspace(0., 2 * np.pi, samples, endpoint=False)
    radius = .05 + .0125 * np.cos(5 * theta)
    return np.column_stack((.5 + radius * np.cos(theta), .5 + radius * np.sin(theta)))


def load_arm(run_dir, arm):
    directory = run_dir / arm
    geometry_path = directory / "geometry_trajectory.json"
    metrics_path = directory / "metrics.json"
    if not geometry_path.is_file() or not metrics_path.is_file():
        raise ValueError(f"{arm} is missing saved geometry or metrics in {directory}")
    geometry = json.loads(geometry_path.read_text())
    metrics = json.loads(metrics_path.read_text())
    trajectory = metrics.get("trajectory", [])
    if not geometry or len(geometry) != len(trajectory):
        raise ValueError(f"{arm} geometry and metrics must contain the same nonzero number of states")
    if [row["iteration"] for row in geometry] != [row["iteration"] for row in trajectory]:
        raise ValueError(f"{arm} saved geometry and metrics iterations disagree")
    for row in geometry:
        for key in ("raw_contour", "converted_contour"):
            points = np.asarray(row[key], dtype=float)
            if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
                raise ValueError(f"{arm} iteration {row['iteration']} has invalid {key}")
    return geometry, trajectory


def cyclic_align(reference, candidate):
    if reference.shape != candidate.shape:
        raise ValueError("Stored contours have incompatible point counts")
    errors = [np.sum((reference - np.roll(candidate, shift, axis=0)) ** 2)
              for shift in range(len(reference))]
    return np.roll(candidate, int(np.argmin(errors)), axis=0)


def frame_points(rows, index, alpha, key):
    current = np.asarray(rows[index][key], dtype=float)
    if alpha == 0 or index + 1 == len(rows):
        return current
    following = cyclic_align(current, np.asarray(rows[index + 1][key], dtype=float))
    return (1 - alpha) * current + alpha * following


def schedule(count, hold, morph, final_hold):
    result = []
    for index in range(count):
        result.extend((index, 0.) for _ in range(hold))
        if index + 1 < count:
            result.extend((index, (step + 1) / (morph + 1)) for step in range(morph))
    result.extend((count - 1, 0.) for _ in range(final_hold))
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, default=None,
                        help="MP4 output path (default: <run-dir>/paired_multistatic_contours.mp4)")
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--hold-frames", type=int, default=4)
    parser.add_argument("--morph-frames", type=int, default=2,
                        help="Labelled visual interpolation between saved states; zero uses saved contours only.")
    parser.add_argument("--final-hold-frames", type=int, default=36)
    parser.add_argument("--dpi", type=int, default=140)
    parser.add_argument("--raw-only", action="store_true", help="Hide the saved Method-B converted contour.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print the rendering plan.")
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = args.run_dir / "paired_multistatic_contours.mp4"
    if any(value <= 0 for value in (args.fps, args.hold_frames, args.final_hold_frames, args.dpi)) or args.morph_frames < 0:
        parser.error("fps, hold frames, final hold frames and dpi must be positive; morph frames must be nonnegative")
    if args.output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    return args


def main(argv=None):
    args = parse_args(argv)
    run_dir = args.run_dir.resolve()
    if not (run_dir / "metrics.json").is_file():
        raise SystemExit(f"Not a completed matched-run directory: {run_dir}")
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        raise SystemExit(f"Output already exists: {output}; use --overwrite to replace it")
    records = {arm: load_arm(run_dir, arm) for arm in ("E0", "E1")}
    frames = schedule(max(len(rows) for rows, _ in records.values()), args.hold_frames,
                      args.morph_frames, args.final_hold_frames)
    if args.dry_run:
        print(f"Validated E0={len(records['E0'][0])} and E1={len(records['E1'][0])} saved states.")
        print(f"Would render {len(frames)} frames at {args.fps} fps to {output} without rerunning the inverse.")
        return 0

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import animation
    if not animation.writers.is_available("ffmpeg"):
        raise SystemExit("Matplotlib cannot find ffmpeg; install ffmpeg or use an environment where it is available")

    truth = target_star()
    all_points = [truth]
    for rows, _ in records.values():
        all_points.extend(np.asarray(row["raw_contour"]) for row in rows)
        all_points.extend(np.asarray(row["converted_contour"]) for row in rows)
    points = np.vstack(all_points)
    span = float(np.max(points.max(axis=0) - points.min(axis=0)))
    center = .5 * (points.max(axis=0) + points.min(axis=0))
    half = .7 * span
    figure, axes = plt.subplots(1, 2, figsize=(11, 5.6), constrained_layout=True)
    panels = {}
    for axis, arm in zip(axes, ("E0", "E1")):
        rows, metrics = records[arm]
        axis.set(title=LABELS[arm], xlabel="x (m)", ylabel="y (m)", aspect="equal",
                 xlim=(center[0] - half, center[0] + half), ylim=(center[1] - half, center[1] + half))
        axis.grid(alpha=.2)
        axis.plot(*closed(truth).T, "k--", lw=1.2, label="target")
        axis.plot(*closed(np.asarray(rows[0]["raw_contour"])).T, color="0.65", lw=1, label="shared start")
        raw, = axis.plot([], [], color=COLORS[arm], lw=2.2, label="raw zero contour")
        converted, = axis.plot([], [], color=COLORS[arm], ls="--", lw=1.2, alpha=.85, label="Method-B contour")
        text = axis.text(.03, .03, "", transform=axis.transAxes, fontsize=8.5, family="monospace",
                         bbox={"boxstyle": "round", "facecolor": "white", "alpha": .85})
        axis.legend(loc="upper right", fontsize=8)
        panels[arm] = raw, converted, text
    figure.suptitle("Stored long star inverse trajectories — post-processing only", fontsize=12)
    writer = animation.FFMpegWriter(fps=args.fps, codec="libx264", bitrate=-1,
                                    extra_args=["-pix_fmt", "yuv420p"])
    print(f"Rendering {len(frames)} frames at {args.fps} fps to {output}", flush=True)
    with writer.saving(figure, str(output), args.dpi):
        for index, alpha in frames:
            for arm in ("E0", "E1"):
                rows, metrics = records[arm]
                state = min(index, len(rows) - 1)
                raw = frame_points(rows, state, alpha if state + 1 < len(rows) else 0., "raw_contour")
                converted = frame_points(rows, state, alpha if state + 1 < len(rows) else 0., "converted_contour")
                raw_line, converted_line, text = panels[arm]
                raw_line.set_data(*closed(raw).T)
                converted_line.set_visible(not args.raw_only)
                if not args.raw_only:
                    converted_line.set_data(*closed(converted).T)
                metric = metrics[state]
                suffix = " (interpolated)" if alpha else ""
                text.set_text(f"accepted update {metric['iteration']}{suffix}\n"
                              f"train loss {metric['training_loss']:.4g}\n"
                              f"3 GHz rel. L2 {metric['evaluation_3ghz_relative_l2']:.4g}\n"
                              f"mean error {1e3 * metric['mean_node_to_exact_boundary_distance_m']:.2f} mm")
            writer.grab_frame()
    plt.close(figure)
    print(f"Saved {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
