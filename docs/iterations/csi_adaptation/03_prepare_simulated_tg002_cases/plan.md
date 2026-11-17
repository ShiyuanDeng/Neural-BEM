# Prepare simulated TG-002 cases

## Status and decisions

Authorized 17 November 2026 by the coordinator. Preparation only: do not
start a campaign or edit `solvers/` or `experiments/comparison/`. Keep all
upstream numerical code unchanged and reuse compatibility patches 0001/0002.
Stay on the current branch and commit only named CSI paths after each run.

The coordinator excluded contrast 0.5. Table C's simulated cases are the
ten frozen TG-002 shapes at squared wavenumber ratio 4, in vacuum. Use one
common inversion half-width 103.75 mm, cell 1.25 mm, 166-by-166 grid,
unless the timing probe leads to a different proposal for review. The
inversion has 36 sources and eight real frequencies 1-8 GHz, in the shipped
first-opus masked layout and calibration path. Thresholds stay protocol 1:
half the signed peak, sensitivity 0.3/0.7. No tuning or truth-based start.

## Questions and work

A. By reading the database setup, angle definitions and coordinate code,
establish the signed map to the exported numerical axes. Use the authors'
labelled 2001 inversion figures for the same file as an independent sign
check if the introduction's unlabelled cross-section is insufficient.
State nominal numerical truth before rescoring the saved activity-02
contrasts. Do not refit or align to the recovered images.

B. One measured-cylinder MF-CC-CSI rerun with the same 112-by-112 grid,
1.25 mm cells, frequencies, inputs, start and 2048 iterations as activity
02. Retain raw snapshots at 128,256,512,1024,2048 using the function's
native every-64 return history. Its `recflag` controls a diary rather than
snapshots; enable the diary in our copy with its required output filename.
Omit MR/CSI and avoid the display code that masks the final image. Score
each raw snapshot. Select the smallest requested count with area and mean
contrast both within 1% of the 2048 values, reporting all differences.

C. Build only a circle-at-contrast-4 example from the frozen TG-002
boundary/placement. The circle is a simple control, not a changed shape or
start. Inventory the shipped forward capabilities. Use unchanged native
FDFD background/material equations and receiver kernel through an owned
driver; record that a complete synthetic example is not shipped. Generate
on a 0.625 mm grid (332-by-332) so inversion and data use different
discretizations. Save the physical permittivity map, true boundary, masked
seven-column incident/total data table, and calibration metadata. Use a
canonical unit line-source amplitude independent of cell size. Feed that
table through the same upstream calibration routine. The BEM true-shape
forward check is later work and is not run here.

D. One MF-CC-CSI-only timing probe on that synthetic circle: common
166-by-166 grid, 1.25 mm cells, 64 iterations, native back-propagation start.
Measure CPU process time per wall second (equivalent utilized cores), RSS,
memory headroom and other MATLAB processes; do not infer utilization from
`maxNumCompThreads` alone. Report indicative concurrency limits.

E. Cost ten contrast-4 shapes, both MF-CC-CSI alone and all three methods,
at 2048 and at B's selected count. Use the measured probe and earlier
per-method rates, label unmeasured MR/CSI rates, include known forward
generation cost separately and show serial and concurrency assumptions.
Do not generate the remaining nine cases or launch any campaign.

## Limits and success criteria

Only one CSI MATLAB process at a time, detached with `setsid nohup`.
Default eight compute threads, recorded rather than changed in upstream
code. BRG currently has several MATLAB jobs, so log all overlap. Read
`/proc/meminfo` before launching, require estimated headroom for this fit,
and enforce at least 14 GiB MemAvailable while it runs; record MemFree too.
For generation and the larger probe, enforce 14 GiB MemFree as well and
require both measures to exceed 18 GiB before starting. The measured run
was already launched with the available-memory guard; check its minimum
unused memory from the retained monitor too.
The monitor stops only our process group if the reserve is crossed and
preserves the failure evidence. Do not stop or reconfigure BRG jobs.

Expected B runtime about 33 minutes from the saved 1963 s timer; budget
2 hours including changed overlap. Forward preparation budget 30 minutes.
Probe estimate about 135 s native from cell-work scaling; budget 15 minutes.
Reading/code/scoring use saved evidence first. Stop if an unapproved change
to the mathematical method or data convention is needed. A poor synthetic
recovery is evidence, not permission to tune.

## Commands and outputs

- Owned code: `experiments/baselines/csi/`; only owned wrapper copies change.
- Activity evidence: `results/csi/preparation/2026-11-17_<purpose>/`.
- Report and figures: `results.md` and `figures/` beside this plan.
- Detached runs use an owned preparation launcher and resource monitor;
  record each exact command, PID/session, source/input hash and exit code.
- Full fields, snapshots/workspaces and synthetic input arrays stay local
  and ignored, with SHA-256 and commands in a manifest. Commit at most about
  5 MB per run: required contrasts, score/cost tables, logs and figures.
- Commit and push after each run, including failures, using `git add <CSI
  paths>` then `git commit -m "..." -- <CSI paths>`. Never a bare commit.
- Stop after the preparation report and the campaign-cost estimate.
