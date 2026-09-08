#!/usr/bin/env python3
"""Stage 0 exact polygon replay and frozen geometry benchmarks; never runs BEM.

The default replays terminal circle/star weights, captures every raw/projected
polygon encountered by production and base/refined audits, and compares full
geometry acceptance and rejection metadata using both implementations. Rejected
historical proposals were not saved in the September-8 bundles; that missing
coverage is recorded explicitly, and additional polygon archives can be supplied.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "solvers"))

from sdf_inverse.geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError, build_ordered_sdf_geometry
from sdf_inverse.models import SirenImplicitField2D
from sdf_to_ordered_boundary import frontend


def _load(bundle, iteration):
    checkpoint = torch.load(bundle / "kress_model.pt", map_location="cpu", weights_only=False)
    constructor = dict(checkpoint["constructor"], dtype=torch.float64)
    model = SirenImplicitField2D(**constructor)
    model.load_state_dict(checkpoint["state_dict"])
    with (bundle / "kress_trajectory.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    row = next(row for row in rows if int(float(row["iteration"])) == iteration)
    vector = np.array([float(value) for key, value in row.items() if key.startswith("raw_")])
    offset = 0
    with torch.no_grad():
        for parameter in model.parameters():
            count = parameter.numel()
            parameter.copy_(torch.from_numpy(vector[offset:offset + count]).reshape(parameter.shape))
            offset += count
    if offset != vector.size:
        raise ValueError("Saved trajectory vector does not match the checkpoint architecture.")
    return model, OrderedSDFGeometryConfig(**checkpoint["geometry_config"])


def _geometry_outcome(model, config):
    try:
        geometry = build_ordered_sdf_geometry(model, config)
    except OrderedSDFGeometryError as exc:
        return {"accepted": False, "exception_type": type(exc).__name__, "reason": str(exc),
                "rejection_reasons": list(getattr(exc, "rejection_reasons", ())),
                "conversion_error_m": getattr(exc, "conversion_error_m", None),
                "conversion_refinement_change_m": getattr(exc, "conversion_refinement_change_m", None)}, None
    return {"accepted": True, "conversion_error_m": geometry.maximum_conversion_error_m,
            "conversion_refinement_change_m": geometry.conversion_refinement_change_m}, geometry.curve.points


def run(args):
    torch.set_num_threads(args.threads)
    started = perf_counter()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    corpus, polygon_rows, builds = {}, [], []
    new_counter = frontend.polygon_self_intersection_count
    legacy_counter = frontend._polygon_self_intersection_count_legacy
    current_label = ""

    def exact_counter(points, *, relative_tolerance=1.e-12):
        polygon = np.ascontiguousarray(points, dtype=np.float64)
        digest = hashlib.sha256(polygon.tobytes() + repr(relative_tolerance).encode()).hexdigest()
        if digest not in corpus:
            old_start = perf_counter()
            old = legacy_counter(polygon, relative_tolerance=relative_tolerance)
            old_seconds = perf_counter() - old_start
            new_start = perf_counter()
            new = new_counter(polygon, relative_tolerance=relative_tolerance)
            new_seconds = perf_counter() - new_start
            if old != new:
                raise AssertionError(f"Polygon replay mismatch: {current_label}: {old} != {new}")
            corpus[digest] = polygon.copy()
            polygon_rows.append({"sha256": digest, "source": current_label,
                                 "points": len(polygon), "relative_tolerance": relative_tolerance,
                                 "legacy_count": old, "vectorized_count": new,
                                 "legacy_seconds": old_seconds, "vectorized_seconds": new_seconds})
        # Return the independently computed scalar answer while replaying.
        return next(row["legacy_count"] for row in polygon_rows if row["sha256"] == digest)

    selected = [("circle", 60), ("star", 47)]
    if args.all_selected_states:
        selected = [("circle", 55), ("circle", 60)] + [("star", n) for n in (0, 16, 32, 40, 47)]
    report = {"stage": 0, "inverse_or_bem_run": False, "saved_state_builds": builds,
              "polygons": polygon_rows, "historical_rejected_candidate_coverage": "unavailable: bundles contain no rejected weights or polygons",
              "additional_archives": args.extra_polygon_npz, "complete_requested_replay": False,
              "legacy_build_timing_note": "Replay checks and deduplicated scalar answers; exact scalar predicate timings are recorded per polygon."}

    def save():
        report["elapsed_seconds"] = perf_counter() - started
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        np.savez_compressed(output / "polygons.npz", **corpus)

    for case, iteration in selected:
        if perf_counter() - started >= args.max_seconds:
            report["stop_reason"] = "wall_time_cap_between_frozen_geometry_builds"
            save()
            return report
        current_label = f"{case}:accepted_state_{iteration}:production_and_base_refined_audit"
        model, config = _load(Path(args.bundles) / case, iteration)
        replay_start = perf_counter()
        with patch.object(frontend, "polygon_self_intersection_count", exact_counter):
            old_outcome, old_points = _geometry_outcome(model, config)
        replay_seconds = perf_counter() - replay_start
        fast_start = perf_counter()
        new_outcome, new_points = _geometry_outcome(model, config)
        fast_seconds = perf_counter() - fast_start
        assert old_outcome == new_outcome, (old_outcome, new_outcome)
        if old_points is not None:
            np.testing.assert_array_equal(old_points, new_points)
        row = {"case": case, "iteration": iteration, "legacy_replay_build_seconds": replay_seconds,
               "vectorized_build_seconds": fast_seconds, "identical_outcome": True,
               "identical_curve_arrays": old_points is not None, "outcome": new_outcome}
        builds.append(row)
        print(json.dumps(row), flush=True)
        save()

    # An intentionally underresolved fit checks geometry rejection propagation.
    # This is a fresh frozen-state audit, never a claimed historical proposal.
    current_label = "star:47:fresh_underresolved_conversion_rejection"
    model, config = _load(Path(args.bundles) / "star", 47)
    underresolved = replace(config, bandwidth=8)
    with patch.object(frontend, "polygon_self_intersection_count", exact_counter):
        old_outcome, _ = _geometry_outcome(model, underresolved)
    new_outcome, _ = _geometry_outcome(model, underresolved)
    assert old_outcome == new_outcome
    assert not new_outcome["accepted"], "Expected the deliberate underresolved fit to reject."
    report["fresh_rejection_replay"] = new_outcome

    for archive in args.extra_polygon_npz:
        with np.load(archive) as polygons:
            for key in polygons.files:
                current_label = f"archive:{archive}:{key}"
                exact_counter(polygons[key])
    for gap in (-2.e-12, 0., 2.e-12):
        current_label = f"synthetic_near_contact:gap={gap}"
        exact_counter(np.array([[0., 0.], [2., 0.], [2., 1.], [1., gap], [0., 1.]]))
    report["complete_requested_replay"] = True
    report["all_integer_counts_equal"] = True
    report["all_topology_conversion_and_rejection_outcomes_equal"] = True
    save()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundles", default=str(ROOT / "results/inverse/implicit_mlp/2026-09-08"))
    parser.add_argument("--output-dir", default=str(ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-implementation/geometry-runtime"))
    parser.add_argument("--all-selected-states", action="store_true")
    parser.add_argument("--extra-polygon-npz", action="append", default=[])
    parser.add_argument("--max-seconds", type=float, default=120.)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args(argv)
    if args.max_seconds <= 0 or args.threads < 1:
        parser.error("--max-seconds and --threads must be positive")
    run(args)


if __name__ == "__main__":
    main()
