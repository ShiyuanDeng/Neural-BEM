# AC-001 numerical evidence

2026-10-05. See [plan](../../../../docs/iterations/CI-SPD/AC-001_plan.md),
[results](../../../../docs/iterations/CI-SPD/AC-001_results.md), and
[derivation](../../../../docs/reference/modal_radial_coefficients.md).

## Final evidence

- `scalars.json` / `scalars-extended.log`: 24/24 scalar cases pass, with
  per-function errors against a 4096-point DCT and 80-digit Bessel/Hankel
  values, endpoint absolute errors, source hashes and timings.
- `forward.json` / `forward-extended.log`: 4/4 TG-002 highest-frequency
  matrix/field comparisons pass. N1024 nodal reference, K_trace=96, window=160.
- `scalar-miller.log`: 35 focused tests pass, including the extended-precision
  integer-order recurrence and refusal paths.
- `cuda-final.xml`: 5 CUDA tests pass on an NVIDIA GeForce RTX 5090, including
  field/Jacobian equivalence and OOM fallback semantics.
- `final-suite.log` / `final-suite.xml`: final maintained package, cleaned
  interface, shared continuation, Kress, and ordered-boundary regressions:
  **628 passed, 46 skipped, 15 warnings**, in 219.70 seconds. Five skipped
  modal CUDA checks passed separately with GPU access as recorded above.

All final production coefficients are complex128; their construction used
NumPy extended precision with a 64-bit significand on this Linux host.
`radial_work_precision_bits` was added as a diagnostic after the successful
forward run; this metadata-only addition does not change its coefficients.

## Intermediate evidence preserved

- `scalar-first.log` and `modal_operator_first.py`: first analytic candidate;
  three small-argument constant-coefficient cancellation failures.
- `modal_operator_differentiated.py`, `forward.log`,
  `forward-differentiated.json`: repaired small-argument path but failed damped
  C matrix gate after differentiation of float64 coefficients.
- `modal_operator_direct_float64.py`, `forward-direct-derivatives.log`,
  `forward-direct-float64.json`: direct derivative weights still failed the
  same damped matrix gate with float64 Bessel inputs.
- `scalars-initial.json`, `scalars-differentiated.json`, `scalars.log`,
  `scalars-final.log`, the earlier scalar logs, `modal-regression.log`,
  `package.*`, `shared.*` and `cuda.xml`: intermediate checks, not substitutes
  for final qualification. Scalar files include the corresponding source hashes.

The Python snapshots preserve source evidence; they are not standalone
drivers. The final drivers live in `experiments/benchmark/`.

## Reproduce

From the repository root, using the existing EMNerf Python environment:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.analytic_radial_validation
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.analytic_radial_forward
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest pytest/bem_inverse experiments/cleaned_interface experiments/shape_continuation pytest/gpr_bem_kress pytest/ordered_boundary -q
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest experiments/cleaned_interface/test_modal_muller.py -k cuda -q
```

The last command needs GPU access; sandboxed CUDA tests otherwise skip.
Drivers write their named JSON outputs in this directory. No inverse fit or
benchmark input regeneration is performed.
