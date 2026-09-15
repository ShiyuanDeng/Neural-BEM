# BIE-004 — experiment-local coupled analytic derivatives

This module differentiates fixed-topology, multi-interface Kress shape response
without modifying the shared solver or optimizer. The
[approved contract](../../docs/iterations/boundary_bie/iteration_02/03_plan.md)
owns the fixed cases, accuracy gates and global execution budget.

**Completed: accurate coupled Jacobians and 1.87x median speedup.**
[Results and evidence](../../results/validation/boundary_bie/BIE-004-20260915-coupled-02/README.md).
Production integration and inverse recovery remain untested.

## Numerical seam

`operators.directional_operators(base, directions)` returns dA, dB and dC in the
production ordering: all component Dirichlet nodes, then all Neumann nodes.
Directions are one existing `KressDirection` per component, including coherent
native position/derivative jets. Materials, source strengths/positions, receiver
positions and frequency stay fixed. Unequal native node counts and periods are
supported by the coupled algebra and covered by the wiring check.

The implementation imports the existing `_Jet`, `_difference_matrices` and
special-function derivative helpers; these private dependencies are pinned by
the result manifest. Smooth exterior-only cross blocks are differentiated in
this module. Unchanged self/cross blocks are reused. Every analytic call checks
its recomputed A/B/C against the stored production matrices.

`support.forward` assembles through production factories and stores one LU.
`support.tangent` reuses that LU in `A dU=dB-dA U`, then evaluates
`dY=dC U+C dU`. No full Jacobian or inverse is computed by a single tangent.
`run.py` compares all 34 production gauge directions on the two frozen states,
streams dA/dB/dC, and records complete accuracy and cost evidence.

## Reproduction

Use the exact command and source hashes in a result bundle. Each physical run
needs a fresh output path. `--previous` carries previous work counters/time into
one permitted correction attempt; it does not increase the contract's budget.
Do not replay a completed campaign merely to regenerate its report.

Saved-table audit/report (no new physical solves):

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.bie004_multi_derivative.summarize \
  results/validation/boundary_bie/BIE-004-20260915-coupled-02
```

Four algebra tests run before the ledger-counted physical checks. The first
attempt's malformed negative-test input was corrected before physical assembly;
the failed attempt is retained and its time charged to the continuation. All
shared numerical files remain read-only while topology work proceeds.
