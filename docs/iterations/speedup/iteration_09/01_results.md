# Iteration 09 results: SPD-010 and SPD-011

2026-09-27. Both experiments are **COMPLETE / PASS** under the [plan](03_plan.md). The user replied "go" to the request to approve SPD-010 / SPD-011. There is no independent reviewer. Both are opt-in or parameterized: the CPU reference kernels remain the default, and `SC_FREQUENCY_THREADS=1` restores the serial loop.

## Answer to the user's question

The shape-continuation inverse and the video preparation were slow for four reasons:

1. Every frequency rebuilt a dense Kress/Müller matrix with 12 complex SciPy Bessel/Hankel calls per node pair. That is 72–75% of recorded time.
2. The twice-resolution acceptance and display checks cost about 80% of the wall time.
3. The 19 frequencies ran serially on one core of 24.
4. The earlier SPD accelerations never reached this pipeline.

A GPU helps once the Bessel functions are handled properly: PyTorch's built-in versions are only accurate to about 1e-6.

| Measured, shared host | Before | SPD-010: CPU threads | SPD-011: CUDA |
|---|---:|---:|---:|
| SC-043 kite inverse | 2157 s | 386 s (5.6×) | 159 s (13.6×) |
| SC-043 six-case sum | 6485 s | three of the six cases: 4.96–5.59× | 639 s (10.2×) |
| latest_vs_hybrid preparation, six cases (worker time) | 4732 s | renderer unchanged | 768 s (6.2×) |
| 19 solves + Jacobians at N = 1024, 8 threads | about 66 s serial (solves only) | 9.1 s | 2.3 s |

## SPD-010: parallel frequency solves

Circle, peanut and kite SC-043 fixed runs were replayed with 8 threads. All 56,964 non-timing recorded values are bit-identical to the archive. The runs were 4.96×, 5.27× and 5.59× faster. See the [results](../../../../results/validation/speedup/SPD-010-20260927-frequency-threads/README.md).

## SPD-011: CUDA single-interface assembly

- **Matrices:** 456 systems agree within 2.0e-16 of max|A|. Predictions agree within 1.0e-13 and Jacobians within 3.5e-14.
- **Inverse runs:** all six SC-043 fixed runs match the archive's outcomes, blocks, units and accepted steps. Endpoint RMS agrees within 2.2e-9, and every audit passes.
- **Video:** zero frontier changes.

See the [results](../../../../results/validation/speedup/SPD-011-20260927-cuda-assembly/README.md).

**Two failed attempts are retained.** Both hit CUDA out-of-memory in the endpoint audits of six concurrent workers. The fix keeps retained states entirely in host memory and serializes device assembly per process; peak device memory is now 14.6 GB.

## Deviations from the plan

- **No batched LU across frequencies.** A per-solve device LU inside SPD-010's thread pool already makes the physics sub-second to about 2 s per 19 frequencies. The remaining cost is on the CPU side: boundary validation, builders and transfers.
- **Committed renderer left unchanged.** The latest_vs_hybrid `render.py` was not modified, because its source hash keys its display caches. It reaches the GPU through the environment variable instead, and does not use frequency threads.
- **Wider code changes.** `ValidationCache` became thread-safe. CUDA solves outside a fit open a solve-local exact validation cache.
- **Stated criteria.** The matrix gate compares against max|A|, which is how "maximum relative entry error" is read here. The video gate thresholds displayed log10 heat rather than raw misfit, because converged misfits near 1e-7 amplify round-off. This criterion was set before the run.

## Next decisions, not scheduled

- Promote `SC_FREQUENCY_THREADS=8` and/or CUDA to defaults for new SC runs.
- Port the multicomponent (two-object) assembly to CUDA.
- Accelerate the O(N²) sampled self-intersection validation, now the largest remaining per-solve cost on the GPU path.
