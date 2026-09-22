# SC-009 — conservative geometric qualification

The ellipse repeats the same accepted inverse trajectory (21 forward calls,
8 Jacobians) after the evaluation-only error-bound correction. All gates pass.
The shape gate now tests the sampled boundary distance plus a conservative
bound for both polygon sampling and smooth-curve interpolation, normalized
by the truth's area-equivalent radius. The latter interpolation term uses the
Fourier second-derivative triangle bound and the linear-interpolation error
constant dt²/8. This is checked against a known continuous Hausdorff distance
for a harmonic perturbation of a circle.

The correction does not change forward fields, derivatives or the optimizer.
The earlier SC-008 glider is independently rescored in its geometry_check.json,
with its original inverse and summary preserved. Combined numerical controls:
42 passing tests, including the existing Kress isolation/block controls.
