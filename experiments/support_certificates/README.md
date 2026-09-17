# Support-exclusion research screen

Read the [assessment and limitations](../../results/experiments/outsider_research_20260916/README.md) before interpreting any result as a certificate for a physical scene. Bounds apply to a finite scalar model and stated material box. Floating-point safeguards are not interval proofs.

Run from the repository root using Python with NumPy, SciPy, Matplotlib and pytest. The session used `/home/drdeng/miniconda3/envs/EMNerf/bin/python`. Limit BLAS threads for these small dense problems:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
python -m pytest -q experiments/support_certificates/test_core.py experiments/support_certificates/test_layered.py
```

The main sequence is:

```bash
python -m experiments.support_certificates.layered_screen
python -m experiments.support_certificates.complex_screen
python -m experiments.support_certificates.primal_check
python -m experiments.support_certificates.broad_material
python -m experiments.support_certificates.broad_qualification
```

`layered_screen` generates the shared fine-grid synthetic data. `complex_screen` bounds arbitrary heterogeneous complex materials with independently bounded permittivity and conductivity. `primal_check` reconstructs saved dual matrices and runs actual physical fits. `broad_material` widens the permittivity upper bound; `broad_qualification` freezes its best witness and subdivides its cells, then evaluates new measurements. Optimizer `success=False` in a witness means the evaluation limit was reached; the actual feasible residual remains a valid upper witness.

Earlier controls, useful for auditing the search rather than the final claim:

```bash
python -m experiments.support_certificates.screen
python -m experiments.support_certificates.material_screen
python -m experiments.support_certificates.alternatives
python -m experiments.support_certificates.independent
python -m experiments.support_certificates.cross_screen
python -m experiments.support_certificates.cross_material
python -m experiments.support_certificates.cross_qualification
```

Results are JSON under `results/experiments/support_certificates_20260916`. Generated NPZ files are caches ignored by the repository and are recreated by the commands. Stored multipliers and material parameters are retained in JSON. `success` for a dual indicates a usable positive-definite numerical bound, not a proven optimal dual solution. Failure to find a positive-definite start is a solver failure, not evidence that the inverse problem is impossible.

After the ROM and passivity runs, `python -m experiments.support_certificates.report` renders the joint figures and `python -m experiments.support_certificates.audit` verifies saved duals and writes the final manifest. Production solvers and their material guardrails are unchanged.
