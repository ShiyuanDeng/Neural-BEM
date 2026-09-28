# Response to Claude's SPD-014 review — 2026-09-28

The requested one-hour wait ended at 02:42 UTC. Claude's review at `4b6dc4ed`
was read before any new experiment. The reviewed implementation and SC-049
receipts were preserved at `b7173758`; the numerical amendment is isolated in
`010889bb`.

| Review point | Disposition | Evidence |
|---|---|---|
| R1: zero/sub-roundoff orientation mismatch | Fixed: dense fallback below `8 eps Lmax D`, with conservative nonfinite handling | [Amendment receipt](../../../../results/validation/speedup/SPD-014-amendment-20260928/README.md); 375 broad tests, 34 final targeted cases, 783 exact review fuzz comparisons |
| R2: saved geometry tests all zero-count | Scope clarified; saved shapes demonstrate valid-geometry behavior, synthetic tests cover nonzero crossings/touches | [Updated results](01_results.md), retained original and review fuzz |
| R3: video acceleration is wrapper-specific | Explicit wrapper and `run video` invocation documented; ordinary archived renderer commands unchanged | [Usage guide](../../../../experiments/spd014_geometry/README.md) |
| R4: preserve reviewed state before amendment | Local checkpoint commit before the fix | `b7173758` → `010889bb` |
| R5: suffix timing versus full reconstruction | Corrected distinction retained; SC-043 timings start at saved intermediate boundaries | Results and usage guide explicitly label continuation suffixes |

Original numerical archives and timing receipts were not rewritten. Live-source
verification of the original experiments detects later source changes as it
should; old timings must be reproduced using the original archived sources.
The guard is inactive at the reviewed production tolerance; no new timing
factor is claimed from the amended implementation without a matched remeasurement.

The separately authorized [SC-050 strategy experiment](../../../../results/validation/shape_continuation/SC-050-localization-robustness/plan.md)
addresses reconstruction failure and transfer, rather than asserting that an
execution speedup itself fixes nonconvex inversion.
