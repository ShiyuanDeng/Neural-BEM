# GauGal refit with TV warm start — native-run report

19 November 2026, UTC. TV fix 94c39f4c0; separate variant ecf3bddbb. One detached runner; circle c0.5 first, then the other nine c0.5 cases, then ten c4 cases. Settings follow plan.md unchanged; there is no time stop. The earlier converged-name launch failed before any fit; its records remain in tv_warm_start_launch_failure.

The first run is preserved whole under [converged_clean_uc_fc](../../../../results/gaugal/converged_clean_uc_fc/). Its circle c0.5 area value is the separately scored saved image of a FAILED fit. Truth scores do not select steps or restarts.

| Case | Area error % | First run area % | Worst frequency residual | Final step | Restarts | Plateau stages | Outcome | Seconds | Start commit |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| circle__c0.5 | 6.0992 | 4.6954 | 0.01329404 | 0.05 | 2 | 0 | STOPPED_EARLY | 630.913 | ecf3bddbb54d3f7099e87fd7a517b6ba60b0761b |
| kite__c0.5 | 7.5008 | 7.5754 | 0.009110976 | 0.2 | 0 | 0 | STOPPED_EARLY | 629.974 | a8516124ca84435c49a5581298e440376b85cbb5 |
| peanut__c0.5 | 5.3000 | 5.4092 | 0.01161834 | 0.1 | 1 | 0 | STOPPED_EARLY | 631.343 | a8516124ca84435c49a5581298e440376b85cbb5 |
| star__c0.5 | 7.9694 | 8.0832 | 0.007806763 | 0.2 | 0 | 1 | STOPPED_EARLY | 625.858 | 5cac0d6137fe02e9738b7310be77aac6863f702e |
| asymmetric__c0.5 | 5.4663 | 5.4953 | 0.01119681 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.042 | 5cac0d6137fe02e9738b7310be77aac6863f702e |
| c_shape__c0.5 | 9.1328 | 9.2058 | 0.01184179 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.158 | ee57f55463d8ad2b76b58b812d962daa75d7f255 |
| hook__c0.5 | 15.6299 | 15.7241 | 0.006108942 | 0.2 | 0 | 0 | STOPPED_EARLY | 629.981 | ee57f55463d8ad2b76b58b812d962daa75d7f255 |
| cross__c0.5 | 7.6442 | 7.6708 | 0.009303573 | 0.2 | 0 | 0 | STOPPED_EARLY | 629.941 | 9746502fe29dece7a77c83810cfc512ec18ba9d0 |
| cog__c0.5 | 4.6523 | 4.6665 | 0.01456093 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.034 | 9746502fe29dece7a77c83810cfc512ec18ba9d0 |
| aphex_twin__c0.5 | 16.9467 | 17.0111 | 0.0155039 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.178 | 458d61743621c498dacee2226310249994079a77 |
| circle__c4 | 2.0536 | 2.3553 | 0.07775004 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.504 | 458d61743621c498dacee2226310249994079a77 |
| kite__c4 | 3.0951 | 2.9655 | 0.05388925 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.335 | a7d6974859b780eff580ef7890fa5d3e89e71b03 |
| peanut__c4 | 1.7206 | 1.6270 | 0.05622402 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.222 | a7d6974859b780eff580ef7890fa5d3e89e71b03 |
| star__c4 | 2.2331 | 2.0065 | 0.07461919 | 0.2 | 0 | 0 | STOPPED_EARLY | 630.431 | 06e78152035c191c5255b16cdd3dc3a4f664468a |

Plateau stages count saved stage stop reasons containing plateau. STOPPED_EARLY/iteration_limit means the configured cap was reached, not outer convergence. Failed saved images are scored diagnostically and excluded from successful-fit counts. Worst frequency residual is an endpoint data residual; inner residuals are checked separately.

Lower-value probes and simultaneous-frequency fits were paused by the coordinator: five PIDs at 19:23:14 UTC, star child 2035661 at 19:23:23 UTC. They remain paused until the coordinator resumes them. No prior activity pause is subtracted from raw case times.

```text
Activity: evaluate_our_method/07_refit_gaugal_with_tv_warm_start, 2026-11-19
Runs: 14/20 nonfailed, 0 failed, 6 pending; wall time 2:27:16
Result: 5/20 planned cases have area <=5%; per-case results above
Failures: none saved
Upstream patches: none by native-run
Changes to our code: none by native-run; scratch reporting helpers only
New unknowns: remaining clean case results
Proposed next activity: review with coordinator; needs user decision: none
```
