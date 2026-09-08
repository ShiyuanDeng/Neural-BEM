"""G1 probe: does the proposed topological-derivative expression reproduce the
finite-radius insertion quotient of the production objective?

Validates the empty-background branch (T0) and the non-empty current-domain
branch (T1) of

    D_T J(z; Omega) = sum_f (w_f / s_f^2)
                      Re[ (k_i^2 - k_e^2)
                          sum_s conj(p_sf - d_sf) u_sf(z) G_f(z, x_r(s)) ]

against Q_rho(z) = (J(Omega + B_rho(z)) - J(Omega)) / (pi rho^2).
"""

from __future__ import annotations

import numpy as np

from topology_probe_common import (
    CENTERS,
    COMPONENT_A,
    COMPONENT_B,
    CircularCylinder2D,
    SOURCE_STRENGTH,
    current_domain_td,
    empty_domain_td,
    objective,
    observed_scale,
    paired_scattered,
    ring_scan,
    wavenumbers,
)

RADII_SEQUENCE = (0.02, 0.01, 0.005, 0.0025, 0.00125, 0.000625)
FREQUENCIES_HZ = (0.5e9, 1.5e9)


def _report(name, predicted, quotients):
    print(f"  D_T J at {name:34s} = {predicted: .8e}")
    for radius, quotient in quotients:
        error = abs(quotient - predicted) / abs(predicted)
        print(
            f"      rho = {radius:9.6f} m   Q_rho = {quotient: .8e}"
            f"   relative error {error:9.4%}"
            f"   sign {'agrees' if np.sign(quotient) == np.sign(predicted) else 'DISAGREES'}"
        )


def main() -> None:
    sources, receivers = ring_scan()
    print("Scene: config/two_circle_config.py targets, acquisition of")
    print("pytest/solver_comparisons/test_two_circle_comparison.py")
    print(f"  A = {COMPONENT_A.center} r = {COMPONENT_A.radius} m")
    print(f"  B = {COMPONENT_B.center} r = {COMPONENT_B.radius} m")
    print(f"  24 paired ring stations at 0.30 m standoff, source strength {SOURCE_STRENGTH}")
    print("  exterior epsr 6, interior epsr 3, lossless, nonmagnetic")

    for frequency in FREQUENCIES_HZ:
        k_e, k_i = wavenumbers(frequency)
        print(f"\n{'=' * 78}\nf = {frequency / 1e9:.2f} GHz   "
              f"k_e = {k_e.real:.4f}   k_i = {k_i.real:.4f}   "
              f"k_i^2 - k_e^2 = {(k_i * k_i - k_e * k_e).real:.4f}   "
              f"k_e * r_B = {k_e.real * COMPONENT_B.radius:.3f}")

        # ---- T0: empty background, truth is component A alone ---------------
        observed = paired_scattered([COMPONENT_A], sources, receivers, k_e, k_i)
        scale = observed_scale(observed)
        base, _ = objective(np.zeros_like(observed), observed)
        print(f"\n T0 empty background, truth = A only.  J(empty) = {base:.16f}")
        print("    closed form for one unit-weight frequency: 0.5 * w_f = 0.5")
        residual = -observed
        probes = {
            "true A centre": COMPONENT_A.center,
            "background (0.60, 0.60)": (0.60, 0.60),
        }
        predicted = empty_domain_td(
            np.array(list(probes.values()), dtype=float),
            sources, receivers, residual, scale, k_e, k_i,
        )
        for (name, point), value in zip(probes.items(), predicted):
            quotients = []
            for radius in RADII_SEQUENCE:
                disk = CircularCylinder2D(center=point, radius=radius, component_id="ins")
                trial = paired_scattered([disk], sources, receivers, k_e, k_i)
                loss, _ = objective(trial, observed)
                quotients.append((radius, (loss - base) / (np.pi * radius * radius)))
            _report(name, float(value), quotients)

        # ---- T1: current domain is exact A, truth is A + B ------------------
        observed = paired_scattered([COMPONENT_A, COMPONENT_B], sources, receivers, k_e, k_i)
        scale = observed_scale(observed)
        predicted_response = paired_scattered([COMPONENT_A], sources, receivers, k_e, k_i)
        base, relative = objective(predicted_response, observed)
        residual = predicted_response - observed
        print(f"\n T1 current domain = exact A, truth = A + B.")
        print(f"    ||d|| = {scale:.8e}   J(A) = {base:.10e}   relative L2 = {relative:.6e}")
        probes = {
            "true B centre": tuple(CENTERS[1]),
            "background (0.50, 0.62)": (0.50, 0.62),
            "background (0.66, 0.66)": (0.66, 0.66),
        }
        predicted = current_domain_td(
            np.array(list(probes.values()), dtype=float),
            [COMPONENT_A], sources, receivers, residual, scale, k_e, k_i,
        )
        for (name, point), value in zip(probes.items(), predicted):
            quotients = []
            for radius in RADII_SEQUENCE:
                disk = CircularCylinder2D(center=point, radius=radius, component_id="ins")
                trial = paired_scattered([COMPONENT_A, disk], sources, receivers, k_e, k_i)
                loss, _ = objective(trial, observed)
                quotients.append((radius, (loss - base) / (np.pi * radius * radius)))
            _report(name, float(value), quotients)


if __name__ == "__main__":
    main()
