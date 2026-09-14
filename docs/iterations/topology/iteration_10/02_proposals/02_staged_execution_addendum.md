# Proposed shared amendment — staged experiments must reach their intervention

Prepared 2026-09-14 from TOP-016. Proposed for adoption with TOP-017. This is a
small supplement to the existing shared implementation principles, not a new
review process or authority to run more experiments.

On adoption, add one dated link to this amendment in
`docs/iterations/implementation_principles.md`. Keep the existing shared file
and approval history intact. The execution contract, not this amendment, owns
all TOP-017 numbers and gates.

## 1. Audit whether the experiment can actually test its question

Before expensive work, list the first stage where the arms differ. Demonstrate
with mocked/synthetic forward calls that the orchestrator reaches that stage
when a valid earlier stage exhausts its intended allocation.

For each stage record a conservative complete-Jacobian batch cost, minimum
candidate/validation work, endpoint reserve and quota. An allocation that
cannot fund even one useful model/step opportunity is a design failure, not a
scientific negative. Work measured only during endpoint scoring does not count
as exposure to a training intervention.

## 2. Separate four independent facts

Report schedule exposure, bounded-protocol completion, numerical validity and
optimization convergence separately. A fifth field reports reconstruction
quality. Do not collapse all of these into one `complete`, `recovered` or
`inconclusive` string.

A protocol intentionally using capped inner stages can complete without every
stage converging. If the protocol was specified to stop entirely on any cap,
its historical classification cannot be changed after seeing the outcome.
Only a prospectively approved successor may change those semantics.

## 3. Use typed resource stops

A planned stage-quota event may transition with a qualified retained state.
A total solve limit, wall-clock limit, failed physical solve, unresolved
numerics or unexpected exception must never masquerade as that event.

Reserve a full maximum-cost batch and endpoint scoring before starting it.
Unused reservation is not a completed solve. If a hard wall limit interrupts
work, retain the last accepted checkpoint and mark missing diagnostics missing;
do not overrun the limit to fill them. Do not catch a generic budget exception
and unconditionally continue at the next frequency.

## 4. Reuse common completed prefixes

When two arms have exactly the same completed prefix and accepted endpoint,
fork subsequent work from that endpoint. Verify coefficient, data and source
provenance; reset optimizer state exactly as the new contract specifies.

Report incremental cost separately from historical/common-prefix cost. Do not
claim the new run has the same trajectory as an uninterrupted run when the
restart policy differs. Do not repeat completed numerical work just to make
the folder layout or logs uniform.

## 5. Qualify controls as carefully as principal cases

A named shape family is not enough to establish capacity in a constrained
parameterization. Separate geometric approximation error, forward error at
that approximation, discretization error and inverse convergence.

A truth-fitted projection is evaluation-only. It may witness an attainable
geometry or objective; failure of one fitting procedure is not proof that no
better representation exists. Keep a regressed control in the scorecard even
when an approximation limitation is discovered.

## 6. Bind diagnostics to the exact state and objective

Every gradient, predicted gain and measured gain needs a coefficient/state hash,
active frequency set, normalization and resolution. A pre-step gradient is not
a post-step stationarity test. Prefer honest missing fields to an expensive
rerun or a misleading reused gradient.

Log rejected production trials, feasibility refusals and unresolved derivative
columns where the existing hooks expose them. If complete counts cannot be
provided without changing the numerical algorithm, state the limitation; do
not claim an exact reason distribution from a filtered log.

## 7. One bounded successor is not an endless budget escalation

After a complete, numerically valid test reaches all declared interventions,
poor recovery is a negative result for that bounded protocol. Do not react by
automatically doubling budgets, adding seeds, changing regularization or
running every scene. Close out with a single evidence-based next decision.

These rules supplement, rather than replace, truth/evaluation isolation,
unchanged defaults, independent review where available, and immutable evidence.
