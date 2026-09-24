# SC-018 comparison protocol

[Completed results and interpretation](../../../../docs/iterations/shape_frequency_continuation/iteration_05/01_results.md).

Requested 2026-09-23: test the new implementations on the previous explicit
Fourier single-object cases before making improvement claims. The user selected
single-object comparisons first; topology and unknown-material inversion are
outside this campaign.

## Cases and data

The matrix uses all six target/initial-shape combinations exposed by
`run_explicit_cartesian_fourier_inverse.py`: circle and five-lobed-star targets,
each initialized with the old circle, ellipse or star. These are existing
fixtures, not six previously saved successful campaigns. The historical anchor
is `cartesian-k6-ellipse-to-star-nystrom-kress-20260910`.

Every arm reads exactly the same per-case `inputs/*/input.json`, with its hash
recorded. Observations are prepared once from the old independent circle Mie
series or star Nyström oracle, with the latter's refinement check required to
pass 1e-7. The original target placements, material contrast 3/6, 24 paired
point-source/receiver positions, source strength 1e-6, and the explicit
Cartesian driver's training frequencies 0.5/1.5/2.5 GHz are retained. Unused
0.25/1/2 GHz observations are held out for scoring. No full multistatic matrix
or extra frequency is exposed to any new inverse.

The old Cartesian K6 initialization is constructed once and its exact
coefficients are shared by every arm. The new solver uses an explicit change
of units: x'=(x-(0.5,0.5))/0.05 and k'=0.05 k. The 2D line-source Green
function and measured fields retain their amplitudes under this conversion.
The new solver's subsequent arclength refit remains part of its algorithm;
its projection tolerance is unchanged.

## Arms, stopping and cost

- `legacy_cartesian`: existing Cartesian K6 polar-angle inverse, finite-
  difference LM, cumulative-frequency continuation, 150 accepted-update cap
  with the original stage allocation and 2-mm modal step limit. No neural fit.
- `fixed`: new GN/SD inverse with prescribed shape band and all three stages.
- `band`: the same measured frequencies with atlas-selected shape band.
- `frequency`: prescribed band with probe-selected frequency.
- `full`: measured frequency and shape band.

The new arms use the same settings: 50 optimizer iterations per decision,
filter-only GN/SD search, curvature-tail energy 0.01, minimum curve storage
band 128 to resolve the inherited non-circular initial states, and at most
12 decisions. Terminal refinement stops on the optimizer's data/small-step/
stationarity/search stop or less than 1e-4 relative improvement over a full
chunk. This shared guard prevents SC-017's endless acceptance of negligible
terminal steps; it is a declared change, not a claim to replay SC-017 exactly.

On this sparse frequency catalog, a preferred jump may contain no available
measurement. All new policies then advance to the next supplied frequency;
they do not declare completion or generate intermediate data. This means the
catalog can leave the frequency-only policy little or no choice.

Each arm has caps of 6000 **single-frequency** forward solves and 600 seconds.
A legacy objective evaluation at three frequencies costs three, not one.
New probes and failed forward attempts are charged. Preparation and final
evaluation are excluded for every arm. Different quadrature sizes, Jacobian
methods, and stage objectives remain intentional algorithm differences; equal
forward counts do not imply equal FLOPs. Four single-thread workers may overlap,
so elapsed times are descriptive rather than controlled speed measurements.

## Scoring and qualification

Every endpoint is scored using the same refined forward evaluator and same
independent observations. All six frequencies receive an N/2N check. Geometry
metrics are symmetric sampled Hausdorff distance, its conservative continuous-
curve upper bound, and normalized symmetric-difference area. Unlike the old
node-to-exact-target maximum, this boundary score is symmetric and does not
depend on the optimizer's node count.

Recovery gates are frozen before the full run: boundary upper bound <=1 mm,
training relative L2 <=0.003, worst held-out relative L2 <=0.05, endpoint
field refinement <=1e-6, and no unhandled algorithm failure. The table also
reports raw errors, so these deliberately practical gates cannot be mistaken
for matching the old nanometre-scale star result.

Validation before the campaign: all **104** continuation-package tests passed,
including independent Mie/Nyström bridge checks, finite differences with a
complex line-source strength, paired/full consistency and cache invalidation.
Six 12-forward budget smoke runs returned scoreable endpoints for the old and
new fixed inverses from circle, ellipse and star starts. Their scratch output
is `/tmp/sc018-smoke02-20260923`; the full evidence is this directory.

After the campaign, 114 existing Kress/ordered-boundary tests also passed.
`audit_bridge.py` repeats the independent-oracle comparison at all six
frequencies and directional derivative checks at each start/training frequency;
its 21 records are in `bridge_audit.json`. Worst discrepancies are 3.86e-10
and 6.08e-9 respectively. `verification.json` records run completeness,
source/input hash agreement, endpoint resolution and pass counts.

## Reproduce

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH=solvers:.
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m pytest -q experiments/shape_continuation
$PY -m experiments.shape_continuation.legacy_cases --output FRESH_OUTPUT \
  --prepare --run --max-forwards 6000 --max-seconds 600 --workers 4
# Regenerate the table/overlays without physics:
$PY -m experiments.shape_continuation.legacy_cases --output FRESH_OUTPUT --report
```

Inputs, checkpoints, probe decisions and endpoints use portable JSON. Numerical
source hashes are frozen at preparation and checked before each arm. Every
failure, incomplete process and budget stop must remain visible in the report.
