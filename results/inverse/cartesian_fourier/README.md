# Cartesian Fourier inverses

Direct inverses whose accepted optimization state is a Cartesian Fourier curve
`gamma(t)` in the **polar-angle** parameter. No neural field participates: no
extraction, no re-distancing, no Eikonal term, no representation audit and no
conversion gate. The shared optimizer's network argument is a parameterless
placeholder under the `curve_only` policy.

Nothing here refits to arc length. That is deliberate and load-bearing: the
analytic five-lobed star is exactly modes 1, 4 and 6 in polar angle, so band six
contains it to `6.4e-17 m`, while the same curve resampled to arc length is not
band-limited at any practical bandwidth — band 32 still leaves `1.069e-04 m`.
Choosing the parameter, not the bandwidth, is what sets the accuracy ceiling.

Run with `run_explicit_cartesian_fourier_inverse.py`. Plan and results:
`docs/iterations/cartesian_fourier/`.

| Run | Result |
|---|---|
| `cartesian-k6-ellipse-to-star-nystrom-kress-20260910` | Wrong ellipse to star, 24 angles, three-stage frequency continuation. Maximum boundary error `4.181e-02 -> 2.761e-09 m` in 41 accepted updates, converged on `stable_data_and_geometry`. Recovered exactly the predicted active modes 1, 4 and 6 with 2, 3 and 5 driven to zero. Radial reference: `2.570e-10 m` in 44 |

A like-for-like comparison against the radial chart — matched work, matched
updates, parameterization behaviour and recovered spectrum — is in
[`comparison_with_radial_fourier.md`](comparison_with_radial_fourier.md).

The comparison target is
`results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/`,
which shares this experiment's initial contour, acquisition, frequencies,
geometry configuration and optimizer settings exactly.

## Topology

Iteration 3 added automatic birth, death, split and merge to this chart, run
against the radial cycle's own suites. The controller receives data and initial
geometry only — no target component count, no event policy.

| Bundle | Result |
|---|---|
| [`topology_controller/iteration-03-20260910`](topology_controller/iteration-03-20260910/README.md) | Five automatic inversions, all `recovered`, with event sequences identical to the radial bundle's |
| [`topology_challenges/challenge-suite-20260910`](topology_challenges/README.md) | Three challenge cases, all `full_pass` against the same declared gates |

Both use `--chart cartesian` on the shared drivers; the radial bundles they are
matched against are unchanged.
