# TOP-016 implementation preflight

Owner: Codex `/root`. Independent reviewer: `/root/top016_review`, read-only source/artifact review, no physical solves. Base revision `d3bbdae`; reviewed `9acae6b` differs only by the supplied zip. User authorization is recorded in the iteration-09 plan.

## Source and API map, recorded before numerical changes

- `run_topology_scene_benchmark.py`: `shared_data` validates frozen observation/material/acquisition equality; `truth_curves` is evaluation/oracle only; `geometry_metrics` supplies unchanged matched polygon Hausdorff/IoU scores.
- `run_fourier_topology_controller.py`: portable `serialize_state`/`deserialize_state`; `baseline._problem`, `_geometry_config`, `iteration01_solve_config` preserve the physical interface.
- `solvers/sdf_inverse/topology_controller.py`: `zero_padded_component`, `component_parameterization`, `_optimizer_config` provide exact padding, geometry and inherited LM settings. No controller policy changes.
- `solvers/sdf_inverse/radial_topology.py`: `MultiRadialFourierState`, `component_radius_floor`, `multiradial_geometry_admissible`, `evaluate_multiradial_objective`, and fixed-topology `run_multiradial_fd_inverse` are reused.
- `solvers/sdf_inverse/optimization.py`: `ComplexScatteredData.frequency_weights=1/n` supplies mean relative squared residual. Existing flattened real/imag ordering is a fixed permutation of the plan's frequency-block ordering; loss and derivatives are equivalent under that permutation. Validate norms before invoking its normalization floor.
- Current LM couples loss target/loss change and accepts any production decrease. The refined feasibility guard is geometry-only. If preflight qualifies inputs/numerics, a small opt-in loss-change toggle and candidate validation/budget hooks are needed; preserve default behavior and reuse the same LM. Runtime refined decrease agreement must be checked before acceptance, not by scoring only the final state.

## Ordered implementation and verification

First build a small experiment-only preflight driver: recover exact retained inputs, freeze portable observations/hashes and contract; test padding/data checks; audit K=9 representation and both-resolution feasibility; then measure the declared node ladder, oracle convergence and two-scale derivatives with solve-boundary accounting and a hard wall timer. No pilot implementation or runs precede those gates. Ordinary geometry and mocked tests use zero physical solves; all physical validation counts in the 5000/1200-second Phase 0/1 allowance.

If preflight fails, retain its precise obstruction and close out without unnecessary optimizer edits. If it passes, implement the bounded screen and only then gated pilot hooks, with focused default/acceptance/stopping/budget/retention/data-isolation tests.

Review disposition and measured checks will be appended before execution/closeout.

## Independent implementation review — 2026-09-14

Reviewer `/root/top016_review` completed read-only source/artifact inspection and hashing with zero physical solves. **Accept** exact retained states, original observation reuse, K=9 gauge-constrained Cartesian chart and existing residual builder with weights 1/N. **Require** dense padding/representation checks, saved-state resolution ladder and added-frequency oracle/derivative checks before screen release. The two stars are analytically representable; the ellipse's polar-profile approximation must be measured.

**Require before any pilot** opt-in loss-change disabling; per-candidate both-resolution loss-decrease reliability (existing controller cross-resolution factor 5); attempted/completed per-frequency ledger and pre-batch reservations; latest accepted-state checkpoint before subsequent Jacobians; and training-only optimizer inputs. **Reject** interpreting the global relative L2 field as equal-frequency aggregate or treating refined geometric admissibility as refined loss acceptance. **Defer** all controller changes and full-suite work. All recommendations accepted by the implementation owner within the plan; pilot-specific hooks are deferred until numerical preflight and screen gates pass.

The reviewer has not independently run the numerical gates. The owner is responsible for measurements, with source/input hashes and all physical calls charged. Preflight starts with the cheaper input/representation/resolution checks, before generating new observations.

## Numerical continuation, declared before the information-screen outcomes

Input/representation/resolution preflight passed using 39 attempted/completed solves and 7.021 s. The smallest qualifying training pair is 128/256; freeze it. The Phase-0 driver is archived at `phase0/driver.py` matching its original source hash. `run_top016_screen.py` consumes that evidence without repeating it and uses only the remaining 4,961 solves / 1,192.979 seconds. Wall accounting sums active numerical worker elapsed times; documentation, implementation and review time between workers is not compute time. One worker, single-thread BLAS; no speed-comparison claim.

The screen driver finishes Phase 0 with analytic-truth 256/512 oracle checks for the three new frequencies and frozen-pair evaluation-frequency checks on the three saved states. It computes complete S/F Jacobians/spectra at both resolutions and both FD scales (1e-4 and 5e-5), using the existing central/feasible-side stencil, explicitly stopping any wholly unresolved column. Per-column two-scale discrepancy must be <=0.25, the qualified TOP-008 stability threshold. Residual frequency-column order is fixed; extract S from F by the known permutation and undo the factor 1/sqrt(4).

For each principal scene, freeze the eight weakest physical directions from the production 0.5-GHz SVD in original descending-spectrum order. Normalize by arclength-weighted linear RMS normal displacement to 1 mm, then record both signs at 0.5 and 1 mm. Each usable direction must have all four feasible probes, with both S/F data changes at least five times the larger of repeatability, roundoff floor, and production/refined disagreement in the **base-subtracted change**. Require the plan's median/fraction thresholds at both resolutions and both amplitudes; never replace a refused direction or count a floor-limited ratio as infinite. This conservative operational mapping is fixed before measurement.

If either case fails, stop the binding screen immediately; mark the other case unmeasured if it has not run, since release requires both. No inverse implementation or pilot runs are justified by a failed screen. Physical observation generation and evaluation accuracy work are charged alongside derivative and probe work. Twelve focused no-forward tests pass, including observation bytes, retained state, residual scale/order, budget prechecks/failure accounting, physical normal scaling, and both-resolution/both-amplitude screen decisions.

## Pilot release and implementation — recorded before pilot outcomes

Both principal information gates passed, all eight weak directions usable in each. Phases 0/1 used 2,781 attempted/completed frequency solves, no failed solves, and 777.976 active seconds. The full screen remains saved in `phase1/sensitivity.json`.

The owner added only opt-in hooks to `run_multiradial_fd_inverse`: independent loss-change disabling, candidate acceptance, Jacobian batch reservation, accepted-state checkpoint before Jacobian, and cache-event accounting. Defaults and the LM equations remain unchanged; the archived pre-hook source is at `phase1/radial_topology_source.py`. A known-residual regression reproduces the archived default trajectory exactly. Thirty-one focused tests pass with no physical solves, including feasible-side derivative regression, both-resolution margin/reliability arithmetic, training-only fit signature, budget reservations, cached work, and interrupted-Jacobian state retention.

`run_top016_pilot.py` implements one bounded trial per invocation. It maps the existing problem's angular frequencies to Hz explicitly. Truth and evaluation observations are outside `fit_stage`. Active per-frequency weights are 1/N. Stage target/margins are the approved values; all other LM settings are inherited and serialized. Per-candidate validation applies both-resolution loss decreases with factor-5 disagreement allowance; out-of-regime candidate resolution stops the trial. Endpoint audits reserve 12 frequency solves before optimization batches; all objective, derivative, rejection, refinement and evaluation work counts.

Budget interpretation, confirmed by the independent reviewer before pilot outcomes: Section 9 says “On any cap … stop that trial”. Failure to reserve the next required Jacobian inside a stage allocation stops that arm as inconclusive; later allocations remain unused. Normal optimizer termination permits the next predetermined stage. No stage-budget borrowing or opportunistic restart is allowed.

Run independent S/F trials with at most two processes, each with single-thread BLAS. Report actual per-trial wall ceilings without interpreting concurrent elapsed times as a controlled speed comparison. No hashed numerical source will be edited during those workers. Only after all six main arms have fixed endpoints may the specifically conditional two local controls run.

## Final closeout

All six main trials and both eligible local controls finished their bounded execution. TOP-016 closes without promotion: the principal comparison and local controls are stage-budget-limited, while completed F-merge introduces a geometric failure. Total 10,306 attempted/completed frequency solves, zero failed. [Independent closeout review](closeout_review.md) verifies the measurements and identifies reporting limitations, now explicit in the report and [gradient associations](gradient_associations.json).

Final focused validation: **31 passed**, zero physical solves. All trial numerical-source hashes, original producing-state/observation hashes, and frozen v1/v2 specification hashes match. The zero-forward summary now verifies stage work including endpoint scoring and all wall ceilings. No completed trial was rerun after the session interruption or to fill a missing summary. Results open [iteration 10](../../../../docs/iterations/topology/iteration_10/01_results.md); any successor remains a separate review decision.
