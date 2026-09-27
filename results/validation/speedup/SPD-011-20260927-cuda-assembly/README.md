# SPD-011: opt-in CUDA Kress backend

**Status: PASS on all four gates.** With `SC_FORWARD_BACKEND=cuda`, the six archived SC-043 inverse runs reproduce every outcome, block stop, work unit and accepted step. Endpoint RMS agrees within 2.2e-9 relative, and every endpoint audit passes. The runs took 6.8–13.6× less wall time than the archived serial CPU runs: 6485 s → 639 s summed. Video preparation is 5.1–7.0× faster per case, with zero frontier changes. Values are not bit-identical; accepted curves agree within 5.0e-13 of max|c|. Two earlier trajectory attempts ran out of device memory. They are retained, and the fix is described below.

The [approved plan](../../../../docs/iterations/speedup/iteration_09/03_plan.md) governs scope. The user replied "go" to the request to approve SPD-010 / SPD-011. The backend is opt-in: CPU stays the default.

## Gate 1–2: matrices, predictions and Jacobians

Each of the six cases has two geometries, the SC-043 start (pre-fit) and the endpoint. Each is solved at every one of the 19 catalog frequencies, at N = 512 and 1024: 456 systems on each backend ([matrix_gate.json](matrix_gate.json)).

| Quantity | Worst over 456 systems | Limit |
|---|---:|---:|
| max \|A_gpu − A_cpu\| / max \|A_cpu\| | 2.0e-16 | 1e-14 |
| Receiver prediction, relative 2-norm | 1.0e-13 | 1e-12 |
| Reciprocal shape Jacobian (48 ripple modes), relative | 3.5e-14 | 1e-12 |
| GPU linear residual | 3.0e-14 | 1e-10 guard |

The Bessel kernel is a port of the Cephes j0/y0/j1/y1 that SciPy uses. It matches SciPy to 1e-14 of |H_n| on 1e-6 ≤ x ≤ 60 (unit test). PyTorch's own `torch.special.bessel_*` is off by about 1e-6 near x = 5, which is why the port exists.

Median time for 19 solves plus 19 Jacobians, with 8 threads and a shared fit cache, on the final code:

| N | CPU, 8 threads | CUDA | Serial CPU (earlier benchmark) |
|---:|---:|---:|---:|
| 512 | 2.19 s | 0.77 s | ≈ 14.4 s (solves only) |
| 1024 | 9.06 s | 2.28 s | ≈ 66 s (solves only) |

## Gate 3: complete inverse runs

`SC_FORWARD_BACKEND=cuda`, 6 workers × 4 frequency threads, clean commit `9a645771` ([trajectory_gate.json](trajectory_gate.json), [drift.json](drift.json)).

| SC-043 fixed run | Archived CPU (s) | CUDA (s) | Speed-up | Units | Accepted steps | Endpoint RMS relative difference | Audit |
|---|---:|---:|---:|---:|---:|---:|---|
| Circle | 254.7 | 37.3 | 6.8× | 114 = | 3 = | 0 | pass |
| Star | 1156.2 | 122.8 | 9.4× | 741 = | 12 = | 1.4e-10 | pass |
| C | 1230.6 | 125.0 | 9.8× | 779 = | 13 = | 1.6e-9 | pass |
| Kite | 2157.1 | 158.8 | 13.6× | 798 = | 9 = | 3.5e-12 | pass |
| Peanut | 652.0 | 81.7 | 8.0× | 418 = | 7 = | 2.2e-9 | pass |
| Hook | 1034.7 | 113.2 | 9.1× | 646 = | 12 = | 1.2e-9 | pass |

- **Identical:** per-block outcomes, stop reasons, M, units and the accepted (block, iteration) sequence.
- **Round-off differences:**
  - Accepted curves differ by at most 5.0e-13 relative to max|c|.
  - Accepted losses differ by at most 5.3e-8 relative, at losses near 1e-15.
  - The largest leaf-wise relative differences sit in quantities that are themselves round-off: disagreement allowances around 1e-20, 2N prediction discrepancies around 1e-14, and near-zero coefficient entries.
- **Timing conditions:** shared-host observations.
  - The archive ran 6 concurrent single-threaded workers.
  - The CUDA runs used 6 workers sharing one GPU, with load average 6–9 and peak device memory 14.6 GB ([gpu_memory.log](gpu_memory.log)).
  - SPD-010's CPU threads alone gave 4.96–5.59× on three of these cases.

### Failed attempts, retained

| Attempt | Fits | Endpoint audits | Cause |
|---|---|---|---|
| [1](attempt_01_oom) | All outcomes, blocks, units and accepted steps matched | 6/6 CUDA out-of-memory | Each of six processes kept every retained state's device matrix and LU, and assembled on four threads at once |
| [2](attempt_02_oom) | Same | 3/6 out-of-memory; the 32 GB card filled | Matrices had moved to host, but each audit still retained four sets of 19 refined LU factors on the device |
| 3 (above) | Same | 6/6 pass; peak 14.6 GB | After its first solve, a state's LU factors move to host memory; later reciprocal solves upload them for one call. Device assembly is serialized per process |

Memory safety costs time. Attempt 1 runs, including their failed audits, took 19–122 s, against 37–159 s for attempt 3.

## Gate 4: video preparation

**PASS.** The committed `latest_vs_hybrid/render.py` was run unchanged with `SC_FORWARD_BACKEND=cuda --prepare-only --workers 6`, into a fresh folder so no display cache was reused. Its own assertions pass on every state: saved loss, endpoint RMS and 2N refinement. [video_gate.py](video_gate.py) then compared every displayed field, state by state, with the committed CPU records ([video_gate.json](video_gate.json)).

| Case | States (original + latest) | Frontier changes | Max displayed log10-heat difference | CPU prep (s) | CUDA prep (s) | Speed-up |
|---|---|---:|---:|---:|---:|---:|
| Circle | 11 + 17 | 0 | 0 | 81.6 | 16.0 | 5.1× |
| Star | 19 + 42 | 0 | 1.6e-8 | 1097.7 | 156.2 | 7.0× |
| C | 81 + 44 | 0 | 1.3e-9 | 931.1 | 149.0 | 6.2× |
| Kite | 57 + 92 | 0 | 4.6e-10 | 1402.9 | 244.1 | 5.7×\* |
| Peanut | 64 + 37 | 0 | 8.8e-10 | 410.9 | 77.0 | 5.3× |
| Hook | 24 + 43 | 0 | 3.4e-9 | 807.7 | 125.7 | 6.4× |

- The gate required no frontier or integer changes, displayed log10 heat within 1e-6, and identical curve RMS. All three hold.
- Misfits agree within 2.7e-9 relative. Heat values agree within 1.6e-7 relative before log clipping.
- Worker time totals 4732 s → 768 s. All six cases took 245 s of wall time with 6 workers, at peak device memory 10.0 GB.
- The committed CPU preparation ran 4 workers and took longer than kite's 1403 s.

\*The CPU kite record reused 3 prefilled display states (304 forward batches). The CUDA run computed all of them (380), so it did more work in less time.

The renderer still solves its 19 frequencies one at a time, because it was left unchanged on purpose: its source hash keys the display caches. A renderer that used `forward.ordered_calls` would also get SPD-010's threading.

## What changed

- `solvers/gpr_bem_kress/cuda_assembly.py` builds `build_muller_system` term for term on the device:
  - the pair invariants;
  - the 24-term power-log near series;
  - the direct Hankel/Bessel differences, via the Cephes port plus order-two recurrence or series;
  - the Kress logarithmic weights and the closed diagonal limits.

  `DeviceFactors` does LU and solves with the same 1e-10 residual guard. It supports only single `PeriodicCurve2D` boundaries with distinct real positive wavenumbers. Anything else, including all multi-object boundaries, stays on the CPU. It skips the CPU builder's overlap *diagnostic*; the matrix is the same.
- `experiments/shape_continuation/forward.py` adds `SC_FORWARD_BACKEND=cpu|cuda`, default `cpu`. States keep host matrices, as on the CPU path. Outside a fit cache, a CUDA solve opens a solve-local exact validation cache, so its three builders validate the boundary once.
- `pytest/gpr_bem_kress/test_cuda_assembly.py`: Bessel accuracy, matrix equality including the near-series branch, declined inputs, the residual guard and device-memory release. `test_frequency_threads.py` compares the CUDA objective with the CPU one.

## Reproduce

```bash
SC_FORWARD_BACKEND=cuda SC_FREQUENCY_THREADS=4 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/speedup/SPD-010-20260927-frequency-threads/replay.py run OUT \
  --cases wrong_circle circle_to_star circle_to_c kite peanut hook --workers 6
python results/validation/speedup/SPD-011-20260927-cuda-assembly/trajectory_gate.py OUT OUT/gate.json
python results/validation/speedup/SPD-011-20260927-cuda-assembly/matrix_gate.py matrix_gate.json
```

## Limits and next steps

- The remaining per-solve cost is mostly CPU work: the O(N²) boundary self-intersection validation (33 ms at N = 512, 132 ms at N = 1024 when uncached), the receiver and incident-field builders, and host–device transfers.
- Multi-object (SC-047/048) assembly still runs on the CPU. Porting `multicomponent.py` would be a separate proposal.
- Promoting CUDA to the default is a separate decision. The fixed policy on six single-object noiseless scenes does not cover every configuration.
