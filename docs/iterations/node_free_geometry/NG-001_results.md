# NG 001 coefficient geometry results

2026-10-11. Component comparison; no inverse runs or default changes.

## Run 01 interrupted replay

[Evidence](../../../results/validation/node_free_geometry/NG-001/run-01/report.json)
and [failure](../../../results/validation/node_free_geometry/NG-001/run-01/failure.json).
The reporting constructor passed `receipt` twice when base construction was
unresolved. The run stopped entering the third state. This software defect is
fixed for the next fresh run; its source snapshot and all results remain.

The two completed states contain 18 fixed moves. The current geometry accepted
18/18. The new engine constructed and certified 15/18; all 15 met both the
1e-5 production and 1e-7 tighter discrepancy gates. Maximum independently
sampled discrepancy was 1.053e-6 nm, consistent with floating-point agreement.
Three 6 mm moves failed the mean-centred scalar expansion: two range failures
and one degree-budget failure. This partial screen is not the full TG-002
component result.

The same-base cheap tests accepted 12/15 for the direct bound and 6/15 for the
squared bound. All 45 checked geometry roles were proved valid by the directed
interval verifier. Complete new trial time, including both working bands and
validity, had median 88.0 ms versus current 8.15 ms across its 18 trials; these
populations differ, so this is descriptive rather than a paired speed claim.
The median paired current/new time ratio was 0.0873 on the 15 common
constructions. Full interval checking is expensive in this implementation.

On the start circle, all three complete directional derivatives passed:
maximum relative error 3.42e-14 against refined analytic quadrature and
3.74e-10 against self finite differences. This does not qualify curved states
or a complete high-band Jacobian.

Analytic controls certified circles, both ellipses and the regular quadratic
at a=0.2 and 0.49. The scalar expansion exceeded 512 terms at a=0.49. The
exact cusp and regular crossing were unresolved, never accepted. Four bounded
tests pass, including disabling curve sampling in the new engine and charging
omitted coefficient derivative tails.
The complete maintained package suite passed 177 tests in 64.06 seconds before
preserving this run and its reporting fix.

## Continuation

Repeat the frozen full panel in a fresh run after the reporting fix, with no
numerical construction change. Decide any mathematical amendment from the
complete recorded failure distribution rather than this partial panel.

## Run 02 complete frozen panel

[Numeric report](../../../results/validation/node_free_geometry/NG-001/run-02/report.json),
[breakdowns and source checks](../../../results/validation/node_free_geometry/NG-001/run-02/breakdown.json),
[figure](../../../results/validation/node_free_geometry/NG-001/run-02/comparison.png).
All 31 states and 279 moves completed in 2487.39 seconds, with unchanged
measured sources, zero physics calls and all new-engine sampling guards active.
CUDA was unavailable to this process; the current control used CPU preparation
and CPU trials in every state. This is a component comparison, not an inverse.

| Result | Current | Coefficient prototype |
|---|---:|---:|
| Accepted finite moves | 277/279 | 57/279 |
| Coarse constructions with qualified reference and both accuracy gates | — | 163/279 |
| Fine constructions with qualified reference and both accuracy gates | — | 183/279 |
| Complete derivative directions passing | Control/reference | 15/15, on all five diagnostic states |
| Median finite trial time, descriptive populations | 0.471 s, all 279 | 15.130 s, 163 common constructions, including both bands and proofs |

The median paired current/new complete-trial ratio is 0.03229: approximately
31 times slower for the prototype. Unresolved proofs remain charged. Coarse
construction alone has median 37.5 ms, but this excludes the second band and
admissibility and is not a complete-path speed claim. The current full
Jacobian preparation cost is charged; the new tangent cost covers three
directions only. Timings are single-pass, include first-use work and lazy
certificates, and have no separate repeated warm-up study.

| Move magnitude | Current accepted | Coarse constructed accurately | Prototype certified |
|---|---:|---:|---:|
| 0.1 micrometre | 93/93 | 90/93 | 42/93 |
| 1 mm | 93/93 | 66/93 | 9/93 |
| 6 mm | 91/93 | 7/93 | 6/93 |

Maximum coefficient-sum error on all 163 qualified coarse constructions is
1.115e-5 nm; maximum independently sampled position error is 5.848e-6 nm.
These values describe floating agreement on the constructed subset. The
maximum complete-tangent relative error is 6.767e-13 against independently
refined analytic quadrature; maximum self finite-difference discrepancy is
2.243e-9. The independent tangent reference's refinement error is at most
1.139e-12. All 15 directions also pass the tighter 1e-5 diagnostic.

The 116 coarse construction failures comprise 72 mean-centred expansion
range failures, eight degree-budget failures, nine moves blocked by one base
bandwidth failure, 12 full speed residual failures, three full phase residual
failures and 12 positive-range budget failures. The fine band constructs 20
additional moves. This supports scalar-proposer and bandwidth limitations;
it does not establish impossibility of coefficient geometry.

The interval verifier proves 15/31 bases and 185 trial roles. All 304
unresolved trial roles exhaust the five-second budget. No ambiguous or
known crossing is accepted. Current refuses two 6 mm kite moves for sampled
self-intersection; the prototype's positive-speed range is unresolved on
both. Those are not independent crossing proofs from the new engine.
Same-base cheap candidate inequalities accept 48/86 for the direct bound
versus 18/86 for the old squared bound. The algebraically stronger bound is
useful but insufficient when the base proof is unavailable or weak.

Including refusals, both coefficient construction bands consume 39.78 s;
base interval proofs consume 103.56 s and trial proofs 1593.01 s. Current full
preparation consumes 174.09 s and all current trials 554.88 s. These ledgers
have different tangent workloads and are not a full-Jacobian comparison.

The full maintained package suite previously passed 177 tests in 64.06 s;
the four focused tests pass again in 0.23 s after this replay. Snapshot hashes,
unique moves, panel completeness and zero physics calls are checked by the
read-only report script. The scientific figure was rendered and inspected.

**Decision:** the centred coefficient map and complete tangent are qualified
on their successfully constructed subset. This initial full engine is not a
practical replacement: decisive geometry proofs and larger nonlinear moves
fail too frequently, and complete trial cost is worse. A bounded follow-up
will isolate the inverse-root proposer and interval evaluation cost. Its
[Newton derivation](NG-001_newton_derivation.md) identifies assumptions and
full-residual requirements. No maintained selector or default changes.
