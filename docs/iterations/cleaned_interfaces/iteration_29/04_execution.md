# GC-001 execution record

2026-10-05. Approved by the user's "run" in response to the registered GC-001.
Existing `feature/shape-frequency-continuation`; no branch/worktree creation.

## Pre-dispatch checks

Production code is unchanged. `experiments/benchmark/gc001.py` calls maintained
geometry implementations and contains no solver construction or fitting call.
The experiment-local B adapter changes only preparation; bounded checks verify
its CUDA coefficients/derivatives and its unchanged sampled spectral trial.

The five replay checks and five package-boundary checks pass: **10 passed in
1.96 s**. See
[qualification log](../../../../results/validation/cleaned_interfaces/GC-001-qualification/pytest-final.log).
An initial command used the nonexistent `test_package.py` filename and ran no
tests; its command-error log is retained alongside the corrected run. An earlier
five-test driver check also passed in 0.61 s before cache-scope clarification.

GPU check: RTX 5090, 0% utilization, no compute processes; desktop allocation
763 MiB. Single BLAS/OpenMP and Torch CPU threads, one process.

Commit the registration, driver and qualification evidence before dispatch.
The run records the exact committed source/hash set and frozen replay-state
hashes in its manifest. A fresh output path is required; exceptions and partial
receipts are preserved. Results will open iteration 30.

## Execution

Command:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -u -m experiments.benchmark.gc001
```

The six measured phases are precision/decision coverage, repeated timing,
preparation ablations, derivative step-size references, interpolation attribution
and component profiling. All use saved TG-002/PC-002 geometry; no physics solves.

The main replay completed in 838.73 s with 31 states/279 moves; the receipt
validator passed frozen inputs, committed numerical source hashes, full phase
coverage, device fallback counts and profile/error-vector accounting. Its
[results](../iteration_30/01_results.md) preserve the main measurements.
The unchanged interpolation errors prompted a bounded attribution continuation
on the same six preselected moves, registered separately before dispatch in
[05_attribution_continuation.md](05_attribution_continuation.md). Its two focused
tests pass in 0.12 s; the main run and source provenance remain intact.

The continuation completed its six cases in 21.19 s. It identifies final
uniform-arclength output sampling/FFT aliasing as the dominant large-disagreement
effect. Its committed source and selection hashes, zero-physics receipt and
native-path reproduction are checked by the final bundle validator. Total
measurement time is 859.92 s (14.33 min). Results and all raw/command-error
evidence are retained; production numerical code is unchanged.
