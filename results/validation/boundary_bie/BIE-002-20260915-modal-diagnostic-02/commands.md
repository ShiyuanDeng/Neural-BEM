# Actual campaign command

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.bie002_modal_diagnostic.run_diagnostic --output results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02
```

The runner executes the algebra tests before physical assemblies. All numerical work is in this process except that counted test subprocess.

## Reporting and source audit

```bash
python -m experiments.bie002_modal_diagnostic.summarize results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02
```

The command above reads saved tables only. `reporting_validation.json` verifies
counter reconciliation, completed operations, physical gate coverage and source
hashes. The original two failed invocations used the same numerical command with
output suffix `-01`; their bootstrap errors are preserved in that sibling bundle.
No directional work remains authorized within the consumed 36-call allowance.
