# Long acquisition: geometry findings

Both inverse arms completed and stopped with `no_decreasing_neural_step`, before their declared work caps. The saved first five accepted raw and converted geometries exactly reproduce the short comparison.

| Final result | Paired-8 E0 | Multistatic-8 E1 |
|---|---:|---:|
| Accepted updates | 42 | 31 |
| Attempted candidates | 349 | 312 |
| Raw symmetric RMS error (mm) | 14.097 | 9.506 |
| Converted symmetric RMS error (mm) | 14.104 | 9.507 |
| Raw symmetric mean error (mm) | 11.020 | 7.691 |
| Raw sampled Hausdorff error (mm) | 37.103 | 23.109 |
| Shared 3 GHz relative error | 0.721501 | 0.544476 |
| Polygon area centroid error (mm) | 16.815 | 8.900 |
| On-contour gradient spread | 21.088 | 6.667 |
| Accepted conversion error (mm) | 0.190273 | 0.199955 |

Multistatic's aggregate geometric advantage persists. At the common cap of 312 attempted candidates, E0 has reached state 41 (14.097 mm raw symmetric RMS) and E1 state 31 (9.506 mm). It is also lower at every compared accepted-event candidate budget; the JSON records the full stepwise comparison. Equal candidate counts are the declared work proxy, not identical CPU effort.

The five lobes are not recovered. E1 mean radius moves from 60.002 to 50.145 mm (truth 50 mm), and centroid error from 28.306 to 8.900 mm. Its centroid-based polar m5 amplitude instead shrinks from 7.181 to 1.530 mm, versus the target 12.5 mm. Phase improves from 14.164° to 8.990°, but phase-aware coefficient error only changes 12.200 to 11.468 mm. It reaches its retrospective minimum of 11.198 mm at state 19 and then worsens. E1 unwanted modes 2–10 excluding 5 grow from 0.172 to 3.766 mm RMS; its final m4 amplitude is 4.184 mm, larger than m5.

E0 polar m5 error worsens throughout its valid range: 12.200 mm at initialization to 18.739 mm at state 24. From state 25 the contour is not polar single-valued about its polygon area centroid, so final polar amplitudes, phase, and m5 error are unavailable. This does not imply an invalid topological boundary; it invalidates this radial description.

Retrospective minima are descriptive only. E0 raw symmetric RMS is best at state 36 (13.980 mm) and shared evaluation at state 35 (0.709667), both slightly better than its final state. E1 raw symmetric RMS and shared evaluation decrease through the final state, while its m5 error has already passed its best value. No truth/evaluation metric was used to select a training step or stopping point.

All 42 E0 and 31 E1 accepted transitions have finite raw and converted through-mode-20 signed normal scores. E0 has 32 positive and 10 negative transitions (negative states 27–30 and 36–41); E1 has 31 positive transitions. These are local nearest-target squared-distance directional scores, not complete finite symmetric-error changes or polar m5 recovery scores.

**Finite proposal-motion evidence is incomplete.** At common predicted 20 µm RMS, E0 has actual scores for 16/24 selected direction probes; all four probes at states 40 and 42 fail topology. E1 has actual scores for 12/20 probes; all four at states 30 and 31 fail the conversion-distance gate. The optimizer states were selected in advance, not by outcomes. For E1's valid states 0, 10 and 20, Adam's score remains slightly better than total steepest descent. E0's total gradient outperforms Adam at valid states 10, 20 and 30; late predicted scores lack admissible finite confirmation. This is not a full optimizer comparison.

The early acquisition improvement survives, while field conditioning, fidelity-limited steps, and poor lobe recovery remain. These data do not automatically establish a higher-frequency, neural-GN, optimizer-change, or relaxed-limit remedy.

The FFT phase calculation corrects the stored −π origin with `(−1)^m`. The reference center is each polygon's area centroid, not an arclength centroid. Distances use arc-weighted saved polygon vertices and point-to-segment distances in both directions; maxima are sampled-polyline estimates. `motion_review.json` contains full per-state metrics; `findings.json` records retrospective minima, matched budgets, provenance, and incomplete-probe coverage. No BEM, neural inverse, or new geometry extraction ran for this review.
