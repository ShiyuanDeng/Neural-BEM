"""Read-only probes for the iteration-3 Claude review of the direct Method-B
Cartesian Fourier proposal.

No model is loaded, no BEM solve, extraction, conversion or inverse is run and
no saved artifact is modified.  The only input is each arm's saved
``geometry_trajectory.json``.  Its ``converted_contour`` is the production
Method-B curve sampled at the 194 equispaced native Kress nodes, so a plain DFT
recovers the retained bandwidth-96 coefficients exactly; the Nyquist bin is
reported as the check that this recovery is exact.

These are Cartesian coefficients in the curve's native (arc-length refit)
parameter.  They are neither the polar spectra of ``01_results.md`` nor the
arc-length normal modes of the optimizer reviews, and must not be compared with
either.
"""

from __future__ import annotations

import json

import numpy as np

RUN = (
    "results/validation/implicit_mlp_adjoint/iteration-02-final/"
    "long-acquisition-20260908T174300326691Z"
)
MOTION_CAP_M = 2.0e-3
CONVERSION_GATE_M = 2.0e-4


def coefficients(points):
    """Exact bandwidth-96 Cartesian coefficients from the 194 saved nodes."""

    p = np.asarray(points, dtype=np.float64)
    n = p.shape[0]
    spectrum = np.fft.fft(p, axis=0) / n
    half = n // 2
    cosine = np.zeros((half, 2))
    sine = np.zeros((half, 2))
    cosine[0] = spectrum[0].real
    for k in range(1, half):
        cosine[k] = 2.0 * spectrum[k].real
        sine[k] = -2.0 * spectrum[k].imag
    nyquist = float(np.linalg.norm(spectrum[half].real))
    return cosine, sine, nyquist


def evaluate(cosine, sine, parameters):
    modes = np.arange(cosine.shape[0])
    phase = parameters[:, None] * modes[None, :]
    points = np.cos(phase) @ cosine + np.sin(phase) @ sine
    first = (-np.sin(phase) * modes) @ cosine + (np.cos(phase) * modes) @ sine
    return points, first


def frozen_tail_amplitude(cosine, sine, band, dense=8192):
    """Largest displacement carried by the modes above ``band``."""

    if band + 1 >= cosine.shape[0]:
        return 0.0
    t = 2.0 * np.pi * np.arange(dense) / dense
    modes = np.arange(band + 1, cosine.shape[0])
    phase = t[:, None] * modes[None, :]
    tail = np.cos(phase) @ cosine[band + 1:] + np.sin(phase) @ sine[band + 1:]
    return float(np.max(np.linalg.norm(tail, axis=1)))


def load(arm, index):
    trajectory = json.load(open(f"{RUN}/{arm}/geometry_trajectory.json"))
    entry = trajectory[index]
    return entry["iteration"], entry["converted_contour"]


def probe_one_spectrum(label, points):
    cosine, sine, nyquist = coefficients(points)
    amplitude = np.sqrt((cosine**2 + sine**2).sum(axis=1))
    print(f"\n=== {label} ===")
    print(f"  nodes {np.asarray(points).shape[0]}, modes 0..{amplitude.size - 1}")
    print(f"  Nyquist bin (mode 97)      {nyquist:.6e} m   (exactness check; a B=96 curve has none)")
    print(f"  mode 0 |a_0|               {amplitude[0] * 1e3:12.6f} mm   (distance of the mean from the origin)")
    print(f"  mode 1                     {amplitude[1] * 1e3:12.6f} mm   (radius * sqrt(2) = {amplitude[1] / np.sqrt(2) * 1e3:.3f} mm)")
    order = np.argsort(amplitude[1:])[::-1][:8] + 1
    print("  eight largest non-constant modes:")
    print("    " + "  ".join(f"k={k}: {amplitude[k] * 1e3:.4f} mm" for k in order))
    print("  largest amplitude above a given mode:")
    for cut in (6, 16, 32, 48, 64, 80):
        print(f"    above mode {cut:>2}            {amplitude[cut + 1:].max() * 1e3:12.6f} mm")
    return cosine, sine, amplitude


def probe_frozen_tail(cosine, sine):
    print("\n  frozen tail carried by an active band B_a (the proposal's section 8.1.B):")
    print("    B_a   active real coefficients   largest frozen-tail displacement")
    for band in (5, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80):
        tail = frozen_tail_amplitude(cosine, sine, band)
        print(f"    {band:>3}   {2 + 4 * band:>25}   {tail * 1e6:15.3f} um")
    print(f"    (the neural conversion-distance gate is {CONVERSION_GATE_M * 1e6:.0f} um)")


def probe_gauge(cosine, sine):
    dense = 8192
    t = 2.0 * np.pi * np.arange(dense) / dense
    points, first = evaluate(cosine, sine, t)
    speed = np.linalg.norm(first, axis=1)
    perimeter = float(np.trapezoid(speed, t))
    print("\n  reparameterization gauge (a shift changes no geometry at all):")
    print(f"    perimeter {perimeter * 1e3:.3f} mm, speed {speed.mean() * 1e3:.3f} mm/rad, "
          f"speed ratio {speed.max() / speed.min():.6f}")
    modes = np.arange(cosine.shape[0])
    print("    shift s (rad)   fixed-parameter max displacement   coefficient norm change")
    for shift in (0.001, 0.005, 0.01, 1.0 / 30.0, 0.05):
        c, s = np.cos(modes * shift), np.sin(modes * shift)
        shifted_cos = c[:, None] * cosine + s[:, None] * sine
        shifted_sin = -s[:, None] * cosine + c[:, None] * sine
        shifted, _ = evaluate(shifted_cos, shifted_sin, t)
        displacement = float(np.max(np.linalg.norm(shifted - points, axis=1)))
        change = float(np.sqrt(((shifted_cos - cosine) ** 2).sum()
                               + ((shifted_sin - sine) ** 2).sum()))
        flag = "  <- saturates the 2 mm cap" if displacement >= MOTION_CAP_M else ""
        print(f"    {shift:11.5f}   {displacement * 1e3:29.4f} mm   {change * 1e3:19.4f} mm{flag}")


def main():
    iteration, points = load("E1", 0)
    cosine, sine, _ = probe_one_spectrum(f"shared initial state, iteration {iteration}", points)
    probe_frozen_tail(cosine, sine)
    probe_gauge(cosine, sine)
    for arm in ("E0", "E1"):
        iteration, points = load(arm, -1)
        probe_one_spectrum(f"{arm} final accepted state, iteration {iteration}", points)


if __name__ == "__main__":
    main()
