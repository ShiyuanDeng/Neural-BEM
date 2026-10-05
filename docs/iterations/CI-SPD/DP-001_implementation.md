# DP-001 implementation and qualification

2026-10-05. Implemented priorities 1 and 2 of the
[inverse pipeline audit](INVERSE_PIPELINE_AUDIT.md). The
[plan](DP-001_plan.md) was sealed before any inverse run; the user subsequently
replied **“Approve DP-001”**, recorded in the separate approval receipt.

Changes live in `solvers/bem_inverse`: opt-in agreement damping, scaled
curvature floor, deadline/proposal guards, exact duplicate detection,
shortened-progress stop, failure provenance and optional terminal tangent
omission. Immutable base-grid and assembly-index reuse and incremental wave
expansions preserve the existing numerical decisions. Bounded audit batches
are selectable, with the serial default retained. Timings distinguish audit
phases, GPU lock/prior-work wait, CUDA-event span, synchronized host span and
host transfer. Failed phase timers now survive exceptions.

No numerical safeguard was removed. Adaptive resolution/refinement and rigid
translation coordinates remain deferred qualifications. Defaults retain
the legacy schedule and one-frequency audit execution.

Validation in the EMNerf environment with single-thread BLAS:

- Maintained package and cleaned-interface suite: **256 passed**, 139.61 s.
- Shared continuation, Kress and ordered-boundary suites: **348 passed**,
  27.18 s (15 existing warnings).
- DP-001 screen/approval guards plus modal CPU/CUDA comparisons after the GPU
  event instrumentation: **21 passed**, 59.38 s. The 18 modal tests overlap
  the maintained suite; the three driver guards are additional.
- Preparation verifies the existing TG-002 seal; frozen baseline and current
  candidate imports resolve to the intended, distinct solver roots. No fit
  was performed during preparation.
- `git diff --check` passed.

The working branch is the existing `feature/shape-frequency-continuation`,
where the maintained package and current campaigns are present. No Git
branch or worktree was created. Frozen baseline sources are extracted to an
ordinary `/tmp` directory from their archived commit. Source archives and
preparation seals remain in the DP-001 evidence directory.

These bounded checks qualify the implementation and driver; recovery and
speed conclusions must come from the approved paired experiment.
