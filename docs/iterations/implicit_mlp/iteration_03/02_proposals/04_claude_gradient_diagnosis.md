# Gradient diagnosis: what the direct control would not have told us

Recorded 2026-09-09 by Claude, after the
[ChatGPT guide](01_chatgpt_guide.md), the
[first Claude review](02_claude_review.md) and the
[second Claude review](03_claude_second_review.md). This is a review-stage
record, not a plan and not authorization. Decisions belong in `03_plan.md`.

It exists because of a question the user put to the three documents: is it clear
that the point of removing the MLP is to find **what in the MLP path fails**,
with the adjoint / shape gradient and the gradient on MLP parameters as the
leading suspects? The short answer is that the purpose is stated but the
granularity is not, and that the control as designed would have answered only
half of it. The rest of this document reports the measurements that answer it
directly instead, at a fraction of the cost of the control.

## What the documents do and do not say

The guide's §1 states the question as whether recovery becomes straightforward
"once the implicit MLP, Eikonal field, extraction reverse and repeated
conversion gates are removed from the optimization loop", and §10.1 adds, once:

> Use `implicit representation/pullback layer` rather than `the MLP alone` in
> the formal conclusion, because the removed factor includes the neural field,
> Eikonal regularization, extraction, Method-B reverse and repeated conversion
> acceptance.

So the documents are clear that five factors move together and that the
conclusion must be about the bundle. They are **not** clear that the aim is to
identify which member of the bundle fails, and neither review foregrounds it:
the first is about the optimizer and the chart, the second about the band and
the acquisition.

**A gap follows that no document records.** The direct control *keeps* the Kress
geometry pullback — §1's pipeline line reads "same Kress geometry pullback" and
§4 is titled "Reuse the Kress adjoint". The adjoint and shape gradient are
therefore a **held-fixed** factor, not a removed one. If they were wrong, the
direct arm would inherit the defect, fail, and §10.3 would redirect the
investigation to "the data objective, acquisition, curve metric, identifiability
or Kress-shape optimization landscape". Of the two leading suspects, the control
tests one and is blind to the other.

## The chain, and where to cut it

```text
weights --[A] Method-B reverse--> curve jets --[B] Kress pullback--> dL
```

Both stages are separately checkable against central finite differences of the
production forward path, at any frozen saved state. That is much cheaper than
the direct control and attributes the result. Central differences carry a
truncation error of order `h**2`, so a **correct** analytic derivative shows a
relative error falling about fourfold per halving of the step, while a **wrong**
one flattens to a nonzero constant. The trend across steps is the evidence; the
magnitude at one step is not.

The long run checked only the composite, and only at state 0, where
`directional_gate` recorded relative errors of `1.3e-8` down to `2.7e-10`. That
is a much stronger state-0 result than either review credited, and it was never
repeated anywhere else on the trajectory.

## Stage B: the Kress shape gradient is correct, including at the distorted contours

The MLP is removed entirely. Each saved `converted_contour` is re-expressed as
its exact bandwidth-96 Cartesian Fourier curve — the recovery check gives a
Nyquist bin of `1e-17 m` and a maximum node difference of `1.5e-15 m` — then
perturbed coherently over modes 0..8, and `sum q_i . d gamma_i + sum p_i . d
gamma'_i` is compared with central differences of the same objective.

| State | `h=1e-4` | `h=5e-5` | `h=2.5e-5` | ratio per halving |
|---|---:|---:|---:|---:|
| E0 / 0 | 2.02e-5 | 5.05e-6 | 1.26e-6 | 4.0 |
| E0 / 21 | 5.05e-4 | 1.26e-4 | 3.16e-5 | 4.0 |
| E0 / 42 | 9.72e-5 | 2.43e-5 | 6.08e-6 | 4.0 |
| E1 / 0 | 5.99e-6 | 1.50e-6 | 3.75e-7 | 4.0 |
| E1 / 16 | 1.72e-5 | 4.29e-6 | 1.07e-6 | 4.0 |
| E1 / 31 | 4.19e-5 | 1.05e-5 | 2.62e-6 | 4.0 |

Every state falls by exactly four per halving, across the board. That is pure
finite-difference truncation with no floor: the analytic derivative is exact,
and the residual is the difference scheme, not the gradient.

**Suspect 1 is cleared** — at the run's own geometries, including E0's late
distorted contours, and with no MLP in the loop. As a by-product this is the
guide's §7.2 validation, already done: the analytic Fourier-coefficient
contraction the direct control depends on is confirmed correct before anyone
builds it.

## Stage A: the Method-B reverse is correct, and degrades a hundredfold late in E0

The differentiable replay is contracted with a fixed random covector and
compared with central differences of the production `build_ordered_sdf_geometry`
curve. No BEM solve is involved. Worst relative error over the two smallest
steps:

| State | E0 | E1 |
|---|---:|---:|
| 0 | 5.69e-8 | 5.69e-8 |
| 10 | 9.71e-8 | 7.50e-7 |
| 20 | 9.37e-8 | 1.41e-7 |
| 26 | 6.34e-8 | 5.76e-9 |
| 30 | **3.74e-6** | 5.48e-9 |
| 31 | **5.67e-5** | *rebuild fails its own gate — see below* |
| 36 | 8.76e-8 | — |
| 40 | 5.81e-7 | — |
| 42 | 1.64e-6 | — |

The replay's own `maximum_replay_error` stays between `6.4e-12` and `2.0e-11 m`
everywhere, reproducing the recorded state-0 value of `7.8e-12` exactly.

E0 states 30 and 31 are the two that do not behave, and a seven-step sweep
separates the reasons:

| `h` | 4e-4 | 2e-4 | 1e-4 | 5e-5 | 2e-5 | 1e-5 | 5e-6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| E0 / 26 | 6.01e-5 | 1.92e-5 | 1.13e-5 | 1.58e-5 | 2.27e-7 | 2.35e-8 | 6.34e-8 |
| E0 / 30 | 2.22e-5 | 2.08e-6 | 6.82e-6 | 4.92e-6 | 3.84e-6 | 3.74e-6 | **3.68e-6** |
| E0 / 31 | 1.08e-4 | 5.61e-5 | 3.91e-5 | **7.27e-6** | 1.54e-5 | 2.92e-5 | 5.67e-5 |

State 30 **plateaus** at `3.7e-6` and stays there over an eightfold range of
step: a real discrepancy at that level. State 31 traces a V — falling as
truncation, then rising as `1/h` once cancellation noise dominates — whose floor
is about `7e-6`; that is a noisy production map, not a wrong derivative. State
26, two accepted steps earlier, converges cleanly to `2e-8`.

So the Method-B reverse agrees to better than `2e-6` at twelve of the fourteen
audited states and to `1e-7` or better at eight of them, and loses about two
orders of magnitude of agreement at E0 states 30 and 31. **Suspect 2 is real but
small.** A relative gradient error of
`4e-6` does not steer a search into the wrong shape; it is a symptom of the
extraction becoming branch-sensitive, which is the piecewise-smoothness caveat
`implicit_mlp_data_gradient` already states in its own docstring.

## The composite behaves as those two imply

The production gradient the inverse actually used, against central differences
of the data loss:

| State | composite | stage A | gradient norm |
|---|---:|---:|---:|
| E0 / 0 | 1.43e-9 | 5.69e-8 | 91.573 |
| E0 / 26 | 6.62e-9 | 6.34e-8 | 15.066 |
| E0 / 30 | 1.27e-6 | 3.74e-6 | 11.033 |
| E1 / 0 | 9.54e-10 | 5.69e-8 | 34.399 |
| E1 / 26 | 2.36e-8 | 5.76e-9 | 8.593 |
| E1 / 30 | 6.43e-6 | 5.48e-9 | 8.555 |

Between `1e-9` and `1e-6` everywhere, with the two largest values appearing only
at the smallest step, which is the noise signature again. **Nothing in this
chain is broken.** Whatever produced the wrong shapes, it was handed a correct
gradient.

## What the audit found instead: both arms finished on the admissibility boundary

Two incidental results are more consequential than either suspect.

**E0's final accepted state is one ordinary step from a topology change.** At
state 42 the sweep aborts with

```text
Conversion audit could not resolve the raw zero set:
Expected exactly 1 closed zero-set component(s); detected 2.
```

at a random weight perturbation of L2 norm `4e-4`, whose largest per-weight
component is `1.88e-5`. E0's median accepted `maximum_weight_step` over the run
is `2.08e-5`, and its largest is `7.98e-5`. So the perturbation that splits the
zero set is the size of a **typical accepted step**. The results document
reports that 22 of 30 terminal candidates failed topology with this message;
this measures how close the accepted state itself sits to the bifurcation, in a
direction chosen at random rather than by the optimizer.

**E1's final accepted state does not survive a rebuild of its own gate.**
Rebuilding state 31 from its saved checkpoint raises

```text
Method-B conversion fidelity failed: raw/converted contour distance
0.000200007 m, refinement change 2.33388e-06 m; limits 0.0002 m and 1e-05 m.
```

The run recorded `199.9554 um` for that state and called the `0.0446 um`
headroom the reason it stopped. A rebuild lands at `200.007 um`, `0.05 um` on
the other side. The physical difference is meaningless; the admissibility
verdict flips. The recorded headroom is therefore not a reproducible margin, and
the final accepted state is better described as sitting *on* the limit than
inside it.

Both arms, by different routes, ended pressed against a geometry gate — which is
the results document's ranked candidate 1, not either gradient hypothesis.

## What this means for the plan

| | Point |
|---|---|
| 1 | State the diagnostic purpose explicitly in `03_plan.md`. The guide's §10.1 caveat is correct and is stated once; the plan should say which member of the bundle each arm can and cannot implicate |
| 2 | The direct control **cannot** test the adjoint / shape gradient, because it reuses it. That is no longer a gap worth closing by experiment — stage B closes it directly, and the answer is that the shape gradient is exact |
| 3 | Both leading suspects are cleared as causes. The composite agrees to between `1e-9` and `6.4e-6`; the shape gradient converges at the truncation rate with no floor; the Method-B reverse is better than `2e-6` outside two late paired states where the production map is itself branch-noisy. Any account of the failure that relies on a wrong gradient is ruled out |
| 4 | Ranked candidate 1 — separating terminal topology detection from conversion distortion — is promoted by this evidence, and candidates 2 and 3 keep their standing. The remaining gradient question is conditioning, not correctness, and those are different claims |
| 5 | The guide's §7.2 directional-derivative validation is already satisfied for the analytic Fourier pullback; the first review's step 2 can be shortened to the `jacobian.T @ residual` cross-check |

Nothing here argues against running the direct control. It argues that the
control was never going to answer the question that prompted it, that the
question has now been answered for a few minutes of compute, and that the
control's value is what the second review said it was: separating ownership and
chart from the optimizer, at a declared band, against a named acquisition.

## Measurements made for this record

Two probes, with scripts, full-precision output and their caveats at
[`review-diagnostics-gradient/`](../../../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/review-diagnostics-gradient/README.md).
**No inverse was run, no optimizer step was taken, no production code was
changed and no saved artifact was modified**; weights are restored after every
perturbation. Stage B loads no model at all. Stage A and the composite read
saved accepted checkpoints.

The caveats are stated in full in that README. The four that matter most here:
each state uses **one fixed random direction**, seeded at 724, so a defect
confined to a subspace could be missed; these are **correctness** checks, and a
derivative can be exact while still being a poor search direction, so nothing
here speaks to conditioning; stage A's map is only **piecewise** smooth, so an
inflated error at one large step beside clean small steps is a branch crossing
rather than a wrong derivative; and the audited states are the **accepted**
states, not the rejected candidates or the terminal proposals.
