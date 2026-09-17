# SPD-008 — exact geometry acceleration

2026-09-17. **Approval status: APPROVED** by the user's explicit “yes” to
SPD-008 implementation and validation. **Execution status: COMPLETE**.
Artifacts: `results/validation/speedup/SPD-008-20260917-geometry/`.
The previous campaign has completed with verification PASS; no numerical workers
were visible before implementation. All sealed historical results are preserved.

The preparation below is the approved design. Its gates and budgets now govern
execution; wording such as “proposed” in the original design does not authorize
SPD-009, automatic default promotion, or an additional all-scene campaign.

Owner: Codex `/root`. Independent reviewer: unassigned. Existing checkout and
branch only. No new branch or worktree is part of this plan.

## Execution record

- **Final closeout:** [iteration 08](../iteration_08/01_results.md). All 16
  numerical workers recover; all eight pairs have exact trajectories, decisions,
  states, endpoints and work. Median time reductions: death 34.0%, merge 22.4%,
  central 50.5%, two stars 54.5%. Both hard-scene and easy-scene gates pass.
  Final audit PASS; all 618 prior TOP-025 artifact hashes remain intact. Total
  campaign usage including the failed launch is 7805.49/10800 s. Retain opt-in;
  no default promotion, additional all-scene run or SPD-009 execution occurred.
- **Timing qualification:** the post-run workspace audit found LAU-001 artifacts
  whose timestamps and 31.30 s recorded duration indicate numerical overlap with
  the last worker; its tests/pilot timing is unavailable. All measured sources
  and exact numerical comparisons pass. Report the observed reductions as
  shared-host measurements, not isolated timing evidence; preserve every sample.
- 2026-09-17: preserved the completed TOP-025 campaign (8/12 recoveries,
  verification PASS) and froze its 211 listed live sources before editing.
- Recorded regression selection: **142 passed, 1 unavailable-CUDA skip**.
- Geometry replay: all 19 records agree across reference/cache/certified at
  64/128/256/512 nodes in both orders (57 arm rows / 456 decisions); 13.38 s,
  zero physical solves. The saved coarse-accept/refined-refuse case is retained.
- Update qualification: **PASS**, 213.69 s and 113 work units, below 1800 s /
  2000 units. Two unprofiled repeats per arm on both hard handoffs reproduce the
  archived first update exactly; the coarse merge fit also has identical states,
  candidate decisions and stopping. A separate profile follows the timings.
- Median stencil speedup: central **3.668x**, two stars **3.586x**. Both exceed
  the predeclared 2x gate. The 16 sequential matched full workers are dispatched
  under the original 10800 s campaign / 2400 s worker ceilings. Defaults and the
  FD-compatible policy remain unchanged. Full-inverse outcomes are pending.
- The first dispatch stopped before numerical work: a progress edit to this
  live document triggered input-drift detection. `campaign_attempt_01` preserves
  the failed launch. The runner now hashes its copied approved plan; a regression
  covers live status edits versus frozen-copy tampering. Geometry/update
  qualification is repeated on the repaired driver, charging the prior 13.38 s
  geometry audit and 213.69 s / 113 update units against the original total caps.
  The failed dispatch's 0.99 s also counts against the full campaign wall cap.
- Repaired-driver validation: **144 passed, 1 unavailable-CUDA skip**. Repeated
  geometry replay passes in 13.25 s; repeated update qualification passes in
  215.55 s / 113 work units. Current-source stencil gains are **3.649x** central
  and **3.563x** two stars. Both attempts together consume 26.63 s of the 300 s
  geometry cap and 429.25 s / 226 units of the 1800 s / 2000-unit update cap.
  The current 16-worker campaign is running sequentially; complete inverse
  timings and paired quality comparisons remain pending.
- Mid-campaign record, first repetition partial: death (46.49 s reference / 30.35 s certified),
  merge (178.30 s / 135.40 s), and central ellipse/star (1071.86 s / 527.32 s)
  recover with exact paired trajectories, decisions and final states. The
  certified two-star worker recovers in 597.56 s; its reference worker is still
  running. These are individual samples, not the final two-repeat medians.

## Decision and baseline

Decide whether the current compiled + reciprocal + readiness inverse can run
materially faster while preserving its geometry decisions, FD-compatible
constraint policy, numerical settings and reconstruction quality.

The sealed SPD-006 central update spent 23.864 s in 136 `allowed` calls out of
26.957 s total. Its nested breakdown includes 10.386 s in adapter sampled
self-intersection, 8.476 s in pair clearance, and 4.401 s in parameterization
validation. These times overlap other profile entries; do not add all rows or
turn this update into a whole-inverse percentage. The current TOP-025 campaign
is a broader correctness/coverage reference once completed, not an isolated
timing control for later sequential workers.

Relevant sources, all under `/home/drdeng/Neural_SDF_BEM_AD`:

| File / seam | Smallest intended change |
|---|---|
| `solvers/sdf_inverse/radial_topology.py`, `run_multiradial_fd_inverse` | Establish an opt-in context for one fit; count geometry requests/cache results; retain retraction, radius floor, all production/refined checks and existing `allowed` policy. |
| `solvers/sdf_inverse/explicit_fourier.py`, `CartesianFourierCurveState.boundary_curve` | Reuse the identical component's validation report; run the resolution/undersampling guard on every request and discretize at the requested grid. |
| `solvers/ordered_boundary/validation.py`, `_self_intersection_count` | Cache expensive pure sampled-audit results by exact point data and the two resolved tolerance arguments, within the fit context only. Keep the existing calculation on a miss. |
| `solvers/gpr_bem_kress/geometry.py`, `PeriodicCurveAdapter.__post_init__` | Preserve construction and caller ownership; benefit from cached sampled validation without returning another curve's adapter. |
| `solvers/gpr_bem_kress/multicomponent.py` | Add a boolean admissibility path with a conservative pair-separation certificate and the existing exact fallback. Preserve the detailed adapter/reporting path. |
| `solvers/sdf_inverse/work_accounting.py` or experiment diagnostics | Report geometry work separately; a cache hit consumes no physical system or Jacobian work unit. |
| Future `experiments/spd008_geometry/` and focused tests | A small comparison driver and qualification evidence, using current runner conventions; no duplicate optimizer or solver. |

A small validation-cache context may live in the ordered-boundary layer so the
lower-level solver never imports the inverse package. An explicit context
manager patterned on the current runtime/execution contexts is preferable to
a process-global LRU: opt-in, fit-local, exception-safe teardown, isolated for
nested contexts, and no accidental worker/thread sharing. Review the exact
dependency boundary before adding a module. No implementation was written here.

## Cache contracts

**Component report.** Key exact Cartesian coefficient arrays (including shape,
dtype and signed-zero bits), chart/bandwidth, period/origin if exposed, component
identity/report metadata, bounds, and the fully resolved validation settings.
The resolved settings include derivative sample count as well as the nominal
validation resolution: Fourier bandwidth can increase derivative sampling.
Exclude requested solver node count only from this report layer, because it
does not determine these validation samples. The separate undersampling and
requested-grid checks still run. Retain failures and the public exception
hierarchy; do not retain traceback-bearing exception objects in a cache.

**Sampled self-intersection.** Key exact ordered points, shape/dtype, and both
resolved cross-product and length tolerances. Orientation/ordering matter.
The generic sampled adapter uses a bounding-box scale; parameterization
validation can also use perimeter in its scale. Therefore identical coefficients
or even identical point arrays alone are insufficient to share results between
these two paths. Cache the integer count, including nonzero counts; constructors
must still raise exactly as before. Keep cheap canonical-grid, speed and
arc-length-weight checks on every adapter construction.

**Prepared sampled curve (optional, only if needed after the above).** The
cache key includes the component and exact discretization contract. Returning
the same immutable sampled object from a private preparation step is possible,
but generic `adapt_periodic_curve(new_curve)` must preserve `adapter.curve is
new_curve`. Do not change this public identity contract to obtain a cache hit.
Do not use the displayed truncated geometry ID as a complete content key.

**Pairs and full-state booleans.** If a pair-result cache is worthwhile, include
both sampled geometries, their ordering/IDs, arc weights and all assembly
clearance settings. A state boolean also depends on all required grids and
feature-radius policy; do not conflate it with a component validation result.
Start without broad state caching until narrower hit rates justify it.

Use bounded entry/byte limits, record evictions and peak memory, and clear the
context at fit exit. Initial candidate cap: 16 MiB total retained key/value
payload, measured and adjustable only as an explicit experiment configuration.
No approximate coefficient rounding, nearby-shape certificates, or reuse across
topology changes is proposed. Key after actual retraction: the re-gauge touches
every component even when the parameter direction is block-local.

Independent endpoint scoring runs outside the optimization cache context.
Refined checks during fitting remain required at their own node counts; reuse
of exact values does not turn them into production-grid checks. Shared-interface
changes must be visible to the topology and Boundary–BIE tracks at integration.

## Boolean pair certificate

Retain valid-component, unique-ID and assembly-config checks before certification.
For each pair compute the original required clearance:

`required = max(minimum_absolute_clearance, minimum_clearance_in_weights * max(max(w1), max(w2)))`.

A sufficient initial certificate is separation along a coordinate axis, using
the actual sampled polygons' enclosing boxes. Every segment is contained in its
box; a positive axis gap is a lower bound on all segment distances and excludes
nesting. If a conservatively rounded lower bound exceeds the original required
clearance and the existing intersection tolerance's safety allowance, the pair
can be accepted without an all-pairs distance matrix. Use tolerance-expanded,
outward-rounded boxes and strict comparisons; return "uncertain" around any
threshold, nonfinite intermediate, or unsupported numerical scale. Keep the
original predicate as the fallback. The floating-point allowance needs an
explicit justification against the reference operations before promotion;
random tests alone do not prove equivalence.

An axis certificate is deliberately sufficient rather than necessary. A
diagonal Euclidean-box certificate can be added only if useful after hit-rate
measurement; overlap of boxes is never evidence that the polygons overlap.
Overlapping/nested/touching/near-clearance cases use the old exact path.

The certificate returns a boolean with a separate diagnostic lower bound. It
does not construct a `ComponentPairReport`, replace its measured `clearance`,
or silently skip solver reporting, source/receiver containment, or acquisition
clearance. Initially change only boolean admissibility; the forward solver's
detailed reports remain computed by the existing reporting path.

## Staged validation after the current campaign

1. Confirm the campaign and its source-sensitive verification are complete and
   that there is no other numerical worker measuring this checkout. Retain its
   results, failures and original inputs. Capture a new baseline/source manifest.
2. Implement opt-in exact caches with focused tests first; compare cache off/on
   using the same reference algorithms. Then add the pair certificate as a
   separately selectable ablation. Defaults remain unchanged during qualification.
3. Geometry-only replay: the 19 prepared records, 64/128/256/512 nodes as
   applicable, original configuration and deliberately binding synthetic cases
   from the validation matrix. Unsupported grids must retain the same refusal.
   Zero physical solves; proposed hard wall cap 300 s. Stop on the first decision
   mismatch, cache-ownership violation, or invalidation failure.
4. Full-update replay: compiled central and two-star stage-one states plus a
   coarse topology fit. Compare baseline, cache-only, and cache+certificate;
   retain the original gauge/steps/constraints. Record requests, unique keys,
   cache hits/misses, certificate/fallback counts and per-layer time. Profile
   separately from unprofiled repeats. Proposed cap: 2,000 existing work units
   and 1,800 s total, pre-reserve work batches, stop on mismatch or cap.
5. Release a matched full campaign only if quality is preserved and stencil
   validation is at least 2x faster on both hard-state replays. This is a proposed
   operational gate, not an observed result or promised full-inverse saving.
   Use death, merge, central ellipse/star and two stars; baseline versus complete
   candidate, two repeats, alternating/reversed order, one worker at a time and
   one BLAS thread. Same observations, original starts, readiness, frequency
   schedule, physical/numerical tolerances and all inner work ceilings.
   Proposed outer cap: 10,800 s total, 2,400 s per worker; keep current per-worker
   solver caps and report timeouts as incomplete rather than extending them.
6. Report medians and both paired samples, topology events, accepted states and
   counts, stop reasons, final geometry and independent field gates. Exact reuse
   should preserve numerical arrays and decisions; unexpected drift is an
   investigation, not grounds to relax a gate. If a baseline hits a wall limit,
   distinguish saved time at the same work from extra progress enabled by that
   time; do not label different trajectories identical.
7. A proposed useful full-run target is at least 20% median reduction on each
   hard scene with all original gates intact and no material easy-scene
   regression. If it fails, record the smaller result and remaining profile;
   do not automatically promote or start more runs. All-scene qualification
   and default promotion require their own recorded scope after these results.

Each future run receives a fresh output directory under
`results/validation/speedup/`, source/input hashes, exact commands, work ledger,
machine load/thread metadata, and archived rejected/failed arms. Existing SPD-006
and current TOP-025 measurements are not overwritten or multiplied into a new
claimed speedup.

## Separate SPD-009 policy study

`analytic_constraint_policy="true"` already exists. Compare it with
`fd_compatible` under the same geometry implementation in both arms, starting
with actual geometric binding constraints and existing one-sided/unresolved
fixtures. Preserve radius floor, gauge retraction, production/refined checks,
source/receiver admissibility, endpoint validation and stopping interpretation.
The current policy unit test mocks the physical objective and Jacobian; it
establishes dispatch behavior, not full-inverse robustness.

The archived 616 Jacobian records have no one-sided/unresolved columns but 20
candidate radius-floor refusals. Retain these real rejected candidates in the
later replay. Their logs contain hashes/reasons; reconstruct a candidate only
from the matching saved base/step/retraction contract and verify its hash, never
infer coordinates from the refusal hash itself.

Changing the policy also changes conservative Jacobian batch reservations
(`1 + directions * 2` versus `1 + directions`). Record this exposure effect
separately from removed geometry time under the same hard work caps. An improved
endpoint caused by more permitted iterations is meaningful, but is not solely
a faster evaluation of identical work. No SPD-009 implementation/default change
or numerical dispatch is included in this preparation.
