# Iteration 10 results: SPD-012 and SPD-013

2026-09-27. Both experiments are **COMPLETE / PASS** under the [plan](03_plan.md). The user replied "yes for first two" to the proposed next steps. There is no independent reviewer.

## SPD-013: two-object runs on the GPU

The multicomponent Kress system is now built on the device. Its self blocks reuse SPD-011's kernels, and its smooth cross-component blocks come from the same Cephes Bessel port. The CPU topology and clearance validation runs first, unchanged.

- **Matrices:** agree within 1.4e-16 of max|A| over 80 systems. Predictions agree within 4.8e-15 and Jacobians within 1.8e-15.
- **Complete runs:** all 12 SC-047 strategy runs and all 3 SC-048 arms reproduce their outcomes, dispatch signatures, work units and passing audits. Worst-object RMS agrees within 6.8e-9.
- **Timing:** summed time fell from 3354 s to 843 s (4.0×).
- **CPU-thread control:** bit-identical on all 15 runs (446,310 values) and 2.2× faster. This extends SPD-010 to two-object runs.
- **Retained failure:** one harness attempt failed on an import path before any comparison.

See the [results](../../../../results/validation/speedup/SPD-013-20260927-cuda-multicomponent/README.md).

## SPD-012: CUDA is the default

`SC_FORWARD_BACKEND` now defaults to `auto`. That means CUDA when available, the CPU otherwise, and a CPU retry after a device out-of-memory error. `cpu` pins the bit-exact reference.

- **GPU determinism:** default-mode replays are bit-identical to SPD-011's and SPD-013's CUDA replays (84,905 values).
- **Reference path:** with `cpu` pinned, results are bit-identical to the archive.
- **Tests:** 340 pass under both settings.

See the [results](../../../../results/validation/speedup/SPD-012-20260927-cuda-default/README.md).

## Combined effect on the shape-continuation pipeline

These are shared-host observations under the new default. All six SC-043 single-object runs take 6.8–13.6× less time than the archived serial CPU runs, 6485 s → 639 s summed (SPD-011, six concurrent workers). The two-object runs are 4.0× faster. Video preparation is 5–7× faster through the unchanged renderer.

## Not done

Accelerating the O(N²) boundary self-intersection validation was item 3 of the proposal. It was not approved, and it is now the main CPU-side cost of a GPU solve.

**Subsequent approval, 2026-09-27:** after Codex's geometry investigation, the
user replied "you have my approval" to the bounded follow-up. That work is
recorded separately as [SPD-014](03_spd014_plan.md), now complete in
[iteration 11](../iteration_11/01_results.md); it does not change the scope
or results of SPD-012/013 above.
