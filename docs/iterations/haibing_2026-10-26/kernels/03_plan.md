# HB-001 kernels questions and bounded experiment

1. Do Haibing's Ψ1/Ψ2 primitives reproduce the existing logarithmic operator,
   and does their band structure leave a cheap remainder on actual geometries?
2. Does the incremental Chebyshev recurrence save work or improve a tiny
   kernel difference on an actual accepted TG-002 shape step?

Registered before execution on 2026-10-26. Source: original Word document
§§8–11 and `Haibing_directions.md` items 2 and 4. No inverse fits.

Use saved PS-003/H3 hook c13.3 warmup iteration 0 (K4) and release M11
iteration 15 (K24), at trace band 64. For each, compare j=1,2 analytic
primitives to the existing exact log-symbol assembly. Measure off-band
leakage and structural occupancy. At the low/high real/damped frequencies,
measure extraction size and singular-value ranks of the complete V-block
remainder at relative tolerances 1e-3 and 1e-6. This does not test full Müller
block compression or imply field accuracy.

For item 4, use the actual accepted release iteration 0→1 coefficient
increment at scales 0, 1e-8 and 1. Freeze a common radial interval covering
both endpoints with 10% headroom. Compare direct and incremental recurrence
for the production six radial coefficient functions at the highest real and
damped frequencies, with the same production window 128. Record three
timings per arm (median), anchor preparation separately, recurrence errors,
and zero-step behavior. For the tiny step compare against an independent
extended-precision complex-FFT recurrence on the same projected operators.
Also record the algebraic ΔR and Δq agreement and common-interval bounds.

Stop after these two geometry cases and one step family. Preserve failures.
No maintained solver changes. These component timings exclude full matrix,
source/receiver, log(q), Jacobian and inverse-fit work; no end-to-end claim.
Run on CPU cores 0–3, single-thread BLAS, and record load and peak memory.
