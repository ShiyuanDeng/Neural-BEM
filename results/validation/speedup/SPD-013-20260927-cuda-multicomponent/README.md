# SPD-013: CUDA two-object (multicomponent) assembly

**Status: PASS.** With `SC_FORWARD_BACKEND=cuda`, all 15 archived two-object runs (12 SC-047 strategy runs and the 3 SC-048 arms) reproduce every outcome, per-dispatch stop, accepted count and work unit. Worst-object RMS agrees within 6.8e-9 relative, and every endpoint audit passes. Summed time fell from 3354 s to 843 s (4.0×). A CPU-thread control is **bit-identical** to the archive on all 15 runs, which extends SPD-010 to two-object runs.

The [approved plan](../../../../docs/iterations/speedup/iteration_10/03_plan.md) governs scope. The user replied "yes for first two" to the proposed next steps.

## Gate 1: matrices, predictions and Jacobians

There are ten two-object scenes: SC-047's initial and true pairs and joint-clean endpoints at both separations, plus SC-048's perturbed start and three arm endpoints. Each was solved at all 4 frequencies, with 256 and 512 nodes per object: 80 systems per backend ([matrix_gate.json](matrix_gate.json)).

| Quantity | Worst | Limit |
|---|---:|---:|
| max \|A_gpu − A_cpu\| / max \|A_cpu\| | 1.4e-16 | 1e-14 |
| Receiver predictions | 4.8e-15 | 1e-12 |
| Reciprocal Jacobians (M5 projected update) | 1.8e-15 | 1e-12 |
| GPU residual | 2.6e-15 | 1e-10 guard |

## Gates 2–3: complete two-object runs

Each run was replayed from its stored inputs with the unchanged `fit`, using 6 workers × 4 frequency threads from clean commit `c4411fb9` ([replay_multi.py](replay_multi.py)).

| Runs | Archive, serial CPU | CPU threads (control) | CUDA |
|---|---:|---:|---:|
| 12 SC-047 strategy runs, summed | 2967 s | 1345 s, **bit-identical** | 758 s |
| 3 SC-048 arms, summed | 387 s | 169 s, **bit-identical** | 85 s |
| Total | 3354 s | 1514 s (2.2×) | 843 s (4.0×) |

- **CPU threads:** 446,310 recorded values match the archive exactly ([cpu_threads/comparison.json](cpu_threads/comparison.json)).
- **CUDA** ([cuda/comparison.json](cuda/comparison.json), [drift.json](drift.json)):
  - Outcomes, dispatch signatures (outcome, stop, accepted, units, active object, modes) and work units are identical in all 15 runs.
  - Worst-object RMS differs by 2e-12 to 6.8e-9 relative.
  - Accepted and final curves differ by at most 5.8e-10 of max|c|, in SC-048's global-direction arm; the others fall between 1e-12 and 1e-11.
  - Per-dispatch final losses differ by at most 1.7e-8 relative. All audits pass.
  - Peak device memory was 11.2 GB ([gpu_memory.log](gpu_memory.log)).
- **Timing:** shared-host observations. The archive ran serially inside each study driver; the replays ran 6 concurrent workers, with load average 6–9 during the CUDA run.

The speed-up is smaller than for single objects (up to 13.6× in SPD-011). These runs have only 4 frequencies and 256 nodes per object, so the CPU-side topology and clearance validation, the receiver builders and the LM work take a larger share of the time.

An earlier replay attempt of the harness failed on an import path, before any comparison. It is retained in [attempt_01_harness_import_error](attempt_01_harness_import_error).

## What changed

`solvers/gpr_bem_kress/cuda_assembly.py` now has three device builders:

- `_difference_blocks`, the single-interface Kress blocks, shared with SPD-011;
- `_cross_blocks`, the ordinary exterior trapezoid kernels between components;
- `build_multicomponent_muller_matrix`, which runs the unchanged CPU `adapt_multicomponent_boundary` topology and clearance validation, then fills and composes the global system.

`build_system_matrix` dispatches single and multi-component geometries, and `forward.solve` uses it. Tests cover matrix equality for two-component boundaries, the clearance guard, and CPU/CUDA agreement of the forward solve and Jacobian.
