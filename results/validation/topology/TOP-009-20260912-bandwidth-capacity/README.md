# TOP-009 — the ladder finished, and the optimizer is still stuck

Rank 2 of the [literature verdict](../../../../docs/iterations/topology/iteration_05/02_proposals/03_literature_verdict.md),
the only other candidate it accepts.
[Contract](../../../../docs/iterations/topology/iteration_06/02_proposals/01_bandwidth_capacity_contract.md) ·
[review](../../../../docs/iterations/topology/iteration_06/02_proposals/02_bandwidth_capacity_review.md) ·
[plan](../../../../docs/iterations/topology/iteration_06/03_plan.md).

Stage 1 passed. Stage 2 failed its declared predicate — boundary error, IoU and
holdout error all worsened while training loss fell 248× — so the line stopped
and the twelve-scene suite was not run.

> **Correction, same day.** Stage 2 was first written up as overfitting on an
> under-determined acquisition, concluding that the binding constraint was data
> and regularization. **That conclusion was wrong**, and
> [stage 3](stage3_correction.py) refutes it with four measurements that need no
> new inversion. The stage-1 and stage-2 *measurements* below are unchanged; the
> reading of them is corrected. This section is the corrected reading.

Observations, initial states and saved final states come from the qualified
[TOP-008 bundle](../TOP-008-20260912-feasible-fd/README.md), byte-identical to
TOP-007's and TOP-006's. No new oracle solve was performed, no controller
default changed, and `bandwidth_promotion` ships opt-in and off.

## Stage 3 — the correction

**The acquisition determines these shapes.** Evaluated at the *true* geometry,
expressed in the reconstruction's own chart:

| State | Training loss | Relative L2 |
|---|---:|---:|
| **True geometry** | **5.2068e-14** | **3.23e-07** |
| Climb start, modes [1, 1] | 9.2195e-05 | 1.36e-02 |
| Climb final, modes [6, 5] | 3.7174e-07 | — |

The climb's answer is **7,139,598× worse** in training loss than the truth. So
24 observations at 0.5 GHz are nowhere near exhausted, there is no
non-uniqueness at this level, and the optimizer is sitting in a local minimum.
An acquisition limit would have shown the truth fitting *no better* than the
reconstruction. It fits seven million times better.

**The mis-fit is largely rotational phase.**

| Component | Matched error | Best over rigid rotation | At |
|---|---:|---:|---:|
| `t001` K=6 vs `truth.star5` | 17.600 mm | **6.523 mm** | 34.0° |
| `t003` K=5 vs `truth.star7` | 11.940 mm | 10.059 mm | 204.0° |

`t001` became a genuine five-lobed star and then sat a third of a lobe out of
phase. Rotated into place it beats the **7.595 mm** circle it started from. The
matched-Hausdorff and IoU gates are phase-sensitive, so a correctly shaped but
mis-rotated star scores worse than a featureless circle of the right size —
which is exactly what the stage-2 table recorded.

Phase-blind shape measures agree that the shape itself improved:

| Curve | Perimeter | Area | Isoperimetric ratio |
|---|---:|---:|---:|
| `truth.star5` | 253.02 mm | 3106.0 mm² | 1.6403 |
| final `t001` (K=6) | **256.13 mm** | **3129.8 mm²** | **1.6680** |
| `truth.star7` | 273.64 mm | 2895.9 mm² | 2.0577 |
| final `t003` (K=5) | 206.85 mm | 2867.0 mm² | 1.1877 |

**And the ladder never finished.** Stage 2 stopped on `solve_cap` — 3127 solves
against the declared 2500 — not on ladder exhaustion. A radial *m*-lobe harmonic
needs Cartesian bandwidth *m*+1, so `truth.star7` requires **K ≥ 8** and `t003`
was cut off at **K = 5**. The second component was never given the bandwidth its
truth requires, and the rung that would have mattered was never attempted. The
earlier write-up recorded the overrun as a budget note without recognising that
it meant the experiment was truncated.

**So the stage-2 failure is optimization, not information.** A local minimum in
rotational phase, on a ladder that stopped early.

Two secondary readings also fall with it. Cross-resolution discrepancy, GCV and
AIC were checked against the saved climb and none identifies the damaging rung —
but that is not evidence about regularization. All three presume a noise floor
the residual should not be driven below, and here the truth drives it to 5e-14.
They are inapplicable, not merely unhelpful.

## Stage 4 — the ladder, finished

Stage 2 stopped on its 2500-solve cap at modes [6, 5], so no statement about the
*full* ladder was ever earned. Rerun from the same saved state with declared
budgets of 40000 solves and 3600 s, it exhausts: **14 of 14 rungs attempted and
retained**, reaching [9, 9] in 7446 solves and 762 s.

| Modes | Matched error | Union IoU | Worst holdout |
|---|---:|---:|---:|
| [1, 1] *start* | **7.595 mm** | **0.7468** | **1.003** |
| [3, 3] | 7.593 mm | 0.7458 | 1.005 |
| [4, 4] | 12.265 mm | 0.7167 | 1.036 |
| [5, 5] | 15.634 mm | 0.6952 | 1.147 |
| **[6, 5]** | **17.599 mm** | **0.6383** | **1.514** |
| [6, 6] | 14.175 mm | 0.6545 | 1.383 |
| [7, 7] | 12.030 mm | 0.7177 | 1.318 |
| [8, 8] | 11.323 mm | 0.7129 | 1.372 |
| [9, 9] *final* | 11.849 mm | 0.7088 | 1.415 |

**The stage-2 cap truncated the climb at its single worst rung.** Matched error
peaks at exactly [6, 5] — 17.599 mm — then recovers to 11.3-11.8 mm once both
components get past it. The earlier write-up read the ladder at the one point
that flattered its failure most, by accident of the budget.

**The full ladder still does not recover.** 11.849 mm against the starting
circles' 7.595 mm, IoU 0.7088 against 0.7468, worst holdout 1.415 against 1.003.
Enrichment ends worse on every gated measure than the two circles it began with.

**And with all the bandwidth its truth requires, the optimizer is still
74,159x above the achievable objective** — final training loss 3.8613e-09
against the truth's 5.2068e-14. `K = 9` covers both a five-lobed and a
seven-lobed star (a radial *m*-lobe harmonic needs Cartesian *m*+1), so this is
no longer a representation limit of any kind. Phase is still wrong at the top of
the ladder: `t001` needs a 156 degree rotation to reach 7.036 mm, `t003` a 138
degree rotation to reach 10.328 mm.

Shape measures show what the components actually became:

| Curve | Perimeter | Area | Isoperimetric ratio |
|---|---:|---:|---:|
| `truth.star5` | 253.02 mm | 3106.0 mm2 | 1.6403 |
| final `t001` (K=9) | 267.56 mm | **3112.5 mm2** | 1.8303 |
| `truth.star7` | 273.64 mm | 2895.9 mm2 | 2.0577 |
| final `t003` (K=9) | 233.07 mm | **2887.3 mm2** | 1.4972 |

Areas are recovered to within 0.3%; perimeters and lobe structure are not, and
each component's isoperimetric ratio sits between the two truths rather than on
its own. The optimizer has the right amount of material in roughly the right
place and the wrong boundary.

**So bandwidth is necessary and nowhere near sufficient.** The binding obstacle
is a local minimum the LM optimizer cannot leave, four orders of magnitude above
the objective the true geometry attains, with every mode it needs available.

[Ladder record](stage4_uncapped_ladder.json) | [script](stage4_uncapped_ladder.py)

## Stage 1 — are the added directions observable? PASS

A per-rung probe of two saved states, no optimizer and no topology search. The
ladder, the 0.25 stability tolerance and the 1.0e-3 beyond-span floor were
declared in the contract before execution.

| State | Rungs probed | Observable | Residual explained beyond the existing span |
|---|---:|---:|---|
| `far-two-stars` — truth is two stars | 14 | **14** | up to **0.6445** |
| `far-two-circles` — truth really is circles | 14 | **0** | at most **3.8e-7** |

At `far-two-stars` the six existing mode-1 directions explain **0.000011** of the
residual. One rung to `K = 3` reaches 20.4% beyond that span; the full ladder
reaches 64.4%. The control behaves as a control: where the truth is already
inside the space, the same ladder explains 3.8e-7, five orders of magnitude
below the floor, and nothing is observable.

Zero padding moved the boundary by **0.000e+00 m** at every rung on both states,
and column estimates are stable to 7.3e-5 against the 0.25 tolerance. The weakest
new column at `K = 9` is 4.7e-6 of the largest, so high rungs add individually
weak directions — a conditioning warning worth carrying.

[Per-rung record](stage1_observability.json) · [script](stage1_observability.py)

## Stage 2 — does climbing help? NOT AS RUN

One bounded continuation from the saved `far-two-stars` state, with the promotion
rule and without it. Geometry and holdout error are recorded at every retained
rung and take **no part** in the promotion decision, which is training-only by
contract.

| Rung retained | Training loss | Matched error | Union IoU | Worst holdout |
|---|---:|---:|---:|---:|
| *start*, modes [1, 1] | 9.219e-05 | **7.595 mm** | **0.7468** | **1.003** |
| `t001` 1→3 | 8.817e-05 | 7.892 mm | 0.7459 | 1.002 |
| `t003` 1→3 | 8.515e-05 | 7.593 mm | 0.7458 | 1.005 |
| `t001` 3→4 | 6.814e-05 | 14.130 mm | 0.7223 | 1.007 |
| `t003` 3→4 | 5.228e-05 | 12.265 mm | 0.7167 | 1.036 |
| `t001` 4→5 | 4.640e-06 | 15.605 mm | 0.7000 | 1.161 |
| `t003` 4→5 | 1.374e-06 | 15.634 mm | 0.6952 | 1.147 |
| `t001` 5→6 | **3.717e-07** | 17.599 mm | 0.6383 | 1.514 |

All seven rungs were retained by the training-only rule. Training loss falls
monotonically by 248×; matched error, IoU and holdout error degrade
monotonically. On the metrics as gated, the best reconstruction in the climb is
the state it started from — which is what stopped the line, correctly, because
the contract's stage-2 predicate included boundary error.

Stage 3 then showed that most of that degradation is phase, on a truncated
ladder. The gate outcome stands; the mechanism behind it is not what it looked
like.

The control arm — the same state refined without promotion — moves nothing in 13
solves, confirming the state really was stationary and that everything above is
attributable to the promotion.

[Climb record](stage2_climb.json) · [script](stage2_climb.py)

## What this bundle establishes

- **The data is sufficient.** The truth fits to 3.23e-07 relative error on the
  training acquisition. Neither more frequencies nor regularization is what the
  frozen v1 shape failures are short of.
- **Bandwidth enrichment produces real shape.** A component that provably could
  only translate and scale became a five-lobed star of the right perimeter, area
  and isoperimetric ratio.
- **The optimizer cannot find the phase.** It lands 34° out and stays there,
  7.1e6× above the achievable objective.
- **The truncation mattered, and did not save the result.** Stage 4 ran the
  ladder to exhaustion at [9, 9]. The stage-2 cap had stopped it at its worst
  rung, so the recovered answer is better than stage 2 reported — 11.849 mm
  rather than 17.599 mm — but still worse than the circles it started from on
  every gated measure.
- **Bandwidth is necessary and not sufficient.** With every mode both truths
  require, the optimizer still sits 74,159x above the achievable objective.

The next question is globalization — escaping a local minimum that four orders
of magnitude of objective and a full mode ladder do not resolve — not
regularization, not acquisition, and no longer capacity. That needs its own
contract; nothing here authorizes one.

## Verification

Stages 1, 2 and 3 read saved artifacts and perform their own solves; no
inversion, oracle solve or benchmark run was repeated. The
[manifest](manifest.json) records the 155 hashed numerical sources and commit
`b7e7d03`. `pytest/sdf_inverse` reports **578 passed** ([log](tests.log)),
including fourteen geometry-and-gauge tests for the ladder that use no BIE solve.

This is a re-reading of artifacts by the implementation owner, not independent
scientific review. Reviewer: unassigned. The stage-3 correction was produced by
the same owner who wrote the reading it overturns.

Reproduce from the repository root:

```bash
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage1_observability.py
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage2_climb.py
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage3_correction.py
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage4_uncapped_ladder.py
```
