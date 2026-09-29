# MA-001 evidence: wavefield-pair structure of shape sensitivities

2026-09-28. Interpretation: [iteration 02 results](../../../../docs/iterations/modal_atlas/iteration_02/01_results.md).

| File | Contents |
|---|---|
| `circle.json` | Part A: circle frontier table (contrasts 0.33/0.5/10), trapped-pole horizon rows, horizon distributions (contrasts 0.33/0.5/3/10). |
| `noncircular_analysis.json` | Part B: per state and frequency, the qualification checks, trace supports, frontier, projected-truncation needs, and cancellation/brightness arrays. |
| `noncircular_tables.md` | Part B tables generated from the analysis. |
| `states.json` | Part B states and the endpoints' final update band `M`. |
| `MA-001_summary.png` | Three-panel summary figure. |

The raw trace spectra (11 states × 2 grids, about 155 MB of compressed `.npz`) were not
committed. They are regenerated deterministically by the commands below,
which take about 12 min on 4 cores.

```bash
# Part A (about 3 min, one core)
PYTHONPATH=. python -m experiments.modal_atlas.circle_study --output results/validation/modal_atlas/MA-001/circle.json
# Part B (BIE solves, one BLAS thread per worker)
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=solvers:. \
  python -m experiments.modal_atlas.noncircular --output <scratch>
PYTHONPATH=solvers:. python -c "import json,pathlib; from experiments.modal_atlas.analyze import analyze; \
  d=pathlib.Path('<scratch>'); json.dump({p.stem.replace('__','/'): analyze(p) for p in sorted(d.glob('*.npz'))}, \
  open('results/validation/modal_atlas/MA-001/noncircular_analysis.json','w'))"
PYTHONPATH=. python -m experiments.modal_atlas.summarize --analysis results/validation/modal_atlas/MA-001/noncircular_analysis.json \
  --states <scratch>/states.json --output results/validation/modal_atlas/MA-001/noncircular_tables.md
PYTHONPATH=. python experiments/modal_atlas/figure.py results/validation/modal_atlas/MA-001
# Tests
PYTHONPATH=. python -m pytest -q experiments/modal_atlas
```
