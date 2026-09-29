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
| Latest cycle | [Iteration 03 / MA-002](iteration_03/01_results.md): the frozen SC-050 policy recovers 3/3 at contrast 0.5 and 2, 2/3 at 4, 0/3 at 13.3. Causes: the `⌊3 max(k, k_i)⌋` band over-releases beyond the contrast-insensitive observable frontier, and circle localization fails at 13.3. Resonance shortens horizons (single-pole law within 2x for pole-shifting directions) but does not cause the failures. |
| Review of the vision | [Independent review](iteration_01/02_proposals/02_independent_review.md). §5.1 is gauge-dependent. The resonance mechanism does not apply to the contrast-0.5 benchmark. |
| Current code check | [MA-001R](../../../results/validation/modal_atlas/MA-001R/README.md), 2026-09-29: Part B re-run on `feature/shape-frequency-continuation` at `032092cd` (CUDA default). Integer quantities identical; continuous ones agree to round-off. |
| Code | `experiments/modal_atlas/` (isolated; no production or continuation code changed). Imported unchanged from `claude/magical-meitner-11naoj` on 2026-09-29. |
| Next | [MA-003 plan](iteration_03/03_plan.md): exterior band and dense exact-Mie localization, separately and together, then transfer to untouched scenes. |

## Cycle history

| Cycle | Question / state |
|---|---|
| [01](iteration_01/03_plan.md) | Vision received and reviewed; MA-001 planned. |
| [02](iteration_02/01_results.md) | MA-001 complete: circle (Mie) and 11 qualified BIE states. MA-001R reproduces Part B on current code; [MA-002 planned](iteration_02/03_plan.md). |
| [03](iteration_03/01_results.md) | MA-002 complete: denser-than-host targets break the frozen pipeline; diagnosis; [MA-003 planned](iteration_03/03_plan.md). |
