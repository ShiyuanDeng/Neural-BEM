# SPD-012: CUDA as the shape-continuation default

**Status: PASS.** The GPU is now the default: with no environment variable set, forward solves use the qualified CUDA assembly whenever torch sees a GPU. That covers single curves (SPD-011) and multi-object boundaries (SPD-013). `SC_FORWARD_BACKEND=cpu` pins the original SciPy reference, which reproduces archived runs bit for bit and never imports torch.

The [approved plan](../../../../docs/iterations/speedup/iteration_10/03_plan.md) governs scope. The user replied "yes for first two" to the proposed next steps.

## Behaviour

| `SC_FORWARD_BACKEND` | Behaviour |
|---|---|
| unset / `auto` (default) | CUDA when torch sees a device and the geometry is supported; otherwise the CPU reference. A device out-of-memory error retries that solve on the CPU, or that reciprocal solve from the host LU factors. It warns and counts each fallback (`cuda_assembly.fallback_counts()`) |
| `cpu` | CPU reference, bit-identical to history. Torch is never imported |
| `cuda` | CUDA required; errors if no device is visible; out-of-memory errors raise |

`ForwardState.backend` records `cuda`, `cpu` or `cpu-fallback`. Frequency threading (SPD-010, `SC_FREQUENCY_THREADS`, default 8) is unchanged.

## Checks

All runs are from clean commit `9c98459a` with no backend or thread variables set, except where `cpu` is pinned.

| Check | Result |
|---|---|
| Default SC-043 circle and peanut vs SPD-011's CUDA replay | **Bit-identical**: 32,387 values ([default_sc043_vs_spd011.json](default_sc043_vs_spd011.json)). The GPU path is deterministic across runs and across 4 vs 8 threads |
| The same runs vs the archive (SPD-011 trajectory gate) | PASS: equal outcomes, blocks, units and accepted steps; RMS within 2.2e-9. 254.7 → 17.2 s and 652.0 → 35.5 s, with 2 workers × 8 threads ([default_sc043_gate.json](default_sc043_gate.json)) |
| Default SC-048 arms vs SPD-013's CUDA replay | **Bit-identical**: 52,518 values ([default_sc048_vs_spd013.json](default_sc048_vs_spd013.json)); trajectory gates PASS |
| `SC_FORWARD_BACKEND=cpu`, SC-043 circle vs the archive | **Bit-identical**, 5.8× faster through threads alone ([cpu_sc043/comparison.json](cpu_sc043/comparison.json)) |
| Test suites | 340 pass under the default, and 340 under `cpu`. New `test_backend_default.py` covers the selection rules, CPU vs CUDA agreement, thread-independent GPU values, and both out-of-memory fallbacks (forward and reciprocal), which are strict under `cuda` |
| No GPU visible (`CUDA_VISIBLE_DEVICES=""`) | `auto` selects the CPU, and solves report `backend == "cpu"` |

## Contract changes

- The pipeline isolation test (`test_pipeline.py`) now runs twice. The `cpu` path must load neither torch nor any legacy or neural package. The `auto` path may load torch and nothing else from that list.
- `test_blocked_reciprocal_contraction_matches_literal_identity` solves through `forward._solve`, so it holds for SciPy and device LU factors alike.
- The SPD-010 bit-identity tests pin `cpu` explicitly.

## What to know

- Default results now match archived CPU results to round-off, not bit for bit. Single-object curves differ by at most 5e-13 of max|c| and two-object curves by at most 5.8e-10. To regenerate a committed record exactly, set `SC_FORWARD_BACKEND=cpu`.
- Each worker process now initializes CUDA (about 0.5 GB of device memory plus its working set). The SPD-011/013 six-worker runs peaked at 11–15 GB on the 32 GB card. The out-of-memory fallback covers heavier sharing.
