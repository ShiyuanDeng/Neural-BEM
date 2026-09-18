# Preserve the solved state, then decide whether a reduced model is safe to reuse

LAU-003 jointly compresses forward and tangent snapshots. Truncation can lose
an already accurate primal span, forcing rank selection to spend sensitivity
modes satisfying the anchor field/residual gate. LAU-004 isolates a hierarchical
construction which preserves that span exactly before truncating corrections.
A second arm protects receiver adjoints too, testing direction-independent
anchor sensitivity preservation separately from offset robustness.

The other lesson is that a passing anchor is not a refresh policy. The guard
uses equation defects and finite-matrix stability to bound reduced field and
four training derivative errors without a reference solve. Two unused directions
and an independent Kress oracle assess what that guard misses. A dense minimum-
singular-value computation is explicitly charged; useful logic is not yet a
speed improvement. Refusal triggers a fresh basis at the current candidate,
then the full model if the new basis is still refused.

The user's “go” authorizes the [bounded LAU-004 contract](../03_plan.md).
This work implements the previously proposed direction; it adds no literature
reproduction, material inversion, topology or production-default changes.
