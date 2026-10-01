# Maintained modal Müller service: accuracy, stage replays and timing

2026-09-30/10-01. This bundle is evidence for the clean `modal_muller` backend in
[`experiments/cleaned_interface`](../../../../experiments/cleaned_interface/README.md#modal-müller-service).
The backend rewrites the independently reviewed Chebyshev prototype behind the
same service contract as `NodalKress`.

**Result: the maintained service reproduces the prototype's accuracy on every
review fixture and all three archived stage decisions. It is 3–4× faster on
one new single-frequency geometry and 11× faster on the 19-frequency catalog on
one core (21× with four frequency threads). It is still about 5× slower than
CUDA Kress on the 19-frequency catalog, and no 36-case inverse campaign has
been run.**

Changes relative to the prototype:

- The fixed `beta=0.05` is replaced by a certified |W|² lower bound, and the
  degrees and orders are chosen by rule.
- The per-frequency Python loops over coefficient dictionaries are replaced by
  frequency-independent regular-wave arrays.
- Real functions use half-spectrum FFTs.
- K' is obtained as the transpose of K.
- Production and refined resolutions raise both the trace cutoff and the
  window.

No production nodal, optimizer, policy, or CI-001-frozen source was edited.

## Accuracy against 2048-node Kress

Relative field error, relative Jacobian error, and the worst Jacobian column.
The references are the review's independent CPU Kress states. The 1024/2048
oracle differences are at most 2.1e-14. The `prototype` columns are the
review's recorded values at its fixed window B.

| Fixture | GHz | K_trace / window | Field | Jacobian | Worst column | Prototype field / Jacobian (B) |
|---|---:|---|---:|---:|---:|---|
| C, K=24, M=24 | 1 | 64 / 128 | 7.2e-14 | 9.5e-14 | 2.9e-13 | 1.8e-13 / 2.4e-13 (128) |
| C, K=24, M=24 | 2.5 | 64 / 128 | 1.37e-8 | 9.11e-8 | 8.13e-7 | 1.37e-8 / 9.11e-8 (128) |
| C, K=24, M=24 | 2.5 | 96 / 160 | 9.9e-13 | 2.5e-12 | 4.1e-12 | 1.6e-12 / 4.5e-12 (128) |
| DF endpoint, K=192, M=67 | 1.25 | 96 / 160 | 2.1e-13 | 6.6e-11 | 4.6e-6 | 2.8e-13 / 6.6e-11 (160) |
| DF endpoint, K=192, M=67 | 1.25 | 128 / 192 | 1.9e-13 | 5.2e-13 | 2.1e-10 | 2.6e-13 / 6.6e-13 (160) |
| DF endpoint, K=192, M=67 | 2.5 | 96 / 160 | 1.58e-10 | 8.72e-8 | 1.34e-5 | 1.57e-10 / 8.72e-8 (160) |
| DF endpoint, K=192, M=67 | 2.5 | 128 / 192 | 1.8e-12 | 5.4e-12 | 3.6e-11 | 1.8e-12 / 5.2e-12 (160) |
| C, damped 0.25 | 0.5 | 64 / 128 | 3.9e-15 | – | – | 8.6e-15 (128) |
| C, damped 0.25 | 1 | 96 / 160 | 3.6e-14 | – | – | 4.5e-14 (128) |
| C, damped 0.25 | 2.5 | 64 / 128 | 4.6e-9 | – | – | 7.2e-9 (128) |
| C, damped 0.25 | 2.5 | 96 / 160 | 6.1e-9 | – | – | 7.2e-9 (128) |

The damped 2.5 GHz floor also appears in the prototype. It does not improve
with K_trace. The policy damps only frequencies up to 1.25 GHz.

We also compared centered differences of the **complete nonlinear SC trial**
with Jacobian·direction (seeded direction, 2.5 GHz, contrast 13.3,
K_trace 128). The C gives 1.81e-6 and 4.52e-7 at steps 1e-6 and 5e-7 m. The
DF endpoint gives 4.68e-6 and 1.17e-6. Halving the step divides the error by
four, the expected centered-difference truncation behaviour, and matches the
prototype to three digits.

## Archived stage replays

The unchanged LM loop runs through `fit_stage(..., physics=ModalMuller(...))`.
Each replay starts from the archived initial curve of its MA-005
`shifted_rotated_c` stage (contrast 13.3), with the archived observations,
configuration, quota and SC-035 update. The service chooses its own resolution
tokens.

| Stage | K_trace (windows) | Trials equal | Accepted | Solves / derivative batches | Loss rel. change | Endpoint max diff |
|---|---|---:|---:|---:|---:|---:|
| D `stage_2_damped` | 64/96 (128/160) | 25/25 | 10 | 104 / 22 | 3.5e-14 | 1.3e-12 units (6.6e-14 m) |
| D `release_M11` | 96/128 (160/192) | 7/7 | 7 | 304 / 152 | 3.2e-12 | 9.4e-13 units (4.7e-14 m) |
| DF `fixed_M43` | 96/128 (160/192) | 1/1 | 1 | 76 / 38 | 2.6e-8 | 1.7e-13 units (8.3e-15 m) |

For every stage, every trial's iteration, damping, backtrack and status
matches, as do the accepted indices, the exit, and the stage-only work
counts. The prototype's endpoint differences were 2.96e-12, 1.51e-12 and
1.76e-13 units. The third loss change is relative to a loss of 2.5e-11.
Replay wall times (18 s, 59 s, 19 s at four frequency threads) ran
concurrently with the accuracy jobs and are not matched timings.

## Matched timing

Hardware: Intel Core Ultra 9 285K, RTX 5090, one BLAS thread. Three
sequential repetitions per method, with the order rotated and reversed, and
medians reported. Each repetition starts with a cold modal geometry. CUDA Kress
is `NodalKress` with SPD-016 and four frequency threads. The prototype is the
review's `NativePhysics` on one thread. Geometry-update preparation is excluded
from every method.

**19-frequency DF endpoint catalog** (K=192, M=67, 0.25–2.5 GHz):

| Method | Level | New geometry forward (s) | Same geometry forward (s) | Jacobian (s) | Worst field | Jacobian |
|---|---|---:|---:|---:|---:|---:|
| Kress CUDA, N=512 | production | 0.447 | 0.446 | 0.216 | 1.1e-13 | 7.7e-14 |
| Kress CPU, N=512 | production | 13.54 | 13.55 | 0.379 | 6.7e-14 | 6.7e-14 |
| Modal prototype | production | 46.57 | 4.20 | 0.069 | 1.6e-10 | 3.0e-8 |
| **Modal service, 1 thread** | production | **4.32** | 2.29 | 0.038 | 1.6e-10 | 3.0e-8 |
| **Modal service, 4 threads** | production | **2.19** | 0.77 | 0.022 | 1.6e-10 | 3.0e-8 |
| Kress CUDA, N=1024 | refined | 1.75 | 1.73 | 0.501 | 5.2e-14 | 4.3e-14 |
| Modal prototype | refined | 46.69 | 4.42 | 0.079 | 2.0e-12 | 2.8e-12 |
| Modal service, 1 thread | refined | 6.64 | 3.54 | 0.048 | 1.8e-12 | 2.6e-12 |
| Modal service, 4 threads | refined | 3.34 | 1.58 | 0.024 | 1.8e-12 | 2.6e-12 |

The catalog reference is 1024-node CPU Kress.

**Single frequency, new-geometry forward (s):**

| Fixture | Kress CUDA 512 | Kress CPU 512 | Prototype | Service, 1 thread | Service, 4 threads |
|---|---:|---:|---:|---:|---:|
| C, 2.5 GHz | 0.040 | 0.710 | 0.836 | 0.256 | 0.266 |
| C, damped 1 GHz | 0.045 | 0.837 | 0.802 | 0.229 | 0.235 |
| DF endpoint, 2.5 GHz | 0.040 | 0.715 | 7.910 | 2.166 | 1.407 |

For a new geometry, the service is 3.3–3.7× faster than the prototype at one
frequency and 10.8× faster on the catalog (21× with four threads).

The receipt splits the one-core production catalog run (38 evaluations) as
follows:

- Geometry preparation (certified log|W|², T_n(R) and wave arrays): 1.43 s
  once per curve.
- Assembly: 4.62 s in total (0.12 s per evaluation, including the lazy
  extension of T_n).
- Graf sources and receivers: 12 ms per evaluation.
- LU and fields: 0.14 s in total.

In the prototype, the 42 s gap between new- and same-geometry runs was mostly
per-frequency regular-wave expansion, about 1.9 s per frequency.

CUDA Kress remains 4.9× faster on the production catalog and about 35× faster
on a single K=192 frequency. The service beats CPU Kress by 3.1× on one core.
None of this is inverse-campaign runtime.

## Reproduce

These receipts are pinned to commit `88f5ee1b`. The source-hash check in
`summarize.py` applies at that commit; the CUDA work after it changed
`modal_muller.py` and `modal_operator.py`, with CPU outputs bitwise unchanged.
Run from the repository root in EMNerf, with the service, replays and
benchmark run sequentially for timing:

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
D=results/validation/cleaned_interfaces/modal-muller-service-20260930
"$PY" -m pytest -q experiments/cleaned_interface/test_modal_muller.py
for p in c endpoint damped directional; do "$PY" $D/accuracy.py $p; done
for s in stage_2_damped release_M11 fixed_M43; do "$PY" $D/replay.py $s 4; done
"$PY" $D/benchmark.py single && "$PY" $D/benchmark.py catalog
"$PY" $D/summarize.py
```

`summarize.py` asserts every replay criterion, checks that each receipt's
recorded `modal_*.py` hash matches the current source, and recomputes the
ratios in `summary.json`. Every receipt records the git head, the source
hashes, and (for the benchmark) the environment and GPU state.

## Scope

- Established: fixture accuracy and complete-trial derivatives, three archived
  LM stages, the contract and end-to-end runner tests, and matched forward and
  Jacobian timings.
- Not established: localization-to-tail behaviour on real scenes, the other
  contrasts and scenes, multiple components, a GPU implementation, or any
  campaign retention or runtime claim.
- The |W|² certificate is an exact-arithmetic inequality with a generous
  rounding allowance, not interval arithmetic.
- The Graf and regular-wave bounds are explicit, but the regular-wave series
  still uses powers of |ζ|². Its cancellation, `eps*I0(|k| rho)`, is refused
  above 1e-9; it is about 1e-11 at the highest catalog frequency.
