# BIE-002 modal diagnostic

Experiment-local fixed-geometry Fourier projection and nonidentity operator
structure measurements. This module imports the current Kress factories and
existing single-interface analytic directional operators. It never changes
shared solver or topology code.

The [approved plan](../../docs/iterations/boundary_bie/iteration_01/03_plan.md)
freezes cases, modes, directions, tolerances, reference ladders and hard budgets.
The first campaign is **complete without promotion**:
[result bundle](../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md).

Rebuild the report without physical solves:

```bash
python -m experiments.bie002_modal_diagnostic.summarize \
  results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02
```

The physical regeneration command is in that bundle's `commands.md`; it needs
a fresh output directory and is not authorization for another campaign. The
36 directional-call allowance has been consumed. `workspace_before.json` pins
the imported numerical modules; the runner stops if they change.

`modal_projection.py` owns only discrete matrix algebra. `fixtures.py` imports
native analytic producers and reconstructs saved Cartesian coefficients without
calling an optimizer. `metrics.py` reserves work before execution and records
failed attempts. `run_diagnostic.py` orchestrates the frozen campaign;
`summarize.py` audits/reports saved tables. `test_modal_projection.py` contains
four algebra tests; physical tests and Taylor probes run inside the counted
campaign. Optional BLAS metadata discovery has a dependency-free fallback.
