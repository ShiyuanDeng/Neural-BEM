# MA-001R: MA-001 Part B re-run on the current solver

2026-09-29. Owner: Claude (Opus 5.5). Source: `032092cd` on
`feature/shape-frequency-continuation`, with the MA-001 code imported unchanged
from `claude/magical-meitner-11naoj` (`a5dd517b`). No code was edited.

**Why.** MA-001 ran on `d2cd5cf9`, before SPD-011 to SPD-015 (the CUDA default,
multicomponent CUDA assembly and native geometry acceleration). Its
[findings note](../../../../docs/reports/fully_modal_muller_atlas_MA-001_findings.md)
said items 1, 4 and 5 needed a re-check on current code before being relied on.

**Result: MA-001 Part B reproduces on the current code.**

- Every integer quantity is identical in all 11 states × 19 frequencies: trace
  supports `K_U`, `K_V` at 10/1/0.1%, frontiers at `τ = 1e-2/1e-3/1e-4`,
  trace bands, and the per-column needed band `K_J` at `1e-3` and `1e-6`.
- Continuous quantities agree to round-off. Column norms differ by at most
  `4.1e-10` relative on columns above `1e-6` of the strongest column, and
  `2.5e-7` on the tiny high-`p` columns. The available product magnitude
  differs by at most `5.8e-11` on columns above `1e-6`.
- Qualification is unchanged in every conclusion. Modal pair sum versus nodal
  quadrature is `≤ 3.1e-8` on the ten qualified states. Nodal quadrature
  versus production `shape_jacobian` is now `≤ 9.7e-16`, against `6.1e-16`
  before; this is the CUDA backend's round-off. `F_released_m/kite` is still
  unqualified: the grid discrepancy is `7.46e-4` and the truncation bound
  fails, exactly as archived.
- Run time: 29 s wall clock with 6 workers on the CUDA default, against about
  12 min on 4 CPU cores for the original.

So MA-001's findings 1 (the pair identity), 4 (the `K_trace(√τ) + 0.6p` trace
band) and 5 (no cancellation at contrast 0.5) hold on the current backend. The
circle findings (2 and 3) never depended on this branch's code.

| File | Contents |
|---|---|
| `summary.json` | Keys compared, maximum differences, both qualification tables. |
| `compare.py` | The comparison against `../MA-001/noncircular_analysis.json`. |
| `analyze_parallel.py` | MA-001's `analyze` over the 11 bundles in parallel. |
| `run.log`, `states.json` | Solve log and the state list. |

The 11 trace-spectrum bundles (about 155 MB) are not committed. To regenerate:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  python -m experiments.modal_atlas.noncircular --output <scratch> --workers 6
OMP_NUM_THREADS=1 PYTHONPATH=solvers:. python results/validation/modal_atlas/MA-001R/analyze_parallel.py \
  <scratch> <scratch>/noncircular_analysis.json
python results/validation/modal_atlas/MA-001R/compare.py <scratch>/noncircular_analysis.json \
  results/validation/modal_atlas/MA-001R/summary.json
```
