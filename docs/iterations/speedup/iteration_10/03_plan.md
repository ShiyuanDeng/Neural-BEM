# SPD-012 and SPD-013: CUDA by default, and CUDA for two-object runs

2026-09-27. **Approval status: APPROVED.** After iteration 09, I listed three next decisions:

1. Make the GPU the default for shape-continuation runs.
2. Port the two-object runs (SC-047/048) to the GPU.
3. Speed up the geometry check.

The user replied, verbatim: "yes for first two". That approves items 1 and 2, recorded here as SPD-012 and SPD-013. Item 3 is not approved. **Execution status: IN PROGRESS.**

Owner: Claude Code. There is no independent reviewer. The work stays on the existing checkout and branch, `feature/shape-frequency-continuation`.

## SPD-013: CUDA multicomponent assembly

`build_multicomponent_muller_system` has three parts:

- Kress exterior-minus-interior self blocks for each component, identical to the single-interface blocks.
- Smooth exterior cross blocks between components: `H_n(k_o r)` for n = 0, 1, 2, weighted by source arc length.
- The same `[[I−dK, dV], [−dT, I+dKp]]` composition.

The port refactors `cuda_assembly` into two device builders, one for the four difference blocks and one for the cross blocks. The CPU `adapt_multicomponent_boundary` validation (topology and clearance) is reused unchanged.

Gates:

1. **Matrix.** Compare against the CPU `build_multicomponent_muller_system` for SC-047/048 scenes (initial, truth and endpoints), at every frequency, with N ∈ {256, 512} per component. Requirements: max |ΔA| / max |A| ≤ 1e-14; predictions and reciprocal Jacobians ≤ 1e-12; the residual guard passes.
2. **Trajectory.**
   - Replay SC-047's 12 strategy runs and SC-048's 3 arms with `SC_FORWARD_BACKEND=cuda`, from their stored inputs.
   - Each must have the same outcome, the same per-dispatch outcomes, stops and accepted counts, and the same work units.
   - Worst-object endpoint RMS must be within 1e-6 relative, and every endpoint audit must pass.
   - Any divergence is reported.
3. **CPU-thread control.** Replay the same runs on the CPU with `SC_FREQUENCY_THREADS=4`. They must be bit-identical to the archive, which extends SPD-010 to two-object runs.
4. **Tests.** New GPU tests pass alongside the existing suites.

## SPD-012: CUDA as the shape-continuation default

`SC_FORWARD_BACKEND` gains `auto`, which becomes the default:

- `auto` uses CUDA when torch and a CUDA device are available and the geometry is supported. Otherwise it uses the CPU reference.
- An explicit `cpu` restores the reference path.
- An explicit `cuda` fails if no GPU is available.
- Under `auto`, a device out-of-memory error during a solve falls back to the CPU for that solve, with a warning and a recorded count. An explicit `cuda` raises instead.
- Each `ForwardState` records the backend that produced it.

Two-object geometries join the default only after SPD-013's gates pass.

Gates:

1. The existing suites pass under the new default. Any test that needs CPU bit-identity pins `cpu` explicitly.
2. `SC_FORWARD_BACKEND=cpu` still reproduces SPD-010's bit-identity. An SC-043 replay under the default matches SPD-011's CUDA replay, which checks GPU run-to-run determinism.
3. The dispatch works: `auto` with no GPU visible (`CUDA_VISIBLE_DEVICES=""`) takes the CPU path, and a simulated out-of-memory error falls back and is counted.
4. The documentation says how to pin the reference path.
