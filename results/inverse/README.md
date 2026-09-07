# Two inverse pipelines

These directories distinguish the two shape representations to compare. They
do not imply that a matched comparison has already been completed.

| Directory | Shape owner and measured status |
|---|---|
| [implicit_mlp](implicit_mlp/README.md) | Full neural weights; extraction/Method B and Kress adjoint. Current circle, ellipse-to-circle and star runs all FAIL recovery acceptance. Gradient checks pass; the recovery pipeline remains broken/unresolved. |
| [radial_fourier](radial_fourier/README.md) | Explicit radial Fourier coefficients. Recorded canonical reconstruction works in the successful controls; MLP fitting/export failures are reported separately. Material and frozen-metric variants live inside this pipeline. |

The old `method_b` bundles are now
[legacy known-shape-family parameter inverses](../legacy/known_shape_family_parameter_inverse/README.md).
They optimize 3–7 parameters in supplied shape families, including a fixed
five-lobe star; their clean videos do not demonstrate full-MLP shape recovery.
The numerical target parameters are still inferred from observations.

Historical neural-feedback and normal-update runs remain in [legacy](../legacy/README.md).
Use the [catalogue](../README.md) for configurations and separate recovery and
representation outcomes. A fair pipeline comparison requires matched data,
initial geometry, resolution and declared work budgets.
