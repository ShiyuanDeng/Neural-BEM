# Independent review of TOP-008 and TOP-009

2026-09-12. Reviewer: Codex. Reviewed experiment tip: `ab10e40`.
Scope: source review, saved-artifact audit, and regression tests. No new
reconstruction experiment or benchmark suite was run.

Follow-up discussion: [boundary methods versus FDTD](02_boundary_methods_and_fdtd.md)
records which suspected causes a solver swap could address and how to separate
that comparison from changing the geometry unknowns or acquisition.

The feasible-side stencil and nested-bandwidth ladder address real defects.
The recorded stage-2 gate failure stands. The stronger conclusion that the
finished ladder proves a phase local minimum and eliminates acquisition,
regularization and optimizer stopping is not supported.

[Machine-readable audit](../../../../../results/validation/topology/TOP-009-20260912-review/evidence_audit.json)
and its [reproduction script](../../../../../results/validation/topology/TOP-009-20260912-review/audit_saved_evidence.py)
read historical records without importing the solver. Their input hashes are
recorded. Existing experiment JSON, scripts and measured outcomes are preserved.

## Findings

### 1. Ladder exhaustion did not establish optimizer stationarity

Of the 14 retained stage-4 rungs, **13 stopped on `loss_change_tolerance` and
one on `maximum_iterations`**. The final K=9 refinement also stopped on loss
change. `_optimizer_config` uses the same absolute `1e-10` for target loss and
accepted loss change, and the latter branch precedes the gradient check.
Consequently the stop reason supplies no bound on the terminal gradient.

The final objective is `3.8613e-9`, with a known lower value `5.2068e-14`.
That establishes suboptimality. It does not distinguish early stopping,
ill-conditioned steps, finite-difference error, active constraints, a saddle,
or a local minimum. Completing the mode ladder resolves its bandwidth cap;
it does not resolve these optimizer questions. The saved rung records omit
terminal gradient norms and unresolved-column counts.

**Decision: accept the capacity finding; reject the local-minimum certificate.
Resolve the remaining optimization question through proposed TOP-010 below.**

### 2. A consistent truth response is not an identifiability result

The small truth residual establishes that this chart and forward model can
closely match the observations at the supplied truth. It does not establish
unique or stable inversion, nor seven significant figures of shape recovery.
For example, `F(x1, x2) = x1` has an exact truth fit for every value of `x2`:
consistency and non-uniqueness coexist. The saved experiment has not performed
an alternative-solution search or a conditioning audit at its final state.

The distinction matters at the actual controller tolerance. In this
single-frequency, unit-weight problem, relative L2 is `sqrt(2 * loss)`.
The final K=9 answer has relative error **8.7878e-5**, below the frozen
controller's **0.003**, while boundary error is **11.849 mm** and worst holdout
error is **1.4154**. The first saved rung below that data tolerance is [5, 5]:
relative error 0.0016580 with 15.634 mm boundary error. The current tolerance
therefore accepts data fits with poor geometry in these saved examples.

The stage-4 script directly calls the fixed-topology optimizer. It bypasses the
controller's early `recovered` return, topology proposals, and cycle/event
limits. A controller handed a saved state below its data threshold would satisfy
that early stop before promotion. This is a source-level observation, not a
prediction of the full controller's trajectory. The finished diagnostic ladder
does not qualify the opt-in controller on the frozen suite.

**Decision: reject “data/regularization eliminated.” Keep acquisition and
regularization unchanged for the next discriminating diagnostic, without
claiming either could not help.**

### 3. The proposed phase remedies need a data-derived direction

The reported 34° and 156° rotations minimize error against the known truth.
No corresponding training-objective decrease was reported for those rotations.
They establish a geometric phase mismatch, not a training-objective phase
minimum. The remaining rotation-corrected errors also exceed the 1-mm gate.
Aggregate area and perimeter cannot identify a lobe pattern by themselves.

Re-fitting the current low-bandwidth contour at higher bandwidth cannot
reliably supply missing shape: exact Fourier projection of the same contour
has zero coefficients in the added modes. A useful seed needs a different,
explicitly data-derived contour or perturbation. Sampling/interpolation error
is not a principled seed. Likewise, at zero cosine/sine amplitude, physical
phase is undefined but Cartesian coefficient directions remain regular;
the gauge basis explicitly contains independent sine and cosine directions.
Zero initialization alone does not establish a phase trap.

**Decision: reject re-fitting the same contour as a phase remedy. Defer
data-selected phase trials until TOP-010 separates stopping from stationarity.
Truth-selected angles must remain evaluation-only.**

### 4. Promotion diagnostics silently omitted completed refinements

The controller accumulated feasibility rejections, one-sided columns and
unresolved columns from fixed and candidate refinement, but omitted
`bandwidth_refinement`. A promotion could therefore encounter unresolved
derivatives while its cycle reported zero. BIE work accounting used its own
ledger and was unaffected.

**Fixed:** include each returned promotion optimizer's counters in its cycle
and promotion record before refined acceptance, including rejected rungs and
refined-evaluation geometry exceptions. Three regression cases reproduced the
omission before the fix and pass afterwards. The numerical proposal and
acceptance rules are unchanged.

Validation: **108 tests passed** across bandwidth promotion, feasible finite
differences, refined feasibility, controller, allocation, selective refinement,
scene benchmark, Cartesian topology and radial topology. This is a focused
regression result, not a new twelve-scene recovery result.

### 5. Correct the trend and cost descriptions

Stage-2 matched error does **not** worsen monotonically. It improves on retained
rungs 1→2 (7.892→7.593 mm) and 3→4 (14.130→12.265 mm).
The final answer is worse than the start and the gate still fails. Claims of
monotone degradation and a strictly best starting boundary score should be
replaced by the actual endpoint comparison.

The stage-4 `solves` field counts optimizer evaluations plus padding/refined
acceptance calls. It excludes the initial baseline and per-rung/final holdout
evaluations; optimizer evaluations can also be rejected before a BIE solve.
It is not a total BIE-work measurement. Keep 7446 as the recorded diagnostic
counter, not a controlled full-controller solve-count comparison.

**Decision: amend the interpretation, preserve the measurements.**

## TOP-010 — separate stopping from stationarity before adding restarts

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Question:** does the saved K=9 state have a resolvable feasible descent
  direction, and does continued local optimization use it?
- **Falsifiable hypothesis:** the final state's apparent stagnation can be
  explained by stopping or local step construction. Stable small gradients and
  absence of tested feasible descent would argue for a globalization study,
  though they would still not prove a local minimum.
- **Baseline:** `ab10e40`; TOP-009 stage-4 final state, data, chart and K=9.
- **Intervention:** diagnostic-only terminal residual/Jacobian audit followed,
  if justified, by one paired fixed-topology continuation. Compare the recorded
  stopping rules with loss-change stopping disabled and a `1e-14` absolute
  loss target. That target is a numerical diagnostic threshold, not a truth
  recovery or benchmark acceptance gate. Keep all other optimizer settings
  fixed; do not introduce a controller default.
- **Controls:** same production/refined resolutions, observations, radius
  floor, gauge, trust bounds, damping, and feasibility guards. Truth and holdout
  may score results, never select directions, starts or accepted steps.
- **Scope and interfaces:** a fresh diagnostic script using existing solver
  APIs; any option needed to isolate loss-change stopping must be separately
  reviewed before numerical implementation. Do not change the physical solver,
  geometry-state interface, acquisition or frozen benchmark.
- **Metrics:** terminal gradient at FD steps `1e-4`, `5e-5`, `2.5e-5`;
  one-sided/unresolved directions, reduced-Jacobian singular values, and actual
  production/refined loss changes along normalized negative-gradient and LM
  directions at the existing step/backtrack scales. Record every continuation
  step, stop reason and terminal diagnostics. Compare boundary/holdout only
  after the training decisions.
- **Compute budget:** at most 500 forward frequency solves for the terminal
  audit and 2500 additional solves for both continuations combined; 600 seconds
  total. Enforce limits at solver-call boundaries and include diagnostics,
  rejected attempts and holdout work in separate ledger categories. Stop and
  retain partial evidence on either limit.
- **Artifacts:** fresh `results/validation/topology/TOP-010-<run-id>/`, containing
  source/config hashes, direction probes, trajectories, complete work counts,
  failure records and a review summary.
- **Decision criteria:** a stable measured descent direction rejects a
  stationarity claim; a lower objective from local continuation rejects the
  claim that a restart is already necessary. If local progress stalls with
  unresolved FD estimates, resolve those first. If stable local diagnostics
  find no descent, design a separate training-selected restart experiment.
  Any later performance claim requires all twelve frozen scenes.
- **Owner:** unassigned. **Reviewer:** unassigned.
