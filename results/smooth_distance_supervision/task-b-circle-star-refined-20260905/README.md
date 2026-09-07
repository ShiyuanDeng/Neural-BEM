# Frozen smooth-distance supervision comparison

This Task-B diagnostic freezes a 65 mm circle and a five-lobe star
(`amplitude=0.2`, rotation `0.15` radians). Both target policies use the same
32-node training polygon, seeded global points, polygon boundary/offset sample
locations, initial 32-wide two-layer MLP, and 600-step budget. For the smooth
arm, samples on polygon edges receive their actual nonzero continuous-curve
distances. No normal-offset identity is assumed.

| Case / targets | Sampled target max error, mm | Independent field distance RMS, mm | Extracted drift, mm | Relative scattered-field error |
|---|---:|---:|---:|---:|
| Circle / polygon | 0.3130 | 0.1929 | 0.2334 | 0.0156791 |
| Circle / smooth | < 1e-12 | 0.1044 | 0.03847 | 0.000141712 |
| Star / polygon | 1.8943 | 3.5422 | 1.6050 | 0.0591357 |
| Star / smooth | < 1e-12 | 3.5959 | 0.5345 | 0.00379626 |

The table uses the finest extraction (`513²`, 1024 projected points,
Cartesian bandwidth 96). Refinement from the previous extraction changes the
curve set by 0.00018 / 0.00017 mm for the circle and 0.0185 / 0.0106 mm for the
star (polygon / smooth). Distance audits refine continuous closest points;
doubling outer set-distance samples from 512 to 1024 changes the reported
drift by at most 0.00181 mm. These are numerical agreement checks, not global
certificates for arbitrary unresolved curves.

The declared distance-target tolerance is 0.001 mm, versus a requested
representation tolerance of 0.2 mm. Independently tightening localization
from 512 to 1024 and target tolerance from `1e-9` to `1e-11` m changes the
reference distances by less than `1.2e-16` m on the 2048 independent points.
All extractions detect one component and satisfy negative-inside orientation.
Independent sign mismatches are 3 / 0 for circle and 8 / 2 for star.

Every final frozen-curve BEM result passes the declared `1e-7` relative
refinement gate; changes from N=256 to N=512 are at most `1.1e-13`.
The canonical circle agrees with independent Mie fields to `3.0e-15`
relative error. The star reference is separately refined Kress on its exact
analytic curve; it is not an independent solver comparison.

The smooth targets improve recovered interfaces and physical predictions in
this bounded test, but do not solve global SDF approximation: the star's
independent distance RMS slightly worsens, and its 0.5345 mm drift still
exceeds the 0.2 mm representation tolerance. All four 600-step fits fail the
deliberately strict redistance stopping tolerances; none is labelled a
successful production SDF export. Near-boundary sampling was held fixed;
an alternative smooth normal-offset sampling experiment has not been run.

The complete run took 114.9 s. Each redistance call took approximately
1.8–2.0 s including target construction; most diagnostic time belongs to
independent extraction/set-distance and physical-field refinement. These
figures are not inverse-loop speedups.

`summary.json` records exact commands, source hashes and dirty-tree state,
all acquisition/material data, seeds, numerical resolutions, convergence
states, calls, and timings. `arrays.npz` contains non-pickled model state,
sampled distances, frozen canonical/representation fields, and extracted
Fourier coefficients. Earlier `task-b-circle-star-v2-20260905` results retain
the two-extraction development experiment; this bundle repeats the identical
600-step fits and adds bandwidth-96 refinement without retuning them.
