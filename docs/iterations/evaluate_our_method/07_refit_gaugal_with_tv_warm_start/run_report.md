# GauGal refit with TV warm start — native-run report

19 November 2026, UTC. TV fix 94c39f4c0; separate variant ecf3bddbb. One detached runner; circle c0.5 first, then the other nine c0.5 cases, then ten c4 cases. Settings follow plan.md unchanged; there is no time stop. The earlier converged-name launch failed before any fit; its records remain in tv_warm_start_launch_failure.

The first run is preserved whole under [converged_clean_uc_fc](../../../../results/gaugal/converged_clean_uc_fc/). Its circle c0.5 area value is the separately scored saved image of a FAILED fit. Truth scores do not select steps or restarts.

| Case | Area error % | First run area % | Worst frequency residual | Final step | Restarts | Plateau stages | Outcome | Seconds | Start commit |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| circle__c0.5 | 6.0992 | 4.6954 | 0.01329404 | 0.05 | 2 | 0 | STOPPED_EARLY | 630.913 | ecf3bddbb54d3f7099e87fd7a517b6ba60b0761b |
| kite__c0.5 | 7.5008 | 7.5754 | 0.009110976 | 0.2 | 0 | 0 | STOPPED_EARLY | 629.974 | a8516124ca84435c49a5581298e440376b85cbb5 |

Plateau stages count saved stage stop reasons containing plateau. STOPPED_EARLY/iteration_limit means the configured cap was reached, not outer convergence. Failed saved images are scored diagnostically and excluded from successful-fit counts. Worst frequency residual is an endpoint data residual; inner residuals are checked separately.

Lower-value probes and simultaneous-frequency fits were paused by the coordinator: five PIDs at 19:23:14 UTC, star child 2035661 at 19:23:23 UTC. They remain paused until the coordinator resumes them. No prior activity pause is subtracted from raw case times.

```text
Activity: evaluate_our_method/07_refit_gaugal_with_tv_warm_start, 2026-11-19
Runs: 2/20 nonfailed, 0 failed, 18 pending; wall time 0:21:04
Result: 0/20 planned cases have area <=5%; per-case results above
Failures: none saved
Upstream patches: none by native-run
Changes to our code: none by native-run; scratch reporting helpers only
New unknowns: remaining clean case results
Proposed next activity: review with coordinator; needs user decision: none
```
