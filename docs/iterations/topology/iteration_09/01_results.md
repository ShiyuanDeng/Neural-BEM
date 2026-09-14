# Topology iteration 09 — the tolerance was never a geometric certificate, and more of the same data cannot make it one

TOP-011 and TOP-012 both completed on 2026-09-12 under the user's direction to
run them and keep iterating.
[Plan](../iteration_08/03_plan.md) ·
[TOP-011 results](../../../../results/validation/topology/TOP-011-20260912-tolerance-sensitivity/README.md) ·
[TOP-012 results](../../../../results/validation/topology/TOP-012-20260912-acquisition-route-a/README.md).

## The question these two answer

Four cycles found and fixed four real defects — the frozen-column derivative,
missing shape capacity, a truncated mode ladder, premature stopping. Every one
improved the training objective and **not one improved the reconstruction**. The
open question was why the gated geometry is insensitive to four orders of
magnitude of training objective.

The answer is in two parts, and only the first was expected.

## Part one — how much geometry the 0.003 tolerance leaves free

TOP-011 walked every right-singular direction of the reduced Jacobian, both
signs, at both saved `K = 9` states, and measured how far the boundary can move
while the **measured** relative L2 stays inside the frozen 0.003 tolerance.

**47 of 68 signed directions permit more boundary movement than the 1 mm
boundary gate itself.** The largest permits **6.82 mm**; the median 3.14 mm. The
weak half of the spectrum permits a median 4.19 mm against **0.34 mm** for the
strong half — a 12× concentration exactly where the contract predicted it.

Zero directions were refused. The feasible set never binds at the reported step,
so none of this is an artifact of the radius floor or either resolution.

So the 0.003 tolerance — which is also the controller's own `recovered` stopping
criterion at `topology_controller.py:795` — certifies a data fit and was never a
geometric certificate. It leaves about seven times the gate's own budget free.

## Part two — the derivative's validity radius, which nobody had looked at

The spectrum splits at rank 15, identically at both states. For ranks 0–14 the
linear model agrees with the measured objective to within 10% **out to the full
permitted step**. For ranks 15–33 it agrees at **no probed step at all**, down
to a quarter of that step, with errors of 0.12 to 16.7. At rank 33 it licenses a
step **4975× larger** than the objective permits.

The Jacobian is not wrong: stable to 3e-06 across three FD scales, full rank
34/34, zero unresolved columns. What is small is the neighbourhood it describes.
In the bottom nineteen directions the objective responds quadratically, so a
Gauss–Newton or LM step honest to its own model is confined to a region holding
a fraction of the millimetres those directions actually contain.

That is a statement about the optimizer's model rather than about the data, and
no earlier cycle had it.

## Scored against the truth, afterwards

Of the 68 permitted steps, 24 move closer to the truth and 44 move away. The
best single direction reaches 10.864 mm from 11.991 mm. The data cannot tell the
two apart: 4 mm toward the truth and 4 mm away from it both sit comfortably
inside the tolerance the controller trusts.

## Part three — richer data of the same kind changes nothing

The user's direction released TOP-012, and the plan took **route A**: more
source/receiver pairs at the existing 0.5 GHz training frequency. It is the only
route that leaves the evaluation contract intact — 1.5 and 2.5 GHz are never
fitted, so the frequency holdout keeps its meaning. Routes B and C were not
taken, and that is a recorded decision rather than a deferral by silence.

A new `config/topology_scenes_v2.json` doubles the ring to **48 pairs**,
strictly interleaving the frozen 24. At the shared positions the v2 oracle
reproduces the v1 observations to a relative difference of **0.0**, so v1's
coverage is a subset of v2's. All twelve scenes passed the same 256 → 512 node
convergence gate, worst relative change 1.21e-13.

The cheap half of the hypothesis ran first, before the suite:

| At the same state, same 0.003 tolerance | v1 (24 pairs) | v2 (48 pairs) |
|---|---:|---:|
| Permitted boundary movement, max | 6.8195 mm | **6.8186 mm** |
| …median over the weak half | 4.1883 mm | 4.1064 mm |
| Directions permitting more than the 1 mm gate | 47 / 68 | **47 / 68** |
| Condition number | 1.2053e+05 | **1.2259e+05** |

**Nothing moved.** And stage 2b says why, from the saved artifacts at zero solve
cost: the observed-norm ratio is **1.41421376** against √2 = 1.41421356, and the
singular values agree to seven digits. The added rows carry the same response
energy and reproduce the same singular directions with the same relative
weights — they **add no direction and reweight nothing**. At 0.5 GHz the
scattered field around a 0.30 m ring is angularly band-limited to a handful of
harmonics, and 24 positions already sample it well above that band.

Spatial sampling at the training frequency is therefore exhausted, and that is a
mechanism rather than a null result.
