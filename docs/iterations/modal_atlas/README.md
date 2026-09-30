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
| Latest cycle | [Iteration 07 / MA-006](iteration_07/01_results.md): **COMPLETE, 9/10 cells qualify.** Persistent modal Müller matrices, both traces, acquisition maps and selected derivatives now accompany the cutoff analysis. Relative to projection, reduced solves require a larger tested cutoff in 1/9 data/J cases and 3/9 local-update cases. Exact Schur correction restores the reference. This is a projected-Nyström control, shape band P=12; no deployed adaptive K_u or inverse-speedup claim. |
| Previous inverse result | [Iteration 06 / MA-005](iteration_06/01_results.md): both gates pass; DF 7/8 transfer (D alone also 7/8), versus frozen 0/8. Excluding repeated development data gives 6/6 versus 0/6. Development 11/12. The original C at contrast 13.3 remains unsolved. These results concern damping and update band M, not trace cutoff K_u. |
| Review of the vision | [Independent review](iteration_01/02_proposals/02_independent_review.md). §5.1 is gauge-dependent. The resonance mechanism does not apply to the contrast-0.5 benchmark. |
| Current code check | [MA-001R](../../../results/validation/modal_atlas/MA-001R/README.md), 2026-09-29: Part B re-run on `feature/shape-frequency-continuation` at `032092cd` (CUDA default). Integer quantities identical; continuous ones agree to round-off. |
| Code | `experiments/modal_atlas/` (isolated; no production or continuation code changed). MA-001 was imported unchanged from `claude/magical-meitner-11naoj` on 2026-09-29. MA-006 adds `operator_atlas.py`, its tests and read-back/plotting report; earlier hash-pinned sources remain unchanged. |
| Next | No successor launched. [MA-006 closeout](iteration_07/01_results.md) identifies affordable cutoff-error estimation and qualification at active M=37–85 as the next numerical questions. The independent MA-005 proposals remain unexecuted. |

## Cycle history

| Cycle | Question / state |
|---|---|
| [01](iteration_01/03_plan.md) | Vision received and reviewed; MA-001 planned. |
| [02](iteration_02/01_results.md) | MA-001 complete: circle (Mie) and 11 qualified BIE states. MA-001R reproduces Part B on current code; [MA-002 planned](iteration_02/03_plan.md). |
| [03](iteration_03/01_results.md) | MA-002 complete: denser-than-host targets break the frozen pipeline; diagnosis; [MA-003 planned](iteration_03/03_plan.md). |
| [04](iteration_04/01_results.md) | MA-003 complete: G1 fails; wrong-basin mechanism; damping probes; [MA-004 planned](iteration_04/03_plan.md). |
| [05](iteration_05/01_results.md) | MA-004 complete: damping repairs 2 of 4 (G1 fails); the 13.3 star is limited by the final band; [MA-005 planned](iteration_05/03_plan.md). |
| [06](iteration_06/01_results.md) | MA-005 complete: G1 and G2 pass; DF 7/8 transfer against 0/8 frozen. |
| [07](iteration_07/01_results.md) | MA-006 complete: operator atlas and projection/reduced/Schur cutoff screen; 9/10 cells qualify, omitted-mode feedback changes usable cutoffs in high-contrast cases. |
