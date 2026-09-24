"""Measure the frequency x shape-harmonic atlas at one fixed geometry.

This driver answers structural questions, not inversion questions: at a
declared boundary it records what every available frequency says about every
shape harmonic, keeping the signed and off-diagonal information that a
sensitivity heatmap discards. Observations come from a synthetic truth and
pass their own N/2N gate; the atlas passes a separate one at spot frequencies.

Truth is used only to generate data and to label the figure. It never reaches
the atlas, which sees geometry, contrast, acquisition and data alone.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from .atlas import Whitening, build, cell_at, harmonic_index, orthonormal_normal_basis
from .forward import Acquisition, Work, solve
from .geometry import FourierCurve, grid_size
from .inverse import Observation
from .run import fixture, provenance, relative


def even_at_least(value):
    return 2 * int(np.ceil(value / 2))


def node_count(wavenumber, contrast, perimeter, points_per_wavelength, band, minimum=64):
    """Quadrature size from the shortest interior wavelength and the Fourier band."""
    largest = wavenumber * max(1.0, np.sqrt(contrast))
    return even_at_least(max(minimum, 2 * (band + 1),
                             points_per_wavelength * perimeter * largest / (2 * np.pi)))


def acquisition_for(wavenumber, policy):
    if policy == "paper":
        count = max(4, int(10 * wavenumber))
    else:
        count = int(policy)
    return Acquisition.ring(count, count)


def geometry_for(name, scene, band=None):
    """Resolve a geometry argument; an optional band truncates a saved iterate.

    A saved inverse endpoint carries every mode its stage stored, most of them
    numerical dust whose only effect is to force an enormous quadrature. The
    truncation is a declared choice, so the discarded tail is reported in the
    label rather than silently dropped.
    """
    if name == "circle":
        return FourierCurve.circle(1.0), "unit circle"
    if name == "truth":
        return fixture(scene), f"{scene} truth"
    path = Path(name)
    with np.load(path) as arrays:
        available = list(arrays.files)
        key = next((entry for entry in ("committed_shape", "shape") if entry in available),
                   sorted(available)[-1])
        shape = FourierCurve(arrays[key])
    label = f"saved iterate {path.parent.name}/{path.name}:{key}"
    if band is not None and band < shape.band:
        keep = np.abs(shape.modes) <= band
        tail = float(np.sqrt(np.sum(np.abs(shape.coefficients[~keep]) ** 2)))
        shape = FourierCurve(shape.coefficients[keep])
        label += f" truncated to band {band} (discarded tail {tail:.2e})"
    return shape, label


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scene", choices=("circle", "ellipse", "glider"), default="glider")
    parser.add_argument("--geometry", default="circle",
                        help="circle, truth, or a path to a saved .npz iterate.")
    parser.add_argument("--contrast", type=float, default=0.33)
    parser.add_argument("--k-start", type=float, default=1.0)
    parser.add_argument("--k-stop", type=float, default=20.0)
    parser.add_argument("--k-step", type=float, default=0.25)
    parser.add_argument("--band", type=int, default=60, help="Common shape-harmonic band.")
    parser.add_argument("--acquisition", default="paper",
                        help="'paper' for floor(10k) directions/receivers, or a fixed count.")
    parser.add_argument("--atlas-points-per-wavelength", type=float, default=30.0)
    parser.add_argument("--data-points-per-wavelength", type=float, default=60.0)
    parser.add_argument("--minimum-data-nodes", type=int, default=256)
    parser.add_argument("--minimum-atlas-nodes", type=int, default=128)
    parser.add_argument("--noise-level", type=float, default=1e-3)
    parser.add_argument("--whitening", default="relative",
                        choices=("relative", "absolute", "acquisition_neutral"))
    parser.add_argument("--gate-count", type=int, default=5,
                        help="Spot frequencies where the atlas itself is checked at N/2N.")
    parser.add_argument("--observation-tolerance", type=float, default=1e-7)
    parser.add_argument("--atlas-tolerance", type=float, default=1e-5)
    parser.add_argument("--max-seconds", type=float, default=20000.0)
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
    shape, label = geometry_for(args.geometry, args.scene)
    shape.validate()
    steps = round((args.k_stop - args.k_start) / args.k_step)
    waves = args.k_start + args.k_step * np.arange(steps + 1)
    truth_perimeter = float(truth.nodes(grid_size(truth.band)).perimeter)
    perimeter = float(shape.nodes(grid_size(shape.band)).perimeter)
    whitening = Whitening(args.whitening, args.noise_level)
    data_work = Work(max_forwards=4 * len(waves) + 8, max_seconds=args.max_seconds)
    atlas_work = Work(max_forwards=4 * len(waves) + 8, max_seconds=args.max_seconds)
    gates = set(np.linspace(0, len(waves) - 1, max(1, args.gate_count)).round().astype(int))

    records, cells, observation_checks, atlas_checks = [], [], [], []
    for index, wavenumber in enumerate(waves):
        acquisition = acquisition_for(wavenumber, args.acquisition)
        data_nodes = node_count(wavenumber, args.contrast, truth_perimeter,
                                args.data_points_per_wavelength, truth.band,
                                minimum=args.minimum_data_nodes)
        half = even_at_least(data_nodes / 2)
        coarse = solve(truth, wavenumber, args.contrast, acquisition, half, work=data_work).prediction
        fine = solve(truth, wavenumber, args.contrast, acquisition, data_nodes, work=data_work).prediction
        difference = relative(coarse, fine)
        observation_checks.append(dict(wavenumber=float(wavenumber), nodes=[half, data_nodes],
                                       relative_difference=difference))
        if difference > args.observation_tolerance:
            raise RuntimeError(f"Observation gate failed at k={wavenumber:g}: {difference:.3g}.")
        observation = Observation(float(wavenumber), acquisition, fine)
        atlas_nodes = node_count(wavenumber, args.contrast, perimeter,
                                 args.atlas_points_per_wavelength, max(shape.band, args.band),
                                 minimum=args.minimum_atlas_nodes)
        cell = cell_at(shape, observation, args.contrast, args.band, atlas_nodes,
                       whitening=whitening, work=atlas_work, keep_selection=True)
        cells.append(cell)
        if index in gates:
            fine_cell = cell_at(shape, observation, args.contrast, args.band, 2 * atlas_nodes,
                                whitening=whitening, work=atlas_work)
            check = dict(wavenumber=float(wavenumber), nodes=[atlas_nodes, 2 * atlas_nodes],
                         sensitivity_relative=relative(cell.sensitivity, fine_cell.sensitivity),
                         gradient_relative=relative(cell.gradient, fine_cell.gradient),
                         block_relative=relative(cell.gauss_newton, fine_cell.gauss_newton))
            # At a geometry that already fits the data the residual is solver
            # noise, so its N/2N ratio says nothing; the gradient check is then
            # reported but excluded from the verdict.
            check["gradient_meaningful"] = cell.relative_residual > 1e-6
            required = [check["sensitivity_relative"], check["block_relative"]]
            if check["gradient_meaningful"]:
                required.append(check["gradient_relative"])
            check["passed"] = max(required) <= args.atlas_tolerance
            atlas_checks.append(check)
        records.append(dict(wavenumber=float(wavenumber), atlas_nodes=atlas_nodes,
                            data_nodes=data_nodes, directions=len(acquisition.directions),
                            receivers=len(acquisition.receivers), sigma=cell.sigma,
                            relative_residual=cell.relative_residual,
                            whitened_misfit=cell.whitened_misfit,
                            effective_rank=cell.effective_rank(),
                            participation_rank=cell.participation_rank(),
                            predicted_decrease=cell.predicted_decrease(),
                            top_eigenvalue=float(cell.eigenvalues[0])))
        print(json.dumps(records[-1]), flush=True)

    harmonics = harmonic_index(args.band)
    np.savez_compressed(
        args.output / "atlas.npz", wavenumbers=waves, harmonics=harmonics,
        sensitivity=np.array([c.sensitivity for c in cells]),
        gradient=np.array([c.gradient for c in cells]),
        eigenvalues=np.array([c.eigenvalues for c in cells]),
        leakage=np.array([c.leakage for c in cells]),
        blocks=np.array([c.gauss_newton for c in cells], dtype=np.float32),
        top_eigenvector=np.array([c.eigenvectors[:, 0] for c in cells]),
        sigma=np.array([c.sigma for c in cells]),
        geometry=shape.coefficients, truth=truth.coefficients)
    summary = dict(
        scene=args.scene, geometry=args.geometry, geometry_label=label,
        contrast=args.contrast, band=args.band, perimeter=perimeter,
        truth_perimeter=truth_perimeter, acquisition=args.acquisition,
        whitening=dict(kind=whitening.kind, level=whitening.level),
        wavenumbers=waves.tolist(), stages=records,
        observation_checks=observation_checks, atlas_checks=atlas_checks,
        atlas_gate_passed=all(c["passed"] for c in atlas_checks),
        data_work=data_work.summary(), atlas_work=atlas_work.summary(),
        elapsed_seconds=perf_counter() - started)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in
                      ("geometry_label", "contrast", "atlas_gate_passed", "elapsed_seconds")}, indent=2))


if __name__ == "__main__":
    main()
