#!/usr/bin/env python3
"""Bounded frozen-state iteration-2 diagnostics; no inverse run is launched.

Examples and the scientific stage gates live in
docs/iterations/implicit_mlp/iteration_02/02_proposals/04_final_plan.md.
Run individual stages to give every selected state its own work budget.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "solvers"))

import numpy as np
import torch
from sdf_inverse.frozen_diagnostics import (
    DiagnosticBudgetExceeded, WorkBudget, array_hash, curve_metric_diagnostic,
    field_only_repair, historical_transition, load_saved_case, neural_motion_diagnostic,
    report_geometry, saved_training_data, sha256,
)

STAGES = ("characterize", "curve_metric", "neural_motion", "field_repair", "conversion_audit")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--states", required=True, help="Comma-separated actual accepted state IDs, or all")
    parser.add_argument("--stages", default="characterize", help=",".join(STAGES))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-states", type=int, default=8)
    parser.add_argument("--max-evaluations", type=int, default=160)
    parser.add_argument("--max-wall-seconds", type=float, default=600)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--curve-modes", type=int, default=12)
    parser.add_argument("--motion-modes", type=int, default=20)
    parser.add_argument("--fd-step-m", type=float, default=2e-5)
    parser.add_argument("--gn-damping", type=float, default=1e-3)
    parser.add_argument("--tsvd-cutoff", type=float, default=1e-3)
    parser.add_argument("--curve-backtracks", type=int, default=4)
    parser.add_argument("--common-rms-motion-m", type=float, default=1e-5)
    parser.add_argument("--alphas", default="1,0.5,0.25")
    parser.add_argument("--repair-steps", type=int, default=25)
    parser.add_argument("--repair-learning-rate", type=float, default=1e-5)
    parser.add_argument("--repair-anchor-beta", type=float, default=1e8)
    parser.add_argument("--repair-samples", type=int, default=256)
    parser.add_argument("--production-factors", default="1,2")
    parser.add_argument("--audit-grids", default="257,513")
    parser.add_argument("--audit-samples", default="512,1024")
    args = parser.parse_args(argv)
    args.stages = args.stages.split(",")
    if not args.stages or any(stage not in STAGES for stage in args.stages):
        parser.error("Unknown diagnostic stage.")
    for name in ("max_states", "max_evaluations", "threads", "repair_samples"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    for name in ("max_wall_seconds", "fd_step_m", "gn_damping", "common_rms_motion_m", "repair_learning_rate", "repair_anchor_beta"):
        if not np.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be finite and positive")
    if not 1 <= args.curve_modes <= 24 or not 1 <= args.motion_modes <= 40:
        parser.error("Mode work caps: curve 1..24, motion 1..40 (qualification requires at least 12/20)")
    if not 0 <= args.curve_backtracks <= 8 or not 1 <= args.repair_steps <= 200:
        parser.error("Curve backtracks capped at 8; field repair capped at 200 steps")
    if not 0 < args.tsvd_cutoff < 1:
        parser.error("TSVD cutoff must be between zero and one")
    try:
        args.alphas = tuple(float(v) for v in args.alphas.split(","))
        args.production_factors = tuple(int(v) for v in args.production_factors.split(","))
        args.audit_grids = tuple(int(v) for v in args.audit_grids.split(","))
        args.audit_samples = tuple(int(v) for v in args.audit_samples.split(","))
    except ValueError:
        parser.error("Malformed numeric list")
    if len(args.alphas) < 3 or len(args.alphas) > 6 or any(not np.isfinite(v) or v <= 0 for v in args.alphas) or any(a <= b for a, b in zip(args.alphas, args.alphas[1:])):
        parser.error("IFT requires 3..6 strictly descending positive alpha values")
    if any(v not in (1, 2, 3) for v in args.production_factors) or any(v < 17 or v > 1025 for v in args.audit_grids) or any(v < 64 or v > 2048 for v in args.audit_samples):
        parser.error("Conversion audit caps: production factors 1..3, audit grids17..1025, samples64..2048")
    return args


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def conversion_audit(case, config, budget, args):
    records = []
    budget.partial_stage = {"configurations": records}
    for factor in args.production_factors:
        for audit_grid in args.audit_grids:
            for audit_samples in args.audit_samples:
                settings = replace(config,
                    grid_shape=tuple(factor * (n - 1) + 1 for n in config.grid_shape),
                    projected_samples=factor * config.projected_samples,
                    bandwidth=factor * config.bandwidth, num_nodes=factor * config.num_nodes,
                    arclength_dense_resolution=factor * config.arclength_dense_resolution,
                    validation_resolution=factor * config.validation_resolution,
                    conversion_audit_grid_shape=(audit_grid, audit_grid), conversion_audit_samples=audit_samples)
                row = {"production_factor": factor, "audit_grid": audit_grid, "audit_samples": audit_samples,
                       "geometry_config": asdict(settings)}
                try:
                    measurement, _, _ = report_geometry(case["model"], settings, budget, maximum_mode=args.motion_modes)
                    row["measurement"] = measurement
                except DiagnosticBudgetExceeded:
                    raise
                except ValueError as error:
                    row["error"] = f"{type(error).__name__}: {error}"
                records.append(row)
    return {"configurations": records, "limits_fixed_m": {"conversion_distance": 2e-4, "refinement_change": 1e-5},
            "resolution_independence": "audit grid and sample count explicitly supplied in every production arm"}


def write_handoff(output, report):
    rows = []
    for state, values in report["states"].items():
        for stage, record in values.get("stages", {}).items():
            rows.append(f"| {state} | {stage} | {record.get('status', 'completed')} |")
    content = ["# Frozen iteration-2 handoff", "", f"Stop: `{report['stop_reason']}`.", "",
        "| Actual saved state | Diagnostic | Status |", "|---|---|---|", *rows, "",
        "Detailed arrays, spectra, normalized derivatives, provenance and fixed-limit geometry decisions are in `report.json`.", "",
        "No long inverse or conditional promotion is authorized by this report. Review measured direction, field, geometry and acquisition evidence before choosing one factor.", "",
        "Stages 5, 7, 8 and 9 remain conditional. No historical Adam moments are fabricated. Field repair is diagnostic-only and restores input weights.", "",
        "An unverified IFT convergence window, unresolved FD metric, missing normal correspondence, truncated work cap or failed geometry gate is unresolved evidence."]
    (output / "handoff.md").write_text("\n".join(content) + "\n")


def main(argv=None):
    args = parse_args(argv)
    torch.set_num_threads(args.threads)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit("Output directory is nonempty; use a fresh path to preserve diagnostics.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    budget = WorkBudget(args.max_evaluations, args.max_wall_seconds)
    case = load_saved_case(args.run_dir)
    states = sorted(case["states"]) if args.states == "all" else [int(v) for v in args.states.split(",")]
    if not states or len(states) > args.max_states or len(set(states)) != len(states) or any(state not in case["states"] for state in states):
        raise SystemExit("Selected state IDs must exist, be unique, and fit --max-states.")
    report = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "command": sys.argv if argv is None else list(argv), "settings": vars(args),
              "source_bundle": str(args.run_dir.resolve()), "input_sha256": case["provenance"],
              "implementation_sha256": {name: sha256(ROOT / name) for name in (
                  "run_implicit_mlp_frozen_diagnostics.py", "solvers/sdf_inverse/frozen_diagnostics.py",
                  "solvers/sdf_inverse/geometry.py", "solvers/sdf_inverse/implicit_adjoint.py")},
              "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip(),
              "physics_note": "saved materials/observations; historical absent vacuum constants use recorded September-8 SI constants eps0=8.8541878128e-12, mu0=1.25663706212e-6",
              "qualifying_mode_coverage": args.curve_modes >= 12 and args.motion_modes >= 20,
              "states": {}, "stop_reason": "running"}
    def flush():
        report["work"] = budget.report()
        path = args.output_dir / "report.json"
        temporary = args.output_dir / "report.tmp.json"
        temporary.write_text(json.dumps(jsonable(report), indent=2, allow_nan=False) + "\n")
        temporary.replace(path)
        write_handoff(args.output_dir, report)
    flush()
    original = case["controller"].parameter_vector().copy()
    data = None
    if any(stage in args.stages for stage in ("characterize", "curve_metric", "neural_motion")):
        data = saved_training_data(case)
    with np.load(case["folder"] / "kress_responses.npz", allow_pickle=False) as archive:
        target_points = archive["exact_boundary_points"].copy()
    config = replace(case["geometry"], conversion_tolerance_m=2e-4)
    active_record = None
    try:
        for state in states:
            budget.check("saved_state_restore")
            case["controller"].assign(case["states"][state])
            entry = {"actual_weights_sha256": array_hash(case["states"][state]),
                     "historical_logged_state": case["historical"].get(state),
                     "historical_transition": historical_transition(case, state), "stages": {}}
            report["states"][state] = entry
            for stage in args.stages:
                budget.partial_stage = None
                active_record = {"status": "running"}
                entry["stages"][stage] = active_record
                print(f"state={state} stage={stage} evaluations={budget.evaluations}", flush=True)
                flush()
                if stage == "characterize":
                    result, build, _ = report_geometry(case["model"], config, budget, maximum_mode=args.motion_modes)
                    from sdf_inverse.forward import predict_paired_curve_response
                    from sdf_inverse.optimization import normalized_complex_residual
                    budget.check("characterization_data_objective", evaluation=True)
                    forward = predict_paired_curve_response(build.curve, data.forward_problem, config, solver="kress")
                    residual = normalized_complex_residual(forward.scattered_response, data.observed_scattered_response, data.frequency_weights)[0]
                    result["training_data_objective"] = .5 * float(residual @ residual)
                elif stage == "curve_metric":
                    result = curve_metric_diagnostic(case["model"], data, config, budget,
                        maximum_mode=args.curve_modes, fd_step_m=args.fd_step_m, damping=args.gn_damping,
                        tsvd_cutoff=args.tsvd_cutoff, backtracks=args.curve_backtracks, target_points=target_points)
                elif stage == "neural_motion":
                    result = neural_motion_diagnostic(case, state, data, config, budget,
                        maximum_mode=args.motion_modes, common_rms_m=args.common_rms_motion_m,
                        alphas=args.alphas, target_points=target_points)
                elif stage == "field_repair":
                    result = field_only_repair(case["model"], case["controller"], config, budget,
                        steps=args.repair_steps, learning_rate=args.repair_learning_rate,
                        anchor_beta=args.repair_anchor_beta, samples=args.repair_samples, maximum_mode=args.motion_modes)
                    weights = result.pop("repaired_weights")
                    checkpoint = args.output_dir / f"state_{state:04d}_field_repair.npz"
                    np.savez_compressed(checkpoint, parameter_vector=weights, source_state=state)
                    result["diagnostic_repaired_weights_file"] = checkpoint.name
                else:
                    result = conversion_audit(case, config, budget, args)
                active_record.update(status="completed", measurement=result)
                flush()
        report["stop_reason"] = "completed_declared_diagnostics"
    except DiagnosticBudgetExceeded as error:
        report["stop_reason"] = str(error)
        if active_record is not None:
            active_record.update(status="work_cap_reached", partial_measurement=budget.partial_stage)
    except Exception as error:
        report["stop_reason"] = "diagnostic_failure"
        report["error"] = f"{type(error).__name__}: {error}"
        (args.output_dir / "traceback.txt").write_text(traceback.format_exc())
        if active_record is not None:
            active_record.update(status="failed", partial_measurement=budget.partial_stage)
    finally:
        case["controller"].assign(original)
        report["input_weights_restored_exactly"] = np.array_equal(original, case["controller"].parameter_vector())
        flush()
    print(f"{report['stop_reason']}: {args.output_dir / 'report.json'}", flush=True)
    return 0 if report["stop_reason"] == "completed_declared_diagnostics" else 2


if __name__ == "__main__":
    raise SystemExit(main())
