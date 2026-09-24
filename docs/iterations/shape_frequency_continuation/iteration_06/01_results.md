# Iteration 06 — isolate step halving, then audit curvature admissibility

2026-09-23. The user approved the proposed step-halving diagnostic on one
failed noncircular start. [SC-019](../../../../results/validation/shape_continuation/SC-019-step-halving/README.md)
records the experiment, an exact control replay, every trial and a motivated
curvature follow-up. No numerical core or production defaults changed.

**Step halving helps, but is not a complete repair.** On ellipse-to-star,
changing only `backtracks=0` to `6` reduces sampled boundary error from
58.7 mm to 39.1 mm. At exactly the original stalled state, a 1/8 Gauss–Newton
step lowers residual 0.864 to 0.782, while the original search rejects all
trials as geometrically invalid. This isolates one local search defect.

The subsequent target audit changes the reading of SC-018: the inherited
SC-017 gate allows 1% curvature energy above band 20, but the exact star has
8.07%. It therefore excludes the true target. The same result holds after
arclength refitting. A restricted gate can still admit close approximations;
this audit alone is not proof that the practical recovery gate is impossible.
It does rule out interpreting the failed exact reconstructions as an intrinsic
limitation of Cartesian/arclength storage or adaptive continuation.

Testing the existing 10% `FitConfig` default, both with and without halving,
completes a four-arm comparison with one changed setting per comparison edge.
Relaxing curvature alone does not improve recovery. Together, the changes
reduce training error from 94.7% to 8.18%, worst held-out error from 184% to
22.0%, and symmetric area error from 77.1% to 5.53%. A false left protrusion
persists and boundary error is 31.6 mm. **All four arms fail the original gates.**

The combined endpoint again lies almost on its curvature limit (9.9951%
against 10%), with a substantial gradient. Its final search rejects most
trials for curvature. Earlier stages mostly reject geometry/refit proposals.
The 128-mode initial storage also fails the exact star's projection tolerance,
although the final 288-mode storage exceeds the target's measured requirement.
Neither fact identifies a complete fix by itself.

The source/input hashes agree; the baseline endpoint and solve count replay
exactly. Every endpoint is scored and passes field refinement. The numerical
core is unchanged from the 218-test SC-018 validation. No budget is exhausted,
and no independent review is claimed.

The immediate issue is a geometry-admissibility and step-control mismatch on
these inherited fixtures. Damping and cumulative-frequency fitting remain
unisolated. Any next comparison should retain the old pipeline and this
four-arm evidence, declare the admissibility settings explicitly, and avoid
attributing these failures to harmonic transport alone.
