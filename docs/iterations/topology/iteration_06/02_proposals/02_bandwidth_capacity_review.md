# Review of the TOP-009 contract

Self-review of [the contract](01_bandwidth_capacity_contract.md), written before
implementation. Accepted points are binding.

## 1. Where in the cycle does a promotion happen? — ACCEPTED

The contract says what a promotion is but not when it is attempted, and the
answer changes both the cost and what the experiment means.

Rejected: attempting promotion every cycle (it competes with topology events
that are still making progress, and multiplies cost on scenes that do not need
it); and treating promotion as another topology candidate (it changes no
component count, so it would consume the event budget and pollute the event
record).

**Resolution:** a promotion is attempted **only when the cycle would otherwise
stop** — when no topology candidate was accepted and the controller is about to
report `topology_stationary`. That is exactly the observed failure mode: runs
stop with the correct component count and the wrong shapes. It costs nothing on
scenes still making topology progress, and it makes the intervention a last
resort rather than a competitor.

## 2. One component at a time, or all of them? — ACCEPTED

Promoting every component at once conflates their contributions: a retained
promotion could be carried entirely by one component while another is being
paid for and doing nothing.

**Resolution:** components are tried in ladder order — lowest current bandwidth
first, ties broken by `component_id` for determinism — each evaluated
independently against the same base, and **at most one is retained**. The
objective change is then attributable to exactly one component and the
retain/revert decision is unambiguous.

Amended during implementation: an earlier wording said one component per cycle
and deferred the rest to the next stationary cycle. That is wrong for the case
this contract exists for — `far-two-stars` has *two* mode-1 components, and if
the first one's promotion is refused the run stops and the second is never
reached. Trying each in order within the stationary cycle keeps attribution
intact and does not strand the second component. The cost is bounded by the
component count, and only in a cycle that was about to end the run anyway.

## 3. The fine ladder is expensive — ACCEPTED, with the cost declared

"Smallest `K` that adds gauge directions" means 1 → 3 → 4 → 5 → … → 9, up to
seven rungs. At `K = 9` one Jacobian is 17 directions, so a refinement there
costs roughly 34 solves an iteration. A component that climbs the whole ladder
is expensive, and the frozen benchmark's ten-minute per-run ceiling is real.

Rejected: a coarse ladder such as 1 → 3 → 5 → 9. It is cheaper but the step size
is arbitrary, and arbitrary constants chosen by the implementer are what the
verdict warns against.

**Resolution:** keep the generic rule and declare the cost. The promotion rule
stops a component climbing at its first reverted rung, so a component that
cannot use `K = 4` never pays for 5 through 9. The plausible bad outcome is
**more timeouts, not more passes**, on the three scenes that already time out.
That is stated now so it cannot be presented later as a surprise.

## 4. Conditioning — ACCEPTED as a measurement, not a mitigation

Added modes raise the condition number of the normal equations, and the verdict
cites Borges and Greengard on excess bandwidth permitting instability. This
contract adds no regularization to compensate, which is deliberate: adding both
capacity and a new regularizer at once would make the result uninterpretable.

**Resolution:** stage 1 measures new-column sensitivity against the solver's
numerical noise and the residual reduction available beyond the existing span,
before any promotion is taken. If conditioning is the binding problem, that is
the measurement that shows it, and the answer is a separately reviewed
regularization proposal — not a quiet damping change inside this one.

## 5. Zero padding must survive the gauge — ACCEPTED

The padded state is immediately gauge-fixed like any other, and a gauge
re-parameterization of an unchanged curve must leave the geometry alone. This is
asserted rather than assumed: the boundary and the production objective are
compared before and after padding at every rung, and a mismatch aborts the
promotion. A silent change here would look exactly like a promotion that helped.

## 6. Does promotion interact with later topology events? — DEFERRED, bounded

A promoted component can subsequently be split, merged or removed, and candidate
construction reads `maximum_mode`. Nothing in the design forbids this and the
existing machinery should carry it, but this contract does not test it
specifically.

**Resolution:** stage 3 reports final mode counts per component alongside the
event record, so an interaction would be visible. If one appears, it gets its
own case rather than being patched inside this cycle.

## 7. Should this build on TOP-008 or on G? — ACCEPTED

The verdict said to compare future interventions against guarded G, written
before TOP-008 existed. Building rank 2 on the uncorrected stencil would mean
the promoted component's new directions are measured by a Jacobian that freezes
refused columns — testing rank 2 through the defect rank 1 just fixed.

**Resolution:** the baseline is the qualified TOP-008 arm, with
`bandwidth_promotion` as the only difference. If TOP-008's stage 3 does not
qualify, this decision is revisited before stage 3 rather than carried forward
silently.

## 8. Scope — REJECTED for widening

Not in this contract: any relaxation of the floor or headroom rule (rank 6/7,
deferred and rejected), multi-frequency acquisition (rank 4, deferred),
analytic derivatives (rank 5, deferred to the boundary–BIE track), solver
replacement (rank 8), representation replacement (rank 9). The temptation is
rank 4 — more frequencies would plausibly make fine harmonics observable — and
it is exactly the deferral the verdict argues for, since fitting on a held-out
frequency destroys the holdout.

## Binding outcome

Points 1, 2, 3, 4, 5 and 7 are binding on the implementation. Point 6 is a
reporting requirement. Point 8 is a refusal to widen.
