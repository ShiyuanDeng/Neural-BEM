# Geometry/field review of the completed acquisition comparison

Field conditioning does **not currently block acquisition promotion**. This
conclusion covers five accepted updates from one shared saved initialization;
it does not establish stability over a long inverse.

| Accepted-state quantity | Shared initial | E0 paired-8, state 5 | E1 multistatic-8, state 5 |
|---|---:|---:|---:|
| Minimum contour gradient norm | 0.8199 | 0.8181 | 0.7652 |
| Maximum contour gradient norm | 1.2302 | 1.3686 | 1.2655 |
| Gradient spread | 1.5005 | 1.6730 | 1.6537 |
| Gradient RMS | 1.0135 | 1.0357 | 1.0074 |
| Contour Eikonal mean square, from saved spectrum | 0.00529 | 0.01292 | 0.00947 |
| Production conversion error, µm | 1.410 | 5.561 | 2.641 |
| Production refinement change, µm | 0.185 | 0.031 | 0.111 |

Both accepted trajectories retain one component and nonzero, unclipped contour
gradients. E1's final conversion error uses only 1.32% of the unchanged 200 µm
budget; refinement change uses 1.11% of the unchanged 10 µm budget. Its minimum
gradient decreases monotonically, so continued monitoring matters, but its
spread and contour Eikonal mean square are slightly better than E0 at state 5.
The box Eikonal penalty increases faster in E1; that is not equivalent to worse
interface conditioning, as the separately recorded contour measurements show.

For **all ten accepted steps**, the next larger rejected proposal binds only on
the 2 mm boundary-motion limit. E1's four topology and two conversion rejections
occur at Adam factors 1 or 0.5, versus accepted factor 1/64. They show the fixed
guards rejecting large proposals; they do not show accepted-state conversion
failure or the historical terminal refinement bottleneck. All twenty common
20 µm proposal probes per arm successfully extract and convert.

The historical 25-step field-only repairs do not justify changing sampling now.
At saved state 32, gradient spread changes only 4.054→3.954 while the contour
moves by up to 87.7 µm. At state 47, spread worsens 11.528→11.718, minimum norm
falls 0.308→0.297, and conversion distance worsens 144.4→146.8 µm despite a better
refinement-change metric; maximum contour movement is 140.9 µm. These tests did
not demonstrate the strong conditioning repair with nearly fixed geometry
required to promote contour-aware Eikonal sampling. They also do not rule out a
better-resolved future field-repair experiment.

No actual geometry implementation defect is exposed by these saved records.
Marching-cell hashes change when contours move across grid cells; that alone is
not a topology failure. Single-component extraction is also not a certificate
of full differential branch consistency. Any longer comparison should retain
the same fixed limits and record minimum gradient, spread, conversion metrics,
binding constraints, and signed geometric progress at every accepted state.

`geometry_review.json` records the measured summaries and source hashes;
`geometry_review.csv` contains every accepted-state field/geometry row.
`geometry_review.py` reproduces the saved-data arithmetic without any model,
extraction, BEM, or inverse evaluation.
