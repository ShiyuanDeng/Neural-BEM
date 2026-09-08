# Acquisition motion measurements

Source: `/home/drdeng/Neural_SDF_BEM_AD/results/validation/implicit_mlp_adjoint/iteration-02-final/long-acquisition-20260908T174300326691Z`.

Saved-data algebra only; no inverse, BEM, or extraction. These measurements require review before promoting a factor.

| Final saved geometry | Paired-8 | Multistatic-8 |
|---|---:|---:|
| Accepted state | 42 | 31 |
| Candidates through accepted state | 319 | 282 |
| Raw symmetric RMS (mm) | 14.097 | 9.506 |
| Raw symmetric mean (mm) | 11.020 | 7.691 |
| Raw sampled Hausdorff (mm) | 37.103 | 23.109 |
| Target-to-raw mean (mm) | 9.483 | 8.502 |
| Converted symmetric RMS (mm) | 14.104 | 9.507 |
| Centroid error (mm) | 16.815 | 8.900 |
| Polar m5 coefficient error (mm) | unavailable | 11.468 |
| Polar m5 amplitude (mm) | unavailable | 1.530 |
| Polar m5 rotation from target (deg) | unavailable | 8.990 |
| Modes 2–10 RMS excluding 5 (mm) | unavailable | 3.766 |
| Shared 3 GHz relative error | 0.721501 | 0.544476 |

| Shared candidate budget | Paired accepted state | Multistatic accepted state | Paired raw RMS (mm) | Multistatic raw RMS (mm) |
|---:|---:|---:|---:|---:|
| 7 | 1 | 1 | 19.742 | 19.456 |
| 14 | 2 | 2 | 19.595 | 19.009 |
| 21 | 3 | 3 | 19.458 | 18.559 |
| 63 | 10 | 9 | 17.591 | 15.745 |
| 70 | 11 | 10 | 17.436 | 15.270 |
| 77 | 12 | 11 | 17.268 | 14.801 |
| 84 | 13 | 12 | 17.089 | 14.340 |
| 91 | 14 | 13 | 16.900 | 13.887 |
| 98 | 15 | 14 | 16.710 | 13.441 |
| 312 | 41 | 31 | 14.097 | 9.506 |

E0: 32/42 interpretable saved raw motions have positive nearest-target descent scores; their sum is 3.7458294e-05 m². Proposal diagnostics cover saved states [0, 10, 20, 30, 40, 42]. Scores from selected proposal states must not be extrapolated to unmeasured states.

E1: 31/31 interpretable saved raw motions have positive nearest-target descent scores; their sum is 0.0001451116 m². Proposal diagnostics cover saved states [0, 10, 20, 30, 31]. Scores from selected proposal states must not be extrapolated to unmeasured states.

Arc-length-weighted directed point-to-closed-polyline distances use saved raw/converted vertices and 4096 exact target vertices. Symmetric means average directed means; symmetric RMS averages directed mean squares before the square root. Hausdorff is the maximum of the sampled directed maxima, not an exact smooth-curve supremum.

The analytic target r=0.05+0.0125*cos(5 theta), center (0.5,0.5), was validated against 1024 archived vertices to 1e-14 m.

The stored radial FFT uses theta_j=-pi+2pi*j/N about each polygon AREA centroid (shoelace formula), not an arclength centroid. Physical cosine/sine coefficients are 2*(-1)^m*Re(c_m), -2*(-1)^m*Im(c_m). The m5 coefficient error is its distance from (0.0125 m,0); divide by sqrt(2) for its radial RMS contribution. Center error is scored separately.

Saved normal-motion scores are arc-weighted inner products with nearest-target normal projections. Positive scores locally decrease half squared distance at unique nearest points. Through-mode-20 scores are not finite total geometric-error changes; normal/arclength mode 5 is not polar mode 5.

Shared budgets are derived from accepted trial counts common to both arms plus the minimum completed candidate count. Each comparison uses the latest saved accepted geometry at or below that budget. No future accepted update is credited.

The controlling plan requires actual neural geometric improvement at matched work; training loss alone does not qualify. Review field conditioning, phase-aware mode error, both boundary-distance directions, accepted/rejected geometry, and shared evaluation before choosing a longer run or another bounded diagnostic.
