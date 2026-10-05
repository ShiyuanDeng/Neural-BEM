# AC-002: current forward-time decomposition

2026-10-05. Authorized by the user's request for percentages spent constructing
Chebyshev arrays, assembling matrices, and the rest of the forward solve.
Current branch: feature/shape-frequency-continuation. No inverse campaign.

Profile TG-002 C-shape truth, contrast 13.3, real 2.5 GHz, K_trace=96,
window=160, one frequency thread and one BLAS thread. Run CPU and CUDA
sequentially, three fresh-geometry/reused-geometry pairs per device after one
untimed warm-up. GPU/runtime initialization is excluded; fresh geometry setup
is included. Reuse means repeating the identical curve and frequency on the
same backend instance.

Use nested exclusive wall timers around the existing stages and function
calls. Separate log Chebyshev construction/certification, radial Chebyshev
array initialization/extension, scalar analytic coefficients, radial array
contraction, remaining matrix assembly, other geometry setup, Graf waves,
LU, fields, and unattributed wrapper/bookkeeping overhead. Synchronize CUDA
at timed boundaries. This instrumented, serial breakdown is not concurrent
catalog throughput or inverse wall-time attribution.

Verify each instrumented field against its uninstrumented device reference
at rtol=1e-11, atol=1e-15, ensure exclusive durations are nonnegative (within
timer roundoff), and require categories to sum to total forward time.
Report means of three repetitions and shares of their total elapsed time;
retain individual observations, source hashes, platform/GPU details and the
historical stage-share source. Do not mix historical percentages with current
scalar timings. Preserve unrelated workspace edits, commit and push the new
driver, plan, measurements and report after validation.
