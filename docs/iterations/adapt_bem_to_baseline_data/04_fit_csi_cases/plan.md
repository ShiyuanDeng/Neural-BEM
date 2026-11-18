# Fit the CSI simulated cases: plan

**Status label, 18 Nov 2026 (coordinator, after the user reopened the frequency set at 01:36 UTC): circle, kite and peanut are an early look at 1 to 3 GHz; the reported pass waits for the user's frequency list.** Nothing else is started. The other seven shapes wait for the final list and their table paths. Every file is kept when the list changes.

Agent `bem-csi-run`, 18 November 2026. This plan restates fixed settings. It
chooses nothing new. Authority: [coordinate_bem_side.md](../../coordinate_bem_side.md)
and the hand-over in
[activity 03 results](../03_adapt_bem_to_csi_data/results.md).

## Questions

For each of the ten TG-002 shapes at contrast 4 in the Fresnel layout: how
well does our BEM (default method on the CSI point-source table) recover the
shape from CSI's simulated data? One run per shape on the GPU is the reported
pass. A CPU run is a cross-check.

## Fixed settings (not changed here)

- Data: retained simulated tables, 1, 2 and 3 GHz rows only (user decision).
  No table is regenerated.
- Ladder 1; 1–2; 1–3 GHz, then the default all-frequency stages. Quotas
  1000, 3000, 4000. Centred 65 mm circle start. Recovered contrast. Series
  limit 1e-9. No noise level. No localization.
- Limits: 13,412 work units; 1 h ceiling per fit. CPU cross-check stops at
  120 s by design.
- Memory: a fit starts only with 16.5 GB available; the user's guard is
  14 GB. One or two fits at a time.
- Wrapper, solver, `experiments/comparison/` and the `csi` agent's paths are
  not edited. A crash is kept and reported.

## Order

1. Now: `circle`, `kite`, `peanut` (tables exist).
2. Per shape: (a) adapter and forward check on the true shape; stop and tell
   the coordinator if any of 1, 2, 3 GHz exceeds 1%; (b) GPU fit; (c) CPU
   cross-check. Flag any CPU/GPU difference.
3. After the first batch of three: stop and report to the coordinator.
   The other seven shapes wait for their table paths.

## Commands

Exactly the hand-over commands, with `S=<shape>__c4`, results in
`results/bem/baseline_data/csi_cases/`:

```bash
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
R=results/bem/baseline_data/csi_cases
$P experiments/bem_on_baseline_data/csi_forward_check.py --out $R/adapter_checks --cases $S
setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cuda > $R/logs/${S}_cuda.log 2>&1 < /dev/null &
CUDA_VISIBLE_DEVICES= setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cpu > $R/logs/${S}_cpu.log 2>&1 < /dev/null &
```

## Success criteria

None for the method: this activity measures. Done means each shape in the
batch has a recorded outcome (completed, refused, crashed or stopped by the
1% rule), the raw metrics are saved, and everything is committed and pushed.

## Run budget

Three shapes, one GPU and one CPU fit each. Timings are indicative: the
machine is loaded by the baseline campaigns.

## User choices

The user fixed the 1–3 GHz rows, the 1% rule, the frequency ladder, the
limits and the start. See "Decisions made with the user" in the coordinator
file.
