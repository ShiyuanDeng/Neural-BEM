# Track 13 auxiliary field experiments

`joint_tail.py` implements the CVX-002 sparse joint inversion for complex
log fields and one real coefficient. It accepts boundary data, incident-field
gradients and a prescribed initial state. It does not import benchmark truth.
The unknown reference field has an H2 penalty; normalized frequency differences
have H3 penalties. A one-factor Picard step solves a regularized real-linear
least-squares problem, with actual nonlinear-objective backtracking.

`cvx002.py` owns TG-002 data generation, qualification, execution and post-fit
scoring. Its full fixed-source Cauchy data are **additional synthetic acquisition**;
this is not the unchanged paired benchmark. The original paired catalog is
reserved for physical prediction checks of the largest threshold contour.
The prototype changes no maintained solver defaults and asserts no global
convexity/convergence theorem.

The [registered plan](../../docs/iterations/convexification/CVX-002_plan.md) and
[results](../../docs/iterations/convexification/CVX-002_results.md) distinguish
the numerical qualifications, partial image improvement and failed recovery.
The original source archives and all failures are retained with the results.

Run from the repository root in the EMNerf environment with
`PYTHONPATH=solvers:.`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and
`MKL_NUM_THREADS=1` (environment variables or command prefixes). Every
measurement output directory must be fresh.

```bash
python -m experiments.convexification.cvx002 --output <fresh-screen-directory>
python -m experiments.convexification.cvx002 --output <fresh-refinement-directory> --grid 57 --cases circle__c0.5 --spans 0 4
```

The second command was conditional on the registered development gate and
uses exactly the same parameters. It is not permission to tune or expand the
screen using truth. `cvx002_diagnostics.py` implements the separately registered
phase refinement and saved-readout checks. It expects the sibling directories
`screen` and `refinement57` containing the prior receipts:

```bash
python -m experiments.convexification.cvx002_diagnostics --output <experiment-parent>/diagnostics
```

The following performs no optimization or forward solves and regenerates
tables, plots and validation receipts from saved screen/refinement artifacts:

```bash
python -m experiments.convexification.cvx002_report <screen-directory> <refinement-directory>
```

Measured runs record source archives/hashes and qualify their boundary fields,
normal derivatives, starting fields, log branches and linear algebra. The report
regenerator checks receipts against those hashes and arrays. An executed source
archive remains authoritative if later development changes current source files.
Saved `.npz` and figure artifacts require scoped `git add -f` under the repository
ignore rules. Preserve failed qualifications along with successful fits.
