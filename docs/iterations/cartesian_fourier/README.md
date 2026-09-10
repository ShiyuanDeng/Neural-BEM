# Cartesian Fourier iterations: start here

This is the handoff for agents working on the Cartesian-Fourier research cycle.
Read the current state below before choosing work. The shared folder convention
is in the [iterations README](../README.md).

## What this project is

A chart study. The authoritative optimization state is a **Cartesian Fourier
curve** `gamma(t)`, and the question is whether it reaches the accuracy the
radial Fourier chart already reaches on the same ellipse-to-star problem.

**No neural field participates.** The MLP is dropped for this cycle — not in the
loop, and not as an audit. That is a deliberate, temporary control, not a finding
about the implicit representation: the implicit-MLP cycle's
[gradient diagnosis](../implicit_mlp/iteration_03/02_proposals/04_claude_gradient_diagnosis.md)
cleared both leading gradient hypotheses, and that cycle remains open at its own
[iteration-3 plan](../implicit_mlp/iteration_03/03_plan.md). Nothing here closes it.

Topology is also out of scope for this cycle: one fixed component, no birth,
death, split or merge. That work lives in
[radial Fourier topology](../radial_fourier_topology/README.md).

## Current handoff

Updated 2026-09-10.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 02](iteration_02/01_results.md) |
| Stage | Iteration 1 executed; its results opened iteration 2. No iteration-2 proposal or plan yet |
| Reference to match | `results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904`: 44 accepted updates, train relative L2 `1.202 -> 1.068e-08`, holdout `1.133 -> 1.339e-08`, maximum boundary error `4.181e-02 -> 2.570e-10 m` |
| Decided before execution | Active band **6**, fixed by an exact algebraic identity, not tuned; polar-angle parameterization at initialization with **no arclength refit**; exact phase gauge projected out. Tangential motion was to be measured and not constrained; execution overturned that, see the amendment below |
| Execution status | Complete. Gates A-E pass as regression tests; the matched run converged in 41 accepted updates with zero backtracks |
| Current scientific outcome | Maximum boundary error `4.181e-02 -> 2.761e-09 m` in 41 accepted updates, against the radial reference's `2.570e-10 m` in 44. The geometric parity gate passes; the two data gates miss by 13% and 30%. The chart recovered exactly the predicted active modes 1, 4 and 6 |
| What decided it | Not bandwidth but parameterization drift, which the plan's section 4 got wrong; see its [amendment](iteration_01/03_plan.md). A gauge-fixing retraction was the fix |
| Next expected research action | Propose iteration-2 checks from the [candidates](iteration_02/01_results.md) in the results, the first being whether the re-gauge truncation is the accuracy floor |

## Read in this order

1. [Iteration-01 plan](iteration_01/03_plan.md): purpose, the band and
   parameterization decision and its evidence, the chart and optimizer changes,
   validation gates, the matched experiment, parity criteria and deferred work.
2. The reference radial run's `metrics.json` and `summary.md` under
   `results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/`.
3. For provenance only, the implicit-MLP cycle's
   [iteration-3 results](../implicit_mlp/iteration_03/01_results.md) and
   [plan](../implicit_mlp/iteration_03/03_plan.md). That cycle's direct-control
   design is where this project's chart question came from; its band, chart and
   arm structure are **not** inherited.

## The one result that shapes everything here

In the polar-angle parameterization the five-lobed star is exactly

```text
gamma_x = r0 cos(theta) + (r0 eps / 2) [cos(6 theta) + cos(4 theta)]
gamma_y = r0 sin(theta) + (r0 eps / 2) [sin(6 theta) - sin(4 theta)]
```

so it has exactly three active Cartesian modes — 1, 4 and 6 — and band 6
contains it to `6.4e-17 m`. Resampled to arclength the same target is not
band-limited at all: band 32 still leaves `1.069e-04 m`, band 48 leaves
`2.941e-05 m`. Choosing the parameterization, not the bandwidth, is what decides
whether the target is reachable. This is also why the implicit cycle's direct
control carried a `43.311 um` frozen-tail floor at B32 — Method B refits to
arclength.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| [01](iteration_01/03_plan.md) | Cartesian band-6 chart parity against the radial reference, MLP dropped | Closed; plan executed, with a recorded amendment to its gauge decision |
| [02](iteration_02/01_results.md) | Results of that run | Active; results recorded, proposals pending |
