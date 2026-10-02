"""Passive full-space conductivity axis for the shape sensitivity atlas."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "solvers"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ordered_boundary import circle
from gpr_bem_kress.polarization import (
    passive_permittivity, passive_wavenumber,
    solve_polarized_transmission, polarized_shape_derivative,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/polarization")
    parser.add_argument("--nodes", type=int, default=192)
    parser.add_argument("--max-harmonic", type=int, default=40)
    args = parser.parse_args()
    if args.max_harmonic < 0 or args.nodes < 8 or args.nodes % 2 or args.nodes <= 2 * args.max_harmonic:
        parser.error("Use an even node count >=8 and greater than twice a nonnegative maximum harmonic.")
    args.output.mkdir(parents=True, exist_ok=True)
    radius = .2
    curve = circle((0, 0), radius).discretize(args.nodes)
    theta = curve.parameters
    harmonics = np.column_stack([np.ones(len(theta))] + [np.sqrt(2) * f(n * theta)
        for n in range(1, args.max_harmonic + 1) for f in (np.cos, np.sin)])
    def ring(radius, count, phase=0):
        angles = 2 * np.pi * np.arange(count) / count + phase
        return radius * np.column_stack([np.cos(angles), np.sin(angles)])
    sources, receivers = ring(.6, 16), ring(.8, 48, .017)
    frequencies = np.linspace(1e8, 1e9, 10)
    conductivities = [0., .001, .01, .05]
    spectra, vectors, rows = [], [], []
    started = time.perf_counter()
    for polarization in ("TM", "TE"):
        for frequency in frequencies:
            reference_scale = None
            for conductivity in conductivities:
                omega = 2 * np.pi * frequency
                ko, ki = passive_wavenumber(6, conductivity, omega), passive_wavenumber(12, 0, omega)
                ratio = 1 if polarization == "TM" else passive_permittivity(12, 0, omega) / passive_permittivity(6, conductivity, omega)
                forward = solve_polarized_transmission(curve, sources, receivers, ko, ki, normal_ratio=ratio)
                derivative = polarized_shape_derivative(forward, harmonics)
                complex_jacobian = derivative.reshape(harmonics.shape[1], -1).T
                real_jacobian = np.concatenate([complex_jacobian.real, complex_jacobian.imag])
                _, singular, vh = np.linalg.svd(real_jacobian, full_matrices=False)
                if reference_scale is None:
                    reference_scale = singular[0]
                row = dict(polarization=polarization, frequency_hz=frequency,
                    background_sigma_sm=conductivity, exterior_kR_real=ko.real * radius,
                    exterior_kR_imag=ko.imag * radius,
                    stable_relative_1e3=int(np.count_nonzero(singular >= .001 * singular[0])),
                    stable_fixed_lossless_floor=int(np.count_nonzero(singular >= .001 * reference_scale)),
                    largest_singular_value=float(singular[0]), lossless_largest_singular_value=float(reference_scale))
                rows.append(row)
                spectra.append(singular)
                vectors.append(vh)
    np.savez_compressed(args.output / "lossy_atlas.npz", singular_values=np.array(spectra),
        right_singular_vectors=np.array(vectors), normal_basis=harmonics)
    metadata = dict(radius_m=radius, target_epsr=12, target_sigma_sm=0,
        background_epsr=6, num_nodes=args.nodes, max_harmonic=args.max_harmonic,
        sources=16, receivers=48, source_radius_m=.6, receiver_radius_m=.8,
        coefficient_units="metres of normal displacement; RMS-normalized real Fourier basis",
        data_convention="real/imag stacked unweighted complex line-source data",
        threshold_note="Relative threshold renormalizes each spectrum; fixed threshold uses sigma1 at zero conductivity for the same frequency/polarization.",
        wall_seconds=time.perf_counter() - started, rows=rows)
    (args.output / "lossy_atlas.json").write_text(json.dumps(metadata, indent=2) + "\n")
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    for column, polarization in enumerate(("TM", "TE")):
        for conductivity in conductivities:
            subset = [row for row in rows if row["polarization"] == polarization and row["background_sigma_sm"] == conductivity]
            for axis, field in zip(axes[:, column], ("stable_relative_1e3", "stable_fixed_lossless_floor")):
                axis.plot(frequencies / 1e9, [r[field] for r in subset], marker="o", markersize=3,
                          label=f"{conductivity * 1000:g} mS/m")
                axis.grid(alpha=.25)
        axes[0, column].set_title(polarization)
        axes[1, column].set_xlabel("Frequency (GHz)")
    axes[0, 0].set_ylabel("Count above 0.001 × own σ₁")
    axes[1, 0].set_ylabel("Count above fixed zero-loss floor")
    axes[0, 1].legend(title="Background conductivity")
    figure.suptitle("Shape sensitivity in homogeneous lossy full space; R=0.2 m, εr=6/12")
    figure.tight_layout()
    figure.savefig(args.output / "lossy_stable_modes.png", dpi=170)
    plt.close(figure)
    print(json.dumps(dict(configurations=len(rows), wall_seconds=metadata["wall_seconds"],
        final_frequency=[r for r in rows if r["frequency_hz"] == frequencies[-1]]), indent=2))


if __name__ == "__main__":
    main()
