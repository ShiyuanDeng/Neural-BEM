#!/usr/bin/env python
"""Run gprMax reference cases and cache calibrated scattered fields.

Must be invoked with the ``gprMax`` conda environment's Python, e.g.::

    /home/drdeng/miniconda3/envs/gprMax/bin/python \
        solvers/gprmax_ref/run_case.py --target-shape circle \
        --frequencies 0.5e9 1.5e9 2.5e9 4e9 6e9 8e9

The default ``--frequency-mode harmonic`` writes one cache entry per requested
frequency, each a genuinely single-frequency FDTD run: the source is gprMax's
continuous-sine ``contsine`` waveform driven at exactly that frequency, not a
broadband pulse read off by DFT. See ``docs/gprmax_reference_study.md``
(2026-09-01 update) for the run-length/settling-time model and why this
replaced the broadband default -- it makes ``wall_clock_seconds`` comparable
to a BEM forward solve at one frequency. ``--frequency-mode scaled`` is the
older per-frequency mode: a Ricker pulse centered on that frequency and a
cell size chosen to keep at least ``--cells-per-wavelength`` samples per
background-medium phase wavelength, capped by ``--cell-size`` so low-frequency
curved-target staircasing does not get worse; phasor read off by DFT over the
whole run. ``--frequency-mode sweep`` regenerates the oldest one-broadband-run
cache format. All three modes size the cell the same way and share the same
cache-key/lookup machinery in ``cache_io.py``, so old cache entries are never
invalidated by this default change -- a lookup just prefers a harmonic entry
when one exists and falls back otherwise.

Each cached frequency still needs two FDTD runs: with the target and without.
Subtracting their time-domain fields at the receiver gives the scattered field
in the same *representation* the BEM solvers report, without ever having to
derive gprMax's Hertzian-dipole source-current normalisation, cell-size
scaling, or mesh-dispersion phase error by hand. Instead, the background-only
run is compared against the closed-form incident field ``0.25j * H_0^(1)(k
|Tx-Rx|)`` at the requested frequency, which pins down a complex calibration
factor; the same factor is then applied to the target run's scattered signal.
Because both runs share the source, the domain, the cell size, and the
propagation path length, this calibration cancels the FDTD-specific unknowns
and leaves only the genuine FDTD discretisation error (staircasing for
curved/voxelized targets, zero staircasing for a grid-aligned square, grid
dispersion along the scattered path, PML reflection) -- exactly what this
reference is meant to measure.

Only one representative Tx/Rx pair is simulated. For the circle target, the
shape is rotationally symmetric about its center and the ring scan in
``pytest/solver_comparisons/test_circle_comparison.py`` is literally that pair
rotated around the center, so every pair on the ring has the identical
scattered field (this is confirmed to 1e-16 by the Fourier-Bessel series, not
assumed). The square target only has 4-fold symmetry, so
``pytest/solver_comparisons/test_square_comparison.py``
compares this single pair against the matching index (angle 0) of its own
ring scan only, not the whole ring. Ellipse, star, and two-circle targets use
the same index-0 convention in their comparison tests.

Requires ``h5py``, present in the ``gprMax`` environment already.
"""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for config

import cache_io  # noqa: E402
from build_scene import build_geometry, render_scene  # noqa: E402

DEFAULT_GPRMAX_CHECKOUT = "/home/drdeng/gprMax"


def _hankel0(k: complex, r: float) -> complex:
    from scipy.special import hankel1

    return 0.25j * hankel1(0, k * r)


def _run_gprmax(inputfile: Path) -> None:
    from gprMax.gprMax import api

    api(str(inputfile), n=1)


def _read_receiver(outputfile: Path) -> tuple[np.ndarray, float]:
    import h5py

    with h5py.File(outputfile, "r") as handle:
        dt = float(handle.attrs["dt"])
        field = np.asarray(handle["/rxs/rx1/Ez"], dtype=float)
    return field, dt


def _spectrum(signal: np.ndarray, dt: float, angular_frequencies: np.ndarray) -> np.ndarray:
    """``F(w) = dt * sum_n f(t_n) exp(+i w t_n)``, matching the sign convention
    documented in ``solvers/gpr_bem_ref/waveforms.py``."""

    time = dt * np.arange(signal.size)
    phase = np.exp(1j * np.outer(angular_frequencies, time))
    return dt * (phase @ signal)


def run(
    *,
    target_shape: str,
    target_size: float,
    target_parameters: dict[str, float | int] | None = None,
    standoff: float,
    tx_rx_offset: float,
    sand_epsr: float,
    sand_sigma: float,
    plastic_epsr: float,
    plastic_sigma: float,
    eps0: float,
    mu0: float,
    frequencies_hz: list[float],
    cell_size: float,
    waveform: str,
    center_frequency: float,
    time_window: float,
    pml_cells: int,
    gprmax_checkout: str,
    keep_scratch: bool,
    extraction_seconds: float | None = None,
) -> Path:
    # Built the same way test code looks results up (cache_io.build_params), so
    # the two can never drift out of sync with each other.
    params = cache_io.build_params(
        target_shape=target_shape,
        target_size=target_size,
        target_parameters=target_parameters,
        standoff=standoff,
        tx_rx_offset=tx_rx_offset,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        plastic_epsr=plastic_epsr,
        plastic_sigma=plastic_sigma,
        eps0=eps0,
        mu0=mu0,
        frequencies_hz=frequencies_hz,
        cell_size=cell_size,
        waveform=waveform,
        center_frequency=center_frequency,
        time_window=time_window,
        pml_cells=pml_cells,
    )

    geometry = build_geometry(
        target_shape=target_shape,
        target_size=target_size,
        target_parameters=target_parameters,
        standoff=standoff,
        tx_rx_offset=tx_rx_offset,
        cell_size=cell_size,
        pml_cells=pml_cells,
    )

    scratch = Path(tempfile.mkdtemp(prefix="gprmax_ref_"))
    sys.path.insert(0, gprmax_checkout)

    try:
        started = time.perf_counter()
        results: dict[str, tuple[np.ndarray, float]] = {}
        for variant, include_target in (("background", False), ("target", True)):
            scene_text = render_scene(
                geometry,
                sand_epsr=sand_epsr,
                sand_sigma=sand_sigma,
                plastic_epsr=plastic_epsr,
                plastic_sigma=plastic_sigma,
                waveform=waveform,
                center_frequency=center_frequency,
                time_window=time_window,
                title=f"penetrable {target_shape}, {variant}",
                include_target=include_target,
            )
            inputfile = scratch / f"{variant}.in"
            inputfile.write_text(scene_text)
            _run_gprmax(inputfile)
            results[variant] = _read_receiver(scratch / f"{variant}.out")
        elapsed = time.perf_counter() - started

        angular_frequencies = 2.0 * np.pi * np.asarray(sorted(frequencies_hz), dtype=float)
        background_signal, dt_bg = results["background"]
        target_signal, dt_tg = results["target"]
        assert dt_bg == dt_tg, "background and target runs must share dt"
        assert background_signal.size == target_signal.size, (
            "background and target runs must share the number of iterations"
        )
        num_iterations_run = int(background_signal.size)

        if extraction_seconds is not None:
            # Harmonic (contsine) runs: drop the transit/ramp/reflection
            # transient and fit the phasor from the trailing steady-state
            # window only. Slicing both signals identically re-zeroes their
            # time origin by the same amount, which introduces the same
            # exp(-i*w*t0) factor into both spectra -- it cancels exactly in
            # the calibration ratio below, so this needs no other adjustment.
            window_samples = max(1, min(background_signal.size, int(round(extraction_seconds / dt_bg))))
            background_signal = background_signal[-window_samples:]
            target_signal = target_signal[-window_samples:]

        background_spectrum = _spectrum(background_signal, dt_bg, angular_frequencies)
        target_spectrum = _spectrum(target_signal, dt_bg, angular_frequencies)

        chord = math.dist(geometry.tx, geometry.rx)
        sand_material_wavenumber = []
        for angular_frequency in angular_frequencies:
            complex_epsr = sand_epsr + sand_sigma / (1j * angular_frequency * eps0)
            k_sand = angular_frequency * np.sqrt(mu0 * eps0 * complex_epsr)
            sand_material_wavenumber.append(k_sand)
        sand_material_wavenumber = np.asarray(sand_material_wavenumber)

        analytic_incident = np.array(
            [_hankel0(k, chord) for k in sand_material_wavenumber], dtype=complex
        )
        calibration = analytic_incident / background_spectrum
        scattered_calibrated = calibration * (target_spectrum - background_spectrum)

        result = {
            "frequencies_hz": sorted(frequencies_hz),
            "scattered_real": scattered_calibrated.real.tolist(),
            "scattered_imag": scattered_calibrated.imag.tolist(),
            "tx": list(geometry.tx),
            "rx": list(geometry.rx),
            "target_center": list(geometry.target_center),
            "domain": [geometry.domain_x, geometry.domain_y],
            "num_iterations": num_iterations_run,
            "dt": dt_bg,
            "wall_clock_seconds": elapsed,
            "extraction_seconds": extraction_seconds,
        }
        path = cache_io.save(params, result)
        print(f"cached to {path}")
        for f, re, im in zip(result["frequencies_hz"], result["scattered_real"], result["scattered_imag"]):
            print(f"  {f/1e9:5.2f} GHz  scattered = {re:+.6e} {im:+.6e}j")
        return path
    finally:
        if keep_scratch:
            print(f"scratch kept at {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


def run_frequency_scaled_sweep(
    *,
    target_shape: str,
    target_size: float,
    target_parameters: dict[str, float | int] | None = None,
    standoff: float,
    tx_rx_offset: float,
    sand_epsr: float,
    sand_sigma: float,
    plastic_epsr: float,
    plastic_sigma: float,
    eps0: float,
    mu0: float,
    frequencies_hz: list[float],
    max_cell_size: float,
    cells_per_wavelength: float,
    waveform: str,
    center_frequency_scale: float,
    time_window: float,
    pml_cells: int,
    gprmax_checkout: str,
    keep_scratch: bool,
) -> list[Path]:
    """Run and cache one independently tuned gprMax simulation per frequency."""

    paths: list[Path] = []
    base_params = cache_io.build_params(
        target_shape=target_shape,
        target_size=target_size,
        target_parameters=target_parameters,
        standoff=standoff,
        tx_rx_offset=tx_rx_offset,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        plastic_epsr=plastic_epsr,
        plastic_sigma=plastic_sigma,
        eps0=eps0,
        mu0=mu0,
        frequencies_hz=frequencies_hz,
        cell_size=max_cell_size,
        waveform=waveform,
        center_frequency=cache_io.DEFAULT_CENTER_FREQUENCY,
        time_window=time_window,
        pml_cells=pml_cells,
    )
    frequency_params = cache_io.build_frequency_scaled_params_from_base
    for frequency_hz in sorted(base_params["frequencies_hz"]):
        params = frequency_params(
            base_params,
            frequency_hz,
            cells_per_wavelength=cells_per_wavelength,
            max_cell_size=max_cell_size,
            center_frequency_scale=center_frequency_scale,
        )
        cell_size = float(params["cell_size"])
        center_frequency = float(params["center_frequency"])
        print(
            f"\nfrequency-scaled run: {frequency_hz / 1e9:.3g} GHz, "
            f"dx={cell_size * 1.0e3:.3g} mm, Ricker fc={center_frequency / 1e9:.3g} GHz"
        )
        paths.append(
            run(
                target_shape=target_shape,
                target_size=target_size,
                target_parameters=target_parameters,
                standoff=standoff,
                tx_rx_offset=tx_rx_offset,
                sand_epsr=sand_epsr,
                sand_sigma=sand_sigma,
                plastic_epsr=plastic_epsr,
                plastic_sigma=plastic_sigma,
                eps0=eps0,
                mu0=mu0,
                frequencies_hz=[float(frequency_hz)],
                cell_size=cell_size,
                waveform=waveform,
                center_frequency=center_frequency,
                time_window=time_window,
                pml_cells=pml_cells,
                gprmax_checkout=gprmax_checkout,
                keep_scratch=keep_scratch,
            )
        )
    print("\nfrequency-scaled cache entries:")
    for path in paths:
        print(f"  {path}")
    return paths


def run_harmonic_sweep(
    *,
    target_shape: str,
    target_size: float,
    target_parameters: dict[str, float | int] | None = None,
    standoff: float,
    tx_rx_offset: float,
    sand_epsr: float,
    sand_sigma: float,
    plastic_epsr: float,
    plastic_sigma: float,
    eps0: float,
    mu0: float,
    frequencies_hz: list[float],
    max_cell_size: float,
    cells_per_wavelength: float,
    ramp_periods: float,
    settle_transit_multiplier: float,
    extraction_periods: float,
    transit_safety: float,
    pml_cells: int,
    gprmax_checkout: str,
    keep_scratch: bool,
) -> list[Path]:
    """Run and cache one genuinely single-frequency (``contsine``) gprMax
    simulation per frequency, instead of a broadband Ricker pulse post-
    processed by DFT. Each run solves exactly the frequency it is asked for:
    the source is a continuous sine wave at that frequency, the domain/cell
    size are still scaled the same way as the Ricker ``scaled`` mode, and the
    time window is only as long as needed for the field to settle into
    steady state plus a trailing extraction window (see
    ``cache_io.harmonic_time_window``). This makes ``wall_clock_seconds``
    directly comparable to a BEM forward solve at that one frequency, rather
    than the cost of a wideband transient that happens to cover it.
    """

    paths: list[Path] = []
    base_params = cache_io.build_params(
        target_shape=target_shape,
        target_size=target_size,
        target_parameters=target_parameters,
        standoff=standoff,
        tx_rx_offset=tx_rx_offset,
        sand_epsr=sand_epsr,
        sand_sigma=sand_sigma,
        plastic_epsr=plastic_epsr,
        plastic_sigma=plastic_sigma,
        eps0=eps0,
        mu0=mu0,
        frequencies_hz=frequencies_hz,
        cell_size=max_cell_size,
    )
    for frequency_hz in sorted(base_params["frequencies_hz"]):
        params = cache_io.build_harmonic_params_from_base(
            base_params,
            frequency_hz,
            cells_per_wavelength=cells_per_wavelength,
            max_cell_size=max_cell_size,
            ramp_periods=ramp_periods,
            settle_transit_multiplier=settle_transit_multiplier,
            extraction_periods=extraction_periods,
            transit_safety=transit_safety,
        )
        cell_size = float(params["cell_size"])
        time_window = float(params["time_window"])
        extraction_seconds = cache_io.harmonic_extraction_seconds(
            frequency_hz, extraction_periods=extraction_periods
        )
        print(
            f"\nharmonic run: {frequency_hz / 1e9:.3g} GHz, dx={cell_size * 1.0e3:.3g} mm, "
            f"time_window={time_window * 1.0e9:.3g} ns, extraction window={extraction_seconds * 1.0e9:.3g} ns"
        )
        path = run(
            target_shape=target_shape,
            target_size=target_size,
            target_parameters=target_parameters,
            standoff=standoff,
            tx_rx_offset=tx_rx_offset,
            sand_epsr=sand_epsr,
            sand_sigma=sand_sigma,
            plastic_epsr=plastic_epsr,
            plastic_sigma=plastic_sigma,
            eps0=eps0,
            mu0=mu0,
            frequencies_hz=[float(frequency_hz)],
            cell_size=cell_size,
            waveform=cache_io.DEFAULT_HARMONIC_WAVEFORM,
            center_frequency=float(frequency_hz),
            time_window=time_window,
            pml_cells=pml_cells,
            gprmax_checkout=gprmax_checkout,
            keep_scratch=keep_scratch,
            extraction_seconds=extraction_seconds,
        )
        cached = cache_io.load(params)
        print(f"  wall clock: {cached['result']['wall_clock_seconds']:.2f} s")
        paths.append(path)
    print("\nharmonic cache entries:")
    for path in paths:
        print(f"  {path}")
    return paths


def _default_frequencies() -> list[float]:
    return [0.5e9, 1.5e9, 2.5e9, 4.0e9, 6.0e9, 8.0e9]


def _target_from_args(args: argparse.Namespace) -> tuple[float, dict[str, float | int] | None]:
    if args.target_shape == "ellipse":
        semi_major = float(args.ellipse_semi_major)
        semi_minor = float(args.ellipse_semi_minor)
        return max(semi_major, semi_minor), {"semi_major": semi_major, "semi_minor": semi_minor}
    if args.target_shape == "star":
        mean_radius = float(args.star_mean_radius)
        amplitude = float(args.star_amplitude)
        lobes = int(args.star_lobes)
        return mean_radius * (1.0 + abs(amplitude)), {
            "mean_radius": mean_radius,
            "amplitude": amplitude,
            "lobes": lobes,
        }
    if args.target_shape == "two_circles":
        radius = float(args.two_circle_radius)
        separation = float(args.two_circle_separation)
        return 0.5 * separation + radius, {
            "circle_centers": [[-0.5 * separation, 0.0], [0.5 * separation, 0.0]],
            "circle_radii": [radius, radius],
        }
    return float(args.target_size), None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-shape",
        type=str,
        choices=("circle", "square", "ellipse", "star", "two_circles"),
        default="circle",
    )
    parser.add_argument("--target-size", type=float, default=0.05)
    parser.add_argument("--ellipse-semi-major", type=float, default=0.07)
    parser.add_argument("--ellipse-semi-minor", type=float, default=0.035)
    parser.add_argument("--star-mean-radius", type=float, default=0.05)
    parser.add_argument("--star-amplitude", type=float, default=0.25)
    parser.add_argument("--star-lobes", type=int, default=5)
    parser.add_argument("--two-circle-radius", type=float, default=0.035)
    parser.add_argument("--two-circle-separation", type=float, default=0.14)
    parser.add_argument("--standoff", type=float, default=0.30)
    parser.add_argument("--tx-rx-offset", type=float, default=0.06)
    parser.add_argument("--sand-epsr", type=float, default=6.0)
    parser.add_argument("--sand-sigma", type=float, default=0.0)
    parser.add_argument("--plastic-epsr", type=float, default=3.0)
    parser.add_argument("--plastic-sigma", type=float, default=0.0)
    parser.add_argument("--eps0", type=float, default=8.854187817e-12)
    parser.add_argument("--mu0", type=float, default=4 * math.pi * 1e-7)
    parser.add_argument("--frequencies", type=float, nargs="+", default=None)
    parser.add_argument(
        "--frequency-mode",
        type=str,
        choices=("harmonic", "scaled", "sweep"),
        default="harmonic",
        help=(
            "harmonic (default): one cache/run per frequency, source is a continuous "
            "sine wave at exactly that frequency (gprMax 'contsine'), phasor fit from the "
            "trailing steady-state window -- see docs/gprmax_reference_study.md. "
            "scaled: legacy one cache/run per frequency with dx based on background "
            "wavelength and a broadband Ricker pulse centered on that frequency, phasor "
            "read off by DFT over the whole run. sweep: legacy one broadband cache "
            "covering every requested frequency in one run."
        ),
    )
    parser.add_argument(
        "--harmonic-ramp-periods",
        type=float,
        default=cache_io.DEFAULT_HARMONIC_RAMP_PERIODS,
        help="Periods for contsine's built-in source ramp (harmonic mode only).",
    )
    parser.add_argument(
        "--harmonic-settle-transit-multiplier",
        type=float,
        default=cache_io.DEFAULT_HARMONIC_SETTLE_TRANSIT_MULTIPLIER,
        help=(
            "Extra settling margin for secondary/PML reflections, as a multiple of the "
            "direct transit *time* (not periods -- reflections travel a roughly frequency-"
            "independent physical distance) (harmonic mode only)."
        ),
    )
    parser.add_argument(
        "--harmonic-extraction-periods",
        type=float,
        default=cache_io.DEFAULT_HARMONIC_EXTRACTION_PERIODS,
        help="Trailing periods used to fit the steady-state phasor (harmonic mode only).",
    )
    parser.add_argument(
        "--harmonic-transit-safety",
        type=float,
        default=cache_io.DEFAULT_HARMONIC_TRANSIT_SAFETY,
        help="Safety factor on the domain-diagonal transit-time estimate (harmonic mode only).",
    )
    parser.add_argument(
        "--cell-size",
        type=float,
        default=cache_io.DEFAULT_CELL_SIZE,
        help="Legacy sweep dx, or the maximum dx allowed in scaled mode.",
    )
    parser.add_argument(
        "--cells-per-wavelength",
        type=float,
        default=cache_io.DEFAULT_FREQUENCY_SCALED_CELLS_PER_WAVELENGTH,
        help="Minimum background-medium cells per wavelength in scaled mode.",
    )
    parser.add_argument(
        "--center-frequency-scale",
        type=float,
        default=1.0,
        help="Ricker center frequency divided by target frequency in scaled mode.",
    )
    parser.add_argument("--waveform", type=str, default="ricker")
    parser.add_argument("--center-frequency", type=float, default=1.5e9)
    parser.add_argument("--time-window", type=float, default=15e-9)
    parser.add_argument("--pml-cells", type=int, default=12)
    parser.add_argument("--gprmax-checkout", type=str, default=DEFAULT_GPRMAX_CHECKOUT)
    parser.add_argument("--keep-scratch", action="store_true")
    args = parser.parse_args()
    target_size, target_parameters = _target_from_args(args)
    frequencies_hz = args.frequencies or _default_frequencies()

    if args.frequency_mode == "harmonic":
        run_harmonic_sweep(
            target_shape=args.target_shape,
            target_size=target_size,
            target_parameters=target_parameters,
            standoff=args.standoff,
            tx_rx_offset=args.tx_rx_offset,
            sand_epsr=args.sand_epsr,
            sand_sigma=args.sand_sigma,
            plastic_epsr=args.plastic_epsr,
            plastic_sigma=args.plastic_sigma,
            eps0=args.eps0,
            mu0=args.mu0,
            frequencies_hz=frequencies_hz,
            max_cell_size=args.cell_size,
            cells_per_wavelength=args.cells_per_wavelength,
            ramp_periods=args.harmonic_ramp_periods,
            settle_transit_multiplier=args.harmonic_settle_transit_multiplier,
            extraction_periods=args.harmonic_extraction_periods,
            transit_safety=args.harmonic_transit_safety,
            pml_cells=args.pml_cells,
            gprmax_checkout=args.gprmax_checkout,
            keep_scratch=args.keep_scratch,
        )
    elif args.frequency_mode == "scaled":
        run_frequency_scaled_sweep(
            target_shape=args.target_shape,
            target_size=target_size,
            target_parameters=target_parameters,
            standoff=args.standoff,
            tx_rx_offset=args.tx_rx_offset,
            sand_epsr=args.sand_epsr,
            sand_sigma=args.sand_sigma,
            plastic_epsr=args.plastic_epsr,
            plastic_sigma=args.plastic_sigma,
            eps0=args.eps0,
            mu0=args.mu0,
            frequencies_hz=frequencies_hz,
            max_cell_size=args.cell_size,
            cells_per_wavelength=args.cells_per_wavelength,
            waveform=args.waveform,
            center_frequency_scale=args.center_frequency_scale,
            time_window=args.time_window,
            pml_cells=args.pml_cells,
            gprmax_checkout=args.gprmax_checkout,
            keep_scratch=args.keep_scratch,
        )
    else:
        run(
            target_shape=args.target_shape,
            target_size=target_size,
            target_parameters=target_parameters,
            standoff=args.standoff,
            tx_rx_offset=args.tx_rx_offset,
            sand_epsr=args.sand_epsr,
            sand_sigma=args.sand_sigma,
            plastic_epsr=args.plastic_epsr,
            plastic_sigma=args.plastic_sigma,
            eps0=args.eps0,
            mu0=args.mu0,
            frequencies_hz=frequencies_hz,
            cell_size=args.cell_size,
            waveform=args.waveform,
            center_frequency=args.center_frequency,
            time_window=args.time_window,
            pml_cells=args.pml_cells,
            gprmax_checkout=args.gprmax_checkout,
            keep_scratch=args.keep_scratch,
        )


if __name__ == "__main__":
    main()
