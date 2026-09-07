"""Frozen circle/star supervision ablation with identical training locations.

This is an explicit Task-B experiment. It neither changes inverse defaults nor
uses extracted neural geometry as an optimization state. Every output path
must be new. Normal-offset locations are historical controls, and their actual
distances are evaluated; no tubular-neighborhood identity is assumed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np
import torch

from gpr_bem_kress import Material
from gpr_bem_kress.forward import solve_kress_tmz_total_field_batch
from gpr_bem_ref import penetrable_cylinder_scattered_field
from ordered_boundary import BoundaryValidationConfig, circle, star
from sdf_inverse.continuous_distance import signed_distance_to_continuous_curve
from sdf_inverse.neural import (
    NeuralRedistanceConfig, SmoothMLPSDF2D, redistance_neural_sdf_to_curve,
    signed_distance_to_curve_polygon,
)
from sdf_to_ordered_boundary import (
    ArcLengthConfig, FrontendConfig, MethodBConfig, TorchImplicitField2D,
    extract_frontend_components, fit_fourier_least_squares, fit_method_b,
)


class CountedMLP(SmoothMLPSDF2D):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value_calls = 0
        self.value_points = 0

    def forward(self, points):
        self.value_calls += 1
        self.value_points += len(points)
        return super().forward(points)


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (complex, np.complexfloating)):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, np.generic):
        return value.item()
    return value


def _relative(a, b):
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(b), np.finfo(float).tiny))


def _provenance():
    command = [sys.executable, *sys.argv]
    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()
    files = [Path(__file__), Path("solvers/sdf_inverse/neural.py"),
             Path("solvers/sdf_inverse/continuous_distance.py")]
    return {
        "command": command, "commit": git("rev-parse", "HEAD"),
        "dirty_status": git("status", "--short"),
        "tracked_diff_sha256": hashlib.sha256(git("diff").encode()).hexdigest(),
        "implementation_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
        "environment": {key: os.environ.get(key) for key in
                        ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "PYTHONPATH")},
    }


def _set_error(first, second, count):
    # Closest-point refinement removes nearest-sample spacing from each directed
    # distance; the outer maximum is independently checked at twice this count.
    queries_a, queries_b = first.discretize(count).points, second.discretize(count).points
    a = signed_distance_to_continuous_curve(queries_a, second, tolerance_m=1e-9, initial_samples=512)
    b = signed_distance_to_continuous_curve(queries_b, first, tolerance_m=1e-9, initial_samples=512)
    return float(max(np.abs(a).max(), np.abs(b).max()))


def _forward_refinement(curve, acquisition, *, nodes):
    records, previous, final = [], None, None
    start = perf_counter()
    for count in nodes:
        values = []
        for omega in acquisition["angular_frequencies"]:
            solved = solve_kress_tmz_total_field_batch(
                curve.discretize(count), acquisition["source_points"],
                acquisition["receiver_points"], omega, acquisition["source_strength"],
                exterior=Material(**acquisition["exterior"]),
                interior=Material(**acquisition["interior"]),
                eps0=acquisition["eps0"], mu0=acquisition["mu0"],
            )
            values.append(np.diag(solved.scattered_receiver))
        final = np.column_stack(values)
        records.append({"num_nodes": count, "relative_change": None if previous is None else _relative(final, previous)})
        previous = final
    return final, {
        "records": records, "seconds": perf_counter() - start,
        "solve_count": len(nodes) * len(acquisition["angular_frequencies"]),
        "converged": records[-1]["relative_change"] < 1e-7,
        "relative_tolerance": 1e-7,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--sample-count", type=int, default=768)
    parser.add_argument("--hidden-features", type=int, default=32)
    parser.add_argument("--solver-nodes", type=int, nargs="+", default=(128, 256, 512))
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing results: {args.output_dir}")
    if args.steps < 2 or len(args.solver_nodes) < 2:
        raise ValueError("At least two steps and two solver resolutions are required.")
    args.output_dir.mkdir(parents=True)
    torch.set_num_threads(1)
    started = perf_counter()
    bounds, center, radius = ((0.35, 0.35), (0.65, 0.65)), (0.5, 0.5), 0.065
    angles = np.linspace(0.0, 2 * np.pi, 6, endpoint=False)
    acquisition = {
        "source_points": np.asarray(center) + .25 * np.column_stack((np.cos(angles), np.sin(angles))),
        "receiver_points": np.asarray(center) + .23 * np.column_stack((np.cos(angles+.31), np.sin(angles+.31))),
        "angular_frequencies": 2 * np.pi * np.asarray((.6e9, .9e9)),
        "source_strength": 1.0 + .2j, "exterior": {"epsr": 6., "sigma": 0., "mur": 1.},
        "interior": {"epsr": 3., "sigma": 0., "mur": 1.},
        "eps0": 8.8541878128e-12, "mu0": 1.25663706212e-6,
    }
    config = NeuralRedistanceConfig(
        bounds=bounds, max_steps=args.steps, minimum_steps=args.steps,
        warmup_steps=min(50, args.steps-1), sample_count=args.sample_count,
        heldout_sample_count=256, seed=31415, check_interval=args.steps,
        patience_checks=100, distance_rms_tolerance_m=1e-5,
        boundary_max_tolerance_m=1e-7, no_op_boundary_max_tolerance_m=1e-9,
        distance_target_tolerance_m=1e-6,
    )
    summary = {
        "schema_version": 1, "experiment": "task_b_frozen_target_only_ablation",
        "provenance": _provenance(), "acquisition": acquisition,
        "redistance_config": asdict(config),
        "distance_accuracy_budget_m": 1e-6, "representation_tolerance_m": 2e-4,
        "sampling": "Identical legacy polygon boundary/offset and seeded global locations in both arms; smooth arm uses actual nonzero boundary-sample targets.",
        "normal_offset_identity_assumed": False,
        "distance_reference": "continuous multiple-local-minimum refinement; initial 512/tightened 1024, tolerances 1e-9/1e-11; agreement is numerical, not certified",
        "bem_training_polygon_nodes": 32, "cases": [],
    }
    arrays = {}
    for name, canonical in (
        ("circle", circle(center, radius)),
        ("star", star(center, radius, .2, 5, rotation=.15)),
    ):
        print(f"{name}: frozen target and reference", flush=True)
        sampled = canonical.discretize(32)
        canonical_fit = fit_fourier_least_squares(
            canonical.discretize(64).parameters, canonical.discretize(64).points,
            bandwidth=6, component_id=name,
        ).boundary
        queries = np.random.default_rng(90210).uniform(*np.asarray(bounds), size=(2048, 2))
        exact, distance_diagnostics = signed_distance_to_continuous_curve(
            queries, canonical, tolerance_m=1e-9, initial_samples=512, return_diagnostics=True,
        )
        tightened = signed_distance_to_continuous_curve(
            queries, canonical, tolerance_m=1e-11, initial_samples=1024, refinement_iterations=56,
        )
        reference, forward_report = _forward_refinement(canonical, acquisition, nodes=args.solver_nodes)
        case = {
            "shape": name, "canonical_cartesian_cosine": canonical_fit.cosine_coefficients,
            "canonical_cartesian_sine": canonical_fit.sine_coefficients,
            "canonical_bandwidth": 6,
            "canonical_forward": forward_report, "reference_distance_diagnostics": distance_diagnostics,
            "tightened_distance_max_change_m": float(np.max(np.abs(exact-tightened))), "arms": [],
        }
        arrays[f"{name}_independent_points"] = queries
        arrays[f"{name}_independent_distance"] = tightened
        arrays[f"{name}_canonical_field"] = reference
        if name == "circle":
            mie = np.column_stack([
                penetrable_cylinder_scattered_field(
                    acquisition["receiver_points"], acquisition["source_points"],
                    k_exterior=Material(**acquisition["exterior"]).wavenumber(omega, acquisition["eps0"], acquisition["mu0"]),
                    k_interior=Material(**acquisition["interior"]).wavenumber(omega, acquisition["eps0"], acquisition["mu0"]),
                    radius=radius, center=center, source_strength=acquisition["source_strength"],
                ) for omega in acquisition["angular_frequencies"]
            ])
            case["canonical_mie_relative_error"] = _relative(reference, mie)
        for policy in ("legacy_polygon", "smooth_curve"):
            print(f"{name}: training {policy}", flush=True)
            model = CountedMLP(
                bounds=bounds, hidden_features=args.hidden_features, hidden_layers=2,
                geometric_center=center, geometric_radius=.060, seed=2718,
            )
            prefix = f"{name}_{policy}"
            targets = signed_distance_to_curve_polygon(queries, sampled) if policy == "legacy_polygon" else signed_distance_to_continuous_curve(
                queries, canonical, tolerance_m=config.distance_target_tolerance_m,
                initial_samples=config.distance_initial_samples,
            )
            fit_started = perf_counter()
            result = redistance_neural_sdf_to_curve(
                model, sampled,
                replace(config, distance_target=policy, smooth_boundary_sampling="legacy_polygon"),
                continuous_curve=canonical,
            )
            fit_seconds = perf_counter()-fit_started
            calls = {"training_model_forward_calls": model.value_calls,
                     "training_model_evaluated_points": model.value_points}
            model.eval()
            with torch.no_grad():
                values = model(torch.as_tensor(queries, dtype=torch.float64)).numpy().reshape(-1)
            arm = {
                "distance_target": policy, "status": "trained", "failure_reason": None,
                "model": model.initialization_metadata(), "redistance_converged": result.converged,
                "redistance_stop_reason": result.stop_reason, "training_steps": result.steps,
                "training_seconds": fit_seconds, "calls": calls,
                "training_seconds_includes_target_construction": True,
                "target_max_error_before_training_m": float(np.abs(targets-tightened).max()),
                "target_rms_error_before_training_m": float(np.sqrt(np.mean((targets-tightened)**2))),
                "independent_field_distance_rms_m": float(np.sqrt(np.mean((values-tightened)**2))),
                "independent_field_distance_max_m": float(np.max(np.abs(values-tightened))),
                "independent_sign_mismatches": int(np.count_nonzero((values < 0) != (tightened < 0))),
                "redistance_diagnostics": dict(result.diagnostics), "extractions": [],
            }
            arrays[f"{prefix}_loss"] = result.loss_history
            arrays[f"{prefix}_field_distance"] = values
            arrays[f"{prefix}_target_distance"] = targets
            for key, value in model.state_dict().items():
                arrays[f"{prefix}_model_{key}"] = value.detach().cpu().numpy()
            previous_extracted = None
            for grid, projected, bandwidth in ((129, 256, 24), (257, 512, 48), (513, 1024, 96)):
                extraction_started, before_calls = perf_counter(), model.value_calls
                record = {"grid_shape": (grid, grid), "projected_samples": projected,
                          "bandwidth": bandwidth, "audit_samples": (512, 1024),
                          "arclength_dense_resolution": 2048, "status": "failed", "failure_reason": None}
                try:
                    field = TorchImplicitField2D(model, device="cpu", dtype=torch.float64)
                    frontend = extract_frontend_components(field, FrontendConfig(
                        bounds=bounds, grid_shape=(grid, grid), projected_samples=projected,
                    ))
                    record["component_count"] = frontend.num_components
                    if frontend.num_components != 1:
                        raise ValueError(f"Expected one component; detected {frontend.num_components}.")
                    fitted = fit_method_b(frontend.components[0], config=MethodBConfig(
                        bandwidth=bandwidth,
                        arclength=ArcLengthConfig(dense_resolution=2048, validation_resolution=512),
                        validation=BoundaryValidationConfig(num_samples_per_component=512),
                    ))
                    if fitted.status != "success":
                        raise ValueError(fitted.failure_reason)
                    extracted = fitted.parameterization
                    evaluation = extracted.discretize(1024)
                    gradient = field.gradient(np.array(evaluation.points, copy=True))
                    if np.any(np.einsum("nd,nd->n", gradient, evaluation.normals) <= 0):
                        raise ValueError("Extracted field fails the negative_inside orientation check.")
                    drift = [_set_error(canonical, extracted, n) for n in (512, 1024)]
                    record.update({
                        "status": "success", "canonical_set_drift_m": drift[-1],
                        "set_audit_refinement_change_m": abs(drift[1]-drift[0]),
                        "set_audit_converged": abs(drift[1]-drift[0]) < 2e-6,
                        "minimum_speed": fitted.validation.minimum_speed,
                        "speed_ratio": fitted.validation.maximum_speed / fitted.validation.minimum_speed,
                        "extraction_fit_refinement_drift_m": None if previous_extracted is None else _set_error(previous_extracted, extracted, 1024),
                    })
                    resolved_solver_nodes = tuple(n for n in args.solver_nodes if n >= 2 * bandwidth + 2)
                    if len(resolved_solver_nodes) < 2:
                        raise ValueError("At least two configured BEM node counts must resolve the frozen extraction bandwidth.")
                    predicted, solve_report = _forward_refinement(extracted, acquisition, nodes=resolved_solver_nodes)
                    record["physical_forward"] = solve_report
                    record["physical_field_relative_error"] = _relative(predicted, reference)
                    arrays[f"{prefix}_extracted_field_grid{grid}"] = predicted
                    arrays[f"{prefix}_extracted_points_grid{grid}"] = evaluation.points
                    arrays[f"{prefix}_extracted_cosine_grid{grid}"] = fitted.representation.cosine_coefficients
                    arrays[f"{prefix}_extracted_sine_grid{grid}"] = fitted.representation.sine_coefficients
                    previous_extracted = extracted
                except (ValueError, RuntimeError, FloatingPointError) as exc:
                    record["status"] = "failed"
                    record["failure_reason"] = f"{type(exc).__name__}: {exc}"
                record["total_seconds"] = perf_counter()-extraction_started
                record["model_forward_calls"] = model.value_calls-before_calls
                arm["extractions"].append(record)
            case["arms"].append(arm)
            print(f"{name}: {policy} target max {arm['target_max_error_before_training_m']:.3g} m; field RMS {arm['independent_field_distance_rms_m']:.3g} m", flush=True)
        summary["cases"].append(case)
    summary["total_seconds"] = perf_counter()-started
    np.savez_compressed(args.output_dir / "arrays.npz", **arrays)
    (args.output_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2, allow_nan=False)+"\n")
    print(f"Wrote {args.output_dir} in {summary['total_seconds']:.1f} seconds", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
