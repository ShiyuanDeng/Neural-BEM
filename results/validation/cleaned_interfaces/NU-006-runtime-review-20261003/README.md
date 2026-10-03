# NU-006 runtime and GPU geometry investigation

2026-10-03. Read-only investigation of solver implementation, archived full-path
receipts, and a new bounded replay. No numerical implementation or public
selection was changed. This directory contains new evidence only.

## Recorded full-path runtimes

The following are the 2026-10-02 six-core-case records, not a fresh full campaign
or a matched runtime qualification. Hardware was RTX 5090, one case worker,
four frequency threads, and one thread per BLAS pool.

| Arm | Six-case wall seconds |
|---|---:|
| Nodal Kress + spline, CI-001 | 572.8 |
| Modal + spectral, NU-004-MS | 292.6 |
| Modal + certified spectral, NU-005 | 390.3 |
| Modal + certified spectral + GPU prepare, NU-006 | 241.7 |
| Modal + legacy spline control, NU-004-MN | 198.5 |

NU-006 is the fastest completed spectral/certificate arm in this comparison.
It is not the fastest recorded arm overall: the spline control was faster.
All these core comparisons retained the existing `circle_to_star` comparison
regression; matching the reference does not mean every case passed its frozen
quality gate. NU-006 has not established all-36 retention or matched runtime.

| Case | NU-006 wall s | GPU prepare s | CPU certificate s | Certificate share |
|---|---:|---:|---:|---:|
| wrong_circle | 6.18 | 0.27 | 0.12 | 1.9% |
| peanut | 17.27 | 0.52 | 2.25 | 13.1% |
| circle_to_c | 28.86 | 0.55 | 9.91 | 34.3% |
| hook | 40.36 | 0.56 | 18.82 | 46.6% |
| circle_to_star | 21.91 | 0.71 | 4.46 | 20.3% |
| kite | 127.10 | 1.29 | 68.36 | 53.8% |
| Total | 241.69 | 3.91 | 103.92 | 43.0% |

The disjoint wall-time breakdown is 3.91 s preparation, 103.92 s certificates,
9.10 s other trial work, and 124.76 s remaining work. Certificates are included
inside the recorded 113.02 s trial time; do not add those columns together.
Physics counters aggregate concurrent frequency work and cannot be subtracted
as wall-time components.

The trials used 246 accepted-curve certificates and 455 full-tier certificates.
All 1,131 validity checks ended at the increment or full tier. Sampled fallback
took zero time, and there were no prepare fallbacks. Thus the expensive item is
the coefficient certificate, not the polygon intersection fallback.

## Current implementation

- `solvers/bem_inverse/geometry_selection.py` selects `BatchedCertifiedUpdate`
  for `certified_spectral`. The public default remains `spline`.
- `batched.py` accelerates projection/finite-difference preparation with torch
  CUDA; it inherits trial validity from `certified.py`.
- `CertifiedSpectralUpdate._certificate` calls `n_update.curve_certificate`,
  which calls CPU `modal_geometry.log_modulus` and SciPy FFT convolutions.
  It computes log coefficients that the geometry check discards. Trial
  construction, quadrature, and small coefficient checks also remain on CPU.
- `device_certified.py` already contains the NU-007 port. It replaces the
  expensive certificate calculation with torch float64 FFT operations and
  omits unused log coefficients. Small scalar work and quotient construction
  remain on the host. This class is not selected by the public geometry factory.
- CUDA modal physics already computes its own log-modulus certificate in
  `modal_cuda.DeviceModalGeometry`. Its cache is separate from each update
  space's certificate cache. Reuse requires exact curve/window/tolerance
  compatibility; physics uses different windows and tighter log tolerance.

## Why NU-007 was not adopted

The preserved [precheck](../NU-007-precheck/precheck.json) matched decisions,
bit-identical accepted candidate coefficients, and tier sequences in all 864
trials. Certificate time was 1,520.15 s on CPU and 150.88 s on GPU, about 10.1x.
The full inverse campaign never ran because a relative-bound gate failed:
1.54e-5 relative error against a required 1e-9.

The [subsequent diagnostic](../NU-007-precheck/gap.json) found that all 477
relative failures involved bounds below 9.9e-5. The worst error scaled to
max(1, |bound|) was 5.97e-12; the closest bound to the acceptance threshold 1
was 0.00639 away, and no bound crossed that threshold. This supports the
roundoff-floor explanation, while preserving the original failed decision.
Both implementations use a heuristic FFT allowance, not verified interval
arithmetic.

## Current bounded replay

[replay.py](replay.py) uses the maintained package and saved NU-006 states:
wrong-circle warmup, and peanut/hook/kite final M37 states. It performs three
repetitions of three seeded normal-step sizes (1e-7, 0.006, 0.018 m), alternating
arm order between repetitions. Both arms use CUDA preparation; only the
certificate implementation differs. CUDA startup and warmup are excluded;
timing boundaries synchronize the device. The larger diagnostic steps are
not a replay of the actual optimizer's step distribution.

[review.json](review.json) records raw bounds, decisions, tier records, times,
input/source hashes, environment, and archived campaign summaries.
[host-certificate-profile.txt](host-certificate-profile.txt) profiles one
current kite endpoint certificate on CPU. A separate `fm002 qualify` pytest
suite was observed running concurrently, so these timings are diagnostic,
not a quiet-host or full-path runtime qualification.

The current replay completed all 36 paired trials:

| Measurement | NU-006 CPU certificates | NU-007 CUDA certificates |
|---|---:|---:|
| Certificate seconds | 220.05 | 26.96 |
| Complete trial seconds | 222.04 | 28.83 |

Certificate acceleration was 8.16x, and complete-trial acceleration 7.70x.
All decisions, refusal reasons, tier sequences, and accepted coefficient arrays
matched. Three repeated kite trials were refused by both arms. The maximum
threshold-scaled bound difference was 7.80e-14, and the smallest distance of
a recorded bound from 1 was 0.1504. This subset does not test near-threshold
agreement. Tiny warmup-circle certificates did not benefit: 10.3 ms total on
CPU versus 11.2 ms on GPU. The expensive endpoint certificates did benefit.

All recorded source hashes were unchanged when checked after the replay.
The CPU kite certificate profile took 0.239 s, including 0.201 s in 257 FFT
dispatches (about 84%). Its log-modulus construction accounted for 0.219 s.
The existing NU-006 and NU-007 tests passed: 10 passed, zero skipped, including
CUDA coverage. See [validation.json](validation.json) for the command and
[tests.xml](tests.xml) for the test receipt.

## Recommended next work

Qualify the existing NU-007 port before attempting another GPU rewrite.
Define threshold-scaled bound agreement before new runs; retain decision,
tier, candidate, and regularity-floor checks, including near-threshold and
refusal cases. Then compare complete inverse paths with identical inputs and
repeated sequential timing pairs before changing the public selection.

If the observed 8–10x certificate acceleration transfers to the inverse,
241.7 - 103.9 + 103.9/(8 to 10) predicts roughly 148–151 s for these six cases,
about 38–39% less wall time. This is an estimate, not an observed NU-007
campaign result. The zero-certificate-cost lower limit is 137.8 s.

Certificate reuse is a separate follow-up: carry compatible candidate evidence
into the next accepted space and consider sharing with physics. It should not
be conflated with a device-only qualification because changing window or
tolerance can change tier behavior. Porting the remaining 9.10 s of trial work
is a smaller opportunity than removing the current certificate bottleneck.
