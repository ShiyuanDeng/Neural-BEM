# Iteration 01 brief — where the inverse spends its time

2026-09-15. Gate-1 material for the [speed-up track](../../README.md). This is a
brief, not a result and not an approval: no numerical work was performed to
write it. Every number below is read out of ledgers that already exist in
committed or in-flight result bundles.

## 1. The profile

Production topology runs record work by stage through
`solvers/sdf_inverse/work_accounting.py`, so the breakdown is already on disk.
Summing `work.attempted` per stage:

| Bundle / scene | total forward solves | `derivative` | `candidate` | `acceptance_validation` | `endpoint` + `initial` | derivative share |
|---|---:|---:|---:|---:|---:|---:|
| TOP-024 arm A | 3748 | 3536 | 144 | 52 | 16 | **94.3%** |
| TOP-024 arm B | 3756 | 3536 | 152 | 52 | 16 | **94.1%** |
| TOP-025 `merge` | 4856 | 4620 | 88 | 78 | 70 | **95.1%** |
| TOP-025 `mixed` | 2260 | 2108 | 36 | 46 | 70 | **93.3%** |
| TOP-025 `repeated-birth` | 1090 | 1020 | — | — | 70 | **93.6%** |
| TOP-025 `far-two-circles` | 1034 | 952 | 4 | 8 | 70 | **92.1%** |
| TOP-025 `split` | 750 | 680 | — | — | 70 | **90.7%** |
| TOP-025 `death` | 750 | 680 | — | — | 70 | **90.7%** |
| TOP-023 (terminal-model diagnostic) | 396 | 320 | 72 | — | 4 † | 80.8% |

Sources: each bundle's `result.json` (`work.attempted`), and for TOP-024 the
per-arm `runs/{A,B}/result.json`. † TOP-023 is a single-state derivative
diagnostic rather than a recovery run: its four remaining calls are
`repeatability`, not endpoint scoring, and its four `candidate_*` damping stages
are pooled into the candidate column. It is listed for contrast, not as a
comparable run. TOP-025 was in progress when this was written,
so its rows are the scenes that had reached the F stage; the remaining scenes do
not change the picture.

**Between 90.7% and 95.1% of every forward solve a topology run performs is a
finite-difference Jacobian probe.** Line search, candidate evaluation,
acceptance validation and endpoint scoring together account for the rest.

This is not an accident of tuning. The optimizer is Levenberg–Marquardt on a
gauge-fixed subspace: at K=9 over two components the state has 76 raw
coefficients and **34 reachable directions**
(`polar_angle_gauge_tangent_basis`, `solvers/sdf_inverse/curve_updates.py:1398`,
dimension `2K−1` per Cartesian component). Central differences over 34 columns
cost `2 × 34 = 68` evaluations per Jacobian — the base point is served from the
optimizer's cache — and each evaluation is one paired multi-component solve per
training frequency. With four cumulative training frequencies that is 272
per-frequency linear systems for one Jacobian, against a handful of solves for
everything else in the iteration.

## 2. What that implies

If a mechanism reduces the cost of the derivative by a factor `r`, and the
derivative is a share `s` of the run, the end-to-end saving is

```
speedup = 1 / ( s/r + (1 - s) )
```

The profile makes `s` large, so `speedup` tracks `r` closely — which is the
whole reason to look at the derivative first:

| `s` | `r = 1.5` | `r = 1.87` | `r = 3` |
|---|---:|---:|---:|
| 0.91 | 1.39x | 1.66x | 2.13x |
| 0.95 | 1.44x | 1.75x | 2.50x |

The same arithmetic disposes of the alternatives, which is why this brief
recommends one candidate rather than surveying them:

- **Parallelism across FD columns.** The 34 probes are embarrassingly parallel
  and nothing in the optimizer is threaded today (confirmed: no
  `ThreadPoolExecutor`/`multiprocessing` anywhere in `radial_topology.py`,
  `topology_controller.py` or the Kress multicomponent assembly; the only
  thread pool in the stack parallelises independent scene/arm jobs in
  `run_topology_scene_benchmark.py:596`). This would help wall clock and not at
  all with solves, it competes for the same cores the campaign already runs four
  workers on, and it makes controlled timing claims harder rather than easier.
  Worth doing later; a poor first result.
- **Cheaper line search / candidate policy.** Attacks 5–9% of the run.
- **Reduced acquisition or fewer frequencies.** Changes what the inverse
  recovers, so by this track's scope boundary it is a topology or Boundary–BIE
  question, not a speed-up one.
- **Operator reuse.** Already measured and closed:
  [BIE-006](../../../../../results/validation/boundary_bie/BIE-006-20260915-205942-operator-reuse/README.md)
  found neither a wider accurate region nor a qualifying finite-reuse saving.

That leaves the derivative itself.

## 3. The candidate

[BIE-004](../../../../../results/validation/boundary_bie/BIE-004-20260915-coupled-02/README.md)
built and qualified a coupled analytic shape Jacobian for the actual
multi-interface Kress system — both directions of every cross-object
interaction, incident traces, receiver weights and normals — differentiating
`A U = B`, `Y = C U` as `A dU = dB − dA U`, `dY = dC U + C dU`, with one base LU
reused for all directions and all 24 source right-hand sides.

Measured, at 1.25 GHz and 256 nodes per object on a saved two-star state:

| | analytic | FD |
|---|---:|---:|
| Full 34-column Jacobian, median of 3 | **26.249 s** | 49.083 s |
| LU factorizations | **1** | 69 |
| RHS batches | 35 | 69 |

1.87x, with non-overlapping ranges and no concurrent numerical worker detected.
Accuracy: full residual Jacobian relative error **1.414e-7** (common) and
**1.405e-7** (terminal) against gauge-retracted central FD, worst column
4.647e-7, all 1008 scaled operator comparisons passing, Taylor ratios
4.0000–4.0006.

So `r ≈ 1.87` is measured rather than hoped for, and the profile gives
`s ≈ 0.91–0.95`. **The pre-registered prediction is 1.73x–1.79x end to end.**

Two honest deductions from that figure, both of which belong in the contract
rather than in a later erratum:

- BIE-004's FD arm used 69 factorizations where the production optimizer uses 68
  — the production base point is cached. The like-for-like per-Jacobian figure is
  therefore about **1.84x**, not 1.87x.
- Once the Jacobian is cheap, everything else becomes a larger share. 1.73–1.79x
  is an upper estimate for a repeat run, not a floor.

## 4. A second, smaller finding

Auditing the same bundles for the optimizer's constrained-differencing counters
gives an exact and somewhat surprising distribution:

| Scene (all `topology/topology_passes.json`) | one-sided columns | unresolved columns |
|---|---:|---:|
| TOP-025 `central-ellipse-star` | 55 | 0 |
| TOP-025 `far-ellipse-star` | 40 | 0 |
| TOP-025 `empty-ellipse-star` | 40 | 0 |
| TOP-025 `mixed` | 38 | 0 |
| TOP-025 `far-two-circles` | 32 | **2** |
| TOP-025 `repeated-birth` | 32 | 0 |
| TOP-025 `merge` | 16 | 0 |
| TOP-025 `split` | 16 | 0 |
| TOP-025 `death` | 6 | 0 |
| TOP-025 `far-two-stars`, TOP-022, TOP-020 | 2 each | 0 |
| **Total** | **281** | **2** |

Every one of the twelve non-zero files is a `topology/topology_passes.json`.
**Not a single constrained column occurs in the F continuation.** The feasible-FD
stencil TOP-008 introduced is exercised exclusively during the H phase, where
births and deaths put components near the feature-radius floor.

This matters because an analytic derivative has no notion of a refused probe. At
an active constraint the FD path either one-sides the quotient — first-order
accurate and biased, where the central quotient is second-order — or, when both
sides are refused, freezes the column to zero. The relevant test
(`pytest/sdf_inverse/test_feasible_finite_differences.py`) puts it exactly:
*"A probe the constraint refuses is not a derivative of zero."* The analytic
column is simply available in both cases.

So there is a possible accuracy improvement as well as a cost one, it is
**localised to topology events**, and it is worth roughly 283 columns across the
suite. It should be measured, not assumed: the true analytic column changes the
search direction, so it must be attributed separately from the saving. The
contract does that in two stages rather than folding it into one number.

## 5. Why this is not filed under Boundary–BIE

The Boundary–BIE track asks which properties of smooth-boundary representations
improve the accuracy, conditioning, differentiation or cost of the BIE inverse.
Building and qualifying the coupled derivative was that question, and BIE-004
answered it. Wiring an already-qualified derivative into the production
optimizer and measuring the resulting wall clock is a different activity: the
formulation, the discretisation, the gauge and the recovered geometry are all
meant to stay exactly where they are, and the deliverable is seconds.

Filing it here also gives the closed BIE-006 negative result and any future cost
work — parallelism, preconditioning, warm starts — a common place to be compared,
and keeps BIE's iteration history intact.

## 6. Recommendation

One experiment, `SPD-001`: promote the coupled derivative to production, wire it
into the single place the topology path takes finite differences, and validate
it in tiers — saved-state equivalence, then matched trajectory, then a bounded
scene A/B. Contract in
[`02_SPD001_contract.md`](02_SPD001_contract.md). It is
`PROPOSED — NOT APPROVED FOR EXECUTION`.
