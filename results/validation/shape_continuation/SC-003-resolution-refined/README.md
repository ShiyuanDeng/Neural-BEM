# SC-003 — resolution screen and the first harder-shape failure

After the SC-002 cleanup, the same short k=1:0.25:2 ladder was run on the
paper's glider coefficients. The inverse completed in 154 forward evaluations,
but failed shape and unused-frequency prediction gates (relative boundary
error 0.230, prediction error 0.00998). The endpoint forward is resolved.
[Original failed pilot](../SC-003-glider-pilot/summary.json) is preserved.
This is not evidence that continuation fails: the pilot stops at k=2 and many
stages stop on iteration limits or constraint-limited small steps.

The subsequent independent resolution screen covers ellipse/glider at k=1,4,8,
contrast 1.44, and 64/128/256/512 nodes. It exposed a spline-integration error
in the arclength coordinates used to build the normal Fourier basis. Periodic
spectral integration replaces that calculation. Curve interpolation and all
acceptance tolerances remain unchanged. The reciprocal contraction now uses
blocked BLAS products with a roughly 32 MiB temporary cap instead of the
four-index einsum; both implement the same bilinear identity.

| 256→512 node Jacobian difference | Before | After |
|---|---:|---:|
| Ellipse, k=8 | 2.98e-9 | 5.37e-15 |
| Glider, k=1 | 3.11e-8 | 1.33e-11 |
| Glider, k=4 | 1.19e-6 | 5.43e-11 |
| Glider, k=8 | 2.89e-6 | 1.14e-10 |

These are refinement differences, not rigorous continuum error bounds.
Forward fields are unchanged. At glider k=8, the measured 512-node Jacobian
time falls from 0.404 s to 0.086 s. This is a single timing observation, not a
repeat-median complete-inverse speed comparison. The earlier 23.54× inverse
speedup is separately qualified by SC-002.

Tests include spectral arclength against an independently refined curve,
the BLAS contraction against the literal reciprocity sum, finite-difference
shape derivatives, and the existing physical/isolation controls. The saved
ellipse observations were replayed again after these numerical improvements.
See [ellipse regression](../SC-003-ellipse-regression/timing.json),
[before screen](../SC-003-resolution-screen/screen.json), and
[after screen](screen.json). Raw fields and selected tangent contractions are
stored in `responses.npz` for both screens.

Next: extend the frequency ladder with explicit storage/quadrature controls
and stage checkpoints. The failed k<=2 pilot is not overwritten or called a
successful reconstruction.
