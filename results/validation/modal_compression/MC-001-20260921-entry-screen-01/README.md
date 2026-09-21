# MC-001 Stage A — modal entries and derivatives

2026-09-21. Complete. **Stage B not released.**

[Scientific closeout](../../../../docs/iterations/modal_compression/iteration_02/01_results.md)
contains interpretation, limits and failure discussion.
[Open the visual gallery](gallery.html) for all 18 standalone PNG/SVG figures.

All 12 reference controls qualified. The common mask meets field error <=1e-6,
every physical derivative error <=1e-3 and represented slots <=50% of the
qualified dense modal reference only on the circle control. No noncircle passes;
the requirement for two noncircles at both kD=2 and 10 is unmet. The nearby-shape,
held-out acquisition/direction and local inverse tests did not run.

This is a full-assembly diagnostic, not a sparse implementation or speed claim.
Shared support positions include a separately represented exact identity.
The full matrix dimension comes from the smallest qualified cutoff on the
predeclared ladder, not a claim of globally minimal dimension.

## Contents

- `config.json`: exact inputs, cutoffs, acquisition, numerical source hashes,
  thread settings and revision.
- `summary.json`: release decision, 210.7-second main run, 288 charged
  assemblies, 265 factorizations, 0.857 GiB peak RSS, no source drift.
- Each `<shape>_kd<value>/case.json`: qualification, FD/grid controls,
  magnitude counts, individual/union tails, every mask's solve/derivative errors.
- Each `arrays.npz`: full selected operator/acquisition, derivatives, states,
  oracle data/derivatives and masks. No pickled Python objects.
- `readback.json`: 144 reconstructed masks and saved-array re-solves
  reproduced the recorded decision.
- `figures/`: 18 PNG/SVG pairs; heatmaps, retention curves, solve errors,
  individual derivative families and physical geometries.
- `gallery.html`: local navigation; no hosted deployment.

Core tests passed: 7 tests in 4.43 seconds, checking tiny-tail accounting,
normal displacement, analytic/FD convergence, independent circle physics and
the derivative of the same frozen-mask forward.

## Reproduce

Run at repository root; the first command requires a **new** output directory.
The last two commands can be used on this existing bundle for read-back and
figure regeneration. Historical source hashes must match for the audit.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_entry_screen.run --output results/validation/modal_compression/MC-001-NEW-ID
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_entry_screen.audit results/validation/modal_compression/MC-001-20260921-entry-screen-01
env MPLCONFIGDIR=/tmp/modal-entry-mpl OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.modal_entry_screen.plots results/validation/modal_compression/MC-001-20260921-entry-screen-01
env MPLCONFIGDIR=/tmp/modal-entry-mpl OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. /home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/modal_compression/MC-001-20260921-entry-screen-01/make_brief_figure.py
```
