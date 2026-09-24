# SC-019 — step halving on ellipse-to-star

The user authorized this diagnostic after SC-018 exposed recovery failures.
The primary comparison changes exactly one setting: `FitConfig.backtracks`
from 0 to 6 in the new fixed-policy arm. Six halvings allow step sizes
1, 1/2, ..., 1/64 inside each existing harmonic-filter level. This matches
that part of the previous inverse's search budget; LM damping, its curvature
prior and cumulative-frequency fitting are not added in this experiment.

Inputs are copied byte-for-byte from SC-018 ellipse-to-star. Both arms use
its fixed policy, update-band rule, geometry resolution, 50 updates per
frequency decision, terminal progress guard and 6000-solve/600-second caps.
Truth/holdouts only enter endpoint scoring. The control must reproduce the
SC-018 endpoint coefficients and solve count exactly. Numerical source and
input hashes are checked, and this diagnostic script is separately hashed.
All stage histories, accepted states and rejected trials are retained.

A separate post-run probe repeats both searches at exactly the control's
first stalled geometry. This distinguishes the immediate effect of adding
step lengths from subsequent trajectory differences. Its work is recorded
separately and excluded from inverse-arm costs.

Scoring uses the unchanged SC-018 evaluator and recovery gates. The old
Cartesian result is linked as context, not rerun for timing. Runs execute
sequentially; elapsed times include checkpoint writing. Neither existing
optimizer code nor default settings change.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
SCRIPT=results/validation/shape_continuation/SC-019-step-halving/run.py
$PY "$SCRIPT" --output FRESH_OUTPUT --prepare --arm control
$PY "$SCRIPT" --output FRESH_OUTPUT --arm halving
$PY "$SCRIPT" --output FRESH_OUTPUT --probe --report
```

## Exploratory curvature follow-up

After the primary comparison, an evaluation-only audit found that the exact
star has 8.07025% of its curvature energy above band 20. The inherited 1%
gate therefore excludes the target. The audit agrees after refitting the truth
in arclength (8.07025%); even band 26 leaves 4.51470% above the cutoff.

This motivated two additional arms using the **existing FitConfig default**
curvature-tail tolerance 0.1, paired with 0 or 6 halvings. Each contrasts with
its corresponding original-gate arm in exactly one setting. This is an
exploratory, target-diagnosed follow-up, not a preregistered gate selection or
a claim that 10% is universally appropriate. Damping and cumulative-frequency
objectives remain unchanged so they cannot explain any improvement here.

`curvature_followup.py` records its own source/config/input manifest for each
arm. All original evidence is retained. Reproduce after the primary runs:

```bash
$PY results/validation/shape_continuation/SC-019-step-halving/curvature_followup.py \
  --output FRESH_OUTPUT --backtracks 0
$PY results/validation/shape_continuation/SC-019-step-halving/curvature_followup.py \
  --output FRESH_OUTPUT --backtracks 6
```
