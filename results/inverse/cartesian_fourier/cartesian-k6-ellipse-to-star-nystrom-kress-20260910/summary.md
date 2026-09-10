# Direct Cartesian Fourier inverse (no MLP)

Target: `star`; initialization contour: wrong `ellipse`.

The accepted optimization state is a Cartesian Fourier curve in the
polar-angle parameter at band `K=6` (26 coefficients,
25 active after the exact phase gauge is removed).
No neural field is constructed, evaluated, trained or audited, and no
arc-length refit occurs at any point.

| Quantity | Initial | Final | Radial reference final |
|---|---:|---:|---:|
| Train rel. L2 | 1.197e+00 | 1.296e-07 | 1.068e-08 |
| Holdout rel. L2 | 1.136e+00 | 1.127e-07 | 1.339e-08 |
| Max boundary error | 4.181e-02 m | 2.761e-09 m | 2.570e-10 m |
| Accepted updates | - | 41 | 44 |

Parity gates met: **False** (train and holdout `<= 1e-07`, boundary error `<= 1e-08 m`).

Stop reason: `stable_data_and_geometry`.

One-time polar-angle projection of the initial contour: `0.514` mm RMS / `0.853` mm maximum. Every later state is reached by increment, never by refitting.
