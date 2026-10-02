"""CPU TE/lossy validation against circle series and normal-deformation FD."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "solvers"))

import numpy as np
from scipy.special import hankel1, h1vp, jv, jvp
from ordered_boundary import circle, ellipse, PeriodicCurve2D
from gpr_bem_kress.polarization import (
    passive_wavenumber, passive_permittivity, solve_polarized_transmission,
    polarized_shape_derivative,
)


def ring(radius, count, phase=0):
    angles = 2 * np.pi * np.arange(count) / count + phase
    return radius * np.column_stack([np.cos(angles), np.sin(angles)])


def circle_series(radius, sources, receivers, ko, ki, ratio=1):
    """Independent separation of variables; exterior scattered line-source field."""
    order = int(np.ceil(max(abs(ko * radius), abs(ki * radius)))) + 35
    modes = np.arange(-order, order + 1)
    jo, ji = jv(modes, ko * radius), jv(modes, ki * radius)
    jop, jip = ko * jvp(modes, ko * radius), ki * jvp(modes, ki * radius)
    ho, hop = hankel1(modes, ko * radius), ko * h1vp(modes, ko * radius)
    scattering = (jip * jo - ratio * jop * ji) / (ratio * hop * ji - jip * ho)
    source_radius = np.linalg.norm(sources, axis=1)
    source_angle = np.arctan2(sources[:, 1], sources[:, 0])
    receiver_radius = np.linalg.norm(receivers, axis=1)
    receiver_angle = np.arctan2(receivers[:, 1], receivers[:, 0])
    coefficients = 0.25j * hankel1(modes[None, :], ko * source_radius[:, None])
    coefficients *= np.exp(-1j * source_angle[:, None] * modes)
    waves = hankel1(modes[:, None], ko * receiver_radius[None, :])
    waves *= np.exp(1j * modes[:, None] * receiver_angle[None, :])
    return (coefficients * scattering) @ waves


def deform(curve, normal_velocity, step):
    displacement = normal_velocity[:, None] * curve.normals
    modes = np.fft.fftfreq(curve.num_nodes, 1 / curve.num_nodes)
    modes[curve.num_nodes // 2] = 0
    coefficients = np.fft.fft(displacement, axis=0)
    jets = [np.fft.ifft(coefficients * (1j * modes[:, None]) ** order, axis=0).real
            for order in (1, 2)]
    return PeriodicCurve2D(curve.component_id, curve.parameters,
                          curve.points + step * displacement,
                          curve.first_derivatives + step * jets[0],
                          curve.second_derivatives + step * jets[1])


def relative_error(value, reference):
    return float(np.linalg.norm(value - reference) / np.linalg.norm(reference))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/polarization")
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    sources, receivers = ring(3, 5), ring(4, 32, .07)
    convergence = []
    for kr in (1, 5, 15):
        reference = circle_series(1, sources, receivers, kr, 2 * kr, 4)
        for nodes in (64, 96, 128, 192, 256):
            result = solve_polarized_transmission(circle((0, 0), 1).discretize(nodes),
                sources, receivers, kr, 2 * kr, normal_ratio=4)
            convergence.append(dict(kR=kr, nodes=nodes,
                relative_l2=relative_error(result.scattered_receiver, reference),
                max_error_over_max_reference=float(np.max(abs(result.scattered_receiver - reference)) / np.max(abs(reference))),
                linear_residual=result.relative_residual))
    derivative_rows = []
    rng = np.random.default_rng(20261002)
    for shape, geometry in (("circle", circle((0, 0), 1)), ("ellipse", ellipse((0, 0), 1, .75))):
        curve = geometry.discretize(192)
        base = solve_polarized_transmission(curve, sources, receivers, 5, 10, normal_ratio=4)
        theta = curve.parameters
        harmonics = np.column_stack([np.ones(len(theta))] + [f(n * theta) for n in range(1, 9) for f in (np.cos, np.sin)])
        directions = harmonics @ rng.normal(size=(harmonics.shape[1], 10))
        directions /= np.max(abs(directions), axis=0)
        analytic = polarized_shape_derivative(base, directions)
        for index in range(10):
            errors = []
            for step in (2e-4, 1e-4, 5e-5):
                fields = [solve_polarized_transmission(deform(curve, directions[:, index], sign * step),
                    sources, receivers, 5, 10, normal_ratio=4).scattered_receiver for sign in (1, -1)]
                fd = (fields[0] - fields[1]) / (2 * step)
                errors.append(relative_error(analytic[index], fd))
            derivative_rows.append(dict(shape=shape, direction=index,
                fd_steps=[2e-4, 1e-4, 5e-5], relative_errors=errors))
    lossy = []
    for freq in (1e8, 5e8, 1e9):
        omega = 2 * np.pi * freq
        for conductivity in (0, .001, .01, .05):
            ko, ki = passive_wavenumber(6, conductivity, omega), passive_wavenumber(12, .005, omega)
            for polarization in ("TM", "TE"):
                ratio = 1 if polarization == "TM" else passive_permittivity(12, .005, omega) / passive_permittivity(6, conductivity, omega)
                curve = circle((0, 0), .2).discretize(192)
                source, receiver = sources * .2, receivers * .2
                result = solve_polarized_transmission(curve, source, receiver, ko, ki, normal_ratio=ratio)
                reference = circle_series(.2, source, receiver, ko, ki, ratio)
                theta = curve.parameters
                direction = np.cos(3 * theta) + .3 * np.sin(5 * theta)
                analytic = polarized_shape_derivative(result, direction)[0]
                step = 1e-6
                fields = [solve_polarized_transmission(deform(curve, direction, sign * step),
                    source, receiver, ko, ki, normal_ratio=ratio).scattered_receiver for sign in (1, -1)]
                fd = (fields[0] - fields[1]) / (2 * step)
                lossy.append(dict(frequency_hz=freq, background_sigma_sm=conductivity,
                    target_sigma_sm=.005, polarization=polarization,
                    k_exterior=[ko.real, ko.imag], k_interior=[ki.real, ki.imag],
                    circle_relative_l2=relative_error(result.scattered_receiver, reference),
                    derivative_relative_l2=relative_error(analytic, fd)))
    report = dict(conventions="exp(-i omega t), H1 outgoing, passive epsilon + i sigma/omega",
                  convergence=convergence, derivatives=derivative_rows, lossy=lossy)
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(max_circle_te_error_256=max(r["relative_l2"] for r in convergence if r["nodes"] == 256),
        max_te_derivative_error=max(r["relative_errors"][-1] for r in derivative_rows),
        max_lossy_circle_error=max(r["circle_relative_l2"] for r in lossy),
        max_lossy_derivative_error=max(r["derivative_relative_l2"] for r in lossy)), indent=2))


if __name__ == "__main__":
    main()
