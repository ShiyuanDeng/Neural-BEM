"""G2/G3 probe: does the validated topological derivative locate the missing
component, and does the threshold-and-seed rule produce an accepted birth?

Reports, per frequency: the raw D_T J value at the true missing centre, the
grid minimum on a declared inspection disk at two resolutions, the C0
threshold region it selects, and the actual-objective birth line search.  It
also records the full J(A + disk(c_B, rho)) curve, which is what a radius
backtracking rule actually walks along.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from topology_probe_common import (
    CENTERS,
    COMPONENT_A,
    COMPONENT_B,
    CircularCylinder2D,
    current_domain_td,
    inspection_grid,
    objective,
    observed_scale,
    paired_scattered,
    ring_scan,
    wavenumbers,
)

FREQUENCIES_HZ = (0.1e9, 0.25e9, 0.5e9, 0.75e9, 1.0e9, 1.5e9, 2.0e9, 2.5e9)
BIRTH_FREQUENCIES_HZ = (0.25e9, 0.5e9, 0.75e9, 1.5e9)
THRESHOLDS = (0.15, 0.20, 0.40)
BACKTRACK_SCALES = (1.0, 0.75, 0.5, 0.35, 0.2, 0.1)
INSPECTION_RADIUS = 0.20
MASK_BUFFER = 0.004
MINIMUM_GAP = 0.005


def _state(frequency):
    sources, receivers = ring_scan()
    k_e, k_i = wavenumbers(frequency)
    observed = paired_scattered([COMPONENT_A, COMPONENT_B], sources, receivers, k_e, k_i)
    predicted = paired_scattered([COMPONENT_A], sources, receivers, k_e, k_i)
    scale = observed_scale(observed)
    base, _ = objective(predicted, observed)
    return sources, receivers, k_e, k_i, observed, predicted - observed, scale, base


def main() -> None:
    centre_b = np.asarray(CENTERS[1], dtype=float)
    print("Current domain = exact component A; truth = A + B; 24 paired ring stations.")
    print(f"Inspection region: disk of radius {INSPECTION_RADIUS} m about the scene centre,")
    print("A masked with a 4 mm buffer.  The ring standoff is 0.30 m, so every")
    print("inspection point is at least 0.10 m from every source and receiver.")

    print(f"\n{'f (GHz)':>8s} {'k_e r_B':>8s} {'J(A)':>9s} {'D_T J(c_B)':>13s} "
          f"{'min (n=121)':>20s} {'d (mm)':>8s} {'min (n=241)':>20s} {'d (mm)':>8s}")
    for frequency in FREQUENCIES_HZ:
        sources, receivers, k_e, k_i, observed, residual, scale, base = _state(frequency)
        at_b = current_domain_td(
            centre_b[None, :], [COMPONENT_A], sources, receivers, residual, scale, k_e, k_i
        )[0]
        row = []
        for count in (121, 241):
            *_ , points, keep = inspection_grid(
                count, radius=INSPECTION_RADIUS, exclude=(COMPONENT_A,), buffer=MASK_BUFFER
            )
            valid = points[keep]
            field = current_domain_td(
                valid, [COMPONENT_A], sources, receivers, residual, scale, k_e, k_i
            )
            index = int(np.argmin(field))
            row.append((valid[index], np.linalg.norm(valid[index] - centre_b) * 1000.0))
        print(f"{frequency / 1e9:8.2f} {k_e.real * COMPONENT_B.radius:8.3f} {base:9.4f} "
              f"{at_b: 13.4e} ({row[0][0][0]:.4f}, {row[0][0][1]:.4f}) {row[0][1]:8.1f} "
              f"({row[1][0][0]:.4f}, {row[1][0][1]:.4f}) {row[1][1]:8.1f}")

    print("\n\nThreshold region, circular seed and birth line search "
          "(n = 241, 4-connected labelling).")
    for frequency in BIRTH_FREQUENCIES_HZ:
        sources, receivers, k_e, k_i, observed, residual, scale, base = _state(frequency)
        axis_x, axis_y, grid_x, grid_y, points, keep = inspection_grid(
            241, radius=INSPECTION_RADIUS, exclude=(COMPONENT_A,), buffer=MASK_BUFFER
        )
        cell = float((axis_x[1] - axis_x[0]) * (axis_y[1] - axis_y[0]))
        values = np.full(points.shape[0], np.inf)
        values[keep] = current_domain_td(
            points[keep], [COMPONENT_A], sources, receivers, residual, scale, k_e, k_i
        )
        field = values.reshape(grid_x.shape)
        minimum = float(np.min(field))
        print(f"\n{'=' * 78}\nf = {frequency / 1e9:.2f} GHz   J(A) = {base:.6f}   "
              f"min D_T J = {minimum:.4e}")
        for threshold in THRESHOLDS:
            mask = np.isfinite(field) & (field < (1.0 - threshold) * minimum)
            labels, count = ndimage.label(mask)
            argmin = np.unravel_index(int(np.argmin(field)), field.shape)
            region = labels == labels[argmin]
            area = float(np.count_nonzero(region)) * cell
            seed = float(np.sqrt(area / np.pi))
            centroid = np.array([float(np.mean(grid_x[region])), float(np.mean(grid_y[region]))])
            print(f"\n  C0 = {threshold:.2f}: {count} region(s); selected area {area:.6f} m^2, "
                  f"r_eq {seed * 1000:.2f} mm (true 35.00 mm),")
            print(f"           centroid ({centroid[0]:.4f}, {centroid[1]:.4f}), "
                  f"{np.linalg.norm(centroid - centre_b) * 1000:.1f} mm from c_B")
            best = None
            for factor in BACKTRACK_SCALES:
                radius = factor * seed
                gap = (
                    float(np.linalg.norm(centroid - np.asarray(COMPONENT_A.center)))
                    - COMPONENT_A.radius - radius
                )
                if gap <= MINIMUM_GAP:
                    print(f"           {factor:5.2f} r_eq = {radius * 1000:7.2f} mm  "
                          f"rejected, clearance {gap * 1000:.1f} mm")
                    continue
                disk = CircularCylinder2D(center=tuple(centroid), radius=radius, component_id="ins")
                trial = paired_scattered([COMPONENT_A, disk], sources, receivers, k_e, k_i)
                loss, _ = objective(trial, observed)
                if loss < base and (best is None or loss < best[1]):
                    best = (radius, loss)
                print(f"           {factor:5.2f} r_eq = {radius * 1000:7.2f} mm  "
                      f"J = {loss:.6e}  dJ = {loss - base: .6e}  "
                      f"{'accept' if loss < base else 'reject'}")
            if best is None:
                print("           -> no_acceptable_birth")
            else:
                print(f"           -> best accepted radius {best[0] * 1000:.2f} mm, "
                      f"J {base:.6f} -> {best[1]:.6f}")

    print(f"\n\n{'=' * 78}")
    print("Objective along the exact-centre birth ray J(A + disk(c_B, rho)):")
    print("the truth is rho = 35.00 mm, where J is identically zero.")
    ladder = (0.001, 0.0025, 0.005, 0.0075, 0.010, 0.015, 0.020, 0.025, 0.030, 0.035)
    for frequency in (0.5e9, 1.5e9):
        sources, receivers, k_e, k_i, observed, residual, scale, base = _state(frequency)
        print(f"\n  f = {frequency / 1e9:.2f} GHz   J(A) = {base:.6e}")
        print(f"  {'rho (mm)':>9s} {'J':>14s} {'J - J(A)':>14s}")
        for radius in ladder:
            disk = CircularCylinder2D(center=tuple(centre_b), radius=radius, component_id="ins")
            trial = paired_scattered([COMPONENT_A, disk], sources, receivers, k_e, k_i)
            loss, _ = objective(trial, observed)
            print(f"  {radius * 1000:9.2f} {loss:14.6e} {loss - base: 14.6e}")


if __name__ == "__main__":
    main()
