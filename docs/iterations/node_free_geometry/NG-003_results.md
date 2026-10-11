# NG 003 coefficient-only reciprocal bootstrap results

2026-10-11. [Plan and bounds](NG-003_plan.md),
[numeric evidence](../../../results/validation/node_free_geometry/NG-003/run-01/report.json).
All 279 frozen moves complete in 67.69 seconds. This is construction-only
with frozen current numerical references, not a full validity or inverse run.

| Qualified construction | NG-001 | NG-002 | NG-003 |
|---|---:|---:|---:|
| Original coarse bands | 163 | 170 | 174 |
| Qualified coarse/fine pair after allowed escalation | Not escalated | 178 | 243 |
| Tiny moves (0.1 micrometre), pair | — | 93/93 | 93/93 |
| 1 mm moves, pair | — | 71/93 | 93/93 |
| 6 mm moves, pair | — | 14/93 | 57/93 |

NG-003 gains 65 pairs over NG-002, with zero regressions. Every one of the
243 constructed pairs has a qualified reference and passes both 1e-5 and
1e-7 discrepancy gates. Maximum coefficient-sum error is 0.0002164 nm,
or relative 4.426e-12. All successful receipts meet their complete output
coefficient error budget. This budget covers arclength projection of the
actual finite intermediate curve, not an unspecified infinite normal move.

All five diagnostic states pass their three complete directions in both
bands: 30 analytic-reference comparisons, maximum relative error 6.766e-13.
Maximum self finite-difference error is 2.254e-9; independent reference
refinement is at most 1.139e-12. The integer iteration/scaling branches are
locally fixed in the differentiated finite algorithm, and finite differences
test their practical effect.

Sampling/fitting entry points and the angular range proposer are patched to
raise throughout every new construction. All guards pass. Speed positivity
comes from the full reciprocal and mixed-product residuals, with discarded
modes charged; output projection error includes centroid and every output
phase. No coefficient pruning or sampled minimum is used. Construction
arithmetic remains float64 and is not an interval-verified accuracy proof.

The 36 remaining pair failures are 35 full speed residual limits and one
output projection bound. A post-run summary correction reads both members
of the final pair; previously a successful fine construction could conceal a
failed coarse construction under the label `band_refinement`. Raw receipts
and measured source snapshots are preserved. The correction changes labels,
not numerical work. Most remaining failures occur at the 6 mm stress size.

Analytic controls retain the expected behavior. The a=.49 regular quadratic
constructs at B2048, with 1.002e-15 m base projection discrepancy. The cusp
never constructs through B8192. The regular crossing constructs but its
directed verifier remains unresolved, never accepted. Scalar regularity
cannot establish geometric simplicity.

Across all moves including every failed construction, two-band work and
preparation within the move ledger sum to 57.99 s, median 106.8 ms and maximum
811.2 ms. This is not complete geometry cost: base proofs are reused as
separate NG-002 evidence and trial proofs are not included. A full validity
replay is required before interpreting the best constructor as an operational
node-free update. No maintained selector or default changes.

The full package validation, source snapshot checks, 279 unique moves, zero
physics calls and both sampling guards are recorded in the validation receipt.
The result supports the reciprocal bootstrap and output-budget mechanism.
It refutes an interpretation of the earlier phase/range refusals as physical
invalidity. Remaining Fourier-tail and projection-budget failures are retained.
