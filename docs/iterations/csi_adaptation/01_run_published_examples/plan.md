# Run the published CSI examples

Questions: does the CC-CSI package (MF-CC-CSI, MR-CSI, CSI) run on this machine
as shipped? Does its output on a case from the paper look like the published
figure?

This activity uses their code only. Our solver is not touched.

## Status

Started on 17 November 2026. The coordinator recorded the user's go to open
two agents "to continue on csi and brg works respectively". This supersedes
the earlier "not now". Activity 01 is authorized; stop after reporting it.

Completed on 17 November 2026. All three steps finished after the two
MATLAB compatibility fixes. Figure 5 was compared with the actual paper;
MF-CC-CSI is qualitatively similar, while the measured-data MF-MR-CSI
result differs. See `results.md`. No threshold was selected. Stop here.

The MATLAB wrapper sets `maxNumCompThreads(8)` and records the actual count.
BRG may run at the same time; these are setup timings, not final table timings.
The MaxwellFDFD system link exists; no path patch is needed.

Step 1 stopped twice on 17 November: first on removed `plottools`, then on
MR-CSI's negative `interp2` refinement factor after MF-CC-CSI completed.
The display-only patch is saved. The coordinator approved patch 0002 on
17 November: replace only the three negative `interp2` calls by sampling
`X(1:2^intrao:end,1:2^intrao:end)`, restoring the legacy query grid. Resume
steps 1 to 3, checking random-array refine/coarsen equality first. Similar
MATLAB compatibility fixes may proceed when old behavior is clear; stop
for unclear behavior or a mathematical change. See `results.md` for evidence.

## User decisions (17 November 2026)

These come from the grilling session recorded in the
[legacy design record](../../../../../Neural_SDF_BEM_AD/docs/iterations/baselines/iteration_01/02_proposals/02_design_decisions.md).
The user split the work into two investigations, `csi_adaptation` and
`brg_adaptation`.

- Principle: "for fair comparison we should avoid changing their code and
  settings, we should instead adapt our code to their test cases."
- Settings: "first run example ones to confirm everything works, then use
  paper settings when we acc generate results for comparison." Code defaults
  apply only where the paper is silent. No tuning.
- All three CSI algorithms run.
- Failures: "the agent is allowed to debug." Every change to upstream files is
  saved as a patch in `external/patches/cc-csi/` and reported.
- No shared layer with BRG. This investigation owns
  `experiments/baselines/csi/` and `results/csi/`. Only
  [`external/sources.json`](../../../../external/sources.json) is shared.
- Stop after this activity and report for review.

## Investigation scope (later activities)

The user agreed these on 17 November 2026; they shape later activities, not
this one.

- Cases: Fresnel `dielTM_dec8f` (one dielectric cylinder, TM, measured data),
  plus TG-002 shapes simulated in the exact Fresnel layout with their code and
  settings unchanged.
- Their code is not run on TG-002.
- Clean data first; noise only after the clean results are reviewed.
- Our method gets exactly the data CSI gets, chooses its own frequency
  schedule within it, and recovers the contrast, as CSI does.
- Our forward solver is checked on each true shape before any inversion.
- Score: set-difference area over true area, contrast error and wall time.
  CSI's shape comes from thresholding its image.
- Extending `solvers/bem_inverse/` for their data (a full sources × receivers
  table, line sources with a calibration factor) comes later in this
  investigation. The user did not fix the order relative to BRG.

## Setup

- Checkouts: `~/neural_bem_external/CC-CSI` at `73a64e1` and
  `~/neural_bem_external/maxwellfdfd` at `690ca8d`.
- MATLAB R2026a, run as `matlab -batch`. One MATLAB process. No GPU.
- MaxwellFDFD: `add_path.m` looks for it at
  `/usr/local/MATLAB/R2026a/toolbox/maxwellfdfd-master`, and every example
  starts with `restoredefaultpath`. The folder is root-owned. Their
  `INSTALL.md` says to copy MaxwellFDFD there, so the user would run:
  `sudo ln -s ~/neural_bem_external/maxwellfdfd /usr/local/MATLAB/R2026a/toolbox/maxwellfdfd-master`.
  If the user prefers no system change, use a path-only patch instead and save
  it.
- `DGradient.mexa64` is prebuilt. If R2026a rejects it, rebuild it from
  `DGradient/DGradient.c` with MATLAB's `mex`.

## Steps

1. **Shipped example I.** `Inv_Fresnel_I.m` as shipped: `uTM_shaped` (metal
   U, TM), 2–16 GHz in 2 GHz steps, 70 × 70 cells of 1.5 mm, 36 sources,
   16 iterations, all three algorithms.
2. **Shipped example II.** `Inv_Fresnel_II.m` as shipped: `FoamDielExtTE`,
   2–10 GHz in 2 GHz steps, 100 × 100 cells, 8 sources, 32 iterations.
3. **Paper case.** `FoamTwinDielTM` with the settings of
   [arXiv 1906.10814](https://arxiv.org/abs/1906.10814), Section 4.1:
   - 7, 8, 9 and 10 GHz;
   - domain [−82.5, 82.5] × [−97.5, 67.5] mm with 1.5 mm cells;
   - 2048 iterations, MF-CC-CSI and MF-MR-CSI.

   Compare with the paper's Figure 5. The case line is already in their
   `Inv_Fresnel_II.m`. Set it in our wrapper copy, not in their file.

A wrapper in `experiments/baselines/csi/` runs each script without changing
it. It saves the workspace outputs (`mchi*`, `time*`, cost history) and every
open figure. Their scripts call `clearvars`, so the wrapper passes the output
folder through an environment variable.

Commands (shape only; the wrapper fixes the details):

```bash
export CSI_OUT=results/csi/examples/inv_fresnel_i
matlab -batch "cd('~/neural_bem_external/CC-CSI'); run('$PWD/experiments/baselines/csi/run_example.m')" \
  2>&1 | tee "$CSI_OUT/matlab.log"
```

## Success criteria

- Steps 1 and 2 finish without error for all three algorithms, and their cost
  falls over the iterations.
- Step 1 shows a U shape and step 2 a cylinder, at the positions given by the
  Fresnel description.
- Step 3 matches Figure 5 of the paper by eye: two cylinders inside the foam
  cylinder, with similar contrast levels.
- Any patch is small, saved and explained.

## Run limits

- Steps 1–2: expected minutes. Stop and report if either takes over 30 min.
- Step 3: estimate from the per-iteration time of step 2 before starting.
  Ask the user if the estimate is above 4 h in total.

## Outputs

- Code: `experiments/baselines/csi/`.
- Raw outputs and logs: `results/csi/examples/<step>/`.
- Report figures: `docs/iterations/csi_adaptation/01_run_published_examples/figures/`.
- Patches: `external/patches/cc-csi/`.
- After running: `results.md` here, then commit and push.

## Exact runner (17 November 2026)

Run `python3 experiments/baselines/csi/run.py shipped_i`, then `shipped_ii`.
Each command limits MATLAB to 30 minutes and saves its log, source snapshot,
outputs split by frequency, figures, and launch timing under
`results/csi/examples/2026-11-17_<step>/`. Report figures live in `figures/`.
Run `paper_tm` only after writing the estimate from shipped example II.
Its limit is four hours. Only compatibility patches 0001 and 0002 were
needed; no algorithm or data change was made.

Steps 1 and 2 completed after patches 0001 and 0002. Before step 3, the
observed step-2 times give 7749.688 s compute, or 9419.626 s including 20%
and 120 s setup/export allowance (2 h 37 min). This is below four hours.
Command: `python3 experiments/baselines/csi/run.py paper_tm`.
It keeps the shipped antenna correction; only the paper settings listed
above change in the wrapper copy. Native CSI is omitted in this paper run.

Storage decision from the coordinator while step 3 was running:
"Commit at most about 5 MB per run: the contrast images, cost history,
timings, logs and small JSON." Full workspaces, per-frequency arrays and
figure workspaces stay local and are listed in `results/csi/.gitignore`.
A manifest records commands and SHA-256 hashes. Already pushed files and
history stay unchanged. Save a compact `final_contrast.mat` for scoring;
it retains unthresholded solver contrasts, without display masking.

Source inspection corrects two descriptions above: `xs` and `ys` in the
shipped drivers are half-widths in millimetres, not cell counts; record the
actual grid from `pars.Ninv`. The paper describes one small cylinder inside
the foam and a second adjacent outside, not two inside. Judge Figure 5 from
the paper itself. No image threshold is chosen in this activity.
