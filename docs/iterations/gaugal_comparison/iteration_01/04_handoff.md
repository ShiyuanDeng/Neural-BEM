# Overnight comparison handoff — 2026-11-02

## Required outcome

Finish the full TG-002 comparison by the working target of **08:00 London,
2026-11-02**. The user confirmed three separate arms: BEM with supplied
contrast, BEM recovering contrast, and GauGal. All 30 cases must appear.

The user explicitly expects **a full comparison table and reasons for
failures**. Include boundary RMS, Hausdorff upper bound, maximum field residual,
contrast estimate/error, image RRMSE/SSIM/PSNR/contrast SNR, runtime, recovery
status and actual stopping/failure reason for each arm. Put the full data in
CSV/JSON as well as readable tables and galleries in `report.md` here.

Explain each unsuccessful result using saved evidence. Distinguish a
numerical refusal, inaccurate final derivatives/fields, high measurement
residual, wrong recovered material, and a time/iteration budget. Separate
observed causes from hypotheses; an inconclusive lower bound does not prove
that a curve is invalid. A partial image is not a completed recovery.

## Workspace and running job

Use `/home/drdeng/Neural_SDF_BEM_AD_organised`, existing branch `organised`,
upstream `origin/organised`. This experiment explicitly uses this worktree;
do not switch to the AGENTS.md default checkout. Do not create a branch or
worktree without the user's explicit permission.

**Do not launch a duplicate overnight job.** A detached supervisor is running:

- PID at handoff: `2126096`, reparented to PID 1, its own session.
- Driver: `python -u -m experiments.gaugal_comparison.overnight`.
- Console log: `/tmp/ggb002-overnight.log`.
- State: `results/validation/cleaned_interfaces/GGB-002/status.json`.
- PID file: `results/validation/cleaned_interfaces/GGB-002/runner.pid`.
- Interpreter: `/home/drdeng/miniconda3/envs/EMNerf/bin/python`.
- `PYTHONPATH=solvers:.:/home/drdeng/Gau-Gal/src`; single-threaded BLAS.

Read the current state and verify the PID before taking action. At 02:32 it
was on the third circle for step 1. The two earlier circle results are saved.
If the process has stopped, inspect its console/state and fix the smallest
actual failure. Completed case JSON files are reused by the driver.

The supervisor runs tuning, freezes one common setting, runs all 30 cases,
invokes `experiments.gaugal_comparison.report`, and commits/pushes after each
case and the final report. Its console is outside the repository so the final
commit can leave a clean tree. Do not alter its running configuration without
a prospective plan amendment. Source edits to the already-loaded supervisor
do not change that process; the report module is loaded in a new subprocess
at the end, so report improvements made now will be used.

## Frozen experiment choices

Read `03_plan.md`, particularly the morning-priority, T0, BEM-selection and
G1/G2 amendments. The main experiments are already authorized.

- Supplied-contrast BEM: S1 with **both** S3 replacements, hook c0.5 and aphex
  c0.5. Removing the degree cap does not change the other cases' paths.
  Combined evidence gives **26/30**; do not call it a fresh full campaign.
- Material-recovery BEM: S2, **23/30**, the strongest completed truth-free
  full campaign. Never substitute truth-assisted R3 starts.
- S4/S4b removed the positive-lower-bound refusal but added no confirmed
  recoveries. They are diagnostic evidence, not selected BEM results.
- GauGal: grid 51, width .7, lambda .5, susceptibility bounds [-.9, 15],
  201-pixel quadrature, all 19 real frequencies, inner-solve cap 100.
- G1: common steps **1, .01, .05**, each on the three circle contrasts,
  30 iterations, 170 s optimization allowance, 210 s outer limit per fit.
  Select by mean image RRMSE; incomplete-setting fallback is documented.
- Steps 4/16 were replaced before running: step 1 diverged on circle c0.5
  (maximum residual 688, RRMSE 10.48), so larger steps were not useful tests.
- G2: chosen shared setting, 80 iterations, 400 s optimization allowance,
  480 s outer limit per case. Circle cases are rerun and marked as tuning.
- No further BEM tuning and no broad MoM/forward sweep for this delivery.

T0 measured 13.42 s build plus 50.12 s for 10 iterations. The original
300-iteration setting would exceed the overnight budget. Report the reduced
budget and actual iteration counts plainly. The existing seven-case forward
sweep does not meet 1% at higher frequencies. The plan now retains all 19
frequencies and discloses that limitation instead of restricting GauGal to
one frequency. This is an adapted TG-002 experiment, not a reproduction of
GauGal's published benchmark or proof of an intrinsic method ranking.

## Work still needed

1. Monitor the existing supervisor and fix actual run failures if necessary.
   Keep within the recorded counts/time limits unless evidence warrants a
   dated amendment. Preserve all earlier outputs and unsuccessful evidence.
2. **Extend the report with explicit failure reasons.** The current renderer
   has aggregate/per-case metrics and galleries, but no complete per-arm
   failure-reason table yet. Read BEM `result.json`, stage `physics_failures`
   and `final_audit.json`; read GauGal stop reasons, histories, inner-solve
   summaries and forward-check evidence. Explain numerical/optimization
   limitations without treating plausible explanations as proved causes.
3. Confirm every case has all three arms represented. Include partial and
   failed outcomes explicitly, never fabricated scores for missing outputs.
   Review the final report and galleries after generation. The preview under
   `GGB-002/report_preview/` is only a layout check using T0, not final data.
4. Commit and push any remaining report/code/results changes; verify the push
   and working-tree status. Avoid documentation tests on a `cp` request.

The report renderer is `experiments/gaugal_comparison/report.py`. It produces
`report.md`, `comparison.csv`, `comparison.json`, and `comparison_figures/`
in this iteration folder. Run it from the repository root with the interpreter
and environment above if the automatic report step fails or needs refreshing.

## Most recent BEM failures

S3 removed the 4,000-term degree cap. Hook c0.5 then recovered at 0.00419 mm
RMS; the saved trial needs 4,354 terms. Aphex c0.5 instead failed the separate
positive-lower-bound calculation, at 5.975 mm RMS.

S4/S4b kept the sampled logarithm interval when the bound was inconclusive.
Cog c13.3 completed at 0.481 mm RMS but field residual 0.246, and failed final
numerical checks. Aphex c4 completed at 0.2078 mm RMS, residual 0.003799
(limit .003), and maximum Jacobian discrepancy .00536. Aphex c0.5 reached
M25 before the 900 s campaign limit; aphex c13.3 reached M85 before its 300 s
limit. Neither timeout has a final recovery result. Preserve them as such.

The shared implementation currently contains the experimental sampled-bound
fallback; the selected BEM report arms are the saved S1/S3 and S2 versions.
Do not silently describe the report as all arms using the latest source.
