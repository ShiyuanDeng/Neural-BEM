# Shape sensitivity atlas

CPU-only, opt-in experiments using the existing Kress forward, discrete
shape derivative, reciprocal identity and observability audit. No inverse
policy or solver default changes.

See [results and reproduction](../../results/atlas/README.md). The entry point
is `python -m experiments.atlas.run_jacobian_spectrum --output NEW_DIRECTORY`.
`top009_projection` audits two explicitly declared finite-error correspondences;
`top009_path` checks a finite deformation after the local-linear model fails.
