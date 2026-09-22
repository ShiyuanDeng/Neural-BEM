# SC-012 — User-run paper glider through k=2

The user ran the bounded command on 2026-09-22 at source
`b158cc627f4a7747174ea8958f336a95b56dea91`. The full output from
`/tmp/paper-glider-033-k2` is preserved byte-for-byte in [run/](run/).
All 41 numerical source hashes still matched when inspected. No additional
forward or inverse solves were launched during this analysis.

**The frequency ladder completed; the shape recovery did not converge.**
`ladder_completed` means that all requested frequencies were visited and passed
the field/Jacobian qualification. It does not assert a fit at every frequency.

- Elapsed: **16.4194 s**; shared work: **231 forwards, 71 Jacobians**, no failed
  forward solves. Budget was 300 forwards / 120 seconds for data, inverse and
  resolution checks together.
- All five observation checks and five field/full-Jacobian stage checks pass.
- 59 updates were accepted, including 50 at the first frequency.
- Final relative data residual: **0.0120846** (1.208%); requested tolerance:
  `1e-5`. Final relative symmetric-area error: **0.157368** (15.737%).

| k | Accepted updates | Stop reason | Data residual | Area error |
|---|---:|---|---:|---:|
| 1 | 50 | iteration_limit | 0.026865 | 0.250498 |
| 1.25 | 4 | small_step | 0.003164 | 0.158115 |
| 1.5 | 5 | small_step | 0.004128 | 0.157368 |
| 1.75 | 0 | no_acceptable_step | 0.007132 | 0.157368 |
| 2 | 0 | no_acceptable_step | 0.012085 | 0.157368 |

Residuals at different frequencies are different objectives. The last two
stages retain the previous physical shape, with zero-padded storage. The tiny
change in the printed area score at k=2 comes from scoring at 16384 instead of
8192 polygon vertices, not an accepted geometric update.

![Saved reconstruction and stage errors](reconstruction.png)

## What the rejected trials show

At k=1.75, the unfiltered GN trial has curvature-tail fraction 0.1615, above
the assumed 0.1 limit. The raw SD trial is admissible but increases the residual
from 0.00713 to 0.00943. Weakly filtered GN candidates still fail the curvature
gate. Stronger filters make them admissible but nondecreasing in residual.

At k=2, both raw candidates fail the curvature gate. The admissible filtered
candidates again fail to decrease the residual. Once only the constant
Cartesian displacement remains, filter levels 4 through 10 repeat the same
trial geometry/residual in this saved run. This explains wasted evaluations
within the filter-only search; it does not establish that no feasible descent
direction exists. The profile has `backtracks=0`, as declared in the paper audit.

The field/Jacobian refinement checks make underresolved quadrature unlikely
to explain these stops. They do not certify global convergence or establish
which regularization/search changes will help. A useful next diagnostic is a
single-update comparison from a stalled checkpoint with step halving enabled,
keeping observations, shape, modes and curvature threshold fixed. That
comparison has **not** been run here. No solver/defaults were changed.

## Reproduce the analysis without inversion

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONPATH=solvers:. MPLCONFIGDIR=/tmp/shape-continuation-mpl \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/shape_continuation/SC-012-paper-glider-k2/analyze.py
```

The script audits saved states, accepted residual decreases and qualification
records; writes [analysis.json](analysis.json); and plots existing coefficients.
It reports differences if run against changed source files.

Original inverse command (recorded for provenance, not rerun during analysis):

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  -m experiments.shape_continuation.paper --mode run --contrast 0.33 --k-stop 2 \
  --max-forwards 300 --max-seconds 120 --output /tmp/paper-glider-033-k2
```
