# Independent Chebyshev proposal verification

Review of the PDF pulled in commit `1723dbee`, requested by the user on
2026-09-30. The PDF's implementation was not supplied; these scripts were
written independently from its equations and the existing solver interfaces.

Read the [claims review](../../../../docs/iterations/cleaned_interfaces/node_free_modal_muller_review.md).

The core fix reproduces. The claimed finite-Parseval geometric certificates
do not: `claims.json` contains explicit counterexamples. No production or
hash-pinned source was modified, and this bundle is not a registered backend.

All three archived stage replays match every trial decision, accepted index,
exit, and stage-specific work count. Endpoint differences are at most
2.96e-12 package units (1.48e-13 m); the PDF's stricter 6e-13-unit endpoint
number is not reproduced by this independent implementation.

## Reproduce

Run from the repository root in the existing EMNerf environment:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export SC_FREQUENCY_THREADS=1
REVIEW_PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
REVIEW_DIR=results/validation/cleaned_interfaces/chebyshev-review-20260930

"$REVIEW_PY" -m pytest -q experiments/modal_muller_research
"$REVIEW_PY" "$REVIEW_DIR/verify.py" claims
"$REVIEW_PY" "$REVIEW_DIR/verify.py" star
"$REVIEW_PY" "$REVIEW_DIR/verify.py" c
"$REVIEW_PY" "$REVIEW_DIR/integration_checks.py" scalar
"$REVIEW_PY" "$REVIEW_DIR/integration_checks.py" c
"$REVIEW_PY" "$REVIEW_DIR/integration_checks.py" damped
"$REVIEW_PY" "$REVIEW_DIR/integration_checks.py" endpoint
"$REVIEW_PY" "$REVIEW_DIR/directional_check.py"
"$REVIEW_PY" "$REVIEW_DIR/replay.py" stage_2_damped
"$REVIEW_PY" "$REVIEW_DIR/replay.py" fixed_M43
"$REVIEW_PY" "$REVIEW_DIR/replay.py" release_M11
"$REVIEW_PY" "$REVIEW_DIR/summarize.py"
```

These commands overwrite this bundle's own receipts. They do not write to
the archived input/result directories. `summarize.py` independently checks
stage-specific work counts; archive ledgers can include earlier stages.
In the raw replay receipts, `comparison.expected_solves` and
`comparison.expected_derivatives` retain those cumulative archive totals;
use `summary.json` for the correct stage-only comparison.

## Evidence and scope

| Artifact | Check |
|---|---|
| `star.json` | All four native Müller blocks, three contrasts, monomial terms and Chebyshev degrees |
| `c.json` | C-shape logarithm, coefficient-window refinement, independent 1024/2048-node oracle |
| `claims.json` | Real/complex Bessel identities; regular crossing curve falsely passes the lower-bound test; simple circle falsely passes upper-bound test; quadratic local-error accumulation |
| `integration_scalar.json` | Six scalar functions against 60-digit mpmath |
| `integration_c.json` | Saved SC C, paired fields and complete-update coefficient Jacobian versus 2048-node reference |
| `integration_endpoint.json` | K=192 DF endpoint, M=67, Ku=64/96/128 with fixed B=160 |
| `integration_damped.json` | Saved C at damping 0.25 and 0.5/1/2.5 GHz |
| `directional.json` | Centered differences of the complete nonlinear SC trial on two curves |
| `replay_*.json` | Fresh fits from each archived stage's initial curve, including all new trial/acceptance records |
| `summary.json` | Independently recomputed replay comparisons, stage-only work accounting and provenance |
| `source_versions/` | Exact earlier script version needed to resolve source hashes in the initial field-check receipts; later changes only extended the counterexamples and corrected an unused oracle selector |

The unmodified native baseline suite passed **30 tests in 8.11 s** before
building the independent prototype. The scripts import production modules
read-only. Boundary nodes occur in the nodal oracle and in SC geometry
operations; the native physics assembly, fields, and Jacobian contraction
operate on coefficients.

`beta=0.05` is a stated experimental assumption for the known valid C/replay
fixtures. Neither independent implementation labels it a certificate. The
radial upper interval uses coefficient triangle bounds, not RMS bisection.
The FFT implementation uses linear convolution, and geometry arrays are
reused only when the complete curve coefficients are unchanged.

No all-36 inverse campaign, multi-object extension, universal validity
certificate, or speed claim is established. Some independent checks ran
concurrently, so recorded elapsed times are not matched performance evidence.
Two early replay attempts finished numerically but failed receipt serialization;
the serializer was corrected and the stages rerun. Only successfully saved
receipts are used for the final comparison.
