# MF-CC-CSI simulated TG-002 campaign

**Final first-batch review, 18 November 2026.** Circle, kite and peanut
completed all 2048 iterations at 1–8 GHz. The launcher exited naturally
at 02:00 UTC and pushed `984771ca8` and `bff0fd4a8`. Remaining fits are
held for the user's review and a new go with the frequency list.
The historical nine-hour check below did not cut any of these fits.

Full review: [review_pack.md](review_pack.md), with every 256/512/1024/2048
score at thresholds 0.3/0.5/0.7, mean permittivity, contrast error, final
costs and timing. Raw rows are in batch_1_review.csv/json under the campaign
root. The final figure is [figures/batch_1.png](figures/batch_1.png).

Final main-threshold area errors: circle 13.6723%, kite 16.1103%, peanut
21.1298%. Mean permittivities: 3.431334, 3.254061, 3.209469; relative
contrast errors: 14.2166%, 18.6485%, 19.7633%. Native rates: 4.741846,
4.727651, 4.736674 seconds per iteration. Campaign wall time: 2:43:24.
The completed first-batch forecast was 10.909 h against the original 9 h
figure; it is retained as history. Current time limits are targets only.

All return codes were zero. Four finite raw arrays and full metadata
were checked per fit. All per-case manifest bytes/hashes and 2048 cost
rows passed; the original 29 source hashes still match. The unchanged
MATLAB wrapper checked exact final/checkpoint equality. No native setting
was shortened or dropped. Timings include concurrent BRG/BEM work.

Threshold sensitivity is large. At 0.7, kite splits into three components
and peanut has two holes. Circle's main area error is not monotone across
saved iterations. Native ChiErr compares with the initial guess, not truth.
These are recorded in the review pack; no threshold was selected after
seeing truth. The figure shows recognisable silhouettes, with halos and
nonuniform recovered interiors.

All ten full parent tables are now frozen for BEM at
results/csi/tg002/2026-11-18_low_band_data/{shape}/forward/synthetic_input.txt.
Their paths/hashes and initial 1–3 GHz row selection are in
[the data note](../05_run_simulated_tg002_cases_at_1_to_3_ghz/data_note.md).
The next launcher has one explicit frequency setting, reuses every parent
by hash, never regenerates inputs, and remains unlaunched.

## Coordination report

```text
Activity: csi_adaptation/04_run_simulated_tg002_cases, 18 November 2026
Runs: 3/10 originally planned; remaining 7 held; wall time 2:43
Result: circle — area error 13.6723%, mean epsilon 3.431334, contrast error 14.2166%
Result: kite — area error 16.1103%, mean epsilon 3.254061, contrast error 18.6485%
Result: peanut — area error 21.1298%, mean epsilon 3.209469, contrast error 19.7633%
Failures: none in the three fits; all 2048 iterations and snapshot scores retained
Upstream patches: external/patches/cc-csi/0001,0002 compatibility; 0003 output-only owned copy
Changes to our code: CSI wrappers/review/data preparation only; no solver or scoring changes
New unknowns: final frequency choice; isolated timing; threshold sensitivity; each other shape's independent forward check
Proposed next activity: review this pack, then choose the remaining-case frequency list; needs user decision: new go and frequency list
```

## Automatically recorded campaign evidence

Updated 2026-11-18T02:00:18.093343+00:00. State: **awaiting coordinator: first-batch forecast exceeds nine hours**.

Nine-hour budget. Ten shapes, contrast 4, 2048 iterations, native back-propagation start.
Grid 166-by-166 at 1.25 mm; native forward 332-by-332 at 0.625 mm. No settings shortened.

Snapshot scores use unchanged protocol-1 image helpers. Area error is symmetric difference over true area.
Contrast error is relative error of mean epsilon_r in the half-peak support against 4.

| Case | Iterations | Area error % | Support mm2 | Mean epsilon_r | Contrast error % | Centre error mm | Native elapsed s |
|---|---:|---:|---:|---:|---:|---:|---:|
| circle | 256 | 12.873 | 8865.023 | 3.1495 | 21.2624 | 1.6662 | 1105.367 |
| circle | 512 | 14.166 | 8966.601 | 3.2849 | 17.8775 | 1.6227 | 2146.683 |
| circle | 1024 | 14.416 | 8986.187 | 3.3705 | 15.7363 | 1.4436 | 4461.090 |
| circle | 2048 | 13.672 | 8927.802 | 3.4313 | 14.2166 | 1.1795 | 9711.300 |

circle: completed.

| kite | 256 | 45.377 | 4281.718 | 2.7483 | 31.2917 | 0.6248 | 1099.235 |
| kite | 512 | 32.699 | 3908.320 | 2.9276 | 26.8096 | 0.6779 | 2136.472 |
| kite | 1024 | 21.053 | 3554.893 | 3.1047 | 22.3830 | 0.8452 | 4427.208 |
| kite | 2048 | 16.110 | 3362.681 | 3.2541 | 18.6485 | 0.8035 | 9682.229 |

kite: completed.

| peanut | 256 | 29.868 | 6194.288 | 2.8768 | 28.0806 | 2.7615 | 1099.544 |
| peanut | 512 | 28.004 | 6107.449 | 2.9988 | 25.0306 | 2.5434 | 2137.732 |
| peanut | 1024 | 25.298 | 5978.320 | 3.1070 | 22.3249 | 2.2695 | 4447.877 |
| peanut | 2048 | 21.130 | 5779.458 | 3.2095 | 19.7633 | 1.9057 | 9700.709 |

peanut: completed.


The measured-cylinder nominal registration is not used for these simulated truths.
For that measured case, registered area error, support size and centre offset remain separate; its nominal position is only about 30 mm.

Raw data, full histories and native logs stay local and ignored. Per-case manifests give SHA-256.
Raw checkpoint arrays, compressed logs, costs, timing/resources and all sensitivity scores are committed.

The output-only owned copy differs by a function rename and one snapshot callback (patch 0003).
The upstream numerical function, objective, projection, line search and settings are unchanged.
Native timers include the small snapshot writes; checkpoint_writes.csv records that I/O separately.

The BEM side must check the exact hashed simulated data on each true boundary later.
Timings overlap other MATLAB work and are not isolated final-comparison timings.

## First-batch time check

```json
{
  "utc": "2026-11-18T02:00:15.045505+00:00",
  "observed_seconds_per_iteration": [
    4.74184578125,
    4.727650699707032,
    4.736674220703125
  ],
  "conservative_rate": 4.74184578125,
  "elapsed_seconds": 9801.41659526527,
  "remaining_forecast_seconds": 29472.29821983166,
  "total_forecast_hours": 10.909365226415813,
  "budget_hours": 9,
  "method": "elapsed + three remaining batches at slowest completed first-batch wall + seven forward generations at 43 s",
  "exceeds_budget": true
}
```
