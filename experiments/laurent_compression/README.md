# LAU-001 — derivative-preserving compression of the native Laurent operator

Isolated screen for [Laurent iteration 01](../../docs/iterations/laurent/iteration_01/03_plan.md).
Measurements and the decision are in the
[result bundle](../../results/validation/laurent/LAU-001-20260917-modal-derivative-compression/README.md);
the verdict is `STRUCTURE_ONLY`.

`experiments/modal_muller_research/` and `solvers/` are **read-only imports**.
`adapters.py` is the only module that touches them, and it imports library
modules only — never `run_*`, `plot_*` or `probe`. Those files are hash-pinned
by 11 recorded bundles and nothing here modifies them.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

$PY -m pytest -q experiments/laurent_compression            # 27 tests
$PY -m experiments.laurent_compression.run_screen --output <dir> --stage pilot --dry-run
$PY -m experiments.laurent_compression.run_screen --output <fresh-dir> --stage campaign
```

The campaign is deterministic (no seeds) and took 31 s on one thread.

| Module | Owns |
|---|---|
| `adapters.py` | The exact identity/log-symbol/smooth split by linearity of `kernel_matrix`; analytic `D_v A` and `D_v b, D_v C`; the frozen-mask solve and tangent; an independent modal-to-nodal lift; the Kress oracle. Perturbed geometries keep the base centre and scale so the acquisition cache stays valid |
| `structure.py` | Gate G1b: predicted versus measured argument support, and the `(d, p*, log_order)` formula behind it |
| `masks.py` | `FULL`, `BAND`, `FORWARD`, `DERIVATIVE_AWARE`, `ANALYTIC_SUPPORT`; per-block allocation, deterministic ties, retention and derivative-support-union accounting |
| `metrics.py` | Frozen gates, the paired-data selection, the lifted residual, the cancellation-aware objective-derivative rule, and the hard-ceiling work ledger |
| `run_screen.py` | Stages G0–G4, the cutoff-qualification ladder, and every artifact the plan requires |
| `test_algebra.py` · `test_derivatives.py` | The plan's §10 checks, including the **entrywise `D_v A` versus finite differences** test that existed nowhere in the repository before this experiment |

Two bugs found and fixed during execution, both in this package and both worth
knowing if it is extended: a synthetic truth that was symmetry-orthogonal to
every training direction (zero objective gradient), and a finite difference that
held `b` and `C` fixed while the tangent differentiated them (so it compared two
different models). Both are covered by tests now.
