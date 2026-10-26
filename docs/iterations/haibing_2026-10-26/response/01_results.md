# Direct physical evidence for Haibing items 6–8

**The response identities work on the real solver. The tested shortcuts do
not yet provide a useful general replacement for its dense solve.** These
are component tests on TG-002 saved shapes, not new reconstruction results.

## Item 6 Schur elimination with high-mode feedback

Original Word §§13–14 proposes eliminating high trace modes while retaining
their influence on the low system, source and receiver. Eight tests use
hook c13.3, real/damped 2.5 GHz, Ku64/128 and two retained bands each.

Exact feedback reproduces all 24 paired predictions with relative errors
3.73e-16–2.79e-14. Dropping the high modes instead produces errors from
7.98e-9 to 2.34. The high-mode feedback therefore matters greatly in some cases.

| State and frequency | Full LU ms | Exact Schur ms | Retained band | Dropped-mode error | Four-correction error |
|---|---:|---:|---:|---:|---:|
| Release Ku64 real | 2.030 | 2.143 | 16 | 1.028 | 1.505 |
| Release Ku64 real | 2.030 | 2.097 | 32 | 2.342 | 0.0367 |
| Release Ku64 damped | 1.957 | 2.082 | 16 | 0.00981 | 0.000902 |
| Release Ku64 damped | 1.957 | 2.059 | 32 | 2.60e-5 | 1.58e-7 |
| Final Ku128 real | 13.118 | 12.555 | 32 | 1.815 | 0.0291 |
| Final Ku128 real | 13.118 | 12.595 | 64 | 4.82e-4 | 1.91e-10 |
| Final Ku128 damped | 12.152 | 12.455 | 32 | 3.93e-5 | 2.14e-7 |
| Final Ku128 damped | 12.152 | 12.519 | 64 | 7.98e-9 | 3.20e-14 |

The proposed diagonal high-block inverse is not uniformly contractive.
Its correction operator has spectral radius 1.096 for release/real/keep16;
error grows from 0.934 without correction to 1.505 after four corrections.

Even when its spectral radius is below one, its Euclidean operator norm is
6.35–33.18. Thus the stated norm-below-one Neumann bound certifies none of
these eight splits. Spectral-radius convergence and that norm bound differ.

A narrow useful result survives: final/damped/keep64 reaches 4.18e-10 field
error with the diagonal inverse in 6.48 ms versus 12.15 ms for full LU.
The matching real case has 2.43e-6 error; four corrections cost 21.15 ms.

**Decision:** exact elimination is a verified algebraic option. Keep the
high-mode feedback. There is no general speed result across real and damped
copies; the favorable damped case alone does not qualify a fit backend.

**Limits:** two shapes, one frequency, field accuracy only. No Schur
Jacobian comparison or full reconstruction was run. Exact timings include
elimination, effective source/receiver construction and the reduced solve.

## Item 7 Forward–adjoint model and directional enrichment

Original Word §§15–16 is tested on the actual PS-003 hook accepted slider
coefficient direction, iteration 0→1 in release_M11. Its endpoint movement
was previously measured as 1.139 mm. Ku64 gives 258 full unknowns.

The base uses all 24 forward and 24 true conjugate-adjoint receiver states.
Their union has rank 48. Adding derivatives of both sets raises rank to 96.
The derivative uses two physical solves at path parameters ±0.001.

| Frequency | Base error at alpha 1 / alpha 0.0625 | Enriched error at alpha 1 / alpha 0.0625 | Last base slope | Last enriched slope |
|---|---:|---:|---:|---:|
| Real | 0.357 / 0.00331 | 0.0482 / 6.61e-7 | 1.936 | 4.023 |
| Damped | 2.33e-4 / 9.99e-7 | 2.94e-6 / 4.78e-11 | 1.986 | 3.995 |

This directly confirms the claimed second/fourth local orders on a physical
shape path, beyond the original document's synthetic 40-dimensional test.
It does not establish adequate accuracy over the whole accepted step.

Base projection, solve and lifting cost 1.01–1.05 ms, compared with
1.91–1.96 ms for full LU and prediction. Enrichment costs 2.35–2.45 ms.
Fresh physical assembly still costs 0.356–0.370 s per candidate.

Anchor basis setup costs 3.33–3.36 ms beyond the physical anchor evaluation.
Enrichment adds 7.77–9.82 ms of solves/basis work plus 0.727–0.737 s for its
two derivative snapshots. These costs have not been amortized away.

**Decision:** the local accuracy mechanism works. The enriched implementation
is slower than LU after the same assembly, and the base's small solve saving
cannot remove assembly cost. Direct reduced assembly remains untested.

**Limits:** one actual slider direction, not the default spectral-refit path;
one contrast and frequency, two wavenumber copies. Finite-difference
snapshot derivatives can limit smaller-step accuracy. No inverse fit or J test.

## Item 8 Dual residual and LM step error control

Original Word §§17–18 is evaluated on the same physical matrices and ROMs.
The dual-residual identity agrees to maximum absolute discrepancy 1.26e-21
(real) and 1.29e-29 (damped), using all 24 paired channels.

The norm bound uses the full matrix's smallest singular value. At nonzero
steps it exceeds the observed response-error norm by 1.08e5–3.06e5 (real)
and 894–3508 (damped). It covers these errors but is often much too loose.

Computing that inverse-norm estimate costs 7.72–7.98 ms, before residual
work. The recorded residual check, including an extra solve to verify the
identity, costs another 3.01–3.61 ms. Both exceed the saved solve time.

At the exact anchor, the residual-product bound falls below floating-point
prediction error. Thus this implementation is an **estimate**, not a
rounding-controlled certificate; the report records that failure explicitly.

Objective bounds use the actual observed-data normalization. For the real
enriched model at alpha 0.0625, the bound is 0.0723 versus actual objective
error 3.18e-8. No candidate-acceptance or whole-fit guarantee follows.

For the LM claim, the saved FI-001 hook_release 19-frequency physical
Jacobian has 912 rows and 23 columns. Five CG steps solve the fixed,
Marquardt-scaled normal equation approximately; the full solve is reference.

| Damping | Actual step error in metric | Bound | Bound / actual |
|---:|---:|---:|---:|
| 1e-6 | 2.96e-5 | 3.40 | 114890 |
| 1e-3 | 2.86e-5 | 0.00337 | 117.7 |
| 1 | 4.15e-8 | 6.99e-8 | 1.684 |

All 15 checked iterates satisfy the bound. At large damping it is useful;
at small damping it is extremely conservative. A defect evaluation costs
about 3 microseconds, while the full 23-variable solve costs 10–44 microseconds.

**Decision:** both identities hold in physical numerical examples. Cheap,
tight, rounding-controlled error budgets are still missing. The LM test
covers a fixed accurate J and residual, not errors from approximate physics.

## Evidence and reproducibility

- [Pre-registered plan](03_plan.md).
- [Prototype](../../../../experiments/haibing_response/study.py).
- [All saved evidence](../../../../results/validation/cleaned_interfaces/HB-003-response/README.md).

Single-thread CPU, cores 8–11, three algebra timing repetitions; other
tracks ran concurrently. Load and GPU-use snapshots are saved. No GPU was
used by this track. Cross-track timings should not be combined.

The run's assertions check exact Schur agreement, fixed-system LM coverage,
and roundoff-aware DWR consistency. The postprocessing note clarifies the
coverage label without changing any numerical calculation or timing.
