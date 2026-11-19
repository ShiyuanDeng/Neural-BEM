# GauGal first continuation run — native-run report

19 November 2026, UTC. This closes the first continuation pass; the two
cap-2000 probes and the ten-case simultaneous-frequency campaign were resumed at 19:19:41 UTC and paused again for activity 07 at 19:23 UTC.
No implementation, upstream source or scoring file was edited by native-run.

## Settings, scope and result counts

TG-002 clean data, one centred blind start, recovered contrast, lattice 51,
width 0.7, TV scale 0.5, susceptibility bounds −0.9 to 15, protocol version 1.
Continuation uses 1, 2, 4, 8, 16, then 19 real frequencies, step 0.2 initially,
up to 1,000 iterations per stage. The committed mismatch stop rule and exact
inner checks are fixed. Truth scores never selected settings or restarts.

There are **19 nonfailed fits out of 20 planned cases, and one FAILED fit**.
The 19 nonfailed fits have saved outcome STOPPED_EARLY with iteration_limit;
they reached the configured stage limits, not the outer convergence rule.
Nine of ten contrast-4 fits and one of nine nonfailed contrast-0.5 fits have
area error at most 5%: **10/20 planned cases**, versus 0/20 old defaults.
Circle__c0.5 is excluded from both the nonfailed and successful-fit counts.
Its saved image has a separate diagnostic score of 4.6954%.

## All 20 first-pass continuation cases

Old default means the saved clean all-frequency 80-iteration reference,
`gaugal/default_clean_uc_fs`. Commit is the source at child start, not the
HEAD at save time. Full hashes remain in each linked fit.json.

| Case | Area error % | Old default area % | Worst frequency residual | Final step | Restarts | Outcome | Seconds | Start commit |
|---|---:|---:|---:|---:|---:|---|---:|---|
| [circle__c4](../../../../results/gaugal/converged_clean_uc_fc/circle__c4/fit.json) | 2.3553 | 110.8518 | 0.09237818 | 0.2 | 0 | STOPPED_EARLY | 2146.573 | `effe8c70f` |
| [kite__c4](../../../../results/gaugal/converged_clean_uc_fc/kite__c4/fit.json) | 2.9655 | 158.3706 | 0.05678632 | 0.2 | 0 | STOPPED_EARLY | 2277.691 | `2296ed11d` |
| [peanut__c4](../../../../results/gaugal/converged_clean_uc_fc/peanut__c4/fit.json) | 1.6270 | 223.6909 | 0.05819941 | 0.2 | 0 | STOPPED_EARLY | 648.559 | `31c1fe1bb` |
| [star__c4](../../../../results/gaugal/converged_clean_uc_fc/star__c4/fit.json) | 2.0065 | 100.3113 | 0.07888992 | 0.2 | 0 | STOPPED_EARLY | 630.612 | `7771dcbe8` |
| [asymmetric__c4](../../../../results/gaugal/converged_clean_uc_fc/asymmetric__c4/fit.json) | 1.6539 | 144.7204 | 0.06207142 | 0.2 | 0 | STOPPED_EARLY | 630.356 | `7771dcbe8` |
| [c_shape__c4](../../../../results/gaugal/converged_clean_uc_fc/c_shape__c4/fit.json) | 3.0388 | 125.0262 | 0.0808622 | 0.2 | 0 | STOPPED_EARLY | 630.413 | `9ec4a62d9` |
| [hook__c4](../../../../results/gaugal/converged_clean_uc_fc/hook__c4/fit.json) | 2.5535 | 116.5453 | 0.1052707 | 0.2 | 0 | STOPPED_EARLY | 630.270 | `9ec4a62d9` |
| [cross__c4](../../../../results/gaugal/converged_clean_uc_fc/cross__c4/fit.json) | 2.2969 | 132.2944 | 0.06600618 | 0.2 | 0 | STOPPED_EARLY | 630.151 | `80c80e9f7` |
| [cog__c4](../../../../results/gaugal/converged_clean_uc_fc/cog__c4/fit.json) | 2.7969 | 125.7538 | 0.07640187 | 0.2 | 0 | STOPPED_EARLY | 630.201 | `80c80e9f7` |
| [aphex_twin__c4](../../../../results/gaugal/converged_clean_uc_fc/aphex_twin__c4/fit.json) | 10.3182 | 85.8133 | 0.05435177 | 0.2 | 0 | STOPPED_EARLY | 630.264 | `30b35c8df` |
| [circle__c0.5](../../../../results/gaugal/converged_clean_uc_fc/circle__c0.5/fit.json) | 4.6954 (saved image only) | 71.4668 | 0.02123799 | 0.0125 | 4 | FAILED | 400.504 | `de5422c0d` |
| [kite__c0.5](../../../../results/gaugal/converged_clean_uc_fc/kite__c0.5/fit.json) | 7.5754 | 11.5070 | 0.009103572 | 0.2 | 0 | STOPPED_EARLY | 630.357 | `3f253b793` |
| [peanut__c0.5](../../../../results/gaugal/converged_clean_uc_fc/peanut__c0.5/fit.json) | 5.4092 | 9.2589 | 0.01147618 | 0.1 | 1 | STOPPED_EARLY | 631.557 | `c20b5dfeb` |
| [star__c0.5](../../../../results/gaugal/converged_clean_uc_fc/star__c0.5/fit.json) | 8.0832 | 10.0898 | 0.007803367 | 0.2 | 0 | STOPPED_EARLY | 625.495 | `48d100c64` |
| [asymmetric__c0.5](../../../../results/gaugal/converged_clean_uc_fc/asymmetric__c0.5/fit.json) | 5.4953 | 7.1753 | 0.0111977 | 0.2 | 0 | STOPPED_EARLY | 630.126 | `3df5a127c` |
| [c_shape__c0.5](../../../../results/gaugal/converged_clean_uc_fc/c_shape__c0.5/fit.json) | 9.2058 | 10.0233 | 0.01182608 | 0.2 | 0 | STOPPED_EARLY | 630.050 | `3df5a127c` |
| [hook__c0.5](../../../../results/gaugal/converged_clean_uc_fc/hook__c0.5/fit.json) | 15.7241 | 8.5012 | 0.006075481 | 0.2 | 0 | STOPPED_EARLY | 630.029 | `435449a42` |
| [cross__c0.5](../../../../results/gaugal/converged_clean_uc_fc/cross__c0.5/fit.json) | 7.6708 | 9.8214 | 0.009299555 | 0.2 | 0 | STOPPED_EARLY | 630.033 | `435449a42` |
| [cog__c0.5](../../../../results/gaugal/converged_clean_uc_fc/cog__c0.5/fit.json) | 4.6665 | 9.0794 | 0.01454004 | 0.2 | 0 | STOPPED_EARLY | 630.282 | `70eaecf1e` |
| [aphex_twin__c0.5](../../../../results/gaugal/converged_clean_uc_fc/aphex_twin__c0.5/fit.json) | 17.0111 | 22.0714 | 0.01548247 | 0.2 | 0 | STOPPED_EARLY | 630.069 | `70eaecf1e` |

Worst frequency residual is the saved endpoint data residual, distinct from
an inner solve residual. For failed circle__c0.5 it covers only the last
accepted 16-frequency image; the other 19 rows cover all 19 frequencies.
Final step for circle is the last attempted step, 0.0125; its saved image
came from the accepted 16-frequency stage at step 0.05.

The code agent supplied kite__c4 on 2296ed11d; it was not refitted here.
Other cases started on the commits shown. Safeguard c20b5dfeb halves a step
and restarts a rejected stage; no-trigger fits stay bit-identical. Old-code
kite__c0.5 is retained: every stage history maximum/start ratio is 1.0 and
its checked solves passed. Peanut__c0.5 used one restart, ending at step 0.1.

## Circle__c0.5 before and after the safeguard

Before: source `30b35c8df9b272aa131c068d74558683d6da0893`, outcome EXCEPTION_PARTIAL,
stop exception, 510.340 s. The saved-image area error was
82.3217%, mismatch 110.7481, worst frequency residual
5.370532. The adjoint check raised 0.000107799 > 0.0001 after
the 16-frequency stage ran away. The checkpoint's local iteration 480 is
not the total updates across preceding stages.

The whole failure folder is preserved [here](../../../../results/_probes/gaugal_convergence/2026-11-19/failed_before_step_safeguard/circle__c0.5),
including fit.json, score.json, arrays, logs and traceback. It was moved
only after the original CLI finished the eight remaining weak cases.

After: source `de5422c0d2b7119297fd83bf711e985c9e28e28f`, outcome **FAILED**,
stop restart_limit, 400.504 s, 5012 total attempted updates.
At 16 frequencies, steps 0.2 and 0.1 were rejected; step 0.05 completed.
At 19 frequencies, steps 0.05, 0.025 and 0.0125 were rejected. Four allowed
halvings were exhausted; there were five rejected attempts in total.
The fit returned its last accepted 16-frequency image. That image's
separate score is 4.6954%; its weighted mismatch is 0.0009574062 and
its worst frequency residual is 0.02123799. It is not a completed fit.

See [stage attempts](../../../../results/gaugal/converged_clean_uc_fc/circle__c0.5/stages.json) and
[saved-image score](../../../../results/gaugal/converged_clean_uc_fc/circle__c0.5/score.json). The saved predictions have
16 frequency rows, so the all-19-frequency output check is false as expected.

After the first pass the coordinator reported the code agent's finding: each stage
after the first reset the TV auxiliary to zero on a non-flat image, smearing
the stage start and causing false circle rejections. This first pass is
therefore evidence of that implementation. Activity 07 will refit all 20
with the fixed code only after the coordinator's go. Activity 07 uses a separate tvwarm run folder; no first-pass result
is replaced, and the failed circle is not counted as recovered.

## Pauses and timings

- BEM GPU sharing began at 15:15:51 UTC. All four then-running GauGal fits
  were paused at 15:16:53 and resumed at 15:18:57: 124 seconds. The affected
  probe and simultaneous-frequency raw times include that pause.
- From 16:04:26 to 19:19:41 UTC, the two cap-2000 probes and their collector,
  plus the simultaneous-frequency peanut child, CLI and monitor, were
  paused for continuation: 11,715 seconds (3 h 15 min 15 s). The coordinator
  resumed all six with SIGCONT. Their wall/optimization times include it.
- The continuation CLI parent alone was paused from 17:38:34 to 17:42:08:
  214 seconds. Its kite child continued. Overall CLI wall includes it;
  the child's case timer was not suspended.
- Continuation circle__c4 shared the GPU. Peanut__c4 began about 26 seconds
  before the dedicated allocation; star__c4 and subsequent cases ran alone.
  Dedicated runs cost about 630 seconds per case; failures cost less.

The first continuation CLI started 15:28:12 UTC; the final circle retry
ended 19:18:29 UTC: 3 h 50 min 17 s elapsed, including the parent-only pause.
Case seconds in the table are saved raw case times, not standalone speed
benchmarks. Exact-solve probes ran 14:40:27–14:44:42 UTC (4 min 15 s).

## Probe results

Step 1: both retained cap-2000 probes completed ten iterations after the
23:00:47 resume. Raw times include pauses and GPU sharing; no time stop was used.
The saved cap-100 runs have 80 iterations, so their solve shares are over a different trajectory.

| Case | Cap | Iterations | Unconverged inner solves % | Worst inner residual | Raw seconds/iteration | Area error % |
|---|---:|---:|---:|---:|---:|---:|
| kite__c4 | 2000 | 10 | 90.7268 | 0.03036324 | 1706.407 | 108.3943 |
| kite__c4 reference | 100 | 80 | 73.8150 | 0.03924051 | 4.042 | — |
| kite__c0.5 | 2000 | 10 | 93.2331 | 0.03233052 | 1716.529 | 58.1964 |
| kite__c0.5 reference | 100 | 80 | 71.4613 | 0.5299407 | 3.971 | — |

Mismatch fell from 19 to 17.8972393 (c4) and 10.9146399 (c0.5).
Increasing the cap to 2,000 did not make the old inner solves converge.
The existing exact-solve probes above and below are separate numerical paths.

Step 2: cancelled by the coordinator; nothing launched.

Step 3: exact-solve code 86232abe1, clean kite__c4, 200 iterations per
step, convergence=CONVERGENCE, max_seconds=None. Mismatch only; no truth
scores were computed for these probes.

| Step | Iterations | Weighted mismatch start → end | Seconds/iteration | Worst checked inner residual | Stop |
|---:|---:|---:|---:|---:|---|
| 0.2 | 200 | 19 → 10.1109053 | 1.13543 | 7.47928e-7 | iteration_limit |
| 1.0 | 200 | 19 → 10.0824825 | 1.13678 | 1.08491e-6 | iteration_limit |

Both mismatches still fell over the last 20 evaluations. Step 1.0 had small
intermediate rises; neither blew up or reached the plateau rule. All checked
inner solves converged; images and 19-by-24 predictions were finite.

## Simultaneous-frequency campaign still running

One detached runner owns the ten clean c0.5 cases; two runners were avoided
because metrics.csv is shared without a lock. The first completed circle
used 364 iterations, mismatch_plateau, area 76.2861%, mismatch 5.8761999,
291.806 s. Kite used 2,802 iterations, mismatch_plateau, area 9.9849%,
mismatch 0.000223769, 2,282.942 s including the 124-second BEM pause.
Both had zero unconverged checked inner solves. Peanut was paused mid-fit
and resumed at 19:19:41. It then finished; star became the active child.
The first-case forecast is no longer applicable.
Peanut's saved result: area 5.7253%, worst frequency residual
0.009207558, 3000 iterations, iteration_limit,
14024.226 raw seconds including the long pause.
No noisy cases or simultaneous-frequency c4 cases were launched here.

At 19:23:14 UTC the coordinator paused probes 1895339/1895343, collector
1903073, CLI 1899688 and monitor 1899680 for activity 07. Peanut child
1921897 had ended. Its successor star child 2035661 was paused at
19:23:23 UTC. The coordinator resumed these six jobs with SIGCONT at 23:00:47 UTC.
The second pause lasted 13,053 seconds (3 h 37 min 33 s), or 13,044 seconds
for star child 2035661. Raw timings include both long pauses. The existing
runs now continue without a time stop; no further numerical work is launched.

## Evidence and activity report

[Continuation run](../../../../results/gaugal/converged_clean_uc_fc),
[old defaults](../../../../results/gaugal/default_clean_uc_fs),
[probe evidence](../../../../results/_probes/gaugal_convergence/2026-11-19),
and [closed continuation pause](../../../../results/_probes/gaugal_convergence/2026-11-19/pause_for_continuation.json).
Per-case JSON and arrays are canonical; shared metrics.csv is derived.
Completed arrays, checks and source commits were pushed in case batches.

```text
Activity: evaluate_our_method/06_make_gaugal_fits_converge, 2026-11-19
Runs: continuation 19/20 nonfailed, 1 FAILED; wall time 3:50:17 including retry and parent pause
Result: c4 9/10 area <=5%; c0.5 1/9 nonfailed area <=5%; total 10/20 planned, old default 0/20
Result: circle__c0.5 FAILED after safeguard; saved-image score 4.6954% reported separately
Result: exact step probes 0.2/1.0 ended at mismatch 10.1109053/10.0824825 after 200 iterations each
Result: cap-2000 probes finished; simultaneous campaign 3/10 saved; six jobs resumed 23:00:47 after activity 07; results pending
Failures: old circle adjoint exception archived; safeguarded circle restart_limit kept in canonical run
Upstream patches: none by native-run
Changes to our code: none by native-run; scratch reporting helpers and saved evidence only
New unknowns: cap-2000 final statistics; remaining simultaneous results; results after TV stage-start fix
Proposed next activity: 07_refit_gaugal_with_tv_warm_start, all 20 clean cases; needs user decision: none; coordinator released activity 07 on code 94c39f4c0
```
