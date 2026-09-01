"""Side-by-side comparison of the two solver packages, plus gprMax, on one
circle scattering case.

See ``test_square_comparison.py`` for the parallel non-circular case -- it
cannot reuse a Mie-series oracle (no closed form for a square cross-section),
so it leans on a self-convergence check plus gprMax instead. This file has the
easier job: a real oracle exists here.

The two BEM packages are imported directly under their real names, so this runs
them in a single process against the same geometry and the same analytic
yardstick. It does not use the ``--solver`` alias from ``conftest.py``.

The case is the one from ``notebooks/_build_notebook.py``: the config's plastic
cylinder in sand, a 161x161 narrow band compressed onto the level set, and a ring
of 24 bistatic Tx/Rx pairs at 0.30 m. The frozen reference uses its historical
``2.0 * merge_distance`` stand-off; the modified solver uses its own default.
Truth is the Mie series ``penetrable_cylinder_scattered_field``.

The third row, gprMax, is a genuinely independent method (FDTD, not a BIE) run
out of process and read from a cache -- see ``solvers/gprmax_ref/`` and
``docs/gprmax_reference_study.md``. If the cache has not been generated for the
current config values, that row is silently omitted rather than failing the
test; regenerate it with::

    /home/drdeng/miniconda3/envs/gprMax/bin/python solvers/gprmax_ref/run_case.py \
        --target-shape circle

A fourth row, ``gpr_bem_kdiff``, is a third solver *package*
(``solvers/gpr_bem_kdiff/``, forked from ``gpr_bem_mod``) that assembles the
same kernel-differenced quadrature directly on the real
``compress_implicit_boundary_band`` boundary -- no perfect-sampling
requirement, works on the boundary ref/mod actually use. Its off-diagonal
near-neighbour log correction for the hypersingular block isn't built yet
(measured, not assumed -- see ``docs/validation_change_log.md``), so it
currently lands near ``gpr_bem_mod``'s own accuracy rather than
``kernel_diff_ref``'s, and breaks down at 8 GHz; printed in full by
``test_circle_kdiff_real_boundary``, gated only at 0.5/1.5/2.5 GHz.

A fifth row, ``kernel_diff*``, is ``gpr_bem_mod``'s own Muller formulation
but with the boundary trace built by ``solvers/kernel_diff_ref/`` --
kernel-differenced quadrature with no finite stand-off, instead of `mod`'s
``+-offset`` averaging. It always uses ``perfect_circle_boundary_samples``
(marked with the trailing ``*``), regardless of ``--perfect-sampling``, since
it has no irregular-node handling yet. See
``test_circle_kernel_diff_perfect_sampling`` and
``docs/validation_change_log.md``.

Run this file so the table is visible::

    python -m pytest pytest/test_circle_comparison.py -s -q
"""

from __future__ import annotations

import math
import time
import warnings

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import config.circle_config as cfg
import gpr_bem_kdiff
import gpr_bem_mod
import gpr_bem_qbx
import gpr_bem_ref
from gprmax_ref import cache_io as gprmax_cache_io
from kernel_diff_ref import solve_transmission_on_circle
from nystrom_ref import circle_parameterization
from qbx_comparison_support import run_qbx_metrics

SOLVERS = (("gpr_bem_ref", gpr_bem_ref), ("gpr_bem_mod", gpr_bem_mod))

RADIUS = float(cfg.TARGET_RADIUS)
CENTER = (float(cfg.TARGET_CENTER_X), float(cfg.TARGET_CENTER_Y))
BOUNDS = (
    (CENTER[0] - 3.0 * RADIUS, CENTER[1] - 3.0 * RADIUS),
    (CENTER[0] + 3.0 * RADIUS, CENTER[1] + 3.0 * RADIUS),
)
GRID = (161, 161)
REF_OFFSET_SCALE = 2.0
RING_STANDOFF = 0.30
NUM_RING_PAIRS = 24
VALIDATION_FREQUENCIES_HZ = (0.5e9, 1.5e9, 2.5e9)
HIGH_ERROR_FREQUENCIES_HZ = (4.0e9, 6.0e9, 8.0e9)
FREQUENCIES_HZ = VALIDATION_FREQUENCIES_HZ + HIGH_ERROR_FREQUENCIES_HZ

MAX_RELATIVE_ERROR = {
    "gpr_bem_ref": {0.5e9: 0.25},
    "gpr_bem_mod": {0.5e9: 0.05, 1.5e9: 0.15, 2.5e9: 0.35},
}


def _ring_scan() -> tuple[np.ndarray, np.ndarray]:
    """A ring of bistatic Tx/Rx pairs around the target, as the notebook builds it."""

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


def _compressed_circle_boundary(solver):
    """Build the boundary with the solver's *own* geometry code.

    The two packages hold separate copies of every class, so a boundary built by
    one would fail the ``isinstance`` checks inside the other. The geometry code
    is identical and deterministic, so this costs nothing in comparability.
    """

    def phi(points):
        return solver.circle_signed_distance(points, center=CENTER, radius=RADIUS)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
        band = solver.build_implicit_boundary_band(
            phi, BOUNDS, grid_shape=GRID, dtype=torch.float64
        )
        return solver.compress_implicit_boundary_band(band)


def _run_solver(name: str, solver, *, perfect_sampling: bool = False) -> dict:
    """Solve the ring case at every frequency and collect the metrics.

    ``perfect_sampling`` swaps the real compressed boundary for
    ``perfect_circle_boundary_samples`` at the *same* node count -- everything
    else (offset rule, formulation, kernels) is untouched, so any accuracy
    delta isolates node placement from those.
    """

    sources, receivers = _ring_scan()
    exterior = solver.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = solver.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    boundary = _compressed_circle_boundary(solver)
    if perfect_sampling:
        boundary = solver.perfect_circle_boundary_samples(
            center=CENTER,
            radius=RADIUS,
            num_samples=boundary.num_samples,
            bounds=BOUNDS,
            dtype=torch.float64,
        )
    requested_offset_distance = None if name == "gpr_bem_mod" else REF_OFFSET_SCALE * float(boundary.merge_distance)

    metrics = {
        "num_samples": int(boundary.num_samples),
        "merge_distance": float(boundary.merge_distance),
        "requested_offset_distance": requested_offset_distance,
        "offset_distance": None,
        "formulation": "unknown",
        "normal_derivative_scheme": "unknown",
        "sampling": "perfect" if perfect_sampling else "ibim",
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

        # One yardstick for both solvers: the reference package's Mie series.
        exact = gpr_bem_ref.penetrable_cylinder_scattered_field(
            receivers,
            sources,
            k_exterior=forward.system.k_exterior,
            k_interior=forward.system.k_interior,
            radius=RADIUS,
            center=CENTER,
        )
        scattered = np.asarray(forward.scattered_receiver)
        metrics["scattered"][frequency_hz] = scattered
        metrics["relative_error"][frequency_hz] = float(
            np.linalg.norm(scattered - exact) / np.linalg.norm(exact)
        )
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(
            np.linalg.cond(np.asarray(forward.system.system_matrix)[0])
        )

    return metrics


def _kdiff_metrics(perfect_sampling: bool) -> dict:
    """``gpr_bem_kdiff``: combined-wavenumber, no-offset kernel-differenced
    quadrature, on the real ``compress_implicit_boundary_band`` boundary (or
    the perfect one, same as ref/mod, when ``--perfect-sampling`` is set).

    Known limitation: the off-diagonal near-neighbour log-singular correction
    for the hypersingular block is not implemented. Later QBX probes showed
    that treating it as the next isolated fix did not remove the
    compressed-target floor; see ``docs/qbx_closure.md``. This frozen baseline
    is printed for visibility and is not gated at 8 GHz.
    """

    if perfect_sampling:
        boundary = gpr_bem_kdiff.perfect_circle_boundary_samples(
            center=CENTER, radius=RADIUS, num_samples=168, bounds=BOUNDS, dtype=torch.float64,
        )
    else:
        def phi(points):
            return gpr_bem_kdiff.circle_signed_distance(points, center=CENTER, radius=RADIUS)

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
        exact = gpr_bem_ref.penetrable_cylinder_scattered_field(
            receivers, sources, k_exterior=forward.system.k_exterior, k_interior=forward.system.k_interior,
            radius=RADIUS, center=CENTER,
        )
        scattered = np.asarray(forward.scattered_receiver)
        metrics["scattered"][frequency_hz] = scattered
        metrics["relative_error"][frequency_hz] = float(
            np.linalg.norm(scattered - exact) / np.linalg.norm(exact)
        )
        metrics["residual"][frequency_hz] = float(forward.linear_system_relative_residual)
        metrics["condition_number"][frequency_hz] = float(np.linalg.cond(forward.system.system_matrix[0]))
    return metrics


def _qbx_rows(perfect_sampling: bool) -> dict[str, dict]:
    """Plain full-row QBX, then the two requested 8x source variants."""

    def phi(points):
        return gpr_bem_kdiff.circle_signed_distance(points, center=CENTER, radius=RADIUS)

    if perfect_sampling:
        boundary = gpr_bem_kdiff.perfect_circle_boundary_samples(
            center=CENTER, radius=RADIUS, num_samples=168, bounds=BOUNDS, dtype=torch.float64,
        )
    else:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="compress_implicit_boundary_band")
            band = gpr_bem_kdiff.build_implicit_boundary_band(
                phi, BOUNDS, grid_shape=GRID, dtype=torch.float64
            )
            boundary = gpr_bem_kdiff.compress_implicit_boundary_band(band)

    points = boundary.points.detach().cpu().numpy()
    target_t = np.mod(np.arctan2(points[:, 1] - CENTER[1], points[:, 0] - CENTER[0]), 2.0 * np.pi)
    parameterization = circle_parameterization(CENTER, RADIUS)
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
                    parameterization=parameterization,
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

    def reference(_frequency_hz, forward):
        return gpr_bem_ref.penetrable_cylinder_scattered_field(
            receivers,
            sources,
            k_exterior=forward.system.k_exterior,
            k_interior=forward.system.k_interior,
            radius=RADIUS,
            center=CENTER,
        )

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
            sdf_fn=phi,
            reference_field=reference,
        )
        for name, (strategy, discretization) in strategies.items()
    }


def _kernel_diff_metrics(num_samples: int) -> dict:
    """Kernel-differenced Muller quadrature (``solvers/kernel_diff_ref/``), always
    on ``perfect_circle_boundary_samples`` regardless of ``--perfect-sampling``.

    Not a variant of ``gpr_bem_mod`` -- a from-scratch quadrature that removes
    the finite trace offset entirely by differencing the exterior/interior
    kernels before integrating. It has no irregular-node handling and is
    circle-only, so running it against the real compressed IBIM boundary would
    not test anything meaningful; forcing perfect sampling here is the point,
    not a shortcut. ``num_samples`` is taken from whatever ``gpr_bem_mod`` used
    this run, so the two rows are a same-N comparison.
    """

    boundary = gpr_bem_mod.perfect_circle_boundary_samples(
        center=CENTER, radius=RADIUS, num_samples=num_samples, bounds=BOUNDS, dtype=torch.float64,
    )
    points = boundary.points.detach().cpu().numpy()
    normals = boundary.normals.detach().cpu().numpy()
    weights = boundary.quadrature_weights.detach().cpu().numpy().reshape(-1)

    sources, receivers = _ring_scan()
    exterior = gpr_bem_mod.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_mod.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

    metrics = {
        "num_samples": int(points.shape[0]),
        "offset_distance": None,
        "formulation": "muller",
        "normal_derivative_scheme": "kernel_diff",
        "relative_error": {},
        "condition_number": {},
        "residual": {},
        "scattered": {},
        "elapsed_seconds": 0.0,
    }
    for frequency_hz in FREQUENCIES_HZ:
        angular_frequency = 2.0 * np.pi * frequency_hz
        k_exterior = complex(exterior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0))
        k_interior = complex(interior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0))
        started = time.perf_counter()
        solution = solve_transmission_on_circle(
            points, normals, weights, CENTER, RADIUS, sources, receivers, k_exterior, k_interior,
            condition_number=True,
        )
        metrics["elapsed_seconds"] += time.perf_counter() - started
        exact = gpr_bem_ref.penetrable_cylinder_scattered_field(
            receivers, sources, k_exterior=k_exterior, k_interior=k_interior, radius=RADIUS, center=CENTER,
        )
        scattered = np.diag(solution.scattered)
        metrics["scattered"][frequency_hz] = scattered
        metrics["relative_error"][frequency_hz] = float(
            np.linalg.norm(scattered - exact) / np.linalg.norm(exact)
        )
        metrics["residual"][frequency_hz] = float(solution.relative_residual)
        metrics["condition_number"][frequency_hz] = float(solution.condition_number)
    return metrics


def _gprmax_metrics() -> dict | None:
    """Load the cached gprMax FDTD run for this case, or ``None`` on a miss.

    gprMax lives in its own conda environment and is never invoked here --
    only its cached result is read. See ``solvers/gprmax_ref/run_case.py``.
    """

    params = gprmax_cache_io.build_params(
        target_shape="circle",
        target_size=RADIUS,
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

    exterior = gpr_bem_ref.Material(epsr=cfg.SAND_EPSR, sigma=cfg.SAND_SIGMA)
    interior = gpr_bem_ref.Material(epsr=cfg.PLASTIC_EPSR, sigma=cfg.PLASTIC_SIGMA)

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
        tx = np.asarray(entry["tx"])[None, :]
        rx = np.asarray(entry["rx"])[None, :]
        angular_frequency = 2.0 * np.pi * frequency_hz
        k_exterior = exterior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0)
        k_interior = interior.wavenumber(angular_frequency, cfg.EPS0, cfg.MU0)
        exact = gpr_bem_ref.penetrable_cylinder_scattered_field(
            rx, tx, k_exterior=k_exterior, k_interior=k_interior, radius=RADIUS,
            center=entry["target_center"],
        )[0]
        got = complex(entry["scattered_real"], entry["scattered_imag"])
        metrics["relative_error"][frequency_hz] = float(abs(got - exact) / abs(exact))
        metrics["condition_number"][frequency_hz] = float("nan")
        metrics["residual"][frequency_hz] = float("nan")
    return metrics


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
    if scheme == "analytic_extrapolated":
        return "analy"
    if scheme == "analytic":
        return "analy"
    if scheme == "kernel_diff":
        return "kdiff"
    if scheme == "kdiff_local":
        return "kdiff2"
    if scheme.startswith("dx="):
        return scheme[3:]
    return scheme[:7]


@pytest.fixture(scope="module")
def perfect_sampling(request) -> bool:
    return bool(request.config.getoption("--perfect-sampling"))


@pytest.fixture(scope="module")
def comparison_results(perfect_sampling, include_qbx_archive) -> dict[str, dict]:
    results = {name: _run_solver(name, solver, perfect_sampling=perfect_sampling) for name, solver in SOLVERS}
    results["gpr_bem_kdiff"] = _kdiff_metrics(perfect_sampling)
    if include_qbx_archive:
        results.update(_qbx_rows(perfect_sampling))
    results["kernel_diff*"] = _kernel_diff_metrics(results["gpr_bem_mod"]["num_samples"])
    gprmax_metrics = _gprmax_metrics()
    if gprmax_metrics is not None:
        results["gprmax"] = gprmax_metrics
    return results


def test_circle_comparison_table(comparison_results, perfect_sampling) -> None:
    """Print the side-by-side table and gate on gross breakage.

    Under ``--perfect-sampling`` the per-frequency thresholds below are not
    checked -- they were tuned against the real irregular boundary, not this
    diagnostic one -- but the table still prints so the two runs can be
    compared by eye.
    """

    print("\n\nCircle scattering vs. Mie series")
    print(
        f"  circle R={RADIUS:.3f} m at {CENTER}, grid {GRID[0]}x{GRID[1]}, "
        f"ref offset = {REF_OFFSET_SCALE} x merge_distance; mod offset = solver default"
    )
    print(f"  sampling = {'perfect (uniform-arclength circle)' if perfect_sampling else 'ibim (compressed band)'}")
    print(f"  {NUM_RING_PAIRS} bistatic Tx/Rx pairs on a {RING_STANDOFF:.2f} m ring")
    print(
        "  * kernel_diff always uses perfect_circle_boundary_samples, regardless of "
        "--perfect-sampling -- see test_circle_kernel_diff_perfect_sampling\n"
    )
    print(_format_table(comparison_results))
    print(
        "\n  note: the time column is indicative only -- whichever solver runs first\n"
        "        absorbs BLAS/import warm-up, so it is not a fair benchmark."
    )
    print()

    for name, metrics in comparison_results.items():
        for frequency_hz, threshold in MAX_RELATIVE_ERROR.get(name, {}).items():
            error = metrics["relative_error"][frequency_hz]
            assert np.isfinite(error), f"{name} produced a non-finite error at {frequency_hz:.3g} Hz"
            if perfect_sampling:
                continue
            assert error < threshold, (
                f"{name} relative error {error:.4f} at {frequency_hz / 1e9:.1f} GHz "
                f"exceeds {threshold}"
            )


def test_modified_solver_improves_circle_scattering_accuracy(comparison_results, perfect_sampling) -> None:
    """The modified formulation should beat the frozen first-kind control."""

    reference = comparison_results["gpr_bem_ref"]
    modified = comparison_results["gpr_bem_mod"]

    assert modified["formulation"] == "muller"
    assert modified["normal_derivative_scheme"] == "analytic_extrapolated"
    # A pure function of merge_distance, so it holds regardless of sampling mode.
    assert modified["offset_distance"] == pytest.approx(0.275 * modified["merge_distance"])

    print("\nmodified solver improvement against the Mie series")
    for frequency_hz in FREQUENCIES_HZ:
        ref_error = reference["relative_error"][frequency_hz]
        mod_error = modified["relative_error"][frequency_hz]
        improvement = ref_error / max(mod_error, 1.0e-15)
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   {improvement:.2f}x")
        if not perfect_sampling and frequency_hz in VALIDATION_FREQUENCIES_HZ:
            assert mod_error < ref_error
    print()


# Generous relative to the measured ~1e-8 floor (see
# docs/validation_change_log.md): this checks the kernel-differenced quadrature
# has no gross regression, not that it stays at its current precision.
# Loose, and only at the validation frequencies: this frozen compressed-cloud
# baseline checks for no gross regression, not for matching kernel_diff_ref's
# accuracy; see docs/qbx_closure.md. Measured on the real compressed boundary:
# 2.6e-4 / 3.1e-3 / 1.3e-2
# at 0.5/1.5/2.5 GHz, roughly gpr_bem_mod's own order of magnitude; 8 GHz was
# 1.7 (170%) and is intentionally not gated below.
KDIFF_MAX_RELATIVE_ERROR = {0.5e9: 0.01, 1.5e9: 0.02, 2.5e9: 0.05}


def test_circle_kdiff_real_boundary(comparison_results, perfect_sampling) -> None:
    """``gpr_bem_kdiff`` against the Mie series, at every frequency, printed
    in full so the 8 GHz breakdown stays visible rather than hidden by a gate.
    """

    row = comparison_results["gpr_bem_kdiff"]
    print("\ngpr_bem_kdiff vs Mie (real compressed boundary unless --perfect-sampling)")
    for frequency_hz in FREQUENCIES_HZ:
        error = row["relative_error"][frequency_hz]
        print(f"  {frequency_hz / 1e9:>4.1f} GHz   error: {error:.4e}   cond: {row['condition_number'][frequency_hz]:.2e}")
        assert np.isfinite(error)
        threshold = KDIFF_MAX_RELATIVE_ERROR.get(frequency_hz)
        if threshold is not None:
            assert error < threshold, (
                f"gpr_bem_kdiff relative error {error:.4e} at {frequency_hz / 1e9:.1f} GHz "
                f"exceeds {threshold}"
            )
    print()


KERNEL_DIFF_MAX_RELATIVE_ERROR = 1.0e-4


def test_circle_kernel_diff_perfect_sampling(comparison_results) -> None:
    """The kernel-differenced quadrature (``solvers/kernel_diff_ref/``) against
    the Mie series, at the same N as ``gpr_bem_mod``, always on a perfect
    circle boundary.

    This isolates the trace/quadrature redesign itself (Issue 2 in
    ``docs/legacy/ibim_error_mitigation_literature_codex.md``) from the still-open
    irregular-node problem: same formulation, same N, same frequencies as
    ``gpr_bem_mod``, but with no finite trace offset anywhere. If this stays
    far more accurate than ``gpr_bem_mod`` at every frequency including the
    high-error band, that is direct evidence of how much of ``mod``'s error
    is the stand-off, not the geometry.
    """

    row = comparison_results["kernel_diff*"]
    modified = comparison_results["gpr_bem_mod"]
    print("\nkernel-differenced quadrature vs Mie (perfect circle sampling, always)")
    print(f"  {'freq (GHz)':>10}{'kernel_diff err':>18}{'mod err':>14}{'cond':>12}")
    for frequency_hz in FREQUENCIES_HZ:
        error = row["relative_error"][frequency_hz]
        mod_error = modified["relative_error"][frequency_hz]
        cond = row["condition_number"][frequency_hz]
        print(f"  {frequency_hz / 1e9:>10.1f}{error:>18.3e}{mod_error:>14.3e}{cond:>12.2e}")
        assert np.isfinite(error)
        assert error < KERNEL_DIFF_MAX_RELATIVE_ERROR, (
            f"kernel_diff relative error {error:.3e} at {frequency_hz / 1e9:.1f} GHz "
            f"exceeds {KERNEL_DIFF_MAX_RELATIVE_ERROR}"
        )
    print()


# Loose: this is a genuinely independent method (FDTD, 2nd-order, staircased
# circle) at ~29-49 cells/wavelength, not a high-accuracy oracle like the
# Nystrom reference. Its own discretisation error against the Mie series
# measured 1.0% / 2.3% / 1.9% at 0.5 / 1.5 / 2.5 GHz -- see
# docs/gprmax_reference_study.md. This threshold checks gprMax has no gross
# error (a sign flip, a units mistake), not that it matches mod's accuracy.
GPRMAX_MAX_RELATIVE_ERROR = 0.05


def test_circle_gprmax_cross_check(comparison_results) -> None:
    """An independent method (FDTD) should not contradict the BEM solvers.

    This is the point of carrying gprMax at all: Nystrom shares the Muller
    formulation with ``mod`` and cannot catch a formulation-level bug (a wrong
    sign in the jump relations, a misplaced factor). gprMax shares no code and
    no formulation with either BEM package, so agreement with it is evidence
    the physics is right, not just that the two BEM copies agree with each
    other.
    """

    gprmax = comparison_results.get("gprmax")
    if gprmax is None:
        pytest.skip(
            "gprMax cache not found for the current config values -- regenerate with "
            "solvers/gprmax_ref/run_case.py (see docs/gprmax_reference_study.md)"
        )

    modified = comparison_results["gpr_bem_mod"]
    print("\ngprMax cross-check (independent FDTD method, not a BIE)")
    for frequency_hz in VALIDATION_FREQUENCIES_HZ:
        gprmax_error = gprmax["relative_error"][frequency_hz]
        mod_error = modified["relative_error"][frequency_hz]
        print(
            f"  {frequency_hz / 1e9:>4.1f} GHz   gprmax vs Mie: {gprmax_error:.4f}   "
            f"mod vs Mie: {mod_error:.4f}"
        )
        assert np.isfinite(gprmax_error)
        assert gprmax_error < GPRMAX_MAX_RELATIVE_ERROR, (
            f"gprMax relative error {gprmax_error:.4f} at {frequency_hz / 1e9:.1f} GHz "
            f"exceeds {GPRMAX_MAX_RELATIVE_ERROR} -- check for a sign or units regression, "
            f"not just discretisation"
        )
    print()
