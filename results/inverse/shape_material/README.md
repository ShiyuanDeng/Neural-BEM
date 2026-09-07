# Explicit shape/material diagnostics

- [Material inverse](material_inverse/bounded-20260906/README.md): fixed-circle or joint radial-K2 shape and one interior permittivity; successful and failed starts.
- [Robustness comparison](material_robustness/bounded-20260906/README.md): full-band, continuation and deterministic multistart on frozen cohorts.

These use analytic Kress derivatives on explicit geometry and perform no
MLP fitting. Their derivative, conditioning and training-only acceptance
lessons inform the [strict pipeline](../../../docs/pipelines/strict_mlp_method_b.md),
while their measured recovery remains a distinct claim.
See [pipeline details](../../../docs/pipelines/shape_material.md) and the [catalogue](../../README.md).
