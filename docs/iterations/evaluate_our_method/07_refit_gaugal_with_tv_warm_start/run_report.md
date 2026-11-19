# GauGal TV warm-start refit — launch status

19 November 2026, UTC. **Launch failure; no numerical fit started.**
There is no recovery count for activity 07 yet. This is not a 0/20 result.

The CLI launched at 19:26:09 UTC under gaugal/converged_clean_uc_fc and
refused before fitting: the TV warm-start change differs from the saved
run.json settings. The old run.json was not changed. The attempted command,
traceback, launch/state files and reporting log are preserved in
[the launch-failure folder](../../../../results/_probes/gaugal_convergence/2026-11-19/tv_warm_start_launch_failure/).

The coordinator corrected the plan: activity 07 gets its own run name,
`gaugal/tvwarm_clean_uc_fc`. The code agent is adding it; native-run waits
for the coordinator's go with that commit. The prepared order is circle c0.5,
the other nine c0.5 cases, then ten c4 cases, with unchanged settings.

All 20 first-run case folders are restored whole with git mv under
[converged_clean_uc_fc](../../../../results/gaugal/converged_clean_uc_fc/).
Their hashes match the pre-move records. The first-run report's links are
restored. Circle c0.5 remains FAILED in that report, with its saved-image
score separate from the nonfailed count.

The six lower-value jobs remain paused: probes 1895339/1895343, collector
1903073, CLI 1899688 and monitor 1899680 at 19:23:14 UTC; star child 2035661
at 19:23:23 UTC. No job was resumed or killed by this preparation.

```text
Activity: evaluate_our_method/07_refit_gaugal_with_tv_warm_start, 2026-11-19
Runs: no numerical fits started; launch failed before fitting
Result: first-run evidence restored whole; separate tvwarm run prepared, awaiting coordinator go
Failures: saved run.json settings mismatch; traceback in tv_warm_start_launch_failure/tv_warm_start_runner.log
Upstream patches: none by native-run
Changes to our code: none by native-run; scratch reporting helper prepared
New unknowns: results of all 20 fixed clean fits
Proposed next activity: launch gaugal/tvwarm_clean_uc_fc on coordinator's code commit; needs user decision: coordinator go
```
