# PC-002 results — fair nodal+spline

Completed 2026-10-04: all ten TG-002 scenes × contrasts 0.5/4/13.3,
one centred start, no localization/grid/restarts. **26/30 recovered**:
9/10, 9/10, 8/10 by contrast. The recovery set is exactly PC-001 M1/N1's.

| Measure | Result |
|---|---:|
| Median fitting time, including stage-entry resolution selection | 48.18 s |
| Median initial + endpoint audit time | 54.82 s |
| Median total time | 100.58 s |
| Sum of per-case total time, one worker | 54.56 min |
| Selected nodal resolutions | N130 early, N386 at K_geometry192 |
| Stage-entry escalations / trial promotions / CPU fallbacks | 0 / 0 / 0 |
| Geometry builds / hits | 8,203 / 40,494 |
| Geometry build wall time, summed over fits | 9.99 s |
| Native initial/final audits passed | 58/60 |
| Independent N1024/N2048 comparisons + full-trial FD passed | 60/60 |

Medians are separate summaries and do not add. Selection cost totals 436.60 s
across the 30 fits and is charged to stage/global work and fitting wall time.
Geometry cache retention is bounded to four entries and 256 MiB each of host
and device geometry. Reported peak device geometry is 456.06 MiB, including a
new preparation before eviction; this is distinct from retained cache bytes.
All fit-exit cache receipts contain zero retained entries/bytes.

All four failures stopped when a candidate left the frozen resolution regime:
Aphex Twin at all three contrasts and hook at 13.3. Aphex 0.5/4 have qualified
native endpoints but fail geometry/data recovery; hook13.3 and Aphex13.3 also
fail native all-real field agreement. Independent N1024/N2048 field/Jacobian
comparisons and full-trial FD pass for every start and returned endpoint.
Their failure evidence is preserved; no promotion or restart was introduced.

## What the speed evidence establishes

The fixed512 floor is unnecessary for the 26 recovered cases under this
policy: N130/N386 passes the independent endpoint checks and retains the same
recoveries. Frequency-independent nodal boundary/pair geometry is shared
across frequency systems and retained forward handles use it for Jacobians.
Source/receiver wave evaluation and Jacobian contraction remain CPU; LU and
reciprocal solves were CUDA throughout. Acquisition-distance hoisting is deferred.

| Historical fit median on common cases | PC-001 | PC-002 NS | Cases |
|---|---:|---:|---:|
| M1 modal + certified spectral | 28.43 s | 48.18 s | 30 |
| N1 fixed512 nodal + certified spectral, promotion enabled | 137.38 s | 48.18 s | 30 |
| N0 fixed512 nodal + spline, stopped campaign | 100.29 s | 41.85 s | 12 |

These are historical comparisons, **not controlled speedup estimates**:
PC-001 used two case workers, PC-002 one; geometry updates differ for M1/N1,
audits differ, and N1 has a promotion response. The approximately fivefold
PC-001 total-time gap cannot be presented as an isolated modal physics speedup.
The current historical fit-time ratio M1 versus NS is about 1.69, also not a
validated matched speedup. Fresh MS/NC controls, identical audit/warm-up/worker
conditions and LU-device controls remain deferred under the priority amendment.

## Provenance and validation

Fit source `1b4dfdab3704967828df75d189e845bd1a6bc08c` was committed/pushed before
fitting. Input seal SHA256:
`34375b59a40ed8e945904b246d3022bdeeeacb2291fced1bafc16f6861be7b00`.
Protocol records the source hashes, idle RTX5090 preflight, one case worker,
four frequency threads, and one BLAS thread. No warm-up was excluded.

Pre-fit validation: 177 unique affected checks pass after a corrected new test
fixture; the original failed fixture log is retained. After fitting, independent
reference token selection was moved behind the physics service hook, removing
a nodal-name check from the generic audit. This changes no resolutions/math;
the added opaque-name test and the final package/interface suite pass (51 tests).
The fit source and numerical source hashes stay recorded unchanged for reproduction.
Read-only bundle validation checks all 30 IDs/settings, all 60 independent
reference audits, exact dispatched work accounting, cache release, zero fallback,
the original numerical source hashes and the frozen input seal.

[Per-case table and gallery](../../../../results/validation/cleaned_interfaces/PC-002/README.md)
· [receipt validation](../../../../results/validation/cleaned_interfaces/PC-002/validation/result-bundle.json)
· [approved priority plan](03_plan.md).
