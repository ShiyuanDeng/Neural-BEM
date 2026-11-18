# Fit the ten simulated CSI cases at five frequencies: plan

18 November 2026. Written by the BEM coordinator (pane `w2:p1`) before any
result on this list exists. Runner: `bem-csi-run`. This is the reported pass
for the BEM row of table C (simulated cases). Authority:
[coordinate_bem_side.md](../../coordinate_bem_side.md).

## The user's choice

In the baseline coordinator's pane (`w1:p1`), 18 Nov 2026, 03:39 UTC:

> Use [0.5, 1, 1.5, 2, 2.5] GHz for all ten C-simulated BEM cases and the
> remaining seven MF-CC-CSI cases. Prepare and freeze the missing-frequency
> data, and give the same observations to both methods. [...] Queue
> preparation, checks and fits with the resource monitor; launch as capacity
> allows without interrupting existing fits. Keep the previous three CSI fits
> as separate eight-frequency results.

This replaces the 1 to 3 GHz list and ends the hold. The early look at 1 to
3 GHz ([activity 04](../04_fit_csi_cases/results.md)) stays as it is.

## Questions

For each of the ten TG-002 shapes at contrast 4 in the Fresnel layout:

1. Does our forward agree with the frozen five-frequency table on the true
   shape, within 1% at each of the five frequencies?
2. How well does our default BEM inverse recover the shape and the contrast
   from that table? One GPU fit per shape is the reported result.

## Data (read only)

- One frozen table per shape, made by the baseline side:
  `results/csi/tg002/2026-11-18_five_frequency_data/<shape>/forward/synthetic_input.txt`,
  with a `.sha256` beside it. 8820 rows; all five frequencies are used.
- Both methods read these same files. The check and the fit verify the
  `.sha256` first and record the table's SHA-256.
- A shape is touched only after the coordinator says its table is frozen.
  Never regenerate, copy or edit a table.

## Fixed settings (set before any result on this list)

- Default method, unchanged: centred 65 mm circle start, `modal_muller` +
  `slider`, real data only, no localization, no warm-up, no noise level,
  recovered contrast from the weak-scatterer start, series limit 1e-9,
  13,412 work units. Table mode and frequency blocks adapt the data layout.
- Frequency rule, as fixed on 18 Nov at 01:39 for any list: the ladder adds
  one frequency at a time, lowest first, up to the larger of 3 GHz and half
  the top frequency; then the default all-frequency stages on the whole list.
  All five frequencies lie below 3 GHz, so the ladder has five stages:
  0.5; 0.5–1; 0.5–1.5; 0.5–2; 0.5–2.5 GHz.
- Ladder shape bands by the default's own rule (three times the top
  wavenumber, rounded down): 1, 3, 4, 6, 7. The default TG-002 ladder has
  3, 5, 7, 9.
- Ladder quotas 1000, 1000, 1000, 1000, 4000 (coordinator, 03:55 UTC). First
  and last as the default; the default's middle 3000 units are shared equally
  by the three middle stages. The ladder total stays 8000 and the fit total
  13,412.
- No stop on elapsed time for the GPU fit (was a 1 h ceiling). The user:
  "treat elapsed-time targets as reports rather than reasons to stop". Stop a
  fit only if it is stuck, faulty or short of memory.
- The CPU cross-check keeps its 120 s cut. It is a cross-check, not a result.
- The stage list is in
  [policy_dry_check.json](../../../../results/bem/baseline_data/csi_five_frequency/2026-11-18/policy_dry_check.json).
  The same code still reproduces the saved plans of the measured cylinder and
  of the early look, apart from the removed time ceiling.

## Checks before a fit

- Per shape: `csi_forward_check.py` on the true shape. It checks the row
  order, the unit source field, the series limit, and the mismatch at each
  frequency at two resolutions.
- The 1% rule: the worst mismatch over the five frequencies must be at or
  below 1%. A shape above 1% is fitted by neither method. Stop that shape
  and tell the coordinator, who tells the baseline side and asks the user.
- The fit refuses to start without a passing check of the same table (same
  SHA-256) and the same frequency list.
- Send the ten check results to the coordinator as soon as they exist: the
  seven CSI fits wait for them.

## Order

1. When the coordinator says the tables are frozen: all ten checks, one
   after another (CPU, about 10 s each). Commit, push, report the check table.
2. GPU fits for every shape that passed, in the order circle, kite, peanut,
   star, asymmetric, c_shape, hook, cross, cog, aphex_twin, as the resource
   rule below allows. Commit and push after each fit, failures included.
3. Report the first finished fit (outcome, last stage, units, seconds, peak
   memory, area error) and go on without waiting.
4. After the ten GPU fits: the CPU cross-checks, one at a time, each
   counted as a BEM fit under the same rule.
5. Final report block; write `results.md` in this folder.

## Commands

From the repository root. The defaults now point at this pass, so give no
`--out` to the fit.

```bash
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
R=results/bem/baseline_data/csi_five_frequency/2026-11-18
S=<shape>__c4
$P experiments/bem_on_baseline_data/csi_forward_check.py --out $R/adapter_checks --cases $S
mkdir -p $R/logs
setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cuda > $R/logs/${S}_cuda.log 2>&1 < /dev/null &
CUDA_VISIBLE_DEVICES= setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cpu > $R/logs/${S}_cpu.log 2>&1 < /dev/null &
```

Outputs: `$R/adapter_checks/<case>.json`; `$R/<case>/<device>/attempt_NN/`
with `manifest.json` (settings, table and row SHA-256, commit),
`fit.json`, `metrics.json` and `local/`.

## Resources

- The resource monitor (pane `w3:p1`, set up by the user) writes its
  ceilings to `results/csi/resource_policy.json`. Read that file before
  every launch. `max_bem_fits` counts all BEM fits together: the B1 workers
  (`b1_run.py _fit`) and this pass (`csi_fit.py --case`). Launch a fit only
  while fewer than `max_bem_fits` are running.
- Memory, the monitor's rule: launch only if available memory minus 4 GiB
  stays at or above 16 GiB (the 14 GiB floor plus 2 GiB). The wrapper itself
  refuses below 16.5 GB, and its guard stops the fit below 14 GB.
  Early-look fits peaked near 2 GB host and 1.4 GB GPU.
- The 1% checks run on the CPU with one thread, about 10 s each. They take
  no GPU slot.
- Never stop or slow another job. Wait for a free slot on the result files,
  not on a timer that could stop a fit.
- Times are indicative: the machine is shared with the baseline runs.

## Success criteria

None for the method: this activity measures. Done means each of the ten
shapes has a recorded check and a recorded outcome (completed, failed,
crashed, or stopped by the 1% rule), scored with the unedited
`experiments/comparison/scoring.py`, and all is committed and pushed.

## Run budget

Ten checks, ten GPU fits, ten CPU cross-checks. No tuning reruns. A failed
or poor fit stays in the table. A crash is kept and reported; the runner
does not edit the wrapper or the solver.
