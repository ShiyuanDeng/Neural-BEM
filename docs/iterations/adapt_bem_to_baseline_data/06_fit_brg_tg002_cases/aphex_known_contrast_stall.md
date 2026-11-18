# Aphex known-contrast stalls — saved records, 18 November 2026

Facts below come from the four saved attempts. No fit or forward solve was run; no code was changed.
Records: [0.5 known](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/aphex_twin__c0.5/known/attempt_01/), [0.5 recovered](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/aphex_twin__c0.5/recovered/attempt_01/).
Records: [4 known](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/aphex_twin__c4/known/attempt_01/), [4 recovered](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/aphex_twin__c4/recovered/attempt_01/).
In each directory: `initialization.json`, `fit.json`, `local/ladder_*_real.json`, `local/full_*_M*.json`, `local/decisions.json`, `local/accepted.json`. All 56 used local records match their bulk-manifest hashes.

**First divergence and ladder endpoints.** Both rows start from the same centred 65 mm circle.
For eta 0.5, known/recovered start contrast is 0.5/0.915112799; L1 entry loss is 6.66849/0.233119.
For eta 4, start contrast is 4/1.590403989; L1 entry loss is 2.26919/0.264199. Thus divergence starts at L1 entry, before any curve update.
At the first accepted L1 step, losses are 2.97169/0.118679 (eta 0.5) and 1.78680/0.125437 (eta 4).
Its box centres are (-3.99,-5.34)/(-18.25,-15.93) mm and (0.83,-1.06)/(-23.21,-15.46) mm, respectively.
Below, K/R mean known/recovered. Size is bounding-box width × height; position is its centre, all in mm, sampled from saved Fourier coefficients at 8192 points.

| Eta, stage | End loss K / R | End size @ position K | End size @ position R | End contrast R |
|---|---:|---|---|---:|
| 0.5, L1 | 8.319e-3 / 3.832e-5 | 80.89×83.21 @ (-23.74,-13.32) | 82.01×70.78 @ (-22.54,-32.37) | 0.689232 |
| 0.5, L2 | 1.167e-3 / 5.996e-5 | 82.52×74.77 @ (-23.31,-28.15) | 84.43×69.87 @ (-25.38,-34.48) | 0.555175 |
| 0.5, L3 | 1.063e-5 / 3.388e-6 | 85.45×68.13 @ (-22.99,-34.12) | 86.57×66.90 @ (-23.74,-36.80) | 0.555696 |
| 0.5, L4 | 3.381e-5 / 4.666e-6 | 84.34×65.94 @ (-23.28,-36.51) | 86.84×66.91 @ (-24.28,-37.87) | 0.539883 |
| 4, L1 | 5.248e-4 / 1.573e-4 | 87.77×65.33 @ (-22.03,-26.76) | 81.44×70.63 @ (-23.07,-30.46) | 3.064156 |
| 4, L2 | 2.646e-3 / 1.158e-3 | 91.52×59.25 @ (-14.24,-32.39) | 82.69×66.33 @ (-25.90,-30.30) | 3.938565 |
| 4, L3 | 1.633e-2 / 2.122e-4 | 77.36×65.60 @ (-20.62,-34.19) | 84.09×66.42 @ (-22.92,-33.34) | 3.871065 |
| 4, L4 | 6.203e-3 / 6.030e-4 | 83.63×67.60 @ (-23.04,-34.38) | 85.18×67.16 @ (-23.38,-35.38) | 3.874034 |

**Where time went.** `fit.json` assigns 1399.93/1431.13 s (97.82%) and 5584.33/5627.66 s (99.23%) to forward geometry preparation for known eta 0.5/4.
That is A1 on the default modal path: [prepare_geometry](../../../../solvers/bem_inverse/forward_solvers/modal_muller.py#L192), as named in the [A1–C12 chain](../../../reference/inverse_information_chain.md). Slider preparation plus trial construction took only 3.19/6.19 s.
Recovered A1 totals are 51.61/36.00 s despite 2525/2522 forward solves, versus only 1102/793 for known. A1 includes device-lock waiting; separate wait, sub-stage timers and log degrees were not saved, so exact per-stage attribution inside A1 is unavailable.
All slow stages below use `nodes=1024`, meaning modal trace cutoff 128, not 1024 collocation nodes; coefficient window and stored geometry band are 192. Recovered stages use the same settings.
P/A/S/N count constructed proposals / accepted / self-intersection refusals / nondecreasing-loss rejections. F is entry plus trial forward solves; D is charged reciprocal derivative work.

| Known eta, stage | Seconds | Units | Seconds/unit (versus 0.024) | P/A/S/N | F | D |
|---|---:|---:|---:|---|---|---:|
| 0.5, M25 | 498.758 | 266 | 1.875 (78×) | 33/6/26/1 | 19+133 | 114 |
| 0.5, M31 | 500.056 | 152 | 3.290 (137×) | 90/3/87/0 | 19+57 | 76 |
| 4, M11 | 492.185 | 152 | 3.238 (135×) | 80/3/77/0 | 19+57 | 76 |
| 4, M25 | 1654.337 | 285 | 5.805 (242×) | 107/7/100/0 | 19+133 | 133 |
| 4, M31 | 1259.256 | 285 | 4.418 (184×) | 114/7/107/0 | 19+133 | 133 |
| 4, M43 | 1890.482 | 266 | 7.107 (296×) | 130/6/124/0 | 19+114 | 133 |

Each geometry-refused proposal uses zero trial forward solves; each proposal reaching the loss test uses 19, one per frequency. Counts are not 19 solves for every constructed proposal.
Known fits record 568/973 self-intersection refusals in total; recovered fits record zero. These are trial refusals, not proof that every accepted curve is simple.
**Why zero-step stages return.** All their 40 trials fail the default C10 geometry check (five damping attempts × eight lengths), before C11 evaluation; [fit_stage](../../../../solvers/bem_inverse/fit_stage.py#L378) then returns `no_decreasing_step` and C12 carries the curve onward.
They charge 19 entry solves and 19 derivatives but no trial solves; unchanged geometry can reuse the A1 cache. Most take 0.92–1.69 s. Exception: eta 0.5 M11 takes 31.81 s on first entry to the larger workspace; zero accepted steps does not itself imply an immediate return or convergence.

**Accepted geometry at the stall.** The [saved truth](../../../../development_results/TG-002/inputs/aphex_twin/truth.json) has size 84.73×66.13 mm, centre (-24.30,-39.06) mm, area 2334.86 mm².
Known eta 0.5 after M31: 85.98×67.79 mm @ (-24.50,-37.92), area 2334.09 mm². Known eta 4 after M43: 83.78×67.72 mm @ (-23.15,-34.91), area 2436.33 mm². Later stages leave these endpoints unchanged.
Thus neither is very large. Their sampled polygons put 176.05/438.41 mm² outside the truth and miss 176.81/336.94 mm² inside it; no `outside_domain` trial refusal is recorded.
Among 8192 boundary samples, excluding pairs less than 10 mm apart along the shorter boundary arc, minimum gaps are 0.000380/0.001584 mm at those known endpoints, versus 6.636/6.378 mm recovered and 6.479 mm on the truth.
Near contact already appears at known eta 0.5 L1 (0.04293 mm) and eta 4 L2 (0.00905 mm). These sampled distances are upper bounds on the true minimum; simple sampled endpoint polygons do not certify the smooth curves against intersection.
Final known/recovered losses are 8.427e-5/2.777e-11 (eta 0.5) and 7.536e-2/8.404e-10 (eta 4); area errors are 15.11%/1.137% and 33.21%/0.4512%.

**Hypothesis 1 — path trap.** Fixing the true contrast from the large, displaced start drives a different early size/position path into near contact; subsequent useful directions cross the geometry boundary and are refused. The weak start plus adjustable contrast avoids that path. These records cannot separate the effect of the initial contrast from the extra material direction.
**Hypothesis 2 — cost of near contact.** Near contact makes the divided-distance lower bound small, increasing the logarithmic expansion work in default A1 [log_modulus](../../../../solvers/bem_inverse/modal_cuda.py#L144). This fits the A1 timer and geometry evidence, but missing saved degrees prevent confirmation; it is not evidence of excess forward-solve counts or higher trace resolution.
