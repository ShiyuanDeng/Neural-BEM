# October 2 exploration: validation and provenance

The [research report](../../docs/reports/exploration_2026-10-02.md) links all ten
experiments, their measurements, derivations and primary references. Work began
after a fast-forward pull to `15611d94` on the existing
`feature/shape-frequency-continuation` branch. No branch or worktree was created.

## Validation

The [final combined test log](tests-final.log) records **60 passed**, with 14
matplotlib/pyparsing deprecation warnings. No test was skipped. It covers every
new experiment's focused tests plus existing Kress API and forward regressions.
The earlier [59-test run](tests-initial.log) is retained separately.

Run from the repository root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  experiments/atlas/test_jacobian_spectrum.py \
  experiments/ibim3d/test_sphere.py \
  experiments/fresnel/test_fresnel2001.py \
  experiments/algoim/test_algoim.py \
  experiments/exploratory_continuation/test_controls.py \
  experiments/halfspace/test_sommerfeld.py \
  pytest/gpr_bem_kress/test_polarization.py \
  pytest/gprmax_ref/test_time_domain_synthesis.py \
  pytest/gpr_bem_kress/test_isolation_and_api.py \
  pytest/gpr_bem_kress/test_muller_forward.py
```

This is the available EMNerf environment: Python 3.9.25, NumPy 2.0.2 and
SciPy 1.13.1. The Algoim checks used the compiled, checksum-verified upstream
cache described in its report. gprMax physical runs used their separate
installed environment and are preserved with inputs, source samples and logs.
The transient unit tests do not rerun FDTD. CPU timings in the reports were
collected under concurrent independent workloads and are descriptive.

## Retained evidence

[manifest.json](manifest.json) identifies the reviewed source and artifact
bytes using SHA256, records the final documentation-link audit and summarizes
the validation environment. It is a **post-run** inventory, not a claim that
every final source byte was present during every earlier experiment. Original
per-experiment manifests remain unchanged when they identify the source at
execution time.

After the atlas sweep, plotting gained explicit frequency colorbars and the
report gained qualifications about singular-vector nonuniqueness. After the
sphere runs, input guards were added without changing the evaluated formulas.
The TOP-009 full-tangent audit was then added as a separate computation. Other
post-run changes and provenance checks are recorded in the polarization,
transient, continuation and Algoim reports. The transient processing correction
has both original and corrected arrays/metrics; the physical solves were reused.

Failed pilots, numerical stops, timeouts, longer retries and corrected
completion flags remain labeled in the evidence. They are not silently replaced
with successful endpoints. The final source and data commit supplies the
versioned reproduction context; ignored historical checkpoints are not needed
for the new Algoim comparison because its exact input weights are retained in
plain JSON.
