# TOP-009 — controlled bandwidth enrichment of surviving components

Contract for rank 2 of the [literature verdict](../../iteration_05/02_proposals/03_literature_verdict.md), the
only other candidate it accepts. The verdict requires this to be a **separate
comparison** from the derivative correction so the two effects stay
identifiable, and this contract implements nothing from ranks 3–10.

## The defect, stated as geometry

The saved `far-two-stars` reconstruction is two components of Cartesian maximum
mode 1, against a five-lobed and a seven-lobed star. It stops with 1.4% of the
training residual unexplained, nothing pinned, and 22 mm of clearance headroom.
The stall is therefore not the derivative defect TOP-008 fixed — a per-side
census found all 6 of its gauge directions feasible on both sides — and not the
feasible set. It is that the shapes are not in the search space.

Measured directly, before any implementation:

| Cartesian max mode `K` | Parameters | Gauge directions |
|---:|---:|---:|
| 1 | 6 | 3 |
| 2 | 10 | **3** |
| 3 | 14 | 5 |
| 4 | 18 | 7 |
| 9 | 38 | 17 |

Under the polar-angle gauge, `K = 1` and `K = 2` carry the **same three**
directions — translate in x, translate in y, scale the radius. A mode-1
component cannot become an ellipse, let alone a star, and padding it to `K = 2`
buys parameters with no new direction at all. Genuine shape directions first
appear at `K = 3`, and each rung above that adds exactly two.

This is a provable property of the approximation space. It is **not** proof that
these particular circles are globally optimal within it, nor that the added
directions are identifiable from 24 observations at one frequency.

## Intervention

One mechanism, opt-in, default off, named `bandwidth_promotion`: a surviving
component may enter a strictly richer nested space, preserving its geometry
exactly.

**The ladder.** From a component's current `K`, the next rung is the smallest
`K' > K` that strictly increases the gauge dimension. From `K = 1` that is 3,
then 4, 5, and so on. The cap is the controller's existing
`chart_contour_modes` — 9 under the frozen spec — which is already the
bandwidth a fitted contour receives, so no new number is introduced and none is
taken from the truth. The rule is stated in terms of gauge dimension, not mode
count, so it can never spend a rung that adds nothing.

**Geometry preservation.** Promotion is zero padding of the Cartesian
coefficient arrays. The padded state must reproduce the pre-promotion boundary
and the production objective to rounding; this is asserted at every rung before
any refinement, and a failure aborts the promotion rather than being absorbed.

**The promotion rule**, predeclared and training-based only: after a bounded
refinement at the new bandwidth, the promotion is retained only if the objective
decreased by more than the controller's existing acceptance margin at **both**
resolutions, with the refined feasibility and admissibility checks unchanged.
Otherwise the component reverts to its pre-promotion state and stops climbing.
No holdout frequency, truth component count, lobe count or location enters any
of this.

Unchanged: the feasible set, the 8-mm certificate, the refined guard, the gauge,
the acquisition, topology candidate construction and acceptance, all margins,
and every default.

## Stages, in order, each able to stop the line

**Stage 1 — are the added directions observable at all?** No topology search. At
the saved `far-two-stars` final state, and at the saved `far-two-circles` state
as a control whose truth really is circular, climb the ladder and at each rung
record: that zero padding preserved geometry and objective; the sensitivity of
each new column against the solver's own numerical noise; and the residual
reduction available in the new directions **beyond the span of the columns that
already existed**. That last quantity is the one that matters — a new column
that merely re-expresses an old one explains nothing.

**Stop the line if** the new directions sit at or below the numerical noise
floor, or offer no residual reduction beyond the existing span. That result
would move the problem to data, conditioning or regularization, and would be a
finding rather than a failure.

**Stage 2 — does climbing actually help?** One bounded fixed-topology
continuation from the `far-two-stars` state with the promotion rule active,
against the same continuation without it. At most 22 iterations per rung, the
existing 600-second ceiling, and a declared cap of **2500 BIE solves** — higher
than TOP-008's because the ladder pays for several refinements, and declared
here rather than discovered.

Record which rungs were retained and which were reverted. **Reaching a higher
mode count is not the result**; the result is the objective at both resolutions
and the boundary error. A run that climbs to `K = 9` and reverts everything is a
clean negative and is reported as one.

**Stage 3 — does it hold on the frozen benchmark?** All twelve unchanged v1
scenes, saved observations and initial states, original gates and per-scene
limits. The comparison is against the best qualified arm from TOP-008 with
`bandwidth_promotion` as the only difference. Report every gate separately, plus
stop reasons, BIE solve counts, final mode counts per component, and rungs
retained against rungs attempted.

## What would falsify this

New columns indistinguishable from numerical noise; or no residual reduction
beyond the existing span; or a continuation that climbs and reverts. Any of
these says bandwidth was not the binding constraint on these scenes, which is
worth knowing precisely because the mode-9 `far-ellipse-star` component already
suggested it.

The honest prior, stated before execution: a mode-1 component provably cannot
represent a star, so **something** must change for `far-two-stars` to pass. That
does not make added modes identifiable from this acquisition. At 0.5 GHz the
exterior wavelength is about 245 mm and `k·rho0 ≈ 0.92`, which makes weak
sensitivity to fine harmonics entirely plausible. The verdict's confidence is
**medium** for star recovery and explicitly unresolved on observability. This
contract is built to measure that, not to assume it.

## Artifacts

Fresh bundle `results/validation/topology/TOP-009-.../` with a manifest and
source hashes, the stage-1 per-rung record, the stage-2 trajectories, the
stage-3 suite metrics, an `analyze.py` regenerating the report from saved
artifacts, and a test log. No hashed source is edited while a suite is running.
