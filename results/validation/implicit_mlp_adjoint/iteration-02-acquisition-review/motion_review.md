# Acquisition motion review

Source: `results/validation/implicit_mlp_adjoint/iteration-02-final/inverse-20260908T170732213677Z`. Saved-data algebra only; no neural optimization, BEM, or new extraction.

Multistatic is supported as the candidate principal factor for the next isolated star comparison. The short trajectory shows more coordinated geometric correction, including a better phase-aware five-lobe coefficient, at comparable and exactly matched candidate work. This does not establish long-run convergence.

| At five accepted updates | Paired-8 | Multistatic-8 |
|---|---:|---:|
| Attempted candidates | 33 | 35 |
| Raw symmetric RMS distance (mm) | 18.926 | 17.642 |
| Raw symmetric mean distance (mm) | 14.916 | 14.723 |
| Raw sampled Hausdorff distance (mm) | 37.589 | 37.132 |
| Raw target-to-curve mean distance (mm) | 14.381 | 14.907 |
| Converted symmetric RMS distance (mm) | 18.929 | 17.646 |
| Centroid error (mm) | 25.770 | 25.069 |
| Polar m5 coefficient error (mm) | 12.746 | 11.738 |
| Polar m5 amplitude (mm) | 6.371 | 6.575 |
| Polar m5 rotation from truth (deg) | 15.507 | 13.591 |
| Modes 2–10 RMS excluding 5 (mm) | 2.571 | 0.955 |
| Shared 3 GHz relative error | 0.942309 | 0.923667 |

Both starts are identical. At exactly 21 candidate evaluations, both have completed 3 updates: raw symmetric RMS is 19.458 mm paired versus 18.559 mm multistatic. At the stricter common cap 33, paired has 5 accepted updates and multistatic 4: 18.926 mm versus 18.104 mm. Multistatic retains its aggregate geometric advantage without credit for extra candidates.

Actual raw and converted motion scores are positive on every accepted update, with no missing normal roots. Their cumulative through-mode 20 raw score is 1.4172036e-05 m² paired versus 4.6574529e-05 m² multistatic. This is a local nearest-target squared-distance directional score, not the finite reduction of the total boundary error.

The initial polygon-area-centroid-based polar m5 amplitude is 7.181 mm versus the target 12.5 mm; it decreases in both arms. However, amplitude alone misses phase: m5 coefficient error changes 12.200→12.746 mm for paired and 12.200→11.738 mm for multistatic. Multistatic rotates toward the target phase; paired rotates away. The centroid is the polygon area centroid computed by the shoelace formula, not the average vertex or arclength centroid. The stored FFT origin of −π is corrected by multiplying complex mode m by (−1)^m. Normal/arclength mode 5 signed scores and polar mode 5 coefficients measure different quantities and must not be equated.

The result is not uniformly better: paired finishes with slightly lower one-sided curve-to-target maximum and target-to-curve mean distance, while multistatic has lower symmetric RMS and sampled Hausdorff distance; field-gradient spread grows in both arms (1.500→1.673 paired, 1.654 multistatic), while multistatic minimum G falls 0.820→0.765. Multistatic also rejects several large proposals for topology/conversion. Accepted conversion errors remain small (5.561 µm paired, 2.641 µm multistatic).

At common 20 µm predicted RMS motion, Adam improves the nearest-target score over total steepest descent at every sampled state in both arms. These fresh records do not justify replacing Adam. Original-band multistatic still makes progress; neither a high-frequency switch nor neural GN is compelled by these five steps.

Boundary-distance calculations use arc-length-weighted distances between saved contour vertices and closed polygon segments in both directions; maxima are sampled-polyline Hausdorff estimates. The 4096-point analytic target was checked against all 1024 archived exact target vertices to 1e-14 m. The JSON contains full per-step metrics, source hashes, formulas, and proposal scores.

The controlling [final plan](/home/drdeng/Neural_SDF_BEM_AD/docs/iterations/implicit_mlp/iteration_02/02_proposals/04_final_plan.md) Stage 7 promotes actual neural geometric improvement at matched work. Section 18B supports multistatic as the selected factor; Section 19 calls for a star-only longer comparison with fixed initial weights, unchanged validated physics, fidelity/rollback checks, and disjoint evaluation. The early field-gradient spread remains modest and similar between arms, but continued drift needs monitoring.
