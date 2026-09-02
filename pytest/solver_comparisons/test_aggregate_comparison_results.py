"""Aggregate the five shape-comparison cases and export their results.

This test computes the same comparison data used by the individual comparison
files and writes current output under ``results/solver_comparisons/current/``:

- ``geometry.png``: analytic target geometry plus the compressed IBIM samples.
- ``geometry_samples.npz``: boundary points, normals, and quadrature weights.
- ``kress_geometry_samples.npz``: Method-B periodic nodes and derivatives for
  the smooth one-component cases.
- ``metrics.json``: scalar solver metrics.
- ``scattered_fields.npz``: complex scattered-field arrays per solver/frequency.
- ``table.txt``: the same table format printed by the case's individual test.

Run with::

    python -m pytest pytest/solver_comparisons/test_aggregate_comparison_results.py -s -q

Add ``--include-qbx-archive`` only to reproduce the closed, slow QBX rows.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

MPLCONFIGDIR = Path("/tmp") / "neural_sdf_bem_ad_matplotlib"
MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[1]
RESULTS_ROOT = REPOSITORY_ROOT / "results" / "solver_comparisons" / "current"
AGGREGATE_METRICS_FILE = RESULTS_ROOT / "aggregate_metrics.md"
ARCHIVED_QBX_ROWS = frozenset({"gpr_bem_qbx", "qbx_fourier8", "qbx_sdfraw8"})


def _load_case_module(case: str) -> ModuleType:
    path = HERE / f"test_{case}_comparison.py"
    module_name = f"_aggregate_{case}_comparison"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _attach_bem_workload_metadata(
    results: dict[str, dict],
    *,
    num_scan_pairs: int,
    error_pair_count: int,
    error_scope: str,
) -> None:
    """Keep accuracy coverage distinct from the work performed by a solver."""

    for solver_name, metrics in results.items():
        # ``pair_count`` is retained for readers of older snapshots.  New code
        # must use the explicit accuracy/workload fields below.
        metrics["pair_count"] = error_pair_count
        metrics["error_pair_count"] = error_pair_count
        metrics["num_sources"] = num_scan_pairs
        metrics["num_receivers"] = num_scan_pairs
        metrics["reported_field_shape"] = (num_scan_pairs,)
        if solver_name == "gpr_bem_kdiff":
            # kdiff solves all RHS columns together, but its receiver kernel is
            # contracted row-by-row with the matching source state.  It never
            # forms the cross-source receiver fields produced by MOD/Kress.
            metrics["receiver_matrix_shape"] = (num_scan_pairs,)
            metrics["internal_receiver_matrix_shape"] = (num_scan_pairs,)
            metrics["receiver_selection"] = "direct_paired"
            metrics["receiver_evaluation_scope"] = (
                f"{num_scan_pairs} direct paired receiver fields; no cross terms "
                "materialized"
            )
        else:
            metrics["receiver_matrix_shape"] = (
                num_scan_pairs,
                num_scan_pairs,
            )
            metrics["internal_receiver_matrix_shape"] = (
                num_scan_pairs,
                num_scan_pairs,
            )
            metrics["receiver_selection"] = "paired_diagonal"
            metrics["receiver_evaluation_scope"] = (
                f"full {num_scan_pairs}x{num_scan_pairs} source-receiver matrix, "
                f"{error_pair_count} paired field(s) retained for error"
            )
        metrics["error_scope"] = error_scope


def _circle_results(module: ModuleType, include_qbx_archive: bool) -> dict[str, dict]:
    results = {name: module._run_solver(name, solver, perfect_sampling=False) for name, solver in module.SOLVERS}
    results["gpr_bem_kress"] = module._kress_metrics()
    results["gpr_bem_kdiff"] = module._kdiff_metrics(False)
    if include_qbx_archive:
        results.update(module._qbx_rows(False))
    results["kernel_diff*"] = module._kernel_diff_metrics(results["gpr_bem_mod"]["num_samples"])
    _attach_bem_workload_metadata(
        results,
        num_scan_pairs=module.NUM_RING_PAIRS,
        error_pair_count=module.NUM_RING_PAIRS,
        error_scope=f"full-ring relative L2 ({module.NUM_RING_PAIRS} paired fields)",
    )
    gprmax = module._gprmax_metrics()
    if gprmax is not None:
        results["gprmax"] = gprmax
    module.attach_parallel_solver_discrepancies(results, module.FREQUENCIES_HZ)
    module.assert_kress_comparison_acceptance(
        results["gpr_bem_kress"],
        results["gpr_bem_mod"],
        module.FREQUENCIES_HZ,
        module.KRESS_MAX_RELATIVE_ERROR,
    )
    return results


def _ellipse_results(module: ModuleType, include_qbx_archive: bool) -> dict[str, dict]:
    nystrom = module._nystrom_baseline()
    results = {name: module._run_solver(name, solver, nystrom) for name, solver in module.SOLVERS}
    results["gpr_bem_kress"] = module._kress_metrics(nystrom)
    results["gpr_bem_kdiff"] = module._kdiff_metrics(nystrom)
    if include_qbx_archive:
        results.update(module._qbx_rows(nystrom))
    _attach_bem_workload_metadata(
        results,
        num_scan_pairs=module.NUM_RING_PAIRS,
        error_pair_count=module.NUM_RING_PAIRS,
        error_scope=f"full-ring relative L2 ({module.NUM_RING_PAIRS} paired fields)",
    )
    gprmax = module._gprmax_metrics(nystrom)
    if gprmax is not None:
        results["gprmax"] = gprmax
    module.attach_parallel_solver_discrepancies(results, module.FREQUENCIES_HZ)
    module.assert_kress_comparison_acceptance(
        results["gpr_bem_kress"],
        results["gpr_bem_mod"],
        module.FREQUENCIES_HZ,
        module.KRESS_MAX_RELATIVE_ERROR,
    )
    return results


def _star_results(module: ModuleType, include_qbx_archive: bool) -> dict[str, dict]:
    nystrom = module._nystrom_baseline()
    results = {name: module._run_solver(name, solver, nystrom) for name, solver in module.SOLVERS}
    results["gpr_bem_kress"] = module._kress_metrics(nystrom)
    results["gpr_bem_kdiff"] = module._kdiff_metrics(nystrom)
    if include_qbx_archive:
        results.update(module._qbx_rows(nystrom))
    _attach_bem_workload_metadata(
        results,
        num_scan_pairs=module.NUM_RING_PAIRS,
        error_pair_count=module.NUM_RING_PAIRS,
        error_scope=f"full-ring relative L2 ({module.NUM_RING_PAIRS} paired fields)",
    )
    gprmax = module._gprmax_metrics(nystrom)
    if gprmax is not None:
        results["gprmax"] = gprmax
    module.attach_parallel_solver_discrepancies(results, module.FREQUENCIES_HZ)
    module.assert_kress_comparison_acceptance(
        results["gpr_bem_kress"],
        results["gpr_bem_mod"],
        module.FREQUENCIES_HZ,
        module.KRESS_MAX_RELATIVE_ERROR,
    )
    return results


def _synthetic_gprmax_timing_row(module: ModuleType, gprmax: dict) -> dict:
    """A gprMax row carrying only wall-clock time, for cases where gprMax is
    the *baseline* (its errors are attached to the other rows via
    ``_attach_gprmax_errors`` instead of standing alone). Every other column
    is n/a -- this row exists purely so the cross-case Wall-Clock Comparison
    table has a gprMax entry for these shapes too.
    """

    frequencies = list(module.FREQUENCIES_HZ)
    return {
        # A plain string, not None: square/two_circle's own _format_table
        # (unlike circle/ellipse/star's) formats num_samples unconditionally
        # and has never before had to handle a gprMax-only row.
        "num_samples": "--",
        "offset_distance": None,
        "formulation": "FDTD",
        "normal_derivative_scheme": f"dx={module.gprmax_cache_io.cell_size_label(gprmax)}",
        "relative_error": {f: float("nan") for f in frequencies},
        "condition_number": {f: float("nan") for f in frequencies},
        "residual": {},
        "elapsed_seconds": module.gprmax_cache_io.wall_clock_seconds(gprmax),
        "end_to_end_seconds": module.gprmax_cache_io.wall_clock_seconds(gprmax),
        "scattered": {},
        "pair_count": 0,
        "error_pair_count": 0,
        "num_sources": 1,
        "num_receivers": 1,
        "receiver_matrix_shape": (1, 1),
        "internal_receiver_matrix_shape": (1, 1),
        "reported_field_shape": (0,),
        "receiver_selection": "timing_only",
        "receiver_evaluation_scope": "one cached FDTD source-receiver pair",
        "error_scope": "timing only (one cached FDTD pair)",
    }


def _square_results(module: ModuleType, include_qbx_archive: bool) -> dict[str, dict]:
    results = {name: module._run_solver(name, solver) for name, solver in module.SOLVERS}
    results["gpr_bem_kdiff"] = module._kdiff_metrics()
    if include_qbx_archive:
        results.update(module._qbx_rows())
    _attach_bem_workload_metadata(
        results,
        num_scan_pairs=module.NUM_RING_PAIRS,
        error_pair_count=1,
        error_scope="index-0 relative discrepancy (one paired field)",
    )
    gprmax = module._gprmax_result()
    if gprmax is not None:
        module._attach_gprmax_errors(results, gprmax)
        results["gprmax"] = _synthetic_gprmax_timing_row(module, gprmax)
    return results


def _two_circle_results(module: ModuleType, include_qbx_archive: bool) -> dict[str, dict]:
    results = {name: module._run_solver(name, solver) for name, solver in module.SOLVERS}
    results["gpr_bem_kdiff"] = module._kdiff_metrics()
    if include_qbx_archive:
        results.update(module._qbx_rows())
    _attach_bem_workload_metadata(
        results,
        num_scan_pairs=module.NUM_RING_PAIRS,
        error_pair_count=1,
        error_scope="index-0 relative discrepancy (one paired field)",
    )
    gprmax = module._gprmax_result()
    if gprmax is not None:
        module._attach_gprmax_errors(results, gprmax)
    module._attach_mod_deltas(results)
    # Added after _attach_mod_deltas: that consistency diagnostic expects
    # every row to carry a full "scattered" field per frequency, which this
    # timing-only row deliberately doesn't have.
    if gprmax is not None:
        results["gprmax"] = _synthetic_gprmax_timing_row(module, gprmax)
    return results


CASE_BUILDERS = {
    "circle": _circle_results,
    "ellipse": _ellipse_results,
    "square": _square_results,
    "star": _star_results,
    "two_circle": _two_circle_results,
}


def _gprmax_cache_note(case: str, module: ModuleType) -> str | None:
    if case not in {"circle", "ellipse", "square", "star", "two_circle"}:
        return None

    params = _gprmax_params(case, module)
    cached = module.gprmax_cache_io.load_frequency_sweep(params)
    if cached is None:
        return "gprMax cache state: missing for this run."

    mode = cached["result"].get("cache_mode", "legacy_fixed_sweep")
    cell_size = module.gprmax_cache_io.cell_size_label(cached)
    entries = list(module.gprmax_cache_io.iter_frequency_results(cached))
    frequencies = ", ".join(f"{entry['frequency_hz'] / 1.0e9:g}GHz" for entry in entries)
    center_frequencies = [
        float(entry["center_frequency"]) / 1.0e9 for entry in entries if "center_frequency" in entry
    ]
    if center_frequencies:
        # "harmonic" mode drives a continuous single-tone (contsine) source at
        # exactly the target frequency, so "center frequency" here just is
        # the target frequency -- unlike "scaled" mode's broadband Ricker
        # pulse, which is centered on but not limited to it.
        fc_label = "cw fc" if mode == "per_frequency_harmonic" else "Ricker fc"
        center_frequency_text = f", {fc_label}=[" + ", ".join(f"{value:g}GHz" for value in center_frequencies) + "]"
    else:
        center_frequency_text = ""
    wall_clock = module.gprmax_cache_io.wall_clock_seconds(cached)
    return (
        f"gprMax cache state: {mode}, dx={cell_size}, frequencies=[{frequencies}]{center_frequency_text}, "
        f"wall_clock={wall_clock:.1f}s."
    )


def _gprmax_params(case: str, module: ModuleType) -> dict[str, Any]:
    kwargs = {
        "target_shape": str(getattr(module.cfg, "TARGET_SHAPE", case)),
        "standoff": module.RING_STANDOFF,
        "tx_rx_offset": float(module.cfg.TX_RX_OFFSET),
        "sand_epsr": float(module.cfg.SAND_EPSR),
        "sand_sigma": float(module.cfg.SAND_SIGMA),
        "plastic_epsr": float(module.cfg.PLASTIC_EPSR),
        "plastic_sigma": float(module.cfg.PLASTIC_SIGMA),
        "eps0": float(module.cfg.EPS0),
        "mu0": float(module.cfg.MU0),
        "frequencies_hz": list(module.FREQUENCIES_HZ),
    }
    if case == "circle":
        kwargs["target_size"] = module.RADIUS
    elif case == "square":
        kwargs["target_size"] = module.HALF_SIDE
    elif case in {"ellipse", "star", "two_circle"}:
        kwargs["target_size"] = module.TARGET_SIZE
        kwargs["target_parameters"] = module._gprmax_target_parameters()
    else:
        raise ValueError(f"Unknown gprMax case {case!r}")
    return module.gprmax_cache_io.build_params(**kwargs)


def _target_metadata(case: str, module: ModuleType) -> dict[str, Any]:
    if case == "circle":
        return {
            "kind": "circle",
            "center_m": module.CENTER,
            "radius_m": module.RADIUS,
        }
    if case == "ellipse":
        return {
            "kind": "ellipse",
            "center_m": module.CENTER,
            "semi_major_m": module.SEMI_MAJOR,
            "semi_minor_m": module.SEMI_MINOR,
        }
    if case == "square":
        return {
            "kind": "square",
            "center_m": module.CENTER,
            "half_side_m": module.HALF_SIDE,
        }
    if case == "star":
        return {
            "kind": "radial_fourier_star",
            "center_m": module.CENTER,
            "mean_radius_m": module.MEAN_RADIUS,
            "relative_amplitude": module.AMPLITUDE,
            "lobes": module.LOBES,
        }
    if case == "two_circle":
        return {
            "kind": "two_circles",
            "centers_m": module.CENTERS,
            "radii_m": module.RADII,
        }
    raise ValueError(f"Unknown case {case!r}")


def _scene_metadata(case: str, module: ModuleType) -> dict[str, Any]:
    """Standalone provenance needed to reproduce a comparison scene."""

    sources, receivers = module._ring_scan()
    smooth_kress_case = case in {"circle", "ellipse", "star"}
    sdf_callable = f"_{case}_level_set" if smooth_kress_case else None
    if case == "circle":
        oracle = {"kind": "analytic_penetrable_cylinder_mie", "num_nodes": None}
    elif case in {"ellipse", "star"}:
        oracle = {
            "kind": "independent_periodic_nystrom",
            "num_nodes": int(module.NYSTROM_N),
        }
    else:
        oracle = {
            "kind": "cached_gprmax_pair0_plus_bem_self_convergence",
            "num_nodes": None,
        }
    return {
        "target": _target_metadata(case, module),
        "extraction": {
            "bounds_m": module.BOUNDS,
            "grid_shape": module.GRID,
            "refined_grid_shape": getattr(module, "REFINED_GRID", None),
            "dtype": "float64",
            "mod_strict_quadrature": True,
            "mod_backend": "numpy",
        },
        "expected_component_count": 2 if case == "two_circle" else 1,
        "implicit_geometry": {
            "module_file": f"pytest/solver_comparisons/test_{case}_comparison.py",
            "callable": sdf_callable,
            "sign_convention": "negative_inside",
            "shared_callable_for_mod_and_kress": smooth_kress_case,
            "kress_component_id": f"comparison-{case}" if smooth_kress_case else None,
            "kress_supported": smooth_kress_case,
        },
        "materials": {
            "exterior": {
                "relative_permittivity": float(module.cfg.SAND_EPSR),
                "conductivity_s_per_m": float(module.cfg.SAND_SIGMA),
                "relative_permeability": 1.0,
            },
            "interior": {
                "relative_permittivity": float(module.cfg.PLASTIC_EPSR),
                "conductivity_s_per_m": float(module.cfg.PLASTIC_SIGMA),
                "relative_permeability": 1.0,
            },
            "eps0_f_per_m": float(module.cfg.EPS0),
            "mu0_h_per_m": float(module.cfg.MU0),
        },
        "source_strength": 1.0,
        "oracle": oracle,
        "kress_geometry_config": (
            {
                "method": "B",
                "projected_samples": 256,
                "fourier_bandwidth": 48,
                "periodic_nodes": 128,
            }
            if smooth_kress_case
            else None
        ),
        "scan": {
            "num_pairs": int(module.NUM_RING_PAIRS),
            "ring_standoff_m": float(module.RING_STANDOFF),
            "tx_rx_offset_m": float(module.cfg.TX_RX_OFFSET),
            "source_points_m": np.asarray(sources, dtype=float),
            "receiver_points_m": np.asarray(receivers, dtype=float),
        },
    }


def _baseline_note(case: str, module: ModuleType, results: dict[str, dict]) -> str:
    if case == "circle":
        return (
            "Baseline: analytic Mie-series solution for one penetrable circular cylinder. "
            "MOD and Kress start from the exact same Torch SDF callable; their table errors are "
            "full-ring relative L2 over 24 paired receiver fields. The gprMax row, when present, "
            "is one cached representative FDTD pair against the same baseline. Its analytic target "
            "has the same zero set, but the historical cache did not consume the Torch callable. "
            "gprMax lookup prefers harmonic single-frequency caches, then scaled Ricker caches, then the "
            "legacy fixed-sweep cache."
        )
    if case == "ellipse":
        return (
            f"Baseline: standalone Nystrom reference, N={module.NYSTROM_N}, on the smooth ellipse. "
            "MOD and Kress start from the exact same Torch implicit field and use the full 24-pair "
            "ring against Nystrom; the gprMax row, when present, uses only the cached index-0 FDTD "
            "pair. Its voxel test describes the same analytic zero set but did not consume that Torch "
            "callable. gprMax lookup prefers harmonic "
            "single-frequency caches, then scaled Ricker caches, then the legacy fixed-sweep cache."
        )
    if case == "star":
        return (
            f"Baseline: standalone Nystrom reference, N={module.NYSTROM_N}, on the smooth star. "
            "MOD and Kress start from the exact same Torch implicit field and use the full 24-pair "
            "ring against Nystrom; the gprMax row, when present, uses only the cached index-0 FDTD "
            "pair. Its voxel test describes the same analytic zero set but did not consume that Torch "
            "callable. gprMax lookup prefers harmonic "
            "single-frequency caches, then scaled Ricker caches, then the legacy fixed-sweep cache."
        )
    if case == "square":
        gprmax_available = _has_finite_metric(results, "relative_error")
        availability = "available in this run" if gprmax_available else "missing in this run"
        return (
            "Baseline: cached gprMax FDTD result for the index-0 ring pair only; "
            f"that cache was {availability}. Table err columns are relative errors against gprMax "
            "when the cache exists, otherwise n/a. gprMax lookup prefers harmonic single-frequency "
            "caches, then scaled Ricker caches, then the legacy fixed-sweep cache. "
            "The separate square pytest also gates gpr_bem_mod by self-convergence."
        )
    if case == "two_circle":
        gprmax_available = _has_finite_metric(results, "relative_error")
        availability = "available in this run" if gprmax_available else "missing in this run"
        return (
            "Baseline: cached gprMax FDTD result for the index-0 ring pair only; "
            f"that cache was {availability}. Table err columns are relative errors against gprMax "
            "when the cache exists, otherwise n/a. The separate two-circle pytest also gates "
            "gpr_bem_mod by self-convergence because nystrom_ref is single-component only; "
            "metrics.json additionally keeps full-ring deltas to gpr_bem_mod as a consistency diagnostic."
        )
    raise ValueError(f"Unknown case {case!r}")


def _has_finite_metric(results: dict[str, dict], metric_name: str) -> bool:
    for metrics in results.values():
        for value in metrics.get(metric_name, {}).values():
            if np.isfinite(value):
                return True
    return False


def _boundary_for_case(case: str, module: ModuleType):
    if case == "circle":
        return module._compressed_circle_boundary(module.gpr_bem_mod)
    if case == "ellipse":
        return module._compressed_ellipse_boundary(module.gpr_bem_mod)
    if case == "square":
        return module._compressed_square_boundary(module.gpr_bem_mod)
    if case == "star":
        return module._compressed_star_boundary(module.gpr_bem_mod)
    if case == "two_circle":
        return module._compressed_two_circle_boundary(module.gpr_bem_mod)
    raise ValueError(f"Unknown case {case!r}")


def _save_geometry_samples(path: Path, boundary) -> None:
    np.savez_compressed(
        path,
        points=_tensor_to_numpy(boundary.points),
        normals=_tensor_to_numpy(boundary.normals),
        quadrature_weights=_tensor_to_numpy(boundary.quadrature_weights).reshape(-1),
        strict_quadrature_weights=_tensor_to_numpy(boundary.strict_quadrature_weights).reshape(-1),
        merge_distance=np.asarray(float(boundary.merge_distance)),
        bounds=np.asarray(boundary.bounds, dtype=float),
    )


def _save_kress_geometry_samples(path: Path, curve) -> None:
    np.savez_compressed(
        path,
        parameters=np.asarray(curve.parameters),
        points=np.asarray(curve.points),
        first_derivatives=np.asarray(curve.first_derivatives),
        second_derivatives=np.asarray(curve.second_derivatives),
        normals=np.asarray(curve.normals),
        curvatures=np.asarray(curve.curvatures),
        arc_length_weights=np.asarray(curve.arc_length_weights),
        period=np.asarray(float(curve.period)),
    )


def _tensor_to_numpy(value) -> np.ndarray:
    if hasattr(value, "detach"):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def _save_scattered(path: Path, results: dict[str, dict]) -> None:
    arrays: dict[str, np.ndarray] = {}
    for solver_name, metrics in results.items():
        for frequency_hz, scattered in metrics.get("scattered", {}).items():
            arrays[f"{_slug(solver_name)}__{_frequency_slug(frequency_hz)}"] = np.asarray(scattered)
    np.savez_compressed(path, **arrays)


def _save_metrics(
    path: Path,
    case: str,
    module: ModuleType,
    results: dict[str, dict],
    baseline_note: str,
    gprmax_cache_note: str | None,
) -> None:
    payload = {
        "case": case,
        "scene": _jsonable(_scene_metadata(case, module)),
        "baseline": baseline_note,
        "gprmax_cache": gprmax_cache_note,
        "frequencies_hz": [float(f) for f in module.FREQUENCIES_HZ],
        "validation_frequencies_hz": [float(f) for f in getattr(module, "VALIDATION_FREQUENCIES_HZ", ())],
        "solvers": {},
    }
    for solver_name, metrics in results.items():
        solver_payload = {}
        for key, value in metrics.items():
            if key == "scattered":
                continue
            solver_payload[key] = _jsonable(value)
        payload["solvers"][solver_name] = solver_payload
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _format_markdown_metrics_table(module: ModuleType, results: dict[str, dict]) -> str:
    frequencies = list(module.FREQUENCIES_HZ)
    minima = _minimum_errors_by_frequency(results, frequencies)
    headers = (
        ["solver", "N", "offset", "method", "disc", "error coverage"]
        + [f"err {frequency / 1.0e9:.1f}GHz" for frequency in frequencies]
        + ["max resid", "forward time [s]", "SDF prep [s]", "end-to-end [s]"]
    )
    aligns = ["---", "---:", "---:", "---", "---", "---"] + ["---:"] * len(frequencies) + ["---:", "---:", "---:", "---:"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(aligns) + " |",
    ]
    for solver_name, metrics in results.items():
        preprocessing_cell, forward_cell, total_cell = _timing_cells(
            solver_name, metrics
        )
        row = [
            _markdown_escape(solver_name),
            _format_num_samples(metrics),
            _format_offset(metrics),
            _markdown_escape(module._display_method(solver_name, metrics)),
            _markdown_escape(module._display_discretization(metrics)),
            _format_error_coverage(metrics),
        ]
        for frequency in frequencies:
            row.append(_format_error_cell(metrics.get("relative_error", {}).get(frequency, float("nan")), minima[frequency]))
        row.extend(
            [
                _format_residual(metrics),
                forward_cell,
                preprocessing_cell,
                total_cell,
            ]
        )
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _minimum_errors_by_frequency(results: dict[str, dict], frequencies: list[float]) -> dict[float, float]:
    minima = {}
    for frequency in frequencies:
        values = [
            float(metrics.get("relative_error", {}).get(frequency, float("nan")))
            for name, metrics in results.items()
            if name not in ARCHIVED_QBX_ROWS
            and str(metrics.get("error_scope", "")).startswith("full-ring")
        ]
        finite = [value for value in values if np.isfinite(value)]
        minima[frequency] = min(finite) if finite else float("nan")
    return minima


def _format_error_cell(value: Any, minimum: float) -> str:
    value = float(value)
    if not np.isfinite(value):
        return "n/a"
    text = (
        f"{value:.2e}"
        if value != 0.0 and abs(value) < 1.0e-3
        else f"{value:.4f}"
    )
    if np.isfinite(minimum) and np.isclose(value, minimum, rtol=1.0e-12, atol=0.0):
        return f"**{text}**"
    return text


def _format_num_samples(metrics: dict[str, Any]) -> str:
    return str(metrics["num_samples"]) if metrics["num_samples"] is not None else "--"


def _format_offset(metrics: dict[str, Any]) -> str:
    return f"{float(metrics['offset_distance']):.5f}" if metrics["offset_distance"] is not None else "--"


def _format_residual(metrics: dict[str, Any]) -> str:
    residuals = [float(value) for value in metrics["residual"].values() if np.isfinite(value)]
    return f"{max(residuals):.1e}" if residuals else "n/a"


def _format_error_coverage(metrics: dict[str, Any]) -> str:
    scope = str(metrics.get("error_scope", "legacy; see case note"))
    error_pair_count = int(metrics.get("error_pair_count", metrics.get("pair_count", 0)))
    if scope.startswith("full-ring"):
        return f"L2 / {error_pair_count} pairs"
    if scope.startswith("index-0"):
        return f"pair 0 / {error_pair_count}"
    return _markdown_escape(scope)


def _receiver_workload_label(metrics: dict[str, Any]) -> str:
    num_sources = int(metrics["num_sources"])
    num_receivers = int(metrics["num_receivers"])
    matrix_shape = tuple(int(value) for value in metrics["receiver_matrix_shape"])
    selection = str(metrics["receiver_selection"])
    if selection == "direct_paired":
        if num_sources != num_receivers or matrix_shape != (num_sources,):
            raise ValueError(
                "direct-paired receiver shape must be one field per source/receiver "
                f"pair; received {matrix_shape}, {num_sources}, and {num_receivers}."
            )
        return f"{num_sources} RHS x {num_receivers} paired Rx ({num_sources} fields)"
    if matrix_shape != (num_sources, num_receivers):
        raise ValueError(
            "receiver_matrix_shape must agree with num_sources and num_receivers; "
            f"received {matrix_shape}, {num_sources}, and {num_receivers}."
        )
    return f"{num_sources} RHS x {num_receivers} Rx"


def _format_optional_seconds(value: Any) -> str:
    if value is None:
        return "--"
    seconds = float(value)
    return f"{seconds:.2f}" if np.isfinite(seconds) else "--"


def _timing_cells(solver_name: str, metrics: dict[str, Any]) -> tuple[str, str, str]:
    preprocessing = _format_optional_seconds(metrics.get("preprocessing_seconds"))
    total = _format_optional_seconds(metrics.get("end_to_end_seconds"))
    if solver_name == "gprmax":
        # Cached FDTD exposes only whole-run wall clock, not an isolated
        # boundary-preparation or forward-solve phase.
        return preprocessing, "--", total
    return preprocessing, _format_optional_seconds(metrics.get("elapsed_seconds")), total


def _markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("*", "\\*")


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {_json_key(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, complex):
        return {"real": _jsonable(float(value.real)), "imag": _jsonable(float(value.imag))}
    return value


def _json_key(key: Any) -> str:
    if isinstance(key, (int, float, np.integer, np.floating)):
        return f"{float(key):.12g}"
    return str(key)


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).replace("*", "star")


def _frequency_slug(frequency_hz: float) -> str:
    return f"{float(frequency_hz) / 1.0e9:g}GHz".replace(".", "p")


def _save_geometry_png(
    path: Path,
    case: str,
    module: ModuleType,
    boundary,
    *,
    kress_curve=None,
) -> None:
    points = _tensor_to_numpy(boundary.points)
    sources, receivers = module._ring_scan()

    fig, ax = plt.subplots(figsize=(6.0, 6.0), dpi=160)
    _plot_analytic_geometry(ax, case, module)
    ax.scatter(points[:, 0], points[:, 1], s=8, color="#1f77b4", alpha=0.75, linewidths=0.0, label="IBIM samples")
    if kress_curve is not None:
        ordered = np.asarray(kress_curve.points)
        closed = np.vstack((ordered, ordered[0]))
        ax.plot(
            closed[:, 0],
            closed[:, 1],
            color="#9467bd",
            linewidth=1.0,
            alpha=0.9,
            label="Method-B / Kress curve",
        )
    ax.scatter(sources[:, 0], sources[:, 1], s=12, marker="^", color="#2ca02c", alpha=0.65, label="Tx")
    ax.scatter(receivers[:, 0], receivers[:, 1], s=12, marker="v", color="#d62728", alpha=0.65, label="Rx")
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(case.replace("_", " "))
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.grid(True, color="#d0d0d0", linewidth=0.6, alpha=0.7)
    ax.legend(loc="upper right", fontsize=7, frameon=True)
    _set_plot_limits(ax, points, sources, receivers)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_analytic_geometry(ax, case: str, module: ModuleType) -> None:
    theta = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=True)
    if case == "circle":
        center = np.asarray(module.CENTER, dtype=float)
        radius = float(module.RADIUS)
        curve = center[None, :] + radius * np.column_stack((np.cos(theta), np.sin(theta)))
        ax.plot(curve[:, 0], curve[:, 1], color="#111111", linewidth=1.5, label="target")
    elif case == "ellipse":
        center = np.asarray(module.CENTER, dtype=float)
        curve = center[None, :] + np.column_stack(
            (module.SEMI_MAJOR * np.cos(theta), module.SEMI_MINOR * np.sin(theta))
        )
        ax.plot(curve[:, 0], curve[:, 1], color="#111111", linewidth=1.5, label="target")
    elif case == "square":
        center = np.asarray(module.CENTER, dtype=float)
        half = float(module.HALF_SIDE)
        corners = np.asarray(
            [
                [center[0] - half, center[1] - half],
                [center[0] + half, center[1] - half],
                [center[0] + half, center[1] + half],
                [center[0] - half, center[1] + half],
                [center[0] - half, center[1] - half],
            ]
        )
        ax.plot(corners[:, 0], corners[:, 1], color="#111111", linewidth=1.5, label="target")
    elif case == "star":
        center = np.asarray(module.CENTER, dtype=float)
        radius = module.MEAN_RADIUS * (1.0 + module.AMPLITUDE * np.cos(module.LOBES * theta))
        curve = center[None, :] + radius[:, None] * np.column_stack((np.cos(theta), np.sin(theta)))
        ax.plot(curve[:, 0], curve[:, 1], color="#111111", linewidth=1.5, label="target")
    elif case == "two_circle":
        for index, (center, radius) in enumerate(zip(module.CENTERS, module.RADII)):
            curve = center[None, :] + radius * np.column_stack((np.cos(theta), np.sin(theta)))
            label = "target" if index == 0 else None
            ax.plot(curve[:, 0], curve[:, 1], color="#111111", linewidth=1.5, label=label)
    else:
        raise ValueError(f"Unknown case {case!r}")


def _set_plot_limits(ax, *point_sets: np.ndarray) -> None:
    finite_sets = [np.asarray(points, dtype=float).reshape(-1, 2) for points in point_sets if np.asarray(points).size]
    all_points = np.concatenate(finite_sets, axis=0)
    mins = np.min(all_points, axis=0)
    maxes = np.max(all_points, axis=0)
    span = np.max(maxes - mins)
    midpoint = 0.5 * (mins + maxes)
    half_width = 0.55 * span
    ax.set_xlim(midpoint[0] - half_width, midpoint[0] + half_width)
    ax.set_ylim(midpoint[1] - half_width, midpoint[1] + half_width)


def _export_case(case: str, include_qbx_archive: bool) -> dict[str, Any]:
    module = _load_case_module(case)
    case_dir = RESULTS_ROOT / case
    case_dir.mkdir(parents=True, exist_ok=True)

    results = CASE_BUILDERS[case](module, include_qbx_archive)
    boundary = _boundary_for_case(case, module)
    kress_geometry = module._kress_geometry() if hasattr(module, "_kress_geometry") else None
    table = module._format_table(results)
    markdown_table = _format_markdown_metrics_table(module, results)
    baseline_note = _baseline_note(case, module, results)
    gprmax_cache_note = _gprmax_cache_note(case, module)

    _save_geometry_png(
        case_dir / "geometry.png",
        case,
        module,
        boundary,
        kress_curve=None if kress_geometry is None else kress_geometry.curve,
    )
    _save_geometry_samples(case_dir / "geometry_samples.npz", boundary)
    kress_geometry_path = case_dir / "kress_geometry_samples.npz"
    if kress_geometry is not None:
        _save_kress_geometry_samples(
            kress_geometry_path, kress_geometry.curve
        )
    else:
        # Do not let a previous experimental run imply that the smooth,
        # single-component Kress route supports this scene.
        kress_geometry_path.unlink(missing_ok=True)
    _save_metrics(case_dir / "metrics.json", case, module, results, baseline_note, gprmax_cache_note)
    _save_scattered(case_dir / "scattered_fields.npz", results)
    (case_dir / "table.txt").write_text(table + "\n")
    return {
        "case": case,
        "case_dir": case_dir,
        "baseline_note": baseline_note,
        "gprmax_cache_note": gprmax_cache_note,
        "table": table,
        "markdown_table": markdown_table,
        "elapsed_seconds": {name: float(metrics["elapsed_seconds"]) for name, metrics in results.items()},
        "preprocessing_seconds": {
            name: float(metrics["preprocessing_seconds"])
            for name, metrics in results.items()
            if metrics.get("preprocessing_seconds") is not None
        },
        "receiver_workload": {
            name: _receiver_workload_label(metrics)
            for name, metrics in results.items()
        },
    }


def _format_wallclock_summary(exports: list[dict[str, Any]]) -> str:
    """One cross-case table of measured wall-clock seconds per solver.

    Workload is deliberately part of each row label: BEM timings cover 24
    source states and 24 receivers, while the cached gprMax timing covers one
    representative source-receiver pair.
    No cross-coverage ratio is emitted because that would not be an equal-work
    normalization; circle symmetry makes even a simple 24x extrapolation
    invalid for that case.
    """

    case_order = [str(export["case"]) for export in exports]
    solver_order: list[str] = []
    for export in exports:
        for name in export["elapsed_seconds"]:
            if name not in solver_order:
                solver_order.append(name)

    headers = ["solver / receiver workload"] + [
        case.replace("_", " ").title() for case in case_order
    ]
    aligns = ["---"] + ["---:"] * len(case_order)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(aligns) + " |"]

    for solver_name in solver_order:
        workload_labels = {
            export["receiver_workload"][solver_name]
            for export in exports
            if solver_name in export["receiver_workload"]
        }
        workload = (
            next(iter(workload_labels))
            if len(workload_labels) == 1
            else "workload varies; see metrics.json"
        )
        row = [_markdown_escape(f"{solver_name} ({workload})")]
        for export in exports:
            seconds = export["elapsed_seconds"].get(solver_name)
            row.append(f"{seconds:.2f}" if seconds is not None else "--")
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _write_aggregate_metrics_file(exports: list[dict[str, Any]]) -> None:
    lines = [
        "# Aggregate Comparison Metrics",
        "",
        "This file is regenerated by "
        "`pytest/solver_comparisons/test_aggregate_comparison_results.py`.",
        "",
        "QBX rows are emitted only with `--include-qbx-archive`. They are archived "
        "diagnostics, not production candidates. Their "
        "accuracy is mixed, every stored oversampled row has invalid QBX clearance, "
        "and their measured cost is substantially above `gpr_bem_mod`/`gpr_bem_kdiff`. "
        "See `docs/qbx_closure.md` for the decision, qualifications, and reopening "
        "criteria.",
        "",
        "## Wall-Clock Comparison",
        "",
        "Raw measured seconds for one full six-frequency sweep on each shape. "
        "BEM rows solve 24 source states. MOD, ref, and Kress materialize all "
        "24x24 source/receiver combinations before selecting the paired diagonal; "
        "kdiff evaluates only the 24 paired receiver fields. Kress additionally "
        "evaluates an incident-representation consistency leak. The cached gprMax "
        "row covers one representative Tx/Rx pair and includes a target plus "
        "matched-background FDTD execution at each frequency. These unequal-work raw "
        "timings are reported without a ratio and must not be interpreted as an "
        "equal-work speedup. See "
        "`docs/gprmax_reference_study.md` for how the gprMax number is measured "
        "(a genuinely single-frequency `contsine` FDTD run per frequency, not a "
        "broadband pulse) and `docs/validation_change_log.md` for the "
        "operator-level QBX forward-solve timing this was requested to be "
        "comparable with.",
        "For the smooth cases, the per-case tables additionally separate SDF "
        "preprocessing from solver time. Kress end-to-end time is their sum; MOD "
        "and ref use their independently timed IBIM extraction. A dash means that "
        "legacy row did not measure preprocessing separately.",
        "",
        _format_wallclock_summary(exports),
        "",
        "## QBX row definitions and status",
        "",
        "`gpr_bem_qbx` is the plain same-node full-row operator (1x sources, identity "
        "prolongation). `qbx_fourier8` uses exactly eight analytic source nodes per "
        "target with Fourier-collocation prolongation; disconnected curves are treated "
        "component by component. `qbx_sdfraw8` means an 8x-refined Cartesian SDF grid, "
        "not exactly 8N sources: the retained raw narrow band can contain many source "
        "points per target.",
        "",
        "These QBX rows are archived experimental diagnostics. `metrics.json` records the actual "
        "source ratio, Fourier collocation condition, constant-prolongation error, and "
        "QBX clearance counts for every frequency. A finite solve does not override an "
        "invalid clearance count; such a row must not be presented as a convergent QBX "
        "result until its expansion geometry is made admissible. Accuracy is mixed rather "
        "than uniformly worse, but no row supplies a robust, admissible accuracy/runtime "
        "improvement; see `docs/qbx_closure.md`.",
        "",
    ]
    for export in exports:
        case = str(export["case"])
        case_dir = Path(export["case_dir"])
        notes = [str(export["baseline_note"])]
        if export["gprmax_cache_note"] is not None:
            notes.extend(["", str(export["gprmax_cache_note"])])
        lines.extend(
            [
                f"## {case.replace('_', ' ').title()}",
                "",
                *notes,
                "",
                f"Data folder: `{case_dir.relative_to(REPOSITORY_ROOT)}`",
                "",
                "Bold marks the lowest finite value only among non-archived rows "
                "explicitly declaring the same full-ring L2 coverage. One-pair gprMax "
                "values are never ranked against those rows.",
                "",
                str(export["markdown_table"]),
                "",
            ]
        )
    AGGREGATE_METRICS_FILE.write_text("\n".join(lines))


def test_aggregate_comparison_results(include_qbx_archive) -> None:
    exports = []
    for case in CASE_BUILDERS:
        export = _export_case(case, include_qbx_archive)
        exports.append(export)
        print(f"{case}: wrote {export['case_dir'].relative_to(REPOSITORY_ROOT)}")
    _write_aggregate_metrics_file(exports)
    print(
        "aggregate: wrote "
        f"{AGGREGATE_METRICS_FILE.relative_to(REPOSITORY_ROOT)}"
    )

    expected_files = {
        "geometry.png",
        "geometry_samples.npz",
        "metrics.json",
        "scattered_fields.npz",
        "table.txt",
    }
    for export in exports:
        case = str(export["case"])
        case_dir = Path(export["case_dir"])
        for filename in expected_files:
            path = case_dir / filename
            assert path.exists(), f"{case} did not write {filename}"
            assert path.stat().st_size > 0, f"{case}/{filename} is empty"
        kress_geometry_path = case_dir / "kress_geometry_samples.npz"
        if case in {"circle", "ellipse", "star"}:
            assert kress_geometry_path.exists()
            assert kress_geometry_path.stat().st_size > 0
        else:
            assert not kress_geometry_path.exists()
    assert AGGREGATE_METRICS_FILE.exists()
    assert AGGREGATE_METRICS_FILE.stat().st_size > 0
    aggregate_text = AGGREGATE_METRICS_FILE.read_text()
    assert "**" in aggregate_text
    assert "gprmax (1 RHS x 1 Rx)" in aggregate_text
    assert "gpr_bem_kdiff (24 RHS x 24 paired Rx (24 fields))" in aggregate_text
    assert "gpr_bem_kress (24 RHS x 24 Rx)" in aggregate_text
    assert "L2 / 24 pairs" in aggregate_text
    assert "pair 0 / 1" in aggregate_text
    assert "must not be interpreted as an equal-work speedup" in aggregate_text
    assert "gprMax 1-pair / fastest BEM" not in aggregate_text

    for export in exports:
        case = str(export["case"])
        payload = json.loads((RESULTS_ROOT / case / "metrics.json").read_text())
        serialized = (RESULTS_ROOT / case / "metrics.json").read_text()
        assert "NaN" not in serialized
        assert "Infinity" not in serialized
        scene = payload["scene"]
        assert scene["extraction"]["grid_shape"] == list(_load_case_module(case).GRID)
        assert len(scene["extraction"]["bounds_m"]) == 2
        assert scene["materials"]["exterior"]["relative_permittivity"] > 0.0
        assert scene["materials"]["interior"]["relative_permittivity"] > 0.0
        assert len(scene["scan"]["source_points_m"]) == scene["scan"]["num_pairs"]
        assert len(scene["scan"]["receiver_points_m"]) == scene["scan"]["num_pairs"]
        for solver_name, metrics in payload["solvers"].items():
            required = {
                "error_pair_count",
                "num_sources",
                "num_receivers",
                "receiver_matrix_shape",
                "internal_receiver_matrix_shape",
                "reported_field_shape",
                "receiver_selection",
                "receiver_evaluation_scope",
            }
            assert required <= metrics.keys(), f"{case}/{solver_name} lacks workload metadata"
            num_sources = int(metrics["num_sources"])
            num_receivers = int(metrics["num_receivers"])
            error_pair_count = int(metrics["error_pair_count"])
            if metrics["receiver_selection"] == "direct_paired":
                assert num_sources == num_receivers
                assert metrics["receiver_matrix_shape"] == [num_sources]
                assert metrics["internal_receiver_matrix_shape"] == [num_sources]
                assert metrics["reported_field_shape"] == [num_sources]
            else:
                assert metrics["receiver_matrix_shape"] == [
                    num_sources,
                    num_receivers,
                ]
                assert metrics["internal_receiver_matrix_shape"] == [
                    num_sources,
                    num_receivers,
                ]
            assert 0 <= error_pair_count <= min(num_sources, num_receivers)

    for case in ("square", "two_circle"):
        table_text = (RESULTS_ROOT / case / "table.txt").read_text().lower()
        assert "nan" not in table_text
        assert "n/a" in table_text
