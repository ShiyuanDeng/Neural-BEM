# NF-001 numerical evidence

Critical review and integrated changes:
[iteration 17](../../../../docs/iterations/cleaned_interfaces/iteration_17/01_results.md).
Advance scope: [iteration 16 plan](../../../../docs/iterations/cleaned_interfaces/iteration_16/03_plan.md).

Run from repository root in a fresh directory:

```bash
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.cleaned_interface.node_free_audit --output FRESH_DIRECTORY
```

- `provenance.json`: source SHA256s, baseline commit, Python/numerical-library
  versions and GPU. Numerical comparisons were sequential; host-wide load was
  not controlled. The baseline had 76 passing cleaned-interface tests.
- `tangent_*.json`: every FD step, independent geometry-grid refinement, finite
  trial comparison, three warm preparation timings per method.
- `physics_*.json`: real/damped complete-trial derivative checks and independent
  trace refinement on the kite and saved hook, contrast 0.5.
- `lm.json`: both bounded inverse arms, endpoints, work and outcomes.
- `adversarial.json`: every CPU/CUDA result, including all inconclusive cases.
- `quadrature.json`: every tested grid, with a 16384-point reference.
- `gpu_gate.json`: independent analysis of existing NU-007 gap data, with its
  input hash. This is not a fresh GPU-certificate campaign.
- `summary.json`: all results together; numerical script time 45.264 s.
- `drift-regression/drift.json`: repaired NU-005 report replayed on all six
  archived cases, with expensive certificate recomputation disabled. It returns
  the original 6/6 match, identical decisions and zero sampled fallbacks; these
  are historical runs, not six fresh inverse runs.
- `validation.json`, `validation.log`, `validation_focused.log`: 101 passing
  full-suite tests and 14 final focused tests (102 distinct tests), final source
  hashes and an explicit list of source changes after the numerical experiment.
  `validation_attempt_01.log` preserves the corrected default-plan compatibility
  failure. `cli_plan.json` verifies explicit NU-006 selection through the CLI.

The analytic tangent is retained as an explicit experimental selection; NU-006
CUDA FD remains faster. No all-36 or sample-free-inverse claim is made.
