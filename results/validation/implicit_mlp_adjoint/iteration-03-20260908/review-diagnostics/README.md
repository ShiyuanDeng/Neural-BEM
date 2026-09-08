# Review diagnostics: the Cartesian Fourier chart

Probes run on 2026-09-08 by Claude to support
[`02_claude_review.md`](../../../../../docs/iterations/implicit_mlp/iteration_03/02_proposals/02_claude_review.md),
the review of the [direct Method-B Fourier proposal](../../../../../docs/iterations/implicit_mlp/iteration_03/02_proposals/01_chatgpt_guide.md).

No model was loaded and no BEM solve, extraction, conversion, gradient
evaluation or inverse was run. No saved artifact was modified. The sole input is
each arm's `geometry_trajectory.json` from
`../../iteration-02-final/long-acquisition-20260908T174300326691Z/`.

| File | Contents |
|---|---|
| `cartesian_fourier_chart.py` | The probe, reproducible from a checkout that retains the long run |
| `cartesian_fourier_chart.txt` | Its full-precision output |

## What is measured

The saved `converted_contour` is the production Method-B curve sampled at the
194 equispaced native Kress nodes. Because the retained representation has
bandwidth 96 and `num_nodes` is exactly `2 * 96 + 2`, a plain DFT of those nodes
recovers the coefficients exactly. The reported Nyquist bin, `9.6e-18 m` at the
shared initial state, is the check that this recovery is exact rather than an
approximation; it is not a physical quantity.

Three quantities follow: the Cartesian mode amplitude spectrum, the largest
displacement carried by the modes above a candidate active band, and the
fixed-parameter displacement produced by a pure reparameterization shift.

## Caveats that travel with the numbers

These are **Cartesian vector coefficients in the curve's own native arc-length
refit parameter**. They are not the polar spectra about the polygon area
centroid reported in `01_results.md`, and they are not the arc-length normal
modes used by the optimizer review. The three must not be interchanged. A polar
mode-5 star appears here mainly as Cartesian modes 4 and 6, so `mode 5` in this
output and `mode-5 amplitude` in the results document are different numbers
about different objects.

Two independent consistency checks against `01_results.md` hold: mode 0 is
`707.598 mm`, matching the distance from the origin to the centre `(0.5, 0.5) m`
of the configured bounds, and mode 1 divided by `sqrt(2)` is `60.377 mm`
initially and `50.235 mm` at E1's final state, against the separately reported
initial and final mean polar radii of `60.002 mm` and `50.145 mm`.

The gauge probe's shift is exact in coefficient space: shifting the parameter
origin rotates each mode pair by `k * s` and leaves the point set unchanged.
Its "fixed-parameter max displacement" column is the same quantity the
production motion cap measures, which is the point of reporting it.
