# Saved ellipse startup diagnosis

These bounded, field/geometry-only probes use the exact `initial_model.pt` from
`iteration-02-suite-20260908T163753015880Z/ellipse-startup`. No inverse, BEM solve,
pretraining update, or network change was run. The original checkpoint is
unchanged; the replay report records its SHA-256.

The initialization is already wrong before Method B: its raw contour is about
**43.5 mm** from the prescribed initial ellipse, consistently on extraction grids
257, 513, and 1025. Its perimeter is **0.5647 m**, versus **0.3539 m** for the
prescribed ellipse. The saved pretraining field RMS mismatch is **18.36 mm**.
On the 513-grid raw contour, gradient norms are **0.587–1.101**, RMS **0.994**.
This is a measured initialization problem; it does not establish the cause of
the pretraining failure or imply that field-gradient repair will fix its shape.

The resolution probe isolates a second effect. At bandwidth 96, increasing
projected samples from 256 to 512 changes the conversion error from about
0.874 mm to **0.5085 mm**, and refinement change from about 89 µm to **4.74 µm**.
At 1024 projected samples, conversion error remains **0.5132 mm**. Increasing
arc-length density from 2048 to 4096 at the original 256 projected samples
also leaves conversion error near 0.874 mm. Consequently the startup sweep now
uses 512 projected samples and arc-length density 2048 at bandwidth 96; it still
correctly rejects the saved initialization against the unchanged **0.2 mm** limit.

`probe.json` records extraction/sample-count measurements.
`requalified/qualification.json` records the updated startup replay, including
raw-vs-prescribed initialization characterization and the individual numeric
rejection gates. That replay completed in **9.84 s** and returned exit code 2
(`unqualified`). Total geometry probe runtime was approximately 33 seconds.

The ellipse inverse remains unavailable for these weights. Increasing conversion
resolution cannot make the raw neural contour match the prescribed ellipse.
The previously documented zero-pretraining-Eikonal ellipse trial produced five
components, so this diagnostic does not promote that failed alternative or
silently change the pretraining objective.

Reproduce the startup diagnostic with a fresh output directory:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python run_implicit_mlp_ellipse_startup.py \
  --checkpoint results/validation/implicit_mlp_adjoint/iteration-02-suite-20260908T163753015880Z/ellipse-startup/initial_model.pt \
  --max-wall-seconds 25 --output-dir /tmp/ellipse-startup-replay
```
