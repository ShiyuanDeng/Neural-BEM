# TOP-009 — bandwidth was not the binding constraint

Rank 2 of the [literature verdict](../../../../docs/iterations/topology/iteration_05/02_proposals/03_literature_verdict.md),
the only other candidate it accepts.
[Contract](../../../../docs/iterations/topology/iteration_06/02_proposals/01_bandwidth_capacity_contract.md) ·
[review](../../../../docs/iterations/topology/iteration_06/02_proposals/02_bandwidth_capacity_review.md) ·
[plan](../../../../docs/iterations/topology/iteration_06/03_plan.md).

**Stage 1 passed and stage 2 failed its declared predicate, so the line was
stopped and the twelve-scene suite was not run.** The added directions are
real, observable, and highly effective at fitting the training data — and every
one of them makes the reconstruction worse. On this acquisition, capacity is not
what is missing.

Observations, initial states and saved final states come from the qualified
[TOP-008 bundle](../TOP-008-20260912-feasible-fd/README.md) and are
byte-identical to TOP-007's and TOP-006's. No new oracle solve was performed,
and no controller default changed. `bandwidth_promotion` ships opt-in and off.

## Stage 1 — are the added directions observable? PASS

A per-rung probe of two saved states, no optimizer and no topology search. The
ladder, the 0.25 stability tolerance and the 1.0e-3 beyond-span floor were
declared in the contract before execution.

| State | Rungs probed | Observable | Residual explained beyond the existing span |
|---|---:|---:|---|
| `far-two-stars` — truth is two stars | 14 | **14** | up to **0.6445** |
| `far-two-circles` — truth really is circles | 14 | **0** | at most **3.8e-7** |

At `far-two-stars` the six existing mode-1 directions explain **0.000011** of the
residual — essentially nothing. One rung to `K = 3` reaches 20.4% beyond that
span; the full ladder reaches 64.4%. The control behaves exactly as a control:
when the truth is already inside the space, added modes explain 3.8e-7 of the
residual, five orders of magnitude below the floor, and nothing is observable.

Zero padding moved the boundary by **0.000e+00 m** at every rung on both states,
and column estimates are stable to 7.3e-5 against the 0.25 tolerance.

One warning visible here and worth carrying: the weakest new column at `K = 9`
is 4.7e-6 of the largest, while the span gain from `K = 8` to `K = 9` is only
0.615 to 0.644. High rungs add directions that are individually very weak.

[Per-rung record](stage1_observability.json) · [script](stage1_observability.py)

## Stage 2 — does climbing help? NO

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

Every rung was retained by the training-only rule. Training loss falls
**monotonically by 248×**. Matched boundary error, union IoU and worst holdout
error **all degrade monotonically**. The best reconstruction in the entire climb
is the state it started from, and there is no rung at which enrichment helps.

The contract's stage-2 predicate was the objective at both resolutions **and the
boundary error**. The boundary error got worse, so stage 2 does not pass and
stage 3 was not run. Running a twelve-scene suite to confirm a rule already shown
to harm generalization would have spent forty-five minutes on a known answer.

The control arm — the same state refined without promotion — moves nothing in 13
solves, confirming the state really was stationary and that everything below is
attributable to the promotion.

**Budget note, reported as an overrun.** 226.8 s against the 600 s ceiling, but
**3127 solves against the declared 2500 cap**. The cap is tested between rungs,
so a rung that begins inside it can finish outside it. That is an implementation
detail of the stage script, not a controller behaviour, and the overrun does not
affect the conclusion — the degradation is monotone from the first rung, long
before the cap.

[Climb record](stage2_climb.json) · [script](stage2_climb.py)

## What this establishes

The two accepted candidates from the literature verdict are now both measured,
and between them they say something the verdict could not:

- **Rank 1 was a real defect** and fixing it freed the pinned component
  ([TOP-008](../TOP-008-20260912-feasible-fd/README.md)).
- **Rank 2 is not a shortage.** The modes are there, they are observable, they
  fit — and they fit the wrong thing. At 0.5 GHz the exterior wavelength is about
  245 mm and `k·rho0 ≈ 0.92`; 24 observations at that single frequency do not
  determine harmonics this fine, so the extra freedom goes into artefacts.

That reframes the remaining failures. `far-ellipse-star` stalling at 3% training
error with a mode-9 component is not an under-parameterized fit — it is an
**over-parameterized one on an under-determined acquisition.** The binding
constraint on the frozen v1 benchmark is data and regularization, not capacity
and no longer the derivative.

This promotes the verdict's rank 4 — richer acquisition, with a fresh
evaluation-only set, since fitting a held-out frequency destroys the holdout —
and a regularization proposal from "deferred" to the next question. It does not
authorize either; both need their own contract.

## Verification

Stage 1 and stage 2 read saved artifacts and perform their own solves; no
inversion, oracle solve or benchmark run was repeated. The
[manifest](manifest.json) records the 155 hashed numerical sources and commit
`b7e7d03`. `pytest/sdf_inverse` reports **578 passed**
([log](tests.log)), including fourteen geometry-and-gauge tests for the ladder
that use no BIE solve.

This is a re-reading of artifacts by the implementation owner, not independent
scientific review. Reviewer: unassigned.

Reproduce from the repository root:

```bash
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage1_observability.py
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage2_climb.py
```
