# Neural SDF BEM AD: organised

This branch holds the maintained 2-D inverse pipeline: modal Müller physics with the
`slider` geometry update, run on the TG-002 benchmark. See the benchmark README for
current settings.

Legacy solvers and experiments remain in `/home/drdeng/Neural_SDF_BEM_AD`.
That workspace now also holds the documentation and results removed during
cleanup. The [transfer index](../Neural_SDF_BEM_AD/legacy_from_organised/2026-11-17/README.md)
locates added files and separately preserved versions.

## What is here

| Location | Role |
|---|---|
| [`experiments/benchmark/`](experiments/benchmark/README.md) | TG-002 scenes, the CLI, the fit runner and recovery scoring |
| `experiments/cleaned_interface/benchmark.py` | CI-001 helpers TG-002 still uses: acquisition ring, observations, scoring |
| `experiments/cleaned_interface/*`, `experiments/shape_continuation/*` | Other files only forward imports to `bem_inverse` |
| [`solvers/bem_inverse/`](solvers/bem_inverse/README.md) | The inverse: problem, policy, runner, modal physics, geometry updates |
| `solvers/gpr_bem_kress/`, `ordered_boundary/`, `periodic_kress/` | Nodal Kress reference solver, which generated the data, and curve geometry |
| `pytest/` | Tests for the kept packages |
| [`development_results/TG-002/`](development_results/TG-002/README.md) | Sealed benchmark inputs |
| [`development_results/`](development_results/README.md) | Sealed benchmark input bundle; historical outputs live in the original workspace |
| `results/` | Current comparison fits, raw scores, noise and execution records |
| [Clean and noisy recovery](docs/iterations/evaluate_our_method/01_measure_clean_and_noisy_recovery/results.md) | Default-method plan and results from 17 November 2026 |
| [Ablations](docs/iterations/evaluate_our_method/02_run_ablations/results.md) | Contrast, data, backend, shape-band and frequency comparisons |
| [Untuned GauGal reference](docs/iterations/evaluate_our_method/03_record_untuned_gaugal_reference/results.md) | Older clean imports and the new noisy reference run |
| [`docs/cleanup/`](docs/cleanup/documentation.md) | Recorded decisions and completed cleanup work |
| [`docs/reference/`](docs/reference) | A1–C12 code map, modal coefficient derivation, node-free scope, Kress guide |

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
