# Fit the ten simulated CSI cases at five frequencies: results

18 November 2026, 04:01 to 05:34 UTC. Runner: `bem-csi-run`. Plan: [plan.md](plan.md).
Data: frozen five-frequency tables, 0.5, 1, 1.5, 2 and 2.5 GHz, 8820 rows each, SHA-256 checked.
Evidence: `results/bem/baseline_data/csi_five_frequency/2026-11-18/` (checks in `adapter_checks/`,
fits in `<shape>__c4/<device>/attempt_01/`, logs, waiter script and state in `logs/`).
Settings as in the plan. Solver clean in every manifest. No fit was rerun and nothing was retuned.
Scores come from the unedited `experiments/comparison/scoring.py`, read after each fit.

## 1% checks (CPU, true shape; worst of the two resolutions)

All ten pass. Worst mismatch over the five frequencies: aphex_twin 0.713% (2.5 GHz), then
cog 0.400%, star 0.416%, circle 0.442% (0.5 GHz). Table in the 04:07 report to the coordinator;
numbers are in each `adapter_checks/<shape>__c4.json`.

## GPU fits (the reported result)

All ten ended `COMPLETED_SCHEDULE`. Area error, centre offset and contrast are against the truth
(contrast truth 4). Every result is one component, no holes.

| Shape | Last stage | Work units | Fit seconds | Peak memory host / GPU (GiB) | Area error | Centre offset (mm) | Contrast |
|---|---|---|---|---|---|---|---|
| circle | `full_6_M37` | 4477 | 200 | 1.83 / 0.83 | 0.97% | 0.010 | 4.0002 |
| kite | `full_6_M37` | 3500 | 194 | 1.81 / 0.83 | 3.80% | 0.021 | 4.0024 |
| peanut | `full_6_M37` | 4264 | 144 | 1.83 / 0.83 | 1.54% | 0.013 | 4.0018 |
| star | `full_6_M37` | 1464 | 47 | 1.83 / 0.83 | 2.34% | 0.015 | 4.0017 |
| asymmetric | `full_6_M37` | 2241 | 65 | 1.84 / 0.83 | 1.29% | 0.018 | 4.0020 |
| c_shape | `full_6_M37` | 2243 | 105 | 1.86 / 0.83 | 2.60% | 0.032 | 4.0027 |
| hook | `full_6_M37` | 2312 | 162 | 1.83 / 0.83 | 3.59% | 0.019 | 4.0054 |
| cross | `full_6_M37` | 1839 | 51 | 1.83 / 0.83 | 2.10% | 0.012 | 4.0012 |
| cog | `full_8_M49` | 3619 | 247 | 1.87 / 0.87 | 2.86% | 0.037 | 4.0005 |
| aphex_twin | `full_6_M37` | 3039 | 195 | 1.85 / 0.83 | 5.96% | 0.107 | 3.9970 |

Median area error 2.47%; worst aphex_twin 5.96%. All used far fewer than 13,412 units.
(Corrected by the coordinator, 18 Nov 07:51 UTC: this line and the report block said 2.2%,
the mean of the fourth and fifth value. From the ten `metrics.json` files: mean 2.71%, median 2.47%.)
Times are indicative (shared machine). Circle, kite and peanut ran at 04:03 to 04:12; the rest
waited from 04:12 to 04:53 behind the memory count (see below).

## CPU cross-checks (stop at 120 s by design)

All ten stopped at the 120 s limit (`TRIAL_WALL_LIMIT`) inside stage 1 to 3 of the full stages,
so none reaches an end result to compare with the GPU. Partial area error at the stop:
circle 0.44%, kite 4.30%, peanut 1.99%, star 2.16%, asymmetric 1.14%, c_shape 1.92%, hook 1.88%,
cross 1.86%, cog 12.65%, aphex_twin 10.92% (partial, not final). Stages both devices finished, from
the saved `metrics.json` files only (the CPU stage cut by the limit is excluded; no run):

| Shape | Stages finished on both | Last such stage | Largest relative `final_loss` difference (stage) | Contrast difference at the last such stage | Accepted steps equal |
|---|---|---|---|---|---|
| circle | 5 | `ladder_5_real` | 4.8e-13 (`ladder_5_real`) | 2.0e-12 | yes |
| kite | 5 | `ladder_5_real` | 4.9e-10 (`ladder_3_real`) | 1.1e-11 | yes |
| peanut | 5 | `ladder_5_real` | 7.9e-10 (`ladder_5_real`) | 2.3e-12 | yes |
| star | 7 | `full_2_M15` | 1.1e-11 (`ladder_4_real`) | 2.8e-12 | yes |
| asymmetric | 6 | `full_1_M11` | 2.0e-11 (`ladder_5_real`) | 6.0e-12 | yes |
| c_shape | 6 | `full_1_M11` | 8.1e-10 (`ladder_3_real`) | 3.8e-12 | yes |
| hook | 6 | `full_1_M11` | 3.8e-9 (`ladder_5_real`) | 1.1e-12 | yes |
| cross | 7 | `full_2_M15` | 7.3e-11 (`full_1_M11`) | 1.3e-12 | yes |
| cog | 5 | `ladder_5_real` | 2.2e-10 (`ladder_4_real`) | 8.3e-12 | yes |
| aphex_twin | 5 | `ladder_5_real` | 1.9e-9 (`ladder_5_real`) | 1.3e-10 | yes |

Same stage names and outcomes (`NORMAL_OPTIMIZER_RETURN`) on both devices in every common stage.
Largest loss difference overall 3.8e-9 (hook); largest contrast difference 1.3e-10 (aphex_twin).
So CPU and GPU agree through the common stages. The CPU never reaches the end of the fit, so
agreement of the final result is not shown.

## What went wrong, kept

- From 04:12 to 04:53 no fit started although a slot was free. My waiter counted only the top
  MATLAB process's memory, so its outstanding growth (7.5 GiB) was above the monitor's (4.1 GiB).
  The coordinator asked for a fix; the waiter now sums each job with its descendants and reads
  the reservations from the policy file (commit `10f5f1153`). Then `star` started at 04:53:19.
  No fit was affected; only the start was late.
- Two pushes were rejected by the remote at 04:04 and 04:07 (ref lock, pack write). The waiter
  retried and they went through.

## Report block

```text
Activity: adapt_bem_to_baseline_data/07_fit_csi_cases_at_five_frequencies, 18 Nov 2026
Runs: 10 checks, 10 GPU fits, 10 CPU cross-checks (120 s cut); one waiter, restarted once; wall time 1:33
Result: all ten checks pass (worst 0.713%); all ten GPU fits COMPLETED_SCHEDULE; area error 0.97% (circle) to 5.96% (aphex_twin), median 2.47%; contrast within 0.0054 of 4 (aphex_twin 3.9970); all CPU runs stopped at 120 s
Failures: none in the fits; 40 min start delay from a memory count that differed from the monitor's (fixed); two transient push rejections
Upstream patches: none
Changes to our code: none (only the runner's own waiter script, logs/waiter.py)
New unknowns: shown: CPU and GPU agree through the 5 to 7 stages both finished (loss within 3.8e-9 relative, contrast within 1.3e-10, same accepted steps); not shown: the end of the fit on the CPU, which stops at 120 s in stage 1 to 3 of the full stages
Proposed next activity: score against the CSI results on the same tables; optionally uncut CPU cross-checks (needs the user's decision on the 120 s cut)
```
