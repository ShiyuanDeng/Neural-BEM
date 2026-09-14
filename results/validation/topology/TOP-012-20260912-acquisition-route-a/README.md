# TOP-012 — route A: twice the angular coverage buys nothing, and here is why

Executes [TOP-012](../../../../docs/iterations/topology/iteration_08/02_proposals/02_acquisition_change.md)
under the [agreed plan](../../../../docs/iterations/topology/iteration_08/03_plan.md),
gated behind [TOP-011](../TOP-011-20260912-tolerance-sensitivity/README.md) as
its own contract requires.

**Route A** — more source/receiver pairs at the existing 0.5 GHz training
frequency — was the plan's choice because it is the only route that leaves the
evaluation contract intact. **1.5 and 2.5 GHz are never fitted here**, so the
frequency holdout keeps its meaning and every recorded holdout number stays
comparable. Routes B and C were not taken.

## What changed, and what did not

| | v1 | v2 (this bundle) |
|---|---|---|
| Specification | `config/topology_scenes_v1.json` | `config/topology_scenes_v2.json` |
| Version string | `topology-scenes-v1` | `topology-scenes-v2-acquisition-a` |
| Ring source/receiver pairs at 0.5 GHz | 24 | **48** |
| Ring standoff | 0.30 m | 0.30 m |
| Training frequencies | 0.5 GHz | 0.5 GHz |
| Holdout frequencies | 1.5, 2.5 GHz | 1.5, 2.5 GHz — **never fitted** |
| Scenes, truths, materials, resolutions, gates, controller policy, budgets | — | **identical** |

The two specifications differ in exactly two keys, `version` and `acquisition`,
and that is asserted in a regression test rather than claimed. The 48 positions
**strictly interleave** the frozen 24: at the shared positions the v2 oracle
reproduces the v1 observations to a relative difference of **0.0**, so v1's
angular coverage is a subset of v2's and the difference is added coverage, never
moved coverage.

**The v1 specification and every v1 bundle are byte-identical.** Nothing was
re-run, re-scored or overwritten, and no result here transfers back to v1. The
0.003 tolerance was not loosened and no gate was re-tuned.

## Stage 1 — the v2 oracle, checked rather than assumed

All twelve scenes generated fresh observations for the enriched acquisition and
passed the same 256 → 512 node convergence gate v1 used, at a worst relative
change of **1.21e-13** against the 1e-05 tolerance. Total 55.8 s.

## Stage 2 — the cheap half of the hypothesis, first

TOP-012's hypothesis is that richer data *shrinks the boundary displacement
permitted inside the data tolerance*. That is TOP-011's measurement with one
input changed, so it was run before the twelve-scene suite — an expensive
comparison should never be bought to answer a question a cheap one settles.

Same state, same 0.003 tolerance, same feasible set, same procedure. Acquisition
is the only difference.

| | v1 (24 pairs) | v2 (48 pairs) | Ratio |
|---|---:|---:|---:|
| Residual entries | 48 | 96 | |
| Relative L2 at the state | 6.7461e-05 | 8.1816e-05 | |
| …still inside the 0.003 tolerance | yes | **yes, 36.7× inside** | |
| Permitted movement, max | 6.8195 mm | **6.8186 mm** | **1.000×** |
| Permitted movement, median | 3.1370 mm | 3.1382 mm | 1.000× |
| …median over the weak half | 4.1883 mm | 4.1064 mm | **0.980×** |
| …median over the strong half | 0.3433 mm | 0.3433 mm | 1.000× |
| Directions permitting more than the 1 mm gate | 47 / 68 | **47 / 68** | 1.000× |
| Condition number | 1.2053e+05 | **1.2259e+05** | 1.017× — *worse* |
| Jacobian rank | 34 / 34 | 34 / 34 | |

**Doubling the angular coverage changed nothing.** The largest permitted
boundary movement moved by one part in ten thousand. The same 47 of 68
directions still permit more movement than the boundary gate. The conditioning
did not improve; it is 1.7% worse.

Note also the first row of that table on its own terms: a state fitted only to
the original 24 positions still satisfies the tolerance on the 24 it never saw,
at 8.18e-05. The new positions did not even *notice* the wrong geometry.

## Stage 2b — why, from the saved artifacts, at zero solve cost

| Quantity | Value |
|---|---:|
| v2 reproduces v1 at the shared positions | **exactly (0.0)** |
| ‖observed‖ ratio, v2 / v1 | **1.41421376** |
| √2 | 1.41421356 |
| Median singular-value ratio, v2 / v1, over 34 directions | **1.0000002** |
| …over the weak half | 1.0009 |
| …over the strong half | 1.0000000 |

The normalized residual divides by the observed column norm, so the norm ratio
matching √2 to seven digits says the added positions carry **exactly the same
response energy** as the original ones. Then

> `J₂ᵀJ₂ = (‖obs₂₄‖/‖obs₄₈‖)² · J₁ᵀJ₁ + Jₙₑwᵀ Jₙₑw = ½ J₁ᵀJ₁ + Jₙₑwᵀ Jₙₑw`

and an unchanged spectrum forces `Jₙₑwᵀ Jₙₑw ≈ ½ J₁ᵀJ₁`. **The new rows
reproduce the existing sensitivity structure direction for direction.** They add
no new direction and they do not reweight the ones already there.

That is the mechanism, and it is the expected physics: at 0.5 GHz the scattered
field around a 0.30 m ring is angularly band-limited to a handful of harmonics,
and 24 positions already sample it well above that band. Interleaving 24 more
resamples the same function.
