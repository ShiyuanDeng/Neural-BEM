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

### First two simultaneous-frequency cases

| Case | Area error % | Final weighted mismatch | Iterations | Stop | Case seconds |
|---|---:|---:|---:|---|---:|
| circle__c0.5 | 76.2861 | 5.8761999 | 364 | mismatch_plateau | 291.806 |
| kite__c0.5 | 9.9849 | 0.000223769 | 2802 | mismatch_plateau | 2282.942 |

Both have zero unconverged checked inner solves. Kite's raw time includes
the 124-second pause and shared GPU use. Its worst endpoint frequency
residual is 0.0101315. The first-case forecast is not representative of all
cases; subsequent runtimes vary greatly. Settings remain fixed.

## Continuation campaign

The coordinator released the committed continuation variant (2296ed11d)
after its saved kite__c4 result: 2.97% area error. Native-run did not refit
that case and does not own its result files.

One detached continuation runner started at 15:28:12 UTC, alongside the
contrast-0.5 simultaneous-frequency runner. Its explicit list is the nine
remaining __c4 cases, then the ten __c0.5 cases. Settings are unchanged:
step 0.2, stage frequency counts 1, 2, 4, 8, 16, 19, with 1,000 iterations
per stage (6,000 maximum per case), the existing TV rule and inner checks.
There is no time stop. The first launch passed the 14 GiB host-memory check.

Each completed case sends its area error, final weighted mismatch, worst
frequency residual and raw seconds through Herdr. continuation_table.json
records those rows. Commits use only native-run's completed case paths;
the code agent's saved kite__c4 and shared run.json are not staged here.
The two run folders have separate case files; both CLIs write the derived
shared metrics.csv at completion, so the per-case JSON files are canonical.

### Continuation results so far

| Case | Area error % | Final mismatch | Worst frequency residual | Seconds | Iterations | Stop | Final step | Restarts | Start commit |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|
| circle__c4 | 2.3553 | 0.05059675 | 0.09237818 | 2146.573 | 6000 | iteration_limit | 0.2 | 0 | effe8c70fbd280f6668dce610c6368dfc73a8a4c |
| peanut__c4 | 1.6270 | 0.02408453 | 0.05819941 | 648.559 | 6000 | iteration_limit | 0.2 | 0 | 31c1fe1bbc6e47a3f4e6f9124d122467d0a92a52 |
| star__c4 | 2.0065 | 0.04438225 | 0.07888992 | 630.612 | 6000 | iteration_limit | 0.2 | 0 | 7771dcbe86f6274bc15fe81114f9150d69549164 |
| asymmetric__c4 | 1.6539 | 0.03868516 | 0.06207142 | 630.356 | 6000 | iteration_limit | 0.2 | 0 | 7771dcbe86f6274bc15fe81114f9150d69549164 |
| c_shape__c4 | 3.0388 | 0.05541937 | 0.0808622 | 630.413 | 6000 | iteration_limit | 0.2 | 0 | 9ec4a62d9fdb2b76c4f3b759c2a6ec770fcf3303 |
| hook__c4 | 2.5535 | 0.06809981 | 0.1052707 | 630.270 | 6000 | iteration_limit | 0.2 | 0 | 9ec4a62d9fdb2b76c4f3b759c2a6ec770fcf3303 |
| cross__c4 | 2.2969 | 0.02191643 | 0.06600618 | 630.151 | 6000 | iteration_limit | 0.2 | 0 | 80c80e9f7c371abbf9e1a1a0b4da5629c81398dd |
| cog__c4 | 2.7969 | 0.0573101 | 0.07640187 | 630.201 | 6000 | iteration_limit | 0.2 | 0 | 80c80e9f7c371abbf9e1a1a0b4da5629c81398dd |
| aphex_twin__c4 | 10.3182 | 0.03018323 | 0.05435177 | 630.264 | 6000 | iteration_limit | 0.2 | 0 | 30b35c8df9b272aa131c068d74558683d6da0893 |
| kite__c0.5 | 7.5754 | 0.0001649472 | 0.009103572 | 630.357 | 6000 | iteration_limit | 0.2 | 0 | 3f253b79379925089204e4d317a57a4ec62200db |
| peanut__c0.5 | 5.4092 | 0.0002434953 | 0.01147618 | 631.557 | 6006 | iteration_limit | 0.1 | 1 | c20b5dfeb9d37959ae80d1eb52bede56ceb9e69a |
| star__c0.5 | 8.0832 | 0.0002420903 | 0.007803367 | 625.495 | 5908 | iteration_limit | 0.2 | 0 | 48d100c6432ba6daaf8c163b73955261d3549498 |
| asymmetric__c0.5 | 5.4953 | 0.0002798454 | 0.0111977 | 630.126 | 6000 | iteration_limit | 0.2 | 0 | 3df5a127c5cb5932196d94ab3e9779126164b1fd |
| c_shape__c0.5 | 9.2058 | 0.0004376154 | 0.01182608 | 630.050 | 6000 | iteration_limit | 0.2 | 0 | 3df5a127c5cb5932196d94ab3e9779126164b1fd |
| hook__c0.5 | 15.7241 | 9.369616e-05 | 0.006075481 | 630.029 | 6000 | iteration_limit | 0.2 | 0 | 435449a42f907a5d5f14fca9c33984d6823acf01 |
| cross__c0.5 | 7.6708 | 0.000261668 | 0.009299555 | 630.033 | 6000 | iteration_limit | 0.2 | 0 | 435449a42f907a5d5f14fca9c33984d6823acf01 |
| cog__c0.5 | 4.6665 | 0.0003090357 | 0.01454004 | 630.282 | 6000 | iteration_limit | 0.2 | 0 | 70eaecf1ea2ca0808316f8b4ac9d949a5933a61f |

Circle ran under sharing. Peanut began about 26 seconds before the dedicated
allocation; star and subsequent cases started fully under that allocation.
Completed case arrays and checks are committed in pairs. The named converged
variant may still stop at its fixed iteration cap; stop reasons are shown.

### Continuation receives the GPU

At 16:04:26 UTC the coordinator paused the two cap-2000 probes, their
collector and the simultaneous-frequency peanut__c0.5 run with its parent
and monitor. Nothing was killed. These jobs stay paused until the
coordinator resumes them after continuation finishes; their raw times
include the open pause. pause_for_continuation.json records the PIDs.

The continuation runner is untouched and now has the GPU compute slot.
The first circle__c4 finished under sharing: area error 2.35526%, final
weighted mismatch 0.0505968, worst frequency residual 0.0923782, 2146.573 s,
6,000 iterations, iteration_limit, zero unconverged checked inner solves.
Subsequent per-case timings will note the new allocation. Peanut__c4 started
just before the allocation and can include a short shared interval.

## User pause for BEM priority

The coordinator paused all four GauGal GPU processes with SIGSTOP at
15:16:53 UTC: PIDs 1895339, 1895343, 1900300 and 1902305. They were paused,
not failed or stuck. Native-run launched no GPU work during the pause.

Native-run also paused its CPU controllers (1903073, 1899680, 1899688)
to prevent a memory guard from killing a paused fit or a runner from
launching another fit. The coordinator resumed the four fits and three controllers with SIGCONT
at 15:18:57 UTC. The read-only GPU sampler stayed active. pause.json records
the 124-second pause and BEM GPU sharing from 15:15:51 UTC.

Raw case wall times and optimization times will include this pause;
seconds-per-iteration values of the affected fits will also include it.
The first-case forecast predates the pause and no longer predicts a finish.

## Divergence safeguard and source records

The first continuation circle__c0.5 ran on 30b35c8df9b272aa131c068d74558683d6da0893.
Its 16-frequency stage diverged; the adjoint residual check later raised
0.000107799 > 0.0001. Its failure stays intact until the initial runner ends.
Then it is archived under failed_before_step_safeguard and refitted once,
as authorized by the coordinator on 19 November at 17:42 UTC.

Safeguard c20b5dfeb halves the step and restarts a stage if its weighted
mismatch exceeds twice its starting value. Rejected attempts are retained;
output checks distinguish rejected attempts from accepted checked solves.
Unchanged fits where the safeguard never fires are bit-identical.

The original kite__c0.5 ran on 3f253b79379925089204e4d317a57a4ec62200db.
It completed all six stages with no divergence: every stage history's
maximum/start ratio is 1.0 and all checked solves passed. Retain this fit:
area error 7.57544%, final step 0.2, zero restarts, iteration_limit.
The previously saved kite__c4 belongs to code agent's 2296ed11d variant.
Each case's exact start commit, final step and restart count appear in the
continuation table and in fit.json; commits made while a fit ran do not
change its recorded start commit.

The CLI parent alone was paused from 17:38:34 to 17:42:08 UTC; its child
continued. Parent wall time includes that pause. At 17:55:31 UTC only the
CPU reporter and publisher were replaced to record restart/source fields
and publish approved retries. Numerical runner 1921378 was untouched.
The other six paused processes remain paused for the coordinator.

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
Runs: 2/4 probes and 2/10 simultaneous cases completed (paused); 17/19 continuation cases saved
Result: exact step 0.2: mismatch 19→10.1109053; 1.13543 s/iter; inner 7.48e-7
Result: exact step 1.0: mismatch 19→10.0824825; 1.13678 s/iter; inner 1.08e-6
Failures: old-code continuation circle__c0.5 diverged; preserved for the approved safeguarded retry
Upstream patches: none
Changes to our code: none; scratch script and result records only
New unknowns: cap-2000 final solve statistics; contrast-0.5 campaign results
Proposed next activity: finish retained probes, ten simultaneous and 19 continuation cases; needs user decision: none
