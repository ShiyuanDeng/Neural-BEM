# SPD-014: exact sampled-geometry acceleration

2026-09-27. **Approval status: APPROVED.** The user replied "you have my
approval" to Codex's investigation and bounded follow-up: qualify the existing
spatial-pruning mechanism for Kress, extend diagnostic-batch cache scope,
measure each separately, and retain identical geometry/reconstruction decisions.
**Execution status: COMPLETE / PASS; qualified opt-in.**
All four stages passed; see the [closeout](../iteration_11/01_results.md).
The original approved contract is preserved in the artifact bundle.

Owner: Codex. Independent reviewer: unassigned. No branch or Git worktree is
created. The existing checkout is currently on
`feature/shape-frequency-continuation`. SPD-012/013 completed at clean commit `e3bc5e5d`; no numerical workers were
running when this implementation was integrated. Staged preparation did not
modify their checkout or compete with their measurements.

## Question and controls

Can exact spatial pruning and diagnostic-batch reuse reduce CUDA-path geometry
cost with unchanged samples, tolerances, intersection counts, physical systems,
Jacobians, accepted states, work units and video frontiers?

The baseline is the completed SPD-012/013 source, pinned before this experiment's
runs, with an explicit CUDA backend and fixed frequency/BLAS thread settings.
SPD-011's saved six-case results are historical correctness evidence, not the
matched timing control. Use fresh output folders and retain unsuccessful arms.

## Implementation map

- `solvers/ordered_boundary/spatial_validation.py`: a SciPy KD-tree broad phase,
  followed by the original orientation/touching predicate. Count candidates
  before materializing them; use the original chunked dense algorithm for
  pathological candidate density or numerically unsuitable tree inputs.
- `ordered_boundary.validation`: retain the dense implementation and select the
  opt-in spatial version for self-intersection counts only. Public input errors,
  pair clearance, sampling, tolerances and component ownership stay unchanged.
- `ordered_boundary.validation_cache`: context-local backend selection, copied
  to frequency threads; include the backend in exact cache keys so A/B calls
  cannot mask one another. The ordinary backend remains `reference`.
- `experiments/spd014_geometry`: small runtime wrappers and a qualification/
  replay driver. Use an explicit active `validation_cache('cache')` around
  direct audits and complete renderer diagnostic batches. Reuse an existing
  active cache without overriding its policy. Never keep fit validation in an
  endpoint audit's independent scope.
- Keep historical SC-042/043 drivers and `latest_vs_hybrid/render.py` byte-for-
  byte intact: load them in a fresh replay harness and wrap their audit/diagnostic
  callables. Record exact wrapper and upstream hashes.

## Stages and gates

1. **Geometry qualification** (900 seconds): existing boundary/SPD-008 tests;
   new crossing, touching, collinear, duplicate, zero-length, translated,
   scaled, nonuniform, tolerance and candidate-density/fallback tests; exact
   counts on all six SC-043 start/end geometries at 256/512/1024/2048 nodes where
   the storage band permits. Include mode restoration, backend-distinct keys,
   invalid-count reuse, threads and independent batch lifetimes. Any count or
   refusal regression stops the numerical comparison.
2. **Four-arm diagnostic measurement** (1200 seconds, at most 30000 forward/
   reciprocal units): reference, cache only, spatial only, both. All six saved
   endpoints, production/refined grids, all 19 frequencies, two sequential
   repeats with reversed arm order. Compare prediction/Jacobian/heat/frontier
   outputs exactly. Instrument executed geometry computations separately from
   physical units and report nested timer limits. Record candidate densities in
   the geometry screen. Require at least 2x faster median uncached checks at
   N>=512 and at least 20% lower combined diagnostic time to proceed.
3. **Matched complete replay** (3600 seconds, at most 25000 forward/reciprocal
   units): six SC-043 fixed cases, one fresh reference and combined worker per
   case, sequential; compare every non-timing recorded value exactly. Independent
   endpoint audits must pass. If a CUDA run has unrelated roundoff variation,
   retain and report it; do not weaken the exact execution-change gate.
4. **Video preparation** (3600 seconds, at most 12000 forward/reciprocal units):
   all six saved tracks through the unchanged renderer, fresh reference and
   combined outputs, sequential cases. Require identical diagnostic fields,
   geometry/RMS and frontiers, original renderer assertions, and unchanged work.
   No videos need re-encoding because displayed results must be identical.

The caps are ceilings, not targets. Reserve a bounded batch before dispatch;
stop on time/work exhaustion and label partial evidence. No overlapping
numerical campaigns. Declare hardware, host load and threading for all timing
claims; sums of worker times are not concurrent makespan.

## Decision

Qualify the new path as opt-in if the quality gates pass and the diagnostic
saving exceeds 20%, reporting the actual complete-inverse/video gains. Retain
reference execution and bound spatial candidate memory. No CUDA/default,
optimizer, pair-clearance policy or generalization claims are added. A failed
gate leaves the candidate unqualified; no automatic retuning or successor.

Artifacts: `results/validation/speedup/SPD-014-20260927-geometry/`, including
source/input manifests, commands/environment, geometry and four-arm reports,
complete replay comparisons, video comparisons and README. Results open the
next available speedup cycle without rewriting SPD-012/013's history.
