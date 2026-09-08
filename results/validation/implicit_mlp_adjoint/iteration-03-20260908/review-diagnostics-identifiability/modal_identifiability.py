"""Modal identifiability of the star under the iteration-3 acquisitions.

A review diagnostic for the second Claude review of the direct Method-B
Cartesian Fourier proposal.  It runs Kress *forward* solves on frozen analytic
curves only.  No inverse is run, no MLP is loaded, no extraction, projection,
Method-B fit, conversion audit or adjoint is evaluated, and no saved artifact
is modified.

For a frozen curve it builds the central finite-difference Jacobian of the
measured data with respect to radial polar modes ``0..K`` and the two centre
translations, under several acquisitions.  Two quantities follow:

* the per-mode sensitivity, the norm of each Jacobian column;
* the coherence between columns, ``|<J_a, J_b>| / (||J_a|| ||J_b||)``, which is
  1 when the acquisition cannot separate two boundary modes at first order.

The normalization matches the inverse's own objective: each frequency column of
the residual is divided by the fixed norm of the observed column at that
frequency, with unit frequency weights.

The finite-difference step is the radial inverse's production
``finite_difference_step_m`` of 2e-4 m; a second step is reported so the
coherences can be seen not to depend on it.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]

import run_sdf_inverse_comparison as driver  # noqa: E402
from sdf_inverse.curve_updates import (  # noqa: E402
    RadialFourierCurveState, radial_fourier_state_curve,
)
from sdf_inverse.forward import (  # noqa: E402
    IndexedForwardProblem, predict_indexed_curve_response,
)
from sdf_inverse.geometry import OrderedSDFGeometryConfig  # noqa: E402

RUN = (
    ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final"
    / "long-acquisition-20260908T174300326691Z"
)
MAXIMUM_MODE = 10
STEPS_M = (2.0e-4, 1.0e-4)

GEOMETRY = OrderedSDFGeometryConfig(
    bounds=((0.0, 0.0), (1.0, 1.0)), grid_shape=(513, 513), projected_samples=256,
    bandwidth=96, num_nodes=194, arclength_dense_resolution=2048,
    validation_resolution=1024,
)

# (label, multistatic, ring pairs, training frequencies in GHz)
ACQUISITIONS = (
    ("E0  paired-8      2 f", False, 8, (0.5, 1.5)),
    ("E1  multistatic-8 2 f", True, 8, (0.5, 1.5)),
    ("    paired-8      6 f", False, 8, (0.25, 0.5, 1.0, 1.5, 2.0, 2.5)),
    ("    multistatic-8 6 f", True, 8, (0.25, 0.5, 1.0, 1.5, 2.0, 2.5)),
    ("    paired-24     2 f", False, 24, (0.5, 1.5)),
    ("    multistatic-24 2 f", True, 24, (0.5, 1.5)),
    ("R   paired-24     6 f", False, 24, (0.25, 0.5, 1.0, 1.5, 2.0, 2.5)),
)


def problem(multistatic: bool, pairs: int, frequencies):
    target = driver.StarTarget()
    sources, receivers = driver._ring_scan(
        center=target.center, standoff=0.30, num_pairs=pairs
    )
    paired = driver._build_problem(frequencies, sources, receivers)
    return IndexedForwardProblem.from_paired(paired, multistatic=multistatic)


def state(center, cosine, sine):
    return RadialFourierCurveState(
        center=np.asarray(center, dtype=np.float64),
        radius_cosine_coefficients=np.asarray(cosine, dtype=np.float64),
        radius_sine_coefficients=np.asarray(sine, dtype=np.float64),
        component_id="component-0",
    )


def response(center, cosine, sine, forward):
    curve = radial_fourier_state_curve(
        state(center, cosine, sine), geometry_config=GEOMETRY
    )
    return predict_indexed_curve_response(
        curve, forward, GEOMETRY, solver="kress"
    ).scattered_response


def real_vector(complex_response, column_norms):
    scaled = np.asarray(complex_response) / column_norms[None, :]
    return np.concatenate((scaled.real.ravel(), scaled.imag.ravel()))


def columns(center, cosine, sine):
    """Perturbation directions: centre x, centre y, then radial cosine 0..K."""

    yield "cx", (center + np.array([1.0, 0.0]), cosine, sine)
    yield "cy", (center + np.array([0.0, 1.0]), cosine, sine)
    for mode in range(MAXIMUM_MODE + 1):
        if mode == 1:
            continue  # mode-1 radius is the translation gauge; carried by cx/cy
        bumped = cosine.copy()
        bumped[mode] += 1.0
        yield f"m{mode}", (center, bumped, sine)


def jacobian(center, cosine, sine, forward, step, column_norms):
    names, cols = [], []
    for name, (pc, pcos, psin) in columns(center, cosine, sine):
        dc = (np.asarray(pc, float) - center) * step
        dcos = (pcos - cosine) * step
        dsin = (psin - sine) * step
        plus = real_vector(response(center + dc, cosine + dcos, sine + dsin, forward),
                           column_norms)
        minus = real_vector(response(center - dc, cosine - dcos, sine - dsin, forward),
                            column_norms)
        names.append(name)
        cols.append((plus - minus) / (2.0 * step))
    return names, np.column_stack(cols)


def report(title, center, cosine, sine):
    print(f"\n\n########## {title} ##########")
    for label, multistatic, pairs, frequencies in ACQUISITIONS:
        forward = problem(multistatic, pairs, frequencies)
        entries = int(np.asarray(forward.source_indices).size)
        observed = np.asarray(
            response(np.array([0.5, 0.5]), TARGET_COSINE, TARGET_SINE, forward)
        )
        column_norms = np.linalg.norm(observed, axis=0)
        print(f"\n=== {label}   entries {entries}, frequencies {len(frequencies)}, "
              f"real residual components {2 * entries * len(frequencies)} ===")
        for step in STEPS_M:
            names, jac = jacobian(center, cosine, sine, forward, step, column_norms)
            norms = np.linalg.norm(jac, axis=0)
            unit = jac / np.maximum(norms, np.finfo(float).tiny)[None, :]
            gram = np.abs(unit.T @ unit)
            index = {name: i for i, name in enumerate(names)}
            singular = np.linalg.svd(jac, compute_uv=False)
            print(f"  finite-difference step {step * 1e6:.0f} um")
            print("    per-mode sensitivity ||J_m|| (dimensionless data per metre):")
            print("      " + "  ".join(
                f"{n}:{norms[i]:9.2e}" for n, i in index.items()))
            pairs_to_show = (("m5", "m3"), ("m5", "m4"), ("m5", "m6"), ("m3", "m4"),
                             ("m2", "m6"), ("m0", "m8"), ("m5", "m7"), ("m2", "m10"))
            print("    coherence |<Ja,Jb>|/(|Ja||Jb|)  (1.0 = inseparable at first order):")
            print("      " + "  ".join(
                f"{a}~{b}:{gram[index[a], index[b]]:.4f}" for a, b in pairs_to_show))
            worst = max(
                ((gram[i, j], names[i], names[j])
                 for i in range(len(names)) for j in range(i + 1, len(names))),
            )
            print(f"    largest off-diagonal coherence  {worst[0]:.4f}  "
                  f"({worst[1]} ~ {worst[2]})")
            print(f"    singular values of J: max {singular[0]:.3e}  "
                  f"min {singular[-1]:.3e}  condition {singular[0] / singular[-1]:.3e}")
            print("      " + "  ".join(f"{s:.3e}" for s in singular))


TARGET_COSINE = np.zeros(MAXIMUM_MODE + 1)
TARGET_COSINE[0] = 0.05
TARGET_COSINE[5] = 0.0125
TARGET_SINE = np.zeros(MAXIMUM_MODE + 1)


def initial_state_from_run():
    """Band-limited radial fit of the shared initial contour, from saved data."""

    trajectory = json.load(open(RUN / "E1/geometry_trajectory.json"))
    spectrum = trajectory[0]["radial_spectrum"]
    coefficients = np.asarray(
        [complex(value["real"], value["imag"]) if isinstance(value, dict) else complex(value)
         for value in spectrum["radial_complex_coefficients"]]
    )
    cosine = np.zeros(MAXIMUM_MODE + 1)
    sine = np.zeros(MAXIMUM_MODE + 1)
    cosine[0] = coefficients[0].real
    for mode in range(1, MAXIMUM_MODE + 1):
        cosine[mode] = 2.0 * coefficients[mode].real
        sine[mode] = -2.0 * coefficients[mode].imag
    cosine[1] = 0.0
    sine[1] = 0.0
    return np.asarray(spectrum["center_m"], dtype=np.float64), cosine, sine


def main():
    print(__doc__)
    print(f"maximum mode {MAXIMUM_MODE}; geometry {GEOMETRY.num_nodes} Kress nodes, "
          f"bandwidth {GEOMETRY.bandwidth}")
    report("exact target star: r = 50 + 12.5 cos(5 theta) mm about (0.5, 0.5) m",
           np.array([0.5, 0.5]), TARGET_COSINE, TARGET_SINE)
    center, cosine, sine = initial_state_from_run()
    print(f"\n\nshared initial contour, radial fit to mode {MAXIMUM_MODE}: "
          f"centre {center}, mean radius {cosine[0] * 1e3:.4f} mm, "
          f"mode-5 amplitude {np.hypot(cosine[5], sine[5]) * 1e3:.4f} mm")
    report("shared initial neural contour (band-limited radial fit)",
           center, cosine, sine)


if __name__ == "__main__":
    main()
