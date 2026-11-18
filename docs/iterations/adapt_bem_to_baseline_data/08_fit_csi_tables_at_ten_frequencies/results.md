# Ten-frequency CSI tables and fits: results

18 November 2026. Runner: `bem-ten`. Plan: [plan.md](plan.md).
State: tables and checks complete; no fit started. Waiting for the coordinator's go.
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

Not started. The coordinator must give the go after this check table and stage list.
Four planned GPU fits: circle, star, kite and hook, one pass each, sequentially.
Stage scores, final residuals and outline comparison remain pending.

Five-frequency references: circle 0.97%, star 2.34%, kite 3.80%, hook 3.59% area error.
The frequency-count question is unanswered until the ten-frequency fits finish.

## Failures kept

The first batch check was launched before star was frozen. Circle completed successfully;
then the command stopped on the missing star SHA-256 file, before a star check began.
The same command resumed after all tables were frozen and skipped the saved circle result.

No check was repeated. No forward table or fit was rerun.
Receipt: [launch failure](../../../../results/bem/baseline_data/csi_ten_frequency/2026-11-18/check_launch_failure.json).
There were no numerical data failures and no 1% failures.

```text
Activity: adapt_bem_to_baseline_data/08_fit_csi_tables_at_ten_frequencies
Runs: 10 data runs; 10 BEM true-shape checks; 1 dry plan; 0/4 fits
Result: all tables frozen; all old-frequency bytes equal; all checks pass; dry policy accepts band 0
Failures: one early batch launch stopped on pending star input; kept; no check repeated
Upstream patches: none
Changes to our code: two new data drivers, a thin BEM runner and a saved-check report script; existing code unchanged
New unknowns: ten-frequency outline quality and whether the optimizer completes the band-0 stage
Proposed next activity: coordinator go for the four planned GPU fits in this activity
```
