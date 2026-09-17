# SPD-008 — exact geometry acceleration halves hard-scene runtime

2026-09-17. **Approval status: APPROVED. Execution status: COMPLETE.**
The user approved the [iteration-07 plan](../iteration_07/03_plan.md); all
conditional gates passed. Owner: Codex `/root`. Review: owner self-review;
independent reviewer unassigned.

**Decision: retain the qualified opt-in.** All 16 full workers recover, with
exact agreement across all eight reference/candidate pairs. Both hard scenes
exceed the 20% median saving target, and both easy scenes improve. The default
remains compiled scattering with reciprocal derivatives and readiness. The
FD-compatible constraint policy is unchanged.

## Complete inverse result

Four noiseless scenes, two repeats per arm, one sequential CPU worker and one
BLAS thread, with alternating/reversed order. Each worker begins from its
original start and includes topology, continuation and independent endpoints.

| Scene | Reference geometry | Exact cache + certificate | Median time reduction |
|---|---:|---:|---:|
| Death | 46.32 s | 30.56 s | 34.0% |
| Merge | 2m56s | 2m17s | 22.4% |
| Central ellipse/star | 17m50s | 8m50s | 50.5% |
| Two stars | 21m55s | 9m58s | 54.5% |

[The result bundle](../../../../results/validation/speedup/SPD-008-20260917-geometry/README.md)
contains both samples, full-precision medians, commands, work counts and machine
load. **Shared-host timing caveat:** the final workspace audit found a separate
LAU-001 screen whose artifact timestamps and recorded 31.30 s duration indicate
overlap with the last worker. Its tests/pilot may also have overlapped. All 240
measured sources remain unchanged, and exact numerical/work comparisons pass;
the wall times are observed shared-host results, not an isolated benchmark.
[The timing record](../../../../results/validation/speedup/SPD-008-20260917-geometry/timing_context.json)
preserves the evidence. This is a bounded four-scene result;
all-scene, noisy-data and GPU gains are not established.

## Quality and mechanism

The implementation reuses exact component reports and sampled self-intersection
counts within each fit. It additionally certifies clearly separated sampled
polygons for boolean admissibility, with conservative numerical guards and the
existing exact fallback. Detailed clearance reports retain measured distances;
curve ownership, bounds, requested-grid checks, refined feasibility, radius
floor, retraction and independent endpoint scoring remain intact.

Paired topology/continuation trajectories, accepted coefficients, gradients,
candidate decisions, refusal reasons, final states, endpoint predictions,
readiness decisions and detailed physical work agree exactly. The maximum
coefficient difference is zero. The cache's peak retained-memory estimate is
16,777,204 bytes, below its 16 MiB limit; long fits evict entries.

Current-source regressions pass **144 tests**, with one unavailable-CUDA skip.
The 19-record geometry replay agrees across reference/cache/certified and all
four grids in both orders (456 decisions). Real update replays match archived
accepted states and show **3.649x / 3.563x** median stencil speedups on the hard
handoffs, releasing the full campaign. A coarse merge fit also agrees exactly.

## Evidence and remaining work

[Verification](../../../../results/validation/speedup/SPD-008-20260917-geometry/verification.json)
passes current and archived source/input hashes, work reconciliation and all
618 hashes in the user's completed twelve-scene compiled campaign. That
campaign's 8/12 recovery result and failures remain preserved.

The first SPD-008 launch stopped before numerical work when a live plan progress
edit tripped input freezing. Its failed arm and diagnostic evidence remain
archived. The runner now verifies its copied plan, with regressions covering
the repair. Both diagnostic attempts and the failed dispatch count against the
original caps: geometry 26.63/300 s; updates 429.25/1800 s and 226/2000 units;
campaign 7805.49/10800 s. Every numerical worker completed within 2400 s.

The separate accelerated central update profile still spends 6.43 of 8.95 s in
stencil checks, including 5.06 s in sampled self-intersections. These nested
one-update times cannot be added or treated as whole-inverse shares. The full
central comparison directly measures a 2.02x gain, smaller than its local
stencil gain because physical work and independent scoring remain.

The next decision is whether to confirm timing under isolated conditions and
qualify default promotion over the complete scene set, or to review a further
exact geometry optimization. No successor
campaign is authorized here. SPD-009's policy change remains separate and
unexecuted. [Implementation and opt-in usage](../../../../experiments/spd008_geometry/README.md).
