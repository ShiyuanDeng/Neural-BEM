# SPD-010: parallel frequency solves

**Status: PASS.** Three archived SC-043 inverse runs were replayed with 8 frequency threads. Every recorded field matches the archive bit for bit: decisions, accepted states, trials, damping, ledger snapshots, acceptance checks, audits, endpoints and scores. The complete runs were 4.96–5.59× faster.

The [approved plan](../../../../docs/iterations/speedup/iteration_09/03_plan.md) governs scope. The user replied "go" to the request to approve SPD-010 / SPD-011.

## Result

| SC-043 fixed run | Archived serial (s) | 8 frequency threads (s) | Speed-up | Work units | Endpoint RMS (mm) |
|---|---:|---:|---:|---:|---:|
| Circle | 254.7 | 51.4 | **4.96×** | 114 = 114 | 0.000244674 = |
| Peanut | 652.0 | 123.8 | **5.27×** | 418 = 418 | 0.00242780 = |
| Kite | 2157.1 | 386.1 | **5.59×** | 798 = 798 | 0.0346059 = |

The comparison covers every non-timing field of `decisions`, `accepted`, `block_1-3`, `checkpoint`, `audit`, `result` and `progress`: 56,964 leaves across the three cases, all equal. Timing keys (`seconds`) are the only exclusion. [replay/comparison.json](replay/comparison.json) holds the per-file counts; [replay/replay.json](replay/replay.json) records the environment and host load.

**Timing conditions.** The two arms ran under different concurrency, so the wall times are shared-host observations, not an isolated benchmark.

- The archive ran as part of SC-043's 18 jobs on 6 concurrent single-threaded workers.
- The replay ran 3 workers × 8 threads on the same 24-core host, from clean commit `508822bb` with one BLAS thread. The load average ranged from about 1 to 12.
- A read-only micro-benchmark measured the mechanism in isolation: 19 solves at N = 512 took 14.4 s serially and 1.95 s with 16 threads (7.4×).

## What changed

- `experiments/shape_continuation/forward.py`: `ordered_calls` runs `function(item)` for all frequencies in a thread pool, then hands the results back strictly in order. `SC_FREQUENCY_THREADS` sets the pool size (default 8); 1 restores the serial loop exactly.
- `experiments/shape_continuation/lm_backend.py`: `Objective._predict` and `Objective.jacobian` consume those calls. The ledger `reserve`/`charge`/`fail` sequence is unchanged. After a failed frequency, later results are discarded, as the serial loop never computed them. Refined states return only their prediction, which releases their matrices early.
- `solvers/ordered_boundary/validation_cache.py`: `ValidationCache` takes an `RLock`. Worker threads run in a copy of the caller's context, so they share an active fit-local cache. Each key is still computed once, and the cache counts equal the serial counts, which is tested.
- Numerics are unchanged: CPU reference kernels, one BLAS thread.

A wall-clock guard (`TrialWallLimit`) fires less often simply because runs are faster. That is the only possible behavioural difference, and no limit was reached here.

## Tests

`experiments/shape_continuation/test_frequency_threads.py` checks, at 1, 3 and 8 threads, that the following are bit-identical:

- predictions, Jacobians, refined predictions and ledger snapshots;
- an injected failure at the third frequency (3 charges, 1 failure);
- a complete `fit_stage` trajectory;
- validation-cache counts.

The suites `experiments/shape_continuation`, `pytest/gpr_bem_kress`, `pytest/shape_continuation`, `pytest/sdf_inverse/test_spd008.py` and `pytest/ordered_boundary` pass: 328 tests.

## Reproduce

From the repository root:

```bash
SC_FREQUENCY_THREADS=8 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/speedup/SPD-010-20260927-frequency-threads/replay.py run OUT \
  --cases wrong_circle peanut kite --workers 3
```

`replay.py` loads the SC-043 worker unchanged and replaces only its source-hash check. It still verifies every frozen input hash and records the source drift. [preliminary/](preliminary) keeps an earlier replay that used interim code without cache sharing. It was also bit-identical: 4.83×, 4.91× and 5.12×.

## Limits

- Only three of the six cases, and only the fixed policy, were replayed.
- Multi-object runs (SC-047/048) use the same `Objective` loop, so they get the threads, but no multi-object replay was run here.
- Thread counts multiply with outer process workers; keep workers × threads ≤ 24.
