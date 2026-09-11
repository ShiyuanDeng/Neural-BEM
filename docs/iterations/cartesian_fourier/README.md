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
cleared both leading gradient hypotheses. That cycle is now **paused by user
direction (2026-09-11)** at its own
[iteration-3 plan](../implicit_mlp/iteration_03/03_plan.md), which was never
executed. Paused, not closed: nothing here or there closes it.

Topology was out of scope for iterations 1 and 2 — one fixed component, no
birth, death, split or merge. **Iteration 3 removes that restriction**: the
chart now carries the same automatic topology controller the
[radial Fourier topology](../radial_fourier_topology/README.md) cycle built, at
the same declared recovery gates on all eight inverse cases, at comparable cost.
The automatic split retains a substantial geometric-accuracy gap.

## Current handoff

Updated 2026-09-10.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 03](iteration_03/03_results.md) |
| Stage | User-directed implementation executed and measured. Iteration 2's proposals remain unopened; iteration 3 answers its question 3 as a by-product |
| Latest contribution | [Topology in the Cartesian chart](iteration_03/03_results.md): all five automatic inversions recover with identical event sequences, all three challenge cases pass their declared gates, at comparable measured cost; see the split caveat |
| Iteration-3 references to match | `results/inverse/radial_fourier/topology_controller/iteration-02-20260909` (five automatic inversions) and `results/inverse/radial_fourier/topology_challenges/` (three challenge cases) |
| Iteration-3 execution status | Complete. Five inversions recover with identical event sequences; three challenge cases pass every declared gate; 13 new regressions, 505 passing in `pytest/sdf_inverse` |
| What iteration 3 settled | The gauge-fixed Cartesian chart is **not** distinguishable from the radial chart in what it can represent: its gauge-fixed set is a linear subspace, and that subspace is exactly the radial chart one band lower. Iteration 2's question 3, answered in the negative. Iteration 1's reported 2x cost gap also closed, and was a measurement artefact — the extra solves probed directions the gauge annihilates |
| Iteration-3 caveat | The `split` inversion recovers at `1.12e-05` relative against radial's `2.89e-07`, because the shared controller's finite candidate search selected a different cut. The pre-split geometries agree to `0.14 mm`; candidate-search sensitivity is a plausible explanation, not an isolated cause |
| Iteration-1 outcome, unchanged | Maximum boundary error `4.181e-02 -> 2.761e-09 m` in 41 accepted updates against the radial reference `mlp-radial-continuation-k5-ellipse-to-star-kress-20260904`'s `2.570e-10 m` in 44. Band **6** was fixed by an algebraic identity, not tuned; the geometric parity gate passes and the two data gates miss by 13% and 30% |
| What decided iteration 1 | Not bandwidth but parameterization drift, which its plan's section 4 got wrong; see the [amendment](iteration_01/03_plan.md). A gauge-fixing retraction was the fix, and iteration 3 found that one application of it is not enough |
| Next expected research action | **Forward-looking work has moved to the question-based tracks.** Iteration 3's topology candidates are carried by the [topology track](../topology/README.md); iteration 2's open re-gauge accuracy floor and the chart/gauge questions are carried by the [boundary–BIE track](../boundary_bie/README.md). Propose new bounded experiments there, under an experiment ID |
| Baseline | [B0 — 2026-09-10](../../baselines/B0_2026-09-10.md). Note that the September 10 audit revised this cycle's split geometry error from `295.9 um` to `175.21 um`; the dated bundle keeps its original value |

The [subsequent pipeline audit](../../../results/validation/cartesian_fourier/pipeline-audit-20260910/README.md)
records correctness fixes, fresh validation, and corrected geometry units.

## Relationship to the active tracks

This cycle is a **completed history**, not a paused queue. It is not moved,
renumbered or superseded, and its iteration folders stay exactly where they are.
Two question-based tracks now carry the forward work and cite this cycle as
starting evidence:

- [Topology](../topology/README.md) — iteration 3's candidate checks 1 and 2
  (split candidate-selection variance, and whether the polish budget is the
  actual lever) are the motivation for its first proposed experiment, `TOP-001`.
- [Boundary–BIE](../boundary_bie/README.md) — iteration 3's candidate checks 3
  and 4 (what the gauge buys, and what the un-gauged chart would cost) and
  iteration 2's re-gauge accuracy floor belong to its geometry-coordinates
  direction.

Neither track has an approved experiment. Nothing in this cycle's records
authorises work in either of them.

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
