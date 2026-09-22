# Cached updates and policy-controlled continuation

2026-09-22. Numerical sources: commit `5e26b09`. Their recorded SHA-256 hashes
were checked against the working files after the runs and all match. Numerical
sources stayed frozen during measurement. The standalone reproduction script
is hashed separately in the manifest. All runs use one BLAS thread and the
same reference CPU nodal Müller/Kress kernels as the preceding baseline.

The refactor exposes `prepare_state`, `optimise_step`, and `fit_prepared` plus
a plain callable continuation strategy. Repeating k or changing M/C/K padding
reuses the physical state; changing the physical problem or N rebuilds it.
One budget spans decisions and optional qualification. A failed qualification
rolls back the decision while preserving its report. The fixed-ladder API is
an adapter over this controller. No legacy inverse dependencies were added.

## Fixed-trajectory controls

| Archived problem | Stages replayed | Saved coefficient arrays | Forward calls | Jacobians | Result |
|---|---:|---:|---:|---:|---|
| SC-009 ellipse | 5, k=1 to 2 | 13 | 21 | 8 | Every array bitwise identical; histories, every trial and stop reason exactly identical. |
| SC-005 glider | First 5, k=1 to 2 | 135 | 190 | 130 | Every array bitwise identical; histories, every trial and stop reason exactly identical. |

Forward counts also match the archived trajectories exactly. The glider prefix
exercises extensive curvature rejection, backtracking and filtering. This is
a regression control; its early endpoint is not a successful glider recovery.
Single-pass elapsed times were 0.826 s and 14.259 s respectively; this is not
a new speed benchmark or a comparison against SPD.

## Actual adaptive ellipse example

The illustrative rule requests one accepted update per decision. It starts at
M=1, increases M after a local stop up to the baseline band at that frequency,
then advances k. It continues to receive the complete decision history.
Every decision includes a field **and full normal Jacobian** N/2N check. The
rule can double N and retry after a failed check; this particular run needed
no such retries. Truth and held-out data enter scoring only after inversion.

- 13 decisions, 11 accepted updates, frequencies k=1 through 2. At k=1 the
  rule actually uses M=1, then 2, then 3 before advancing frequency.
- 40 forwards: 27 optimization calls plus 13 qualification calls. No extra
  starting solve between same-frequency decisions. 37 Jacobians: 11 optimizer
  derivatives plus 26 qualification derivatives. Two separate evaluation solves.
- Every qualification passes: largest relative field discrepancy `2.37e-15`,
  largest relative Jacobian discrepancy `1.23e-15` (rounded upward).
- Final training residual `1.09135e-6`; unused frequency/acquisition error
  `2.59033e-7`; conservative relative boundary-error upper bound `8.73717e-4`.
- Controller stops with `policy_stop` after the final frequency reports
  `data_fit`. Inverse plus qualification/checkpoint time is 2.742 s.

This verifies that harmonic and frequency decisions can change during a real
inverse solve. It does not establish that this illustrative rule is faster,
more robust, or preferable to the fixed ladder. No broad policy sweep or full
117-frequency campaign was run for this refactor.

## Contract tests and reproduction

**57 tests pass**, including physical cache invalidation, data-only residual
changes, exact manual-step/whole-fit equivalence, qualification rollback and
cache recovery, budget exhaustion during fitting/checking, repeated/revisited
frequencies, decision limits, and clean imports. A real glider field can pass
while its Jacobian fails the resolution gate; the gate checks both.

From the repository root:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pytest -q experiments/shape_continuation/test_controller.py \
  experiments/shape_continuation/test_pipeline.py \
  pytest/gpr_bem_kress/test_isolation_and_api.py \
  pytest/gpr_bem_kress/test_muller_blocks.py
$PY results/validation/shape_continuation/SC-010-step-controller/replay.py \
  --output /tmp/controller-qualification-new
```

Use a fresh output path. [The saved measurements](measurements/) contain source
and input hashes, full fixed-replay histories/trials, coefficient arrays, every
adaptive decision and qualification, endpoint fields, work counters and times.
The [controller contract and pseudocode](../../../../experiments/shape_continuation/README.md#adaptive-controller-contract)
describe the experiment interface and stopping/rollback semantics.
