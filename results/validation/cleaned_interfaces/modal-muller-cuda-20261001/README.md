# Modal Müller on CUDA: accuracy, stage replays and matched timing

2026-10-01. This bundle is evidence for CUDA execution of the maintained
`modal_muller` service
([`modal_cuda.py`](../../../../experiments/cleaned_interface/modal_cuda.py)).
The user approved the speed-up plan with "cp, then go." after the CPU service
was committed at `88f5ee1b`.

**Result: modal Müller on CUDA is faster than maintained CUDA Kress on a full
catalog. It matches the CPU service's accuracy against 2048-node Kress and
reproduces all three archived stage decisions. On the 19-frequency K=192
catalog, a new geometry costs 0.26 s at production level (CUDA Kress: 0.44 s)
and 0.34 s at refined level (CUDA Kress N=1024: 1.73 s). CUDA Kress remains
faster for a single cold frequency.**

## What moved to the device

The following run in torch float64/complex128, mirroring the CPU modules:

- the polynomial products;
- the certified log|W|² recurrence and its residual certificate;
- the stored T_n(R) arrays;
- the per-frequency combination;
- the seven window products;
- the exact-log Galerkin contraction.

The following stay on the CPU:

- scalar Bessel/Hankel values (SciPy; no `torch.special`);
- Graf sources and receivers, regular-wave arrays;
- LU, fields and the Jacobian.

Handles hold only host arrays, and device work shares the process-wide
`_device_work` lock. `device=cpu` is unchanged: on four fixture evaluations
its predictions and Jacobians are bitwise identical to commit `88f5ee1b`.
`auto` falls back to the CPU after device out-of-memory and records the
reason; `cuda` fails instead. Graf regular waves are now built once per
wavenumber and shared by sources and receivers, also bitwise identical on
the CPU.

## Accuracy

The table gives relative errors against the review's independent 2048-node
CPU Kress, for the CPU and CUDA services at the same tokens, plus their
difference ([accuracy_fields.json](accuracy_fields.json)).

| Fixture | GHz | K_trace | CPU field | CUDA field | CUDA−CPU field | CUDA−CPU Jacobian |
|---|---:|---:|---:|---:|---:|---:|
| C, K=24, M=24 | 1 | 64 / 96 | 7.2e-14 / 1.8e-13 | 1.0e-13 / 1.9e-13 | 8.3e-14 / 3.5e-13 | 1.4e-13 / 4.6e-13 |
| C, K=24, M=24 | 2.5 | 64 / 96 | 1.37e-8 / 9.9e-13 | 1.37e-8 / 1.8e-12 | 6.0e-13 / 2.7e-12 | 1.4e-12 / 7.6e-12 |
| DF endpoint, K=192, M=67 | 1.25 | 96 / 128 | 2.1e-13 / 1.9e-13 | 2.0e-13 / 1.3e-13 | 1.2e-13 / 1.1e-13 | 2.1e-13 / 3.0e-13 |
| DF endpoint, K=192, M=67 | 2.5 | 96 / 128 | 1.58e-10 / 1.8e-12 | 1.58e-10 / 1.2e-12 | 4.2e-13 / 7.4e-13 | 1.4e-12 / 2.5e-12 |
| C damped 0.25 | 0.5–1.25 | 64 / 96 | ≤ 5.3e-13 | ≤ 4.4e-13 | ≤ 6.2e-13 | – |
| C damped 0.25 | 2.5 | 64 / 96 | 4.6e-9 / 6.1e-9 | 2.4e-9 / 5.1e-9 | 3.7e-9 / 3.6e-9 | – |

**Predeclared gate:**

- **Jacobians: passed.** CUDA−CPU Jacobian differences are ≤ 1e-10.
- **Fields: failed.** The ≤ 1e-12 field gate is missed twice: C at 2.5 GHz
  with K_trace 96 (2.7e-12), and damped 2.5 GHz (3.7e-9).

In both cases each device's own error against Kress is the same size as the
difference. CUDA's error is within 2.0× of the CPU's on every row. The damped
2.5 GHz case is the known cancellation floor and lies outside the policy,
which damps only up to 1.25 GHz. So the gate was set below the method's own
floor. Agreement with the independent reference is unchanged.

Complete-trial centered differences on CUDA at 2.5 GHz with K_trace 128 give:

| Curve | Step 1e-6 m | Step 5e-7 m |
|---|---:|---:|
| C | 1.81e-6 | 4.52e-7 |
| DF endpoint | 4.68e-6 | 1.17e-6 |

These match the CPU service to three digits.

## Archived stage replays on CUDA

| Stage | Trials equal | Accepted | Solves / derivative batches | Loss rel. change | Endpoint max diff | Wall (diagnostic) |
|---|---:|---:|---:|---:|---:|---:|
| D `stage_2_damped` | 25/25 | 10 | 104 / 22 | 2.4e-14 | 1.2e-12 units | 4.1 s |
| D `release_M11` | 7/7 | 7 | 304 / 152 | 3.4e-12 | 1.2e-12 units | 8.4 s |
| DF `fixed_M43` | 1/1 | 1 | 76 / 38 | 1.7e-8 | 2.2e-13 units | 5.1 s |

In every stage, every trial's iteration, damping, backtrack and status
matches, as do the accepted indices, the exit and the stage-only work. All
evaluations ran on `cuda-modal` with no fallback. The CPU service took 18,
59 and 19 s for these stages. The runs overlapped with the accuracy jobs, so
their wall times are not matched timings.

## Matched timing

Hardware: Core Ultra 9 285K and RTX 5090, one BLAS thread. The protocol:

- three sequential repetitions with order rotated and reversed; medians
  reported;
- a cold modal geometry in every repetition;
- CUDA context, Kress ray table and cuFFT plans warmed once before timing
  (1.0 s, excluded);
- CUDA Kress uses SPD-016 and four frequency threads.

**19-frequency DF endpoint catalog** (K=192, M=67, 0.25–2.5 GHz; reference
1024-node CPU Kress):

| Method | Level | New geometry forward (s) | Same geometry forward (s) | Jacobian (s) | Forward + Jacobian (s) | vs CUDA Kress |
|---|---|---:|---:|---:|---:|---:|
| Kress CUDA, N=512 | production | 0.435 | 0.452 | 0.222 | 0.647 | 1.00 |
| Modal CPU, 4 threads | production | 2.060 | 0.758 | 0.021 | 2.079 | 4.74 |
| Modal CUDA, 1 thread | production | 0.468 | 0.273 | 0.039 | 0.507 | 1.08 |
| **Modal CUDA, 4 threads** | production | **0.261** | 0.120 | 0.020 | **0.284** | **0.60** |
| Kress CUDA, N=1024 | refined | 1.725 | 1.722 | 0.517 | 2.243 | 1.00 |
| Modal CPU, 4 threads | refined | 3.276 | 1.560 | 0.024 | 3.299 | 1.90 |
| Modal CUDA, 1 thread | refined | 0.650 | 0.395 | 0.048 | 0.699 | 0.38 |
| **Modal CUDA, 4 threads** | refined | **0.342** | 0.146 | 0.024 | **0.365** | **0.20** |

**Single frequency** (new-geometry forward, s):

| Fixture | Kress CUDA 512 / 1024 | Modal CUDA, 4 threads, production / refined | Modal CPU, 4 threads, production |
|---|---:|---:|---:|
| C, 2.5 GHz | 0.030 / 0.104 | 0.046 / 0.055 | 0.283 |
| C, damped 1 GHz | 0.036 / 0.126 | 0.040 / 0.049 | 0.255 |
| DF endpoint, 2.5 GHz | 0.030 / 0.105 | 0.089 / 0.133 | 1.377 |

For a single cold frequency the once-per-curve geometry preparation (about
0.05 s at K=192) dominates, so CUDA Kress stays faster at production. From a
few frequencies per geometry upward, and at the refined level, modal CUDA is
faster. Its same-geometry frequency (about 6 ms) and its Jacobian (10–30×
cheaper) are the reasons. The four-thread gain over one thread comes from
overlapping the CPU parts (Graf waves, LU) with the device work.

These are forward/Jacobian workloads, not inverse-campaign runtime.

## Reproduce

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
D=results/validation/cleaned_interfaces/modal-muller-cuda-20261001
"$PY" -m pytest -q experiments/cleaned_interface/test_modal_muller.py
"$PY" $D/accuracy.py fields && "$PY" $D/accuracy.py directional
for s in stage_2_damped release_M11 fixed_M43; do "$PY" $D/replay.py $s 4 cuda; done
"$PY" $D/benchmark.py single && "$PY" $D/benchmark.py catalog   # alone on the machine
"$PY" $D/summarize.py
```

`summarize.py` asserts the replay criteria, the all-CUDA receipts and the
source hashes. It evaluates both predeclared gates and recomputes the ratios
in `summary.json`.

## Scope

- Not established: no inverse case or campaign has run on CUDA modal.
- Not implemented: frequency batching across `evaluate` calls, device LU, and
  a device-side Graf step.
- The next measurement is one full original-start case, to find the inverse
  bottleneck. The nodal records name CPU geometry validation (SC trials) as a
  likely candidate.
