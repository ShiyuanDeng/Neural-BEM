"""Compare ref/mod on two non-touching circular components.

This is the multi-component analogue of ``test_square_comparison.py``:
``nystrom_ref`` is currently single-curve only, so gprMax provides the external
FDTD baseline for the single representative index-0 Tx/Rx pair. Full-ring
behavior is still gated by gpr_bem_mod self-convergence under boundary
refinement. The metrics also keep solver deltas against ``gpr_bem_mod`` on the
same 24-pair ring scan as a consistency diagnostic.

Regenerate the gprMax cache with::

    /home/drdeng/miniconda3/envs/gprMax/bin/python solvers/gprmax_ref/run_case.py \
        --target-shape two_circles

Run this file so the table is visible::

    python -m pytest pytest/test_two_circle_comparison.py -s -q
"""

from __future__ import annotations

import math
import time
import warnings

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config.two_circle_config as cfg
import gpr_bem_kdiff
import gpr_bem_mod
import gpr_bem_ref
from gprmax_ref import cache_io as gprmax_cache_io

SOLVERS = (("gpr_bem_ref", gpr_bem_ref), ("gpr_bem_mod", gpr_bem_mod))

CENTERS = np.asarray(cfg.TARGET_CIRCLE_CENTERS, dtype=float)
RADII = np.asarray(cfg.TARGET_CIRCLE_RADII, dtype=float)
CENTER = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))
TARGET_SIZE = float(cfg.TARGET_SIZE)
BOUND_PADDING = 0.04
BOUNDS = (
    (
        float(np.min(CENTERS[:, 0] - RADII) - BOUND_PADDING),
        float(np.min(CENTERS[:, 1] - RADII) - BOUND_PADDING),
    ),
    (
        float(np.max(CENTERS[:, 0] + RADII) + BOUND_PADDING),
        float(np.max(CENTERS[:, 1] + RADII) + BOUND_PADDING),
    ),
)
GRID = (161, 161)
REFINED_GRID = (241, 241)
REF_OFFSET_SCALE = 2.0
RING_STANDOFF = 0.30
NUM_RING_PAIRS = 24
VALIDATION_FREQUENCIES_HZ = (0.5e9, 1.5e9, 2.5e9)
HIGH_ERROR_FREQUENCIES_HZ = (4.0e9, 6.0e9, 8.0e9)
FREQUENCIES_HZ = VALIDATION_FREQUENCIES_HZ + HIGH_ERROR_FREQUENCIES_HZ

SELF_CONVERGENCE_MAX_RELATIVE_CHANGE = 0.05
GPRMAX_MAX_RELATIVE_ERROR = 0.35


def _ring_scan() -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0.0, 2.0 * np.pi, NUM_RING_PAIRS, endpoint=False, dtype=float)
    separation = float(cfg.TX_RX_OFFSET) / RING_STANDOFF
    sources = np.column_stack(
        (
            CENTER[0] + RING_STANDOFF * np.cos(angles),
            CENTER[1] + RING_STANDOFF * np.sin(angles),
        )
    )
    receivers = np.column_stack(
        (
            CENTER[0] + RING_STANDOFF * np.cos(angles + separation),
            CENTER[1] + RING_STANDOFF * np.sin(angles + separation),
        )
    )
    return sources, receivers


def _phi_factory(solver):
    def phi(points):
        return solver.circles_union_signed_distance(points, centers=CENTERS, radii=RADII)

    return phi


def _compressed_two_circle_boundary(solver, *, grid: tuple[int, int] = GRID):
    """Build the disjoint-circle union boundary with the solver's own classes."""

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = solver.build_implicit_boundary_band(
            _phi_factory(solver),
            BOUNDS,
            grid_shape=grid,
            dtype=torch.float64,
        )
        return solver.compress_implicit_boundary_band(band)


def _run_solver(name: str, solver) -> dict:
    sources, receivers = _ring_scan()
    exterior = solver.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = solver.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    boundary = _compressed_two_circle_boundary(solver)
    requested_offset_distance = None if name == "gpr_bem_mod" else REF_OFFSET_SCALE * float(boundary.merge_distance)

    metrics = {
        "num_samples": int(boundary.num_samples),
        "merge_distance": float(boundary.merge_distance),
        "requested_offset_distance": requested_offset_distance,
        "offset_distance": None,
        "formulation": "unknown",
        "normal_derivative_scheme": "unknown",
        "relative_error": {f: float("nan") for f in FREQUENCIES_HZ},
        "relative_delta_to_mod": {f: float("nan") for f in FREQUENCIES_HZ},
        "condition_number": {},
        "residual": {},
        "scattered": {},
        "elapsed_seconds": 0.0,
    }

    for frequency_hz in FREQUENCIES_HZ:
        angular_frequency = 2.0 * np.pi * frequency_hz
        started = time.perf_counter()
        forward = solver.solve_ibim_tmz_total_field_batch(
            boundary,
            sources,
            receivers,
            angular_frequency,
            1.0,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            offset_distance=requested_offset_distance,
            use_strict_quadrature=True,
            backend="numpy",
        )
        metrics["elapsed_seconds"] += time.perf_counter() - started
        if metrics["offset_distance"] is None:
            metrics["offset_distance"] = float(forward.system.offset_distance)
            metrics["formulation"] = str(getattr(forward.system, "formulation", "difference"))
            metrics["normal_derivative_scheme"] = str(
                getattr(forward.system, "normal_derivative_scheme", "finite_difference")
            )
        metrics["scattered"][frequency_hz] = np.asarray(forward.scattered_receiver)
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(
            np.linalg.cond(np.asarray(forward.system.system_matrix)[0])
        )

    return metrics


def _kdiff_metrics() -> dict:
    """``gpr_bem_kdiff`` on the real compressed two-circle boundary.

    The exact SDF is passed in so the local diagonal treatment can use autograd
    curvature on each circular component. This is still printed only: without a
    multi-component oracle, agreement with ``gpr_bem_mod`` is a consistency
    diagnostic rather than an accuracy proof.
    """

    phi = _phi_factory(gpr_bem_kdiff)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = gpr_bem_kdiff.build_implicit_boundary_band(phi, BOUNDS, grid_shape=GRID, dtype=torch.float64)
        boundary = gpr_bem_kdiff.compress_implicit_boundary_band(band)

    sources, receivers = _ring_scan()
    exterior = gpr_bem_kdiff.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_kdiff.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    metrics = {
        "num_samples": int(boundary.num_samples),
        "merge_distance": float(boundary.merge_distance),
        "requested_offset_distance": None,
        "offset_distance": None,
        "formulation": "muller",
        "normal_derivative_scheme": "kdiff_sdfcurv",
        "relative_error": {f: float("nan") for f in FREQUENCIES_HZ},
        "relative_delta_to_mod": {f: float("nan") for f in FREQUENCIES_HZ},
        "condition_number": {},
        "residual": {},
        "scattered": {},
        "elapsed_seconds": 0.0,
    }
    for frequency_hz in FREQUENCIES_HZ:
        angular_frequency = 2.0 * np.pi * frequency_hz
        started = time.perf_counter()
        forward = gpr_bem_kdiff.solve_ibim_tmz_total_field_batch(
            boundary,
            sources,
            receivers,
            angular_frequency,
            1.0,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            sdf_fn=phi,
        )
        metrics["elapsed_seconds"] += time.perf_counter() - started
        metrics["scattered"][frequency_hz] = np.asarray(forward.scattered_receiver)
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(np.linalg.cond(forward.system.system_matrix[0]))
    return metrics


def _gprmax_target_parameters() -> dict[str, list[list[float]] | list[float]]:
    relative_centers = CENTERS - np.asarray(CENTER, dtype=float)[None, :]
    return {
        "circle_centers": [
            [
                round(float(x), gprmax_cache_io.SCENE_DECIMAL_PLACES),
                round(float(y), gprmax_cache_io.SCENE_DECIMAL_PLACES),
            ]
            for x, y in relative_centers
        ],
        "circle_radii": [round(float(radius), gprmax_cache_io.SCENE_DECIMAL_PLACES) for radius in RADII],
    }


def _gprmax_result() -> dict | None:
    """Load the cached gprMax FDTD run for this case, or ``None`` on a miss."""

    params = gprmax_cache_io.build_params(
        target_shape=str(cfg.TARGET_SHAPE),
        target_size=TARGET_SIZE,
        target_parameters=_gprmax_target_parameters(),
        standoff=RING_STANDOFF,
        tx_rx_offset=float(cfg.TX_RX_OFFSET),
        sand_epsr=float(cfg.SAND_EPSR),
        sand_sigma=float(cfg.SAND_SIGMA),
        plastic_epsr=float(cfg.PLASTIC_EPSR),
        plastic_sigma=float(cfg.PLASTIC_SIGMA),
        eps0=float(cfg.EPS0),
        mu0=float(cfg.MU0),
        frequencies_hz=list(FREQUENCIES_HZ),
    )
    return gprmax_cache_io.load_frequency_sweep(params)


def _attach_gprmax_errors(results: dict[str, dict], gprmax_result: dict) -> None:
    """Fill ``relative_error`` in place, comparing only the index-0 ring pair."""

    for metrics in results.values():
        for entry in gprmax_cache_io.iter_frequency_results(gprmax_result):
            frequency_hz = float(entry["frequency_hz"])
            exact = complex(entry["scattered_real"], entry["scattered_imag"])
            got = complex(metrics["scattered"][frequency_hz][0])
            metrics["relative_error"][frequency_hz] = abs(got - exact) / abs(exact)


def _attach_mod_deltas(results: dict[str, dict]) -> None:
    modified = results["gpr_bem_mod"]
    for metrics in results.values():
        for frequency_hz in FREQUENCIES_HZ:
            reference = modified["scattered"][frequency_hz]
            got = metrics["scattered"][frequency_hz]
            metrics["relative_delta_to_mod"][frequency_hz] = float(
                np.linalg.norm(got - reference) / np.linalg.norm(reference)
            )


def _format_table(results: dict[str, dict]) -> str:
    ghz = [f"{f / 1e9:.1f}" for f in FREQUENCIES_HZ]
    header = (
        f"{'solver':<14}{'N':>5}{'offset':>10} {'method':>7} {'disc':>7}"
        + "".join(f"{'err ' + g + 'GHz':>13}" for g in ghz)
        + f"{'max resid':>12}{'time [s]':>10}"
    )
    lines = [header, "-" * len(header)]
    for name, metrics in results.items():
        offset = f"{metrics['offset_distance']:>10.5f}" if metrics["offset_distance"] is not None else f"{'--':>10}"
        row = f"{name:<14}{metrics['num_samples']:>5}{offset}"
        row += f" {_display_method(name, metrics):>7} {_display_discretization(metrics):>7}"
        row += "".join(_format_error(metrics["relative_error"][f]) for f in FREQUENCIES_HZ)
        residuals = [float(value) for value in metrics["residual"].values() if np.isfinite(value)]
        row += f"{max(residuals):>12.1e}" if residuals else f"{'n/a':>12}"
        row += f"{metrics['elapsed_seconds']:>10.2f}"
        lines.append(row)
    return "\n".join(lines)


def _format_error(error: float) -> str:
    return f"{error:>13.4f}" if not math.isnan(error) else f"{'n/a':>13}"


def _display_method(name: str, metrics: dict) -> str:
    formulation = str(metrics["formulation"])
    if name == "gpr_bem_ref" and formulation == "difference":
        return "--"
    if formulation == "muller":
        return "muller"
    if formulation == "difference":
        return "diff"
    return formulation[:7]


def _display_discretization(metrics: dict) -> str:
    scheme = str(metrics["normal_derivative_scheme"])
    if scheme == "finite_difference":
        return "fd"
    if scheme in ("analytic_extrapolated", "analytic"):
        return "analy"
    if scheme == "kdiff_local":
        return "kdiff2"
    if scheme == "kdiff_sdfcurv":
        return "kdfsdf"
    return scheme[:7]


@pytest.fixture(scope="module")
def comparison_results() -> dict[str, dict]:
    results = {name: _run_solver(name, solver) for name, solver in SOLVERS}
    results["gpr_bem_kdiff"] = _kdiff_metrics()
    _attach_mod_deltas(results)
    return results


@pytest.fixture(scope="module")
def gprmax_result() -> dict | None:
    return _gprmax_result()


def test_two_circle_comparison_table(comparison_results, gprmax_result) -> None:
    if gprmax_result is not None:
        _attach_gprmax_errors(comparison_results, gprmax_result)

    center_distance = float(np.linalg.norm(CENTERS[1] - CENTERS[0]))
    component_gap = center_distance - float(RADII[0] + RADII[1])
    analytic_perimeter = float(2.0 * np.pi * np.sum(RADII))
    boundary = _compressed_two_circle_boundary(gpr_bem_mod)
    measured_perimeter = float(boundary.quadrature_weights.sum())

    print("\n\nTwo-circle scattering, gpr_bem_ref vs gpr_bem_mod")
    print(
        f"  centers={CENTERS.tolist()}, radii={RADII.tolist()}, gap={component_gap:.3f} m, "
        f"grid {GRID[0]}x{GRID[1]}, ref offset = {REF_OFFSET_SCALE} x merge_distance; "
        "mod offset = solver default"
    )
    print(f"  {NUM_RING_PAIRS} bistatic Tx/Rx pairs on a {RING_STANDOFF:.2f} m ring")
    if gprmax_result is not None:
        print(
            "  err columns: index-0 ring pair only, vs gprMax "
            "(4/6/8 GHz shown as diagnostics, not gated)\n"
        )
    else:
        print("  err columns: n/a, no gprMax cache for this case -- see test_two_circle_gprmax_cross_check\n")
    print(_format_table(comparison_results))
    print()

    assert component_gap > 0.0
    assert measured_perimeter == pytest.approx(analytic_perimeter, rel=5.0e-3)
    modified = comparison_results["gpr_bem_mod"]
    assert modified["formulation"] == "muller"
    assert modified["normal_derivative_scheme"] == "analytic_extrapolated"
    assert modified["offset_distance"] == pytest.approx(0.275 * modified["merge_distance"])
    for metrics in comparison_results.values():
        for frequency_hz in FREQUENCIES_HZ:
            assert np.isfinite(metrics["condition_number"][frequency_hz])
            assert np.isfinite(metrics["residual"][frequency_hz])
            assert np.isfinite(metrics["relative_delta_to_mod"][frequency_hz])
            if gprmax_result is not None:
                assert np.isfinite(metrics["relative_error"][frequency_hz])


def test_two_circle_gprmax_cross_check(comparison_results, gprmax_result) -> None:
    """Independent FDTD check for the one representative pair gprMax ran."""

    if gprmax_result is None:
        pytest.skip(
            "gprMax cache not found for the current config values -- regenerate with "
            "solvers/gprmax_ref/run_case.py --target-shape two_circles"
        )
    _attach_gprmax_errors(comparison_results, gprmax_result)

    modified = comparison_results["gpr_bem_mod"]
    print("\ntwo-circle gprMax cross-check (index-0 ring pair only)")
    for frequency_hz in FREQUENCIES_HZ:
        error = modified["relative_error"][frequency_hz]
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   mod vs gprmax: {error:.4f}")
        assert np.isfinite(error)
        if frequency_hz not in VALIDATION_FREQUENCIES_HZ:
            continue
        assert error < GPRMAX_MAX_RELATIVE_ERROR, (
            f"gpr_bem_mod relative error {error:.4f} at {frequency_hz / 1e9:.1f} GHz vs gprMax "
            f"exceeds {GPRMAX_MAX_RELATIVE_ERROR}"
        )
    print()


def test_two_circle_kdiff_real_boundary(comparison_results) -> None:
    row = comparison_results["gpr_bem_kdiff"]
    print("\ngpr_bem_kdiff vs gpr_bem_mod (same two-circle boundary, no oracle)")
    for frequency_hz in FREQUENCIES_HZ:
        delta = row["relative_delta_to_mod"][frequency_hz]
        print(
            f"  {frequency_hz / 1e9:>4.1f} GHz   delta: {delta:.4f}   "
            f"cond: {row['condition_number'][frequency_hz]:.2e}"
        )
        assert np.isfinite(delta)
    print()


def test_two_circle_self_convergence() -> None:
    solver = gpr_bem_mod
    sources, receivers = _ring_scan()
    exterior = solver.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = solver.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    coarse_boundary = _compressed_two_circle_boundary(solver, grid=GRID)
    fine_boundary = _compressed_two_circle_boundary(solver, grid=REFINED_GRID)

    print(
        f"\ntwo-circle self-convergence (gpr_bem_mod, N={coarse_boundary.num_samples} "
        f"-> {fine_boundary.num_samples})"
    )
    for frequency_hz in FREQUENCIES_HZ:
        angular_frequency = 2.0 * np.pi * frequency_hz
        scattered = []
        for boundary in (coarse_boundary, fine_boundary):
            forward = solver.solve_ibim_tmz_total_field_batch(
                boundary,
                sources,
                receivers,
                angular_frequency,
                1.0,
                exterior=exterior,
                interior=interior,
                eps0=cfg.EPS0,
                mu0=cfg.MU0,
                offset_distance=None,
                use_strict_quadrature=True,
                backend="numpy",
            )
            scattered.append(np.asarray(forward.scattered_receiver))
        coarse_scattered, fine_scattered = scattered
        relative_change = float(
            np.linalg.norm(fine_scattered - coarse_scattered) / np.linalg.norm(fine_scattered)
        )
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   relative change: {relative_change:.4f}")
        assert np.isfinite(relative_change)
        if frequency_hz not in VALIDATION_FREQUENCIES_HZ:
            continue
        assert relative_change < SELF_CONVERGENCE_MAX_RELATIVE_CHANGE, (
            f"two-circle scattered field changed by {relative_change:.4f} between N="
            f"{coarse_boundary.num_samples} and N={fine_boundary.num_samples} at "
            f"{frequency_hz / 1e9:.1f} GHz -- exceeds {SELF_CONVERGENCE_MAX_RELATIVE_CHANGE}"
        )
    print()
