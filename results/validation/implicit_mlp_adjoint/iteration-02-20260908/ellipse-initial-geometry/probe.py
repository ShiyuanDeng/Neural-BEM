"""Replay archived initial ellipse weights through the repaired geometry only.

No pretraining, inverse optimization, or BEM forward solve is performed.
The output describes this new diagnostic, not the failed run's traceback.
"""

from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shlex
import sys
from time import perf_counter

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]

import run_sdf_inverse_comparison as driver
from sdf_inverse.geometry import OrderedSDFGeometryError, build_ordered_sdf_geometry
from sdf_inverse.models import SirenImplicitField2D, build_siren_parameter_controller


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = OUT / "probe.json"
    if output.exists():
        raise SystemExit(f"Refusing to replace {output}; preserve it before rerunning.")
    started = perf_counter()
    source = ROOT / "results/inverse/implicit_mlp/2026-09-07/ellipse-to-circle/metrics.json"
    suite_path = ROOT / "results/inverse/implicit_mlp/2026-09-08/wrong_start_suite.json"
    metrics = json.loads(source.read_text())
    suite = json.loads(suite_path.read_text())
    run = next(record for record in suite["runs"] if record["case"] == "ellipse-to-circle")
    # Parsing validates the recorded command but does not create outputs or train.
    args = driver._parse_args(run["inverse_command"][2:], implicit_defaults=True)
    initialization = metrics["initialization"]
    archived_vector = np.asarray(initialization["raw_parameter_vector"], dtype="<f8")
    names = initialization["raw_parameter_names"]
    constructor = {
        "bounds": metrics["experiment"]["geometry_config"]["bounds"],
        "hidden_features": initialization["hidden_features"],
        "hidden_layers": initialization["hidden_layers"],
        "omega_0": initialization["omega_0"],
        "random_seed": initialization["random_seed"],
    }
    model = SirenImplicitField2D(**constructor, dtype=torch.float64, device="cpu")
    controller = build_siren_parameter_controller(model)
    assert list(controller.names) == names, "Archived parameter order changed"
    controller.assign(archived_vector)
    assert np.array_equal(controller.parameter_vector(), archived_vector)
    config = replace(
        driver._build_target(args.target).geometry_config(args.num_nodes),
        bandwidth=args.bandwidth,
        grid_shape=(args.grid_resolution, args.grid_resolution),
        projected_samples=args.projected_samples,
        conversion_tolerance_m=args.conversion_tolerance_mm * 1.0e-3,
    )
    geometry_started = perf_counter()
    try:
        geometry = build_ordered_sdf_geometry(model, config)
        measured = {
            "status": "accepted_geometry",
            "conversion_error_m": geometry.maximum_conversion_error_m,
            "conversion_refinement_change_m": geometry.conversion_refinement_change_m,
            "rejection_reasons": [],
        }
    except OrderedSDFGeometryError as error:
        measured = {
            "status": "rejected_geometry",
            "exception_type": type(error).__name__,
            "exception_message": str(error),
            "conversion_error_m": getattr(error, "conversion_error_m", None),
            "conversion_refinement_change_m": getattr(error, "conversion_refinement_change_m", None),
            "rejection_reasons": list(getattr(error, "rejection_reasons", [])),
        }
    geometry_seconds = perf_counter() - geometry_started
    source_paths = {Path(__file__).resolve(), ROOT / "run_sdf_inverse_comparison.py"}
    for name, module in tuple(sys.modules.items()):
        if name.split(".")[0] in {"sdf_inverse", "sdf_to_ordered_boundary", "ordered_boundary"}:
            location = getattr(module, "__file__", None)
            if location and Path(location).suffix == ".py":
                source_paths.add(Path(location).resolve())
    thread_names = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    environment = {name: os.environ.get(name) for name in (*thread_names, "PYTHONPATH")}
    command = " ".join(f"{name}={shlex.quote(value)}" for name, value in environment.items() if value is not None)
    command += " " + shlex.join([sys.executable, str(Path(__file__).resolve())])
    report = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Frozen September 7 initial ellipse weights with geometry settings parsed from the failed September 8 suite command; geometry only.",
        "caveat": "The September 8 ellipse run saved neither its freshly pretrained weights nor its traceback. This diagnostic is a new probe of archived September 7 initial weights; it supports a conversion-failure hypothesis but does not establish the original exception or exact equality to that unsaved model.",
        "source": {
            "metrics_path": str(source.relative_to(ROOT)),
            "metrics_sha256": sha256(source),
            "vector_json_location": "initialization.raw_parameter_vector",
            "vector_sha256": hashlib.sha256(archived_vector.tobytes(order="C")).hexdigest(),
            "vector_hash_encoding": "Contiguous little-endian IEEE-754 float64 values in initialization.raw_parameter_names order",
            "parameter_names_sha256": hashlib.sha256(json.dumps(names, separators=(",", ":")).encode()).hexdigest(),
            "parameter_count": int(archived_vector.size),
            "constructor": {**constructor, "dtype": "torch.float64", "device": "cpu"},
            "original_geometry_config": metrics["experiment"]["geometry_config"],
            "original_pretraining_report": initialization["pretraining"],
            "original_run_command": metrics["provenance"]["command"],
        },
        "failed_run_record": {
            "suite_path": str(suite_path.relative_to(ROOT)),
            "suite_sha256": sha256(suite_path),
            "status": run["status"],
            "inverse_exit_code": run["inverse_exit_code"],
            "inverse_command": run["inverse_command"],
        },
        "geometry_config": asdict(config),
        "limits_m": {"conversion_distance": config.conversion_tolerance_m, "conversion_refinement_change": 0.05 * config.conversion_tolerance_m},
        "measurement": measured,
        "geometry_probe_seconds": geometry_seconds,
        "total_probe_seconds_excluding_imports_and_json_write": perf_counter() - started,
        "weights_unchanged_exactly": bool(np.array_equal(controller.parameter_vector(), archived_vector)),
        "pretraining_steps_run": 0,
        "inverse_updates_run": 0,
        "bem_forward_solves_run": 0,
        "reproduction": {
            "working_directory": str(ROOT),
            "command": command,
            "environment": environment,
            "python": platform.python_version(),
            "packages": {package: importlib.metadata.version(package) for package in ("numpy", "scipy", "scikit-image", "torch")},
            "current_source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in sorted(source_paths)},
        },
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(output), "measurement": measured, "geometry_probe_seconds": geometry_seconds}, indent=2))


if __name__ == "__main__":
    main()
