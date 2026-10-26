# Direct evidence for Haibing items 2 and 4

**Item 2 works as an identity, with useful low-frequency compression but a
poor high-frequency remainder in this test. Item 4 improves tiny differences
but takes about twice as long as direct radial recomputation.**

Source correspondence: item 2 is original Word §§8–9, equations 20–25;
item 4 is §§10–11, equations 27–30. These are direct tests of the proposed
operations on saved TG-002 geometry, not the overnight frequency interpolant.

## Item 2 singular weights and bands

We used hook c13.3 from PS-003/H3: warmup iteration 0, K4, and release M11
iteration 15, K24. Both comparisons use N64 and 129×129 single-layer blocks.
The Ψ coefficients use the closed form outside the low modes and recurrence
inside them. The independent comparison uses the existing exact log symbol
on R and R². No numerical quadrature of the logarithmic singularity is used.

| Saved geometry | j | Relative matrix difference | Off-band relative norm | Allowed band occupancy |
|---|---:|---:|---:|---:|
| Warmup K4 | 1 | 4.19e-16 | 1.15e-16 | 12.7% |
| Warmup K4 | 2 | 8.19e-16 | 1.38e-16 | 23.9% |
| Release K24 | 1 | 8.36e-16 | 1.43e-16 | 61.1% |
| Release K24 | 2 | 1.34e-15 | 1.21e-16 | 93.7% |

Occupancy is the fraction permitted by the exact 2jK bandwidth, not the
fraction actually nonzero. The warmup curve is nearly circular, so its
actual sparsity is better. Roundoff accounts for the measured off-band terms.

For the complete V block, we subtracted the proposed singular terms and
measured the smallest SVD rank giving spectral-norm error below 1e-6 times
the **original V norm**. Thus a large remainder does not get a looser target.

| Geometry | Frequency | Original rank | Ps1 remainder rank | Ps2 remainder rank | Ps2 extraction norm / V norm |
|---|---|---:|---:|---:|---:|
| K4 | 0.25 GHz real | 129 | 55 | 29 | 2.58 |
| K4 | 0.25 GHz damped | 129 | 61 | 31 | 4.73 |
| K24 | 0.25 GHz real | 129 | 51 | 42 | 0.182 |
| K24 | 0.25 GHz damped | 129 | 56 | 44 | 0.498 |
| K4 | 2.5 GHz real | 129 | 129 | 129 | 266,953 |
| K4 | 2.5 GHz damped | 129 | 129 | 129 | 733,882 |
| K24 | 2.5 GHz real | 129 | 129 | 129 | 39,070 |
| K24 | 2.5 GHz damped | 129 | 129 | 129 | 120,724 |

The low-frequency rank reduction supports keeping the early-stage idea open.
At the high frequency, Ps1/Ps2 leave no rank reduction at this tolerance.
The extracted and remaining matrices are much larger than their sum, directly
confirming the cancellation concern in the review.

This tests the **complete V remainder**, not the complete Müller-system
remainder. There is no claim about full-system compression, derivatives,
field error, preconditioner quality, or an end-to-end speed-up. The prototype
assembles dense primitives and is not an optimized banded implementation.

## Item 4 incremental geometry and Chebyshev arrays

We replayed the actual accepted hook release M11 iteration 0→1 coefficient
step, then multiplied that increment by 0, 1e-8 and 1. The coefficient window
was 128, matching N64 plus the production margin. No inverse fit was run.

The frozen radial upper bound was 10.50617 in package squared-length units;
the endpoint coefficient upper bounds were 9.55106 and 9.50712. Every tested
candidate remained inside. The finite-increment formulas for R and q agreed
with endpoint subtraction to 3.19e-14 and 2.45e-14 relative, respectively.

All six production radial functions used the same fixed scalar Chebyshev
coefficients on both arms. Three repeated component timings give:

| Frequency | Degree | Direct median, ordinary step | Increment median, ordinary step | Ratio | Anchor array storage |
|---|---:|---:|---:|---:|---:|
| 2.5 GHz real | 62 | 67.9 ms | 132.1 ms | 1.95 | 66.6 MB |
| 2.5 GHz damped | 56 | 66.3 ms | 139.8 ms | 2.11 | 60.2 MB |

Anchor preparation was another 67.5/62.2 ms. Both arms assume the anchor
already exists; direct target timing does not recompute it. Incremental timing
includes its two multiplier setups and combination of all six functions.
The incremental recurrence takes two coefficient products per degree.

The zero step returned exactly zero. Across ordinary and tiny steps,
anchor-plus-increment agreed with direct target functions to 8.37e-14
relative at real frequency and 6.44e-13 at damped frequency.

For the 1e-8 step, an independent complex FFT recurrence in extended precision
(63 mantissa bits) recomputed both endpoints, then subtracted. The measured
relative discrepancies against that reference were:

| Frequency | Double endpoint subtraction | Incremental difference | Discrepancy reduction |
|---|---:|---:|---:|
| Real | 8.07e-5 | 4.43e-8 | 1,822× |
| Damped | 2.65e-4 | 1.53e-7 | 1,732× |

These are discrepancies against a finite-precision reference, not verified
error bounds. The reference itself subtracts nearby extended-precision
outputs, so its remaining cancellation limits the precision conclusion.

The result supports item 4 for tasks that need a tiny difference itself.
It does not support replacing direct radial recomputation to save time.
We did not implement incremental log(q), complete matrix, source/receiver
updates or Jacobians; those remain open and would add costs.

## Reproduction and scope

Run from the repository root with the EMNerf Python environment:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 taskset -c 0-3 python -m experiments.haibing_kernels.study
```

The driver refuses an existing manifest. It preserves source/code hashes,
machine load, affinity, all repeated timings and numerical receipts under
`results/validation/cleaned_interfaces/HB-001-kernels/`. Peak RSS was 331 MB;
final load averages were 0.689/0.423/0.188. These are CPU component timings,
not production GPU or full-fit timings. The maintained solver is unchanged.
