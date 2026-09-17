# SPD-008 implementation review

2026-09-17. Owner self-review; no independent review is claimed.

**Accept:** cache pure component reports and sampled intersection counts, with
full content keys and effective tolerance/settings keys. Invalid reports/counts
are reusable; exception objects are not retained. The cache is opt-in and is
replaced at each fixed-topology fit, then cleared even when a fit raises.
No solver arrays, local Kress maps or approximate coefficients are cached here.

**Accept with a narrower implementation:** the adapter's expensive sampled
audit is cached, while a fresh adapter retains the caller's exact curve object.
Canonical-grid, derivative/weight and speed checks still run. This avoids the
public identity-contract violation of returning an equal but differently owned
adapter. Bounds checks and undersampling guards also run on every request.

**Accept with conservative fallback:** pair certification is limited to boolean
admissibility. An axis box gap bounds all segment distances; it excludes real
intersections and nesting. The implementation additionally requires union-box
diameter at most three times the larger component diameter and normal, bounded
edge/coordinate scales. These restrictions leave room below the reference
orientation tolerance for the cross-product roundoff bound. Outward-rounded,
tolerance-expanded boxes and a 4096-epsilon coordinate-scale margin protect
touching, point-to-segment projection/distance and ray-crossing comparisons.
Uncertain cases call the unchanged exact pair validator. The original detailed
adapter still produces all exact `ComponentPairReport` distances, and acquisition
checks remain independent. The certificate is not a report or a distance cache.

**Defer:** full sampled-curve/adapter caching and pair-result caching. The first
implementation already removes repeated expensive audits, preserving ownership
without a new prepared-boundary interface. Measure its incremental benefit
before broadening the cache surface.

**Defer to SPD-009:** true-analytic constrained-direction policy. Both current
arms retain FD-compatible stencils, radius-floor checks, gauge retraction,
refined candidate checks and the same conservative Jacobian reservations.

**Qualification coverage:** focused tests cover cross-resolution report reuse,
one-float coefficient changes, changed bounds/validation settings, intersection
tolerances/order, invalid reports, adapter ownership, warmed malformed weights
and grids, bounded eviction/cleanup/nested scopes, strict clearance thresholds,
nesting, changed assembly settings, diagonal overlapping boxes, unsupported
separation scales, poses/scales/gaps and the saved TOP-006 refined-grid failure.
Existing ordered-boundary, Kress, refined feasibility, feasible-FD, Cartesian,
SPD-001/006/007 and TOP-025 integration tests remain in the regression selection.

The repaired runner's recorded regression run passes 144 tests with one
unavailable-CUDA skip (142 before the two harness regressions were added).
An earlier unrecorded development invocation omitted `PYTHONPATH=solvers` and
failed the existing fresh-process import test; the recorded driver supplies it
to both pytest and worker subprocesses. One initial new undersampling fixture
requested six nodes, which the configuration rejects before the intended chart
guard; it was corrected to eight nodes with a mode-four curve. Neither was a
numerical mismatch or a relaxed geometry gate.

The first full launch stopped before any numerical work because a live plan
status edit tripped input freezing. The failed launch is retained. The runner
now verifies the archived plan copy; a regression ensures that live status
edits are permitted and altered archived content is refused. A second regression
checks that preserved diagnostic attempts reduce the remaining original budget.
Qualification repeated successfully with the repaired runner before the new
full launch: 13.25 s for geometry, 215.55 s / 113 work units for updates, and
3.649x / 3.563x hard-scene stencil gains. Both diagnostic attempts and the failed
dispatch remain charged against the original total budgets.

The saved-state, exact-update and full-inverse gates own the numerical and speed
claims. Passing these unit tests alone does not authorize a default promotion or
establish a whole-inverse speed factor. The recorded full-campaign target also
makes “no material easy-scene regression” explicit as no more than 5% median
slowdown; two repeats remain limited evidence, and both samples are retained.

**Closeout:** all 16 full workers recover, all eight pairs match exactly,
including endpoint predictions and detailed work, and both performance gates
pass. Median hard-scene time reductions are 50.5% and 54.5%; easy reductions
are 34.0% and 22.4%. Cache payload estimates stay within 16 MiB, with eviction
observed. The file-only audit also preserves all 618 prior TOP-025 artifact
hashes. This closes the approved experiment as qualified opt-in; it does not
promote defaults or authorize another campaign.

**Post-run timing qualification:** the workspace gained another task's staged
Laurent files during SPD-008. Its campaign artifacts and recorded 31.30 s runtime
indicate overlap with the final two-star worker; its tests/pilot may also have
overlapped. All 240 measured source hashes remain unchanged. Numerical quality
is qualified, while the wall times are shared-host observations rather than an
isolated benchmark. Evidence is copied into the result bundle; the other task
was untouched. No samples were dropped and no extra numerical runs dispatched.
