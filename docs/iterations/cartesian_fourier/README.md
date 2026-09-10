# Cartesian Fourier iterations: start here

This is the handoff for agents working on the Cartesian-Fourier research cycle.
Read the current state below before choosing work. The shared folder convention
is in the [iterations README](../README.md).

## What this project is

A chart study. The authoritative optimization state is a **Cartesian Fourier
curve** `gamma(t)`, and the question is whether it reaches the accuracy the
radial Fourier chart already reaches — first on one fixed-topology
ellipse-to-star problem (iterations 1 and 2), then on the whole automatic
topology suite (iteration 3).

**No neural field participates.** The MLP is dropped for this cycle — not in the
loop, and not as an audit. That is a deliberate, temporary control, not a finding
about the implicit representation: the implicit-MLP cycle's
[gradient diagnosis](../implicit_mlp/iteration_03/02_proposals/04_claude_gradient_diagnosis.md)
cleared both leading gradient hypotheses, and that cycle remains open at its own
[iteration-3 plan](../implicit_mlp/iteration_03/03_plan.md). Nothing here closes it.

Topology was out of scope for iterations 1 and 2 — one fixed component, no
birth, death, split or merge. **Iteration 3 removes that restriction**: the
chart now carries the same automatic topology controller the
[radial Fourier topology](../radial_fourier_topology/README.md) cycle built, at
that cycle's accuracy and cost, on all eight of its inverse cases.

## Current handoff

Updated 2026-09-10.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 03](iteration_03/03_results.md) |
| Stage | User-directed implementation executed and measured. Iteration 2's proposals remain unopened; iteration 3 answers its question 3 as a by-product |
| Latest contribution | [Topology in the Cartesian chart](iteration_03/03_results.md): all five automatic inversions recover with identical event sequences, all three challenge cases pass their declared gates, at equal cost |
| Iteration-3 references to match | `results/inverse/radial_fourier/topology_controller/iteration-02-20260909` (five automatic inversions) and `results/inverse/radial_fourier/topology_challenges/` (three challenge cases) |
| Iteration-3 execution status | Complete. Five inversions recover with identical event sequences; three challenge cases pass every declared gate; 13 new regressions, 505 passing in `pytest/sdf_inverse` |
| What iteration 3 settled | The gauge-fixed Cartesian chart is **not** distinguishable from the radial chart in what it can represent: its gauge-fixed set is a linear subspace, and that subspace is exactly the radial chart one band lower. Iteration 2's question 3, answered in the negative. Iteration 1's reported 2x cost gap also closed, and was a measurement artefact — the extra solves probed directions the gauge annihilates |
| Iteration-3 caveat | The `split` inversion recovers at `1.12e-05` relative against radial's `2.89e-07`, because the shared controller's finite candidate search selected a different cut. The pre-split geometries agree to `0.14 mm`; this is search-path variance, not a chart property |
| Iteration-1 outcome, unchanged | Maximum boundary error `4.181e-02 -> 2.761e-09 m` in 41 accepted updates against the radial reference `mlp-radial-continuation-k5-ellipse-to-star-kress-20260904`'s `2.570e-10 m` in 44. Band **6** was fixed by an algebraic identity, not tuned; the geometric parity gate passes and the two data gates miss by 13% and 30% |
| What decided iteration 1 | Not bandwidth but parameterization drift, which its plan's section 4 got wrong; see the [amendment](iteration_01/03_plan.md). A gauge-fixing retraction was the fix, and iteration 3 found that one application of it is not enough |
| Next expected research action | Propose the next bounded experiment from [iteration 3's candidates](iteration_03/03_results.md) or [iteration 2's](iteration_02/01_results.md). The open iteration-2 question about the re-gauge accuracy floor is unaffected by iteration 3 |

## Read in this order

1. [Iteration-03 results](iteration_03/03_results.md) and its
   [implementation record](iteration_03/02_implementation.md), if you are here
   for topology. The implementation record is written around the five failures
   that shaped the design and is the more useful of the two to read first.
2. [Iteration-01 plan](iteration_01/03_plan.md): purpose, the band and
   parameterization decision and its evidence, the chart and optimizer changes,
   validation gates, the matched experiment, parity criteria and deferred work.
3. The reference radial run's `metrics.json` and `summary.md` under
   `results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/`.
4. For provenance only, the implicit-MLP cycle's
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
| [02](iteration_02/01_results.md) | Results of that run | Closed for the topology question; its other candidate checks remain open |
| [03](iteration_03/03_results.md) | Topology treatments in the Cartesian chart, matched against the radial topology suites | Active; user-directed implementation executed, all eight cases measured |
