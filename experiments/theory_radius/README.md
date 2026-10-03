# Fixed-chart theory diagnostics

TR-001–003 implement the first three experiments approved after the
[October 3 theory review](../../docs/theory_directions_cartesian_fourier_2026-10-03.md).
The [frozen plan](../../docs/iterations/theory_radius/iteration_01/03_plan.md)
owns cases, coordinates, gates and budgets. These are campaign diagnostics;
the maintained inverse in `solvers/bem_inverse/` does not import this package.

Use the existing EMNerf environment from the repository root:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
tr_python=/home/drdeng/miniconda3/envs/EMNerf/bin/python
"$tr_python" -m pytest experiments/theory_radius pytest/bem_inverse -q
"$tr_python" -m experiments.theory_radius.atlas
"$tr_python" -m experiments.theory_radius.report TR-001
# Validate, commit and push before the next experiment.
"$tr_python" -m experiments.theory_radius.handoffs
"$tr_python" -m experiments.theory_radius.report TR-002
"$tr_python" -m experiments.theory_radius.folds
"$tr_python" -m experiments.theory_radius.report TR-003
```

The default output is `results/validation/theory_radius/`. Numerical commands
refuse existing experiment directories. Reports rebuild from saved measurements
without new solves and check source/input seals. Preserve existing evidence;
reproduction requires the archived source and a new output root (set `common.OUTPUT`
in the isolated reproduction process before invoking `common.execute`). No Git
branch or worktree is needed.

`common.py` provides fixed Cartesian charts, physical RMS scaling, real residual
normalization and thin wrappers over existing nodal physics. `atlas.py` measures
sampled local Jacobian variation. `handoffs.py` audits chart applicability and
truncation on saved trajectories. `folds.py` measures full objective curvature
and tracks a bounded stationary data-homotopy branch. `report.py` rebuilds the
tables and radius plot; `test_diagnostics.py` contains independent checks.

The radius is empirical: a finite sample does not bound the Lipschitz supremum.
Truth-centred radii and retrospective handoff indicators are not online inverse
controls. The stationary branch uses a fixed chart and a data homotopy, so it
does not reproduce the production moving-chart frequency ladder. Source seals,
refusals, numerical gates, work counts and timing limits accompany each result.

The actual TR-003 execution retained its first stage-entry adapter failure and
continued only the two branches with `python -m experiments.theory_radius.resume_branches`.
The resumed numerical work completed, but a concurrent edit to the unused
FM-003 reporting module triggered the broad final source guard. The explicit
`python -m experiments.theory_radius.closeout` review qualifies that completed
evidence while preserving the original failed guard. It checks all numerical
source/input hashes, the exact named nondependency exception, retained endpoint
hashes, branch completeness and combined budgets. Its report is
`TR-003-branches/QUALIFIED_REPORT.md`; the original manifest and failure are not
rewritten. `interpret.py` separately distinguishes TR-001 radius probes above
and below their recorded origin-refinement floor.
