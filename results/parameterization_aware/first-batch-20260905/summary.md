# Parameterization-aware fitting: bounded C1/C2 experiment

C1 changes only the exact ellipse parameterization. C2 shares frozen projected points and varies Cartesian bandwidth independently of BEM nodes.

The new ordered-label variable-projection method is a simpler experiment inspired by [Zhao–Serkh](https://arxiv.org/abs/2301.04241), not their speed/tangent-angle algorithm.

Geometry gate: 0.0002 m; maximum per-frequency field gate: 0.001. The source is noiseless homogeneous full-space TMz.

| Case | Arm | Accuracy-eligible | Observed matched-work win |
|---|---|---:|---:|
| circle | skip-arclength | True | True |
| circle | ordered-label-unregularized | True | False |
| circle | ordered-label-penalized | True | False |
| ellipse | skip-arclength | True | False |
| ellipse | ordered-label-unregularized | True | False |
| ellipse | ordered-label-penalized | True | False |
| star | skip-arclength | False | False |
| star | ordered-label-unregularized | True | False |
| star | ordered-label-penalized | True | False |
| nonstar | skip-arclength | False | False |
| nonstar | ordered-label-unregularized | True | False |
| nonstar | ordered-label-penalized | False | False |

Methods: 82; rows: 246; wall time: 45.50 s.

Fit failures and baseline fallbacks remain in metrics. Timings are one bounded sample, not a statistical speedup claim. No production default was changed. Conditioning, derivative/normal errors, spectra, closest-point refinement agreement, oracle convergence and full source provenance are in the JSON/CSV bundle.

The non-star reference is an invertible parabolic shear of the unit circle. Its visibility-kernel tangent halfplanes are inconsistent, so it is not star-shaped about any point. Its native Cartesian bandwidth is two.
