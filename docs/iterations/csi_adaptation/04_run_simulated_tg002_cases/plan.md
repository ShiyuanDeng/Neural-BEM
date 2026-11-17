# Run simulated TG-002 cases with MF-CC-CSI

## Status and user decisions

17 November 2026. The coordinator conveyed the user's words:
**"okay for now keep only mf-cc-csi, and run them three at time"**.
The campaign has the go, subject to the coordinator's **6 h total budget**
and instruction: if the timing probe says it will not fit, report before
starting instead of cutting any cases, grid or iterations.

**Not started: the activity-03 probe forecasts 7.96 h for the requested
four batches, exceeding 6 h.** Even perfect sharing of all work across
three workers gives 6.65 h, before additional contention or a reduction
to two workers. The coordinator must resolve the limit before launch.
No activity-04 forward generation or inversion has run. Do not silently
replace 2048 with a shorter count: the measured snapshot check also found
no requested earlier count within 1% of the final area and mean contrast.

## Question, cases and comparisons

Run one clean-data MF-CC-CSI fit for each of the ten frozen TG-002 shapes,
relative permittivity 4 (susceptibility 3 in vacuum). Map the acquisition
scene centre to the Fresnel origin; retain every target's frozen relative
placement, orientation and boundary. No grid search or alternate start.
The table entry is the raw 2048-iteration result. Earlier snapshots are
evidence, never a replacement entry selected after seeing truth.

Planned order, with at most three detached fits active:

| Batch | Shapes |
|---|---|
| 1 | circle, kite, peanut |
| 2 | star, asymmetric, c_shape |
| 3 | hook, cross, cog |
| 4 | aphex_twin |

The method and settings stay the same for every case: first-opus layout,
36 transmitters at 0.72 m, 72 possible receivers at 0.76 m, original
49-per-source mask, all eight frequencies 1-8 GHz, 2048 iterations,
native back-propagation start, centre [0,0,0], half-widths 103.75 mm,
1.25 mm cells and 166-by-166 grid. Keep the shipped projection,
regularization/objective, line search, five-cell border/PML and calibration.
Eight MATLAB compute threads are set in the wrapper, not upstream code.
No MR-CSI or CSI campaign fits are authorized by this activity.

## Frozen simulated data

Extend only the owned activity-03 native-forward driver to accept each
frozen shape. It uses unchanged native FDFD matrix/material routines and
receiver kernel, on a finer 332-by-332 grid with 0.625 mm cells and the
same physical half-width. Native averaging of dielectric cells onto Ez
nodes is retained. Do not use the inversion discretization for data.

Reuse activity 03's frozen circle file rather than generating it again:
`results/csi/preparation/2026-11-17_generate/synthetic_input.txt`, SHA-256
`34ed9276fb6680d01ff6e7a7c26c8d19fb70fe5df4dbe1a81de39e025924cefe`.
For each other case, retain the true boundary/material arrays and the
exact seven-column table locally, with SHA-256, bytes and command in a
manifest. Verify finite values, exact template mask, native material
matrix consistency and relative solve residual below 1e-9. Preserve
failed data generation and continue with the next case.

The physical unit incident Green field is independent of grid spacing.
The inversion reads only the same incident/total table and uses the
unchanged per-source calibration. It receives no true geometry, position,
permittivity or support. The BEM side later checks these exact data files
on each true boundary; that check is outside this activity. The input
phasor is exp(+j omega t); later BEM ingestion must conjugate it.

## Early snapshots and frozen scoring

Save raw unmasked complex contrasts at 256,512,1024,2048, with native
numerical x/y vectors and frequency convention. The native `Mchi` history
is updated every 64 iterations but returned only at function exit;
`recflag` writes a diary, not early image files. Therefore an owned copy
will add output-only writes immediately after the existing history update
at the four requested iterations. Keep the complete optimizer state and
all arithmetic unchanged. Save its exact diff under
`external/patches/cc-csi/` and report it. Do not split the run into fresh
chunks or restart from a contrast image, which would change the method.

Import the frozen image-region functions from
`experiments/comparison/scoring.py`, as in activities 02/03. Do not edit
that module. Protocol version 1 uses half the largest-magnitude signed
peak, with 0.3/0.7 sensitivities, all components and holes, the shared
201-by-201 scoring grid and the frozen TG-002 truth. Report set-difference
area / true area, mean relative permittivity in the support, its relative
error against 4, centroid, and native time per case and snapshot. Do not
choose a new success threshold. The full `score()` entry point assumes
the BEM boundary-output schema; reuse its unchanged image helpers instead.

## Resources, run budget and failure handling

Each fit is launched with `setsid nohup` and its own output directory.
Monitor MATLAB plus descendants, CPU time, RSS, MemAvailable, MemFree and
other MATLAB jobs. The probe used 5.20 CPU cores on average, with an
eight-thread ceiling and peak family RSS 6.447 GiB. Three workers are a
CPU ceiling, not a demonstrated three-fold speedup. Three fit families
plus 14 GiB reserve require at least 33.34 GiB available before launch,
with headroom for BRG growth. Start two if three do not fit, and keep at
least 14 GB memory available throughout; also record unused MemFree.
Do not stop or reconfigure BRG jobs. Preserve any memory-limit failure,
reduce to two, and continue eligible cases rather than losing the log.

Measured native rate: 3.440759 s/iteration. At 2048 this is 7046.674 s
per case, plus 12.393 s measured wrapper overhead. Four batches forecast
7.84 h for inversion and 0.12 h for ten forward generations: **7.96 h**
total (about 42 s less when reusing the circle data). Ideal division by
three is still **6.65 h**. Two-worker scheduling is slower. These rates
were measured under BRG overlap; no clean-run or concurrent speedup is
assumed to waive the user's six-hour limit.

The **current run budget is 6 h total**. Stop before starting because the
forecast exceeds it. Once the coordinator resolves this conflict, record
that decision here before launching. A six-hour wall monitor must preserve
all completed/early snapshots and logs if the budget remains in force.
No settings or cases may be cut to make the estimate fit.

## Commands, evidence and commits

The preparation commands already run are documented in activity 03.
The campaign launcher/scoring extension is to be implemented only after
the budget conflict is resolved, under `experiments/baselines/csi/`.
Its exact executable command will be recorded here before any run.

New raw evidence goes to `results/csi/tg002/2026-11-17_<case>/` (or the
actual run date). Reports and figures belong beside this plan. Compact
evidence retains four required raw images, costs, timings, logs and small
JSON. Full workspaces, per-frequency fields/matrices, material maps and
data tables remain local and explicitly ignored, with SHA-256 manifests.
Avoid duplicate diary copies and sample resource logs compactly while
retaining exact reserve minima, so each batch stays near the 5 MB rule.
Keep native float64 raw contrasts; do not mask or quantize to save space.

After each batch of three (and the final single case), commit and push
its owned code, documentation and compact evidence, failures included.
Use `git add <CSI paths>` and `git commit -m "..." -- <CSI paths>`.
Check the push and status. Never stage other agents' paths, create a
branch/worktree, rewrite old evidence, edit solver code or alter scoring.

Success for this activity is ten recorded outcomes with 2048 table entries
or preserved failures, all available snapshot scores, hashes of the exact
data files, native/launcher timings and overlap notes. Numerical success
is reported as raw metrics under the frozen protocol, not selected here.
