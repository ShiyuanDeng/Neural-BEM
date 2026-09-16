# Geometry cost after solver reduction: concrete follow-up points

2026-09-16. Source review while SPD-006's frozen workers run. **Analysis only;
no geometry, constraint-policy or numerical implementation change.** This
supplements the earlier [remaining-cost profile](../01_results.md), whose
94.6% stencil-feasibility share applies to one profiled death continuation
stage, not the whole inverse.

SPD-006's completed [compiled hard-case profile](../../iteration_06/01_results.md)
now confirms the same issue: 136 stencil checks take 23.86 seconds, or 88.5%
of one 26.96-second update. It reproduces the archived accepted state exactly.
All 16 full workers report zero one-sided/unresolved columns, making a separate
true-analytic policy comparison promising. This does not validate behavior at
binding constraints; those cases remain required in that comparison.

The next opportunity is more specific than “cache geometry.” The current
Cartesian gauge basis is block diagonal across components, yet each legacy
plus/minus stencil check rebuilds and validates the entire boundary at both
production and refined grids. Unchanged components are repeatedly audited.

## Exact reuse, with current decisions preserved

1. **Cache continuous component validation independently of node count.**
   `CartesianFourierCurveState.boundary_curve` validates at
   `config.validation_resolution`, then discretizes at `config.num_nodes`.
   The current 256/512 continuation configurations both validate at 256
   samples. Cache the report by exact coefficients and every validation/bounds
   setting, then discretize separately. Reuse also applies to the unchanged
   component during another component's directional probes. Preserve all
   validation failures and bounds checks.
2. **Reuse the Kress adapter for the same immutable sampled curve.**
   `PeriodicCurveAdapter.__post_init__` performs another sampled-polygon
   intersection check. The existing node-based geometry identifier hashes the
   arrays, but `adapt_periodic_curve` rebuilds the adapter on every call.
   Key a bounded cache by the complete geometry contract, including native
   grid/period and derivative/weight data. Do not use only component ID, object
   identity, or the displayed truncated geometry hash. Do not substitute a
   continuous-validation report for the sampled-polygon audit without proving
   their grid and tolerance contracts agree.
3. **Separate boolean admissibility from exact clearance reporting.**
   `multiradial_geometry_admissible` needs a yes/no answer, but its adapter
   computes full pairwise polygon intersections and segment distances.
   Disjoint sampled-polygon bounding boxes with distance strictly above the
   original required clearance can certify a separated pair cheaply; all
   uncertain pairs can use the current calculation. This preserves the
   predicate if proved and tested. A lower bound must never be stored as an
   exact measured clearance in `ComponentPairReport`. Keep the full reporting
   path or explicitly distinguish certificate bounds from distances.

Frequency-independent geometry is also rebuilt for repeated field calls at
one state. A fit-local prepared boundary can extend the above reuse, with
cache keys covering both the geometry and assembly settings. Shape changes,
topology events and resolution changes must invalidate the appropriate entries.
Nothing here justifies reusing a certificate for a nearby, different shape.

## Smaller follow-up inside the compiled evaluator

`CompiledEvaluator.evaluate` currently constructs both the prediction and full
shape Jacobian for every trial state. Rejected line-search candidates need only
the prediction. A lazy split could retain local compilations and source traces
for a forward-only trial, then solve receiver illuminations and check angular
derivative convergence when that state actually needs a Jacobian. Preserve the
existing forward angular check on every trial and derivative checks before any
Jacobian use. The same-state prediction consistency check still applies.

This is a bounded implementation opportunity after the geometry work. It must
be compared with the current eager implementation, including any cost of a
second reduced solve and cache management. Current compiled full-worker
diagnostics show zero local-shape cache hits on the first central and two-star
fits: updates change both components, although same-state objective/Jacobian
reuse is active. Do not estimate full-inverse savings from a translation-only
cache benchmark or the earlier known-count local inverse.

## A separate policy decision

The existing `analytic_constraint_policy="true"` removes the historical
finite-difference stencil restriction from the analytic Jacobian. Actual
candidate geometry is still checked. This can eliminate entire probe families,
whereas exact reuse only makes them cheaper. It changes the optimizer's
constrained-direction behavior, so it needs a separate matched comparison with
binding geometry constraints, one-sided/unresolved cases and the original
recovery checks. Do not combine that policy change silently with SPD-006.

The discriminator is a per-stage count/time breakdown for component
validation, sampled self-intersection and pair-clearance work, followed by a
matched complete inverse. Keep the same classification decisions and final
quality for exact reuse; compare time and recovery at the same final requirements
for a policy change. No new speed factor is claimed by this source review.

Source anchors:
[component boundary construction](../../../../../solvers/sdf_inverse/explicit_fourier.py),
[Kress adapter](../../../../../solvers/gpr_bem_kress/geometry.py),
[multi-component validation](../../../../../solvers/gpr_bem_kress/multicomponent.py),
[stencil policy](../../../../../solvers/sdf_inverse/radial_topology.py),
[current geometry configuration](../../../../../run_radial_fourier_topology_inverse.py).
