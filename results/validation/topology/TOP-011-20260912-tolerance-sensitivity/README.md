# TOP-011 — the 0.003 data tolerance certifies almost nothing about geometry

Executes [TOP-011](../../../../docs/iterations/topology/iteration_08/02_proposals/01_sensitivity_and_conditioning.md)
under the [agreed plan](../../../../docs/iterations/topology/iteration_08/03_plan.md).

**Diagnostic only. No source change, no controller default, no new arm, and no
state advanced or saved as a reconstruction.** Observations and saved states
come from the [TOP-008](../TOP-008-20260912-feasible-fd/README.md),
[TOP-009](../TOP-009-20260912-bandwidth-capacity/README.md) and
[TOP-010](../TOP-010-20260912-stopping-vs-stationarity/README.md) bundles. Truth
was read in a second pass, after every step had been chosen and measured.

## The headline

At the restart plateau, **47 of 68 signed singular directions permit more
boundary movement than the 1 mm boundary gate itself**, while the *measured*
relative L2 error stays inside the frozen 0.003 tolerance. At the ladder
endpoint it is 48 of 68.

| | Ladder endpoint | Restart plateau |
|---|---:|---:|
| Relative L2 at the state | 8.7878e-05 | 6.7461e-05 |
| …inside the 0.003 tolerance by | 34.1× | 44.5× |
| Directions measured / refused | 68 / **0** | 68 / **0** |
| Permitted boundary movement — max | **6.658 mm** | **6.820 mm** |
| — median | 3.055 mm | 3.137 mm |
| — min | 0.101 mm | 0.102 mm |
| — median over the **strong** half (ranks 0–16) | 0.353 mm | 0.343 mm |
| — median over the **weak** half (ranks 17–33) | **4.057 mm** | **4.188 mm** |
| Directions permitting more than the 1 mm gate | **48 / 68** | **47 / 68** |
| Distance from the truth at the state | 11.849 mm | 11.991 mm |

So the answer to "how much geometry hides inside the data tolerance" is: about a
twelvefold multiple of the gate that decides whether a reconstruction is
correct, concentrated exactly where the contract predicted — in the
weakly-constrained directions, at a **12× ratio** between the weak and strong
halves of the spectrum.

**The feasible set never binds.** Zero directions were refused by the radius
floor or by either resolution, and at the reported step the binding constraint
is the measured tolerance in 55–56 of 68 directions and the linear model's own
tolerance crossing in the remaining 12–13. Not one is limited by feasibility, so
none of this is an artifact of the guards.

## Movement against the spectrum

Permitted movement, in millimetres, larger of the two signs, at the plateau:

| Rank | σ | mm | Rank | σ | mm |
|---:|---:|---:|---:|---:|---:|
| 0 | 2.883e+01 | 0.106 | 17 | 3.685e-01 | 3.970 |
| 3 | 2.373e+01 | 0.140 | 19 | 2.158e-01 | **6.820** |
| 6 | 1.408e+01 | 0.206 | 20 | 1.432e-01 | 5.130 |
| 9 | 7.068e+00 | 0.460 | 23 | 3.967e-02 | 3.760 |
| 12 | 2.475e+00 | 1.154 | 26 | 1.532e-02 | 3.520 |
| 14 | 1.147e+00 | 2.142 | 30 | 2.704e-03 | 5.390 |
| 16 | 4.966e-01 | 4.003 | 33 | 2.392e-04 | 5.398 |

It climbs monotonically with falling σ to rank 19 and then **plateaus** at 3–6 mm
even though σ keeps falling another three orders of magnitude. That plateau is
the second finding.

## The linear model fails exactly where the movement is

| | Ladder endpoint | Restart plateau |
|---|---:|---:|
| Median relative error of the linear prediction | 3.047 | 2.932 |
| …over the strong half | **0.00085** | **0.00117** |
| …over the weak half | **20.71** | **23.62** |
| Worst | 380.5 | 562.5 |
| Probes agreeing within 10% | 114 / 343 | 119 / 348 |

In the strong directions the linear model is accurate to one part in a thousand.
In the weak ones it is wrong by factors of twenty to five hundred, and always in
the same direction: the true residual grows **much faster** than the derivative
says. At rank 33 the linear model licenses a step of 12.59; the measurement
permits 0.0025, five thousand times smaller.

So the weak directions are not data-blind. The objective responds to them
strongly; the **derivative** does not, because their leading response is
quadratic. That is what caps the permitted movement at ~6 mm instead of the
metres the spectrum alone would allow, and it is the contract's third decision
criterion firing on its own terms: the local model does not describe the
tolerance neighbourhood in the directions that matter.

### The validity radius, read from the same probes

`model_validity_radius.py` reads those probes back — **no solver runs** — and
splits the spectrum cleanly at rank 15, identically at both states:

| | Ranks 0–14 | Ranks 15–33 |
|---|---|---|
| Linear model within 10% | **out to the full permitted step** | **at no probed step at all** |
| Smallest fraction of the permitted step probed | — | 0.25–0.50 |
| Model error there | ≤0.10 | **0.12 – 16.7** (0.14 – 28.2 at the endpoint) |

The Jacobian itself is not wrong: it is stable to 3e-06 across the three FD
scales with zero unresolved columns. What the split says is that in the bottom
nineteen directions the model's **validity radius** is smaller than a quarter of
the step the tolerance permits. A Levenberg–Marquardt step confined to where its
own model holds moves the boundary by a fraction of the millimetres those
directions actually contain.

## Scored against the truth, afterwards

Of the 68 permitted steps, **24** move closer to the truth and 44 move further.
The best single direction reaches **10.864 mm** from 11.991 mm, and the best
union IoU reaches 0.7297 from 0.7088.

Two things follow, and they point in opposite directions:

- The tolerance ball is **not** centred on the truth, and no single singular
  direction inside it recovers the shape. The state is ~12 mm out; the largest
  permitted single-direction step is 6.8 mm.
- The data provides **no signal at all** about which way to go. Movement of
  4 mm toward the truth and 4 mm away from it are indistinguishable to the
  objective — both sit comfortably inside the tolerance the controller trusts.

This measures movement along **one singular direction at a time**. The full set
reachable inside the tolerance is larger, and its diameter is not measured here.

## Conditioning is stable, not a finite-difference artifact

Singular values agree to **2.3e-06 and 2.9e-06 relative** across FD steps
1.0e-4 / 5.0e-5 / 2.5e-5, at full rank 34/34, with zero one-sided and zero
unresolved columns at every scale. Spectrum: 2.883e+01 down to 2.392e-04,
condition number 1.205e+05 at the plateau and 1.383e+05 at the endpoint.

## What this decides

The contract's first criterion: **large displacement inside tolerance,
concentrated in small-σ directions**. The decoupling between the training
objective and the gated geometry is a conditioning and information problem, and
the named successor is acquisition — chosen against a measured spectrum rather
than guessed. [TOP-012](../TOP-012-20260912-acquisition-route-a/README.md) runs
route A on that basis.

What it does **not** license: loosening the 0.003 tolerance so the gate agrees
with the geometry. The honest reading is that the tolerance certifies a data
fit and was never a geometric certificate, and this is how much geometry it
leaves free.

## Work

| | Solves | Geometry checks | Seconds |
|---|---:|---:|---:|
| Both states | **1103** of the declared 1200 | 1930 | **194** of the declared 600 |

By category: 4 base, 408 Jacobian (two states × three FD steps), 691 tolerance
walk. Feasibility bisection builds curves rather than solving the BIE, so it
costs geometry checks and no solves — that is why the feasible set could be
searched exhaustively inside the budget.

## Files

| File | What it is |
|---|---|
| `tolerance_sensitivity.py` | The experiment. Diagnostic only |
| `tolerance_sensitivity.json` | Per-direction table, probes, spectra, truth scores |
| `execution.log` | Full run log |
| `manifest.json` | Source and configuration provenance |
| `model_validity_radius.py`, `.json` | Where the linear model stops describing, from the recorded probes; no solves |
| `write_manifest.py` | How the manifest was produced |
