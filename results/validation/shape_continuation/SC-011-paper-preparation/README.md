# SC-011 — Paper profiles and cheap smoke qualification

2026-09-22. The user authorized preparation for the paper comparison and
explicitly ruled out expensive inverse runs. No new branch was created.
Numerical source was frozen at `2c6b2a3fb82549cf50bd3f83533a8617162bb340` before
measurement. All **41 source hashes** in both manifests matched afterward.

The [profile and fidelity audit](../../../../experiments/shape_continuation/PAPER.md)
describe the remaining differences from the author algorithm. These results
do **not** reproduce Figure 1 or demonstrate high-contrast recovery.

## Performed work

- **72 tests passed in 2.69 s**, including the existing inverse/controller and
  Kress block/isolation tests. New controls cover the zero-solve default, fixed
  smoke caps, observation-failure isolation, budget evidence, polygon scoring,
  and the contrast-10 forward field against an independent circle series.
- [Full plan](plan/plan.json): both contrasts, all 117 frequencies through k=30,
  acquisition and resolution counts, and single-matrix memory sizes. **Zero
  forward or inverse solves** for planning.
- [Smoke](smoke/summary.json): one attempted optimization iteration at k=1 per
  contrast, each accepting one update. Shared cap: 16 forwards and 30 seconds.
  Actual total: **15 forwards, 6 Jacobians, 2.8515 s**, including reference
  generation, inverse, refinement and area scoring. Single BLAS thread.
  This is one timing pass, not a benchmark or speedup comparison.

| Contrast `ki²/k²` | M / K / N | Initial → final residual | Forward calls | Relative symmetric-area error |
|---|---|---|---|---|
| 0.33 | 3 / 70 / 142 | 0.177720 → 0.122235 | 9 | 0.332697 |
| 10 | 9 / 70 / 222 | 0.152559 → 0.147046 | 6 | 0.352943 |

Both local stops are **iteration_limit**, intentionally after one update, not
data-fit or convergence claims. Both use filter level 3 with no step halvings;
the low-contrast update is SD and the high-contrast update is GN. All trial
records, including rejected candidates, are saved. Neither one-step shape is
a recovered glider.

Reference N/2N differences: `6.79e-11` (114/228 nodes, contrast .33) and
`5.52e-16` (360/720 nodes, contrast 10), against tolerance `1e-7`. Endpoint field
and full normal-Jacobian differences are at most `1.26e-15` and `1.12e-15`,
against tolerance `1e-6`. Polygon scores at 4096/8192 vertices change by at most
`3.84e-7` in absolute normalized area. See [audit.json](audit.json).

## Reproduce

From the repository root, use fresh output paths:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pip install -r experiments/shape_continuation/requirements-paper.txt
$PY -m pytest -q experiments/shape_continuation \
  pytest/gpr_bem_kress/test_isolation_and_api.py \
  pytest/gpr_bem_kress/test_muller_blocks.py
$PY -m experiments.shape_continuation.paper --output /tmp/sc011-plan-new
$PY -m experiments.shape_continuation.paper --mode smoke --output /tmp/sc011-smoke-new
```

Environment: Python 3.9, NumPy 2.0.2, Shapely 2.0.7; exact GEOS and platform
versions are in the manifests. Shapely is a new optional **evaluation-only**
dependency; importing the paper profile or running the forward/inverse does
not load it.

## Limits exposed without running the campaign

This explicit interpretation of the paper's Fourier storage is expensive for
the dense solver. At k=30, on the initial circle, inverse N is 4202 / 6642 for
contrasts .33 / 10. The high-contrast doubled reference would require N=21580:
one complex Müller matrix alone is about **29.8 GB**, before work arrays or LU.
The plan is not a runtime feasibility qualification. High-frequency work needs
separate resolution/cost qualification; no such matrices were allocated here.

Curvature tolerance, stopping normalization, quadrature, candidate acceptance,
and per-frequency rather than per-update storage still differ or remain
underspecified. Those are recorded explicitly in the audit. The full ladders,
Figure 1 recovery, adaptive-policy comparisons and volume inverse were not run.
