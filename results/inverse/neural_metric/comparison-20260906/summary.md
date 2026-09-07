# Frozen neural tangent metric comparison

All arms reconstruct an explicit, gauge-fixed K5 radial Fourier curve with the verified full Kress objective derivative.
The neural arms use frozen random-feature metrics from the wrong exact-circle initialization: 65 active output-head columns, not learned hidden-network or direct SDF optimization.
No representation was trained, extracted or synchronized during reconstruction. Losses across frequency stages are different objectives.

| Case | Metric | Accepted | Stop reason | Physics qualified | Refined training error | Held-out error | Geometry RMS (mm) | Forward solves | Reconstruction (s) |
|---|---|---:|---|---|---:|---:|---:|---:|---:|
| circle | identity | 15 | loss_tolerance | True | 0.003905 | 0.04008 | 0.064 | 40 | 34.80 |
| circle | sobolev | 13 | loss_tolerance | True | 0.006851 | 0.07527 | 0.114 | 30 | 29.14 |
| circle | neural_seed0 | 15 | iteration_budget | True | 0.1297 | 1.528 | 2.292 | 28 | 29.49 |
| circle | neural_seed1 | 15 | iteration_budget | True | 0.06747 | 0.5765 | 1.043 | 28 | 28.15 |
| circle | neural_seed2 | 15 | iteration_budget | True | 0.1076 | 1.073 | 1.698 | 28 | 36.79 |
| star | identity | 15 | iteration_budget | True | 0.2776 | 0.6039 | 6.556 | 28 | 36.29 |
| star | sobolev | 15 | iteration_budget | True | 0.308 | 0.5388 | 6.055 | 28 | 36.34 |
| star | neural_seed0 | 15 | iteration_budget | True | 0.4885 | 0.8866 | 12.399 | 28 | 29.17 |
| star | neural_seed1 | 15 | iteration_budget | True | 0.4609 | 0.7896 | 10.942 | 28 | 27.89 |
| star | neural_seed2 | 15 | iteration_budget | True | 0.5578 | 0.8845 | 10.621 | 28 | 33.39 |

Iteration/forward-budget exits and line-search failures are not reported as convergence.
Physical refinement and held-out evaluation costs are separate from reconstruction; initial model/metric setup is charged to every run.
The cap is 160 total frequency-specific forward calls per run, not 160 calls for each frequency. Adjoint/operator costs are separately counted.
The explicit Sobolev length .35 is a predeclared moderate smoother. Beating it would not separate neural coupling from stronger smoothing; that needs an additional spectral-matched explicit control.
The chart is fixed, finite-dimensional and star-shaped. This experiment does not test topology changes or prove an advantage for signed-distance values.
