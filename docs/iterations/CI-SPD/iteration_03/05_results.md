# EW-001 — smaller Ewald splits still fail; contraction cost closes the 2D line

**Terminal: `CIRCLE_FAILS_AT_UNREGISTERED_SPLIT`.** Completed 2026-10-05 under the approved [plan](03_plan.md). User authorization: “go on EW-001”.

None of the three smaller splits passed the circle diagonal gate. The best registered 256-grid result was **4.9558e-4** at ξ/k*=0.35, about **4,956 times** the 1e-7 gate. The contraction-only complex128 lower bound was **5.129 s** per 19-frequency, two-media service, **46.2–48.3x** maintained modal assembly. Both findings close this registered 2D line.

## Reproduction and circle qualification

ON-003’s ξ/k*=1 results reproduced exactly: all **192 normalized block errors**, maximum absolute difference **0**, required ≤1e-12. The new driver redirects ON-003’s unchanged `run()` to EW-001’s own evidence directory. It changes the split and receipt label; it preserves all numerical settings, the pinned reference archive and the circle calculation.

The following table gives the worst normalized diagonal error across all 12 contrast/frequency/catalog configurations at **grid 256, trace cutoff 128**. K′ equals K on a circle. Every listed block must pass ≤1e-7.

| ξ/k* | Gaussian tail estimate | V | K = K′ | T | Gate |
|---:|---:|---:|---:|---:|---|
| 0.5 | 8.238e-09 | 5.701e-07 | 1.227e-04 | 1.606e-02 | FAIL |
| 0.4 | 8.299e-13 | 4.796e-07 | 3.644e-05 | 7.133e-03 | FAIL |
| 0.35 | 5.081e-16 | 2.308e-07 | 6.140e-06 | 4.956e-04 | FAIL |

The 128 grids also failed at every split. Both trace cutoffs failed on every grid; all **576 new block rows** and **192 reproduction rows** are preserved and rebuilt from the saved spectra in verification. The full table is in [the evidence README](../../../../results/validation/cleaned_interfaces/EW-001/README.md).

## Error source: far-grid representation, rather than near quadrature

The independent heat-time control uses ON-003’s unchanged 256/512 Gauss orders and reference module. For each saved configuration it decomposes the total error into (angular near − independent heat near) and (grid far − [analytic outgoing − independent heat near]). No candidate correction, grid refinement or additional split was introduced.

| ξ/k* | Worst T mode | Total normalized T error | Near error at that mode | Far error at that mode | Component cancellation ratio |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 122 | 1.606e-02 | 1.287e-13 | 1.606e-02 | 6.112 |
| 0.4 | 128 | 7.133e-03 | 3.135e-13 | 7.133e-03 | 3.382 |
| 0.35 | -126 | 4.956e-04 | 9.778e-14 | 4.956e-04 | 1.163 |

All three worst T failures occur at contrast 0.5, 0.25 GHz, real catalog, near the edge of the trace band. The cancellation ratio here is (|near| + |far|)/|analytic medium difference| at the failing mode; its modest values do not explain the failure.

Across the full registered panel, the maximum normalized near-error contribution was **9.617e-10**. The maximum absolute heat-order difference was **7.098e-12**. Radial multiplier refinement differences were at most **3.232e-15**. These are far below the failing T errors.

The error is therefore in the finite far-grid representation. The Gaussian term exp(−τ q_max²) is **not an error bound for this candidate**. Its multiplier is the radial transform of a smoothly truncated outgoing-minus-near kernel, as ON-003’s [derivation](../../../../results/validation/cleaned_interfaces/ON-003/derivation.md) explicitly states. It is not the unwindowed Gaussian Helmholtz multiplier. The compact cutoff and rectangular Fourier truncation remain in the measured construction. The evidence identifies far-grid error as dominant; it does not separately apportion that error between shell-window effects and the finite Cartesian grid.

**Correction to the proposed interpretation:** the original registered ξ≥k* range was not the sole reason for ON-003’s failure. Extending it to the proposed smaller splits did not qualify the circle control. The original ON-003 report remains intact; this report supersedes the smaller-split pass prediction.

## Cost gate

Timing used the RTX 5090 and maintained `modal_cuda.muller_matrix`, the saved PC-001 M1 `kite__c4` endpoint, all 19 real frequencies, both media, and one cold plus three warm repeats. Each current matrix already combines exterior and interior media. Geometry setup is separate; cold assembly includes lazy radial extension. Warm service time is the median of three complete catalog traversals.

| K_trace | Geometry setup s | Cold service s | Warm service repeats s | Warm median s | Ewald lower bound / current |
|---:|---:|---:|---|---:|---:|
| 128 | 0.179409 | 0.260942 | 0.107312, 0.100645, 0.106161 | 0.106161 | 48.31x |
| 160 | 0.088201 | 0.132017 | 0.111415, 0.110617, 0.111064 | 0.111064 | 46.18x |

The Ewald contraction times `Aᴴ(D A)` with the diagonal weighting included, resident operands and synchronized wall-clock measurement. Input generation is outside the timed interval. Projection uses **190 contractions**: five per medium × two media × 19 frequencies. It excludes map construction, near corrections and transfers.

| Trace columns | Precision | Cold contraction s | Warm repeats s | Warm median s | Projected 190 contractions s |
|---:|---|---:|---|---:|---:|
| 257 | complex128 | 0.028649 | 0.027015, 0.026990, 0.026992 | 0.026992 | 5.128510 |
| 257 | complex64 | 0.011008 | 0.001146, 0.001136, 0.001139 | 0.001139 | 0.216458 |
| 129 | complex128 | 0.009093 | 0.008402, 0.008395, 0.008388 | 0.008395 | 1.595001 |
| 129 | complex64 | 0.000549 | 0.000529, 0.000521, 0.000526 | 0.000526 | 0.099893 |

The decision uses **257 columns, complex128**, as registered. The 129-column and complex64 results are context only. K_trace=160 has 321 current trace columns, so the 257-column Ewald projection against it is still a lower bound. complex64 is not eligible for the 1e-7 precision gate.

Cross-checking all **30 ON-001 baseline receipts** gives median assembly seconds per call **0.010611 s**, and count-weighted aggregate **0.011373 s**. The fresh warm endpoint measurements are **0.005587 s** per frequency at K=128 and **0.005845 s** at K=160. Historical receipts cover varying curves, resolutions and lazy preparation, so they provide context rather than a matched timing comparison. Assembly thread seconds are divided by assembly calls, with no additional division by frequency threads.

The pre-registered economy threshold was lower bound <0.5x current assembly. The measured lower bound exceeds current assembly by 46–48x, so it fails that threshold by about 92–97x. This does not measure a complete Ewald forward service or inverse speedup; it already rejects the proposed dense contraction path.

## Validation, provenance and scope

- Eight focused tests passed: EW-001 coverage/decision guards and all six ON-003 independent numerical controls.
- All 768 diagonal rows rebuilt from preserved arrays; manifest/archive copies and numerical source hashes verified.
- 576 error-attribution rows, 48 heat controls and all cost repeats checked. An initial closeout count assertion expected 42 heat controls; it was corrected to the 48 recorded waves and its failed-check receipt retained. Numerical outputs were unchanged.
- Existing ON-003 driver, numerical modules, frozen observations and evidence preserved. Cost imports point at maintained solver sources, in a fresh process independent of the pinned circle reference.
- Numerical work serialized by exclusive compute and shared source locks; RG-001 ran separately between batches. EW-001 code/evidence published after each completed batch under the Git lock; unrelated RG-001 files excluded.

Curved-state blocks, full fields, off-diagonal Cartesian-grid actions, derivatives and inverse integration remain **unrun and unqualified**. A diagonal pass would have been only a necessary screen; here there was no pass. No additional experiment is proposed or launched as part of this closeout.

Evidence: [summary](../../../../results/validation/cleaned_interfaces/EW-001/summary.json), [cost receipt](../../../../results/validation/cleaned_interfaces/EW-001/costs/receipt.json), [near-error attribution](../../../../results/validation/cleaned_interfaces/EW-001/near_error_attribution.json), [verification](../../../../results/validation/cleaned_interfaces/EW-001/verification.json), [extended verification](../../../../results/validation/cleaned_interfaces/EW-001/extended_verification.json).

Implementation: [circle and cost driver](../../../../experiments/benchmark/ew001.py), [independent near diagnostics](../../../../experiments/benchmark/ew001_diagnostics.py).

Published batches: `8b410aaa` reproduction; `a7943efa` ξ=0.5; `e04e1e62` ξ=0.4; `3cd501e1` ξ=0.35; `aea7c56c` cost; `8aad88be` independent heat attribution. Final documentation and verification are committed separately.
