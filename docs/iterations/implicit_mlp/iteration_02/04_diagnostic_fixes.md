# Repairs from the completed diagnostic suite

Historical repair record. The short and long acquisition inverses subsequently
completed; their final outcomes open [iteration 3](../iteration_03/01_results.md).
The [short acquisition review](05_acquisition_review.md) records why the longer
experiment was selected. Commands below describe completed work, not a new run.

Recorded 2026-09-08. Source: `iteration-02-suite-20260908T163753015880Z`.
The suite ran diagnostics, not inverse comparisons. These repairs precede the
paired-8/multistatic-8 inverse comparison and apply equally to both arms.

## What was fixed

1. **Motion measurement had a polygon sampling bias.** Comparing smooth normal
   velocities with intersections against polygon chords created an error
   proportional to step size, falsely failing every IFT convergence check.
   Raw motion now solves the candidate field's zero along fixed reference
   normals. Method-B motion intersects its smooth Fourier interpolant. Independent
   extracted polygon motion remains recorded. The convergence threshold is
   unchanged, and failed/nontransverse roots remain explicit.

   All 12 tested raw data/total/Eikonal directions at circle55/60 and star32/47
   now pass the unchanged convergence criterion. At star47, the total-gradient
   10 µm motion error falls from 1.014 µm to 0.006585 µm. At star32, Method-B
   motion error falls from 1.382 µm to 0.004332 µm; both corrected errors scale
   quadratically. These are measurement fixes, not changes to the Kress adjoint.
   [Raw evidence](../../../../results/validation/implicit_mlp_adjoint/iteration-02-diagnostic-fixes/field-root-recheck.json)
   and [Method-B evidence](../../../../results/validation/implicit_mlp_adjoint/iteration-02-diagnostic-fixes/smooth-method-b-recheck.json).

2. **The late-star conversion audit was sensitive to sample count.** New matched
   inverse arms use an explicit audit grid of at least 513 and 1,024 base audit
   samples (2,048 refined), preserving the saved production geometry map and
   both limits: 0.2 mm distance and 0.01 mm refinement change.

   | Frozen star47 geometry | 512-sample refinement change | 1,024-sample refinement change |
   |---|---:|---:|
   | Accepted base state | 9.983 µm, pass | 0.357 µm, pass |
   | Same fresh data-descent candidate | 16.757 µm, reject | 0.127 µm, pass |

   Candidate conversion distance is approximately 148.8 µm in both audits,
   below the unchanged 200 µm limit. This establishes an audit-resolution issue;
   it does not establish that the candidate would pass Armijo or recover geometry.
   [Geometry-only replay](../../../../results/validation/implicit_mlp_adjoint/iteration-02-post-diagnostic-repairs/conversion-audit-replay.json).

3. **Post-inverse reporting would crash on the first transition.** A local
   dictionary overwrote the captured correspondence function. The reporter now
   uses separate names and the corrected smooth-motion measurements. It restores
   accepted weights on diagnostic failure, preserves both completed inverse
   results, records failed evaluation/geometry diagnostics, and reports incomplete
   postprocessing with exit 2. The one-command runner saves its console output
   and traceback in `run.log` and `failure.json`.

4. **Star target scores silently lacked usable correspondence.** Some reference
   normal lines miss the target entirely. Strict normal-line scores remain
   unavailable in that case. A separately labelled nearest-target squared-distance
   directional score now measures whether a proposed normal motion reduces that
   distance; it never constructs or selects the training direction.

5. **Ellipse qualification needed more projected samples, but its initialization
   remains invalid.** At bandwidth 96, 512 projected samples stabilize refinement
   (89 µm becomes 4.74 µm), but conversion distance remains 0.5085 mm. The raw
   contour is 43.5 mm from the prescribed initial ellipse, with perimeter 0.5647 m
   versus 0.3539 m. Increasing integration density does not repair this mismatch.
   The startup report now records these quantities, exact source-checkpoint hash,
   and numerical rejection metrics. No tolerance was relaxed, no fresh pretraining
   substituted, and ellipse remains excluded from the inverse comparison.
   [Ellipse evidence](../../../../results/validation/implicit_mlp_adjoint/iteration-02-implementation/ellipse-failure-mechanism/README.md).

## What remains a research question

Curve-space finite differences are resolved. Curve GN lowers data loss, and on
the circle its signed target alignment is stronger than steepest descent.
This is not yet evidence that a neural GN optimizer is the best next repair.

Field repair improves the state32 gradient spread only from 4.054 to 3.954;
state47 worsens from 11.528 to 11.718 while the contour moves by up to 140.9 µm.
These runs do not support promoting contour-aware Eikonal sampling. The next
comparison therefore retains the uniform-box penalty and tests acquisition alone.
Higher-band, sampling and long-run promotion remain unsupported by current results.

## Validation and next command

189 regression tests passed in 7.24 s. A subsequent matched-runner regression
adds explicit recovery after a failed evaluation, bringing coverage to 190
distinct tests. Bounded saved-state checks used no BEM solves or inverse updates.
The costly inverse runs have been left to the user.

Copy this command only (not Markdown fence markers):

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python /home/drdeng/Neural_SDF_BEM_AD/run_implicit_mlp_iteration2_matched.py --action all --comparison acquisition
```

This qualifies the updated numerical path and then runs **both actual star
inverse arms**, paired-8 and multistatic-8, from identical saved weights and
fresh Adam state. Each is capped at five accepted updates, 120 attempted
candidates, or 600 inverse seconds. Evaluation and geometric reporting follow
both saved trajectories. A fresh timestamped result directory is created
automatically; no diagnostic-suite rerun is needed for this command.
