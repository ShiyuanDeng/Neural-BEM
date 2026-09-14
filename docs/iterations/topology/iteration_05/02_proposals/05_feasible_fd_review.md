# Review of the TOP-008 contract

Self-review of [the contract](04_feasible_fd_contract.md), written before
implementation. Each point is resolved as accepted, rejected or deferred, and
the accepted ones are binding on the implementation.

## 1. Mixed-order columns — ACCEPTED, with a recorded limitation

A central difference is second-order accurate in `h`; a one-sided difference is
first-order. Arm H therefore assembles a Jacobian whose 5 central columns and 15
one-sided columns do **not** carry comparable truncation error, and
`matrix.T @ matrix` mixes them without weighting.

Rejected remedies: a larger step on the one-sided side (it would probe a
displacement the optimizer never takes, and at this state the feasible side is
bounded by the floor anyway); a second-order one-sided stencil using two points
on the same side (it doubles the solve cost of 15 of 20 columns for an accuracy
the stage-1 sequence has not yet shown to be the binding error).

**Resolution:** keep the configured step on both stencils, and make the
mixed-order structure a declared property measured in stage 1 rather than a
hidden one. If the three-size sequence shows the one-sided columns dominating
the model error, that is a stage-1 stop and a finding, not something to patch
mid-run.

This is a real cost of the narrow fix and it is worth stating plainly: a
first-order estimate of a column is unambiguously better than a fabricated zero,
and unambiguously worse than a central estimate.

## 2. The base residual must be the gauge-fixed base — ACCEPTED

A one-sided quotient needs `r(x)`, which the current `jacobian()` never uses.
The base state passed in is already gauge-fixed at every call site, but the
implementation must obtain `r(x)` through the same cached `evaluate()` the
probes use, so the base residual is the one the optimizer actually holds and
costs no extra solve. Forming it any other way risks a gauge mismatch that
would appear as a spurious derivative.

Sign convention is fixed here to remove the ambiguity the verdict warns about:
forward is `(r(R(+hd)) - r(x)) / h`, backward is `(r(x) - r(R(-hd))) / h`. Both
estimate `+Jd`. A unit test asserts both against an analytic residual with a
known one-sided answer, with no BIE solve.

## 3. "Frozen" changes meaning when the flag is on — ACCEPTED

`stop_reason = "infeasible_jacobian" if frozen_columns else ...` is correct only
if `frozen_columns` continues to mean *no derivative information was obtained*.
Under the fix a one-sided column is information, so it must not count as frozen.
The implementation therefore reports two separate counts — one-sided and
unresolved — and only the unresolved count drives the stop reason and the
convergence guards. With the flag off both counts reduce to today's behaviour.

## 4. Attribute access on stubbed results — ACCEPTED

TOP-007 broke four controller tests by reading a new `MultiRadialFDResult`
attribute unconditionally, because existing tests stub the result with
`SimpleNamespace`. The same mistake is available here. New attributes are read
**only when `feasible_fd_jacobian` is on**, exactly as the guard counters are.

## 5. Does a recovered column bias the step into the constraint? — DEFERRED to stage 2

A one-sided column measures the residual change on the side the floor permits.
The reconstructed LM direction could still point out of the feasible region, and
backtracking a blocked direction need not find a tangential alternative — the
verdict says this explicitly, and it is why rank 3 exists.

This review does not claim the fix escapes the stall. Stage 2 is the test, and a
stop-reason change alone does not pass it. If stage 2 shows a measured model
with no feasible decrease, rank 3 gets a separately reviewed case built on the
observed blocked directions — it does not get implemented inside this contract.

## 6. Should the fix be on by default? — REJECTED for this cycle

Same reasoning that kept the refined guard opt-in: flipping a default changes
the reference behaviour that TOP-001 and TOP-005 replay bundles reproduce
against. Two defaults are now pending that decision, and it should be taken once,
in a declared comparison, not twice in two closeouts.

## 7. Is the census enough to justify skipping stage 1? — REJECTED

Tempting, since the census already proves every refused direction has a feasible
side. It proves a *geometric* fact and nothing about derivative quality. The
census cost no solves; stage 1 measures whether the resulting numbers are
trustworthy, which is a different question. Stage 1 stands.

## 8. Scope creep into rank 2 — REJECTED

`far-two-stars` has 6 of 6 directions clean and still fails. It is visible in
the census, it is the obvious next thing, and it is **not** in this contract.
The verdict is explicit that the capacity correction belongs in a separate
comparison so the two effects can be identified. Implementing both at once would
make a passing suite uninterpretable.

## Binding outcome

Points 1, 2, 3 and 4 are binding on the implementation. Point 5 is the stage-2
hypothesis. Points 6, 7 and 8 are refusals to widen the change.
