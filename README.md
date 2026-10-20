# Neural SDF BEM AD: organised

This branch holds only the latest 2-D inverse pipeline: modal Müller physics with the
certified spectral geometry update (`modal_fixed`), run on the TG-002 benchmark. It is the
starting point for a clean rewrite.

Everything else was removed here: legacy solvers, root `run_*.py` drivers, older
experiments, their results and their docs. They remain on
`feature/shape-frequency-continuation`. To restore one path, run
`git checkout feature/shape-frequency-continuation -- <path>`.

## What is here

| Location | Role |
|---|---|
| [`experiments/benchmark/`](experiments/benchmark/README.md) | TG-002 scenes, the CLI, the fit runner and recovery scoring |
| `experiments/cleaned_interface/benchmark.py` | CI-001 helpers TG-002 still uses: acquisition ring, observations, scoring |
| `experiments/cleaned_interface/*`, `experiments/shape_continuation/*` | Other files only forward imports to `bem_inverse` |
| [`solvers/bem_inverse/`](solvers/bem_inverse/README.md) | The inverse: problem, policy, runner, modal physics, geometry updates |
| `solvers/gpr_bem_kress/`, `ordered_boundary/`, `periodic_kress/` | Nodal Kress reference solver, which generated the data, and curve geometry |
| `pytest/` | Tests for the kept packages |
| `results/validation/cleaned_interfaces/TG-002/` | Sealed benchmark inputs |
| [`results/validation/cleaned_interfaces/PC-001/`](results/validation/cleaned_interfaces/PC-001/README.md) `M1/` | Reference run of the default method: 26/30 recovered |
| [`docs/evidence.md`](docs/evidence.md) | Why each part of the pipeline was chosen, with the supporting numbers |
| [`docs/reference/`](docs/README.md) | A1–C12 code map, modal coefficient derivation, node-free scope, Kress guide |

The kept code is every file the benchmark CLI imports, found by tracing imports from
`experiments/benchmark`. Kept tests import only that code. Some kept modules still carry
opt-in research options; the rewrite decides which of them stay.

## Run

From the repository root, in the EMNerf environment:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

"$PY" -m experiments.benchmark verify                    # check the sealed inputs
"$PY" -m experiments.benchmark plan --cases aphex_twin__c13.3
"$PY" -m experiments.benchmark run --cases circle__c0.5 --run-dir <fresh dir>
"$PY" -m pytest experiments/benchmark pytest -q
```

A fit of `circle__c0.5` on this branch reproduces the PC-001 `M1` result to about nine
significant figures.
