# Implementation review (owner review, not independent review)

Codex reviewed the measured call paths before interpreting the comparison.
The independent reviewer remains unassigned.

## Scope of the SPD reference

This is **SPD-008 execution of the original fixed-topology continuation** from
the atlas's bad circle, not a rerun of the complete TOP-025 topology pipeline.
`spd008_comparison.spd_fit` calls `run_top017.fit_stage`, which calls the original
`run_multiradial_fd_inverse`. It explicitly selects the compiled runtime,
real-Bessel kernels and certified geometry validation. A single component uses
the full Kress/reciprocal route; the multi-component compressed path and pair
separation certificate have no opportunity here. All 240 numerical/test source
files in the original SPD-008 campaign manifest are unchanged.

Native SPD continuation retains K17, the polar-angle gauge, 33 reduced
directions, feasible-side derivative guards and the 8-mm native radius floor.
The floor concerns the radial representation, not a lower curvature radius.
The hybrid retains K192 arclength storage, the M=3/5/7/9 normal-update ladder,
its original coefficient clipping and V2 refit guard. These are different
representations and feasible sets. Equal numeric stopping thresholds in
different coordinates are not invariant notions of stationarity. Recovery is
therefore compared by independent geometric errors, not by stop labels alone.

The topology/readiness wrappers are outside the experiment. Historical full
SPD timings include a different path to the continuation handoff, so a bad
common-start outcome does not contradict their near-truth recovery records.
The comparison tests the two declared continuation methods; it cannot isolate
harmonic restriction as the sole cause of an outcome difference.

The hybrid keeps its existing reference CPU kernel route in `forward.solve`;
this experiment transfers SPD-008's exact geometry reuse, not a new kernel or
factorization implementation. SPD receives its faster real-Bessel route. The
cache-off/on hybrid pair isolates the cache effect despite these native
implementation differences between SPD and the hybrid.

## Data and geometry ownership

The optimizer observations are explicitly selected from each case's immutable
catalog at 0.5/0.75/1.0/1.25 GHz. SPD's `training_data` receives only the active
prefix. The hybrid stage receives the same prefix, uniform weights and
normalized objective. `sc.load` supplies historical solver/controller settings;
its old merge observations and geometry are not used as these fits' data/start.
Truth and the other 15 catalog frequencies enter only post-run scoring. Reading
input bytes to verify their hashes does not supply truth to either optimizer.

The input-circle bridges agree exactly on the preflight grid. The additional
[actual-start audit](actual_start_audit.json) compares saved iteration-zero
states after native initialization and the hybrid arclength refit: differences
are at roundoff (below 1e-14 m), not a different initial boundary. Both use 512/1024
production/refined nodes and the same prediction tolerances. A decreasing
candidate that leaves the refined numerical regime remains a hard stop in both
methods, not an opportunity to relax a guard or quietly increase resolution.

Both drivers call the stage fitters directly. The old SPD outer wrapper's
initial/interstage twelve-solve scorer is not included in either inversion;
in particular its checks on future/evaluation frequencies are not an early
stopping rule here. The shared start is checked in preflight, accepted candidates
are checked on active training frequencies, and the common endpoint scorer
checks all four training frequencies after fitting. This explicit scoring
placement avoids charging only SPD for historical reporting work and is another
reason not to describe SC-030 as an unchanged full TOP-025 pipeline rerun.

Geometric RMS is arclength weighted in both directions, so SPD's polar-angle
sampling does not receive the same weight as uniform-arclength sampling merely
because both arrays have the same length. Hausdorff scoring includes its
documented sampling/interpolation bound. The common field evaluator is the
package forward at 1024 nodes: it is outside fitting and selection, but shares
the hybrid's forward implementation. It is not an independent third physics
implementation. The cross-implementation start check is reported separately.
Catalog residuals outside the four training frequencies are diagnostics at
1024 nodes; this experiment does not independently refine all nineteen endpoint
frequencies. The primary geometry-error comparison does not depend on those
field scores. Endpoint training-resolution flags remain separate from the
checks made on each accepted step's active frequencies.

## Exact cache

The public hybrid intersection function validates inputs before constructing
its key. The key includes the complete ordered float point array and the
tolerance's dtype, shape and bytes. The unchanged spatial predicate computes
the value on a miss. A crossing count remains a crossing count on a hit;
exceptions are not cached. The existing shared-adapter predicate includes
resolved tolerances and complete points in a separate namespace.

Each decorated fit opens its own bounded context (16 MiB conservative storage
accounting). Exiting clears the entries and restores the previous context,
including on failure. No solver state, operator, Jacobian or approximate
geometry is reused by this change. The cache-off control also records counters.

## Measurement and reproduction

Inversion time covers the existing fit loops, including their logging and
validation. Setup and independent scoring have separate measured times;
worker wall time is also retained. Work includes frequency solves and reciprocal
batches with their native categories; equal units need not take equal time.

Each run is a fresh, single-threaded process; workers are sequential, with
rotated/reversed arm order. Environment and host load are recorded at worker
start and finish. The shared host is not reserved or CPU-pinned, and two repeats
support ranges rather than confidence intervals. Failed runs' elapsed times
are costs to failure, not times to recovery.

The report checks current sources/inputs against the frozen manifest, cache
pair trajectory digests, repeat agreement, SC-029 hybrid endpoint/work replay,
and accepted-step numerical discrepancies. It reads saved artifacts only and
does not rerun the physical inverse or select a best iterate.
