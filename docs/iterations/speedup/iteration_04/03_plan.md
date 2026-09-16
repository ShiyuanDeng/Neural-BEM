# SPD-005 — Reciprocal Kress integration and matched full inverse

Approval: **APPROVED**. Execution: **COMPLETE**. Outcome: **PASS**, 2026-09-16.
The user's “then go” authorizes the sequence in the
[priority review](02_reciprocal_derivative_priority_review.md). This direct
instruction supplies execution authorization without requiring another named-ID
confirmation. Work stays on the existing branch; no commit/push is requested.

Integrate an opt-in `reciprocal` inverse runtime using the existing Kress forward,
Cartesian gauge directions, normalization, constrained-direction policy,
topology controller and cumulative frequency schedule. Preserve `fast` as the
operator-derivative comparison and `reference` as FD. No default promotion until
evidence supports its numerical scope. Materials outside the qualified reciprocal
domain retain the existing derivative path and forward restrictions.

Qualify saved pre/post-event states and difficult handoffs at 64/128 and 256/512
nodes, all four training frequencies. Use operator comparisons and independent
directional finite differences. Initial release gates: relative Jacobian and
worst-column errors <=1e-4 against the same-grid operator, selected refined
directions <=1e-4, directional FD <=2e-4. Retain failed coarse-grid results and
restrict the integration if needed; do not loosen thresholds after seeing data.
Check complex source strengths, weighted residuals, coupled geometry and work
accounting in permanent tests. Bound qualification to 1200 seconds.

Then run death, split and merge from the original starts with the original
observations: operator `fast`, reciprocal alone, reciprocal plus SPD-004
readiness. Two repetitions per arm/scene, sequential single-thread workers,
balanced arm order; maximum 18 workers, 1200 seconds each, 7200 seconds total.
Existing inner solve/stage/time ceilings remain. Reserve the same conservative
Jacobian batch bounds; separately charge reciprocal RHS batches, never label
contractions as full systems or derivative assemblies. Reuse the existing
training-only readiness gate without changing its thresholds.

Freeze actual numerical sources and inputs before the campaign. Require all
original recovery, numerical, topology and geometry gates; compare final
coefficients, boundaries, event sequences and optimizer effort. Speed ratios
are full worker wall times including endpoint verification, excluding previously
qualified truth-data generation. Record profiling and explicit primal/reciprocal
RHS work. Host-wide isolation is unverified; no speedup factor multiplication.
Stop and retain failures on numerical, recovery or provenance regression.

Close out in iteration 05 with results, scope of usable integration and the new
bottleneck profile. GPU work and new topology/data policies are follow-ups,
not part of this comparison.

## Qualification amendment before full dispatch

The unrestricted raw derivative diagnostic completed in 370.90 s. 57/58
checks passed. The 64-node pre-split fixture misses the original same-grid
worst-column gate (`1.2333e-4 > 1e-4`); at 128 nodes the discrepancy is
`2.5289e-7`. Preserve that failed raw diagnostic under
`SPD-005-20260916-qualification-01` with source and artifact manifests.

Implement the allowed scope restriction: the opt-in runtime uses reciprocal
derivatives only when every component has at least 128 nodes, otherwise the
unchanged operator derivative. An explicit raw `method="reciprocal"` remains
available for diagnostics; it is not the production runtime selection. The
matched campaign therefore preserves the 64-node topology derivative in all
arms and tests reciprocal continuation at 256 nodes.

Requalify the guarded runtime on current sources against the sealed operator
arrays, with exact operator equality on 64-node grids, the original thresholds
on 128/256/512 grids, per-frequency checks, and fresh independent FD. Reuse the
expensive operator references only after checking their full artifact manifest
and unchanged forward/operator sources; reviewed source changes are the
automatic guard, runtime metadata and guard tests. Keep both qualification
phases within the original combined 1200-second ceiling. This narrows the
usable domain; it does not relax any accuracy threshold. No full worker is
released until this guarded qualification passes.

Guarded qualification **PASS**, 58/58 checks, 66.42 s; both qualification
phases total 437.32 s. Worst per-frequency error is `2.994e-7`; worst fresh FD
error is `2.232e-9`. 93 regression tests pass, one unavailable-CUDA test skips.
The frozen campaign has been dispatched under
`results/validation/speedup/SPD-005-20260916-full-inverse` with two repetitions
of each of three arms on death/split/merge. Numerical source edits pause until
the campaign ends. The artifact's approved plan is the pre-dispatch snapshot.

The kernel counters leave part of the full runtime unattributed. To complete
the planned remaining-cost profile, follow the timed campaign with one CPU
profile of the existing death continuation stage 1 (training only, 256/512
nodes, reciprocal runtime, same optimizer and handoff). Cap this diagnostic at
400 work units and 120 seconds. Run it only after the timed workers, retain its
own source/input record, and report profiler call-stack costs separately from
matched wall-clock ratios. This is a local cost diagnostic, not another full
inverse repetition or a changed algorithm.

## Closeout

All 18 full workers recovered in 3103.91 campaign seconds, with all source,
input and work-accounting checks passing. Median reciprocal gains against the
operator control are 1.77x/1.81x/2.38x on death/split/merge; combined gains are
5.10x/6.64x/2.33x. The post-campaign stage profile completed in 12.51 s using
three work units; legacy stencil-feasibility checks consumed 94.6% of its
profiled stage time. See [iteration 05 results](../iteration_05/01_results.md)
for the measured integration scope, full evidence and next priority.
