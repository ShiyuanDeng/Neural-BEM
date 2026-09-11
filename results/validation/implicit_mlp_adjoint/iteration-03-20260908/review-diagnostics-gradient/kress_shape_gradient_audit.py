"""Is the Kress shape gradient correct at the run's own deformed geometries?

Stage B of the gradient-chain audit, and independently the check the direct
Method-B Fourier proposal's section 7.2 asks for. It removes the MLP entirely:
a saved contour is re-expressed exactly as its bandwidth-96 Cartesian Fourier
curve, perturbed coherently in coefficient space, and the Kress objective
adjoint plus geometry pullback

    dL = sum_i q_i . d gamma_i + sum_i p_i . d gamma'_i

is compared with central finite differences of the same production objective.

No inverse is run, no MLP is loaded, no extraction, projection or Method-B fit
is performed, and no saved artifact is modified. The only inputs are each arm's
``geometry_trajectory.json`` and the run's ``observations.npz``.

Because the saved contour has 194 nodes and bandwidth 96 is exactly
``(194 - 2) / 2``, the discrete Fourier transform of those nodes recovers the
curve exactly; the reported Nyquist bin is the check that it did.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]

import run_implicit_mlp_iteration2_matched as matched  # noqa: E402
from gpr_bem_kress.geometry_pullback import build_kress_geometry_pullback  # noqa: E402
from gpr_bem_kress.shape_derivative import build_indexed_objective_adjoint  # noqa: E402
from ordered_boundary.analytic import fourier_curve  # noqa: E402
from sdf_inverse.forward import predict_indexed_curve_response  # noqa: E402
from sdf_inverse.geometry import OrderedSDFGeometryConfig  # noqa: E402
from sdf_inverse.implicit_adjoint import _residual_transform  # noqa: E402
from sdf_inverse.optimization import (  # noqa: E402
    ComplexScatteredData, normalized_complex_residual,
)

RUN = (
    ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final"
    / "long-acquisition-20260908T174300326691Z"
)
ARMS = {"E0": ("paired", (0.5, 1.5)), "E1": ("multistatic", (0.5, 1.5))}
ACTIVE_BAND = 8
STEPS = (1.0e-4, 5.0e-5, 2.5e-5)
SEED = 724


def coefficients(points):
    n = points.shape[0]
    spectrum = np.fft.fft(points, axis=0) / n
    half = n // 2
    cosine = np.zeros((half, 2))
    sine = np.zeros((half, 2))
    cosine[0] = spectrum[0].real
    for mode in range(1, half):
        cosine[mode] = 2.0 * spectrum[mode].real
        sine[mode] = -2.0 * spectrum[mode].imag
    return cosine, sine, float(np.linalg.norm(spectrum[half].real))


def curve_from(cosine, sine, num_nodes):
    return fourier_curve(cosine, sine, component_id="component-0").discretize(
        num_nodes, require_even=True
    )


def jet(cosine, sine, parameters):
    modes = np.arange(cosine.shape[0])
    phase = parameters[:, None] * modes[None, :]
    points = np.cos(phase) @ cosine + np.sin(phase) @ sine
    first = (-np.sin(phase) * modes) @ cosine + (np.cos(phase) * modes) @ sine
    return points, first


def loss(curve, data, geometry_config):
    forward = predict_indexed_curve_response(
        curve, data.forward_problem, geometry_config, solver="kress",
        retain_kress_state=True,
    )
    residual, _ = normalized_complex_residual(
        forward.scattered_response, data.observed_scattered_response,
        data.frequency_weights,
    )
    return 0.5 * float(residual @ residual), forward


def audit(cosine, sine, data, geometry_config, rng):
    base, forward = loss(curve_from(cosine, sine, geometry_config.num_nodes),
                         data, geometry_config)
    adjoint = build_indexed_objective_adjoint(
        forward.kress_states, data.observed_scattered_response,
        data.forward_problem.source_indices, data.forward_problem.receiver_indices,
        residual_transform=_residual_transform(data),
    )
    pullback = build_kress_geometry_pullback(adjoint)

    direction_cos = np.zeros_like(cosine)
    direction_sin = np.zeros_like(sine)
    direction_cos[: ACTIVE_BAND + 1] = rng.normal(size=(ACTIVE_BAND + 1, 2))
    direction_sin[1: ACTIVE_BAND + 1] = rng.normal(size=(ACTIVE_BAND, 2))
    scale = np.sqrt((direction_cos ** 2).sum() + (direction_sin ** 2).sum())
    direction_cos /= scale
    direction_sin /= scale

    parameters = 2.0 * np.pi * np.arange(geometry_config.num_nodes) / geometry_config.num_nodes
    delta_points, delta_first = jet(direction_cos, direction_sin, parameters)
    analytic = float(pullback.contract(delta_points, delta_first))

    rows = []
    for step in STEPS:
        high, _ = loss(curve_from(cosine + step * direction_cos,
                                  sine + step * direction_sin,
                                  geometry_config.num_nodes), data, geometry_config)
        low, _ = loss(curve_from(cosine - step * direction_cos,
                                 sine - step * direction_sin,
                                 geometry_config.num_nodes), data, geometry_config)
        finite = (high - low) / (2.0 * step)
        rows.append({"step": step, "analytic": analytic, "finite_difference": finite,
                     "relative_error": abs(finite - analytic)
                     / max(abs(finite), abs(analytic), 1e-12)})
    return base, rows


def main():
    print(__doc__)
    observations = np.load(RUN / "observations.npz")
    geometry_config = OrderedSDFGeometryConfig(
        bounds=((0.3, 0.3), (0.7, 0.7)), grid_shape=(513, 513), projected_samples=256,
        bandwidth=96, num_nodes=194, arclength_dense_resolution=2048,
        validation_resolution=1024,
    )
    print(f"active perturbation band {ACTIVE_BAND}, steps {STEPS}, seed {SEED}\n")
    summary = {}
    for arm, (acquisition, frequencies) in ARMS.items():
        trajectory = json.load(open(RUN / arm / "geometry_trajectory.json"))
        data = ComplexScatteredData(
            matched.build_problem(acquisition, frequencies), observations[arm], np.ones(2)
        )
        print(f"########## {arm}: {acquisition} ##########")
        for entry in trajectory:
            if entry["iteration"] not in (
                trajectory[0]["iteration"], trajectory[len(trajectory) // 2]["iteration"],
                trajectory[-1]["iteration"],
            ):
                continue
            points = np.asarray(entry["converted_contour"], dtype=np.float64)
            cosine, sine, nyquist = coefficients(points)
            rebuilt = curve_from(cosine, sine, geometry_config.num_nodes)
            recovery = float(np.max(np.linalg.norm(np.asarray(rebuilt.points) - points, axis=1)))
            base, rows = audit(cosine, sine, data, geometry_config,
                               np.random.default_rng(SEED))
            worst = max(row["relative_error"] for row in rows[-2:])
            print(f"  --- state {entry['iteration']} ---")
            print(f"    exact-recovery check: Nyquist bin {nyquist:.3e} m, "
                  f"max node difference {recovery:.3e} m")
            print(f"    data objective {base:.6f}")
            print("    B  Kress shape gradient  " + "  ".join(
                f"h={row['step']:.2e}: {row['relative_error']:.3e}" for row in rows
            ) + f"   | worst of last two: {worst:.3e}")
            summary[f"{arm}/{entry['iteration']}"] = worst
        print()
    print("########## summary: worst relative error over the two smallest steps ##########")
    for key, value in summary.items():
        print(f"  {key:10} {value:.3e}")


if __name__ == "__main__":
    main()
