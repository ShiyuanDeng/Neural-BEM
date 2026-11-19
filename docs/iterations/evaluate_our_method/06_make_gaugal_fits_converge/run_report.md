# GauGal convergence probes and low-contrast clean runs

19 November 2026, UTC. Native-run owns the probe and run evidence only.
No repository implementation, scoring or upstream file was edited by this agent.

## User/coordinator changes and current scope

The original Part 1 used two cap-2000 probes, two 15-minute iteration-count
probes and two larger-step probes. The coordinator cancelled Step 2, retained
the running Step 1 fits, and changed Step 3 to the committed exact-solve path
at steps 0.2 and 1.0 for 200 iterations each, mismatch only.

The coordinator then released only the ten clean contrast-0.5 campaign cases.
No contrast-4 campaign case is launched by native-run. The code agent owns
the step-0.05 contrast-4 check and its continuation work.

## Step 1: higher inner-iteration cap

Started 14:36:03 UTC: clean kite__c4 and kite__c0.5, ten outer iterations,
SolverControls(pcg_max_iter=2000). The two fits use the original numerical
branch already imported before the exact-solve commit. They remain active.
Their first mismatch evaluations each took about 130.22 optimization seconds.
Final solver shares and residual maxima await their completion.

Both use the same blind input path as the comparison runner: lattice 51,
width 0.7, TV scale 0.5, step 0.05, susceptibility bounds -0.9 to 15,
all 19 real frequencies, no time stop. No truth is passed to reconstruction.

## Step 2

Skipped by the coordinator to save time. No Step 2 fit launched.

## Step 3: exact-solve step sizes

Committed numerical code: 86232abe1. The scratch script calls reconstruct
with convergence=CONVERGENCE and max_seconds=None. Settings are unchanged
except step 0.2/1.0 and the 200-iteration limit. No truth score was computed
for these probes. Decisions and reports use weighted mismatch only.

| Step | Iterations | Weighted mismatch: start → end | End minus value 19 steps earlier | Seconds/iteration | Worst inner relative residual | Stop |
|---:|---:|---:|---:|---:|---:|---|
| 0.2 | 200 | 19 → 10.1109053 | -0.1152054 | 1.13543 | 7.47928e-7 | iteration_limit |
| 1.0 | 200 | 19 → 10.0824825 | -0.0599668 | 1.13678 | 1.08491e-6 | iteration_limit |

Both remain below the initial mismatch and are still falling over their last
20 evaluations. Neither blows up. Step 1.0 has small intermediate rises;
its final mismatch is only slightly below step 0.2. Neither reached the
committed plateau rule before the 200-iteration limit.

All 19 endpoint data residuals are saved in each fit.json. Their ranges are
0.41549–1.05461 at step 0.2 and 0.35937–1.04984 at step 1.0. Inner residuals
and observed-data residuals are separate quantities.

The scratch script copies each existing checked-solve residual after the
check returns; it does not change the solve or gradient. All inner solves
were converged, all final images finite and all prediction arrays 19 by 24.
Every-20-iteration results were sent through Herdr until the coordinator
requested results only. Each probe's fit.npz is kept for later review.

## Contrast-0.5 campaign

A single detached runner was launched at about 14:46 UTC for the explicit
ten __c0.5 cases in gaugal/converged_clean_uc_fs. The runner writes the shared
metrics.csv directly without a lock, so two runners were not used. The
existing matching run.json is read and not rewritten.

The command, GPU sample, memory sample, process IDs and live state are in
results/gaugal/converged_clean_uc_fs/low_contrast_launch.json and
low_contrast_state.json. The monitor sends the first-case timing and forecast
as soon as fit.json appears. No time stop is imposed; the host-memory floor
is 14 GiB. All times come from date -u.

## User pause for BEM priority

The coordinator paused all four GauGal GPU processes with SIGSTOP at
15:16:53 UTC: PIDs 1895339, 1895343, 1900300 and 1902305. They are paused,
not failed or stuck. No GPU work is launched or resumed by native-run.

Native-run also paused its CPU controllers (1903073, 1899680, 1899688)
to prevent a memory guard from killing a paused fit or a runner from
launching another fit. They must resume only after the coordinator's go.
The read-only GPU sampler remains active. pause.json records the details.

Raw case wall times and optimization times will include this pause;
seconds-per-iteration values of the affected fits will also include it.
The first-case forecast predates the pause and no longer predicts a finish.

## Evidence

Probe root: results/_probes/gaugal_convergence/2026-11-19/.
The one scratch script is probe.py. Each fit keeps its state, mismatch log,
fit record, final arrays and output checks. Completed probe folders have
SHA-256 manifests. The final campaign table will be added here after the run. The first case
completed at about 14:51 UTC: circle__c0.5, 364 iterations, mismatch_plateau,
final weighted mismatch 5.8761999, area error 76.2861%, case time 291.806 s.
Its first-case forecast is 48.63 minutes total and 43.77 minutes remaining;
first_case_forecast.json records the numbers and GPU-sharing context.

Activity: evaluate_our_method/06_make_gaugal_fits_converge, 2026-11-19
Runs: 2/4 probes completed; 1/10 campaign cases completed; wall time pending
Result: exact step 0.2: mismatch 19→10.1109053; 1.13543 s/iter; inner 7.48e-7
Result: exact step 1.0: mismatch 19→10.0824825; 1.13678 s/iter; inner 1.08e-6
Failures: none; live Step 1 and campaign fits paused by user at 15:16:53 UTC
Upstream patches: none
Changes to our code: none; scratch script and result records only
New unknowns: cap-2000 final solve statistics; contrast-0.5 campaign results
Proposed next activity: wait for coordinator to resume GauGal after BEM; needs user decision: coordinator resume
