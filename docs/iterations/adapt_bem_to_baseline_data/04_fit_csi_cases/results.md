# Fit the CSI simulated cases: results

**Early look at 1 to 3 GHz; the reported pass waits for the user's frequency list.**

## State at handoff (18 November 2026, about 02:10 UTC)

**Done.** Early look at 1 to 3 GHz on circle, kite and peanut (contrast 4):
true-shape checks, three GPU fits and three 120 s CPU cross-checks, all
committed and pushed. Results are in the sections below. Nothing is running.

**Next.** All ten shapes as the reported pass, once the coordinator gives the
user's final frequency list and the table paths. The three early-look results
stay as they are; new runs go beside them. Do not start before that list.

**Before running anything:** `bem-csi` is changing the wrapper now. The tables
move to `results/csi/tg002/2026-11-18_low_band_data/` and the frequency list
becomes one dataset setting. Re-read the hand-over section of
[activity 03 results](../03_adapt_bem_to_csi_data/results.md) first; its
commands may differ from the ones below. Also re-read
[coordinate_bem_side.md](../../coordinate_bem_side.md) (Limits, Working with
the coordinator) and [plan.md](plan.md).

**Commands used (hand-over, at the time of the early look).** From the
repository root, `P=/home/drdeng/miniconda3/envs/EMNerf/bin/python`,
`R=results/bem/baseline_data/csi_cases`, `S=<shape>__c4`:

```bash
$P experiments/bem_on_baseline_data/csi_forward_check.py --out $R/adapter_checks --cases $S   # stop if the 1% rule fails
mkdir -p $R/logs
setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cuda > $R/logs/${S}_cuda.log 2>&1 < /dev/null &
CUDA_VISIBLE_DEVICES= setsid nohup $P experiments/bem_on_baseline_data/csi_fit.py --case $S --device cpu > $R/logs/${S}_cpu.log 2>&1 < /dev/null &
```

Start a fit only with 16.5 GB available (guard 14 GB); one or two at a time.
Each fit peaks near 1.8 GB host and 0.8 GB GPU. GPU fits took 1 to 3 min,
CPU fits stop at 120 s.

**Pitfalls met.**

- Give no `--out` or `--checks`: the defaults are right. A relative `--out`
  crashes the record step (`relative_to`). If you must pass one, make it
  absolute.
- An attempt with `fit.json` but no `metrics.json` is not completed by the
  wrapper. A rerun starts a fresh `attempt_NN` and refits. The fit itself
  repeats exactly on the GPU, so nothing is lost, but both attempts stay. Use
  the attempt with `metrics.json` as the row. Report it; do not edit the
  wrapper.
- `pgrep -f` in a wait loop matches its own shell, so the loop never ends.
  Wait on the result files instead.
- The kite GPU fit ended `NUMERICAL_FAILURE` in its last stage. Keep such
  outcomes in the table; no tuning reruns.

**Rules that bind you** (from the coordinator's brief): never edit the
wrapper (`experiments/bem_on_baseline_data/csi_*`), the solver,
`experiments/comparison/` or the `csi` agent's paths; never regenerate a
table; commit and push by path after each fit, failures included; stop and
report in your pane after each batch, with the report block; ask the
coordinator, not the user.

Circle, kite and peanut at contrast 4, 18 November 2026, 01:35 to 02:05 UTC.
Plan: [plan.md](plan.md). Evidence: `results/bem/baseline_data/csi_cases/`
(`<shape>__c4/<device>/attempt_NN/metrics.json`, `fit.json`, `manifest.json`;
logs in `logs/`; checks in `adapter_checks/`). Commands are the hand-over
commands. Solver clean in every manifest. The machine was loaded (load 23 to
32, about 50 MATLAB processes), so times are indicative.

## True-shape check (1% rule at 1, 2, 3 GHz)

| Shape | Worst mismatch at 1 to 3 GHz | Rule |
|---|---|---|
| circle | 0.30% | pass |
| kite | 0.34% | pass |
| peanut | 0.17% | pass |

## GPU fits (the early look)

Scores from the unedited `experiments/comparison/scoring.py`, read after the
fit. Area error and centre offset are against the truth. Contrast is the
recovered value (truth 4).

| Shape | Outcome | Last stage | Work units | Fit time | Peak memory (host / GPU) | Area error | Centre offset | Contrast | Residual 1 / 2 / 3 GHz |
|---|---|---|---|---|---|---|---|---|---|
| circle | `COMPLETED_SCHEDULE` | `full_6_M37` | 1987 | 71 s | 1.74 / 0.82 GiB | 1.17% | 0.010 mm | 4.0006 | 0.146 / 0.115 / 0.116 % |
| kite | `NUMERICAL_FAILURE` | `full_6_M37` | 2216 | 178 s | 1.75 / 0.82 GiB | 3.08% | 0.026 mm | 4.0013 | 0.158 / 0.064 / 0.083 % |
| peanut | `COMPLETED_SCHEDULE` | `full_6_M37` | 2386 | 123 s | 1.76 / 0.82 GiB | 1.50% | 0.019 mm | 4.0014 | 0.165 / 0.085 / 0.083 % |

All three are one component, no holes. Every fit used far fewer than the
13,412 units and stopped well inside the 1 h ceiling.

Kite: the sixth stage (`full_6_M37`) stopped with "production evaluation
failed at candidate state" after 6 accepted steps. Stages 1 to 5 returned
normally. The record is kept as the outcome of the fit; I did not retry it.
Stopped fits stay in the table.

## CPU cross-check (stops at 120 s by design)

All three stopped at the 120 s wall limit (`TRIAL_WALL_LIMIT`), so none
reached the end. Where both devices finished the same stage they agree:

| Shape | Stages both completed | Accepted steps | Largest loss difference | Largest contrast difference |
|---|---|---|---|---|
| circle | ladder 1 to 3, `full_1_M11` | same (7, 4, 3, 22) | 4e-7 relative | 3.5e-10 |
| kite | ladder 1 to 3 | same (10, 6, 5) | 4e-9 | 1e-9 |
| peanut | ladder 1 to 3, `full_1_M11` | same (9, 6, 5, 6) | 5e-8 | 8e-10 |

The CPU stopped inside the next stage (circle `full_2_M15`, kite
`full_1_M11`, peanut `full_2_M15`), so it has no end result to compare. The
CPU's partial scores (area error 1.22%, 2.68%, 1.44% for circle, kite, peanut)
are not final. No outcome or step-count difference was found on any stage both
devices completed.

## Failure, kept: relative `--out` path

I first started circle and kite on the GPU with a relative `--out` (my
argument error, not a wrapper bug). The fits ran and wrote `fit.json`; the
record step then failed (`relative_to` on a relative path) and no
`metrics.json` was written. Logs: `logs/relative_out_record_failure/`.
Rerunning the exact hand-over command made a **new** `attempt_02` and refitted,
because the wrapper completes an attempt only when a `metrics.json` already
exists. The fit-from-`fit.json` completion that the hand-over describes does
not cover a record step that fails before `metrics.json` is written. Reported
to the coordinator; not edited.

The refits are a free repeat of the GPU fits. For circle and kite, `fit.json`
of `attempt_01` and `attempt_02` is identical in every value except times, so
the GPU fit repeats exactly. The reported rows above use `attempt_02`. Both
attempts are kept.

## Not run

The other seven shapes (star, asymmetric, c_shape, hook, cross, cog,
aphex_twin): the coordinator's instruction; they wait for the final frequency
list and their table paths.

## Report block

```text
Activity: adapt_bem_to_baseline_data/04_fit_csi_cases, 18 Nov 2026 (first batch, early look at 1 to 3 GHz)
Runs: 8 fits run for 3 shapes (circle and kite GPU twice, peanut GPU once, CPU once each); first batch of 3 of 10 shapes; wall time about 0:30
Result: circle 1.17% area, 0.010 mm; kite 3.08% area (numerical failure in the last stage), 0.026 mm; peanut 1.50% area, 0.019 mm; CPU agrees on every stage it completed
Failures: kite stage full_6_M37 numerical failure (logs/kite__c4_cuda.log); relative --out record failure on circle and kite attempt_01 (logs/relative_out_record_failure/)
Upstream patches: none
Changes to our code: none
New unknowns: whether the kite failure repeats in later stages under the user's final frequency list; wrapper does not complete an attempt that has fit.json but no metrics.json
Proposed next activity: the other seven shapes after the user's frequency list; needs user decision: the frequency list
```
