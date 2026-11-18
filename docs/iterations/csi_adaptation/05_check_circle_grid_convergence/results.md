# Circle forward-grid check

18 November 2026. Resume takes priority and is ready/pushed. Original
campaign is running without intervention. Grid-check work uses separate
CSI-owned paths and does not change campaign inputs or settings.

The saved 0.625 mm row was reproduced using the BEM side's pair mask/order
and one conjugation: 0.172326, 0.126049, 0.303387, 1.139565, 0.822753,
1.678183, 2.294550, 5.913594 percent at 1–8 GHz. The denominator is the
table norm, matching their report. Exact-reference denominators are also
saved in [grid_errors.json](../../../../results/csi/grid_check/2026-11-18_circle/grid_errors.json).
The copied independent circle series agrees with their saved predictions
to below 1e-10; exact discrepancies are in that JSON.

The first 1.25 mm attempt failed before generating any table: the owned
grid copy changed x coordinates but retained the old y-coordinate vector.
The dimension assertion stopped MATLAB. Return code 1, 6.59 s wall time,
peak family RSS 1.322 GiB, minimum available memory 18.134 GiB. This is a
driver-copy error, not a forward-solver failure or a campaign failure.
The failed executed driver and evidence are kept unchanged in
[cell_1.25_mm](../../../../results/csi/grid_check/2026-11-18_circle/cell_1.25_mm/launch.json),
including compressed native log, source hashes, resource samples and outcome.

Command: `PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m
experiments.baselines.csi.circle_grid_check --analyze --generate 1.25`.
The launch record retains its exact MATLAB command and CSI environment.

Boundary rule: point membership produces binary staircase dual cells;
the unchanged native mean_material_node then averages four neighbouring
cells onto primary Ez nodes. There is no exact cut-cell area fraction.

The corrected coarse run completed all eight frequencies in
[attempt 02](../../../../results/csi/grid_check/2026-11-18_circle/cell_1.25_mm_attempt_02/launch.json).
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

Pending: fine run when the full 6 GiB job allowance plus reserve fits;
then the requested exact-circle diagnostic fits on available tables.
No upstream patch; no change to solver or comparison code.
