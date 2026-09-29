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
| Latest cycle | [Iteration 06 / MA-005](iteration_06/01_results.md): **both gates pass.** A damped start `k(1 + 0.25i)` plus fixed stages up to the measured observable frontier (DF) recovers 7 of 8 transfer attempts at contrasts 4 and 13.3, where frozen SC-050 recovers 0 (6 of 6 against 0 of 6 excluding `opposite_c`, which repeats the development C's data). Development: 11 of 12. At contrast 0.5 DF equals D, which matches SC-050 to within 0.001 mm. The 13.3 original C remains unsolved. |
| Review of the vision | [Independent review](iteration_01/02_proposals/02_independent_review.md). §5.1 is gauge-dependent. The resonance mechanism does not apply to the contrast-0.5 benchmark. |
| Current code check | [MA-001R](../../../results/validation/modal_atlas/MA-001R/README.md), 2026-09-29: Part B re-run on `feature/shape-frequency-continuation` at `032092cd` (CUDA default). Integer quantities identical; continuous ones agree to round-off. |
| Code | `experiments/modal_atlas/` (isolated; no production or continuation code changed). Imported unchanged from `claude/magical-meitner-11naoj` on 2026-09-29. |
| Next | Proposed, not run ([iteration 06](iteration_06/01_results.md#proposed-next-steps-not-run)): independent review; noise-aware frontier; realistic damped noise; the 13.3 C; unknown permittivity. |

## Cycle history

| Cycle | Question / state |
|---|---|
| [01](iteration_01/03_plan.md) | Vision received and reviewed; MA-001 planned. |
| [02](iteration_02/01_results.md) | MA-001 complete: circle (Mie) and 11 qualified BIE states. MA-001R reproduces Part B on current code; [MA-002 planned](iteration_02/03_plan.md). |
| [03](iteration_03/01_results.md) | MA-002 complete: denser-than-host targets break the frozen pipeline; diagnosis; [MA-003 planned](iteration_03/03_plan.md). |
| [04](iteration_04/01_results.md) | MA-003 complete: G1 fails; wrong-basin mechanism; damping probes; [MA-004 planned](iteration_04/03_plan.md). |
| [05](iteration_05/01_results.md) | MA-004 complete: damping repairs 2 of 4 (G1 fails); the 13.3 star is limited by the final band; [MA-005 planned](iteration_05/03_plan.md). |
| [06](iteration_06/01_results.md) | MA-005 complete: G1 and G2 pass; DF 7/8 transfer against 0/8 frozen. |
