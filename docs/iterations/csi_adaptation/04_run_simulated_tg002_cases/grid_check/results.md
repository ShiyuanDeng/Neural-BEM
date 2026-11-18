# Circle forward-grid check

**Closed by the coordinator's band-cut decision, 18 November 00:55 UTC.**
This side measurement is filed under activity 04, leaving activity 05
for the user's new 1–3 GHz campaign. Earlier coarse evidence is retained
as dropped side work; neither extra grid is used in the comparison.

The 0.3125 mm MATLAB process (PID 788105) was stopped on the coordinator's
instruction after checking its executable, exact executed-driver path,
output environment and process group. Only that group received SIGTERM.
Return code -15, peak family RSS 5.024 GiB, minimum MemAvailable 14.988 GiB.
No fine table was completed. Partial logs and all outputs are retained;
the controller's exact launch-time source snapshot matches its saved hash.
The old campaign and its workers were untouched.

## Reason for restricting the band

The user's words, relayed by the coordinator: "id say we just supply less
frequency range to it, you know below 4GHz such that simulated data are
accurate there." The main simulated comparison now uses 1, 2 and 3 GHz.
No data file is corrected or replaced by an equivalent-circle fit.

The requested 0.625 mm diagnostic matches the coordinator's numbers to
their displayed rounding. Best contrast at the true radius/centre:
4.001355, 4.000125, 4.001252, 4.001846, 4.004450, 4.006989, 4.008002,
4.010206. These are contrast shifts of 0.003–0.255%, not image-fit results.
The common fit gives radius 49.981525 mm, contrast 4.009216, centre shift
(+0.004765, -0.007664) mm, norm 0.009025 mm. Its per-frequency errors are
0.294, 0.417, 0.843, 2.256, 0.571, 0.592, 0.774, 2.731 percent.
Weighting is equal relative-L2 per frequency; one centred truth start,
no grid search. Independent-frequency fits change contrast only.

Full independent fit errors, the common fit and table hash are in
[exact_circle_fits.json](../../../../../results/csi/grid_check/2026-11-18_circle/exact_circle_fits.json).
Command: `PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m
experiments.baselines.csi.circle_grid_check --cells 0.625 --fit`.
The exact series formula was copied into CSI-owned code; BEM files were
read only. Its truth prediction agrees with the saved reference below
1e-10, with no fitted conjugation, shift, rotation or calibration.

18 November 2026. Resume takes priority and is ready/pushed. Original
campaign is running without intervention. Grid-check work uses separate
CSI-owned paths and does not change campaign inputs or settings.

The saved 0.625 mm row was reproduced using the BEM side's pair mask/order
and one conjugation: 0.172326, 0.126049, 0.303387, 1.139565, 0.822753,
1.678183, 2.294550, 5.913594 percent at 1–8 GHz. The denominator is the
table norm, matching their report. Exact-reference denominators are also
saved in [grid_errors.json](../../../../../results/csi/grid_check/2026-11-18_circle/grid_errors.json).
The copied independent circle series agrees with their saved predictions
to below 1e-10; exact discrepancies are in that JSON.

The first 1.25 mm attempt failed before generating any table: the owned
grid copy changed x coordinates but retained the old y-coordinate vector.
The dimension assertion stopped MATLAB. Return code 1, 6.59 s wall time,
peak family RSS 1.322 GiB, minimum available memory 18.134 GiB. This is a
driver-copy error, not a forward-solver failure or a campaign failure.
The failed executed driver and evidence are kept unchanged in
[cell_1.25_mm](../../../../../results/csi/grid_check/2026-11-18_circle/cell_1.25_mm/launch.json),
including compressed native log, source hashes, resource samples and outcome.

Command: `PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m
experiments.baselines.csi.circle_grid_check --analyze --generate 1.25`.
The launch record retains its exact MATLAB command and CSI environment.

Boundary rule: point membership produces binary staircase dual cells;
the unchanged native mean_material_node then averages four neighbouring
cells onto primary Ez nodes. There is no exact cut-cell area fraction.

The corrected coarse run completed all eight frequencies in
[attempt 02](../../../../../results/csi/grid_check/2026-11-18_circle/cell_1.25_mm_attempt_02/launch.json).
Peak family RSS was 1.457 GiB and minimum available memory 17.572 GiB.
The saved table's SHA-256 is in its data.json; exact driver, source hashes,
native residual/material checks and compressed log are retained there.

Relative-L2 percent, divided by the table norm, at 1–8 GHz:

| Cell mm | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.25 | 0.24275 | 0.23739 | 0.86399 | 3.22503 | 2.81170 | 6.55130 | 8.39737 | 23.48164 |
| 0.625 | 0.17233 | 0.12605 | 0.30339 | 1.13957 | 0.82275 | 1.67818 | 2.29455 | 5.91359 |

Observed orders from 1.25 to 0.625 mm: 0.494, 0.913, 1.510, 1.501,
1.773, 1.965, 1.872, 1.989. The high-frequency errors are close to
second order on this pair of grids; boundary rasterization also changes.
This does not establish a pure dispersion cause or an asymptotic order.

The first fine-grid precheck used its entire 6 GiB cap as a launch
allowance and waited. Coarse observed family RSS 1.457 GiB and saved
0.625 mm generator family RSS 2.160 GiB give 4.97 GiB by a fixed-startup
plus grid-linear allocation estimate. The fine precheck now reserves
5 GiB plus the 14 GiB reserve and 0.25 GiB stop margin; actual family
RSS still has a 6 GiB cap and memory is checked every 0.2 seconds.
This is a resource estimate, not a claimed measured fine-grid peak.

No further grid runs or other-grid diagnostic fits are planned after the
user's decision. The 0.625 mm diagnostic above is the retained result.
No upstream patch; no change to solver or comparison code.
