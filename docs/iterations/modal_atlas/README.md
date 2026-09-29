# Modal atlas

**Research question:** What does the modal structure of the boundary
wavefields explain about how scattering data become shape information? Can
that explanation support frequency, band and trace-resolution decisions?

Opened 2026-09-28 by user direction from the
[research vision](iteration_01/02_proposals/01_research_vision.md), with
approval to proceed independently. Nothing was moved. The closed Laurent and
Modal-compression tracks, and the Shape/frequency continuation evidence, are
cited as starting evidence.

## Current handoff

| Item | State |
|---|---|
| Latest cycle | [Iteration 02 / MA-001](iteration_02/01_results.md). The pair identity is exact. The frontier is bracketed by trace supports and tends to `2k`. The trapped-pole horizon law holds with constant 0.1. Sensitivities need traces to `√τ` with band `≈ K_trace(√τ) + 0.6p`. Cancellation does not explain brightness at contrast 0.5. |
| Review of the vision | [Independent review](iteration_01/02_proposals/02_independent_review.md). §5.1 is gauge-dependent. The resonance mechanism does not apply to the contrast-0.5 benchmark. |
| Current code check | [MA-001R](../../../results/validation/modal_atlas/MA-001R/README.md), 2026-09-29: Part B re-run on `feature/shape-frequency-continuation` at `032092cd` (CUDA default). Integer quantities identical; continuous ones agree to round-off. |
| Code | `experiments/modal_atlas/` (isolated; no production or continuation code changed). Imported unchanged from `claude/magical-meitner-11naoj` on 2026-09-29. |
| Next | Three candidates in iteration 02; none dispatched. |

## Cycle history

| Cycle | Question / state |
|---|---|
| [01](iteration_01/03_plan.md) | Vision received and reviewed; MA-001 planned. |
| [02](iteration_02/01_results.md) | MA-001 complete: circle (Mie) and 11 qualified BIE states. |
