# SPD-005 — reciprocal Kress works; geometry checks are the next bottleneck

2026-09-16. **COMPLETE / PASS**, following the user-authorized
[reciprocal integration plan](../iteration_04/03_plan.md).

Reciprocal derivatives are integrated into the production Cartesian inverse as
an opt-in runtime. Across 18 fresh full workers, they give **1.77x–2.38x
additional full-inverse speedup** over the already fast operator-derivative
pipeline, with every original recovery gate preserved. Adding readiness gives
5.10x/6.64x on the easy death/split cases. The remaining-cost profile points
directly to repeated geometry validation in the legacy FD-compatible policy.

The [complete result bundle](../../../../results/validation/speedup/SPD-005-20260916-full-inverse/README.md)
owns the raw timings, quality metrics, work ledgers, source snapshots and
verification. [summary.json](../../../../results/validation/speedup/SPD-005-20260916-full-inverse/summary.json)
can be regenerated without solving the inverse again.

## Full inverse results

Medians of two complete workers per arm/scene, single-thread CPU, sequential
workers with rotated/reversed arm order. All arms start from the same original
states and use the same observations, controller, normalization, feasibility
rules and frequency schedule. The combined arm applies SPD-004's unchanged
training-only readiness gate. Timers include topology, candidate fits,
continuation and endpoint verification; archived qualified truth-data generation
is excluded.

| Scene | Operator derivative | Reciprocal runtime | Reciprocal + readiness | Reciprocal gain | Combined gain |
|---|---:|---:|---:|---:|---:|
| Death | 234.826 s | 133.028 s | 46.018 s | 1.77x | 5.10x |
| Split | 223.031 s | 123.523 s | 33.572 s | 1.81x | 6.64x |
| Merge | 409.848 s | 172.004 s | 175.925 s | 2.38x | 2.33x |

**All 18 workers recover.** All event sequences match their controls. Death and
split endpoints are exactly equal across arms. The maximum merge difference is
`1.0813e-10 m` in coefficients and `3.6749e-10 m` on the sampled boundary.
Merge's final truth-boundary Hausdorff error is about 0.0478 mm and its maximum
evaluation-frequency relative error is about 0.362%, essentially unchanged.
Operator and reciprocal arms have identical accepted-step counts: `[0,0,0,0]`
for death/split and `[16,1,2,3]` for merge. Every continuation stage reports zero
unresolved and zero one-sided columns in this campaign.

Readiness adds another 2.89x/3.68x over reciprocal alone on death/split. Under
the qualified runtime guard below, these combined runs skip the entire phase
that would use reciprocal derivatives, so their gain is the readiness gain.
Merge is correctly unready: its largest training error at the handoff is 4.1%.
It retains continuation; screening adds eight systems and about 2.3% to the
median runtime relative to reciprocal alone. Do not multiply separate speedup
factors from earlier experiments.

### Practical runtime compared with the documented full runs

For one complete reconstruction per scene, the measured medians above are:

| Scene | Current analytic default, remeasured | Reciprocal | Reciprocal + readiness |
|---|---:|---:|---:|
| Death | 3 min 55 s | 2 min 13 s | 46 s |
| Split | 3 min 43 s | 2 min 04 s | 34 s |
| Merge | 6 min 50 s | 2 min 52 s | 2 min 56 s |
| Three scenes sequentially, sum of medians | 14 min 28 s | 7 min 09 s | 4 min 16 s |

These include topology search, candidate fits, continuation and final checks,
but exclude truth-data generation and video rendering. The 51.73-minute
SPD-005 campaign ran all three arms twice on all three scenes (18 workers);
it is not the time for one pass through these scenes.

The documented [TOP-025 twelve-scene campaign](../../topology/iteration_18/01_results.md)
took **90.35 minutes with up to four single-BLAS-thread workers**, using the
historical FD/reference pipeline. Seven of twelve scenes recovered; the total
also includes failed or stopped cases. No twelve-scene campaign with the new
reciprocal runtime has been measured. Its total cannot be obtained reliably by
dividing 90.35 minutes by the three-scene gains: difficult-scene work, stopping
conditions and concurrent scheduling differ. The table is the controlled
full-inverse comparison currently available.

## Qualification and integration boundary

The unrestricted raw reciprocal diagnostic passed **57/58 checks**. Its one
failure is the 64-node pre-split state: worst-column discrepancy `1.2333e-4`
against the same-grid operator exceeds the predeclared `1e-4` gate. At 128
nodes that discrepancy falls to `2.5289e-7`. The raw failure is preserved in
[qualification 01](../../../../results/validation/speedup/SPD-005-20260916-qualification-01/qualification.json).
This is a discretization/derivative-consistency limit, not evidence that the
continuous reciprocal identity is wrong; the raw reciprocal result is actually
closer to the refined operator on that fixture.

The production runtime therefore retains operator derivatives if **any
component has fewer than 128 nodes**. Guarded qualification passed **58/58
checks**, including exact operator fallback at 64 nodes, all four training
frequencies, 128/256/512-node comparisons, saved pre/post-event states, full
256-node gauge bases on two difficult handoffs, and fresh directional FD.
Worst per-frequency discrepancy is `2.994e-7`; worst FD discrepancy is
`2.232e-9`. See [qualification 02](../../../../results/validation/speedup/SPD-005-20260916-qualification-02/qualification.json).
The two phases took 437.32 s together, within the 1200 s ceiling. The expensive
operator arrays were reused for phase two only after artifact verification and
review of the unchanged operator/forward sources.

**93 regression tests pass; one unavailable-CUDA test skips.** The guarded
runtime is selected by `--inverse-runtime reciprocal`,
`SDF_INVERSE_RUNTIME=reciprocal`, or `inverse_runtime("reciprocal")` in Python.
`fast` remains the operator-derivative default/comparison; `reference` retains
FD. Explicit low-level `method="reciprocal"` calls bypass the node guard for
diagnostics. The existing lossless, nonmagnetic, common-material forward domain
and FD-compatible constrained-direction policy remain unchanged.

The [production bridge](../../../../solvers/sdf_inverse/analytic_jacobian.py)
uses [coupled reciprocal trace contractions](../../../../solvers/gpr_bem_kress/reciprocal_shape_derivative.py)
without importing the exploratory modal solver. Unit receiver illuminations
reuse the base LU; primal traces already contain the source strengths. The
bilinear product has no conjugation. The 64-node topology fits in this campaign
retain the operator derivative; reciprocal savings occur in continuation.

## Work removed and work remaining

| Scene | Full systems, operator → reciprocal | Operator directions, operator → reciprocal | New reciprocal RHS batches | Receiver RHS columns |
|---|---:|---:|---:|---:|
| Death | 157 → 157 | 470 → 130 | 10 | 240 |
| Split | 193 → 193 | 451 → 111 | 10 | 240 |
| Merge | 308 → 308 | 1768 → 250 | 46 | 1104 |

The replaced 340/340/1518 directions become cheap contractions. Their receiver
batches use existing factors and are not counted as new matrix assemblies or
full systems. Attempted/completed/failed reciprocal work is separately budgeted;
the original conservative Jacobian batch reservations remain. All work ledgers
reconcile. The combined arm uses 89/125/316 full systems respectively.

## Big-picture finding: the inverse still behaves like an FD pipeline

A separate, post-campaign CPU profile repeated the real death continuation
stage 1 with the reciprocal runtime, unchanged optimizer and training data.
It completed one Jacobian and zero shape steps in 12.50 profiled seconds:

| Call path | Calls | Cumulative profiled time |
|---|---:|---:|
| Complete continuation stage | 1 | 12.505 s |
| Legacy stencil feasibility `allowed` | 68 | 11.830 s (**94.6%**) |
| Geometry admissibility | 137 | 11.361 s |
| Sampled self-intersection audit | 560 | 7.234 s |
| Complete reciprocal Jacobian bridge, including base solve | 1 | 0.270 s |
| Reciprocal receiver solve + contraction | 1 | 0.0094 s |

These are nested call-stack times; **do not add the rows** or treat this one
stage's percentages as a whole-campaign profile. The diagnostic used only two
physical systems plus one reciprocal batch, well within its 400-unit/120 s
caps. Its [profile and source/input record](../../../../results/validation/speedup/SPD-005-20260916-full-inverse/remaining_cost_profile/summary.json)
are separate from the matched timing samples.

**Next priority: address geometry validation and the FD-compatible policy.**
The derivative calculation is now cheap, but the optimizer still probes both
sides of 34 directions to reproduce historical FD feasibility behavior. First
audit exact reuse of immutable geometry/admissibility results across boundary
construction, Kress adaptation, frequencies and repeated states. Separately
qualify the existing true-analytic policy with real candidate feasibility and
binding-constraint cases; do not silently remove safeguards or claim its speed
before a matched experiment. This is an algorithm/pipeline decision before it
is a GPU problem. Keep readiness for adequate handoffs and earlier final-grid
feasibility on the harder-case agenda.

## Provenance and limits

Campaign wall time was **3103.91 s**, within 7200 s; all 18 sequential workers
stayed within 1200 s each and retained their inner caps. CPU: Intel Core Ultra
9 285K, one BLAS thread. Hardware/load metadata is saved; host-wide isolation is
unverified. Current numerical sources and inputs match the frozen campaign.
No independent reviewer or CUDA speedup is claimed.

This is three noiseless scenes with two repetitions per arm, not a twelve-scene
or noisy-data qualification. The roughly 19x exploratory fixed-topology fitting
result is a different scope and optimizer path. The measured full inverse gain
is the 1.77x–2.38x above. The runtime remains opt-in; no production-default,
constraint-policy, GPU, branch or worktree change was made by this closeout.
