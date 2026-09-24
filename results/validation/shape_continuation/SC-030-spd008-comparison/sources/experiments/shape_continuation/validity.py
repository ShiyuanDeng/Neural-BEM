"""Measure where the first-order atlas stops predicting, per frequency and harmonic.

Two ladders are run at one geometry:

* a forward ladder along single shape harmonics, giving the linearization
  horizon `eps*(k, p)` - the RMS normal displacement at which `J h` stops
  describing the measured change in the data;
* an optimization ladder along band-restricted Gauss-Newton steps, giving the
  measured decrease against the quadratic model's promise.

Truth supplies data and never enters either ladder's model. Every displaced
curve carries a checked Fourier representation error relative to its own
displacement, so no horizon is read off an unresolved geometry.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from .atlas import Whitening, cell_at, harmonic_index
from .forward import Acquisition, Work, solve
from .geometry import grid_size
from .horizon import (default_storage_band, gauss_newton_direction,
                      linearization_error, step_quality, unit_direction)
from .inverse import Observation
from .run import fixture, provenance, relative
from .survey import acquisition_for, even_at_least, geometry_for, node_count


def cosine_column(harmonic):
    """Atlas column holding `cos(n s)`; `n = 0` is the constant column."""
    return 0 if harmonic == 0 else 2 * harmonic - 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scene", choices=("circle", "ellipse", "glider"), default="glider")
    parser.add_argument("--geometry", default="circle")
    parser.add_argument("--geometry-band", type=int, default=None,
                        help="Truncate a saved iterate to this band; the discarded tail is recorded.")
    parser.add_argument("--contrast", type=float, default=0.33)
    parser.add_argument("--wavenumbers", type=float, nargs="+",
                        default=[1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0])
    parser.add_argument("--harmonics", type=int, nargs="+",
                        default=[1, 2, 3, 5, 8, 12, 20, 30])
    parser.add_argument("--band-limits", type=int, nargs="+", default=[3, 6, 12, 24])
    parser.add_argument("--amplitude-min", type=float, default=1e-4)
    parser.add_argument("--amplitude-max", type=float, default=3e-1)
    parser.add_argument("--amplitude-count", type=int, default=12)
    parser.add_argument("--step-min", type=float, default=1e-3)
    parser.add_argument("--step-max", type=float, default=1.0)
    parser.add_argument("--step-count", type=int, default=10)
    parser.add_argument("--points-per-wavelength", type=float, default=30.0)
    parser.add_argument("--data-points-per-wavelength", type=float, default=60.0)
    parser.add_argument("--minimum-data-nodes", type=int, default=256)
    parser.add_argument("--noise-level", type=float, default=1e-3)
    parser.add_argument("--representation-tolerance", type=float, default=1e-3)
    parser.add_argument("--observation-tolerance", type=float, default=1e-7)
    parser.add_argument("--max-seconds", type=float, default=30000.0)
    parser.add_argument("--max-forwards", type=int, default=20000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        run(args)
    except Exception as exc:
        (args.output / "failure.json").write_text(
            json.dumps(dict(type=type(exc).__name__, message=str(exc)), indent=2) + "\n")
        raise


def run(args):
    started = perf_counter()
    (args.output / "manifest.json").write_text(json.dumps(
        dict(provenance(), arguments={k: str(v) for k, v in vars(args).items()}), indent=2) + "\n")
    truth = fixture(args.scene)
    shape, label = geometry_for(args.geometry, args.scene, args.geometry_band)
    shape.validate()
    band = max(args.harmonics + args.band_limits)
    perimeter = float(shape.nodes(grid_size(shape.band)).perimeter)
    truth_perimeter = float(truth.nodes(grid_size(truth.band)).perimeter)
    storage_band = default_storage_band(shape, band)
    whitening = Whitening("relative", args.noise_level)
    amplitudes = np.geomspace(args.amplitude_min, args.amplitude_max, args.amplitude_count)
    steps = np.geomspace(args.step_min, args.step_max, args.step_count)
    work = Work(max_forwards=args.max_forwards, max_seconds=args.max_seconds)
    data_work = Work(max_forwards=4 * len(args.wavenumbers) + 8, max_seconds=args.max_seconds)

    horizons, qualities, observation_checks, cells = [], [], [], []
    for wavenumber in args.wavenumbers:
        acquisition = acquisition_for(wavenumber, "paper")
        data_nodes = node_count(wavenumber, args.contrast, truth_perimeter,
                                args.data_points_per_wavelength, truth.band,
                                minimum=args.minimum_data_nodes)
        half = even_at_least(data_nodes / 2)
        coarse = solve(truth, wavenumber, args.contrast, acquisition, half, work=data_work).prediction
        fine = solve(truth, wavenumber, args.contrast, acquisition, data_nodes, work=data_work).prediction
        difference = relative(coarse, fine)
        observation_checks.append(dict(wavenumber=wavenumber, nodes=[half, data_nodes],
                                       relative_difference=difference))
        if difference > args.observation_tolerance:
            raise RuntimeError(f"Observation gate failed at k={wavenumber:g}: {difference:.3g}.")
        observation = Observation(float(wavenumber), acquisition, fine)
        # Every solve in one frequency's ladders uses the same quadrature, so a
        # finite difference never mixes two discretizations.
        nodes = max(node_count(wavenumber, args.contrast, perimeter,
                               args.points_per_wavelength, band),
                    even_at_least(2 * (storage_band + 1) + 2))
        cell = cell_at(shape, observation, args.contrast, band, nodes,
                       whitening=whitening, work=work)
        cells.append(cell)
        directions = {f"harmonic_{n}": unit_direction(band, cosine_column(n))
                      for n in args.harmonics}
        probes, state, jacobian = linearization_error(
            shape, wavenumber, args.contrast, acquisition, nodes, band, directions,
            amplitudes, storage_band=storage_band, work=work,
            tolerance=args.representation_tolerance)
        for probe in probes:
            horizons.append(dict(
                wavenumber=wavenumber, direction=probe.label,
                harmonic=int(probe.label.split("_")[1]), nodes=nodes,
                horizon_05=probe.horizon(0.05), horizon_10=probe.horizon(0.10),
                horizon_25=probe.horizon(0.25), order=probe.order(),
                achieved=probe.achieved.tolist(),
                relative_error=probe.relative_error.tolist(),
                linear_norm=probe.linear_norm.tolist(),
                representation_error=probe.representation_error.tolist(),
                failures=list(probe.failures)))
        # A Gauss-Newton step is a different direction for each declared band,
        # so its horizon is a property of the schedule, not only of the physics.
        gn_directions = {}
        for limit in args.band_limits:
            direction = gauss_newton_direction(cell, band_limit=limit)
            magnitude = np.linalg.norm(direction)
            if magnitude == 0:
                continue
            gn_directions[f"gn_band_{limit}"] = direction / magnitude
            quality = step_quality(shape, observation, args.contrast, nodes, band, cell,
                                   direction, steps, storage_band=storage_band, work=work,
                                   tolerance=args.representation_tolerance,
                                   label=f"gn_band_{limit}")
            qualities.append(dict(
                wavenumber=wavenumber, band_limit=limit, nodes=nodes,
                full_step_rms=float(np.linalg.norm(direction) / np.sqrt(perimeter)),
                steps=quality.steps.tolist(), achieved=quality.achieved.tolist(),
                predicted_decrease=quality.predicted_decrease.tolist(),
                actual_decrease=quality.actual_decrease.tolist(),
                ratio=np.where(np.isfinite(quality.ratio), quality.ratio, None).tolist(),
                whitened_misfit=cell.whitened_misfit))
        if gn_directions:
            gn_probes, _, _ = linearization_error(
                shape, wavenumber, args.contrast, acquisition, nodes, band, gn_directions,
                amplitudes, storage_band=storage_band, work=work,
                tolerance=args.representation_tolerance, state=state, jacobian=jacobian)
            for probe in gn_probes:
                horizons.append(dict(
                    wavenumber=wavenumber, direction=probe.label, harmonic=None, nodes=nodes,
                    horizon_05=probe.horizon(0.05), horizon_10=probe.horizon(0.10),
                    horizon_25=probe.horizon(0.25), order=probe.order(),
                    achieved=probe.achieved.tolist(),
                    relative_error=probe.relative_error.tolist(),
                    linear_norm=probe.linear_norm.tolist(),
                    representation_error=probe.representation_error.tolist(),
                    failures=list(probe.failures)))
        print(json.dumps(dict(wavenumber=wavenumber, nodes=nodes,
                              forwards=work.attempted,
                              horizon_10={h["direction"]: h["horizon_10"] for h in horizons
                                          if h["wavenumber"] == wavenumber})), flush=True)

    summary = dict(
        scene=args.scene, geometry=args.geometry, geometry_label=label,
        contrast=args.contrast, band=band, perimeter=perimeter,
        storage_band=storage_band, amplitudes=amplitudes.tolist(), steps=steps.tolist(),
        whitening=dict(kind=whitening.kind, level=whitening.level),
        observation_checks=observation_checks, horizons=horizons, step_quality=qualities,
        cells=[dict(wavenumber=c.wavenumber, relative_residual=c.relative_residual,
                    whitened_misfit=c.whitened_misfit, effective_rank=c.effective_rank(),
                    predicted_decrease=c.predicted_decrease()) for c in cells],
        work=work.summary(), data_work=data_work.summary(),
        elapsed_seconds=perf_counter() - started)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(dict(geometry_label=label, contrast=args.contrast,
                          forwards=work.attempted,
                          elapsed_seconds=summary["elapsed_seconds"]), indent=2))


if __name__ == "__main__":
    main()
