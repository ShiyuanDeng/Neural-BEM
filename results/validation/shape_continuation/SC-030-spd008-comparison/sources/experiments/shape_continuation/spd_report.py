"""SC-020 report: rebuild the comparison table and figure from saved artifacts only.

No physical solves. Reads each arm's `result.json`, SPD's per-stage metrics and
the hybrid's per-stage endpoint scores, and the saved TOP-025 reference.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from .geometry import FourierCurve
from .spd_cases import CENTER, LENGTH, read, write


def spd_rows(directory):
    metrics = read(directory / "F" / "metrics.json")
    rows = []
    for stage in metrics["stages"]:
        terminal, score = stage["terminal"], stage["score"]
        rows.append(dict(stage=stage["stage"], outcome=terminal["stage_outcome"], stop=terminal["optimizer_stop"],
            accepted=terminal["accepted_steps"], loss=terminal["production_loss"],
            units=terminal["work"]["stage_work_units"], score=score))
    return metrics, rows


def hybrid_rows(directory, result):
    rows = []
    scores = {s["stage"]: s["score"] for s in result["stage_scores"]}
    for stage in result["stages"]:
        rows.append(dict(stage=int(stage["stage_label"].split("_")[1]), outcome=stage["outcome"],
            stop=stage["stop_reason"], accepted=stage["accepted_steps"], loss=stage["final_loss"],
            units=stage["work"]["stage_units"], score=scores.get(stage["stage_label"]),
            trials=stage["trial_status"]))
    return rows


def fmt(value, spec=".3g"):
    return "—" if value is None else format(value, spec)


def report(output):
    spd = read(output / "runs" / "spd" / "result.json")
    hybrid = read(output / "runs" / "hybrid" / "result.json")
    reference = read(output / "inputs" / "spd_top025_continuation_metrics.json")
    spd_metrics, spd_stage = spd_rows(output / "runs" / "spd")
    hybrid_stage = hybrid_rows(output / "runs" / "hybrid", hybrid)
    lines = ["| Arm | Stage | Outcome / stop | Accepted | Stage loss | Stage units | Hausdorff mm | IoU | "
             "Train rel. (0.5–1.25 GHz, 512 nodes) | Eval rel. (1.5, 2.5 GHz) | Qualified |",
             "|---|---:|---|---:|---:|---:|---:|---:|---|---|---|"]
    for arm, rows in (("spd", spd_stage), ("hybrid", hybrid_stage)):
        for row in rows:
            s = row["score"] or {}
            geometry = s.get("geometry", {})
            lines.append(f"| {arm} | {row['stage']} | {row['outcome']} / {row['stop']} | {row['accepted']} | "
                f"{fmt(row['loss'])} | {row['units']} | {fmt((geometry.get('maximum_matched_hausdorff_m') or 0)*1e3, '.4f')} | "
                f"{fmt(geometry.get('union_iou'), '.4f')} | {', '.join(fmt(x, '.2e') for x in s.get('training_errors', []))} | "
                f"{', '.join(fmt(x, '.2e') for x in s.get('evaluation_errors', []))} | {s.get('numerically_qualified')} |")
    summary = dict(
        spd=dict(status=spd["status"], recovered=spd["fresh_recovery_pass"], work_units=spd["work"]["budget_work_units"],
                 attempted_calls=spd["work"]["total_attempted"], active_wall_seconds=spd["work"]["active_wall_seconds"],
                 elapsed_seconds=spd["elapsed_seconds"],
                 final_state_sha256=spd["final_state_sha256"],
                 reproduces_top025=spd["final_state_sha256"] == reference["final_state_sha256"]),
        hybrid=dict(status=hybrid["status"], recovered=hybrid["fresh_recovery_pass"],
                    work_units=hybrid["work"]["work_units"], elapsed_seconds=hybrid["elapsed_seconds"],
                    solves=sum(hybrid["work"]["solves"].values()),
                    reciprocal_batches=sum(hybrid["work"]["reciprocal_batches"].values()),
                    trial_status={k: v for row in hybrid_stage for k, v in row["trials"].items()}))
    trial_totals = {}
    for row in hybrid_stage:
        for key, value in row["trials"].items():
            trial_totals[key] = trial_totals.get(key, 0) + value
    summary["hybrid"]["trial_status"] = trial_totals
    band = read(output / "manifest.json")["mapping"]["update_modes"]
    summary["normal_error_spectrum_mm"] = spectra(output, spd_metrics, hybrid, 16)
    if band != 16:
        summary[f"normal_error_spectrum_split_at_M{band}_mm"] = spectra(output, spd_metrics, hybrid, band)
    write(output / "comparison.json", dict(summary=summary, spd_stages=spd_stage, hybrid_stages=hybrid_stage))
    figure(output, spd_metrics, hybrid)
    return lines, summary


def truth_ellipse(output):
    spec = read(output / "inputs" / "scene_spec.json")
    return next(s for s in spec["scenes"] if s["id"] == "merge")["truth"][0]


def normal_error(curve, truth, count=4096):
    """Signed distance (package units) along each node's normal to the exact ellipse."""
    a, b = truth["semi_major"] / LENGTH, truth["semi_minor"] / LENGTH
    if truth["rotation"] or truth["center"] != [CENTER.real, CENTER.imag]:
        raise ValueError("Report assumes the axis-aligned merge ellipse at the scene centre.")
    nodes = curve.nodes(count)
    p, n = nodes.points, nodes.normals
    A = (n[:, 0] / a) ** 2 + (n[:, 1] / b) ** 2
    B = 2 * (p[:, 0] * n[:, 0] / a ** 2 + p[:, 1] * n[:, 1] / b ** 2)
    C = (p[:, 0] / a) ** 2 + (p[:, 1] / b) ** 2 - 1
    root = np.sqrt(B * B - 4 * A * C)
    r1, r2 = (-B + root) / (2 * A), (-B - root) / (2 * A)
    return nodes, np.where(np.abs(r1) < np.abs(r2), r1, r2)


def spectra(output, spd_metrics, hybrid, band=16):
    """Evaluation-only split of the normal error into arclength harmonics <=M and >M."""
    from .geometry import arclength_angles
    from .spd_cases import from_cartesian
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root), str(root / "solvers")]
    import run_fourier_topology_controller as driver
    truth = truth_ellipse(output)
    curves = dict(handoff=from_cartesian(driver.deserialize_state(read(output / "inputs" / "handoff.json")["state"]).components[0]),
                  spd_final=from_cartesian(driver.deserialize_state(spd_metrics["final_state"]).components[0]))
    for line in (output / "runs" / "hybrid" / "trajectory.jsonl").read_text().splitlines():
        row = json.loads(line)
        curves[f"hybrid_{row['stage']}"] = FourierCurve(np.array(row["coefficients"]["real"]) + 1j * np.array(row["coefficients"]["imag"]))
    rows = {}
    for name, curve in curves.items():
        nodes, h = normal_error(curve, truth)
        s, _ = arclength_angles(nodes)
        uniform = np.interp(np.linspace(0, 2 * np.pi, len(s), endpoint=False), np.r_[s, 2 * np.pi], np.r_[h, h[0]])
        amplitude = np.abs(np.fft.rfft(uniform)) / len(s) * 2 * LENGTH * 1e3
        rows[name] = dict(maximum=float(np.max(np.abs(h)) * LENGTH * 1e3),
                          within_update_band=float(np.linalg.norm(amplitude[:band + 1])),
                          beyond_update_band=float(np.linalg.norm(amplitude[band + 1:])))
    return rows


def figure(output, spd_metrics, hybrid):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .spd_cases import from_cartesian
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root), str(root / "solvers")]
    import run_fourier_topology_controller as driver
    spec = read(output / "inputs" / "scene_spec.json")
    truth = next(s for s in spec["scenes"] if s["id"] == "merge")["truth"][0]
    t = np.linspace(0, 2 * np.pi, 2000)
    ellipse = (truth["center"][0] + truth["semi_major"] * np.cos(t)) + 1j * (truth["center"][1] + truth["semi_minor"] * np.sin(t))
    handoff = from_cartesian(driver.deserialize_state(read(output / "inputs" / "handoff.json")["state"]).components[0])
    spd_final = from_cartesian(driver.deserialize_state(spd_metrics["final_state"]).components[0])
    hybrid_final = FourierCurve(np.array(hybrid["final_curve"]["real"]) + 1j * np.array(hybrid["final_curve"]["imag"]))

    def physical(curve, count=4096):
        return curve.values(count) * LENGTH + CENTER

    def normal_error(curve):
        # Signed distance along the normal to the exact ellipse, in mm.
        a, b = truth["semi_major"] / LENGTH, truth["semi_minor"] / LENGTH
        nodes = curve.nodes(4096)
        p, n = nodes.points, nodes.normals
        A = (n[:, 0] / a) ** 2 + (n[:, 1] / b) ** 2
        B = 2 * (p[:, 0] * n[:, 0] / a ** 2 + p[:, 1] * n[:, 1] / b ** 2)
        C = (p[:, 0] / a) ** 2 + (p[:, 1] / b) ** 2 - 1
        root_ = np.sqrt(B * B - 4 * A * C)
        r1, r2 = (-B + root_) / (2 * A), (-B - root_) / (2 * A)
        h = np.where(np.abs(r1) < np.abs(r2), r1, r2)
        angle = np.angle(nodes.points[:, 0] + 1j * nodes.points[:, 1] * a / b)
        order = np.argsort(angle)
        return angle[order], h[order] * LENGTH * 1e3

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    axes[0].plot(ellipse.real, ellipse.imag, "k--", lw=1.4, label="truth")
    for curve, style, label in ((handoff, "k:", "handoff (both arms)"), (spd_final, "C0-", "SPD final"),
                                (hybrid_final, "C3-", "hybrid final")):
        z = physical(curve)
        axes[0].plot(z.real, z.imag, style, lw=1.1, label=label)
    axes[0].set_aspect("equal")
    axes[0].set_title("merge: boundaries (m)")
    axes[0].legend(fontsize=8)
    for curve, style, label in ((handoff, "k:", "handoff"), (spd_final, "C0-", "SPD final"),
                                (hybrid_final, "C3-", "hybrid final")):
        angle, error = normal_error(curve)
        axes[1].plot(angle, error, style, lw=1, label=label)
    axes[1].set_xlabel("ellipse parameter angle (rad)")
    axes[1].set_ylabel("normal distance to truth (mm)")
    axes[1].set_title("Boundary error along the curve")
    axes[1].axhline(0, color="0.7", lw=.6)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output / "boundaries.png", dpi=160)
    plt.close(fig)


def verify(output, summary):
    """Frozen pass criteria of the SC-020 plan, plus source/input integrity."""
    from .spd_cases import digest, source_hashes, ROOT
    manifest = read(output / "manifest.json")
    current = source_hashes()
    recorded = manifest["source_sha256"]
    changed = sorted(k for k in set(current) | set(recorded) if current.get(k) != recorded.get(k))
    inputs_ok = all(digest(output / name) == item["sha256"] == digest(ROOT / item["source"])
                    for name, item in manifest["inputs"].items())
    hybrid = read(output / "runs" / "hybrid" / "result.json")
    final = hybrid.get("final") or {}
    stages_qualified = [s["score"]["numerically_qualified"] for s in hybrid["stage_scores"]]
    criteria = dict(
        spd_reference_reproduced=summary["spd"]["status"] == "COMPLETED_SCHEDULE" and summary["spd"]["reproduces_top025"],
        hybrid_schedule_complete=hybrid["status"] == "COMPLETED_SCHEDULE" and len(stages_qualified) == 4,
        hybrid_every_endpoint_qualified=bool(stages_qualified) and all(stages_qualified),
        hybrid_final_gates=dict(final.get("gates", {})),
        hybrid_final_gates_pass=bool(final.get("original_gates_pass")))
    passed = (criteria["spd_reference_reproduced"] and criteria["hybrid_schedule_complete"]
              and criteria["hybrid_every_endpoint_qualified"] and criteria["hybrid_final_gates_pass"])
    record = dict(status="PASS" if passed else "FAIL", criteria=criteria, inputs_unchanged=inputs_ok,
                  sources_changed_since_preparation=changed,
                  note="Sources changed after preparation must be report-only; numerical modules are hash-frozen.")
    write(output / "verification.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lines, summary = report(args.output)
    print("\n".join(lines))
    print(json.dumps(summary, indent=1))
    print(json.dumps(verify(args.output, summary), indent=1))


if __name__ == "__main__":
    main()
