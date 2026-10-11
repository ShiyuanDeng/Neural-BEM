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
