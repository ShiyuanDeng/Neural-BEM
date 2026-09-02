"""Compare ref/mod/gprMax on a smooth star, using Nystrom as truth.

The star parameters match ``docs/nystrom_reference_study.md``:
``r(t) = 0.05 * (1 + 0.25 cos(5t))``. Nystrom is treated as the baseline here
because its documented self-convergence is near machine precision for this
smooth shape. gprMax is included as an independent FDTD cross-check, but only
for the index-0 ring pair because the star is not rotationally symmetric.

Regenerate the gprMax cache with::

    /home/drdeng/miniconda3/envs/gprMax/bin/python solvers/gprmax_ref/run_case.py \
        --target-shape star

Run this file so the table is visible::

    python -m pytest pytest/solver_comparisons/test_star_comparison.py -s -q
"""

from __future__ import annotations

import math
import time
import warnings

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config.star_config as cfg
import gpr_bem_kdiff
import gpr_bem_mod
import gpr_bem_qbx
import gpr_bem_ref
from gprmax_ref import cache_io as gprmax_cache_io
from nystrom_ref import build_curve, solve_transmission, star_parameterization
from archived_qbx.qbx_comparison_support import run_qbx_metrics

SOLVERS = (("gpr_bem_ref", gpr_bem_ref), ("gpr_bem_mod", gpr_bem_mod))

MEAN_RADIUS = float(cfg.TARGET_MEAN_RADIUS)
AMPLITUDE = float(cfg.TARGET_STAR_AMPLITUDE)
LOBES = int(cfg.TARGET_STAR_LOBES)
TARGET_SIZE = float(cfg.TARGET_SIZE)
CENTER = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))
BOUNDS = (
    (CENTER[0] - 3.0 * TARGET_SIZE, CENTER[1] - 3.0 * TARGET_SIZE),
    (CENTER[0] + 3.0 * TARGET_SIZE, CENTER[1] + 3.0 * TARGET_SIZE),
)
GRID = (161, 161)
REF_OFFSET_SCALE = 2.0
RING_STANDOFF = 0.30
NUM_RING_PAIRS = 24
NYSTROM_N = 512
VALIDATION_FREQUENCIES_HZ = (0.5e9, 1.5e9, 2.5e9)
HIGH_ERROR_FREQUENCIES_HZ = (4.0e9, 6.0e9, 8.0e9)
FREQUENCIES_HZ = VALIDATION_FREQUENCIES_HZ + HIGH_ERROR_FREQUENCIES_HZ

GPRMAX_MAX_RELATIVE_ERROR = 0.50


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


def _chebyshev_t(values: torch.Tensor, order: int) -> torch.Tensor:
    if order == 0:
        return torch.ones_like(values)
    if order == 1:
        return values
    previous = torch.ones_like(values)
    current = values
    for _ in range(2, order + 1):
        previous, current = current, 2.0 * values * current - previous
    return current


def _star_level_set(points: torch.Tensor) -> torch.Tensor:
    center = torch.tensor(CENTER, device=points.device, dtype=points.dtype)
    rel = points - center[None, :]
    radius = torch.sqrt(torch.sum(rel * rel, dim=1, keepdim=True) + 1.0e-30)
    cos_theta = rel[:, 0:1] / radius
    cos_lobes_theta = _chebyshev_t(cos_theta, LOBES)
    boundary_radius = MEAN_RADIUS * (1.0 + AMPLITUDE * cos_lobes_theta)
    return radius - boundary_radius


def _compressed_star_boundary(solver):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = solver.build_implicit_boundary_band(
            _star_level_set,
            BOUNDS,
            grid_shape=GRID,
            dtype=torch.float64,
        )
        return solver.compress_implicit_boundary_band(band)


def _wavenumbers(frequency_hz: float) -> tuple[complex, complex]:
    angular_frequency = 2.0 * np.pi * frequency_hz
    exterior = gpr_bem_ref.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_ref.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    return (
        exterior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0),
        interior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0),
    )


def _nystrom_baseline() -> dict:
    sources, receivers = _ring_scan()
    curve = build_curve(star_parameterization(CENTER, MEAN_RADIUS, AMPLITUDE, LOBES), NYSTROM_N, "star")
    baseline = {
        "scattered": {},
        "residual": {},
        "incident_consistency": {},
        "elapsed_seconds": 0.0,
    }
    for frequency_hz in FREQUENCIES_HZ:
        k_exterior, k_interior = _wavenumbers(frequency_hz)
        started = time.perf_counter()
        solution = solve_transmission(curve, sources, receivers, k_exterior, k_interior)
        baseline["elapsed_seconds"] += time.perf_counter() - started
        baseline["scattered"][frequency_hz] = np.diag(solution.scattered)
        baseline["residual"][frequency_hz] = float(solution.relative_residual)
        baseline["incident_consistency"][frequency_hz] = float(solution.incident_consistency)
    return baseline


def _run_solver(name: str, solver, nystrom: dict) -> dict:
    sources, receivers = _ring_scan()
    exterior = solver.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = solver.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    boundary = _compressed_star_boundary(solver)
    requested_offset_distance = None if name == "gpr_bem_mod" else REF_OFFSET_SCALE * float(boundary.merge_distance)
    metrics = {
        "num_samples": int(boundary.num_samples),
        "merge_distance": float(boundary.merge_distance),
        "requested_offset_distance": requested_offset_distance,
        "offset_distance": None,
        "formulation": "unknown",
        "normal_derivative_scheme": "unknown",
        "relative_error": {},
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
        scattered = np.asarray(forward.scattered_receiver)
        exact = nystrom["scattered"][frequency_hz]
        metrics["scattered"][frequency_hz] = scattered
        metrics["relative_error"][frequency_hz] = float(np.linalg.norm(scattered - exact) / np.linalg.norm(exact))
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(np.linalg.cond(np.asarray(forward.system.system_matrix)[0]))

    return metrics


def _kdiff_metrics(nystrom: dict) -> dict:
    """``gpr_bem_kdiff`` on the real compressed star boundary, vs Nystrom.

    Validation-order step 2b: the star is the harder of the two smooth
    non-circular shapes (5 lobes, amplitude 0.25 -- curvature varies far more
    than the ellipse), so this is the sharpest test yet of the local-
    curvature diagonal treatment before the square's actual corners. Known
    limitation carried over from circle/ellipse: no off-diagonal near-
    neighbour log correction yet -- see docs/validation_change_log.md.
    """

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = gpr_bem_kdiff.build_implicit_boundary_band(
            _star_level_set, BOUNDS, grid_shape=GRID, dtype=torch.float64
        )
        boundary = gpr_bem_kdiff.compress_implicit_boundary_band(band)

    sources, receivers = _ring_scan()
    exterior = gpr_bem_kdiff.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_kdiff.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    metrics = {
        "num_samples": int(boundary.num_samples),
        "offset_distance": None,
        "formulation": "muller",
        "normal_derivative_scheme": "kdiff_local",
        "relative_error": {},
        "condition_number": {},
        "residual": {},
        "scattered": {},
        "elapsed_seconds": 0.0,
    }
    for frequency_hz in FREQUENCIES_HZ:
        angular_frequency = 2.0 * np.pi * frequency_hz
        started = time.perf_counter()
        forward = gpr_bem_kdiff.solve_ibim_tmz_total_field_batch(
            boundary, sources, receivers, angular_frequency, 1.0,
            exterior=exterior, interior=interior, eps0=cfg.EPS0, mu0=cfg.MU0,
        )
        metrics["elapsed_seconds"] += time.perf_counter() - started
        scattered = np.asarray(forward.scattered_receiver)
        exact = nystrom["scattered"][frequency_hz]
        metrics["scattered"][frequency_hz] = scattered
        metrics["relative_error"][frequency_hz] = float(np.linalg.norm(scattered - exact) / np.linalg.norm(exact))
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(np.linalg.cond(forward.system.system_matrix[0]))
    return metrics


def _qbx_rows(nystrom: dict) -> dict[str, dict]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = gpr_bem_kdiff.build_implicit_boundary_band(
            _star_level_set, BOUNDS, grid_shape=GRID, dtype=torch.float64
        )
        boundary = gpr_bem_kdiff.compress_implicit_boundary_band(band)

    points = boundary.points.detach().cpu().numpy()
    target_t = np.mod(
        np.arctan2(points[:, 1] - CENTER[1], points[:, 0] - CENTER[0]),
        2.0 * np.pi,
    )
    strategies = {
        "gpr_bem_qbx": (
            gpr_bem_qbx.FullRowQBX(
                source=gpr_bem_qbx.SameNodeSources(), source_workers=8, allow_invalid_clearance=True
            ),
            "qbx_1x",
        ),
        "qbx_fourier8": (
            gpr_bem_qbx.FullRowQBX(
                source_workers=8,
                allow_invalid_clearance=True,
                source=gpr_bem_qbx.ParameterizedFourierSources(
                    parameterization=star_parameterization(CENTER, MEAN_RADIUS, AMPLITUDE, LOBES),
                    oversampling_factor=8,
                    target_parameters=target_t,
                )
            ),
            "qbx_f8",
        ),
        "qbx_sdfraw8": (
            gpr_bem_qbx.FullRowQBX(
                source_workers=8,
                allow_invalid_clearance=True,
                source=gpr_bem_qbx.RawSDFBandSources(
                    grid_refinement_factor=8,
                    base_grid_shape=GRID,
                )
            ),
            "qbx_s8",
        ),
    }
    sources, receivers = _ring_scan()
    exterior = gpr_bem_kdiff.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_kdiff.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)
    return {
        name: run_qbx_metrics(
            boundary=boundary,
            sources=sources,
            receivers=receivers,
            frequencies_hz=FREQUENCIES_HZ,
            exterior=exterior,
            interior=interior,
            eps0=cfg.EPS0,
            mu0=cfg.MU0,
            t_assembly=strategy,
            discretization=discretization,
            sdf_fn=_star_level_set,
            reference_field=nystrom["scattered"],
        )
        for name, (strategy, discretization) in strategies.items()
    }


def _gprmax_target_parameters() -> dict[str, float | int]:
    return {"mean_radius": MEAN_RADIUS, "amplitude": AMPLITUDE, "lobes": LOBES}


def _gprmax_metrics(nystrom: dict) -> dict | None:
    params = gprmax_cache_io.build_params(
        target_shape="star",
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
    cached = gprmax_cache_io.load_frequency_sweep(params)
    if cached is None:
        return None
    metrics = {
        "num_samples": None,
        "offset_distance": None,
        "formulation": "FDTD",
        "normal_derivative_scheme": f"dx={gprmax_cache_io.cell_size_label(cached)}",
        "relative_error": {f: float("nan") for f in FREQUENCIES_HZ},
        "condition_number": {f: float("nan") for f in FREQUENCIES_HZ},
        "residual": {f: float("nan") for f in FREQUENCIES_HZ},
        "elapsed_seconds": gprmax_cache_io.wall_clock_seconds(cached),
    }
    for entry in gprmax_cache_io.iter_frequency_results(cached):
        frequency_hz = float(entry["frequency_hz"])
        got = complex(entry["scattered_real"], entry["scattered_imag"])
        exact = complex(nystrom["scattered"][frequency_hz][0])
        metrics["relative_error"][frequency_hz] = float(abs(got - exact) / abs(exact))
    return metrics


def _format_table(results: dict[str, dict]) -> str:
    ghz = [f"{f / 1e9:.1f}" for f in FREQUENCIES_HZ]
    header = (
        f"{'solver':<14}{'N':>5}{'offset':>10} {'method':>7} {'disc':>7}"
        + "".join(f"{'err ' + g + 'GHz':>13}" for g in ghz)
        + f"{'max resid':>12}{'time [s]':>10}"
    )
    lines = [header, "-" * len(header)]
    for name, metrics in results.items():
        num_samples = f"{metrics['num_samples']:>5}" if metrics["num_samples"] is not None else f"{'--':>5}"
        offset = f"{metrics['offset_distance']:>10.5f}" if metrics["offset_distance"] is not None else f"{'--':>10}"
        row = f"{name:<14}{num_samples}{offset}"
        row += f" {_display_method(name, metrics):>7} {_display_discretization(metrics):>7}"
        row += "".join(_format_error(metrics["relative_error"][f]) for f in FREQUENCIES_HZ)
        residuals = [r for r in metrics["residual"].values() if not math.isnan(r)]
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
    if formulation == "FDTD":
        return "fdtd"
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
    if scheme.startswith("dx="):
        return scheme[3:]
    return scheme[:7]


@pytest.fixture(scope="module")
def nystrom_baseline() -> dict:
    return _nystrom_baseline()


@pytest.fixture(scope="module")
def comparison_results(nystrom_baseline, include_qbx_archive) -> dict[str, dict]:
    results = {name: _run_solver(name, solver, nystrom_baseline) for name, solver in SOLVERS}
    results["gpr_bem_kdiff"] = _kdiff_metrics(nystrom_baseline)
    if include_qbx_archive:
        results.update(_qbx_rows(nystrom_baseline))
    gprmax = _gprmax_metrics(nystrom_baseline)
    if gprmax is not None:
        results["gprmax"] = gprmax
    return results


def test_star_comparison_table(comparison_results, nystrom_baseline) -> None:
    print("\n\nStar scattering vs. Nystrom reference")
    print(
        f"  star r0={MEAN_RADIUS:.3f} m, amp={AMPLITUDE:.2f}, lobes={LOBES} at {CENTER}, "
        f"grid {GRID[0]}x{GRID[1]}, Nystrom N={NYSTROM_N}"
    )
    print(f"  {NUM_RING_PAIRS} bistatic Tx/Rx pairs on a {RING_STANDOFF:.2f} m ring")
    print("  err columns: BEM rows use the full ring vs Nystrom; gprMax is index-0 only")
    print("  4/6/8 GHz shown as diagnostics, not gated\n")
    print(_format_table(comparison_results))
    print()

    for residual in nystrom_baseline["residual"].values():
        assert residual < 1.0e-10
    for name, metrics in comparison_results.items():
        if name == "gprmax":
            continue
        for frequency_hz in FREQUENCIES_HZ:
            assert np.isfinite(metrics["condition_number"][frequency_hz])
            assert np.isfinite(metrics["residual"][frequency_hz])


def test_modified_solver_improves_star_accuracy(comparison_results) -> None:
    reference = comparison_results["gpr_bem_ref"]
    modified = comparison_results["gpr_bem_mod"]

    assert modified["formulation"] == "muller"
    assert modified["normal_derivative_scheme"] == "analytic_extrapolated"
    assert modified["offset_distance"] == pytest.approx(0.275 * modified["merge_distance"])

    print("\nmodified solver improvement against Nystrom on the star")
    for frequency_hz in FREQUENCIES_HZ:
        ref_error = reference["relative_error"][frequency_hz]
        mod_error = modified["relative_error"][frequency_hz]
        improvement = ref_error / max(mod_error, 1.0e-15)
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   {improvement:.2f}x")
        if frequency_hz in VALIDATION_FREQUENCIES_HZ:
            assert mod_error < ref_error
    print()


def test_star_kdiff_real_boundary(comparison_results) -> None:
    """``gpr_bem_kdiff`` vs Nystrom, printed in full (no gate yet)."""

    row = comparison_results["gpr_bem_kdiff"]
    print("\ngpr_bem_kdiff vs Nystrom (real compressed star boundary)")
    for frequency_hz in FREQUENCIES_HZ:
        error = row["relative_error"][frequency_hz]
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   error: {error:.4e}   cond: {row['condition_number'][frequency_hz]:.2e}")
        assert np.isfinite(error)
    print()


def test_star_gprmax_cross_check(comparison_results) -> None:
    gprmax = comparison_results.get("gprmax")
    if gprmax is None:
        pytest.skip(
            "gprMax cache not found for star -- regenerate with "
            "solvers/gprmax_ref/run_case.py --target-shape star"
        )

    modified = comparison_results["gpr_bem_mod"]
    print("\nstar gprMax cross-check (index-0 pair only, vs Nystrom)")
    for frequency_hz in FREQUENCIES_HZ:
        gprmax_error = gprmax["relative_error"][frequency_hz]
        mod_error = modified["relative_error"][frequency_hz]
        print(
            f"  {frequency_hz / 1e9:>4.1f} GHz   gprmax: {gprmax_error:.4f}   "
            f"mod full-ring: {mod_error:.4f}"
        )
        assert np.isfinite(gprmax_error)
        if frequency_hz not in VALIDATION_FREQUENCIES_HZ:
            continue
        assert gprmax_error < GPRMAX_MAX_RELATIVE_ERROR, (
            f"star gprMax relative error {gprmax_error:.4f} at {frequency_hz / 1e9:.1f} GHz "
            f"exceeds {GPRMAX_MAX_RELATIVE_ERROR}"
        )
    print()
