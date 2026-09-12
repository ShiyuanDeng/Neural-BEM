# Topology iteration 07 — bandwidth results and interpretation review

> **Independent review amendment, 2026-09-12:** the historical interpretation
> below is superseded where it claims a certified local minimum, unique/data-
> sufficient inversion, or monotone geometry degradation. Thirteen of fourteen
> retained rung refinements stopped on loss change, and the final data error is
> already below the controller's tolerance despite poor geometry. Truth
> consistency does not prove identifiability; truth-selected rotations do not
> measure training descent. Measurements and the stage-2 gate failure stand.
> [Review, counter repair, and proposed TOP-010](02_proposals/01_independent_review.md)
> contain the current conclusions and next step. The original reading is kept
> below as the cycle's historical record.

TOP-009 stopped at stage 2 on 2026-09-12, implementing rank 2 of the
[literature verdict](../iteration_05/02_proposals/03_literature_verdict.md).
[Full results](../../../../results/validation/topology/TOP-009-20260912-bandwidth-capacity/README.md).
The frozen twelve-scene v1 benchmark, its observations, budgets and gates are
unchanged; `bandwidth_promotion` ships opt-in and off; no suite was run.

## Correction notice

This page was first written as *"the modes were never the problem"*, concluding
from stage 2 that bandwidth enrichment overfits an under-determined acquisition
and that the binding constraint had become data and regularization. **That
conclusion was wrong.** A stage-3 diagnostic, run the same day and needing no new
inversion, refutes it. The stage-1 and stage-2 measurements are unchanged and
still stand; what follows is the corrected reading of them. The superseded
reading is preserved in the git history of this file and in the
[bundle](../../../../results/validation/topology/TOP-009-20260912-bandwidth-capacity/README.md)'s
correction notice rather than quietly rewritten.

## The result in one line

Adding shape bandwidth **does** produce real shape — and with every mode both
truths require, the optimizer still ends **74,159× above** a known attainable
objective, and worse on matched error, IoU and holdout than the two circles it
started from. Why it stops there is not established by this cycle.

## Stage 4 — the ladder, finished

Stage 2 stopped on its 2500-solve cap at modes [6, 5], so no statement about the
full ladder had been earned. Rerun with declared budgets of 40000 solves and
3600 s it exhausts: **14 of 14 rungs retained**, reaching [9, 9] in 7446 solves
and 762 s.

| Modes | Matched error | Union IoU | Worst holdout |
|---|---:|---:|---:|
| [1, 1] *start* | **7.595 mm** | **0.7468** | **1.003** |
| [3, 3] | 7.593 mm | 0.7458 | 1.005 |
| [5, 5] | 15.634 mm | 0.6952 | 1.147 |
| **[6, 5]** | **17.599 mm** | **0.6383** | **1.514** |
| [7, 7] | 12.030 mm | 0.7177 | 1.318 |
| [8, 8] | 11.323 mm | 0.7129 | 1.372 |
| [9, 9] *final* | 11.849 mm | 0.7088 | 1.415 |

**The stage-2 cap stopped the climb at its single worst rung.** Matched error
peaks at exactly [6, 5] and improves at every transition afterwards. Stage 2 read
the ladder at the one point that flattered its failure most, by accident of the
budget — a second way truncation distorted the result, beyond the one stage 3
found.

Two caveats on this table. The 7446 `solves` figure is the stage script's own
counter — optimizer evaluations plus padding and refined-acceptance calls — and
excludes the baseline and per-rung holdout evaluations, while some optimizer
evaluations are rejected before any BIE solve. It is a diagnostic counter, not a
controlled BIE-work measurement. And the script calls the fixed-topology
optimizer directly, bypassing the controller's early `recovered` return, its
topology proposals and its cycle limits; a controller handed a state already
inside its data tolerance would have stopped before promoting at all. This ladder
does not qualify the opt-in mechanism on the frozen suite.

**It still does not recover.** The finished ladder ends worse than the starting
circles on matched error, IoU and holdout alike — though the path there is *not*
monotone: matched error improves on seven of the fourteen rung transitions,
including every one after the [6, 5] peak. At `K = 9`, which covers both a five-
and a seven-lobed star, the training loss is 3.8613e-09 against the truth's
5.2068e-14, so bandwidth is no longer the missing ingredient. A truth-selected
156° rotation of `t001` reaches 7.036 mm, which scores a phase mismatch without
measuring any training descent along it.

Areas come back to within 0.3% (3112.5 mm² against 3106.0; 2887.3 against
2895.9) while perimeters and lobe structure do not. The optimizer finds the
right amount of material in roughly the right place and the wrong boundary.

## What stage 3 measured

**A known attainable objective exists, far below what the climb reaches.** At
the true geometry, expressed in the reconstruction's own chart, the training loss
is **5.2068e-14** — relative L2 error 3.23e-07. The climb's final answer sits at
3.7174e-07, which is **7,139,598×** worse. That establishes suboptimality, and
nothing more: forward consistency at the truth is not identifiability. A residual
this small shows the chart and forward model *can* match the observations at the
truth; it does not show the inverse is unique or stable, and no
alternative-solution search or conditioning audit has been run. (`F(x1, x2) = x1`
fits exactly for every `x2`.)

**A substantial phase mismatch is present.** Component `t001` at K=6 scores
17.600 mm matched error against `truth.star5`, but **6.523 mm** once rigidly
rotated by 34° — better than the 7.595 mm circle it started from. That angle is
**selected against the known truth**, so it measures a geometric mismatch and is
evaluation-only; no training-objective decrease was measured along it, and it is
not evidence of a phase minimum in the objective. Its perimeter (256.13 mm
against 253.02), area (3129.8 mm² against 3106.0) and isoperimetric ratio
(1.6680 against 1.6403) all say it is a five-lobed star of the right size. The
matched-Hausdorff and IoU gates are phase-sensitive, so a correctly shaped but
mis-rotated star scores worse than a featureless circle.

**And the stage-2 ladder never finished.** It stopped on its declared `solve_cap`,
3127 solves against 2500 — not on ladder exhaustion. A radial *m*-lobe harmonic
needs Cartesian bandwidth *m*+1, so `truth.star7` needs **K ≥ 8** and `t003` was
cut off at **K = 5**. The rung that would have mattered for the second component
was never attempted. The first write-up recorded the overrun as a budget note
without noticing it meant the experiment was truncated.

## What still stands from stage 1

The added directions are real and observable: at `far-two-stars` the six existing
mode-1 directions explain 0.000011 of the residual, one rung to K=3 reaches 20.4%
beyond that span and the ladder reaches 64.4%. Zero padding moved the boundary by
exactly 0.000e+00 m. The circular control found **0 of 14** rungs observable, so
the probe distinguishes a space missing shape from one that is not.

Stage 1 was right, and it was the part that predicted this: the modes were always
going to be usable.

## Why stage 2 still stopped the line, correctly

The contract's stage-2 predicate was the objective at both resolutions **and the
boundary error**. Boundary error degraded, so the gate held and the twelve-scene
suite was not run. That was the right call on the evidence available at the time,
and it remains the right call — shipping a rule that degrades the gated metric
would have been wrong whatever the mechanism turned out to be.

What changed is the diagnosis, not the decision.

## Where this leaves the track

Two mechanisms are measured and neither is sufficient:

1. **The derivative** — real defect, fixed in TOP-008, not sufficient.
2. **Capacity** — genuinely missing, genuinely restored, not sufficient.

**Data and regularization are not eliminated**, contrary to this page's original
reading. The decisive counter-observation is the controller's own tolerance: the
final K=9 answer has relative L2 error **8.7878e-05**, comfortably inside the
frozen **0.003** data gate, while its boundary error is **11.849 mm** and worst
holdout error **1.4154**. The first saved rung under that tolerance is [5, 5] at
15.634 mm. A data fit this good coexisting with geometry this poor is evidence
*for* taking acquisition and regularization seriously, not against.

What remains open is **why the optimizer stops where it does**, and the saved
record cannot answer it. **Thirteen of the fourteen retained rung refinements
stopped on `loss_change_tolerance`**, one on `maximum_iterations`, and none on
the gradient test. `_optimizer_config` uses the same absolute `1e-10` for the
loss target and the accepted loss change, and that branch runs *before* the
gradient check — so the stop reason bounds nothing about the terminal gradient.
Suboptimality is established; early stopping, ill-conditioned steps,
finite-difference error, active constraints, a saddle and a local minimum are all
still consistent with it, and the saved rung records carry no terminal gradient
norms or unresolved-column counts.

The earlier claim here of a certified local minimum is withdrawn. Completing the
ladder resolved the bandwidth cap and nothing else.

Also recorded: cross-resolution discrepancy, GCV and AIC were checked against
the saved climb and none flags the damaging rung. All three presume a noise floor
the residual should not be driven below, and this problem is noiseless, so they
are inapplicable here rather than refuted. That says nothing either way about
whether some *other* regularization would help.

## Next

One question, not authorized, needing its own contract: **escaping the phase
minimum.** The ladder is no longer part of it — stage 4 settled that. Candidate
mechanisms, in the order the evidence supports them:

1. ~~Seed the new modes from a contour fit instead of zeroing them.~~
   **Withdrawn.** An exact Fourier projection of the *same* contour has zero
   coefficients in precisely the added modes, so re-fitting what is already there
   supplies no new shape. A useful seed needs an explicitly data-derived contour
   or perturbation; sampling error is not a principled seed. The related claim
   that zero padding is a "phase trap" is also withdrawn — at zero amplitude the
   physical phase is undefined, but the gauge basis still contains independent
   sine and cosine directions, which are perfectly regular.
2. **Try several phases at promotion time**, selected by *training* objective
   only. Deferred until stopping is separated from stationarity, since a restart
   is not yet shown to be necessary.
3. ~~Raise the ladder's solve cap.~~ **Done** — stage 4. The ladder exhausts at
   [9, 9] and the failure survives it, which is what promotes the other two from
   speculation to the actual next test.

The next step is neither of these. It is the diagnostic the independent review
proposes as **TOP-010: separate stopping from stationarity** — audit the terminal
gradient at three FD steps, the reduced-Jacobian singular values, and whether a
feasible descent direction actually exists at the saved K=9 state, before any
restart mechanism is chosen. Acquisition and regularization stay on the table
rather than being ruled out.

No controller default, gate, scene or budget changed in this cycle.
TOP-002–TOP-004 remain deferred proposals.
