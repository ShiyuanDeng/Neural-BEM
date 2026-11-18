# Ten-frequency CSI tables and fits: results

18 November 2026. Runner: `bem-ten`. Plan: [plan.md](plan.md).
State: tables and checks complete; 2/4 GPU fits recorded.
The dry policy accepts band 0 at 0.25 GHz. No policy change was made.

## Data

Ten unchanged-CSI-forward tables at contrast 4, 0.25 to 2.5 GHz in 0.25 GHz steps.
Each has 17640 finite rows and the frozen 36-source, 49-receiver mask.
Order: circle, star, kite, hook, peanut, asymmetric, c_shape, cross, cog, aphex_twin.

Data runs: 2026-11-18T11:24:52Z to 2026-11-18T11:33:16Z.
Summed MATLAB wall time: 464.303 s.
Peak family RSS 2.259 GiB; minimum available 33.333 GiB.

All 50 old-frequency blocks equal the frozen five-frequency tables byte for byte.
This holds in the raw generated tables and the final frozen tables; field differences are zero.
Each block has its own matching SHA-256 in the per-shape checks.

Maximum native residual: 5.94342e-12.
All runs record HEAD and a clean `solvers/bem_inverse/`.
Table and material bulk files remain local and ignored, with SHA-256 in each bulk manifest.

Circle exact-series errors at all ten frequencies and byte proofs: [data_note.md](data_note.md).
All circle errors pass 1%; worst is 0.44397601% at 0.5 GHz using the exact norm.
Data evidence: [summary](../../../../results/csi/tg002/2026-11-18_ten_frequency_data/summary.json).

## BEM true-shape checks

Every entry is a percentage, worst over the two checked resolutions.
All ten shapes pass the adapter checks and the 1% rule at every frequency.
The largest mismatch is 0.712499% (Aphex Twin, 2.5 GHz).

| Shape | 0.25 | 0.5 | 0.75 | 1 | 1.25 | 1.5 | 1.75 | 2 | 2.25 | 2.5 | Worst (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| circle | 0.2455 | 0.4420 | 0.3052 | 0.1723 | 0.1883 | 0.1347 | 0.1959 | 0.1260 | 0.2266 | 0.1767 | 0.4420 |
| star | 0.2414 | 0.4164 | 0.2787 | 0.1730 | 0.1755 | 0.1842 | 0.2111 | 0.1437 | 0.2758 | 0.2684 | 0.4164 |
| kite | 0.1615 | 0.1229 | 0.1461 | 0.1905 | 0.1519 | 0.1685 | 0.2380 | 0.2001 | 0.1555 | 0.2855 | 0.2855 |
| hook | 0.1763 | 0.2067 | 0.1890 | 0.1739 | 0.1433 | 0.1627 | 0.1853 | 0.1404 | 0.1313 | 0.1877 | 0.2067 |
| peanut | 0.1275 | 0.2080 | 0.1894 | 0.1724 | 0.1463 | 0.1101 | 0.1479 | 0.1682 | 0.1591 | 0.2622 | 0.2622 |
| asymmetric | 0.1659 | 0.2779 | 0.2115 | 0.1839 | 0.2172 | 0.1967 | 0.1785 | 0.2002 | 0.2021 | 0.3668 | 0.3668 |
| c_shape | 0.2468 | 0.2978 | 0.2388 | 0.2989 | 0.2308 | 0.2155 | 0.2240 | 0.2085 | 0.2817 | 0.2755 | 0.2989 |
| cross | 0.1492 | 0.2666 | 0.2176 | 0.1609 | 0.1749 | 0.1500 | 0.1612 | 0.1369 | 0.1778 | 0.2359 | 0.2666 |
| cog | 0.2067 | 0.4004 | 0.3073 | 0.1824 | 0.1703 | 0.1415 | 0.1534 | 0.1371 | 0.1950 | 0.3111 | 0.4004 |
| aphex_twin | 0.4163 | 0.3538 | 0.3082 | 0.4009 | 0.4226 | 0.4566 | 0.4858 | 0.4825 | 0.6215 | 0.7125 | 0.7125 |
| Worst per GHz | 0.4163 | 0.4420 | 0.3082 | 0.4009 | 0.4226 | 0.4566 | 0.4858 | 0.4825 | 0.6215 | 0.7125 | 0.7125 |

Evidence: [check summary](../../../../results/bem/baseline_data/csi_ten_frequency/2026-11-18/check_summary.json).
Each `adapter_checks/<shape>__c4.json` retains both resolutions and provenance.
No CPU fit or tuning run was made.

## Dry plan

Same default wrapper and solver. Fixed work limit 13412; no elapsed-time stop.
The ten ladder quotas total 8000. All frequencies in each range advance by 0.25 GHz.
The first stage's band 0 is accepted by the unchanged policy.

| Stage | GHz | Shape band | Quota |
|---|---|---:|---:|
| ladder_1_real | 0.25 | 0 | 1000 |
| ladder_2_real | 0.25–0.5, step 0.25 | 1 | 375 |
| ladder_3_real | 0.25–0.75, step 0.25 | 2 | 375 |
| ladder_4_real | 0.25–1, step 0.25 | 3 | 375 |
| ladder_5_real | 0.25–1.25, step 0.25 | 3 | 375 |
| ladder_6_real | 0.25–1.5, step 0.25 | 4 | 375 |
| ladder_7_real | 0.25–1.75, step 0.25 | 5 | 375 |
| ladder_8_real | 0.25–2, step 0.25 | 6 | 375 |
| ladder_9_real | 0.25–2.25, step 0.25 | 7 | 375 |
| ladder_10_real | 0.25–2.5, step 0.25 | 7 | 4000 |
| full_1_M11 | 0.25–2.5, step 0.25 | 11 | 1500 |
| full_2_M15 | 0.25–2.5, step 0.25 | 15 | 1500 |
| full_3_M19 | 0.25–2.5, step 0.25 | 19 | 1500 |
| full_4_M25 | 0.25–2.5, step 0.25 | 25 | 304 |
| full_5_M31 | 0.25–2.5, step 0.25 | 31 | 304 |
| full_6_M37 | 0.25–2.5, step 0.25 | 37 | 304 |

Before `full_4_M25`, the default cleanup runs; it has no fit quota.
After `full_6_M37`, the default frontier check uses two work units.
It may append bands 43, 49, 55, 61, 67, 73, 79, 85 or 91,
all ten frequencies, quota 304 each, within the same global work limit.

Evidence: [dry plan](../../../../results/bem/baseline_data/csi_ten_frequency/2026-11-18/policy_dry_check.json).
The plan is a dry construction, not proof that the optimizer completes band 0.
Any fit refusal stays a failure; there is no workaround or rerun.

## Fits

The coordinator accepted the checks and dry plan and gave the go on 18 November 2026.
Fits ran detached, one at a time here, sharing the GPU with activity 09.
Times are indicative. No rerun, tuning or elapsed-time stop was used.

Settings: centred 65 mm circle; modal_muller + slider; real data only;
no localization, warm-up or declared noise; recovered contrast from the weak start.
Series limit 1e-9; 13412 work units. The ten-stage ladder and quotas are unchanged.

| Shape | Data | Outcome | Last stage | Work units | Fit seconds | Contrast | Area error (%) |
|---|---|---|---|---:|---:|---:|---:|
| circle | five frequencies | COMPLETED_SCHEDULE | full_6_M37 | 4477 | 199.658 | 4.000202526 | 0.968039 |
| circle | ten frequencies | COMPLETED_SCHEDULE | full_6_M37 | 5867 | 130.072 | 4.001086944 | 0.170636 |
| star | five frequencies | COMPLETED_SCHEDULE | full_6_M37 | 1464 | 47.484 | 4.001657661 | 2.343903 |
| star | ten frequencies | COMPLETED_SCHEDULE | full_6_M37 | 2522 | 61.864 | 4.001308345 | 1.016269 |

Pending fits: kite, hook.

## Area error at every saved stage

Every saved stage curve is decoded from fit.json with bem_inverse.io.curve_from,
then scored with csi_fit.score(case, curve, contrast). No solve is run.
Area error is symmetric difference area divided by true area, in percent.

| Shape | Data | Stage | Top GHz | Shape band | Area error (%) |
|---|---|---|---:|---:|---:|
| circle | five | ladder_1_real | 0.5 | 1 | 2.564571 |
| circle | five | ladder_2_real | 1 | 3 | 0.190815 |
| circle | five | ladder_3_real | 1.5 | 4 | 0.073965 |
| circle | five | ladder_4_real | 2 | 6 | 0.078862 |
| circle | five | ladder_5_real | 2.5 | 7 | 0.080929 |
| circle | five | full_1_M11 | 2.5 | 11 | 0.429744 |
| circle | five | full_2_M15 | 2.5 | 15 | 0.638376 |
| circle | five | full_3_M19 | 2.5 | 19 | 0.727294 |
| circle | five | full_4_M25 | 2.5 | 25 | 0.792986 |
| circle | five | full_5_M31 | 2.5 | 31 | 0.910797 |
| circle | five | full_6_M37 | 2.5 | 37 | 0.968039 |
| circle | ten | ladder_1_real | 0.25 | 0 | 65.956150 |
| circle | ten | ladder_2_real | 0.5 | 1 | 1.996955 |
| circle | ten | ladder_3_real | 0.75 | 2 | 0.770509 |
| circle | ten | ladder_4_real | 1 | 3 | 0.331402 |
| circle | ten | ladder_5_real | 1.25 | 3 | 0.260833 |
| circle | ten | ladder_6_real | 1.5 | 4 | 0.088474 |
| circle | ten | ladder_7_real | 1.75 | 5 | 0.088163 |
| circle | ten | ladder_8_real | 2 | 6 | 0.079118 |
| circle | ten | ladder_9_real | 2.25 | 7 | 0.070518 |
| circle | ten | ladder_10_real | 2.5 | 7 | 0.068498 |
| circle | ten | full_1_M11 | 2.5 | 11 | 0.124051 |
| circle | ten | full_2_M15 | 2.5 | 15 | 0.148983 |
| circle | ten | full_3_M19 | 2.5 | 19 | 0.163547 |
| circle | ten | full_4_M25 | 2.5 | 25 | 0.163642 |
| circle | ten | full_5_M31 | 2.5 | 31 | 0.165737 |
| circle | ten | full_6_M37 | 2.5 | 37 | 0.170636 |
| star | five | ladder_1_real | 0.5 | 1 | 32.450985 |
| star | five | ladder_2_real | 1 | 3 | 31.233888 |
| star | five | ladder_3_real | 1.5 | 4 | 32.077703 |
| star | five | ladder_4_real | 2 | 6 | 3.471104 |
| star | five | ladder_5_real | 2.5 | 7 | 3.814836 |
| star | five | full_1_M11 | 2.5 | 11 | 1.659524 |
| star | five | full_2_M15 | 2.5 | 15 | 1.007168 |
| star | five | full_3_M19 | 2.5 | 19 | 2.155939 |
| star | five | full_4_M25 | 2.5 | 25 | 2.280248 |
| star | five | full_5_M31 | 2.5 | 31 | 2.324645 |
| star | five | full_6_M37 | 2.5 | 37 | 2.343903 |
| star | ten | ladder_1_real | 0.25 | 0 | 90.757366 |
| star | ten | ladder_2_real | 0.5 | 1 | 31.523068 |
| star | ten | ladder_3_real | 0.75 | 2 | 31.517868 |
| star | ten | ladder_4_real | 1 | 3 | 31.361323 |
| star | ten | ladder_5_real | 1.25 | 3 | 31.490511 |
| star | ten | ladder_6_real | 1.5 | 4 | 32.080384 |
| star | ten | ladder_7_real | 1.75 | 5 | 3.414568 |
| star | ten | ladder_8_real | 2 | 6 | 3.405894 |
| star | ten | ladder_9_real | 2.25 | 7 | 3.540243 |
| star | ten | ladder_10_real | 2.5 | 7 | 3.644577 |
| star | ten | full_1_M11 | 2.5 | 11 | 1.578873 |
| star | ten | full_2_M15 | 2.5 | 15 | 0.859021 |
| star | ten | full_3_M19 | 2.5 | 19 | 1.019366 |
| star | ten | full_4_M25 | 2.5 | 25 | 1.011200 |
| star | ten | full_5_M31 | 2.5 | 31 | 1.034510 |
| star | ten | full_6_M37 | 2.5 | 37 | 1.016269 |

## Per-frequency data mismatch

Percent relative scattered-field mismatch. True shape: worst of the two checked resolutions.
Final fit: saved wrapper final_residual at its own working resolution.
Only saved values are read here; no extra forward solve is run.

| Shape | Curve | 0.25 GHz | 0.5 GHz | 0.75 GHz | 1 GHz | 1.25 GHz | 1.5 GHz | 1.75 GHz | 2 GHz | 2.25 GHz | 2.5 GHz |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| circle | true | 0.245503 | 0.442034 | 0.305160 | 0.172326 | 0.188260 | 0.134680 | 0.195902 | 0.126049 | 0.226631 | 0.176721 |
| circle | ten-frequency final | 0.285771 | 0.410793 | 0.295896 | 0.154770 | 0.175323 | 0.142591 | 0.164124 | 0.120777 | 0.138404 | 0.101913 |
| circle | five-frequency final | not used | 0.402493 | not used | 0.145990 | not used | 0.146974 | not used | 0.115867 | not used | 0.097416 |
| star | true | 0.241413 | 0.416448 | 0.278684 | 0.172982 | 0.175524 | 0.184197 | 0.211119 | 0.143713 | 0.275842 | 0.268444 |
| star | ten-frequency final | 0.287670 | 0.382196 | 0.267185 | 0.158926 | 0.159714 | 0.184905 | 0.191814 | 0.124742 | 0.107158 | 0.169214 |
| star | five-frequency final | not used | 0.365854 | not used | 0.147694 | not used | 0.175679 | not used | 0.145305 | not used | 0.165309 |

## Run records

| Shape | Start UTC | Commit | Solver dirty | Start GiB | Peak host / GPU GiB |
|---|---|---|---|---:|---:|
| circle | 2026-11-18T11:37:09+00:00 | `068501c18` | False | 35.149 | 1.966 / 0.827 |
| star | 2026-11-18T11:40:19+00:00 | `33e0a6579` | False | 36.569 | 1.948 / 0.827 |

Evidence: [fit comparison and saved stage scores](../../../../results/bem/baseline_data/csi_ten_frequency/2026-11-18/fit_comparison.json).
Each fit has manifest.json, fit.json, metrics.json, a log and bulk_manifest.json.
Fit-local histories stay local and ignored; bulk_manifest.json records their SHA-256.

## Conclusion

Pending: no conclusion before all four fits return.

## Failures kept

The first batch check began before star was frozen. Circle finished; star had not begun.
The command stopped on the missing star SHA-256 file. The later command skipped circle.
No check or fit was repeated. The launch failure receipt is kept in the results folder.
No numerical data, 1% check or fit failure.

```text
Activity: adapt_bem_to_baseline_data/08_fit_csi_tables_at_ten_frequencies
Runs: 10 data runs; 10 BEM checks; 1 dry plan; 2/4 GPU fits
Result: all data and checks pass; clear area-error gain on 2/4 shapes; fits pending
Failures: early batch launch met pending star input; no numerical failure
Upstream patches: none
Changes to our code: new data drivers, thin runner and saved-result report scripts; existing code unchanged
New unknowns: remaining fits
Proposed next activity: finish the remaining authorized fits
```
