#!/usr/bin/env python3
"""Review saved acquisition trajectories; no Torch, BEM, or extraction.

Example:
    python motion_review.py --run-dir /path/to/completed/run --output-dir /path/to/review

Outputs contain measured comparisons and require scientific review before any
promotion. Curated conclusions from an earlier run are never carried forward.
The default output is a new ``generated`` subdirectory beside this script.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter

import numpy as np


ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "run_implicit_mlp_iteration2_matched.py").exists())
DEFAULT_RUN = ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final/inverse-20260908T170732213677Z"
DEFAULT_TARGET = ROOT / "results/inverse/implicit_mlp/2026-09-08/star/kress_responses.npz"
PLAN = ROOT / "docs/iterations/implicit_mlp/iteration_02/02_proposals/04_final_plan.md"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def arc_weights(points):
    lengths = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
    if np.any(lengths == 0):
        raise ValueError("Saved polygon contains duplicate consecutive vertices")
    return (lengths + np.roll(lengths, 1)) / (2 * lengths.sum())


def distances(reference, polygon):
    edge = np.roll(polygon, -1, axis=0) - polygon
    squared_lengths = np.einsum("si,si->s", edge, edge)
    if np.any(squared_lengths == 0):
        raise ValueError("Distance polygon contains duplicate consecutive vertices")
    pieces = []
    for batch in np.array_split(reference, max(1, math.ceil(len(reference) / 128))):
        delta = batch[:, None] - polygon[None]
        fraction = np.clip(np.einsum("nsi,si->ns", delta, edge) / squared_lengths, 0, 1)
        difference = delta - fraction[:, :, None] * edge[None]
        pieces.append(np.sqrt(np.einsum("nsi,nsi->ns", difference, difference).min(axis=1)))
    return np.concatenate(pieces)


def symmetric_distances(curve, target):
    forward, reverse = distances(curve, target), distances(target, curve)
    curve_weights, target_weights = arc_weights(curve), arc_weights(target)
    forward_mean, reverse_mean = float(curve_weights @ forward), float(target_weights @ reverse)
    forward_ms, reverse_ms = float(curve_weights @ forward ** 2), float(target_weights @ reverse ** 2)
    return {
        "curve_to_target_mean_m": forward_mean,
        "curve_to_target_rms_m": math.sqrt(forward_ms),
        "curve_to_target_max_m": float(forward.max()),
        "target_to_curve_mean_m": reverse_mean,
        "target_to_curve_rms_m": math.sqrt(reverse_ms),
        "target_to_curve_max_m": float(reverse.max()),
        "symmetric_mean_m": .5 * (forward_mean + reverse_mean),
        "symmetric_rms_m": math.sqrt(.5 * (forward_ms + reverse_ms)),
        "symmetric_hausdorff_m": float(max(forward.max(), reverse.max())),
    }


def exact_target(count):
    theta = np.arange(count) * 2 * np.pi / count
    return .5 + (.05 + .0125 * np.cos(5 * theta))[:, None] * np.column_stack((np.cos(theta), np.sin(theta)))


def signed_score(spectrum):
    effects = spectrum.get("signed_effect_by_mode")
    return float(sum(effects.values())) if effects and all(v is not None for v in effects.values()) else None


def radial_metrics(radial):
    result = {"center_distance_m": float(np.linalg.norm(np.array(radial["center_m"]) - .5))}
    if not radial.get("polar_single_valued") or radial.get("radial_amplitudes_m") is None:
        result.update(polar_m5_interpretable=False, polar_m5_uninterpretable_reason="Saved contour is not polar single-valued about its polygon area centroid")
        return result
    amplitudes = np.asarray(radial["radial_amplitudes_m"])
    coefficient = radial["radial_complex_coefficients"][5]
    # Stored theta=-pi+2pi*j/N: convert FFT coefficients to physical theta.
    cosine, sine = -2 * coefficient["real"], 2 * coefficient["imag"]
    wrong_modes = np.r_[np.arange(2, 5), np.arange(6, 11)]
    result.update(
        polar_m5_interpretable=True,
        mean_radius_m=float(amplitudes[0]),
        polar_m5_amplitude_m=float(amplitudes[5]),
        polar_m5_cosine_m=cosine,
        polar_m5_sine_m=sine,
        polar_m5_coefficient_error_m=math.hypot(cosine - .0125, sine),
        polar_m5_rotation_degrees=math.degrees(math.atan2(sine, cosine) / 5),
        polar_wrong_modes_2_to_10_excluding5_rms_m=float(np.sqrt(.5 * np.sum(amplitudes[wrong_modes] ** 2))),
        polar_amplitudes_0_to_20_m=amplitudes[:21].tolist(),
    )
    return result


def review_arm(source, name, target, hashes):
    files = {}
    for filename in ("geometry_trajectory.json", "metrics.json", "fresh_proposal_geometry.json", "trials.jsonl"):
        path = source / name / filename
        hashes[name + "/" + filename] = sha256(path)
        files[filename] = ([json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                           if filename.endswith("jsonl") else json.loads(path.read_text()))
    metrics = files["metrics.json"]
    by_iteration = {int(row["iteration"]): row for row in metrics["trajectory"]}
    trials = files["trials.jsonl"]
    accepted = {int(row["iteration"]) + 1: index + 1 for index, row in enumerate(trials) if row.get("accepted")}
    rows = []
    for geometry in sorted(files["geometry_trajectory.json"], key=lambda row: row["iteration"]):
        iteration = int(geometry["iteration"])
        metric = by_iteration[iteration]
        if iteration and iteration not in accepted:
            raise ValueError(f"{name} geometry state {iteration} has no saved accepted trial")
        row = {
            "iteration": iteration,
            "attempted_candidates_through_accept": accepted.get(iteration, 0),
            "raw_distances": symmetric_distances(np.asarray(geometry["raw_contour"]), target),
            "converted_distances": symmetric_distances(np.asarray(geometry["converted_contour"]), target),
            "field_statistics": geometry["field_statistics"],
            "evaluation_3ghz_relative_l2": metric.get("evaluation_3ghz_relative_l2"),
            "conversion_error_m": metric.get("conversion_error_m"),
            "conversion_refinement_change_m": metric.get("conversion_refinement_change_m"),
            **radial_metrics(geometry["radial_spectrum"]),
        }
        for kind in ("raw", "converted"):
            spectrum = geometry.get(kind + "_motion_spectrum")
            if spectrum is None:
                continue
            row[kind + "_motion"] = {
                "rms_m": spectrum.get("rms"),
                "signed_effect_by_normal_arclength_mode_m2": spectrum.get("signed_effect_by_mode"),
                "signed_effect_through_mode20_m2": signed_score(spectrum),
                "missing_normal_roots": geometry.get(kind + "_correspondence", {}).get("missing_normal_intersections"),
            }
        rows.append(row)
    proposals = []
    for row in files["fresh_proposal_geometry.json"]:
        if row.get("scale_label") != "common_predicted_rms_20um":
            continue
        proposals.append({
            "iteration": row["iteration"], "direction": row["direction"],
            "predicted_score_m2": signed_score(row.get("V_n_spectrum", {})),
            "actual_score_m2": signed_score(row.get("actual_raw_motion_spectrum", {})),
            "finite_probe_failure": row.get("finite_probe_failure"),
        })
    return {
        "acquisition": "paired8" if name == "E0" else "multistatic8",
        "accepted_updates": metrics["accepted_updates"],
        "attempted_candidates": metrics["candidate_evaluations"],
        "inverse_seconds": metrics["inverse_seconds"],
        "rejection_counts": metrics["rejection_reason_counts"],
        "trajectory": rows,
        "geometry_states_reviewed": [row["iteration"] for row in rows],
        "selected_proposal_states": sorted({row["iteration"] for row in proposals}),
        "proposals_at_common_20um_rms": proposals,
    }


def matched_comparisons(arms):
    budgets = [set(row["attempted_candidates_through_accept"] for row in arm["trajectory"])
               for arm in arms.values()]
    cap = min(arm["attempted_candidates"] for arm in arms.values())
    selected = sorted((set.intersection(*budgets) | {cap}) - {0})
    comparisons = []
    for budget in selected:
        comparison = {"candidate_budget": budget, "arms": {}}
        for name, arm in arms.items():
            eligible = [row for row in arm["trajectory"] if row["attempted_candidates_through_accept"] <= budget]
            if not eligible:
                continue
            row = eligible[-1]
            comparison["arms"][name] = {
                "iteration": row["iteration"],
                "attempted_candidates_through_accept": row["attempted_candidates_through_accept"],
                "raw_symmetric_rms_m": row["raw_distances"]["symmetric_rms_m"],
                "converted_symmetric_rms_m": row["converted_distances"]["symmetric_rms_m"],
                "polar_m5_coefficient_error_m": row.get("polar_m5_coefficient_error_m"),
                "evaluation_3ghz_relative_l2": row.get("evaluation_3ghz_relative_l2"),
            }
        comparisons.append(comparison)
    return comparisons


def render_markdown(report):
    def formatted(value, scale=1, digits=3):
        return "unavailable" if value is None else f"{value * scale:.{digits}f}"
    rows = {name: arm["trajectory"][-1] for name, arm in report["arms"].items()}
    lines = ["# Acquisition motion measurements", "", f"Source: `{report['source_run']}`.", "",
             "Saved-data algebra only; no inverse, BEM, or extraction. These measurements require review before promoting a factor.", "",
             "| Final saved geometry | Paired-8 | Multistatic-8 |", "|---|---:|---:|"]
    fields = [
        ("Accepted state", "iteration", 1, 0),
        ("Candidates through accepted state", "attempted_candidates_through_accept", 1, 0),
        ("Raw symmetric RMS (mm)", ("raw_distances", "symmetric_rms_m"), 1000, 3),
        ("Raw symmetric mean (mm)", ("raw_distances", "symmetric_mean_m"), 1000, 3),
        ("Raw sampled Hausdorff (mm)", ("raw_distances", "symmetric_hausdorff_m"), 1000, 3),
        ("Target-to-raw mean (mm)", ("raw_distances", "target_to_curve_mean_m"), 1000, 3),
        ("Converted symmetric RMS (mm)", ("converted_distances", "symmetric_rms_m"), 1000, 3),
        ("Centroid error (mm)", "center_distance_m", 1000, 3),
        ("Polar m5 coefficient error (mm)", "polar_m5_coefficient_error_m", 1000, 3),
        ("Polar m5 amplitude (mm)", "polar_m5_amplitude_m", 1000, 3),
        ("Polar m5 rotation from target (deg)", "polar_m5_rotation_degrees", 1, 3),
        ("Modes 2–10 RMS excluding 5 (mm)", "polar_wrong_modes_2_to_10_excluding5_rms_m", 1000, 3),
        ("Shared 3 GHz relative error", "evaluation_3ghz_relative_l2", 1, 6),
    ]
    for label, key, scale, digits in fields:
        values = [row.get(key[0], {}).get(key[1]) if isinstance(key, tuple) else row.get(key)
                  for row in rows.values()]
        lines.append("| " + label + " | " + " | ".join(formatted(value, scale, digits) for value in values) + " |")
    lines += ["", "| Shared candidate budget | Paired accepted state | Multistatic accepted state | Paired raw RMS (mm) | Multistatic raw RMS (mm) |",
              "|---:|---:|---:|---:|---:|"]
    for comparison in report["matched_candidate_budgets"]:
        a, b = (comparison["arms"][name] for name in ("E0", "E1"))
        lines.append(f"| {comparison['candidate_budget']} | {a['iteration']} | {b['iteration']} | "
                     f"{formatted(a['raw_symmetric_rms_m'], 1000)} | {formatted(b['raw_symmetric_rms_m'], 1000)} |")
    for name, arm in report["arms"].items():
        valid_scores = [row["raw_motion"]["signed_effect_through_mode20_m2"] for row in arm["trajectory"]
                        if row.get("raw_motion", {}).get("signed_effect_through_mode20_m2") is not None]
        states = arm["selected_proposal_states"]
        lines += ["", f"{name}: {sum(value > 0 for value in valid_scores)}/{len(valid_scores)} interpretable saved raw motions have positive nearest-target descent scores; "
                  f"their sum is {sum(valid_scores):.8g} m². Proposal diagnostics cover saved states {states}. "
                  "Scores from selected proposal states must not be extrapolated to unmeasured states."]
    lines += ["", *[description + "\n" for description in report["methods"].values()],
              "The controlling plan requires actual neural geometric improvement at matched work; training loss alone does not qualify. "
              "Review field conditioning, phase-aware mode error, both boundary-distance directions, accepted/rejected geometry, and shared evaluation before choosing a longer run or another bounded diagnostic.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--target-archive", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--target-samples", type=int, default=4096)
    args = parser.parse_args(argv)
    if args.output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        args.output_dir = Path(__file__).resolve().parent / ("recheck-" + stamp)
    if args.target_samples < 1024:
        parser.error("--target-samples must be at least 1024")
    started = perf_counter()
    source, output = args.run_dir.resolve(), args.output_dir.resolve()
    if source == output or source in output.parents:
        parser.error("--output-dir must be outside the immutable source run directory")
    if any((output / name).exists() for name in ("motion_review.json", "motion_review.md")):
        parser.error("Choose a fresh --output-dir; existing review evidence must not be overwritten")
    with np.load(args.target_archive, allow_pickle=False) as archive:
        archived_target = archive["exact_boundary_points"]
    np.testing.assert_allclose(archived_target, exact_target(len(archived_target)), rtol=0, atol=1e-14)
    target = exact_target(args.target_samples)
    report = {
        "source_run": str(source), "reproduce_argv": sys.argv,
        "source_sha256": {"target_archive": sha256(args.target_archive), "controlling_final_plan": sha256(PLAN),
                          "review_script": sha256(Path(__file__))},
        "methods": {
            "boundary_distance": "Arc-length-weighted directed point-to-closed-polyline distances use saved raw/converted vertices and "
                f"{args.target_samples} exact target vertices. Symmetric means average directed means; symmetric RMS averages directed mean squares before the square root. "
                "Hausdorff is the maximum of the sampled directed maxima, not an exact smooth-curve supremum.",
            "target": f"The analytic target r=0.05+0.0125*cos(5 theta), center (0.5,0.5), was validated against {len(archived_target)} archived vertices to 1e-14 m.",
            "radial_phase": "The stored radial FFT uses theta_j=-pi+2pi*j/N about each polygon AREA centroid (shoelace formula), not an arclength centroid. "
                "Physical cosine/sine coefficients are 2*(-1)^m*Re(c_m), -2*(-1)^m*Im(c_m). "
                "The m5 coefficient error is its distance from (0.0125 m,0); divide by sqrt(2) for its radial RMS contribution. Center error is scored separately.",
            "signed_normal_score": "Saved normal-motion scores are arc-weighted inner products with nearest-target normal projections. Positive scores locally decrease half squared distance "
                "at unique nearest points. Through-mode-20 scores are not finite total geometric-error changes; normal/arclength mode 5 is not polar mode 5.",
            "matched_work": "Shared budgets are derived from accepted trial counts common to both arms plus the minimum completed candidate count. "
                "Each comparison uses the latest saved accepted geometry at or below that budget. No future accepted update is credited.",
        },
        "arms": {}, "assessment": "Measurements only; scientific promotion requires review of this run. No conclusion from an earlier run is inherited.",
    }
    for name in ("E0", "E1"):
        report["arms"][name] = review_arm(source, name, target, report["source_sha256"])
    report["matched_candidate_budgets"] = matched_comparisons(report["arms"])
    report["work_seconds"] = perf_counter() - started
    output.mkdir(parents=True, exist_ok=True)
    (output / "motion_review.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (output / "motion_review.md").write_text(render_markdown(report))
    print(f"Saved {output / 'motion_review.json'} and motion_review.md in {report['work_seconds']:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
