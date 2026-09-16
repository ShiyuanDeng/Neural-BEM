# SPD-002 — default CPU acceleration in the current pipeline

The user authorized making the fast analytic CPU path the current pipeline
default. [Plan and scope](../../docs/iterations/speedup/iteration_02/03_plan.md).

Normal Cartesian topology commands need no new options. The controller,
scene benchmark, challenge driver and TOP-025 campaign/scene runner accept
`--inverse-runtime reference` to restore FD/reference CPU. The environment
setting `SDF_INVERSE_RUNTIME=reference` covers other callers and subprocesses.
Run manifests record the selection; prepared benchmark/campaign inputs reject
a changed runtime selection. An explicit `gpr_bem_kress.execution.execution`
context takes precedence over the automatic CPU kernel context.

The fast profile uses analytic Cartesian coefficient derivatives and preserves
feasible-stencil behavior. Radial coefficient states still use FD. Analytic
base systems remain in physical-solve totals; derivative assemblies/tangents
are recorded separately and charged against the work cap. CUDA is optional.

## Full-pipeline validation

`run.py` invokes the actual current `experiments.top025.run` worker sequentially
on original `death` and `split` starts, for reference and fast profiles. It
reuses immutable prepared observations. Both automatic topology and the full
four-stage continuation run at the original resolutions and settings, including
recovery and refined-resolution checks. The experiment has a 2,400-second
outer ceiling plus the existing per-phase work limits. It stops on source
drift, another numerical worker, failed recovery or inconsistent records.

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=solvers:. \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -u \
  -m experiments.spd002_default_runtime.run --bundle FRESH_PATH
```

After completion, rebuild the report without BIE solves:

```bash
PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.spd002_default_runtime.summarize BUNDLE
```

The frozen numerical snapshot describes the measured run; documentation and
reporting additions need not share the dispatch time. Historical SPD-001 and
TOP-025 bundles are preserved. Two full-case checks do not replace a twelve-scene
campaign or guarantee identical speedups on every scene.
