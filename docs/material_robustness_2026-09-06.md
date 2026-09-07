# Bounded explicit shape/material robustness

Date: 2026-09-06. This is the practical robustness branch approved after the
[E/H1/F/D follow-up](sdf_kress_followup_2026-09-06.md). It adds a separate,
opt-in orchestration layer; historical D results and production defaults are
unchanged. Unequal materials on separate objects, topology changes, learned
priors, and 3-D are outside this branch.
The physics remains homogeneous full-space 2-D TMz transmission with
positive lossless nonmagnetic materials and known source calibration.

## Verdict and measured outcome

Keep bounded multistart as a useful **opt-in explicit-curve workflow**. It
recovered all five declared difficult-start cases; continuation alone did
not resolve the historical circle failures. This improves the practical
inverse without adding SDF machinery. It is not a proof of global robustness
and does not justify replacing established defaults from five synthetic
cases.

The fresh [result bundle](../results/material_robustness/bounded-20260906/README.md)
contains all 15 workflows, including the eight failed recoveries:

| Policy | Physical recovery | Selected-state stationarity | Forward attempts | Analytic-direction attempts | Workflow time |
|---|---:|---:|---:|---:|---:|
| Full-band local control | 0/5 | 0/5 | 450 | 2,276 | 111.68 s |
| Low-to-high continuation | 2/5 | 2/5 | 329 | 1,333 | 67.11 s |
| Contrast-stratified multistart continuation | 5/5 | 5/5 | 424 | 1,659 | 82.03 s |

These costs are totals over each policy's five workflows, not per-workflow
caps. The policy comparison is not matched-cost; the lower measured
multistart total than this local control is not a general speedup claim.
Only the combined restart/continuation policy was tested; plain full-band
multistart was not, so the two ingredients' effects are not fully isolated.
All workflows completed their allocated search, none hit a global cap, and
there were no invalid probes or failed forward/direction calls in this batch.
An optimizer completing its search is plainly not the same as recovering
the object.

Multistart recovers both clean targets to numerical precision at the tested
resolutions and the fixed circle's interior permittivity 3 from the failed
initial value 9. The noisy results are more practically informative:

- Circle: symmetric geometry error **64.89 µm**, interior `epsr=3.0000483`,
  absolute material error `4.83e-5`, and shifted-angle clean holdout relative
  field error `0.003488`.
- Noncircular target: symmetric geometry error **51.05 µm**, interior
  `epsr=8.4019470`, absolute material error `0.001947`, and shifted-angle clean
  holdout relative field error `0.006427`.

Both are below the frozen 200 µm geometry, 0.1 material, and 0.02 noisy-fit
holdout gates, and both pass the separate stationarity test. Noisy circle
accuracy reproduces the useful basin reached by historical D's easier
starts; the new contribution is reaching that basin from its difficult
high-material start.

Continuation's two successes are the new noncircular target, clean and
noisy. Its circle joint fits remain at interior `epsr≈7.584`, with about
21.7 mm geometry error; the full-band joint circle control remains near
`epsr≈4.12`, with about 41.4 mm geometry error. Fixed-circle full-band and
continuation both finish near `epsr≈10.143`, with clean holdout error about
1.247. These are not resolution failures: all selected candidates pass
N128→256 field refinement, with maximum change `5.55e-13`. Nor are these
eight failures certified stationary at the declared `1e-7` tolerance;
small-step/optimizer stopping is not silently promoted to convergence.

The end-to-end batch took **283.71 s**: 260.81 s of workflow work, 18.35 s
of qualification, 1.32 s of observation preparation, and other manifest/
checkpoint overhead. Workflow totals are 1,203 forward and 5,268 analytic
direction attempts. Qualification adds 180 forward solves; independent new
Nyström observations add eight frequency solves; historical circle
observation generation adds zero. Observation/acquisition hashes and the
sealed selection checkpoint are unchanged; no recorded source changed
during measurement.

The next physics extension I recommend is **different materials on a fixed
number of separated explicit loops**, starting with a two-cylinder forward
oracle and derivative checks before inversion. It needs region-indexed
material ownership and cross-object operator validation, not a true SDF.
Nested regions, object-count discovery, and 3-D require additional design
decisions. Broader starting distributions and repeated-noise/acquisition
studies remain necessary before stronger robustness or uncertainty claims.

## Implementation and selection contract

[`robust_material_inverse.py`](../solvers/sdf_inverse/robust_material_inverse.py)
reuses the explicit radial-K2 curve, six scaled real parameters, physical
bounds, immutable observations, and analytic Kress residual derivatives from
D/E. It adds three policies: full-band local fitting, cumulative low-to-high
frequency continuation, and deterministic multistart continuation.

No SDF is queried, trained, or extracted. The code addresses starting basins
of the same physical inverse problem, not a representation error. The API
accepts training data only: there are no target-geometry or held-out-data
arguments.

Every workflow first evaluates the initial candidate on the full training
band, providing a valid fallback if later search exhausts its budget. The
multistart candidates are the initial state, its geometry with material at
the bounds' first and third quartiles (3.9 and 9.3), and, for joint shape
fitting, the box-midpoint circle with each quartile material. Fixed-shape
search never substitutes another geometry.

Low-band screening retains two branches: the lowest-score available start
on each side of the known exterior permittivity, then any remaining slots
by low-band score. This prevents a low-frequency ambiguity from discarding
an entire material-contrast sign. These are bound/background-derived starts,
not guesses obtained from target or held-out errors.

The delivered candidate has the smallest **common full-band training
objective** among valid full-band evaluations. A valid best-seen trial is
retained even if its optimizer later fails; a low-only candidate is never
eligible. A worse stationary branch cannot replace a better-scoring branch.
Each frequency retains its original immutable normalization and complex
source strength; the final objective retains original column order.

Global caps count frequency-level forward and analytic-direction attempts,
including screening, unsuccessful work, ranking, and the final selected-state
stationarity audit. This audit is separate from optimizer stop flags but
uses the same analytic E derivative, not an independent derivative oracle.
It reuses the selected candidate's already-paid
forward state. There is no uncounted re-solve at an exhausted forward cap.
Reports distinguish allocated search completion, budget exhaustion,
projected-gradient stationarity, and post-selection physical recovery.
Near-bound distances/flags are independent of SciPy's active-mask heuristic.
Neither small projected gradient nor optimizer success establishes recovery.

## Frozen comparison protocol

[`run_material_robustness_comparison.py`](../run_material_robustness_comparison.py)
declares 15 workflows before measurement:

- Circle and noncircular targets, each with clean and 1% complex-noisy data,
  each with the three policies: 12 joint-shape workflows.
- The historical fixed circle, clean data, high-permittivity initial state,
  with the same three policies: three fixed-shape workflows.

The historical circle observations, noise, acquisitions, complex source
strengths, and high-material starts are loaded verbatim from frozen D NPZ
and manifest files and hash-checked. No Mie observations are regenerated.
The joint initial state is `[0.043, 0.505, 0.495, -0.002, 0.001, 9]`; the
fixed-circle initial state is `[0.05, 0.5, 0.5, 0, 0, 9]`, in SI geometry
units and relative permittivity.

The new noncircular target is fixed before measurement at
`[0.052, 0.503, 0.497, 0.0025, -0.0015, 8.4]`. Its material lies above the
background value 6, whereas the historical circle has material 3. Its
observations use separately implemented native-curve Nyström kernels, with
N128/256/512/1024 refinement and a `1e-8` self-convergence gate, not the
candidate Kress solver. These are independent implementations in the same
Müller/Nyström mathematical family, not an unrelated physical formulation.
New complex-noise seeds are 4306 (training) and 4316 (holdout).

The optimization uses N64, with 40 evaluations per continuation stage and
80 for the full-band local control. Each multistart workflow retains two
branches, each with the 40/40 stage allocation. Every workflow shares caps
of 400 frequency-level forward attempts and 2,400 analytic-direction
attempts. Actual work differs: this is a bounded recovery comparison, **not
a matched-cost speedup experiment**.

All 15 training-only selections and their parameter hashes are sealed
before any selected-candidate geometry/holdout qualification. Qualification
cannot restart or select a candidate. It replays the selected training
objective at N64, audits N64/128/256 field refinement, and uses predeclared
physical gates: 200 µm symmetric geometry error, 2 µm geometry-refinement
agreement, 0.1 absolute material error, clean holdout relative error `1e-4`
(or 0.02 for noisy fits), and `1e-5` field self-convergence. Stationarity is
reported separately at scaled projected-gradient infinity norm `1e-7`.

No bounds, seeds, budgets, gates, or rankings are tuned after this batch's
outcomes. Single synthetic targets and one noisy realization per target do
not support global convergence, broad identifiability, or uncertainty claims.

## Reproduction

Use a fresh output directory; an existing directory is rejected:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  run_material_robustness_comparison.py \
  --output results/material_robustness/bounded-20260906
```

The bundle separates workflow, observation-generation, and qualification
costs; preserves failed branches and intermediate candidates; stores strict
JSON, CSV, and non-pickled numeric NPZ; and records source/input hashes and
the unchanged sealed selection checkpoint.

## Post-run safety repair and validation

A read-only peer review during measurement identified an extreme-amplitude
edge: finite residual entries can still overflow their squared scalar loss.
The source stayed frozen until the batch finished. Afterwards the opt-in
wrapper was hardened to reject nonfinite objectives before best-candidate
selection, retain a valid previously paid candidate, and record a null loss
with an explicit failure reason rather than non-JSON infinity. It does not
mislabel a successful forward call as a failed solve.

Two adversarial toy regressions cover both a retained finite incumbent and
the absence of any finite initial candidate, including exact work accounting
and strict JSON. This post-run guard does not change normal finite-objective
arithmetic, seeds, optimizer settings, bounds, or ranking. The measured
bundle retains its original source hashes; it was not rerun or relabelled
as a measurement of the later guarded source.

The final combined regression, after the guard, passed **561 tests**, with
276 existing warnings in **110.59 s**. It covers ordered boundaries,
SDF-to-curve conversion, Kress derivatives/forward assembly, multi-component
seams/oracles, all inverse tests, and the parameterization, distance,
derivative, material, and robustness driver contracts. The exact command is
in the [validation log](validation_change_log.md). An independent saved-array
audit recomputed candidate rankings, normalization replay, physical gates,
work/phase totals and frozen hashes without rerunning a solver.
All 2,303 saved NPZ arrays are numeric and finite with `allow_pickle=False`;
all four JSON files pass strict parsing. `git diff --check` passes.
