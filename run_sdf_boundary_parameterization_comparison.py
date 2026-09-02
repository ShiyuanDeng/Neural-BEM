#!/usr/bin/env python3
"""Run the isolated neural-SDF boundary-parameterization comparison.

This driver is intentionally independent of ``solver_select`` and every BIE
pipeline.  It extracts one shared contour for each shape/grid/sample case,
fits Method A once, and fits Methods B and C for every requested bandwidth.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parent
SOLVERS_ROOT = REPOSITORY_ROOT / "solvers"
if str(SOLVERS_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVERS_ROOT))

from sdf_to_ordered_boundary.experiment import (  # noqa: E402
    analytic_comparison_shapes,
    comparison_profile,
    run_comparison_experiment,
)


def _integer_list(value: str, *, label: str, minimum: int) -> tuple[int, ...]:
    tokens = [token.strip() for token in str(value).split(",")]
    if not tokens or any(not token for token in tokens):
        raise argparse.ArgumentTypeError(f"{label} must be a comma-separated integer list.")
    try:
        values = tuple(int(token) for token in tokens)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{label} must be a comma-separated integer list."
        ) from exc
    if any(item < minimum for item in values):
        raise argparse.ArgumentTypeError(f"Every {label} value must be at least {minimum}.")
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError(f"{label} must not contain duplicates.")
    return values


def _grid_shapes(value: str) -> tuple[tuple[int, int], ...]:
    shapes: list[tuple[int, int]] = []
    for raw_token in str(value).split(","):
        token = raw_token.strip().lower()
        if not token:
            raise argparse.ArgumentTypeError(
                "grid resolutions must be comma-separated N or NYxNX values."
            )
        parts = token.split("x")
        if len(parts) == 1:
            parts = [parts[0], parts[0]]
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(
                "grid resolutions must be comma-separated N or NYxNX values."
            )
        try:
            shape = (int(parts[0]), int(parts[1]))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "grid resolutions must be comma-separated N or NYxNX values."
            ) from exc
        if min(shape) < 2:
            raise argparse.ArgumentTypeError("Every grid dimension must be at least 2.")
        shapes.append(shape)
    if len(set(shapes)) != len(shapes):
        raise argparse.ArgumentTypeError("grid resolutions must not contain duplicates.")
    return tuple(shapes)


def _shape_names(value: str) -> tuple[str, ...]:
    names = tuple(token.strip().lower() for token in str(value).split(",") if token.strip())
    if not names:
        raise argparse.ArgumentTypeError("shapes must contain at least one name.")
    return names


def build_parser() -> argparse.ArgumentParser:
    available_shapes = tuple(shape.name for shape in analytic_comparison_shapes())
    parser = argparse.ArgumentParser(
        description=(
            "Compare periodic spline, Fourier least-squares, and SDF-refined "
            "Fourier boundary parameterizations outside all active solvers."
        )
    )
    parser.add_argument(
        "--profile",
        choices=("smoke", "study"),
        default="smoke",
        help="Reproducible sweep/resolution preset (default: smoke).",
    )
    parser.add_argument(
        "--output",
        "--output-dir",
        dest="output_dir",
        type=Path,
        help=(
            "Artifact directory. The default is a timestamped directory below "
            "results/sdf_boundary_parameterization/."
        ),
    )
    parser.add_argument(
        "--shapes",
        default=",".join(available_shapes),
        help=(
            "Comma-separated analytic cases. Available: " + ", ".join(available_shapes)
        ),
    )
    parser.add_argument(
        "--grid-resolutions",
        type=_grid_shapes,
        help="Optional comma-separated grid sizes, e.g. 65,129 or 65x81.",
    )
    parser.add_argument(
        "--projected-samples",
        help="Optional comma-separated projected-loop sample counts.",
    )
    parser.add_argument(
        "--bandwidths",
        help="Optional comma-separated Fourier bandwidths.",
    )
    parser.add_argument(
        "--kress-samples",
        help=(
            "Optional comma-separated even node counts used to sample each frozen "
            "final curve without refitting."
        ),
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip PNG generation while retaining JSON, CSV, and NPZ artifacts.",
    )
    return parser


def _parse_selected_shapes(parser: argparse.ArgumentParser, value: str):
    available = {shape.name: shape for shape in analytic_comparison_shapes()}
    try:
        names = _shape_names(value)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    unknown = sorted(set(names) - set(available))
    if unknown:
        parser.error(
            "unknown shape(s): "
            + ", ".join(unknown)
            + "; available: "
            + ", ".join(available)
        )
    if len(set(names)) != len(names):
        parser.error("--shapes must not contain duplicates.")
    return tuple(available[name] for name in names)


def _default_output_directory(profile_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        REPOSITORY_ROOT
        / "results"
        / "sdf_boundary_parameterization"
        / f"{profile_name}-{timestamp}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = comparison_profile(args.profile)
    try:
        if args.grid_resolutions is not None:
            settings = replace(settings, grid_shapes=args.grid_resolutions)
        if args.projected_samples is not None:
            settings = replace(
                settings,
                projected_sample_counts=_integer_list(
                    args.projected_samples,
                    label="projected sample",
                    minimum=8,
                ),
            )
        if args.bandwidths is not None:
            settings = replace(
                settings,
                bandwidths=_integer_list(
                    args.bandwidths,
                    label="bandwidth",
                    minimum=1,
                ),
            )
        if args.kress_samples is not None:
            settings = replace(
                settings,
                metrics=replace(
                    settings.metrics,
                    kress_sample_counts=_integer_list(
                        args.kress_samples,
                        label="Kress sample",
                        minimum=4,
                    ),
                ),
            )
    except (argparse.ArgumentTypeError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    selected_shapes = _parse_selected_shapes(parser, args.shapes)
    output_directory = args.output_dir or _default_output_directory(settings.name)
    result = run_comparison_experiment(
        output_directory,
        profile=settings,
        shapes=selected_shapes,
        make_plots=not args.no_plots,
    )
    print(f"artifacts: {result.output_directory}")
    print(f"shared front ends: {result.frontend_count}")
    print(f"method rows: {len(result.records)}")
    print(
        "statuses: "
        + ", ".join(
            f"{status}={count}" for status, count in sorted(result.status_counts.items())
        )
    )
    print(f"metrics CSV: {result.metrics_csv_path}")
    print(f"manifest: {result.manifest_path}")
    incomplete = any(
        record.status == "failed" or record.metrics_failure_reason is not None
        for record in result.records
    )
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
