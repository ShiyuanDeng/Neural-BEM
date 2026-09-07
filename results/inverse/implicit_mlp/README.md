# Implicit MLP + Method B inverse

**Current recovery status: FAIL / unresolved.** All three completed 12-pair
runs below fail their declared overall recovery acceptance. The Kress adjoint
and neural derivative checks pass, but that has not repaired reconstruction.

The accepted shape belongs to all 8,577 trainable SIREN weights (width 64,
two hidden layers). A known wrong shape supplies initialization; the network
is then updated directly from the Kress adjoint through the current Method-B
conversion branch. Each candidate is re-extracted and re-solved. The inverse
does not fit a separately updated explicit curve at each iteration.

| Run | Accepted updates | Final holdout relative L2 | Maximum node-to-target-boundary distance | Overall |
|---|---:|---:|---:|---|
| [Circle → circle](circle-20260907T151516/summary.md) | 43 | 0.06394 | 1.038 mm | FAIL; no decreasing neural step |
| [Ellipse → circle](ellipse-to-circle-20260907T151516/summary.md) | 60 | 0.31864 | 6.450 mm | FAIL; iteration budget |
| [Star → star](star-20260907T151516/summary.md) | 60 | 0.78392 | 26.833 mm | FAIL; iteration budget |

These are existing runs indexed during reorganization, not rerun experiments.
Read each bundle's `metrics.json` for initial/final data loss, individual gates,
training/holdout frequencies and full settings. The boundary metric is the
stored node-to-exact-boundary distance, not a continuous Hausdorff certificate.
Saved videos may be rendered even when recovery gates fail.

The other current pipeline is [Explicit Radial Fourier](../radial_fourier/README.md).
The much cleaner old parametric Method-B videos are archived under
[known shape-family controls](../../legacy/known_shape_family_parameter_inverse/README.md):
those use 3–7 unknowns with supplied analytic shape structure, not this network.
The initial derivative/acceptance validation is preserved separately in
[validation](../../validation/implicit_mlp_adjoint/README.md).

Run with [`run_implicit_mlp_inverse.py`](../../../run_implicit_mlp_inverse.py).
See the [pipeline explanation](../../../docs/pipelines/implicit_mlp.md)
and [reproduction commands](../../../docs/reproduction.md). Comparing these
results with radial recovery still requires matched acquisitions, initial
geometry, resolution and work budgets.
