# Iteration 06 — protected spans lower rank; guarded delivery works in the pilot

Opened by **LAU-004 COMPLETE**, authorized by the user's “go” following LAU-003.
[Contract](../iteration_05/03_plan.md) ·
[Measured closeout](../../../../results/validation/laurent/LAU-004-20260917-closeout/README.md).

**The construction hypothesis has a useful partial result:** protecting the
primal span reduces rank from 80 to 56 on the ellipse and 120 to 112 on the
asymmetric star under a matched rank ladder. Both survive all four training-span
motions physically, while untrained motion and new illumination still fail.
The half-dimension target remains unmet. The ellipse comparison uses a fresh
rank-80 baseline; LAU-003's old rank 90 is not reclassified.

**The guard/rebuild policy delivers 42/42 physical passes.** It reuses 18
frozen models (six at the anchor), refuses all 18 inaccurate frozen cases and
conservatively refuses six accurate ones. The 24 rebuilds all pass, with no
full fallback. The guard uses matrix defects and four training sensitivities;
physical evaluation independently checks two additional directions and Kress.

90 tests, 14 full controls, 12 physical finite differences, 66 bound checks and
both new/old bundle audits pass. The full campaign is not released because
there is no successful nonanchor reuse at <=half dimension. Accurate delivery
through repeated rebuilds is not an efficiency claim. All 18 inaccurate frozen
models also exceed the simple primal-residual threshold, so the stronger guard
is not yet shown necessary on these physical fixtures.

**Next direction:** add residual corrections after refusal rather than immediately
rebuilding, and make rank selection anticipate finite geometry motion. Compare
those costs with full recompilation before opening an inverse-performance
campaign. The 48-dimensional primal/adjoint model demonstrates why anchor-only
rank selection is insufficient: it passes every anchor but rebuilds on every
nonanchor candidate. A complete inverse/recovery benefit remains untested.
