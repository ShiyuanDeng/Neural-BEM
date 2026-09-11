# Cartesian Fourier pipeline audit — 2026-09-10

Audited commit `e34ed5f` and applied corrections in the working tree. The
Cartesian topology implementation exists and remains MLP-free. Fresh numerical
runs complete all five automatic controller cases and qualify all three full
challenge cases. The single-component ellipse-to-star study also completes.

## Corrections

- **Gauge convergence:** zero Fourier truncation could falsely certify a
  phase-shifted circle whose coefficients were outside the optimizer's gauge
  subspace. Convergence now also bounds the input-to-output displacement at
  the same parameter. Phase and reversed-traversal regressions check the actual
  canonical coefficients.
- **Newton and winding:** retain the best measured Newton parameters when a
  later iterate worsens, and reject contours that make more than one turn
  about their center, including the periodic seam.
- **Feature radius:** a star-shaped curve need not be parameterized by polar
  angle. The previous formula claimed a 58.39-mm lower bound for an ungauged
  ellipse with a 10-mm minor radius. Ungauged curves now use a conservative
  sampled-radius bound with a derivative-based between-sample margin. Canonical
  polar-angle curves retain the radial coefficient-norm certificate.
- **Controller API:** `chart='cartesian'` now converts supplied radial initial
  geometry at the library entry point, rather than relying on the CLI to do so.
- **Contour fidelity:** gauge convergence and the initial projection error did
  not bound cumulative movement during gauge fixing. The final Cartesian
  contour must now also remain close to the source topology-mask contour.
- **Reference scope:** the single-component driver no longer reports parity
  against unrelated saved ellipse-to-star numbers for circle targets or a
  different acquisition/resolution. Unevaluated comparisons are explicitly null.
- **Evidence and navigation:** added a pipeline guide and corrected the main
  indexes, stale descriptions of re-gauging, nonexistent video links in
  numerical-only controller summaries, and nanometre/micrometre unit errors in
  the iteration-3 report. Historical measured JSON and trajectories were not edited.

## Tests and artifact checks

The existing inverse suite passed **505 tests** before edits. The final suite
passed **514 tests** in 71.09 seconds; see [tests.log](tests.log). The nine new
regressions include a physical single-component run with neural construction,
evaluation, extraction, audits and re-distancing forbidden inside the inverse.
The initial analytic level set is still extracted once by its driver.

All fresh controller frames contain Cartesian components and have gauge-subspace
coefficient residual below `2.68e-14`. Accepted trajectories are monotone, and
every topology event passes its production/refined improvement margin. Event
sequences match the previous Cartesian bundle. The three challenge bundles
pass their own full-profile gates, including held-out and geometry checks.
[verification.json](verification.json) records these checks and final source hashes.

Nine historical MP4s have readable video streams and positive durations; see
[media_audit.json](media_audit.json). The saved-trajectory renderer was also run
on the fresh Cartesian death case: [video](controller/death/inversion.mp4),
[visually inspected final frame](controller/death/final.png). Numerical runs
used `--skip-video`; the other fresh cases link their metrics instead.

## Fresh automatic controller results

| Case | Event sequence | Final relative L2 | Sampled Hausdorff (m) |
|---|---|---:|---:|
| [death](controller/death/metrics.json) | death | 1.102537e-06 | 4.057532e-08 |
| [merge](controller/merge/metrics.json) | merge | 7.878761e-05 | 7.241253e-04 |
| [mixed](controller/mixed/metrics.json) | split → death | 4.282593e-07 | 1.419974e-08 |
| [repeated-birth](controller/repeated-birth/metrics.json) | birth → birth → birth | 1.620667e-07 | 9.261685e-09 |
| [split](controller/split/metrics.json) | split | 6.873380e-06 | 1.752108e-04 |

All five stop `recovered`. The corrected final-contour check changes the split
candidate search: its sampled Hausdorff error improves from **295.85 µm to
175.21 µm**, but the radial reference is **15.60 nm**. Thus the shared acceptance
criterion passes while matching geometric accuracy remains unproven on that
case. The event-selection/polishing budgets and recovery tolerances were not tuned.

The old report mislabeled several nanometre values as micrometres. In particular,
its radial split error was 15.60 nm, not 15.60 µm. Correcting the unit increases
the apparent historical Cartesian/radial gap by a factor of 1,000.

## Fresh challenge results

| Case | Outcome | Train relative L2 | Maximum geometry error (m) |
|---|---|---:|---:|
| [far-circle](challenges/far-circle/metrics.json) | full_pass | 1.930632e-07 | 1.082887e-08 |
| [large-split](challenges/large-split/metrics.json) | full_pass | 1.930632e-07 | 1.082887e-08 |
| [ellipse-star](challenges/ellipse-star/metrics.json) | full_pass | 5.677814e-03 | 5.516188e-04 |

The ellipse/star held-out 2.5-GHz relative L2 is `5.245e-02`. Qualification is
against the case's declared tolerances, not a claim of uniformly small error.

## Single-component result and remaining design choices

The [fresh ellipse-to-star run](single-star/summary.md) completes **41 accepted
updates**, with maximum sampled boundary error **2.761e-09 m**, train relative
L2 **1.296e-07**, and holdout relative L2 **1.127e-07**. It stops on
`stable_data_and_geometry`. The geometric parity gate passes; the two `1e-7`
data gates still fail narrowly, as in the original study.

The single-component optimizer still uses full Cartesian coefficient probes
with a phase gauge and one re-gauging operation per step. The topology optimizer
uses a converged gauge and the smaller subspace that preserves it. This audit
preserves that design distinction; it does not claim the topology cost reduction
has been transferred to the single-component driver.

The Cartesian topology policy still requires each component to be star-shaped
in its polar-angle gauge. Its shape family matches the gauge-fixed radial chart
one bandwidth lower. Supporting non-star-shaped components would require a
separate parameterization/optimization design; it was raised with the user and
not silently enabled. Likewise, changing candidate-polishing budgets to close
the split accuracy gap is a separate comparative experiment.

## Reproduction

Use `/home/drdeng/miniconda3/envs/EMNerf/bin/python` in this workspace and set
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
PYTHONPATH=solvers`. Choose fresh output directories.

```bash
python -m pytest -q pytest/sdf_inverse
python run_fourier_topology_controller.py --chart cartesian --profile full --skip-video --output <fresh-controller-directory>
python run_radial_fourier_topology_challenges.py --chart cartesian --profile full --skip-video --output <fresh-challenge-directory>
python run_explicit_cartesian_fourier_inverse.py --target star --initial-shape ellipse --train-ghz 0.5,1.5,2.5 --holdout-ghz 0.25,1.0,2.0 --num-pairs 24 --maximum-mode 6 --outer-iterations 150 --output-dir <fresh-single-directory>
python run_fourier_topology_controller.py --render-only --case death --output <fresh-controller-directory>
```

The two topology jobs and the single-component job ran concurrently, so wall
clock time is not a controlled chart-speed comparison. Physics, observations,
full-profile budgets and gate thresholds were retained.
