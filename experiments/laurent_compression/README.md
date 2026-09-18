# LAU-001 — derivative-preserving compression of the native Laurent operator

Isolated screen for [Laurent iteration 01](../../docs/iterations/laurent/iteration_01/03_plan.md).
The original measurements remain in the
[LAU-001 bundle](../../results/validation/laurent/LAU-001-20260917-modal-derivative-compression/README.md).
The current runner implements the independently reviewed **LAU-001-R1 validation
repair**, authorized by the user on 2026-09-17. Its contract is
[iteration 02](../../docs/iterations/laurent/iteration_02/03_plan.md), and its
current evidence is the [qualified rerun](../../results/validation/laurent/LAU-001-R1-20260917-151900-qualified/README.md).

`experiments/modal_muller_research/` and `solvers/` are **read-only imports**.
`adapters.py` is the only module that touches them, and it imports library
modules only — never `run_*`, `plot_*` or `probe`. Those files are hash-pinned
by 11 recorded bundles and nothing here modifies them.

```bash
cd /home/drdeng/Neural_SDF_BEM_AD
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python

$PY -m pytest -q experiments/laurent_compression experiments/modal_muller_research  # 66 tests
$PY -m experiments.laurent_compression.run_screen --output <dir> --stage pilot --dry-run
$PY -m experiments.laurent_compression.run_screen --output <fresh-dir> --stage campaign
$PY -m experiments.laurent_compression.audit_bundle <fresh-dir>
```

The campaign is deterministic (no random masks). Existing output directories
are rejected. The original 31-second run did not execute all the planned gates;
its runtime is not the runtime of the repaired campaign.

The current screen qualifies receiver fields and all six physical directional
derivatives against independently refined nodal Kress. Its derivative oracle
uses nodal reciprocal traces, checked against centered Kress reassembly. Native
finite differences check all six directions at ka=2 per fixture, at three step
sizes. The objective gate participates in every acceptance decision. Residuals
use fixed oracle flux coordinates `(u, J*d_n u)`.

Refinement changes K and B separately and reports both fixed-fraction and
fixed-entry budgets. An asymmetric star, new transmitter coordinates, and the
two planned geometry offsets test generalization. The continuous Hadamard
expression on compressed traces is reported separately from the discrete
frozen-mask tangent. Every comparison links its six directional records and
saved mask through explicit IDs and hashes; `audit_bundle` checks those links
and recomputes all acceptance predicates from the stored errors.

| Module | Owns |
|---|---|
| `adapters.py` | The exact identity/log-symbol/smooth split by linearity of `kernel_matrix`; analytic `D_v A` and `D_v b, D_v C`; the frozen-mask solve and tangent; an independent modal-to-nodal lift; the Kress oracle. Perturbed geometries keep the base centre and scale so the acquisition cache stays valid |
| `structure.py` | Gate G1b: predicted versus measured argument support, and the `(d, p*, log_order)` formula behind it |
| `masks.py` | `FULL`, `BAND`, `FORWARD`, `DERIVATIVE_AWARE`, `ANALYTIC_SUPPORT`; per-block allocation, deterministic ties, retention and derivative-support-union accounting |
| `metrics.py` | Frozen gates, common acceptance predicate, flux residual, cancellation-aware objective gate, and resource reservations before operations |
| `evaluation.py` | Independent Kress qualification, native qualification, physical versus compression-only derivative errors, and common assessment for all arms |
| `run_screen.py` | Qualification, retention sweeps, independent resolution axes, finite differences, held-out checks, source pinning and checkpoints |
| `audit_bundle.py` | Read-back checks of predicates, comparison/direction links, masks, budgets and numerical source hashes |
| `test_algebra.py` · `test_derivatives.py` · `test_screen.py` | Algebra/derivative tests and regressions for independent references, objective gating, flux scaling, fixed entry budgets and overwrite protection |

Two bugs found and fixed during execution, both in this package and both worth
knowing if it is extended: a synthetic truth that was symmetry-orthogonal to
every training direction (zero objective gradient), and a finite difference that
held `b` and `C` fixed while the tangent differentiated them (so it compared two
different models). Both are covered by tests now.
