# SPD-006 — compiled Kress continuation

Approval: **APPROVED**. Execution: **COMPLETE / QUALITY PRESERVED**. The user's “go” after the
[integration review](02_proposals/01_compiled_scattering_integration_review.md)
authorizes implementation, qualification and matched full inverse measurement.
Existing branch/checkout; no commit, push, branch or worktree requested.

Integrate an opt-in `compiled` runtime for Cartesian continuation fits at
256 or more nodes. Preserve reciprocal Kress elsewhere, including the existing
operator fallback below 128 nodes. Keep the full Cartesian gauge basis,
optimizer, geometry checks, data normalization and topology/continuation policy.
Single-component fits use reciprocal Kress: there is no inter-object system to
reduce. Include merge as that unchanged control. Final and candidate refined
checks, training readiness, and topology fields retain full Kress.

Port the nodal scattering compiler, without importing exploratory numerical
code. Cache local matrices by exact local coefficients, frequency, material,
resolution and fixed cylindrical normalization. Contract reciprocal traces
reconstructed from local regular-wave solutions rather than materializing a
separate acquisition-independent dT for every coefficient. This is the same
reciprocal identity; compare against the full production gauge Jacobian.
Use paired angular orders 20/24, increasing to 24/28 and 28/32 if needed.
Require forward change <=1e-11 and whole/worst-column derivative change <=1e-7
between consecutive orders. Unsupported geometries, failed residual checks or
unresolved angular convergence fall back with recorded reasons. Retain the
current 2e-11 internal objective/Jacobian prediction-consistency check.

Qualification: archived pre/post death/split/merge plus difficult
central-ellipse-star/far-two-stars handoffs; 256/512 nodes and all four training
frequencies, full reachable gauge directions. Compare predictions <=1e-10,
whole Jacobian <=1e-6 and worst column <=1e-5 against same-grid full Kress;
directional FD <=2e-4. Include weighted residuals, complex source strengths,
translation, cache validity, fallback, unchanged ordinary runtimes and work
budgeting in regression tests. Bound numerical qualification and diagnostic
pilots to 1800 seconds and 2000 compiled/full frequency batches combined;
retain failed attempts and amendments rather than changing thresholds silently.

Matched campaign: reciprocal plus SPD-004 readiness versus compiled plus the
same readiness, fresh original starts and observations. Death, merge,
central-ellipse-star and far-two-stars; two repetitions, rotated/reversed arm
order, sequential single-BLAS-thread workers. Maximum 16 workers, 2400 seconds
each, 10800 campaign seconds. Preserve original inner caps. Hard-case reference
failures remain results; stop on new numerical/implementation/integrity failure
or loss of reference recovery. Compare event histories, accepted steps, final
coefficients/boundaries, all original recovery gates and numerical checks.

Charge a compiled frequency evaluation batch separately from physical Kress
systems; count each local factorization, RHS count, reduced system and cache
hit passively. An angular check is included in that batch; every repeated
order evaluation and fallback is recorded. Original stage work ceilings stay
in force. This new work category must not be called a physical full-system
solve. Include startup, topology, candidate fits, continuation, readiness and
endpoint checking in worker times; exclude existing truth-data generation and
videos. Freeze source/input snapshots before full dispatch; no numerical edits
while timed workers are active.

Adopt only the qualified opt-in scope with matched quality and useful full-run
savings. A negative or restricted result is valid. No GPU change, constraint
policy change, reduced shape capacity, or full twelve-scene claim. Close out
in speedup iteration 06, retaining raw evidence and remaining costs.

## Pre-dispatch qualification

2026-09-16: **33/33 checks PASS**, 11 saved states at 256/512 nodes, all four
training frequencies and the full reachable gauge basis. Maximum prediction
discrepancy is `5.126e-14`, maximum Jacobian column discrepancy `2.838e-13`,
and maximum directional FD discrepancy `8.422e-9`. Qualification used 352
budget units in 103.02 seconds, within both ceilings. Evidence:
`results/validation/speedup/SPD-006-20260916-qualification-01`.

**114 regression tests pass; one unavailable-CUDA test skips.** The full
campaign now freezes 220 numerical/runner/test sources. Numerical edits pause
through the timed workers. Reporting code lives separately and is archived
at closeout. The raw single-component compiler was qualified, while the
production runtime keeps its predeclared single-component Kress fallback.

## Closeout

All 16 fresh full workers recovered, with matching events, accepted-step counts
and numerical gates. Median full-runtime reductions are 4.46% on central
ellipse/star and 5.58% on two stars; death and the single-component merge control
are unchanged. The campaign used 10486.87 of 10800 seconds. All 1340 angular
checks passed at 20/24 without hard-scene fallback. All frozen source/input and
work-accounting checks passed.

The post-campaign one-update profile reproduced its archived accepted state
exactly. Legacy stencil feasibility used 88.5% of its 26.96 seconds. Qualification
plus the diagnostic used 357 units and 129.97 seconds, within both allowances.
The opt-in backend is retained; geometry/constraint work is the next priority.
No default promotion, constraint-policy change or GPU implementation was made.
Full evidence and limits: [iteration 06 results](../iteration_06/01_results.md).
