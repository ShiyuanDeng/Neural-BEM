# Research implementation principles

Prepared 2026-09-14. Adopted by user direction on 2026-09-14; shared guidance for all research tracks.

This is a supplement to [the iteration workflow](README.md), not another approval layer. The workflow owns folder conventions, experiment approval and collaboration rules. This document owns how to choose, implement and interpret a bounded numerical experiment. Adopt it by explicit user direction; do not infer authority to run adjacent experiments from its existence.

## 1. Optimize for a scientific decision, not for another implementation

Start each cycle with one question whose possible answers change what happens next. Name the cheapest measurement that distinguishes those answers, the intended reconstruction benefit, and the condition that ends the line.

A defect can be real without being the dominant reconstruction bottleneck. Finding a defect justifies a bounded correction and regression test; it does not automatically justify a new optimizer, representation, controller or benchmark campaign.

Do not choose work merely because it is easy to implement, produces a lower objective, creates more tests, or is the next numbered proposal. Equally, do not erase a real accuracy or cost improvement because the aggregate pass count did not change.

## 2. Keep different levels of evidence separate

Use the following distinctions in plans, dashboards and conclusions:

| Evidence | What it does not establish by itself |
|---|---|
| Code exists and unit tests pass | The mathematical method is correct or the inverse recovers geometry |
| A derivative agrees with finite differences | Useful optimization steps or successful reconstruction |
| A true geometry fits the observations | Uniqueness, stability, or convergence from an unknown initialization |
| Training residual decreases | Better shape, correct object count, or better prediction |
| One diagnostic succeeds | General controller performance |
| A benchmark gains no pass | No geometric, reliability or cost improvement anywhere |
| A small selected subset succeeds | Twelve-scene qualification or generalization |

Separate **measurement**, **interpretation**, **hypothesis** and **decision**. Use “not established” rather than turning an absent measurement into a negative finding.

## 3. Locate the failure before changing the architecture

Classify failures separately as forward-model inconsistency, numerical-resolution failure, derivative failure, infeasible geometry, insufficient representation capacity, wrong component count, poor fixed-topology shape recovery, poor held-out prediction, or resource exhaustion.

Several can coexist. Use controls that remove one factor: for example, fixed-topology recovery before changing topology proposals, and a near-truth diagnostic before making a global convergence claim. A diagnostic that uses a supplied count or truth-assisted initialization must be labelled as such and excluded from automatic-recovery claims.

Do not replace a working BIE solver because an inverse-data Jacobian is ill-conditioned. Do not add topology mechanisms to repair an isolated fixed-topology optimization failure. Do not revive a paused representation merely because another representation encounters an inverse-problem difficulty.

## 4. Make comparisons identifiable

Freeze the reference configuration, initial states, observations, geometry chart, feasible set, material assumptions, scoring definitions and work accounting before comparing arms.

Change one principal mechanism where possible. Necessary repairs shared by both arms are permitted, but must be explicit. Compare against the newly matched control, not against an older run that lacks those repairs.

A multifrequency continuation experiment tests the combined acquisition/continuation protocol unless separate arms isolate its components. Do not advertise a cleaner causal conclusion than the design supports.

For staged objectives, record each stage's active measurements, weights and normalization. Monotonicity applies within an unchanged objective; loss values from different stages are not automatically comparable. Retain common-frequency audit errors throughout.

## 5. A cheap diagnostic must be able to stop expensive work

A screening stage is not a gate if the full suite runs regardless of its answer. Predeclare numerical quality checks and the operational improvement needed to release the next stage.

Use solve-count caps and wall-clock ceilings as hard ceilings, not targets. Check the remaining budget before a batch whose maximum cost is known. Never overrun a cap and then interpret an unfinished experiment as a completed negative result.

Do not silently extend a ladder, add restarts, increase a frequency range, relax a gate, replace a failing scene, or open a successor experiment. A budget-limited run is **inconclusive within the declared budget**, unless the measurements already answer a narrower question.

## 6. Preserve the meaning of geometry and sensitivity

State whether coefficients represent Cartesian coordinates, a radial function, or a constrained subspace of Cartesian curves. Do not describe a gauge-constrained implementation as unrestricted Cartesian Fourier geometry.

Compare sensitivity in the same parameter coordinates and scaling. Report the physical boundary displacement associated with a coefficient perturbation; a singular value without its coordinate convention is not a physical resolution measure.

Full rank does not imply good conditioning. Similar singular values do not establish similar singular vectors or equal information matrices. Probe the same physical directions under competing acquisitions when making a claim about newly informative measurements.

Local, one-direction-at-a-time probes witness ambiguity but do not bound the complete nonlinear solution set. A local displacement bound around an incorrect reconstruction is not a bound on its distance from the truth.

## 7. Treat stopping and numerical accuracy as explicit design choices

Record separately:

- data-fit threshold reached;
- gradient or projected-gradient stationarity test;
- small step or small loss change;
- acceptance-margin rejection;
- infeasibility or unresolved derivative;
- work-budget exhaustion.

None is a substitute for the others. Preserve existing machine-readable stop strings where compatibility matters; explain them in reporting rather than silently changing their historical meaning.

Use stopping and acceptance settings consistent with the objective normalization and measured numerical accuracy. A large fixed absolute margin can dominate a small objective; making it arbitrarily tiny is not a substitute for checking numerical reliability. Verify the physical forward at the added frequencies and relevant candidate geometries, not only on an easy initial state.

Constraint-refused finite differences are not zero derivatives. Preserve feasibility checks and use the existing qualified feasible-side treatment where applicable. Do not obtain apparent progress by silently clipping coefficients, bypassing clearance guards, or changing the chart.

## 8. Protect the truth and evaluation-data boundary

Truth may generate synthetic observations, check representability and score completed reconstructions. It may not choose inversion updates, restart directions, accepted candidates, frequency steps, or the best iterate.

Separate optimization from evaluation in the program interface. The optimizer should receive observations, acquisition metadata and its initial geometry, not the truth object or held-out observations.

Once held-out scores are repeatedly used to choose research directions, describe them as **development evaluation data**, even if they never enter the optimizer. A later generalization claim needs genuinely untouched scenes or measurements. Do not retrospectively call a fitted frequency held out.

## 9. Implement the smallest credible test

Prefer existing state objects, residual builders, optimizer routines, validation helpers and artifact conventions. Put experiment orchestration in one small driver rather than creating a general experiment framework.

Before editing numerical code, write a short file/API map, list the proposed changes and add the tests that make them safe. A few opt-in configuration hooks can be appropriate; a second optimizer implementation, duplicated forward solver, new registry or broad refactor needs its own scientific justification.

Keep defaults unchanged during qualification. Make an experimental flag either graduate through a measured decision or remain clearly experimental; do not accumulate undocumented production alternatives.

When a defect blocks the experiment, repair it within the declared scope, revalidate both arms and retain provenance. If the required repair changes the scientific intervention or shared physical interface, stop with a scoped proposal instead of folding it into the current experiment.

## 10. Review once, then execute the approved contract

Use one implementation owner and an independent reviewer where available. Record actual assignments; never invent a reviewer or a successful review.

The reviewer checks the intervention, controls, data isolation, budgets and material numerical risks. Resolve disagreements as accept, reject, defer, or a named bounded diagnostic. Avoid repeated full-plan rewrites when a small amendment suffices.

Once the user approves an ID and its conditional stages, agents may proceed through stages whose gates pass without repeatedly asking for the same approval. They may not change the scope or authorize another ID. Per the user's 2026-09-14 override, branch or additional-worktree creation always needs separate explicit approval, including in full-access mode; an approved experiment, plan or ZIP does not grant it. Use the existing checkout sequentially by default, and never mutate a checkout being measured.

## 11. Count work and preserve negative evidence

Record attempted and completed forward frequency solves, failed solves, cache hits, objective calls, validation calls and derivative calls by stage. Where practical also distinguish matrix assembly/factorization from multiple-right-hand-side work. Measurement count alone is not a computational cost model.

For wall-clock claims record hardware, threading, concurrency and relevant load. Report partial work as a lower bound when accounting is incomplete. Timeouts, exceptions, wrong counts and poor predictions remain in the comparison.

Save inputs, configurations, source hashes, accepted states, terminal diagnostics and exact commands. A summary should be rebuildable from the saved artifacts without rerunning the inverse.

## 12. Keep documentation lightweight and authoritative

The shared workflow owns operating rules; the plan owns the experiment contract; result bundles own measurements; track handoffs own current status; the dashboard links them. Do not maintain competing copies of large results tables.

New proposals remain in the current iteration. Executed results open the next iteration. Do not manufacture a results file or renumber history merely because the research direction changed.

Correct an earlier interpretation with a dated amendment or a later review that links it. Preserve original measurements and executed plans. Do not rewrite history to make the latest explanation appear to have been predicted.

An experiment is complete when its artifacts and limitations support a clear decision, including a negative or inconclusive decision. “Keep iterating” is not a substitute for closeout.

## Staged-execution amendment — adopted 2026-09-14

The user adopted the [TOP-017 staged-execution amendment](topology/iteration_10/02_proposals/02_staged_execution_addendum.md). It distinguishes planned stage quotas from hard trial limits, requires effective intervention exposure, and preserves historical TOP-016 classifications. The approved experiment plan owns the numerical limits.
