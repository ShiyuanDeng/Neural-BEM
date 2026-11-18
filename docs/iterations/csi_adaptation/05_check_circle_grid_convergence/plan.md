# Check circle forward-grid convergence

18 November 2026. Coordinator request during activity 04: first finish
the resume path, then measure circle data at 1.25, 0.625 and 0.3125 mm,
then reproduce small exact-circle fits. The resume is ready and pushed;
the original campaign keeps running untouched. This is forward-only work,
with no inversion or changes to campaign settings or frozen data.

Question: do the native-generator errors against the exact circle reduce
under grid refinement? Also measure the equivalent contrast/radius/centre
shifts in an exact-circle fit, as a diagnostic only. These are not baseline
fits or tuned campaign inputs. Truth is the frozen TG-002 circle (50 mm
radius, its unchanged centre, relative permittivity 4).

Reuse the exact retained 0.625 mm table and the BEM side's read-only
truth_predictions.npz and forward_checks.json. Match its measured-pair
mask and C order, conjugate the exp(+j omega t) table once, and first
reproduce its eight reported relative-L2 values. Use the table norm for
the primary row to match that report; also save reference-norm errors.
The reference predictions match the independent exact series to 1e-13.

Generate new tables only at 1.25 and 0.3125 mm in
results/csi/grid_check/2026-11-18_circle/. Use a separate driver copied
from generate_synthetic.m, changing only cell size, grid dimensions and
the matching coordinate assertions. Keep physical domain, PML cell count,
native matrix/material averaging, sources, receiver kernel and all eight
frequencies unchanged. Keep the exact executed driver and hashes. The
binary dual-cell staircase and native four-cell Ez average are retained.

Budget: two forward-only MATLAB runs, sequential, one MATLAB process for
this activity, at most 10 minutes per grid. No inverse iterations. Start
only with room for the observed/predicted family RSS plus 14 GiB reserve;
stop only this activity's process group if available memory reaches a
14.25 GiB margin or its family RSS reaches 6 GiB. Skip the fine grid if
the measured/predicted memory requirement exceeds about 6 GiB. Save any
failure and report missing rows rather than weaken these limits. The
existing CSI and BRG processes are never signalled.

Commands use the EMNerf Python, PYTHONPATH=solvers:., python -B, and
experiments.baselines.csi.circle_grid_check with --generate 1.25 or
--generate 0.3125, followed by --analyze and --fit. The controller saves
exact argv, environment, timing, resource samples and source/data hashes.
Raw tables/material maps stay local and ignored; compact JSON/CSV/logs
and the executed drivers are committed and pushed after each run.

For the add-on, copy the exact-circle formula from csi_forward_check.py
into CSI-owned code without importing or editing BEM code. Fit one
positive contrast per frequency with radius/centre fixed, then one common
radius, contrast and x/y centre across all eight frequencies. Start at
truth; no grid search. Use a single CPU thread. Compare the 0.625 mm
diagnostic with the coordinator's supplied numbers and report any gap.
No fitted value is used to regenerate inputs or change a campaign result.

Success: the reproduced 0.625 mm row; two new rows or recorded memory
skips/failures; observed per-frequency convergence orders; boundary rule;
diagnostic-fit table; commands, hashes and resource limits. Report the
grid rows in at most twelve lines. BEM-side paths are read-only.
