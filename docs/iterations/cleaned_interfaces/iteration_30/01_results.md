# GC-001: geometry precision, runtime and where the differences originate

2026-10-05. Main replay completed from committed source `97f1a327` under the
[approved registration](../iteration_29/03_plan.md). Its six phases took
**838.73 s (13.98 minutes)**. No new inverse fitting or physics solves.

Validated coverage: 31 distinct fixed TG-002/PC-002 states, 279 common moves,
11 repeated-timing states with three repeats per arm, five preparation/FD/profile
diagnostic states, six predeclared largest-disagreement interpolation probes.
All four arms accepted 277 moves and refused the same two self-intersections.
There were zero decision disagreements and zero device fallbacks. 278/279
refined curve references and all 15 derivative references qualified. The one
unresolved curve reference is `kite__c4 / 0.006m-d2`; exclude it from accuracy
rankings. Raw measurements, source hashes, errors and validation are retained in
the [result bundle](../../../../results/validation/cleaned_interfaces/GC-001/README.md).

## Geometry runtime

Median of per-state medians on the 11-state repeated panel, milliseconds:

| Geometry arm | Preparation | First 1 mm trial | Subsequent 6 mm trial |
|---|---:|---:|---:|
| Spline CPU | 1,133.4 | 33.84 | 34.62 |
| Spectral CPU, sampled validity | 2,197.0 | 59.50 | 64.56 |
| GPU-prepared spectral, sampled validity | 41.37 | 65.26 | 65.65 |
| GPU-prepared spectral, certified validity | 41.46 | 97.60 | 487.10 |

The two trial columns use different moves/sizes; they are not a controlled
measurement of cache warm-up. The preparation paired median speedups are
27.10x versus spline and 54.75x versus sequential CPU spectral. GPU preparation
does not make the finite trial projection GPU-resident; that remains CPU.
The 6 mm certificate timings are stress-move costs, not representative LM
averages to substitute into the full-inverse receipts.

The exclusive diagnostic profiles identify repeated normal-basis construction
as the largest spline preparation component (1.45 of 3.17 s across the fixed
five-state profile panel). CPU spectral also spends 2.31 s in coefficient
quadrature and 1.54 s in crop reconstruction (6.62 s total). These are profiled
times, distinct from the uninstrumented headline measurements. GPU batching
reuses the base basis/geometry within the perturbation batch; its phase and
quadrature arithmetic run on device, with transfers included in wall time.

On the high-band circle/hook/kite diagnostic states, removing only the unused
crop diagnostic cuts CPU spectral preparation by approximately 19–24%, with
bit-identical derivative coefficients. Batched Torch CPU preparation takes
5.4–6.3 s versus 1.9–2.3 s for sequential NumPy spectral. The same batched
calculation takes 0.036–0.042 s on CUDA. Thus neither batching alone nor skipped
diagnostics explains the GPU gain: hardware execution, shared geometry and
the different phase-evaluation implementation all contribute. These ablation
times are single diagnostic runs, not the three-repeat headline panel.

## Precision and interpretation

On the 278 qualified references, the worst parameter-aligned curve errors are
**400.83 nm for spline and 0.1855 nm for spectral**. Median errors are 0.000737
and 0.00000285 nm; many small moves are at floating-point round-off, so these
are computed refinement/reference differences, not physical accuracy guarantees.
At 1 mm steps, spline's worst error is only 0.2023 nm. Both worst-error arms
occur on the same aphex 6 mm stress move. Maximum normal and tangential S/F
differences are 377.86 and 215.39 nm, respectively: it is not solely a gauge
shift. The biggest spline difference approaches the internal 1e-5 sigma0
projection tolerance, despite being far below the 1 mm recovery gate.

At native derivative step 1e-7 m, the largest spline/CPU-spectral geometry-column
disagreement is 5.45e-7 relative; CUDA/CPU-spectral is 1.46e-8. In the fixed
five-state 1e-6/1e-7/1e-8 m sweep, the largest native/reference column error is
1.33e-7. Smaller steps expose cancellation/rounding; no systematic accuracy
improvement follows from shrinking the FD step. These are geometry derivatives,
not a validation of physical field Jacobians on changed inverse paths.

The six factorial interpolation checks do not support the hypothesis that
cubic inverse/position interpolation dominates the large stress errors:
replacing both leaves approximately the same error. An adaptive, bounded
[attribution continuation](../iteration_29/05_attribution_continuation.md) on
the **same six moves** will vary only the final arclength output sampling grid
before FFT cropping, then separately the speed/arclength integration grid.
Main measurements remain intact. Attribution beyond this point is pending
that discriminating check.

## Bigger picture

Recorded boundary-update geometry takes 19.10% of summed PC-001 M1 total
runtime and 19.45% of PC-002 NS total runtime; median case shares are 15.54%
and 15.61%. N1's median share was 3.08%, explaining why the old fixed-floor
baseline could make geometry look negligible. Its long failed/promoted cases
raise the total-weighted share to 15.21%.

At unchanged physical work/decisions/audits, halving all geometry-update time
saves about 9.5–9.7% overall; eliminating it all gives at most approximately
1.24x. A 27x preparation improvement cannot be quoted as a 27x inverse speedup.
Optimizing preparation while increasing certificate trial cost has competing
effects. About 80% of current complete time lies outside the recorded geometry
update category, including physics/audits and other work; geometry assembly
inside physics is not counted in that category. Exact fitting-only shares are
unavailable from the saved combined geometry counters.

Direct runtime optimization is worthwhile in high-M preparation, but geometry
alone cannot explain a large full-inverse speedup. Spectral gives a larger
numerical margin on big moves, without changing any of this replay's decisions.
The replay supplies no evidence of fixing the four inverse failures or improving
recovery; those are questions about changed inverse trajectories and physical
resolution, outside this geometry-only experiment.
