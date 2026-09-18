# Iteration 05 — preserve sensitivities before attempting local inverse reuse

Opened by **LAU-003 COMPLETE**, authorized by the user's 2026-09-17 direction
to move to our innovations. [Contract](../iteration_04/03_plan.md) ·
[Measured closeout](../../../../results/validation/laurent/LAU-003-20260917-closeout/README.md).

**The first innovation screen separates accurate fields from accurate inverse
sensitivities.** Forward-only trace reduction fits anchor fields to about 1e-11
but fails derivatives badly. A primal/receiver-adjoint basis preserves all six
physical derivatives, including two untrained directions, with 48 instead of
194 unknowns on the difficult asymmetric star. That compact basis fails both
0.5%-radius geometry offsets: matching the anchor does not establish reuse.

A 120-dimensional tangent-enriched basis passes both offsets. Its stored
forward/derivative family is 48.8% of full, but its rank exceeds the predeclared
half-dimension target and shifted sources fail. The ellipse needs 90/98 unknowns
for the same tangent construction. Neither arm satisfies the compact-reuse
hypothesis across these controls.

The pilot stops before the full campaign: 11/12 physical FD rows pass, with
one coarse-step forward-only check at 1.39e-4 vs a 1e-4 gate. The finer check
passes with a fourfold reduction; all enriched-arm checks pass. The original
gate remains a recorded failure. All eight full controls qualify; B=128/160
refinement agrees to roundoff; **83 tests and the bundle audit pass**.

**Direction:** develop residual-guided sensitivity closure and an explicit basis
refresh rule for inverse updates. A hierarchical basis preserving the primal
span before adding orthogonal tangents is a concrete next candidate, since
joint POD currently spends many modes meeting the strict anchor residual.
This is an untested proposal. Generic POD/interpolation is prior art; any new
contribution needs to come from the Laurent-specific construction, qualification
and inverse behavior. No speed, inverse recovery or production claim is made.
