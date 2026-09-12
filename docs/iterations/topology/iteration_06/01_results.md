# Topology iteration 06 — the derivative was wrong; the shapes are still the problem

TOP-008 completed on 2026-09-12, implementing rank 1 of the
[literature verdict](../iteration_05/02_proposals/03_literature_verdict.md).
[Full results](../../../../results/validation/topology/TOP-008-20260912-feasible-fd/README.md).
The intervention is one opt-in stencil change in the fixed-topology optimizer.
The frozen twelve-scene v1 benchmark, its observations, budgets and gates are
unchanged, and both controller defaults are untouched.

## What was actually wrong

`jacobian()` abandoned both sides of a difference quotient when either
retraction failed, and wrote a zero column when either evaluation did. A refused
probe means a step is inadmissible; it does not mean the derivative is zero. The
normal equations then consumed a number nothing measured. Separately, both
`gradient_tolerance` branches could certify convergence from exactly those
zeros, which the other two tolerance branches already refuse to do.

## The three stages

**Stage 1 — the derivative model. PASS.** A per-direction probe of two saved
states, no optimizer. At the pinned `far-ellipse-star` state, **15 of 20 gauge
directions are refused on exactly one side and none on both**, so every frozen
column is recoverable — the open question the verdict flagged, settled
favourably. Estimates are stable across the declared 0.5h/h/2h sequence to
7.2e-3 worst relative drift against a 0.25 tolerance, and where a central
difference also exists the one-sided estimate differs by at most 4.5e-3. The
mixed-order Jacobian the correction assembles is therefore a measured, small
effect rather than an assumed-safe one.

**Stage 2 — a feasible decrease. PASS.** One bounded continuation from that
state, run with each stencil, inside all declared budgets:

| | Frozen columns | Feasible columns |
|---|---|---|
| Iterations taken | **0** | 22 |
| Refined loss | 4.695e-4 | **1.029e-4** |
| Matched boundary error | 18.624 mm | **9.070 mm** |
| Pinned component's radius certificate | 8.000 mm | **22.737 mm** |

The frozen arm takes zero steps: every direction that would move the pinned
component is a zeroed column, so there is nothing to descend. The corrected one
leaves the floor entirely. It stopped at `maximum_iterations`, still improving,
so that is a lower bound and not a converged answer — and 9.07 mm is still far
outside the 1-mm gate. The component moved; it did not arrive.

**Stage 3 — the frozen benchmark. NO NEW PASS.** H returns 10/12 against G's
9/12, and **both still pass 5/12**.

| Scene | Change under H |
|---|---|
| `central-ellipse-star` | **Completes** where G times out: 9.22 mm, 0.777 IoU |
| `split` | 0.175 mm → **0.000023 mm**, holdout 1.13e-2 → **3.24e-6**, 1172 → **281 solves** |
| `far-two-stars` | **Identical** to G — the control with no constrained direction |
| `far/empty-ellipse-star` | **Mixed**: boundary 18.62 → 17.62 mm, training error *worse* 3.06e-2 → 6.45e-2 |

Arm G reproduces TOP-007 exactly on all nine completed scenes. Verification
passes every check.

## What this cycle establishes, and what it does not

It establishes that the derivative model was invalid, that the invalidity was
what pinned the mode-9 component, and that correcting it frees that component
and makes one scene converge that previously ran out of time. `split` becoming
four times cheaper and five orders of magnitude more accurate is a real gain
that the pass count does not show.

It does not establish that the correction recovers any failing scene. The pass
count is unchanged, and on the two ellipse/star scenes a better-measured
Jacobian changed *where* the run went, improving boundary error while making the
training residual worse. That is the Borges–Rachh caution the verdict cited,
observed directly: a better optimizer is not the same thing as a better
reconstruction.

Every guarded run used at least one one-sided column, so the declared "inert
wherever no column is one-sided" check again has no members. The identical
`far-two-stars` final state stands in its place, recorded per scene rather than
claimed as a check that applied.

## Adoption

`feasible_fd_jacobian` stays **opt-in** this cycle. Two defaults are now pending
the same decision — this and `refined_feasibility_guard` — and flipping either
changes the reference behaviour TOP-001 and TOP-005 replay bundles reproduce
against. That decision should be taken once, in a declared comparison, rather
than twice in two closeouts.

## Next

Rank 2 of the verdict, the only other candidate it accepts:
[TOP-009](../iteration_05/02_proposals/06_bandwidth_capacity_contract.md),
controlled bandwidth enrichment. `far-two-stars` is the case — two Cartesian
mode-1 components against a five- and a seven-lobed star, nothing pinned, 1.4%
of the training residual unexplained, and its final state bit-identical under
both stencils. Under the polar-angle gauge, `K = 1` and `K = 2` carry the same
three directions, so that component provably cannot become a star. Whether the
added directions are observable from 24 observations at one frequency is the
question stage 1 of that contract measures.

No controller default, gate, scene or budget changed in this cycle.
TOP-002–TOP-004 remain deferred proposals.
