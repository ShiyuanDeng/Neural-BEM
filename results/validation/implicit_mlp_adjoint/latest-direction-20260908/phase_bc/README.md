# Start-at-truth and termination diagnostics — 2026-09-08

Commit `838bedf4eb37beb3c01ae770958e6c92f2abdf04`, with the working-tree changes hashed in [provenance.json](provenance.json).

The three-update truth control remains near its supervised target fit and improves training and fixed holdout errors. Maximum boundary error increases slightly, so this is a usable short local neighborhood, not a stability or recovery result. The separate frozen audit closes the historical termination question: the first valid fallback is backtrack 9, but its movement is below the declared meaningful-step floor.

Both experiments use eight source rows and eight receiver rows on the existing ring, paired diagonal readout (eight complex measurements per frequency), train frequencies 0.5 and 1.5 GHz, float64 SIREN width 64 with two hidden layers (8,577 weights), Kress nodes 194, Method-B bandwidth 96, grid 513 × 513, projected samples 256, arc-length integration 2048 and validation 1024. Conversion distance must remain at most 0.2 mm and refinement change at most 0.01 mm; maximum boundary movement is 2 mm. All existing Armijo and extraction gates are retained.

## Short truth control

The initialization is the exact-target SIREN fitting control built by the existing 6,000-step supervised procedure, with pretraining Eikonal weight zero. It is an approximate target fit, not the analytic boundary. The inverse retains Eikonal weight 0.01 and fixed regularization samples, learning rate 0.001, Adam with adjoint steepest-descent fallback, and a 14-halving search budget. Work budget: three accepted updates. The fixed evaluation-only holdout is 3.0 GHz; its independent 512-versus-1024-node oracle check is recorded in [Phase A](../phase_a/oracle_3ghz_validation.json). Holdout values never enter acceptance or stopping.

| Accepted iterate | Data loss | Regularized objective | Train rel. L2 | Holdout rel. L2 | Max boundary error (mm) | Movement (mm) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.00012263121 | 0.00060488644 | 0.010730664 | 0.11963353 | 1.191125 | 0.000000 |
| 1 | 6.788741e-05 | 0.00054435363 | 0.0081350821 | 0.11178056 | 1.149769 | 0.288362 |
| 2 | 6.1695467e-05 | 0.00053608002 | 0.0077540707 | 0.097611947 | 1.281490 | 0.218229 |
| 3 | 5.8510465e-05 | 0.00052639901 | 0.0074517973 | 0.089258326 | 1.290189 | 0.408107 |

Initial data-gradient norm: `1.007281379`. Initial Eikonal-gradient norm: `9.673492481`; weighted by 0.01: `0.09673492481`. The final budget iterate does not require another adjoint, so its gradient norms remain explicitly unevaluated.

Fitted amplitude changes from `0.249403379` to `0.251772623` (target 0.25); rotation from `-0.00100994828` to `-0.000689011437` radians (target 0). Center, mean radius, both conversion checks and every accepted holdout value are in [the compact trajectory](start-at-truth/kress_accepted_iterates.json). Boundary error is the maximum sampled Method-B-node distance to the exact target, not a certified continuous Hausdorff bound.

Stop: `maximum_iterations` after 3 accepted updates, 27 attempted training forward evaluations and 23 rejected trials. Four additional holdout evaluations are evaluation only. Inverse wall time: 387.219 seconds including callback work. Rejection reasons overlap: `{"boundary_motion_limit": 10, "conversion_distance": 3, "conversion_refinement_change": 1, "data_armijo": 17, "extraction_topology": 3, "non_finite_or_solver_failure": 0, "regularized_armijo": 17}`. The [trial log](start-at-truth/kress_trials.jsonl) records each candidate and every applicable failure reason; physics/motion tests are not evaluated when extraction or conversion rejects the candidate first.

Four additional all-frequency forward evaluations (initial field, analytic target, supervised target fit, final field), supervised fitting and oracle work sit outside the inverse counts/timing. The separate post-optimization replay validation below adds four more evaluation-only holdout predictions and is reported separately.

The three steps reduce data loss and holdout error, and all move more than the 0.1 mm reporting floor. Maximum boundary error nevertheless worsens from 1.191125 to 1.290189 mm. This separates a usable near-target neighborhood from the large wrong-start failure, while retaining evidence of geometrically adverse descent. Longer local stability, basin reachability and general recovery are not established. The ordinary full-recovery gates still report FAIL; a three-step truth diagnostic does not satisfy their recovery-from-wrong-start requirements.

The original run's 387.219-second inverse timing includes 52.217 seconds of successful holdout forward callbacks. Subtracting that measured work gives 335.002 seconds, with small callback bookkeeping overhead still included. The corrected driver saves the accepted checkpoint and completes optimization before an optional separate holdout replay; evaluation errors are recorded per iterate and final accepted weights are restored. A [post-optimization replay of this saved trajectory](post_optimization_holdout_replay.json) reproduces every holdout value with maximum absolute difference 0 and preserves final weights exactly. No inverse was rerun.

## Frozen fallback audit

Reloaded the historical `star-bw96` final checkpoint and its exact archived observations. This audit uses no holdout and does not replay Adam moments or update/snapshot a new neural state. It evaluates every unchanged production fallback from backtrack 0 through 14 and restores the frozen weights exactly after each trial.

| Backtracks | Rejection / result |
|---|---|
| 0–1 | Extraction/topology: two components |
| 2 | Boundary motion and both Armijo tests |
| 3–4 | Conversion distance |
| 5–8 | Conversion refinement change |
| 9–14 | All production gates pass |

Backtrack 8 has conversion distance 0.112325 mm (passes), but refinement change 0.0115825 mm (fails). Backtrack 9 lowers data loss from 0.3461879920809253 to 0.3460535595880327, a 0.0388322% improvement; its conversion distance is 0.109192 mm, refinement change 0.00900314 mm and movement 0.0707587 mm. This exactly reproduces the prior review probe.

Stop: `completed_frozen_diagnostic_budget`, after 16 attempted forward evaluations including the initial state, 235.460 seconds, and nine rejected trials. Independent reason counts: `{"boundary_motion_limit": 1, "conversion_distance": 2, "conversion_refinement_change": 4, "data_armijo": 1, "extraction_topology": 2, "regularized_armijo": 1}`. Full metrics are in [frozen_fallback_metrics.json](frozen_fallback_metrics.json).

A movement below 0.1 mm is explicitly classified as a crawl for this diagnostic. The floor is a declared reporting threshold, not an acceptance change or a convergence theorem. Every valid frozen fallback here is below it. An available accepted step explains the former premature stop; it does not explain or solve the approximately 36 mm wrong-start reconstruction error.

## Reproduction and validation

Exact commands are in [commands.txt](commands.txt). The frozen audit requires the existing locally ignored historical checkpoint and response archive. The direct truth control regenerates its supervised target fit. Per-weight CSV/checkpoints/response archives are generated locally; the compact JSON trajectory is the reviewable accepted-state record.

Validation: 53 focused inverse, driver and conversion-repair tests pass; see [tests.log](tests.log). Tests cover independent conversion rejection metadata, acceptance beyond eight halvings, unchanged fatal solver propagation with weight rollback, failed holdout replay isolation, the reporting-only movement floor, terminal unevaluated gradients and neural/analytic CLI defaults.
