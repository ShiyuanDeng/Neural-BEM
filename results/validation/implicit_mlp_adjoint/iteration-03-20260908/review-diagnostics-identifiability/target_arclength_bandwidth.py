"""How much Cartesian bandwidth the star target needs in Method B's own chart.

A read-only review diagnostic.  No model is loaded and no BEM solve, inverse,
extraction or conversion is run; the only saved input is the shared initial
``converted_contour`` from the long run.  Everything else is analytic.

Method B refits by arc length, so the chart the direct control would optimize
is the Cartesian Fourier expansion in the *arc-length* parameter.  The star is
exactly bandwidth 6 in the polar-angle parameter, because

    (R + A cos 5th)(cos th, sin th)

expands to modes 1, 4 and 6 only.  Arc length is a nonlinear remap of that
parameter, so the same curve is not bandlimited in the chart actually used.
This prices the difference, and then prices the error floor of the proposal's
frozen-tail design, whose achievable curves are

    free active modes 0..B_a  +  the initial curve's modes above B_a.

Because the frozen modes are L2-orthogonal to the active ones, the parameterwise
L2 displacement of the best achievable curve is exactly the L2 norm of the
frozen-tail difference, minimized over the parameter-origin gauge.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
RUN = (
    ROOT / "results/validation/implicit_mlp_adjoint/iteration-02-final"
    / "long-acquisition-20260908T174300326691Z"
)
MEAN_RADIUS_M = 0.05
AMPLITUDE_M = 0.0125
LOBES = 5
CENTRE = np.array([0.5, 0.5])
DENSE = 1 << 16
BANDWIDTH = 96
CONVERSION_GATE_M = 2.0e-4


def target_polar(theta):
    radius = MEAN_RADIUS_M + AMPLITUDE_M * np.cos(LOBES * theta)
    return CENTRE + radius[:, None] * np.column_stack((np.cos(theta), np.sin(theta)))


def target_speed(theta):
    radius = MEAN_RADIUS_M + AMPLITUDE_M * np.cos(LOBES * theta)
    derivative = -LOBES * AMPLITUDE_M * np.sin(LOBES * theta)
    return np.hypot(radius, derivative)


def arclength_samples(count):
    """Sample the target at ``count`` points equispaced in arc length."""

    theta = 2.0 * np.pi * np.arange(DENSE) / DENSE
    speed = target_speed(theta)
    cumulative = np.concatenate(([0.0], np.cumsum(0.5 * (speed[1:] + speed[:-1])
                                                  * np.diff(theta))))
    total = cumulative[-1] + 0.5 * (speed[-1] + speed[0]) * (2.0 * np.pi / DENSE)
    wanted = total * np.arange(count) / count
    theta_at = np.interp(wanted, np.concatenate((cumulative, [total])),
                         np.concatenate((theta, [2.0 * np.pi])))
    return target_polar(theta_at), total


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
    return cosine, sine


def tail_displacement(cosine, sine, band, dense=8192):
    if band + 1 >= cosine.shape[0]:
        return 0.0, 0.0
    t = 2.0 * np.pi * np.arange(dense) / dense
    modes = np.arange(band + 1, cosine.shape[0])
    phase = t[:, None] * modes[None, :]
    tail = np.cos(phase) @ cosine[band + 1:] + np.sin(phase) @ sine[band + 1:]
    magnitude = np.linalg.norm(tail, axis=1)
    return float(magnitude.max()), float(np.sqrt(np.mean(magnitude ** 2)))


def tail_rms(cosine, sine, band):
    """Exact parameterwise RMS displacement of the modes above ``band`` (Parseval)."""

    if band + 1 >= cosine.shape[0]:
        return 0.0
    energy = 0.5 * ((cosine[band + 1:] ** 2).sum() + (sine[band + 1:] ** 2).sum())
    return float(np.sqrt(energy))


def shift(cosine, sine, s):
    modes = np.arange(cosine.shape[0])
    c, sn = np.cos(modes * s), np.sin(modes * s)
    return (c[:, None] * cosine + sn[:, None] * sine,
            -sn[:, None] * cosine + c[:, None] * sine)


def main():
    print(__doc__)

    theta = 2.0 * np.pi * np.arange(2 * BANDWIDTH + 2) / (2 * BANDWIDTH + 2)
    polar_cos, polar_sin = coefficients(target_polar(theta))
    polar_amplitude = np.sqrt((polar_cos ** 2 + polar_sin ** 2).sum(axis=1))
    print("=== target in the POLAR-ANGLE parameter (not the chart Method B uses) ===")
    print("  " + "  ".join(f"k={k}: {polar_amplitude[k] * 1e3:9.5f} mm"
                           for k in range(0, 9)))
    print(f"  largest amplitude above mode 6: {polar_amplitude[7:].max() * 1e3:.3e} mm "
          "(exactly bandlimited at 6)")

    points, perimeter = arclength_samples(2 * BANDWIDTH + 2)
    arc_cos, arc_sin = coefficients(points)
    arc_amplitude = np.sqrt((arc_cos ** 2 + arc_sin ** 2).sum(axis=1))
    speed = target_speed(2.0 * np.pi * np.arange(DENSE) / DENSE)
    print("\n=== target in the ARC-LENGTH parameter (the chart the control optimizes) ===")
    print(f"  perimeter {perimeter * 1e3:.4f} mm; polar-parameter speed ratio "
          f"{speed.max() / speed.min():.6f}")
    print("  " + "  ".join(f"k={k}: {arc_amplitude[k] * 1e3:9.5f} mm"
                           for k in range(0, 9)))
    print("  next modes: " + "  ".join(f"k={k}: {arc_amplitude[k] * 1e3:8.5f} mm"
                                       for k in range(9, 17)))
    print("\n  bandwidth the target itself needs in this chart:")
    print("    B_a   active real coefficients   max truncated displacement    RMS")
    for band in (4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 40, 48):
        top, rms = tail_displacement(arc_cos, arc_sin, band)
        flag = "   <- inside the 200 um conversion gate" if top < CONVERSION_GATE_M else ""
        print(f"    {band:>3}   {2 + 4 * band:>25}   {top * 1e6:15.3f} um   "
              f"{rms * 1e6:9.3f} um{flag}")

    trajectory = json.load(open(RUN / "E1/geometry_trajectory.json"))
    initial = np.asarray(trajectory[0]["converted_contour"], dtype=np.float64)
    init_cos, init_sin = coefficients(initial)

    print("\n=== error floor of the frozen-tail design ===")
    print("  achievable curves are: free modes 0..B_a  +  the INITIAL curve's modes above B_a.")
    print("  the floor is the frozen-tail difference, minimized over the parameter gauge.")
    print("    B_a   |tail(initial)|max   |tail(target)|max   floor RMS   floor max   best shift")
    grid = np.linspace(0.0, 2.0 * np.pi, 2048, endpoint=False)
    for band in (4, 6, 8, 10, 12, 16, 20, 24, 32, 48):
        init_top, _ = tail_displacement(init_cos, init_sin, band)
        target_top, _ = tail_displacement(arc_cos, arc_sin, band)
        best = None
        for s in grid:
            sc, ss = shift(init_cos, init_sin, s)
            rms = tail_rms(arc_cos - sc, arc_sin - ss, band)
            if best is None or rms < best[0]:
                best = (rms, s)
        sc, ss = shift(init_cos, init_sin, best[1])
        top, _ = tail_displacement(arc_cos - sc, arc_sin - ss, band)
        best = (best[0], top, best[1])
        print(f"    {band:>3}   {init_top * 1e6:16.3f} um   {target_top * 1e6:15.3f} um   "
              f"{best[0] * 1e6:8.3f} um   {best[1] * 1e6:8.3f} um   {best[2]:.4f} rad")
    print("\n  |tail(initial)| is the quantity the guide's section 8.1.B budget prices and")
    print("  the quantity the first review reported; the floor column is what the design")
    print("  can actually never correct.  Both are parameterwise displacements in the")
    print("  shared arc-length parameter, not symmetric point-to-curve distances.")


if __name__ == "__main__":
    main()
