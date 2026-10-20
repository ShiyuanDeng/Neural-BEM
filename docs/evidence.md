# Evidence behind the current pipeline

This page records why the pipeline on this branch looks the way it does: which
choices were tested, what each test measured, and what is still unknown. It
replaces the dated iteration logs, which were removed with the code they described.
Every number below comes from a data file kept on this branch; section 10 lists them.

The pipeline is `modal_fixed` on TG-002: modal Müller physics, the
`certified_spectral` geometry update, the default `CumulativePolicy`, and the centred
start with no grid search (`--localization none`).

**Recovery** always means the CI-001 rule, unchanged since 2026-09-30:

- the final numerical check of the returned curve passes;
- boundary RMS error ≤ 1 mm;
- Hausdorff upper bound ≤ 2 mm;
- every per-frequency relative residual ≤ max(0.003, 3 × noise). TG-002 is noiseless,
  so the limit is 0.003.

Timings are single runs on one machine (Intel Core Ultra 9 285K, RTX 5090) unless a
section says otherwise. They show size and direction, not confidence intervals.

## 1. The benchmark and the start

TG-002 has ten scenes at contrasts 0.5, 4 and 13.3: 30 cases. Every case starts from
the same 65 mm circle at the scene centre. Target centroids sit 22–38 mm off centre.
Data are noiseless real and damped (k(1 + 0.25i)) catalogs at 19 frequencies
(0.25–2.5 GHz) on a 24-pair ring. The catalogs were computed with the CPU nodal Kress
solver; N1024 and N2048 agree to 1e-8 relative for every case.

**Why there is no grid search.** On the older far-start scenes (SC-050, 220–267 mm from
the target), the continuation alone recovered 0/6 cases and 6/6 with the exhaustive disk
search. Those results measured the search, not the method. The user retired far starts
and the search on 2026-10-04. The 22–38 mm range is supported by SC-043/SC-044, which
recovered all 12 contrast-0.5 configurations from 13–39 mm offsets without any search
(older SC policy).

**Not measured:** NL-001, the matched comparison of TG-002 with and without the search,
was planned but never run. The claim that TG-002 needs no search rests on the 26/30
recoveries below, not on a paired control.

**All 30 truths pass the pipeline's own checks** (RG-001 stage 0). Every true boundary
passes the final numerical check and the residual limit. The four failures in section 7
are therefore failures of the path, not of the data or of the truths' resolution.
One exception: the cog 13.3 truth exceeds the early undamped stage's accuracy tolerance
by 25×, then passes the final one.

## 2. The reference run: PC-001 M1

`results/validation/cleaned_interfaces/PC-001/M1/` is the default `modal_fixed` method on
all 30 cases (2026-10-04, code `583b4e0f`, CUDA, four frequency threads, two case
workers). **26/30 recovered: 9, 9 and 8 at contrasts 0.5, 4 and 13.3.** The summed case
time is 1,031 s; the median case takes 31.4 s, the median recovered case 27.9 s. On this branch a fresh
`circle__c0.5` fit reproduces its RMS to about nine significant figures.

| Case | Recovered | RMS mm | Hausdorff upper mm | Max residual | Seconds |
|---|---|---:|---:|---:|---:|
| `circle__c0.5` | yes | 7.82e-06 | 0.019 | 1.0e-06 | 6.0 |
| `circle__c4` | yes | 1.61e-05 | 0.019 | 1.3e-05 | 6.3 |
| `circle__c13.3` | yes | 5.37e-05 | 0.019 | 4.2e-08 | 7.5 |
| `kite__c0.5` | yes | 1.45e-02 | 0.073 | 4.8e-06 | 91.2 |
| `kite__c4` | yes | 1.45e-02 | 0.061 | 1.2e-05 | 37.5 |
| `kite__c13.3` | yes | 1.55e-02 | 0.071 | 6.9e-05 | 56.1 |
| `peanut__c0.5` | yes | 2.16e-03 | 0.026 | 1.2e-07 | 20.2 |
| `peanut__c4` | yes | 1.67e-03 | 0.024 | 2.3e-07 | 18.6 |
| `peanut__c13.3` | yes | 5.98e-04 | 0.022 | 1.9e-07 | 21.4 |
| `star__c0.5` | yes | 1.91e-02 | 0.083 | 6.3e-06 | 21.4 |
| `star__c4` | yes | 3.50e-03 | 0.039 | 8.0e-07 | 33.2 |
| `star__c13.3` | yes | 1.40e-03 | 0.034 | 4.2e-07 | 60.1 |
| `asymmetric__c0.5` | yes | 1.24e-02 | 0.074 | 7.5e-06 | 25.7 |
| `asymmetric__c4` | yes | 4.57e-03 | 0.044 | 2.3e-06 | 34.0 |
| `asymmetric__c13.3` | yes | 3.18e-03 | 0.041 | 9.4e-06 | 45.2 |
| `c_shape__c0.5` | yes | 4.28e-04 | 0.029 | 8.7e-08 | 23.0 |
| `c_shape__c4` | yes | 6.22e-04 | 0.030 | 3.1e-07 | 34.7 |
| `c_shape__c13.3` | yes | 3.05e-05 | 0.027 | 2.2e-06 | 36.1 |
| `hook__c0.5` | yes | 1.13e-03 | 0.030 | 1.8e-07 | 26.5 |
| `hook__c4` | yes | 1.25e-03 | 0.031 | 4.7e-07 | 49.0 |
| `hook__c13.3` | **no** | 8.66 | 25.133 | 1.6 | 36.1 |
| `cross__c0.5` | yes | 2.79e-03 | 0.030 | 2.4e-07 | 25.8 |
| `cross__c4` | yes | 2.32e-03 | 0.027 | 6.9e-07 | 25.8 |
| `cross__c13.3` | yes | 1.33e-04 | 0.023 | 1.1e-07 | 45.0 |
| `cog__c0.5` | yes | 5.04e-02 | 0.169 | 9.7e-06 | 27.5 |
| `cog__c4` | yes | 8.44e-03 | 0.045 | 2.7e-06 | 28.4 |
| `cog__c13.3` | yes | 9.47e-04 | 0.031 | 2.7e-07 | 73.1 |
| `aphex_twin__c0.5` | **no** | 4.40 | 11.059 | 1.3 | 29.6 |
| `aphex_twin__c4` | **no** | 1.69 | 5.150 | 0.76 | 38.4 |
| `aphex_twin__c13.3` | **no** | 4.15 | 14.124 | 1.7 | 47.8 |

All four failures stop with `NUMERICAL_FAILURE`: "candidate leaves the frozen
numerical-resolution regime". Hook 13.3 and aphex 4 stop in `release_M11`, aphex 0.5 and
13.3 in `stage_3_damped`. Aphex 13.3 also fails its final numerical check.

## 3. Physics: modal Müller

The modal service replaced boundary collocation with a Fourier–Galerkin Müller
formulation. Its trace cutoff `K_trace` sets the number of trace unknowns.

### 3.1 Accuracy and the two fixes

- **Service fixtures (2026-09-30).** C-shape at 2.5 GHz with K_trace 64: field 1.37e-8,
  Jacobian 9.11e-8 relative. An inverse endpoint at K_trace 128: 1.8e-12 and 5.4e-12.
  Damped 2.5 GHz has a floor near 6e-9 from cancellation. Three archived inverse stages
  replay every trial decision, accepted index and work count.
- **CUDA (2026-10-01).** CUDA versus CPU: Jacobians within 7.6e-12, fields within
  2.7e-12 (3.7e-9 at damped 2.5 GHz, the same floor). CUDA error against a 2048-node
  Kress reference stays within 2× of the CPU error on every fixture.
- **First all-36 campaign (CI-001-modal, 2026-10-01).** Modal 19/36 versus nodal 28/36.
  27/36 cases made identical decisions, with endpoints within 2.3e-7 mm, in about 3× less
  time (923 s versus 2,754 s). The nine differences had two causes:
  1. Graf expansion refused offset starts (7 cases): 131–248 orders were needed, the
     cap was 128, and the unscaled Hankel function overflows near order 150.
  2. The production trace cutoff was too coarse at contrast 13.3 (2 cases): K_trace 96
     gave 1.3–9.3e-8 error at 2.1–2.5 GHz, within 2× of the 1e-7 acceptance tolerance.
     K_trace 128 gave ≤ 3.8e-10 and 160 gave ≤ 1.1e-12.
- **Fixes.** The Graf step now runs in scaled form with a proved tail bound and no order
  cap; the scaled Hankel recurrence agrees with mpmath to about 3e-15 up to order 120,
  where SciPy's `hankel1` is off by 1e-5. The production cutoff became
  `K_trace = max(64, 32·(ceil(K/64)+1))`: 128/160 at K = 192 instead of 96/128. 7/9
  affected cases then matched nodal in decisions and work, RMS within 2.7e-7 mm.
- **The cutoff a curve needs depends on the curve.** The contrast-13.3 C stop needed
  K_trace ≈ 192–224 to match Kress 512 accuracy: 1e-7 at 128, 2.3e-9 at 160,
  3.8e-11 at 192. The current rule picks the cutoff from the storage band only.

### 3.2 Against nodal Kress on TG-002

| Run | Physics, geometry update | Recovered | Median time, all cases | Note |
|---|---|---:|---:|---|
| PC-001 M1 | modal, certified spectral | 26/30 | 31 s | reference run |
| PC-001 N1 | nodal N512, certified spectral, one promotion to N1024/2048 | 26/30 | 157 s | same 26 cases; the four promoted failures took 814–1,863 s and recovered none |
| PC-001 N0 | nodal N512, spline | 12/12 run | 120 s | stopped by the user after 12 cases |
| PC-002 | nodal, spline, fair profile (N130 early, N386 at K192, geometry reused across frequencies) | 26/30 | 48.18 s fit | same 26 cases; 60/60 independent N1024/N2048 comparisons pass |

M1 and N1 final RMS values agree to about eight significant figures. These timings are
not a matched speedup: PC-001 used two workers and PC-002 one, the audits differ, and N1
rebuilt nodal geometry for every frequency. The historical M1 to PC-002 fit-time ratio
is about 1.69.

### 3.3 Analytic radial coefficients and the cost of one solve

AC-001 builds all six radial coefficient arrays from analytic Bessel-product formulas,
with no radial sampling or DCT. Over 24 scalar cases (contrasts 0.5/4/13.3, real and
damped, up to alpha 96.49):

- against a 4096-point DCT reference, the worst coefficient l1 error is 6.37e-13 of the
  reference l1 norm;
- against 80-digit Bessel/Hankel values, the worst absolute error is 2.18e-13 of the
  coefficient l1 norm.

Forward comparison at 2.5 GHz, contrast 13.3, K_trace 96, against a CPU N1024 nodal
reference (relative errors):

| Geometry / damping | Analytic matrix | DCT matrix | Analytic field | DCT field |
|---|---:|---:|---:|---:|
| Circle / real | 2.79e-13 | 2.76e-13 | 1.43e-13 | 1.38e-13 |
| Circle / 25% | 2.58e-11 | 2.81e-11 | 5.35e-12 | 9.28e-12 |
| C-shape / real | 3.62e-13 | 3.82e-13 | 9.01e-13 | 1.19e-12 |
| C-shape / 25% | 9.07e-9 | 1.13e-8 | 2.85e-9 | 5.10e-9 |

Scalar setup is 2.76× slower than the DCT (median 1.00 ms versus 0.354 ms). Extended
precision was needed: float64 versions gave 3.63e-8 and 5.46e-8 on the damped C-shape,
above the 2.26e-8 tolerance.

AC-002 timed one CUDA forward solve (C-shape truth, contrast 13.3, 2.5 GHz, K_trace 96,
one thread, mean of three):

| Work | New geometry ms | Share | Reused geometry ms | Share |
|---|---:|---:|---:|---:|
| Log-Chebyshev construction and its certificate | 22.479 | 46.5% | 0 | 0% |
| Radial Chebyshev arrays | 8.877 | 18.4% | 0.026 | 0.2% |
| Scalar analytic coefficients (CPU) | 2.950 | 6.1% | 2.838 | 23.7% |
| Coefficient contraction | 0.632 | 1.3% | 0.657 | 5.5% |
| Remaining assembly and transfer | 1.513 | 3.1% | 1.525 | 12.7% |
| Graf source/receiver waves (CPU) | 7.039 | 14.6% | 2.786 | 23.3% |
| LU (CPU) | 2.707 | 5.6% | 3.011 | 25.1% |
| Solve and receiver fields (CPU) | 1.061 | 2.2% | 1.052 | 8.8% |
| Other setup | 1.092 | 2.3% | 0.088 | 0.7% |
| **Total** | **48.351** | | **11.984** | |

A new curve costs about 4× a repeated one, mostly in geometry construction that is shared
across frequencies. On a repeated curve, LU, scalar coefficients and Graf waves dominate.

## 4. Geometry update: certified spectral

### 4.1 How it was built

Each step was tested on the six CI-001 core cases against nodal CI-001. "Match" means
the same recovery status with no drift flag. "Decision-identical" means the same accepted
steps in every stage and the same work units. σ₀ is the curve length divided by 2π.

| Step | Change | Result | Wall time, six cases |
|---|---|---|---:|
| NU-001 | coefficient normal update | arm A matched 2/6, arm B 3/6, both with drift flags: rejected | — |
| NU-002 | spectral arclength reset | exact within 1e-5 σ₀ at K = 192 (up to r_σ ≈ 3.4), but moved the shape by 1e-4–3e-2 σ₀ at K = 8–20: cannot be used where drift starts | — |
| NU-003 | spectral increment map replaces the spline resampler (nodal physics) | 6/6, decision-identical in all 72 stages (9,677 units); final curves within 6e-8 σ₀; geometry preparation 2.2× slower | +15% |
| NU-004 | NU-003 map with modal physics | 6/6, decision-identical to nodal and to modal + spline | 293 s (nodal 573 s) |
| NU-005 | certificate tiers decide validity before any sampled test | all 1,131 checks decided by certificates, no sampled fallback; bit-identical to NU-004 | 390 s |
| NU-006 | GPU-batched preparation (now the default) | decision-identical to NU-005; final curves within 2.1e-10 σ₀; preparation 149.8 s → 3.9 s | 242 s |
| NU-007a | GPU certificates | 18 inverse pairs pass; certificates 103.5 s → 7.5 s | 247.2 s → 149.6 s |

NU-005's certificate tiers are: exact area, then an increment bound, then the full |W|²
certificate. They can accept a curve but cannot refuse one; refusals still come from the
sampled self-intersection test. In NU-006, certificates were 104 s of 242 s (43%).
NU-007a's times are sums of per-case medians over three repeats per arm, the only
matched timing in this table; the other rows are single runs.

Per-case NU-005 and NU-006 rows are in `NU-005/comparison.csv` and
`NU-006/comparison.csv`; the 72-state NU-006 pre-check is in `NU-006-precheck/precheck.json`;
the NU-007a per-case table is in `NU-007a-20261003/README.md`.

### 4.2 Fixed-move replay on TG-002 states (GC-001)

GC-001 replayed 279 geometry moves from 31 saved TG-002 states, with no fitting. All four
update variants accepted the same 277 moves and refused the same two self-intersections.

| Update | Preparation ms | 1 mm trial ms | 6 mm trial ms |
|---|---:|---:|---:|
| Spline, CPU | 1,133.4 | 33.84 | 34.62 |
| Spectral, CPU, sampled validity | 2,197.0 | 59.50 | 64.56 |
| Spectral, GPU preparation, sampled validity | 41.37 | 65.26 | 65.65 |
| Spectral, GPU preparation, certified validity | 41.46 | 97.60 | 487.10 |

- **Accuracy.** Worst curve error: spline 400.83 nm, spectral 0.1855 nm, both on the same
  aphex 6 mm stress move. The spline error comes from aliasing when uniform-arclength
  samples are FFT-cropped. Refining only that output grid by 8× cut the aphex error to
  0.906 nm.
- **Cost share.** Geometry update was 19.1% of PC-001 M1's summed runtime. Removing it
  entirely would give at most about 1.24× overall.
- **Certificates on large moves** cost 487 ms against 66 ms for the sampled test, with the
  same decisions on all 279 moves.

### 4.3 The Gaussian update failed (ON-001 F)

`gaussian_lipschitz` failed its saved-state check of the complete proposed move: 11/16
passed, and 10/16 after a correction. It was never used in a fit. It is not a replacement
for `certified_spectral`.

## 5. Policy options

`bem_inverse.policies` names every tested variant. Each row differs from its parent by
one change.

| Policy | Status | Evidence | Result |
|---|---|---|---|
| `baseline` | default | PC-001 M1, ON-001 B | 26/30 |
| `accuracy_exit` | qualified | ON-001 E vs B, all 30 | 26/30, 1.546× median speedup |
| `feedback` | qualified | DP-001 F vs E, all 30 | 26/30, 1.134× median speedup |
| `decision_gate` | experimental | RG-001 vs E, all 30 | 26/30, no new recovery, slower failures |
| `four_phase` | candidate | CS-001, 8 cases | 4/8 vs 5/8 control: one regression |
| `reach_clip` | rejected | ON-001 G, 8 cases | 4/8, 0.924× (slower) |
| `working_frequencies` | rejected | ON-001 W, 8 cases | 4/8, every success slower (0.890×) |
| `validity_first`, `entry_reuse`, `exact_fast`, `compact_release`, `resolution_response`, `adaptive_resolution` | candidate | **none** | never run; see 5.5 |

### 5.1 `accuracy_exit` (ON-001)

The fit stops at the first accepted full-catalog state whose largest residual is ≤ 0.003,
once that state passes its final numerical check. All 30 fresh B/E pairs:

| Quantity | B (baseline) | E (`accuracy_exit`) |
|---|---:|---:|
| Recovered | 26/30 | 26/30 (same cases) |
| Summed output seconds, all 30 | 803.35 | 550.99 |
| Summed fit seconds | 685.96 | 438.03 |
| Median recovered output seconds | 22.41 | 13.72 |
| Work units, fit plus checks | 63,619 | 41,531 |
| Proposals / accepted | 2,511 / 1,826 | 2,145 / 1,572 |
| Geometry refusals | 43 | 43 |

- **Speed.** Median paired speedup 1.546× (10th percentile 1.225×); every common success
  was faster.
- **Repeated timing.** Three repeats per case: circle 4 1.240×, kite 0.5 3.857×,
  star 13.3 1.600×.
- **Accuracy cost.** Median recovered RMS rises from 0.00191 to 0.01498 mm. The worst is
  0.188 mm (kite 0.5), still far inside 1 mm.

The per-case table is `ON-001/final_table.md`.

### 5.2 `feedback` (DP-001)

`feedback` adds three changes on top of `accuracy_exit`:
- agreement-based damping with a scaled curvature floor and a stop on shortened progress;
- no Jacobian rebuild after the last step;
- final checks run two frequencies at a time.

Results:
- **Recovery:** 26/30 in both arms, same cases.
- **Speed:** median paired speedup 1.134× (10th percentile 1.101×); 26/26 successes were
  faster.
- **Totals:** summed time 552.62 s → 506.30 s (8.4% less). The four failures took slightly
  longer, 116.05 s → 120.24 s.
- **Damping floor:** the smallest damping went from 1.05e-14 to 1.05e-6.
- **Accuracy:** largest recovered RMS 0.188284 → 0.188331 mm.

The test checked the three changes together, not each one separately.

| Failure | E RMS mm / s | F RMS mm / s |
|---|---:|---:|
| `aphex_twin__c0.5` | 4.3983 / 20.37 | 4.4751 / 21.68 |
| `aphex_twin__c4` | 1.6854 / 27.55 | 1.6855 / 24.34 |
| `aphex_twin__c13.3` | 4.1524 / 42.04 | 2.5703 / 51.09 |
| `hook__c13.3` | 8.6575 / 26.09 | 8.6531 / 23.12 |

### 5.3 `decision_gate` (RG-001)

When a trial fails the field accuracy test, this option keeps the production/refined
gain decision instead of stopping the fit. Results:
- **Recovery:** 26/30, with no new recovery.
- **Same paths:** all 26 successes reproduced ON-001 E's accepted paths bitwise.
- **Time:** the suite total rose from 554.11 s to 841.09 s, because failures ran on.

| Failure | Stop RMS mm | With gate RMS mm | Accepted inaccurate steps |
|---|---:|---:|---:|
| `aphex_twin__c0.5` | 4.398 | 3.868 | 1 |
| `aphex_twin__c4` | 1.685 | 0.664 | 25 |
| `aphex_twin__c13.3` | 4.152 | 3.948 | 45 |
| `hook__c13.3` | 8.657 | 7.969 | 19 |

All four failure endpoints fail the field accuracy test. Aphex 4 gets within 1 mm RMS
but fails the Hausdorff and residual limits. Longer budgets outside the benchmark gave no
recovery either: aphex 0.5 and hook 13.3 kept the same endpoints, and aphex 13.3 reached
3.776 mm.

### 5.4 `four_phase` (CS-001)

This option fits position and size first (exact translation and scaling at damped
0.25 GHz) and keeps the frequency ladder. It then runs four compact all-frequency shape
stages at (M, K) = (11,24), (15,32), (19,40), (25,52) before full release (95,192).

| Case | Control | Revised | RMS mm control / revised | Seconds control / revised |
|---|---|---|---|---|
| circle 4 | pass | pass | 0.000016 / 0.000011 | 4.09 / 2.53 |
| kite 4 | pass | pass | 0.1322 / 0.1317 | 11.96 / 8.10 |
| peanut 0.5 | pass | pass | 0.0260 / 0.0250 | 6.91 / 4.54 |
| cog 4 | pass | pass | 0.0397 / 0.0381 | 14.05 / 9.86 |
| C-shape 13.3 | pass | **fail** | 0.000359 / 0.2510 | 21.19 / 10.36 |
| hook 13.3 | fail | fail | 8.6531 / 8.7150 | 22.91 / 20.78 |
| aphex 4 | fail | fail | 1.6855 / 1.7611 | 24.26 / 33.81 |
| aphex 13.3 | fail | fail | 2.5703 / 2.7348 | 51.36 / 40.86 |

The four shared successes were 1.499× faster at the median. The C-shape regression
stopped at the second shape stage (M15/K32), where a 2.5 GHz trial's production/refined
difference was 1.128e-7 against the 1e-7 tolerance. Compact storage maps to trace
cutoffs 64/96 instead of the control's 128/160, so the schedule also lowered the physics
resolution. No case reached full release.

### 5.5 Six candidates have no evidence

`validity_first`, `entry_reuse`, `exact_fast`, `compact_release`, `resolution_response`
and `adaptive_resolution` were registered for a screen (PS-001) that never ran. No plan
or result was recorded. Their stated targets are motivations, not measurements.

## 6. Where the time goes and what each check decides

From ON-001 E's receipts. Times are summed single-case measurements.

| Output time | 26 recovered | 4 failures | All 30 |
|---|---:|---:|---:|
| Fitting | 336.23 s | 101.80 s | 438.03 s |
| Final and early numerical checks | 82.22 s | 11.52 s | 93.74 s |
| Setup and output | 16.68 s | 2.54 s | 19.22 s |
| **Total** | **435.14 s** | **115.85 s** | **550.99 s** |

These geometry timers sit inside the rows above and must not be added to them:

| Geometry, nested | Successes | Failures |
|---|---:|---:|
| Preparation | 19.08 s | 2.03 s |
| Complete trials | 41.08 s | 47.72 s |
| of which certificates | 19.05 s | 46.14 s |
| of which projection quadrature | 13.33 s | 0.49 s |

Physics phase durations summed over threads, all 30 cases: assembly 300.39 s, waves
232.99 s, LU 197.72 s, modal geometry 105.49 s, fields 64.39 s, Jacobian 19.51 s. They
overlap across four frequency threads, so they rank targets but are not wall-time shares.

What each check changed on the saved B and E paths:

| Check | Decisions it changed |
|---|---|
| Coarse moved-curve validity | all 43 refusals |
| Fine refit and its agreement test | none |
| Fine moved-curve validity | none |
| Final candidate validity | none |
| Certificate tiers | 75–78% of checks settled by the cheap increment tier; no sampled fallback |
| Refined re-solve before acceptance | in the 26 successes, 1,660 checks and 1,313 accepts; accepting on production gain alone changes 0 decisions. In the failures, 393 checks and 4 changed decisions |
| Step halving | 1,288 of 1,313 accepted steps were full length; 25 needed one halving |

The refined re-solves are nearly half of all forward solves in successful fits. These
counts support testing fewer checks; they do not prove a check is safe to delete. A
changed update produces different proposals, and every failed case diverged.

## 7. The four failures

### 7.1 The same four everywhere

`aphex_twin` at all three contrasts and `hook__c13.3` fail in every default-pipeline
variant: PC-001 M1 and N1, PC-002, ON-001 B and E, DP-001 E and F, RG-001. Each stops
when a candidate's production and refined fields differ by more than the stage tolerance
(1e-7 above 0.5 GHz, 1e-5 at or below): the trial needs more physics resolution than the
stage allows. `modal_fixed` has no response to
that, so the fit ends there.

| Approach | Result on the four |
|---|---|
| Nodal promotion to N1024/2048 (PC-001 N1) | ran further, 814–1,863 s each; 0 recovered |
| Fair nodal profile (PC-002) | same four fail at the same kind of stop |
| Accept inaccurate steps (RG-001) | 0 recovered; aphex 4 reached 0.664 mm RMS but failed the other limits |
| Damping feedback (DP-001) | 0 recovered; aphex 13.3 RMS 4.15 → 2.57 mm |
| Four-phase schedule (CS-001) | 0 recovered; aphex 4 refused with "\|W\|² lower bound not certified" |
| Four-control schedule with adaptive trace cutoff (MA-007) | **hook 13.3 recovered**; aphex not tried |

### 7.2 MA-007: hook 13.3 recovered

MA-007 ran 18 settings on `hook__c13.3` from the standard start. It used
`FourControlPolicy` (`solvers/bem_inverse/four_control_policy.py`) and
`IndependentModalMuller` (`solvers/bem_inverse/modal_accuracy.py`). The `feedback`
control fails this case: `NUMERICAL_FAILURE` in `release_M11`, 8.653 mm RMS.

The four controls are:
- **F**, the highest fitted frequency;
- **M**, the update band;
- **K**, the stored curve band;
- **Ku**, the modal trace cutoff.

Schedule S0 starts with a damped 0.25 GHz warm-up. It then raises (F GHz, M, K) together
through eight slots: (0.5,3,8), (0.75,5,12), (1.0,7,16), (1.25,9,20), then the switch to
real data, (1.5,11,24), (1.75,19,40), (2.0,37,96), (2.5,95,192). Besides the usual stops,
a slot ends when its loss improves by less than 1% over its last 5 accepted steps.

Ku starts at 64. It rises by one rung (64, 96, 128, …) whenever the next 32 modes change
the fields, the Jacobian or the first proposal. G is `FourControlPolicy()` with its
defaults: caps (2.5, 95, 192, 192) for (F, M, K, Ku), order S0.

| ID | Caps F/M/K/Ku | Recovered | RMS mm | Max residual % | Fit units | Seconds | Outcome |
|---|---|---|---:|---:|---:|---:|---|
| G | 2.5/95/192/192 | yes | 0.000434 | 0.0365 | 4,473 | 103.67 | REQUIRED_ACCURACY_REACHED |
| F0 | 1.0/95/192/192 | no | 0.006307 | 1.580 | 4,837 | 136.66 | COMPLETED_SCHEDULE |
| F1 | 1.5/95/192/192 | no | 0.003981 | 0.474 | 5,354 | 133.19 | COMPLETED_SCHEDULE |
| M0 | 2.5/19/192/192 | no | 0.046726 | 3.664 | 4,745 | 107.85 | COMPLETED_SCHEDULE |
| M1 | 2.5/37/192/192 | yes | 0.000434 | 0.0365 | 4,397 | 100.97 | REQUIRED_ACCURACY_REACHED |
| K0 | 2.5/95/32/192 | yes | 0.000211 | 0.0223 | 6,590 | 140.50 | TRIAL_WALL_LIMIT |
| K1 | 2.5/95/64/192 | yes | 0.000434 | 0.0365 | 4,397 | 99.43 | REQUIRED_ACCURACY_REACHED |
| U0 | 2.5/95/192/64 | no | 0.036539 | 8.831 | 6,275 | 142.59 | TRIAL_WALL_LIMIT |
| U1 | 2.5/95/192/128 | yes | 0.000434 | 0.0365 | 4,473 | 102.74 | REQUIRED_ACCURACY_REACHED |
| G_E0 | G, old rung exits | yes | 0.000433 | 0.0364 | 5,293 | 118.61 | REQUIRED_ACCURACY_REACHED |
| O1 | M1 caps, F and Ku first | no | 9.399324 | 160.0 | 7,474 | 138.86 | TRIAL_WALL_LIMIT |
| O2 | M1 caps, M and K first | yes | 0.001884 | 0.215 | 3,511 | 140.87 | TRIAL_WALL_LIMIT |
| O3 | M1 caps, F and M first | no | 0.139741 | 30.5 | 6,424 | 138.99 | TRIAL_WALL_LIMIT |
| O4 | M1 caps, K and Ku first | no | 8.474925 | 191.8 | 2,949 | 111.72 | KU_CAP_UNRESOLVED |
| O5 | M1 caps, F and K first | no | 9.398282 | 159.0 | 7,515 | 139.84 | TRIAL_WALL_LIMIT |
| O6 | M1 caps, M and Ku first | no | 4.050856 | 188.1 | 535 | 81.17 | NUMERICAL_FAILURE |
| O7 | M1 caps, all four together | yes | 0.000725 | 0.117 | 4,274 | 105.46 | REQUIRED_ACCURACY_REACHED |
| O8 | M1 caps, adaptive contests | no | 9.318069 | 161.9 | 2,342 | 136.27 | TRIAL_WALL_LIMIT |

Seconds are the audited fit return, including checks. What the runs show on this case:

- **The full 2.5 GHz catalog is needed.** F0 and F1 fit their own frequencies to
  about 1e-6, and their RMS is below 0.01 mm. They still miss the omitted frequencies by
  1.58% and 0.47%, worst at 2.0 GHz. A good-looking outline is not enough.
- **M37 is enough on this path; M19 is not.** G entered M95 but accepted no move there.
- **K32, K64 and K192 all recover.** K32 needed 49.9% more work and hit the time limit.
- **Ku64 fails, Ku128 recovers.** G raised Ku to 96 when a candidate's field comparison
  failed, then to 128 at the final stage. With Ku capped at 64, U0 refused 22 candidates
  at its cap.
- **The order of release matters.** Six of eight orderings fail. Raising Ku early does
  not supply missing shape directions (O1, O4).

These are single runs on one scene. They show individually sufficient settings, not
tested upper limits. The combined reduced caps were never run. No result shows how S0
does on aphex or on the other 26 cases.

MA-007 ran each setting with this call; it has not been rerun on this branch:

```python
from bem_inverse.four_control_policy import FourControlPolicy
from bem_inverse.modal_accuracy import IndependentModalMuller
from bem_inverse.physics import Execution
from bem_inverse.runner import fit
from experiments.benchmark import campaign as c

execution = Execution(device='cuda', frequency_threads=4, audit_frequency_batch=2)
physics = IndependentModalMuller(execution, trace_cap=192, workspace=512)
result = fit(c.problem('hook__c13.3'), solver='modal_muller', physics=physics, execution=execution,
             policy=FourControlPolicy(), geometry_update='certified_spectral',
             localization_adapter=c.keep_start, output='<fresh run directory>')
```

## 8. Kept code with only legacy evidence

These modules are still imported by the pipeline but have no TG-002 evidence.

- **Relaxed BIE and full-matrix observations** (`full_matrix`, `relaxed_gradient`), nodal
  physics only. FM-002: damping recovered 3/3 cases with or without relaxation, and the
  real prefix 1/3 with or without. RB-001 removed all four immediate stops but recovered
  0/4. All on legacy CI-001 cases.
- **Nodal resolution promotion** (`nodal_fixed`): PC-001 N1 above; no recovery added.
- **Grid localization** (`mie_localize`, `mie_grid`): retired with far starts (section 1).
- **Fair nodal profile** (`nodal_geometry`, `nodal_resolution`): PC-002 above.

## 9. Not established

- That TG-002 needs no grid search: NL-001 was never run.
- Any noisy-data result: TG-002 is noiseless.
- Matched modal versus nodal speed: every comparison above differs in workers, audits or
  geometry reuse.
- Timing confidence intervals: almost all timings are single runs.
- The six unscreened candidate policies (section 5.5).
- Any recovery of aphex at any contrast.
- The four-control schedule beyond `hook__c13.3`.

## 10. Data files on this branch

All paths are under `results/validation/`.

| Section | Files |
|---|---|
| 1, 2 | `cleaned_interfaces/TG-002/` (sealed inputs); `cleaned_interfaces/PC-001/M1/` (every receipt of the reference run) |
| 3.1 | `cleaned_interfaces/CI-001-modal-review/README.md`, `modal-muller-cuda-20261001/README.md`, `modal-muller-fixes-20261001/README.md` |
| 3.2 | `cleaned_interfaces/PC-001/report.md`, `comparison.csv`; `cleaned_interfaces/PC-002/README.md` |
| 3.3 | `cleaned_interfaces/AC-001/scalars.json`, `forward.json`; `cleaned_interfaces/AC-002/profile.json` |
| 4.1 | `cleaned_interfaces/NU-005/comparison.csv`, `NU-006/comparison.csv`, `NU-006-precheck/precheck.json`, `NU-007a-20261003/README.md` |
| 4.2 | `cleaned_interfaces/GC-001/README.md` |
| 4.3, 5.1, 6 | `cleaned_interfaces/ON-001/final_table.md`, `final_comparison.json`; `cleaned_interfaces/inverse-pipeline-audit-20261005/receipt_analysis.json` |
| 5.2 | `cleaned_interfaces/DP-001/table.md`, `final_comparison.json` |
| 5.3 | `cleaned_interfaces/RG-001/table.md`, `timing_table.md`, `closeout.json` |
| 5.4 | `cleaned_interfaces/CS-001/table.md`, `report.json` |
| 7.2 | `modal_atlas/MA-007/research18-001/results.md`, `results.csv`, `summary.json`, `actual_paths.json` |

Links inside the kept README files may point to files that exist only on
`feature/shape-frequency-continuation`. The full write-ups, run folders and source
archives are there at commit `a64de2eed`. They are not needed to check the numbers above.
