# Topology iteration 07 — the modes were never the problem

TOP-009 stopped at stage 2 on 2026-09-12, implementing rank 2 of the
[literature verdict](../iteration_05/02_proposals/03_literature_verdict.md).
[Full results](../../../../results/validation/topology/TOP-009-20260912-bandwidth-capacity/README.md).
The frozen twelve-scene v1 benchmark, its observations, budgets and gates are
unchanged; `bandwidth_promotion` ships opt-in and off; no suite was run.

## The result in one line

Adding shape bandwidth to a stalled component fits the training data **248×
better** and makes the reconstruction **monotonically worse** at every rung.

| Rung retained | Training loss | Matched error | Union IoU | Worst holdout |
|---|---:|---:|---:|---:|
| *start*, modes [1, 1] | 9.219e-05 | **7.595 mm** | **0.7468** | **1.003** |
| both components 1→3 | 8.515e-05 | 7.593 mm | 0.7458 | 1.005 |
| both 3→4 | 5.228e-05 | 12.265 mm | 0.7167 | 1.036 |
| both 4→5 | 1.374e-06 | 15.634 mm | 0.6952 | 1.147 |
| `t001` 5→6 | **3.717e-07** | 17.599 mm | 0.6383 | 1.514 |

The best reconstruction in the whole climb is the state it started from.

## Why this is not a null result

Stage 1 ruled out the boring explanations before stage 2 ran.

The added directions are **real and observable**. At `far-two-stars` the six
existing mode-1 directions explain 0.000011 of the residual; one rung to `K = 3`
reaches 20.4% beyond that span and the full ladder reaches 64.4%. Column
estimates are stable to 7.3e-5 against a declared 0.25 tolerance, and zero
padding moved the boundary by exactly 0.000e+00 m at every rung.

The control worked. At `far-two-circles`, whose truth genuinely is circular, the
same ladder explains at most 3.8e-7 of the residual beyond the existing span —
five orders of magnitude under the declared floor — and not one rung is
observable. So the probe distinguishes a space that is missing shape from one
that is not.

So the modes are present, measurable and effective at fitting. They simply fit
the wrong thing.

## What it means

At 0.5 GHz the exterior wavelength is about 245 mm and `k·rho0 ≈ 0.92`. Twenty-four
observations at that one frequency do not determine harmonics this fine, so
every direction the promotion adds is spent on artefacts. The training-only
promotion rule — written that way deliberately, because using holdout data to
choose modes would destroy the holdout — retained all seven rungs, which is the
correct behaviour of a rule that cannot see what it is doing wrong.

This reframes the two remaining shape failures. `far-ellipse-star` stalling at
3% training error with a **mode-9** component is not an under-parameterized fit.
It is an over-parameterized one on an under-determined acquisition, which is why
TOP-008 freeing that component improved its boundary error while making its
training residual worse.

**The binding constraint on frozen v1 is data and regularization.** It is no
longer the derivative, which TOP-008 fixed, and it was never capacity.

## Why stage 3 was not run

The contract's stage-2 predicate was the objective at both resolutions **and the
boundary error**. Boundary error degraded, so stage 2 does not pass and the gate
holds. Running the twelve-scene suite would have spent forty-five minutes
confirming that a rule already shown to harm generalization harms it on twelve
scenes instead of one — and the rule would have been tuned after seeing its
result, which is what the stage structure exists to prevent.

One budget overrun is recorded rather than smoothed: the climb used 3127 solves
against a declared 2500 cap, because the stage script tests the cap between
rungs and a rung that starts inside it can finish outside. It does not affect the
conclusion; degradation is monotone from the first rung.

## What ships

`bandwidth_promotion` stays in the tree, opt-in and off, with fourteen
geometry-and-gauge tests and no BIE solve among them. It is the instrument that
produced this finding and the one a regularized or multi-frequency successor
would reuse. Nothing about it is recommended as a default.

Both accepted candidates from the literature verdict are now measured. Ranks
3, 5, 6, 8 remain deferred; 7, 9 remain rejected; 10 remains not pursued.

## Next

Two questions, neither authorized, each needing its own contract:

1. **Regularization.** The promotion rule chose on training data alone and had
   no way to see it was overfitting. A discrepancy principle, an L-curve, or a
   coefficient penalty would give it one. This is the cheaper of the two and it
   reuses everything already built.
2. **Acquisition** — the verdict's rank 4. More frequencies would plausibly make
   fine harmonics identifiable, but 1.5 and 2.5 GHz are the current holdout, so
   using them requires a **new untouched evaluation set** and therefore a change
   to the frozen benchmark's data contract. That is a decision for the user, not
   a step to take quietly.

No controller default, gate, scene or budget changed in this cycle.
TOP-002–TOP-004 remain deferred proposals.
