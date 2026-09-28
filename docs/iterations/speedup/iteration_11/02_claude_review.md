# Claude review of SPD-014 (exact sampled-geometry acceleration)

2026-09-28. Reviewer: Claude Code, requested by the user ("check codex implementation of speedups", then "document your diagnostics"). This is an independent review of Codex's uncommitted SPD-014 working tree: `spatial_validation.py`, the `validation.py` / `validation_cache.py` changes, `experiments/spd014_geometry`, `test_spd014.py` and the evidence bundle. The review did not modify any Codex file. Diagnostic scripts and outputs are in [`results/validation/speedup/SPD-014-review-20260928/`](../../../../results/validation/speedup/SPD-014-review-20260928/README.md).

## Verdict

- **The implementation and evidence hold for the qualified use:** the default relative tolerance of 1e-12, on the six development scenes.
- **One latent correctness defect (R1):** the claim of exact count agreement fails when the crossing tolerance is below cross-product round-off. At `relative_tolerance=0`, the dense reference counts distant collinear segments as "proper" crossings through round-off signs; the spatial path prunes them.
  - No current caller is affected, because all use 1e-12.
  - A one-line guard restores exactness. It was checked on 783 comparisons and never fires at the production tolerance, so the SPD-014 measurements stay valid.
- **Two scope notes (R2, R3)** and one provenance note (R4). I accept Codex's timing-scope correction of my SPD-010–013 summaries (R5).

## What was checked, and passed

| Check | Result |
|---|---|
| Predicate identity | Spatial and dense evaluate the same `o1–o4` expressions and padded-box touch tests with identical floating-point operations; candidate pairs get bit-identical verdicts |
| Adjacency | `gap > 1 and gap < n−1` on `query_pairs` output (`i < j`) equals the dense upper-triangle non-adjacent mask |
| Broad-phase completeness | For true crossings, midpoint distance ≤ (L_i + L_j)/2 ≤ L_max. For tolerated touches, an extra ≤ √2·length_tolerance. The pad also covers midpoint and distance round-off. Sound, given the premise in R1 |
| Memory bound and fallbacks | `count_neighbors` runs before `query_pairs`, with a budget of min(262144, max(4096, 16n)). Non-finite radius, SciPy `ValueError` and non-finite or negative tolerances fall back to the dense checker |
| Cache and context | The backend is in the exact cache key, so A/B arms cannot hit each other's entries. The `ContextVar` backend reaches frequency threads through SPD-010's `copy_context` |
| Frozen provenance | `experiments.spd014_geometry.run.verify(bundle)` passes on the current tree: plan, source archive, sources and 559 inputs are unchanged |
| Tests | 370 pass (`pytest/ordered_boundary`, `experiments/spd014_geometry`, `experiments/shape_continuation`, `pytest/gpr_bem_kress`, `pytest/shape_continuation`, `pytest/sdf_inverse/test_spd008.py`) |
| Headline numbers, recomputed from raw bundle files | Geometry screen: 209.2× median, 36/36 counts equal. Batches: 132.61 → 52.08 s (60.7%), 96/96 identical. Inverse: 302.82 → 281.38 s (7.1%), 6/6 comparisons pass, equal units. Video: 638.61 → 296.05 s (53.6%), 6/6 pass. All match the closeout |

## Findings

### R1: exactness fails below the round-off tolerance (latent; fix recommended)

- **Observed.** The independent fuzz ([fuzz.py](../../../../results/validation/speedup/SPD-014-review-20260928/fuzz.py)) covers 261 polygons × 3 relative tolerances (0, 1e-12, 1e-6). The polygons are star polygons with subdivided straight edges, lemniscates, pinched curves, tolerance-boundary touches and random walks, at offsets up to 3e8. It found 2 mismatches, both at relative tolerance 0:
  - 5/2 star polygon, 200 nodes: reference 7, spatial 5.
  - 9/4 star polygon, 360 nodes: reference 28, spatial 27.
- **Cause.** The pairs counted only by the dense reference, for example segments (42, 70) and (42, 71) of the 5/2 star, are collinear pieces of the same straight star edge.
  - Their midpoints are 1.33–1.38 apart, against segment length 0.048.
  - Their orientations are pure round-off (±3.5e-18). With `cross_tolerance = 0` the signs alternate, so the dense "proper crossing" test fires for segments that do not intersect.
  - The spatial path excludes them correctly, so its count is geometrically right but differs from the reference.
  - The docstring's completeness argument assumes that a computed proper crossing implies a true one. That holds only when `cross_tolerance` exceeds cross-product round-off.
- **Bound.** `fl(cross(b−a, c−a))` has absolute error ≤ about 4u·|b−a|·|c−a| ≤ 2·eps·L_max·D, where D is the bounding-box diagonal. Differences of stored points are rounded relative to their own size, so translation does not enlarge the error. With the default relative tolerance of 1e-12, `cross_tolerance = 1e-12·D²` exceeds this bound by at least about 500×, because L_max ≤ D.
- **Reach.** Every current caller uses 1e-12: `gpr_bem_kress.geometry`, `sdf_inverse`, and `validate_periodic_parameterization`, whose default `intersection_relative_tolerance` is 1e-12. The SPD-014 evidence is unaffected. The public API still accepts `relative_tolerance=0.0`, and resolved tolerances can be passed directly.
- **Fix.** In `spatial_self_intersection_count`, use the dense fallback unless `cross_tolerance ≥ 8·eps·L_max·D` (a 4× margin over the bound):
  - [guard_check.py](../../../../results/validation/speedup/SPD-014-review-20260928/guard_check.py) applies this rule to all 783 fuzz comparisons: **all equal**.
  - The guard fired only on the 261 zero-tolerance cases, never at 1e-12 or 1e-6, so production timings are unchanged.
  - Also state the premise in the docstring, and add the subdivided-star, zero-tolerance case to `test_spd014.py`. The fixture set has no distant collinear segments, which is why the tests missed this.
  - The fix changes a frozen source hash, so record it as a post-qualification amendment.

### R2: saved-shape evidence covers only the "no crossing" outcome (scope)

- All 36 saved geometries in the geometry screen have **zero** intersections, and none took the dense fallback.
- On real shapes, exact equality is therefore demonstrated only when the answer is 0. Crossing and touching equality rests on the synthetic unit tests. This review's fuzz adds 212 non-zero-count comparisons on the pruned path at non-zero tolerance, all equal.
- Please add this limit to the SPD-014 README.

### R3: the video gain is reachable only through the experiment wrapper (usability)

- The 2.16× video saving needs `cache_diagnostic` around the renderer's `diagnostic`, plus `geometry_acceleration('both')`.
- The committed `latest_vs_hybrid/render.py` and normal inverse commands get none of SPD-014 unless callers enter these contexts.
- This matches "qualified opt-in". The closeout should say plainly that default runs are unchanged, and give the one-line invocation if the user wants the gain.

### R4: provenance (no action beyond committing)

The SPD-014 code and evidence are uncommitted, and the runs recorded a dirty tree. This is mitigated by the frozen source tarball and hashes, which verify now. Commit before applying R1, so the amendment is a visible diff.

### R5: timing-scope correction (accepted)

Codex's handoff note is right. SPD-010–013's SC-043 "inverse" replays start from saved intermediate shapes: they are continuation suffixes, not full circle-start reconstructions. My summaries said, for example, "kite inverse 36 → 2.6 min"; that measures the suffix only. The SPD-010–013 numbers stand as matched suffix measurements.

## Suggested resolution order

1. Commit the current SPD-014 files unchanged.
2. Apply R1: guard, docstring premise and regression test. Re-run `test_spd014.py` and this review's `fuzz.py`.
3. Add the R2 and R3 wording.
