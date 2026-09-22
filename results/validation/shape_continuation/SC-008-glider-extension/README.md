# SC-008 — qualified glider extension through k=12

Resumes the safeguarded SC-005 endpoint at k=4.75 and continues in steps of
0.25 through k=12, with the same contrast 1.44, optimizer, tolerances and
wavelength-scaled resolution policy. This is a continuation from the earlier
unit-circle run, with a **new explicit budget**, not a same-budget comparison.
The parent files are hashed in the manifest; all 14 overlapping observation
matrices and their acquisitions are bitwise identical to SC-005.

All 30 requested stages complete using 522 new forward evaluations and 196
Jacobians, with zero failed forwards. The cumulative inverse count is 2022.
Every stage passes both N/2N field and full normal-Jacobian checks. The largest
relative differences are 4.4e-15 for fields and 1.35e-13 for Jacobians.
The final stage uses 328 stored Fourier modes, 43 normal update modes,
24 curvature modes and 658 Kress nodes. Its curvature tail is 0.0862.

The endpoint passes the held-out prediction and shape gates:

- Held-out relative field error: **9.98e-6** at unused k=9.375 and rotated
  23-direction / 29-receiver acquisition.
- Sampled relative boundary error: **0.001395** (about 0.14%).
- Conservative continuous-boundary error upper bound: **0.001803** (about
  0.18%) at 16384 samples, below the declared 0.01 shape threshold.
- Final training residual: **2.471e-5**, with a `small_step` stop. This is
  above the stricter 1e-5 data-fit tolerance and is not labeled a data-fit stop.

The [geometry check](geometry_check.json) was recomputed after the run to
include both polygon sampling and smooth-curve interpolation error in the
bound. The original summary is retained unchanged. Sampling at 8192 and 16384
changes the estimated distance by 7.4e-9. New runs use the conservative upper
bound in the shape gate. This scoring correction does not change the inverse.

Wall times: 33.3 s observation generation, 440.2 s inverse **including** every
field/Jacobian stage check, and 232.9 s endpoint scoring. The high-resolution
checks are substantial; the sub-second ellipse timing is not a timing claim
for this longer dense-BEM run.

[Summary and all trials](summary.json) · [provenance](manifest.json) ·
[artifact audit](audit.json) · [recovery plot](recovery.png).
The plot's dashed initial curve is this restart's k=4.75 endpoint; the original
unit-circle start and earlier progress are retained in SC-005.

This qualifies one full-aperture, known-contrast, single-component hard-shape
case. It does not reproduce the paper's 117-frequency campaign, its contrast
study or cavity cases, and does not establish general robustness. It provides
a checked baseline on which harmonic/frequency policies can be compared.
