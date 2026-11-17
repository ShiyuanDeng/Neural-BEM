# Run the Fresnel dielectric cylinder

## Status and coordinator decisions

Authorized and started 17 November 2026. The coordinator accepted activity
01 and opened this activity without another go. Stop after reporting it.
Use the current branch; edit only CSI paths. No solver or scoring edits.

The coordinator set: keep shipped radii; keep exported numerical coordinates;
use protocol version 1 support at half the signed peak, retaining 0.3 and
0.7 sensitivity scores. Import the existing comparison scoring functions.
MR-CSI's Figure 5 disagreement stays unexplained. No settings change during
the reading check. Long runs must use `setsid nohup`. BRG runs MATLAB too;
record the overlap and label timings indicative. Eight MATLAB threads.

## Questions and sequence

1. Reading check, at most 30 minutes: compare paper Figure 5's MR-CSI
   constraints, regularization, start, iterations and data with the shipped
   driver and function. List established differences and possible causes;
   do not tune. Check patch 0002 by explicit linear interpolation of a
   refined random array at query nodes `1:2:end`, versus direct sampling.
   No check run may exceed one minute.
2. Run measured `dielTM_dec8f`, all three methods, all eight 1-8 GHz
   frequencies, 2048 iterations, their back-propagation start. The coordinator
   chose centre [0,0,0], half-widths 70 mm and 1.25 mm cells because the
   driver/paper do not give this case's grid. Change only our driver copy.
   Keep the first-opus 36-source, 72-position masked receiver layout and
   shipped calibration, signs and antenna radii. No added noise or warm-up.
3. Save raw unmasked contrasts, per-method native times and cost histories.
   Preview support area, centroid and mean support contrast at 0.5 of the
   signed peak, plus sensitivities 0.3/0.7. Get cylinder radius, position and
   permittivity from Belkebir and Saillard (2001), not memory. Cite it and
   preserve the physical coordinate mapping. Report scoring API limits.
4. Fit an indicative time model against cells, sources and frequencies
   using all completed runs. Estimate ten TG-002 shapes at contrasts 0.5
   and 4, all three methods (60 fits), simulated in this Fresnel layout.
   Give total hours and limitations. Do not generate data or start fits.

## Comparisons and success criteria

The explicit interpolation check agrees to rounding. All three methods
complete the specified run without altering upstream numerical settings.
Retain every component in the imported image support and score only after
inversion. A poor recovery is a result, not a reason to tune or rerun.
Record source-backed truth, actual grids, overlap, time, failures and the
full-to-compact export check. No BEM comparison or success cut-off yet.

## Budget and estimates

Reading/check budget: 30 minutes, each check under 60 seconds. Before the
long run, save a numeric estimate from activity 01's measured TM rates.
Initial expected total is about three hours including reading and allowance;
do not start if the resulting point estimate exceeds four hours. Enforce a
four-hour activity wall limit. The estimate is indicative under BRG overlap.
No full inversion is run for calibration, grid testing or timing estimation.

Preflight recorded before the long run: 7044.089 s native compute for all
three methods; 10372.907 s including 20%, setup/export and all 30 minutes
of reading. This is 2 h 52 min 53 s, below four hours. Detached run limit:
12600 s, reserving the reading allowance. See `reading.md` and the saved
`preflight_time_model.json`. The explicit interpolation check passed all
eight cases with zero difference; the failed first harness is retained.

## Commands and outputs

- Reading evidence: `results/csi/fresnel/2026-11-17_reading_check/`.
- Check: `timeout 60 matlab -batch` running our explicit interpolation check.
- Long run: `setsid nohup python3 experiments/baselines/csi/run.py diel_tm`
  with its logs redirected under `results/csi/fresnel/`; poll saved status.
- Run outputs: `results/csi/fresnel/2026-11-17_diel_tm/`; analysis, score
  preview and time-model commands are recorded with the actual run.
- Report: `results.md` here; figures in `figures/` here.
- Commit at most about 5 MB per run. Full fields/workspaces/source snapshots
  stay local and git-ignored under `results/csi/.gitignore`, with commands
  and SHA-256 hashes in a manifest. Keep all pushed history unchanged.
- Commit and push each check/run, failed runs included, using named paths:
  `git add <CSI paths>` then `git commit -m "..." -- <CSI paths>`.
