# SPD-010 and SPD-011: frequency threads and an opt-in CUDA Kress backend

2026-09-27. **Approval status: APPROVED.** I asked the user to reply "approve SPD-010", "approve SPD-011", or both; I had recommended both, in order. The user replied, verbatim: "go". **Execution status: COMPLETE / PASS.** See the [results](01_results.md), including two retained CUDA out-of-memory attempts.

Owner: Claude Code. There is no independent reviewer. Work stays on the existing checkout and branch `feature/shape-frequency-continuation`; no new branch or worktree.

## Why

The user asked why the shape-continuation inverse and the video preparation are slow, and whether a GPU would help. Existing records answer this without new numerical work:

- Assembly takes 72–75% of the forward time: the SC-047/048 work records, and the latest_vs_hybrid peanut preparation (299 of 411 s).
- SC-043 fixed-release runs take 255–2157 s per case.

Four causes compound:

1. **Dense Kress assembly** makes 12 complex SciPy Bessel/Hankel calls per node pair, plus array plumbing. At N = 512 that is 0.82 s per frequency; at N = 1024 it is 3.15 s.
2. **Twice-resolution checks cost the most.** The LM acceptance validation and the video refinement check re-solve at 2N, which costs 4× the assembly and 7× the LU.
3. **Everything runs serially.** The 19 frequencies are solved one after another, with one BLAS thread, on a 24-core host.
4. **The earlier SPD accelerations never reached this pipeline.** `experiments/shape_continuation/forward.py` pins the CPU reference kernels.

Read-only benchmarks on 2026-09-27 found the following:

- Threading the 19 solves is 7.4× faster at 16 threads, with bit-identical predictions.
- On the RTX 5090, the Bessel kernels and batched LU are fast.
- `torch.special.bessel_*` has about 1e-6 error near x = 5, so a GPU path needs its own Bessel kernel.

## SPD-010: parallel frequency solves (CPU, exact)

`forward.ordered_calls` runs the independent frequency solves and Jacobians in a thread pool (`SC_FREQUENCY_THREADS`, default 8; 1 restores the loop). `lm_backend.Objective` consumes the results strictly in order, so the ledger reserve/charge/fail sequence is unchanged. Workers copy the caller's context, and `ValidationCache` becomes thread-safe, so a fit-local exact cache is shared with the same counts. The reference kernels are unchanged.

Gates:

1. Unit tests at 1, 3 and 8 threads. Predictions, Jacobians, ledger records, an injected failure and a full `fit_stage` trajectory must all be bit-identical. Validation-cache counts must equal the serial counts.
2. Replay the archived SC-043 fixed runs for circle, peanut and kite on the current code. Every recorded field except timings must match the archive bit for bit.
3. The existing suites pass.

## SPD-011: opt-in CUDA single-interface assembly (`SC_FORWARD_BACKEND=cuda`)

`solvers/gpr_bem_kress/cuda_assembly.py` mirrors `build_muller_system` term for term on the GPU in float64/complex128. It uses a jiterator port of SciPy's Cephes j0/y0/j1/y1, the recurrence or series for order two, and device LU with the same 1e-10 residual guard. Multi-component boundaries, complex wavenumbers and equal wavenumbers stay on the CPU. The default remains `cpu`.

Gates:

1. **Matrix:** max |ΔA| / max |A| ≤ 1e-14 against the CPU reference for all 6 cases × 19 frequencies × N ∈ {512, 1024}. Predictions must agree to ≤ 1e-12, and the residual guard must pass. The Bessel kernel is checked against SciPy up to x = 60.
2. **Jacobian:** the reciprocal shape Jacobian agrees to ≤ 1e-12.
3. **Trajectory:** SC-043 fixed runs on all six cases with CUDA. They must have the same stop reasons and unit counts, and endpoint RMS within 1e-6 relative of the archive. Any divergence is reported, not tuned away.
4. **Video:** latest_vs_hybrid preparation on the GPU, written to a separate folder. The renderer's own assertions must pass, and the heat/front fields must match the committed CPU preparation.
5. **Timing:** a before/after table with the host load declared.

Default promotion and a GPU port of the multicomponent assembly are separate decisions.
