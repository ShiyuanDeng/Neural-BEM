# Fit both BEM rows to saved BRG TG-002 data

## Authority and questions

18 November 2026. The BEM coordinator assigned `bem-b1` both B1 rows.
The user opened B1: "Both rows must use the saved BRG observations."
First prepare, check all 20 cases, and stop for the coordinator's go.
Then run known contrast, circle__c4 first, report its cost, then the other
19. Recovered contrast follows all known-contrast cases. One fit at a time;
only the coordinator may raise concurrency. No tuning reruns or solver edits.

Questions: do the two forward copies agree on every frozen true shape and
frequency, and what are the known/recovered-contrast fits on BRG's copy?
BRG's own inverse results are outside this activity's judgment.

## Fixed settings, before results

The coordinator's new brief supersedes older B1 proposals in BRG activity 04.
All ten TG-002 shapes at eta 0.5 and 4; one centred 65 mm circle from
`experiments.benchmark.scenes.start_fixture`. Preserve true offsets/rotations.
Read BRG's `results/brg/tg002_shapes/2026-11-17/<case>/local/data_NNN.mat`;
verify every file against its BRG bulk manifest before numerical use.
Missing files or hashes and mismatches go to the coordinator/baseline side.
Never generate, replace or alter BRG observations.

BEM length unit is 0.05 m, origin 0.5+0.5j m, default physical bounds.
BRG length unit is 0.065 m: multiply receivers and geometry by 1.3 and
wavenumbers by 1/1.3. Directions and complex scattered amplitudes are
unchanged. Verify physical receiver locations, phase products, physical
wavenumbers from the recorded background constants, and frozen coefficients.
No conjugation, gain, phase fit or far-field normalization.

Use `RealOnlyPolicy` with its unchanged default continuation schedule on the
19 TG-002 frequencies (odd indices among BRG's 37). The ladder uses 0.5,
0.75, 1 and 1.25 GHz, followed by the default full-catalog stages and tail.
`modal_muller` + `slider`, real observations, no localization, no warm-up,
no noise level, default resolution profile and series_loss=1e-9.
Only table_mode=True and ragged frequency blocks adapt the data interface.
Row one supplies eta; row two uses the unchanged weak-start scalar rule
(epsilon=1e-3, minimum start 0.05) on the lowest saved frequency, followed by
MaterialUnknown defaults. Truth is unavailable to the fitting path.

## Checks, comparisons and success criteria

Before any fit, verify all 740 saved observation hashes and their layouts.
For each true shape from `scenes.truth_fixture`, verify the frozen source and
BRG-request coefficients. Generate our own production and refined forward
copies at all 37 frequencies using the unchanged resolution profile for its
truth storage band. CUDA execution, one frequency/BLAS/OpenMP/Torch thread.
Save both complex field copies, units/layout, hashes and diagnostics locally.

At every frequency record complex Frobenius relative difference against BRG,
maximum absolute error, receiver/direction errors and the production/refined
difference (refined norm denominator). Limits fixed by the coordinator:
BRG difference <=0.01 and refinement <=1e-6; series limit remains 1e-9.
Any above-limit check, true-shape refusal or solver crash blocks that case
and is reported before a fit. Preserve failures; no resolution selection,
per-case cap or tolerance change. Complete available cases' checks, then stop
for the coordinator. Missing cases remain pending, never marked passing.

After each fit use unedited `experiments/comparison/scoring.py`, retaining
raw region, boundary, material/image and contrast scores, failures included.
Record fit outcomes and accepted endpoints, not success-only summaries.
No additional truth-based optimizer feedback or tuning reruns.

## Budget, resources and records

At most 740 paired-frequency checks, 20 known and 20 recovered fits.
Per fit 13,412 work units; disable elapsed-time stops in policy and supervisor.
Report times beyond 120 s and 1 h, continue unless stuck, faulty or memory
limited. Guard only the owned worker process group below 14 GiB available.
Launch only when available minus expected host peak minus 1 GiB exceeds
14 GiB; first peak estimate 3 GiB. Measure host high water and GPU sampled
and allocator peaks. A memory stop is excluded and requeued, retaining its
attempt. Before first fit confirm no csi_fit.py/brg_paper.py fit runs.
Recheck capacity after the current CSI batch; keep the simulated-CSI hold.
No existing job is stopped or modified.

First-fit report: outcome, last stage, work units, fit seconds, seconds/unit,
peak host/GPU memory, area error and a 40-fit forecast. Times are indicative
on this shared machine. Record command, commit, solver dirty state and source
hashes, all input hashes, thread controls, processes and resources each run.
Pin thread environment before NumPy import, Torch pools to one before work.
If solver sources are dirty/changed, the fit is not a reported result.

Commit and push owned paths after each check run and each fit, including
failures. Keep about 5 MB per run; bulk in ignored local/ with SHA-256.
No branch/worktree. Do not edit solver, baseline, comparison, other agents'
files or coordination files. Questions are reported in this pane.

## Commands and locations

Python: `/home/drdeng/miniconda3/envs/EMNerf/bin/python`, repository root.
Owned code: `experiments/bem_on_baseline_data/b1_*.py`.
Evidence: `results/bem/baseline_data/brg_tg002/2026-11-18/`.
Report: this folder's `results.md`; figures, if needed, in `figures/`.

- `python experiments/bem_on_baseline_data/b1_run.py prepare`: hashes,
  layout/unit checks, fixed schedule comparison and missing-data report.
- `python experiments/bem_on_baseline_data/b1_run.py checks`: guarded,
  sequential forward checks on available verified cases; no fit.
- After coordinator go only: `python experiments/bem_on_baseline_data/b1_run.py fit --case circle__c4 --row known`.
- After first-fit report: same command for each remaining known case, then
  `--row recovered` for each case. Queue order is saved in prepare receipts;
  launch remains sequential and does not imply permission to bypass stops.

Report includes actual settings, dates, failures, measurements and evidence.
The all-case check report and first-fit report are explicit coordinator stops.

## Coordinator continuation note, 18 November

The baseline side has observations for 16 cases; cog and aphex_twin at both
contrasts are being generated. A case is usable only once its bulk manifest
exists and all 37 file hashes match. Check complete cases now and pick up
remaining cases when their manifests appear. Read-only access remains strict.
A new coordinator session takes over in pane w2:p1; the fixed brief and both
review stops remain unchanged.

`python experiments/bem_on_baseline_data/b1_run.py watch-checks` watches only
for these manifests, checks newly available cases under the same guard, and
stops once all case checks are recorded. It never starts an inverse fit.
