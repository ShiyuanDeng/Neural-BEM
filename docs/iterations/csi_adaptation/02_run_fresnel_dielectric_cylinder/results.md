# Measured Fresnel dielectric cylinder

Activity 02 completed on 17 November 2026. All three methods completed
2048 iterations on `dielTM_dec8f`. The detached launcher exited with code 0.
The short explicit interpolation check passed eight cases exactly. No new
upstream patch, scoring edit, solver edit or synthetic inversion was made.

## Reading check

The [reading note](reading.md) compares Figure 5's constraints,
regularization, start, iterations and data with the shipped driver and
`MR_CSI_Brent.m`. Positivity and the common back-propagation start agree;
the paper does not give a complete discrete MR regularization/line-search
parameter list. Antenna/source conventions and the displayed-domain
interpretation differ as recorded in activity 01. They are possible causes,
not demonstrated explanations. The Figure 5 MR-CSI difference stays open.
No setting was changed to reproduce its speckled result.

The explicit old rule uses linear interpolation of an already-refined
array at `1:2:end` in both directions. Against direct sampling, all eight
real/complex, N=17/112 checks gave zero difference and `isequal=true`.
The successful MATLAB check took 2.439 s, below its 60-second limit.
The first harness failed in its result collector after 2.433 s; both
commands/logs remain saved. Reading finished before the inversion began,
within the 30-minute allowance. See the
[successful check](../../../../results/csi/fresnel/2026-11-17_reading_check_repeat/explicit_interpolation.json)
and [failed harness](../../../../results/csi/fresnel/2026-11-17_reading_check/matlab.log).

## Actual run and settings

17 November 2026, 20:22:29 to 21:56:23 UTC; total wall time 5634.383 s
(1 h 33 min 54 s). The command used `setsid nohup` to detach the Python
launcher. It remained a session/group leader with no terminal throughout.
The MATLAB limit was 12600 s, leaving the full 30-minute reading allowance
inside four hours. The estimate saved before running was 10372.907 s
including reading, 20% and setup/export; it was not exceeded.

- Measured `dielTM_dec8f`; TM, eight frequencies 1 through 8 GHz, 36 sources.
- Centre [0,0,0], half-widths 70 mm, 1.25 mm cells: actual grid 112 by 112.
  Primary node coordinates are [-70,68.75] mm in both numerical directions.
- Back-propagation start, 2048 iterations, no added noise, no warm-up and
  early stopping disabled. Each method starts from the same inputs.
- First-opus radii 0.72/0.76 m, source offset -2.5 degrees, receiver indexing,
  data mask, per-source calibration and sign conventions stay as shipped.
- Eight MATLAB compute threads. Existing compatibility patches 0001 and
  0002 from activity 01 are reused, unchanged.

| Method | Native seconds | Seconds/iteration | Reported cost, first to last | Native peak Re chi at 8 GHz |
|---|---:|---:|---|---:|
| MF-CC-CSI | 1963.225 | 0.958606 | 4.0439 to 0.10343 | 2.15589 |
| MF-MR-CSI | 1909.379 | 0.932314 | 4.3813 to 0.065348 | 2.18855 |
| CSI | 1746.849 | 0.852953 | 0.55942 to 0.0079871 | 2.86188 |

All raw contrast arrays are finite. Real contrast agrees exactly across
frequencies for each method. Native reported costs have different
definitions and must not be ranked against one another. MF-CC-CSI has one
printed increase, MR-CSI 1007, CSI none; all end below their initial cost.

Overlap was recorded in [the sample log](../../../../results/csi/fresnel/2026-11-17_diel_tm/overlap.jsonl)
and [summary](../../../../results/csi/fresnel/2026-11-17_diel_tm/overlap_summary.json).
Of 99 in-progress samples, 86 show two MATLAB processes, eight show three,
and five show CSI alone. These are sample counts, not exact time fractions.
The timers are indicative under changing overlap, not isolated table-C
performance measurements. No GPU was used by CSI.

Evidence: [detached command](../../../../results/csi/fresnel/2026-11-17_diel_tm_detached.json),
[launch and exit](../../../../results/csi/fresnel/2026-11-17_diel_tm/launch.json),
[settings/timers](../../../../results/csi/fresnel/2026-11-17_diel_tm/matlab_summary.json),
[analysis](../../../../results/csi/fresnel/2026-11-17_diel_tm/analysis.json),
[cost histories](../../../../results/csi/fresnel/2026-11-17_diel_tm/cost_history.csv),
[raw compact contrasts](../../../../results/csi/fresnel/2026-11-17_diel_tm/final_contrast.mat),
[calibration factors](../../../../results/csi/fresnel/2026-11-17_diel_tm/source_calibration.csv).
The compact export was checked against every full-workspace contrast array
and matches exactly. Neither export applies the native display mask.

## Source truth and score preview

Belkebir and Saillard (2001), *Special section: Testing inversion algorithms
against experimental data*, Inverse Problems 17, 1565-1571,
[DOI](https://doi.org/10.1088/0266-5611/17/6/301),
[author PDF](https://www.fresnel.fr/perso/belkebir/Articles/Ip01Introduction_Belkebir.pdf).
Section 4.2 and Figure 6(a) give radius 15 mm, displacement about 30 mm,
and relative permittivity 3 +/- 0.3; Table 1 identifies this data file.
Nominal true area is 706.858 mm2 and susceptibility is 2 +/- 0.3.
These values came from the actual paper, not recollection.

The drawing shows the cylinder left of its origin without labelled numeric
axes. Before inversion, `reading.md` declared rightward-x/upward-y drawing
coordinates, giving (-30,0) mm in that drawing frame. That frame has **not
been registered** to the exported numerical axes. All three recovered
numerical centroids are instead near (2,26) mm. No rotation, reflection or
translation was fitted to make a score improve. The result exposes the
remaining frame mapping; it does not prove a 41 mm localization failure.
The source specifies the displacement only approximately, so even a
registered centroid comparison would use nominal experimental truth.

The preview imports the frozen protocol-1 `support_rings`, `region` and
`region_scores` functions from `experiments/comparison/scoring.py`. It
linearly resamples unmasked real contrast in physical numerical x/y onto
the shared 201-by-201 +/-100 mm grid, with zero outside the native domain.
Support uses half the largest-magnitude peak with its sign. Every component
and hole is kept. Mean susceptibility is over those thresholded pixels;
the reported relative permittivity adds one. No scoring code was edited.

| Method | Support area, mm2 | Area difference from nominal | Numerical centroid (x,y), mm | Centroid radius, mm | Mean chi | Mean relative permittivity |
|---|---:|---:|---|---:|---:|---:|
| MF-CC-CSI | 736.537 | +4.20% | (1.887,26.351) | 26.419 | 1.72927 | 2.72927 |
| MF-MR-CSI | 715.659 | +1.25% | (1.615,26.282) | 26.332 | 2.01211 | 3.01211 |
| CSI | 566.504 | -19.86% | (1.838,26.530) | 26.593 | 2.28088 | 3.28088 |

These area, size, centroid-coordinate and material summaries are valid
without choosing a frame rotation. The three centroid radii are compared
with the paper's approximately 30 mm offset, not an exact coordinate pair.
All three mean permittivities lie within the quoted 3 +/- 0.3 range. This
is a preview, not a recovery/pass/fail claim. CSI keeps one central hole
at the prescribed half-peak threshold; it was not filled by hand.

| Method | Area at 0.3 / 0.7, mm2 | Mean relative permittivity at 0.3 / 0.7 |
|---|---|---|
| MF-CC-CSI | 823.247 / 540.192 | 2.64132 / 2.87926 |
| MF-MR-CSI | 758.038 / 676.739 | 2.96481 / 3.06095 |
| CSI | 671.128 / 422.981 | 3.09857 / 3.46804 |

All sensitivity centroids and topology counts are in
[score_preview.json](../../../../results/csi/fresnel/2026-11-17_diel_tm/score_preview.json).
Frame-dependent symmetric-difference and centroid-distance values are
explicitly nested as `unregistered_drawing_frame_metrics`; they are not
verified physical errors and must not enter the final comparison table.
The full `score()` API is tied to TG-002 truth/catalog files; its lower-level
support/region functions suffice here, but a Fresnel truth entry and a
verified signed frame mapping are missing for full registered scoring.

Figures: [numerical-coordinate support preview](figures/diel_tm_support_preview.png),
[native display](figures/diel_tm_figure_02.png), and
[costs](figures/2026-11-17_diel_tm_costs.png). The dashed reference in the
preview is explicitly the unregistered paper drawing, not an aligned truth.
The native display swaps numerical matrix dimensions; it was not used to
choose the numerical centroid or to alter the exported arrays.

## Cost model for the next activity: no synthetic runs started

The [model](../../../../results/csi/fresnel/2026-11-17_diel_tm/cost_model.json)
lists all completed native timings so far. Failed starts have no saved
per-method timer, so they cannot supply iteration-rate observations.

| Run | Grid cells | Sources | Frequencies | Components | Iterations | Seconds/iteration CC / MR / CSI |
|---|---:|---:|---:|---:|---:|---|
| Shipped I | 8836 | 36 | 8 | 1 | 16 | 0.589737 / 0.601298 / 0.551709 |
| Shipped II | 17956 | 8 | 5 | 2 | 32 | 2.115727 / 1.668301 / 1.644203 |
| Paper twin | 12100 | 18 | 4 | 1 | 2048 | 0.463044 / 0.410329 / not run |
| Measured cylinder | 12544 | 36 | 8 | 1 | 2048 | 0.958606 / 0.932314 / 0.852953 |

Model: iteration seconds scale with cells times sources times frequencies,
using a method-specific median coefficient from the TM observations. TE
is listed separately because it has two components and a different receiver
union. The factors were not varied independently, so their exponents are
assumed, not identified. Receiver count, sparse factorization, frequency
values, overlap, contrast and line search limit extrapolation.

For ten TG-002 shapes at both relative-permittivity ratios 0.5 and 4,
three methods and 2048 iterations (60 fits), the pooled model predicts
**30.82 native inverse hours** on the current 112-by-112 layout. Directly
matching this measured case's rates gives **31.22 native hours**, or
**31.30 launcher-wall hours** if its setup/export overhead repeats.
These totals exclude forward data generation, whose cost has not been
measured here. They are computational estimates, not a justified campaign
setting or a scientific coverage claim.

Two limits must be settled before that next campaign:

- **Contrast:** TG-002 defines contrast as the squared wavenumber ratio,
  so 0.5 in vacuum is susceptibility -0.5. The unchanged CSI projection
  forbids it. Thirty of the proposed 60 fits cannot represent their truth.
  This activity does not reinterpret the contrast or relax the constraint.
- **Domain:** reading the frozen TG-002 boundaries (no simulations) shows
  eight extend outside +/-70 mm, and all ten intersect the present fixed-zero
  five-cell border. Maximum sampled extent is 96.121 mm. With the same cell
  size and an illustrative six-cell margin, a common half-width 103.75 mm
  gives 166-by-166 cells and covers the sampled raw support. This is only
  a cost scenario, not a selected setting; native TV/display margins may
  warrant more room. See [bounds](../../../../results/csi/fresnel/2026-11-17_diel_tm/tg002_domain_check.json).

That larger-grid scenario multiplies cell work by 2.196747. The pooled
forecast becomes **67.71 hours**; using this case's matched rates gives
**68.58 native inverse hours** for all 60 fits (about 82.30 hours with a
20% compute allowance), plus unmeasured data-generation/setup work.
Sparse-factorization scaling may depart from the assumed linear cell law.
No simulation, inversion or setting choice for those shapes was started.

## Storage, failures and handoff

About 466 MB of complete run outputs remain local, git-ignored: full
workspaces, per-frequency fields and figure workspaces. Compact unmasked
contrasts, costs, native times, logs, preview scores and small metadata are
committed within the 5 MB rule. A manifest records the commands, input and
source hashes, and SHA-256 for local and committed outputs. Already pushed
activity-01 evidence is unchanged. See `manifest.json` and
`storage_check.json` alongside this run.

The only experimental failure was the first short-check result collector;
its log is retained. Main MATLAB exited 0 without a crash. One offline
cost-model path formatting error was corrected before the final model;
it did not rerun or change MATLAB. No new upstream change was needed.

This activity stops here. Coordinator review is needed for the signed
Fresnel truth-frame mapping, the negative-contrast cases and the future
domain/generation choices. The old Figure 5 MR-CSI difference remains open.
Our maintained solver and the frozen scoring module were not edited.

## Successor status, 18 November 2026

Activity 02 was accepted. Its old drawing-frame scores and cost scenarios
are preserved as history, not current campaign choices. Activity 03
[frame.md](../03_prepare_simulated_tg002_cases/frame.md) and
[results.md](../03_prepare_simulated_tg002_cases/results.md) document the
nominal registered centre (0,+30) mm using primary reading. The radius
remains 15 mm and epsilon_r 3 +/-0.3. Exact surveyed centre coordinates
are unavailable; the database gives only an approximately 30 mm offset.

Report the measured CC image's registered symmetric-difference area error
35.123%, support area 736.537 mm2 (+4.20% size bias), centroid
(1.887,26.351) mm, vertical offset -3.649 mm and full centroid distance
4.108 mm separately. Do not fit a shift or call this an exact 35% physical
shape failure against uncertain metrology. The corresponding registered
MR/CSI scores are saved in activity 03; no old arrays or JSON were changed.

The coordinator excluded contrast 0.5 because the unchanged projection
forbids negative susceptibility. The common simulated grid is now chosen:
166-by-166 at 1.25 mm, half-width 103.75 mm. Native finer-grid data
generation was built and timed in activity 03. Activity 04 runs only
MF-CC-CSI on ten contrast-4 shapes, by the user's later decision. The
60-fit estimates above are historical counterfactuals, not authorized jobs.
Protocol-1 half-signed-peak support and 0.3/0.7 sensitivities are fixed.

The maintained inverse and comparison module are unchanged. Full `score()`
expects the original benchmark output schema, so the adapters import its
unchanged image-region helpers and report mean epsilon_r separately.
The MR/Figure-5 discrepancy and independent BEM forward comparison remain
open; no rerun of activity 02 is required for the handoff.
