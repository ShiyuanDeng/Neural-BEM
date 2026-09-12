# Topology iteration 07 — not the modes, not the data, the optimizer

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
truths require, the optimizer still lands **74,159× above** the objective the
true geometry achieves, and worse on every gated measure than the two circles it
started from.

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
peaks at exactly [6, 5] and recovers afterwards. Stage 2 read the ladder at the
one point that flattered its failure most, by accident of the budget — a second
way that truncation distorted the result, beyond the one stage 3 found.

**It still does not recover.** The finished ladder is worse than the starting
circles on matched error, IoU and holdout alike. And at `K = 9`, which covers
both a five- and a seven-lobed star, the training loss is 3.8613e-09 against the
truth's 5.2068e-14 — so this is no longer a representation limit of any kind.
Phase is still wrong at the top: `t001` needs 156° to reach 7.036 mm.

Areas come back to within 0.3% (3112.5 mm² against 3106.0; 2887.3 against
2895.9) while perimeters and lobe structure do not. The optimizer finds the
right amount of material in roughly the right place and the wrong boundary.

## What stage 3 measured

**The acquisition is not the limit.** At the true geometry, expressed in the
reconstruction's own chart, the training loss is **5.2068e-14** — relative L2
error 3.23e-07. The climb's final answer sits at 3.7174e-07, which is
**7,139,598×** worse. Twenty-four observations at 0.5 GHz determine these shapes
to seven significant figures. An acquisition limit would have shown the truth
fitting no better than the reconstruction.

**The mis-fit is largely phase.** Component `t001` at K=6 scores 17.600 mm
matched error against `truth.star5`, but **6.523 mm** once rigidly rotated by
34° — better than the 7.595 mm circle it started from. Its perimeter (256.13 mm
against 253.02), area (3129.8 mm² against 3106.0) and isoperimetric ratio
(1.6680 against 1.6403) all say it is a five-lobed star of the right size. The
matched-Hausdorff and IoU gates are phase-sensitive, so a correctly shaped but
mis-rotated star scores worse than a featureless circle.

**And the ladder never finished.** Stage 2 stopped on its declared `solve_cap`,
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

Three explanations have now been tested and eliminated in order:

1. **The derivative** — real defect, fixed in TOP-008, not sufficient.
2. **Capacity** — genuinely missing, genuinely restored, not sufficient.
3. **Data and regularization** — refuted here: the truth fits to 3.23e-07.

What is left is **globalization**, and stage 4 makes that conclusion much
stronger than stage 3 could. With every mode both truths require, the optimizer
still sits four orders of magnitude above the achievable objective. The failure
survives a finished ladder, so it cannot be blamed on representation, on data,
or on a truncated experiment. A promotion that zero-pads also starts the new
modes at exactly zero, where the phase of a symmetric mode pair is least
determined. These are optimization problems, addressable without touching the
acquisition or the frozen benchmark.

Also invalidated: the earlier suggestion that classical model selection had
"failed". Cross-resolution discrepancy, GCV and AIC were checked against the
saved climb and none flags the damaging rung — but all three presume a noise
floor the residual should not go below, and here the truth drives it to 5e-14.
They are inapplicable to a noiseless problem, which is a different statement.

## Next

One question, not authorized, needing its own contract: **escaping the phase
minimum.** The ladder is no longer part of it — stage 4 settled that. Candidate
mechanisms, in the order the evidence supports them:

1. **Seed the new modes instead of zeroing them.** Promotion currently pads with
   zeros, which is the least informative starting phase available. The controller
   already fits contours at a requested bandwidth for topology candidates; the
   same machinery could seed a promotion.
2. **Try several phases at promotion time** and keep the best by training
   objective. Directly targets the observed failure and needs no new theory.
3. ~~Raise the ladder's solve cap.~~ **Done** — stage 4. The ladder exhausts at
   [9, 9] and the failure survives it, which is what promotes the other two from
   speculation to the actual next test.

Regularization is **not** the next step, and neither is richer acquisition. Both
were plausible before stage 3 and neither survives it.

No controller default, gate, scene or budget changed in this cycle.
TOP-002–TOP-004 remain deferred proposals.
