# Relaxed BIE

**Question:** Does relaxing the boundary integral equation improve shape
recovery when gradients, numerical accuracy and computational cost are
controlled fairly?

Opened 2026-10-03 by user direction. This is the active home for relaxed-BIE
research, including its full-matrix acquisition controls. Numerical code
remains in `solvers/bem_inverse/`; FM-001/FM-002 drivers and sealed evidence
keep their existing paths.

## Current handoff

| Item | State |
|---|---|
| Current cycle | [Iteration 02](iteration_02/01_results.md): RB-001 complete; all four immediate stops removable, no added recovery |
| Completed experiment | [RB-001: recover the stopped trajectories](iteration_01/03_plan.md) |
| Approval status | **APPROVED** by the user's 2026-10-03 request, "go on relaxed bie track" |
| Execution status | **COMPLETE** — four replays, qualification, four continuations, both-resolution audits and closeout |
| Current decision | Keep the ordinary damped production default and the response opt-in. RB-001 adds 0/4 full or paired recoveries; all finer endpoint audits pass. This is bounded negative evidence, not stationary or universal failure |
| Next action | Review the closeout. No further numerical experiment is approved; a smaller-step-first comparison would require a new scoped proposal |
| Literature and GPU assessment | [Review and resolved recommendations](iteration_01/02_proposals/01_literature_and_gpu_review.md) |
| Mathematical reference | [Complete reduced-loss derivative](../cleaned_interfaces/iteration_19/04_derivative.md), preserved at its sealed path |
| Historical evidence | [FM-001/FM-002 index](evidence_index.md) |

FM-002 completed all twelve runs: damping recovered 3/3 cases with or without
relaxation, and the real prefix recovered 1/3 with or without relaxation.
The complete gradient passed qualification and 477 regression tests. All four
failed runs stopped at the fixed numerical-resolution guard; their rejected
candidates still decreased loss at both evaluated resolutions. This warrants
an accuracy-controlled continuation check before interpreting those stops as
failure of relaxed BIE itself.

## What moved here

This track owns the current interpretation, research question, literature/GPU
review and future plans. Navigation now points here. Historical experiment
IDs and iteration numbers are not reassigned: cleaned-interface iterations
18 and 19 remain the original FM-001/FM-002 records. Their plans, reports,
derivation, source archives and run bundles are covered by saved hashes and
remain byte-for-byte at their original locations. The new review explicitly
qualifies the old closeout recommendation without rewriting it.

New experiment artifacts belong under `results/validation/relaxed_bie/RB-001/`.
The ordinary default, frozen thresholds and existing observations remain fixed.
The [completed bundle](../../../results/validation/relaxed_bie/RB-001/README.md)
records 506 passing tests and 47.12 minutes across the recorded numerical
phases. C/R1 reached its original fitting wall cap; the other tails completed
their scheduled bands with stage-quota exits. None establishes stationarity.

## Cycle history

| Cycle | State |
|---|---|
| [01](iteration_01/01_results.md) | Starting FM-002 evidence, revised assessment and the sealed RB-001 advance plan |
| [02](iteration_02/01_results.md) | RB-001 complete: four exact replays; both diagnostics remove each immediate stop; four qualified finer endpoints but 0/4 recoveries |

Follow the [shared iteration workflow](../README.md). Execution results are
in iteration 02; the advance plan retains its sealed pre-result state.
