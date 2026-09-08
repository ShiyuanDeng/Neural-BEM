#!/usr/bin/env python3
"""Persist an ellipse initialization, qualify its geometry, then optionally smoke it.

The default performs no inverse. Geometry resolutions are tested independently
of circle settings, keeping the 0.2 mm / 0.01 mm fidelity limits.
"""
from __future__ import annotations

import argparse
import contextlib
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
import traceback

import numpy as np
import torch

import run_sdf_inverse_comparison as driver
from sdf_inverse.geometry import OrderedSDFGeometryError, build_ordered_sdf_geometry
from sdf_inverse.implicit_adjoint import ImplicitMLPAdjointConfig, run_implicit_mlp_adjoint_inverse
from sdf_inverse.models import SirenImplicitField2D
from sdf_inverse.neural_optimization import maximum_curve_set_distance


def _production_refinement_distance(first, second):
    """Compare Fourier-resolved curves without a coarse BEM-node chord floor."""
    from scipy.signal import resample
    count = max(2048, len(first), len(second))
    return maximum_curve_set_distance(resample(first, count, axis=0),
                                      resample(second, count, axis=0))


def _initial_contour_characterization(model, config):
    """Separate a malformed initial field from its Method-B conversion error.

    The reference is the prescribed wrong-start ellipse, not inverse truth.
    This diagnostic cannot qualify geometry or change any acceptance limit.
    """
    from sdf_to_ordered_boundary import (
        FrontendConfig, ProjectionConfig, TorchImplicitField2D, prepare_single_component,
    )
    from sdf_inverse.geometry import _projection_residual_tolerance
    parameter = next(model.parameters())
    field = TorchImplicitField2D(model, dtype=parameter.dtype, device=parameter.device,
                                sign_convention="negative_inside")
    reference = prepare_single_component(field, FrontendConfig(
        bounds=config.bounds, grid_shape=(513, 513), projected_samples=1024,
        projection=ProjectionConfig(residual_tolerance=_projection_residual_tolerance(parameter.dtype)),
    ))
    raw = np.array(reference.projected_points)
    gradient_norms = np.linalg.norm(field.gradient(raw), axis=1)
    ellipse = driver._analytic_shape_for_siren("siren_ellipse")
    phase = np.arange(2048) * (2*np.pi / 2048)
    ellipse_points = (np.column_stack((np.cos(phase), np.sin(phase)))
                      * ellipse.semi_axes.detach().cpu().numpy()) @ ellipse.rotation_matrix.detach().cpu().numpy().T
    ellipse_points += ellipse.center.detach().cpu().numpy()
    distance = maximum_curve_set_distance(raw, ellipse_points)
    return {
        "evaluation_kind": "fresh frozen initial-field characterization; no BEM",
        "reference": "prescribed wrong-start ellipse; not the inverse target",
        "grid_shape": [513, 513], "projected_samples": 1024,
        "component_count": reference.num_components,
        "raw_to_intended_ellipse_set_distance_m": distance,
        "initial_shape_mismatch_exceeds_conversion_budget": distance > config.conversion_tolerance_m,
        "raw_perimeter_m": reference.single_component.projected_diagnostics.perimeter,
        "intended_ellipse_perimeter_m": float(np.linalg.norm(np.roll(ellipse_points, -1, axis=0) - ellipse_points, axis=1).sum()),
        "raw_bounds": [raw.min(axis=0).tolist(), raw.max(axis=0).tolist()],
        "on_contour_gradient_norm": {"minimum": float(gradient_norms.min()),
                                     "maximum": float(gradient_norms.max()),
                                     "rms": float(np.sqrt(np.mean(gradient_norms**2)))},
        "qualification_policy": "diagnostic only; fixed geometry fidelity gates remain mandatory",
    }


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, help="Audit these exact weights, skipping pretraining.")
    p.add_argument("--pretrain-steps", type=int, default=6000)
    p.add_argument("--max-wall-seconds", type=float, default=180.)
    p.add_argument("--smoke-updates", type=int, default=0)
    p.add_argument("--max-candidates", type=int, default=30)
    args = p.parse_args(argv)
    if not 0 <= args.smoke_updates <= 5 or not 1 <= args.max_candidates <= 120:
        p.error("Smoke limits are 0..5 accepted updates and 1..120 candidates.")
    if not np.isfinite(args.max_wall_seconds) or args.max_wall_seconds <= 0 or args.pretrain_steps < 1:
        p.error("Time cap and pretraining steps must be positive.")
    return args


def main(argv=None):
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"stage": "initialization", "status": "running", "resolutions": [],
              "command": sys.argv if argv is None else list(argv),
              "limits_m": {"conversion": .0002, "refinement_change": .00001},
              "wall_cap_policy": "checked between stages; pretraining and an in-flight build may finish beyond cap"}
    path = args.output_dir / "qualification.json"
    def save():
        path.write_text(json.dumps(driver._jsonable(report), indent=2) + "\n")
    save()
    started = perf_counter()
    status = 0
    with (args.output_dir / "stdout.log").open("w", buffering=1) as out, (args.output_dir / "stderr.log").open("w", buffering=1) as err:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                base = replace(driver._build_target("circle").geometry_config(64), bandwidth=20,
                               grid_shape=(257, 257), projected_samples=128, conversion_tolerance_m=.0002,
                               conversion_audit_grid_shape=(513, 513), conversion_audit_samples=512)
                if args.checkpoint is None:
                    model, controller = driver._build_initial_model("siren_ellipse", hidden_features=64,
                        hidden_layers=2, pretrain_steps=args.pretrain_steps, pretrain_eikonal_weight=.1)
                else:
                    bundle = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
                    kwargs = dict(bundle["constructor"])
                    kwargs["dtype"] = torch.float64
                    model = SirenImplicitField2D(**kwargs)
                    model.load_state_dict(bundle["state_dict"])
                    controller = driver.build_siren_parameter_controller(model)
                    report["source_checkpoint"] = str(args.checkpoint.resolve())
                    report["source_checkpoint_sha256"] = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
                    report["source_initialization"] = bundle.get("initialization")
                # This is deliberately before every geometry construction.
                driver._write_initial_neural_checkpoint(args.output_dir / "initial_model.pt", model, "siren_ellipse", base)
                report["initial_weights_saved_before_geometry"] = True
                report["stage"] = "initial_contour_characterization"
                save()
                if perf_counter() - started < args.max_wall_seconds:
                    report["initial_contour"] = _initial_contour_characterization(model, base)
                report["stage"] = "geometry_qualification"
                save()
                qualified = None
                for nodes, bandwidth, grid, samples in ((64, 20, 257, 128), (98, 48, 513, 256), (194, 96, 513, 512)):
                    if perf_counter() - started >= args.max_wall_seconds:
                        report["status"] = "wall_cap"
                        break
                    cfg = replace(base, num_nodes=nodes, bandwidth=bandwidth,
                                  grid_shape=(grid, grid), projected_samples=samples,
                                  arclength_dense_resolution=2048 if bandwidth == 96 else 512,
                                  validation_resolution=1024 if bandwidth == 96 else 256)
                    row = {"geometry_config": vars(cfg), "status": "running"}
                    report["resolutions"].append(row)
                    save()
                    try:
                        built = build_ordered_sdf_geometry(model, cfg)
                        if perf_counter() - started >= args.max_wall_seconds:
                            row["status"] = "wall_cap_before_independent_refinement"
                            report["status"] = "wall_cap"
                            break
                        refined_cfg = replace(cfg, grid_shape=(2*grid-1, 2*grid-1),
                                              projected_samples=2*samples,
                                              arclength_dense_resolution=2*cfg.arclength_dense_resolution)
                        refined = build_ordered_sdf_geometry(model, refined_cfg)
                        distance = _production_refinement_distance(built.curve.points, refined.curve.points)
                        row.update(status="qualified" if distance <= .00001 else "production_refinement_failed",
                                   production_refinement_change_m=distance,
                                   production_comparison_samples=max(2048, built.curve.num_nodes, refined.curve.num_nodes),
                                   conversion_error_m=built.maximum_conversion_error_m,
                                   conversion_refinement_change_m=built.conversion_refinement_change_m,
                                   refined_geometry_config=vars(refined_cfg),
                                   refined_conversion_error_m=refined.maximum_conversion_error_m,
                                   refined_conversion_refinement_change_m=refined.conversion_refinement_change_m)
                        if row["status"] == "qualified":
                            qualified = cfg
                            break
                    except OrderedSDFGeometryError as error:
                        row.update(status="geometry_rejected", error=str(error),
                                   rejection_reasons=getattr(error, "rejection_reasons", ["extraction_topology"]),
                                   conversion_error_m=getattr(error, "conversion_error_m", None),
                                   conversion_refinement_change_m=getattr(error, "conversion_refinement_change_m", None),
                                   traceback=traceback.format_exc())
                    save()
                report["qualified"] = qualified is not None
                if qualified is not None:
                    report["qualified_geometry_config"] = vars(qualified)
                    report["status"] = "qualified"
                elif report["status"] == "running":
                    report["status"] = "unqualified"
                    if report.get("initial_contour", {}).get("initial_shape_mismatch_exceeds_conversion_budget"):
                        report["mechanism"] = (
                            "The saved raw zero contour differs materially from the prescribed initial ellipse, "
                            "and the bounded Method-B conversion sweep did not satisfy the fixed limits. "
                            "More conversion resolution cannot repair the initialization's shape mismatch."
                        )
                if args.smoke_updates:
                    remaining = args.max_wall_seconds - (perf_counter() - started)
                    if qualified is None or remaining <= 0:
                        report["smoke_status"] = "not_run_unqualified_or_wall_cap"
                    else:
                        report["stage"] = "smoke_inverse"
                        save()
                        target = driver._build_target("circle")
                        sources, receivers = driver._ring_scan(center=target.center, standoff=.3, num_pairs=12)
                        problem = driver._build_problem((.25, .5), sources, receivers)
                        data = driver.ComplexScatteredData(problem, target.observations(problem))
                        def proposal(record):
                            torch.save(record, args.output_dir / f"kress_optimizer_{record['iteration']:04d}.pt")
                        def progress(record):
                            torch.save({"iteration": record, "state_dict": model.state_dict()},
                                       args.output_dir / f"accepted_{record.iteration:04d}.pt")
                        result = run_implicit_mlp_adjoint_inverse(model, controller, data, qualified,
                            config=ImplicitMLPAdjointConfig(max_iterations=args.smoke_updates,
                                max_candidate_evaluations=args.max_candidates, max_wall_seconds=remaining),
                            optimizer_callback=proposal, progress_callback=progress)
                        report["smoke_status"] = result.stop_reason
                        report["smoke_accepted_updates"] = result.final_iteration.iteration
                        report["smoke_candidate_evaluations"] = result.total_evaluation_count - 1
                report["stage"] = "complete"
            except Exception as error:
                report.update(status="failed", error=f"{type(error).__name__}: {error}")
                (args.output_dir / "failure_traceback.txt").write_text(traceback.format_exc())
                traceback.print_exc()
                status = 1
            finally:
                report["elapsed_seconds"] = perf_counter() - started
                save()
    print(path)
    return status if status else (0 if report.get("qualified") else 2)


if __name__ == "__main__":
    raise SystemExit(main())
