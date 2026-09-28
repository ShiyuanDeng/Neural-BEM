# Iteration 30: localization repairs the distant-start failure

2026-09-28. **SC-050 COMPLETE.** The original far-circle-to-C failure is repaired
by a data-only center/radius search before deformable shape fitting. Six
prespecified development strategies distinguish initialization from numerical
resolution. The selected policy then transfers without fitting-based retuning
to six additional scene configurations.

| Original C strategy | RMS mm | Max relative residual | Full audit | Localization + fit s |
|---|---:|---:|---|---:|
| Baseline | 188.37 | 3.20 | FAIL | 1.60, early failure |
| 0.25 GHz warm-up only | 227.28 | 2.01 | FAIL | 13.80 |
| Quarter-sized coefficient steps | 214.05 | 2.32 | FAIL | 5.97 |
| Double quadrature, 1024/2048 | 188.35 | 3.20 | FAIL | 7.35 |
| Circle localization | 0.00181 | 3.95e-7 | PASS | 93.90 |
| Localization + 0.25 GHz warm-up | 0.00131 | 2.76e-7 | PASS | 93.03 |

The selected policy takes 109.00 s including initial/final independent audits
and post-fit scoring, excluding startup/provenance hashing. Both localization
arms are successful; the small numerical difference between them does not
establish an additional practical benefit from the warm-up. The prespecified
data-only selection rule chose the combined policy before transfer fitting.
The baseline's short runtime is a failed early stop, not a successful fast solve.

| Added scene | Baseline RMS mm | Selected RMS mm | Selected Hausdorff upper mm |
|---|---:|---:|---:|
| Opposite-side C start | 172.35 | 0.00131 | 0.0315 |
| Translated/rotated C | 210.04 | 0.00108 | 0.0304 |
| Translated/rotated star | 234.83 | 0.0180 | 0.0805 |
| New asymmetric shape | 228.08 | 0.0124 | 0.0802 |
| New thin C | 198.11 | 0.0334 | 0.2089 |
| New asymmetric shape, fixed 1% noise | 227.94 | 0.2198 | 0.7267 |

The selected policy passes all recovery and numerical gates: **5/5 clean and
1/1 noisy**, versus baseline **0/6**. Localization/fitting takes 92–139 s on
these transfers; audits and scoring bring worker times to 108–155 s. The noisy
maximum residual is 1.152%; its allowed ceiling is three times realized noise
with a 0.003 floor. This single noise draw does not establish statistical noise
robustness. Some final stages exhaust their fixed quotas; passing reconstruction
gates is not a claim of full optimizer convergence.

## Scientific interpretation

The original atlas's M3 Jacobian is reasonably conditioned (about 2.8 at
0.5 GHz), but its local least-squares direction shrinks and moves the displaced
circle away from the target. At 0.25 GHz the radius/translation subspace explains
75.9% of the squared residual locally, yet the predicted position change is
still wrong geometrically. A large decrease in local data loss does not imply
successful localization. The full-wave circle search evaluates alternative
positions before enabling flexible deformation, and the ablation supports this
as the consequential change on the failed scene.

[Bao, Hou & Li (2007)](https://doi.org/10.1016/j.jcp.2007.08.020) motivate
localization before frequency continuation; [Borges, Rachh & Greengard (2022)](https://arxiv.org/html/2210.11607v1#S2.SS1)
provide the penetrable-object continuation framework; [Borges & Greengard (2014)](https://arxiv.org/html/1408.5436v1#S3)
discuss damping and initialization. These are methodological precedents, not
proofs of global convergence for our paired near-field acquisition. The detailed
[plan](../../../../results/validation/shape_continuation/SC-050-localization-robustness/plan.md)
records the physics/acquisition differences and falsifiable hypotheses.

## Provenance and limits

The requested hour elapsed before reviewing Claude's SPD-014 findings. The
[review response](../../speedup/iteration_11/03_review_response.md) records the
sub-roundoff exact-count fix, 375 broad tests and 783 exact fuzz comparisons.
SC-050 reproduces SC-049's accepted baseline states exactly. Fresh observations
pass resolution and independent Kress checks. All 18 planned comparisons,
54 endpoint dense/spatial count comparisons, frozen sources/inputs, budgets,
and the selection rule pass the final evidence verification.

Two setup failures occurred before any localization ranking because a grid
circle enclosed a receiver. They are preserved; an acquisition-only exterior
check and qualification refusal handling repaired the harness. Before any
transfer fit, five proposed starting circles were also found to enclose sensors.
A single target-independent radial contraction made them feasible; their
original specifications, clearances and input hashes are retained. Targets,
observations and the selected policy did not change. These corrections are
explicitly part of the provenance and are not hidden successful-only reruns.

Total recorded physical work is 29,860 units including input generation,
audits, post-fit residuals and conservatively charged setup failures. The
finite panel uses fixed known contrast, one connected component, one acquisition,
a bounded circle family and one noise draw. It supports an experimental
localization-first option, not universal recovery or a new speedup factor.
No production default, branch or worktree was changed.

[Complete evidence, tables, and plots](../../../../results/validation/shape_continuation/SC-050-localization-robustness/README.md).
