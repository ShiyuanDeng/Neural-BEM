# SC-048: compact global-motion directions

[Frozen plan](../../../../docs/iterations/shape_frequency_continuation/iteration_27/03_plan.md).
Owner: Codex; no independent reviewer. This is a bounded development comparison
after SC-047's completed coupled and topology screens. Read `summary.json` for
the original decision and [TABLES.md](TABLES.md) for the rebuilt endpoint table.

**Primary gate failed; transfer runs withheld.** M5 / M9 / enriched worst-object
RMS is 0.705 / 2.72 / 3.58 mm, with 152 / 152 / 168 work units. All three
complete the six-dispatch schedule and pass field refinement. The enriched
complete-trial derivative qualifies, but useful finite progress does not
follow. [Iteration 28](../../../../docs/iterations/shape_frequency_continuation/iteration_28/01_results.md)
records the interpretation. No retuning or production promotion follows.

The experiment tests M5 local normal updates enriched with exact translations,
rotation and dilation against unchanged M5 and M9 controls. It keeps the
shared LM backend, data, relative objective, physical step bound, refined
acceptance and work accounting. The enrichment wrapper is local to this
evidence bundle; no production update default changes.

Added physical normal velocities are orthogonalized against the original
space. A pre-dispatch 5% residual cutoff excludes nearly redundant motions;
the original normal columns remain exactly unchanged. A finite trial applies
the existing projected shape update followed by an exact similarity transform.
The complete-trial derivative is qualified before fitting. Parameter count is
reported, but a lower count is not by itself a computational speed claim.

All arms jointly refine both objects. The primary close pair includes fixed
intrinsic shape perturbations beyond the original SC-047 similarity errors:
the ellipse's negative first coefficient is multiplied by 1.12, and the C
receives declared 1.5/1.0 mm normal-mode displacements. The starting component
count, shape family, approximate location and contrast remain known.

The primary comparison permits six one-iteration dispatches, at most 200
forward/reciprocal units and 900 seconds per arm, including an endpoint reserve.
Actual costs remain visible even when the ceilings agree. Qualification has
its own 200-forward/600-second cap. SC-047 and SC-048 scores are not paired
strategy comparisons: the starting shapes and schedules differ.

Only a passing primary gate admits the predeclared three transfer scenarios.
A failed primary gate stops the study without threshold, schedule or input
retuning. No endpoint is selected using truth. Unscored states are saved
before geometry scoring. Noise and untouched-shape generalization require
their own evidence even if this primary screen succeeds.

Rebuild tables, figures and receipt checks from saved outputs:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/shape_continuation/SC-048-global-motion-directions/report.py
```

For a fresh numerical run, copy `run.py`, `global_update.py` and `report.py`
into a new sibling results directory, retaining the committed SC-047 bundle
and repository sources. Execute `run.py` with the same environment. Its
relative import locates SC-047's fixed drivers; the new directory preserves
canonical outcomes. It refuses to overwrite an existing summary. The frozen
manifest hashes numerical dependencies and the plan; closeout checks record
input hashes separately. No ignored NPZ files are required.
