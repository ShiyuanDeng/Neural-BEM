# SPD-015: integrate the geometry speedups into shape continuation

2026-09-28. Authorized by the user's "integrate and validate the speedups",
clarified as "Enable the geometry speedups in the current shape-continuation
pipeline". Work stays on the existing `feature/shape-frequency-continuation`
checkout. No branch/worktree creation, optimizer change or topology-default
promotion is included.

The candidate enables SPD-014's amended exact spatial intersection checks and
bounded geometry caches in native shape-continuation calls. Cache scopes cover
fits, objective batches and diagnostics; endpoint calls create fresh scopes.
Explicit cache/intersection contexts retain precedence. The reference is the
same source with `SC_GEOMETRY_RUNTIME=reference`; the candidate leaves this
variable unset. CUDA and frequency threading are identical in both arms.

The production API uses `SC_GEOMETRY_RUNTIME=reference|cache|spatial|both`, default
`both`, and a context-local override. The shared ordered-boundary default remains
reference for other callers. A native video entry point wraps the unchanged
historical renderer's complete diagnostic; historical scripts and artifacts are
not overwritten.

Validation, sequential on the shared RTX 5090 host, with four frequency threads
and one BLAS thread:

1. Targeted and broad shape-continuation, boundary, Kress and cache tests, covering
   exact CPU/CUDA fields/Jacobians, fit trajectories/work, invalid geometries,
   sub-roundoff fallback, context precedence/restoration, thread sharing and
   independent batch lifetimes. No timing workers overlap tests.
2. Repeat SPD-014's saved-geometry screen on amended sources (900 s), then the
   96 four-arm diagnostics (1200 s / 30000 forward-plus-reciprocal units).
   Require exact complete diagnostic hashes, at least 2x median uncached geometry
   speedup at N >= 512 and at least 20% combined diagnostic time reduction.
3. Six fresh paired SC-043 continuation suffixes, using native defaults without
   SPD-014 audit/forecast wrappers (3600 s / 25000 units). Compare all 54 paired
   non-timing JSON files exactly and require every independent audit to pass.
4. Six paired video preparations using the native entry point (3600 s / 12000
   units). Require every displayed field, frontier, geometry, work counter and
   renderer assertion to agree. No re-encoding is needed for identical content.

Fresh folders retain failures. Freeze source/input hashes and commands before
timing. Report measured execution counts and aggregate/per-scene wall times;
nested geometry timers are not additive. These timings cover saved SC-043
suffixes, not original-circle reconstructions. Tests cover CPU and multiple
components, but the timing campaign adds no multicomponent/noisy performance
claim. Default promotion requires passing correctness gates and diagnostic gain;
inverse/video gains are reported as measured, never inferred from old receipts.
