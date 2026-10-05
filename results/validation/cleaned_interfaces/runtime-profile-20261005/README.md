# Historical runtime profile and lean-LM model (read-only)

**Historical, uncorrected accounting model.** Geometry/physics counters
include audit work while the fit timer excludes it; their subtraction does
not establish measured fit component shares. The lean-LM forecasts inherit
this limitation. See the [corrected pipeline audit](../../../../docs/iterations/CI-SPD/INVERSE_PIPELINE_AUDIT.md).
Raw calculations are preserved and reproducible; summary metadata records
this limitation explicitly.

Report: [iteration 32](../../../../docs/iterations/cleaned_interfaces/iteration_32/01_results.md).

```bash
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.runtime_profile
```

`summary.json` contains four analysis sections plus status/accounting metadata:

- **`profile_E`:** fit-time shares, physics thread-time components, solve mix
  and certificate-tier counts for E's successes and failures.
- **`decisions`:** which geometry check refused trials in B, E and RG; how E
  successes' margin rejections were classified; accepted steps by halving count.
- **`lean_model`:** low/central/high predictions, with assumptions, per-case
  speedups and suite totals.
- **`ggb_case8`:** the GGB-001 case 8 trajectory, read from the local Gau-Gal
  evidence path declared in the script. It is `null` if that checkout is
  absent; this analysis script does not enforce its commit or input hash.

No solves or fits are run. The lean numbers are model predictions, not
measurements.
