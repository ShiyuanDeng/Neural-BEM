# GGB-003 stage one plan: fair evaluation of our own method

Questions: How well does the real-only, unknown-contrast default recover all 30 TG-002 scenes, clean and with noise?
What changes with damped data, the nodal backend, a fixed shape band, simultaneous frequencies, or a single frequency?
What settings and storage must be fixed so later baselines are compared under the same rules?

Written 17 November 2026 from the user interview on
[the stage-one proposal](../iteration_01/02_proposals/01_stage_one_actions_verified.md).
Decisions are recorded in [D13](../../../cleanup/user_decisions.md#d13-ggb-003-stage-one-runs-scoring-and-storage-2026-11-17).
Where this plan and the proposal differ, this plan applies.
The code is written ([implementation record](#implementation-record-17-november-2026)); no planned run has started.

**[decision]** marks what the user decided. **[proposal]** marks details still open to change before the runs.

## Scope

**[decision]** Stage 1 evaluates our own method fairly. It makes no claims.
Claims wait until Stage 2, when external baselines have run.
Choosing and running external baselines other than GauGal is Stage 2.

**[decision]** The run limit is 6 hours in total, including GauGal and follow-ups.

## Default method

**[decision]** The default is `modal_muller` + `slider`, real data only, unknown contrast (recovered),
localization `none`, centred 65 mm start. `Problem` must accept an absent damped catalog.

**[decision]** The default has no warm-up. The 0.25 GHz band-1 step is removed.

| Step | Default schedule |
|---|---|
| 1 | Real 0.5 GHz, then add 0.75, 1.0 and 1.25 GHz one at a time. Shape band follows the existing rule (three times the top wavenumber, rounded down). |
| 2 | All 19 real frequencies, shape bands 11, 15, 19, 25, 31, 37. |
| 3 | Adaptive tail, more bands up to 95 if the data supports them. |

Frequencies, bands and budgets are copied from the current schedule in
[policy.py](../../../../solvers/bem_inverse/policy.py#L143), with real data in place of damped.
The old "return to real data" step is dropped because it repeats step 1.
No tuning on any case. The result is reported as it comes out.

## Runs

**[decision]** Only the default runs all 30 scenes. Every other run uses the 20 scenes without contrast 13.3.
User's reason: other baselines do not have scenes with that high a contrast.
Contrast 13.3 results are reported in a separate block, so cross-run tables share the same 20 scenes.

**[decision]** Noisy data and damped data never appear together.

| # | Family | Run folder | What differs from the default | Scenes | Fits | Rough time |
|---|---|---|---|---:|---:|---:|
| 1 | bem | `default_clean_uc_fc` | nothing | 30 | 30 | 10 min |
| 2 | bem | `default_n1d0_uc_fc`, `default_n1d1_uc_fc`, `default_n1d2_uc_fc` | 1% noise, three draws | 30 | 90 | 30 min |
| 3 | bem | `default_clean_kc_fc` | contrast supplied | 20 | 20 | 5 min |
| 4 | bem | `default_cleandamped_uc_fc` | damped catalog added; old schedule unchanged, including its damped 0.25 GHz warm-up | 20 | 20 | 7 min |
| 5 | bem | `nodal_clean_uc_fc`, `nodal_n1d0_uc_fc` | nodal backend | 20 | 40 | not measured |
| 6 | bem | `fixedband37_clean_uc_fc` | shape band 37 throughout, no growth, no tail | 20 | 20 | 7 min |
| 7 | bem | `default_clean_uc_fs` | skip step 1; start at all 19 frequencies | 20 | 20 | 7 min |
| 8 | bem | `default_clean_uc_sf0.5`, `_sf1`, `_sf1.5`, `_sf2` | one frequency only; same band growth rule, stopping at the adaptive limit for that frequency | 20 | 80 | 15 min |
| 9 | gaugal | `default_n1d0_uc_fs` | GauGal, untuned, run last | 20 | 20 | 1.9 h |
| 10 | — | RegPy forward check | independent forward solver, no fit | 1 | — | minutes |

Times are scaled from saved medians (14–21 s per BEM fit, 340 s per GauGal case).
None of the new runs has been timed; failing cases take longer.
Estimated total for the listed runs is about 4 hours.

Notes on single runs:

- Run 4 differs from the default in both data and warm-up. Say so wherever it is compared.
- Run 5 on clean data fits data made by the same nodal solver, so it may look too good.
  The noisy draw is there for a fairer modal versus nodal comparison. Record this caveat with the results.
- Run 9 uses the saved GGB-002 GauGal settings with no tuning effort.
  **[decision]** Record in the report that GauGal was not tuned, so its numbers are a reference, not a fair baseline.
- Run 10 **[proposal]**: `asymmetric__c4`, all 19 real frequencies, relative field difference limit 1e-6,
  written down before the comparison is computed.

## Noise

**[decision]** Start at 1% complex-Gaussian noise, since noise has not been used before.
Raise to 5% only if 1% goes well and time remains.

**[decision]** Three fixed draws per case for the default. Every method reads the same saved noisy arrays.
**[proposal]** Seeds 0, 1, 2. Save each array with its seed, expected level and realized level per frequency.

## Scoring and success

**[decision]** The main metric is unaligned symmetric-difference area divided by true area.
All reconstructed components are scored, holes kept, component count reported.
Material-field error is computed on one grid shared by all methods.
Boundary RMS, Hausdorff, Chamfer, centroid distance, image scores, work counts and fit time are kept.

**[decision]** A fit is successful when area error is ≤ 5%. This uses area alone, for clean and noisy data.
The old count (RMS ≤ 1 mm, Hausdorff ≤ 2 mm, residual limit) is shown beside it as a secondary column.

**[decision]** The success rule is a data-analysis choice only. It needs the true shape, so the fit never sees it.
Stopping during a fit is unchanged: residual, step size and budget.

**[decision]** The 5% cut-off is provisional and deliberately a little loose.
It may be changed once all raw metrics are in. A change is a recount with a dated note, not a rerun.
Metric definitions are fixed before the runs; only the cut-off stays adjustable.

## Storage

**[decision]** The root is `results/`. The user is clearing the old contents.

```
results/
  _shared/noise/n1d0/<case>.npz     noisy data, read by every family
  metrics.csv                       one row per fit, all families
  <family>/                         bem, gaugal, later ones
    <run>/                          <variant>_<data>_<contrast>_<frequency>
      run.json                      settings for this run, written once
      <case>/                       e.g. circle__c4
        fit.json   fit.npz          solver output, no truth used
        score.json                  truth-based metrics
```

| Tag | Values now | Meaning |
|---|---|---|
| variant | `default`, `nodal`, `fixedband37` | the one method change from the default |
| data | `clean`, `cleandamped`, `n1d0`, `n1d1`, `n1d2`, `n5d0` | noise level and draw; `damped` means the extra catalog |
| contrast | `uc`, `kc` | unknown or known contrast |
| frequency | `fc`, `fs`, `sf0.5`, `sf1`, `sf1.5`, `sf2` | frequency continuation, simultaneous, single frequency |

Rules:

- Every run folder carries all four tags, in this order, even at their usual values.
- A new method adds a family folder or a new tag value, never a new position.
- `run.json` records exactly what `default` meant: backend, update rule, schedule and code commit.
- Each noise draw is its own run folder. Every case folder holds the same three files.
- Case folders keep the existing names, such as `circle__c4`.
- Failed fits are saved the same way as successful ones.
- `fit.*` is written by the solver side and holds no truth-based numbers.
  `score.json` is written by a separate step that reads the fit and the truth.
- `metrics.csv` holds raw numbers only. The success column is computed when the report is built.

Plan, report and figures stay in this folder, `docs/iterations/gaugal_comparison/iteration_02/`.

## Work before the runs

1. Change `Problem` so the damped catalog can be absent, and add the real-only schedule above.
2. Add the schedule variants: simultaneous, fixed band 37, single frequency.
3. Add noise generation and saving under `results/_shared/noise/`.
4. Extend scoring: all components, area error, material-field error on the shared grid.
   Fix the grid, support threshold, sign handling, connectivity, hole treatment and empty-output rule.
5. Write fits and scores into the storage layout, and build `metrics.csv`.
6. Write these settings into each `run.json` before its run starts.

Keep checks to the minimum needed for the changed code.

## Order and time

1. Run 1, then run 2.
2. Runs 3 to 8.
3. Run 10 can go at any point; it needs no fit.
4. Run 9 (GauGal) last of the listed runs.
5. Follow-ups in whatever remains of the 6 hours.

If time runs short, runs are dropped from the end of this order and the report says which.

## Follow-ups

**[decision]** In the remaining time an agent explores next steps, either those named here or others it finds useful.
The first named follow-up is 5% noise on the default (`default_n5d0_uc_fc`), if the 1% results are good.

Before each follow-up, the agent writes a dated note in this folder:
what it saw, what it changes, how many fits, and when it stops.
Follow-ups stay on the same question: how well our own method performs.

## Open items

- **Sealed inputs.** The clean TG-002 catalogs now sit in `results/validation/cleaned_interfaces/TG-002/inputs/`.
  They must survive the clearing of `results/`, or be given a new home, before any run.
- **Old GauGal clean results.** Rescoring them under the new rules needs the saved GGB-002 outputs.
  If those are cleared, this plan has only the noisy GauGal run.
- **Nodal timing.** No estimate exists. If run 5 threatens the 6-hour limit, its noisy half is dropped first.

## Implementation record (17 November 2026)

Code: [experiments/comparison](../../../../experiments/comparison/README.md), one command per run.
Solver side: `Problem(damped=None)` and [RealOnlyPolicy](../../../../solvers/bem_inverse/real_only_policy.py).
Workflow decision: [D15](../../../cleanup/user_decisions.md#d15-ggb-003-write-the-code-first-a-cheaper-agent-runs-it-2026-11-17).

**[proposal]** Details the plan left open, as the code fixes them. Change any of them before run 1, not after.

| Detail | As implemented |
|---|---|
| Fit time limit | 120 s wall per BEM fit (`FIT_SECONDS` in `bem.py`), the TG-002 contract value. Not in the plan; see the note below. |
| Unknown-contrast start | MR-001's weak-scatterer rule at the lowest real frequency the fit may read. Run 4 uses the lowest damped frequency, as before. |
| Run 4 | Unchanged `CumulativePolicy` with the start kept; the same setup as GGB-002's recovered-contrast runs. |
| Run 6, fixed band 37 | Same stages, frequencies, quotas and iteration caps as the default; only the shape band is 37 everywhere. Ladder storage is 76 (2M+2). No frontier, no tail. |
| Run 7, simultaneous | The six whole-catalog stages (bands 11 to 37) from the start circle, then the tail. |
| Run 8, single frequency | The catalog holds that one frequency. One stage at band floor(3k), then the frontier is measured once at that frequency; bands 11, 15, 19, ... are released while the last band is below it. |
| Noise | Per frequency, level times the clean norm; rule in [noise.py](../../../../experiments/comparison/noise.py). The per-frequency standard deviation is declared to the BEM fit, which then uses the existing whitening and discrepancy stop. GauGal gets the noisy data only. |
| GauGal | Saved GGB-002 setting; one child process per case, 400 s optimization limit, 600 s outer limit. The truth fields of the loaded case are blanked before the adapter sees it. |
| Scoring | Protocol version 1, written out in [scoring.py](../../../../experiments/comparison/scoring.py): 201 x 201 shared grid at 1 mm, image support at half the peak magnitude with the peak's sign, even-odd fill of every closed level line, no minimum component size, empty region scores area error 1. Image methods also get area error at 0.3 and 0.7 of the peak as a sensitivity check. |
| Old count | Uses the new all-component boundary RMS and Hausdorff upper bound, plus the residual limit. BEM rows also keep the earlier TG-002 curve distances. |
| Timing | Fits run one at a time in one process, after one untimed warm-up solve. `fit_seconds` is the fit alone; start solve, final residual and scoring are separate. |
| Storage additions | `results/_checks/forward_regpy/` for run 10. `import-ggb002` copies the 30 saved clean GauGal fits to `gaugal/default_clean_uc_fs` for rescoring. `.gitignore` now lets `fit.npz` and the noise files through. |

**Fit time limit.** A failing fit is slow: one single-frequency test fit ran 292 s, and failed fits in the
saved GGB-002 runs took up to 1685 s. Without a limit the 6-hour total cannot hold.
With 120 s, one recovered fit in the saved runs (173 s) would have been cut short.

**Time estimate.** The table's times assumed median fit times. Measured here: nodal about 84 s per fit,
so run 5 is near an hour. Slow failures will add to every run; expect the listed runs to pass 4 hours.

Checks made while writing, all in a scratch folder and not kept as results:

- Run 4's setup on `kite__c4` reproduces the saved GGB-002 fit exactly (RMS 0.017780 mm, 24.7 s).
- The new all-component boundary RMS agrees with the earlier curve RMS on single-curve fits.
- The 30 imported clean GauGal fits reproduce their saved RRMSE and SSIM.
- The RegPy forward check on `asymmetric__c4`: worst difference 9.8e-11 against the 1e-6 limit.
- One fit per variant ran through fit, scoring and `metrics.csv`. Single test fits are not results:
  the default recovered `kite__c0.5`, `circle__c4` and `star__c4` and failed `kite__c4`;
  the fixed-band, simultaneous and single-frequency test fits failed.

Open items, updated:

- **Sealed inputs.** Settled: they are in `development_results/TG-002` and the code reads them there.
- **Old GauGal clean results.** Kept in `development_results/GGB-002/G2_all`; `import-ggb002` rescoring covers them.
- **Nodal timing.** Measured once, about 84 s for a fit the default finishes in 31 s.

## Not in this plan

- External baselines other than GauGal, and any claims about them (Stage 2).
- TG-002-F and plane-wave support (Stage 2).
- Gradient-descent and top-frequency-only runs.
- Any tuning of the default or of GauGal.
- Corrections to the old GGB-002 report; those stay as listed in the proposal, steps 1.1 and 1.2.
