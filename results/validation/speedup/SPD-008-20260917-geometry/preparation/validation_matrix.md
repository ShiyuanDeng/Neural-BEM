# Validation matrix for later integration

Definitions were read, not executed. `audit.json` records source hashes, exact
test names and line numbers for 81 existing functions. Fixture coordinates and
selectors are in `fixtures.json`; hash/schema checks passed, geometric checks
remain pending. Repository-relative paths below are under
`/home/drdeng/Neural_SDF_BEM_AD`.

| ID | Required check | Existing starting point | Pass condition after implementation |
|---|---|---|---|
| G01 | Repeated identical component at production/refined grids | `explicit_fourier.py:boundary_curve`; prepared SPD-006 handoffs | One reusable validation report when effective validation settings match; separate discretizations and undersampling checks. |
| G02 | Change coefficients by one representable float; change bandwidth | Cartesian fixtures and `test_cartesian_fourier_chart.py` | Required cache miss, including signed-zero/shape distinctions in exact keys; decisions match baseline. |
| G03 | Change bounds, tolerance or resolved derivative sample count | `BoundaryValidationConfig` | Required miss; boundary-equality/bounds rejection unchanged. |
| G04 | Re-gauging of supposedly unchanged component | `MultiRadialFourierState.polar_angle_gauge_fixed`; hard profile input | Keys use actual post-retraction arrays; never skip re-gauging or round coefficients to create hits. |
| G05 | Same sampled points, different native period/origin/grid | `test_adapter_affinely_normalizes_a_nonstandard_period_without_changing_ds` | Canonical-grid and derivative/weight checks still apply on every adapter construction. |
| G06 | Equal content in distinct curve objects | `test_adapter_preserves_the_node_owned_curve_and_weights` | Each adapter owns its exact caller object; no cross-object alias returned from cache. |
| G07 | Bad weights/speeds/odd or too-small grids | `test_component_grid_failures_use_the_public_geometry_error_hierarchy`; `test_solver_owned_discretization_restrictions_fail_explicitly` | Same refusal and public exception hierarchy with cache warm and cold. |
| G08 | Same points with differing intersection tolerances | Parameterization versus sampled validation in `validation.py` | Separate cache entries unless both resolved cross and length tolerances match. |
| G09 | Self-intersecting polygon, zero-length edge, nonfinite data | `pytest/ordered_boundary/`; malformed fixture in `test_multicomponent.py` | Same baseline outcome; no successful record reused for altered points/ordering. |
| G10 | Cached invalid state repeated | Parameterization and adapter refusal paths | Failure remains a failure; public diagnostics preserved without retaining exception tracebacks. |
| G11 | Component reorder, rename, append, death, split, merge | 6 archived pre/post-event SPD-006 fixtures; permutation test in `test_multicomponent.py` | No stale identity, order, pair report or whole-boundary entry. |
| G12 | Cache eviction, byte cap, nested contexts and cleanup on exception | New tests needed | Values/decisions identical; retained payload bounded; cache state cannot leak into independent fits/endpoints. |
| G13 | Widely separated polygons | Circle fixtures in `test_multicomponent.py` and hard-case archive | Certificate agrees with exact predicate; records lower bound separately; actual distance reports unchanged. |
| G14 | Bounding boxes overlap but polygons do not | New rotated/concave fixture needed | Certificate reports uncertainty and uses exact fallback; no false rejection. |
| G15 | Touching, crossing, nesting and duplicate IDs | `test_topology_and_resolution_guards_fail_before_assembly` | Same refusal for cold/warm caches; disjoint-box certificate cannot bypass earlier component guards. |
| G16 | Clearance below/equal/just above required; altered weights/settings | Close-circle fixture and new threshold cases | Strict `clearance > required` preserved; ambiguity routes to old predicate; both absolute and weight-scaled thresholds covered. |
| G17 | 64 accepts while 128/256 refuses | `test_recorded_abort_state_is_admissible_at_production_and_refused_when_refined`; prepared TOP-006 checkpoint | Exact expected outcomes with caches populated in both coarse-to-fine and fine-to-coarse order. |
| G18 | Mandatory refined checks and handoff refusal | `test_refined_feasibility_guard.py` optimizer and handoff tests | Same initial-state rejection, candidate refusals and refined feasibility behavior. |
| G19 | Sources/receivers inside or too near a boundary | `test_sources_and_receivers_are_rejected_inside_any_component` | Still checked by compiled/full paths; boolean component-pair acceleration never certifies acquisition geometry. |
| G20 | Exact-cache integration with analytic/FD-compatible policy | `test_spd001.py`, `test_spd006.py`; central/two-star replay | Same Jacobians, candidate decisions, accepted states/steps and recovery; separate cache-only/certificate ablations. |
| P01 | True-analytic policy at a real feature-radius floor | Current mocked policy test plus saved hard-scene refusals | Candidate constraints remain enforced; feasible progress/stopping measured, not inferred from zero unresolved columns. |
| P02 | One feasible stencil side or neither side | `test_feasible_finite_differences.py` plus new physical geometry cases | FD-compatible behavior unchanged; true-policy differences explicit; no false stationarity claim. |
| P03 | Policy changes batch reservation/exposure | `radial_topology.py:jacobian`; `runtime.py:jacobian_work_bound`; `run_top017.py` ledger | Identical hard caps, accurate reservation/attempt accounting, extra progress distinguished from runtime per identical work. |

Suggested first regression selection after implementation: the two Kress API
files, two ordered-boundary files, refined-feasibility/feasible-FD suites and
SPD-001/006 focused suites, plus new cache/certificate cases. Use the existing
EMNerf interpreter and one BLAS thread. Add SPD-007/TOP-025 integration checks
before any full campaign, because current defaults and readiness routing must
remain intact. Freeze the exact selection in the experiment contract; do not
launch it while the current campaign is measuring this checkout.

Synthetic tests are for classification edge cases. The geometry-only fixture
replay establishes equivalence on saved states; full-update and complete-inverse
comparisons establish optimizer behavior and runtime. None substitutes for the
others, and the current preparation claims none of these future passes.
