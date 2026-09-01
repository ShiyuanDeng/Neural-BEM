"""Side-by-side comparison of the two solver packages, plus gprMax, on one
square scattering case.

Parallel to ``test_circle_comparison.py``, but for a target with corners
instead of a smooth curve. There is no closed-form (Mie/Fourier-Bessel-style)
oracle for a square cross-section, so this file leans on two different checks
instead of a single analytic yardstick:

- gprMax as the external oracle, via ``solvers/gprmax_ref/``. A square target
  *aligned to the FDTD grid* has zero staircasing (``build_geometry`` snaps
  the half-side to a whole number of cells) -- unlike the circle case, where
  staircasing was gprMax's dominant error source (see
  ``docs/gprmax_reference_study.md``). The square only has 4-fold symmetry,
  though, not the circle's full rotational symmetry, so gprMax's one
  simulated Tx/Rx pair only matches the ring scan's index-0 entry; the error
  columns below compare only that one pair, not the whole ring.
- Self-convergence (N -> a refined N) as an in-repo check that does not depend
  on gprMax at all, mirroring ``solvers/nystrom_ref``'s ellipse/star tests.

The target is centered the same place as the circle case and given the explicit
``TARGET_HALF_SIDE`` from ``config.square_config`` -- not area-matched, just
"roughly the same size", per the request that started this file.

Regenerate the gprMax cache with::

    /home/drdeng/miniconda3/envs/gprMax/bin/python solvers/gprmax_ref/run_case.py \
        --target-shape square

Run this file so the table is visible::

    python -m pytest pytest/test_square_comparison.py -s -q
"""

from __future__ import annotations

import math
import time
import warnings

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config.square_config as cfg
import gpr_bem_kdiff
import gpr_bem_mod
import gpr_bem_ref
from gprmax_ref import cache_io as gprmax_cache_io

SOLVERS = (("gpr_bem_ref", gpr_bem_ref), ("gpr_bem_mod", gpr_bem_mod))

HALF_SIDE = float(cfg.TARGET_HALF_SIDE)
CENTER = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))
BOUNDS = (
    (CENTER[0] - 3.0 * HALF_SIDE, CENTER[1] - 3.0 * HALF_SIDE),
    (CENTER[0] + 3.0 * HALF_SIDE, CENTER[1] + 3.0 * HALF_SIDE),
)
GRID = (161, 161)
REFINED_GRID = (241, 241)
REF_OFFSET_SCALE = 2.0
RING_STANDOFF = 0.30
NUM_RING_PAIRS = 24
VALIDATION_FREQUENCIES_HZ = (0.5e9, 1.5e9, 2.5e9)
HIGH_ERROR_FREQUENCIES_HZ = (4.0e9, 6.0e9, 8.0e9)
FREQUENCIES_HZ = VALIDATION_FREQUENCIES_HZ + HIGH_ERROR_FREQUENCIES_HZ

GPRMAX_MAX_RELATIVE_ERROR = 0.15
SELF_CONVERGENCE_MAX_RELATIVE_CHANGE = 0.25


def _ring_scan() -> tuple[np.ndarray, np.ndarray]:
    """A ring of bistatic Tx/Rx pairs around the target, as the notebook builds it.

    Angle 0 (index 0) is the pair gprMax's single representative run actually
    matches -- see ``build_geometry`` in ``solvers/gprmax_ref/build_scene.py``.
    """

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


def _compressed_square_boundary(solver, *, grid: tuple[int, int] = GRID):
    """Build the boundary with the solver's *own* geometry code.

    The two packages hold separate copies of every class, so a boundary built
    by one would fail the ``isinstance`` checks inside the other.
    """

    def phi(points):
        return solver.rectangle_signed_distance(points, center=CENTER, half_extents=(HALF_SIDE, HALF_SIDE))

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = solver.build_implicit_boundary_band(phi, BOUNDS, grid_shape=grid, dtype=torch.float64)
        return solver.compress_implicit_boundary_band(band)


def _run_solver(name: str, solver) -> dict:
    """Solve the ring case at every frequency and collect the metrics.

    Unlike ``test_circle_comparison.py``, no oracle is available here, so
    ``relative_error`` starts as all-NaN and is filled in later, only for the
    single frequency-by-frequency index-0 pair, by ``_attach_gprmax_errors``.
    """

    sources, receivers = _ring_scan()
    exterior = solver.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = solver.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    boundary = _compressed_square_boundary(solver)
    requested_offset_distance = None if name == "gpr_bem_mod" else REF_OFFSET_SCALE * float(boundary.merge_distance)

    metrics = {
        "num_samples": int(boundary.num_samples),
        "merge_distance": float(boundary.merge_distance),
        "requested_offset_distance": requested_offset_distance,
        "offset_distance": None,
        "formulation": "unknown",
        "normal_derivative_scheme": "unknown",
        "relative_error": {f: float("nan") for f in FREQUENCIES_HZ},
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
    """``gpr_bem_kdiff`` on the real compressed square boundary.

    The sharpest test yet of the diagonal treatment: a square's corners are
    an actual SDF-gradient discontinuity, not just rapidly-varying curvature
    the way the star's lobes are. This now passes ``sdf_fn`` so the diagonal
    fit uses exact autograd curvature (``_sdf_curvature``) instead of the
    neighbour-turning-angle estimate -- removes one source of error, but not
    the missing off-diagonal near-neighbour log correction for T (see
    docs/validation_change_log.md), so this still is not expected to be a
    clean win -- printed for visibility.
    """

    def phi(points):
        return gpr_bem_kdiff.rectangle_signed_distance(points, center=CENTER, half_extents=(HALF_SIDE, HALF_SIDE))

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = gpr_bem_kdiff.build_implicit_boundary_band(phi, BOUNDS, grid_shape=GRID, dtype=torch.float64)
        boundary = gpr_bem_kdiff.compress_implicit_boundary_band(band)

    sources, receivers = _ring_scan()
    exterior = gpr_bem_kdiff.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_kdiff.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    metrics = {
        "num_samples": int(boundary.num_samples),
        "offset_distance": None,
        "formulation": "muller",
        "normal_derivative_scheme": "kdiff_sdfcurv",
        "relative_error": {f: float("nan") for f in FREQUENCIES_HZ},
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
            sdf_fn=phi,
        )
        metrics["elapsed_seconds"] += time.perf_counter() - started
        metrics["scattered"][frequency_hz] = np.asarray(forward.scattered_receiver)
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(np.linalg.cond(forward.system.system_matrix[0]))
    return metrics


def _gprmax_result() -> dict | None:
    """Load the cached gprMax FDTD run for this case, or ``None`` on a miss."""

    params = gprmax_cache_io.build_params(
        target_shape="square",
        target_size=HALF_SIDE,
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
    return cached


def _attach_gprmax_errors(results: dict[str, dict], gprmax_result: dict) -> None:
    """Fill ``relative_error`` in place, comparing only the index-0 ring pair.

    That is the only one gprMax's single representative Tx/Rx pair matches --
    the square only has 4-fold symmetry, not the circle's full rotational one,
    so the other 23 ring pairs have no oracle to compare against here.
    """

    for metrics in results.values():
        for entry in gprmax_cache_io.iter_frequency_results(gprmax_result):
            frequency_hz = float(entry["frequency_hz"])
            exact = complex(entry["scattered_real"], entry["scattered_imag"])
            got = complex(metrics["scattered"][frequency_hz][0])
            metrics["relative_error"][frequency_hz] = abs(got - exact) / abs(exact)


def _format_table(results: dict[str, dict]) -> str:
    """One row per solver, metrics across the columns."""

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
    return results


@pytest.fixture(scope="module")
def gprmax_result() -> dict | None:
    return _gprmax_result()


def test_square_comparison_table(comparison_results, gprmax_result) -> None:
    """Print the side-by-side table.

    No closed-form oracle exists for a square cross-section, so unlike
    ``test_circle_comparison.py`` this does not gate on an accuracy
    threshold -- see ``test_square_gprmax_cross_check`` and
    ``test_square_self_convergence`` for the checks that do.
    """

    if gprmax_result is not None:
        _attach_gprmax_errors(comparison_results, gprmax_result)

    print("\n\nSquare scattering, gpr_bem_ref vs gpr_bem_mod")
    print(
        f"  square half-side={HALF_SIDE:.3f} m at {CENTER}, grid {GRID[0]}x{GRID[1]}, "
        f"ref offset = {REF_OFFSET_SCALE} x merge_distance; mod offset = solver default"
    )
    print(f"  {NUM_RING_PAIRS} bistatic Tx/Rx pairs on a {RING_STANDOFF:.2f} m ring")
    if gprmax_result is not None:
        print(
            "  err columns: index-0 ring pair only, vs gprMax "
            "(4/6/8 GHz shown as diagnostics, not gated)\n"
        )
    else:
        print("  err columns: n/a, no gprMax cache for this case -- see test_square_gprmax_cross_check\n")
    print(_format_table(comparison_results))
    print()

    for metrics in comparison_results.values():
        for frequency_hz in FREQUENCIES_HZ:
            assert np.isfinite(metrics["condition_number"][frequency_hz])
            assert np.isfinite(metrics["residual"][frequency_hz])


def test_square_gprmax_cross_check(comparison_results, gprmax_result) -> None:
    """An independent method (FDTD, zero staircasing here) should not
    contradict ``gpr_bem_mod``, on the one pair it actually ran."""

    if gprmax_result is None:
        pytest.skip(
            "gprMax cache not found for the current config values -- regenerate with "
            "solvers/gprmax_ref/run_case.py --target-shape square"
        )
    _attach_gprmax_errors(comparison_results, gprmax_result)

    modified = comparison_results["gpr_bem_mod"]
    print("\nsquare gprMax cross-check (index-0 ring pair only)")
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


def test_square_kdiff_real_boundary(comparison_results, gprmax_result) -> None:
    """``gpr_bem_kdiff`` vs gprMax, index-0 pair only (printed, no gate --
    corners are the hardest case for the local-curvature diagonal treatment
    and the off-diagonal correction is still missing; see
    docs/validation_change_log.md)."""

    if gprmax_result is None:
        pytest.skip(
            "gprMax cache not found for the current config values -- regenerate with "
            "solvers/gprmax_ref/run_case.py --target-shape square"
        )
    _attach_gprmax_errors(comparison_results, gprmax_result)

    row = comparison_results["gpr_bem_kdiff"]
    print("\nsquare gpr_bem_kdiff vs gprMax (index-0 ring pair only)")
    for frequency_hz in FREQUENCIES_HZ:
        error = row["relative_error"][frequency_hz]
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   kdiff vs gprmax: {error:.4f}")
        assert np.isfinite(error)
    print()


def test_square_self_convergence() -> None:
    """Does not depend on gprMax at all: gpr_bem_mod's scattered field should
    not swing wildly as the boundary is refined, which is the thing a square's
    corners (an SDF gradient discontinuity the circle never exercises) could
    plausibly break. Not a rigorous convergence-order study, just a floor
    under how much N=161^2 -> 241^2 is allowed to move the answer.
    """

    solver = gpr_bem_mod
    sources, receivers = _ring_scan()
    exterior = solver.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = solver.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    coarse_boundary = _compressed_square_boundary(solver, grid=GRID)
    fine_boundary = _compressed_square_boundary(solver, grid=REFINED_GRID)

    print(
        f"\nsquare self-convergence (gpr_bem_mod, N={coarse_boundary.num_samples} "
        f"-> {fine_boundary.num_samples})"
    )
    for frequency_hz in FREQUENCIES_HZ:
        angular_frequency = 2.0 * np.pi * frequency_hz
        results = []
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
            results.append(np.asarray(forward.scattered_receiver))
        coarse_scattered, fine_scattered = results
        relative_change = float(
            np.linalg.norm(fine_scattered - coarse_scattered) / np.linalg.norm(fine_scattered)
        )
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   relative change: {relative_change:.4f}")
        assert np.isfinite(relative_change)
        if frequency_hz not in VALIDATION_FREQUENCIES_HZ:
            continue
        assert relative_change < SELF_CONVERGENCE_MAX_RELATIVE_CHANGE, (
            f"square scattered field changed by {relative_change:.4f} between N="
            f"{coarse_boundary.num_samples} and N={fine_boundary.num_samples} at "
            f"{frequency_hz / 1e9:.1f} GHz -- exceeds {SELF_CONVERGENCE_MAX_RELATIVE_CHANGE}"
        )
    print()
