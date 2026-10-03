# Local-radius and stationary-branch diagnostics

Opened 2026-10-03 after the user's approval of the first three experiments in
the [theory-document review](../../theory_directions_cartesian_fourier_2026-10-03.md).

Question: can local stability/nonlinearity explain the early paired-data C
failure, can the proposed handoff inequality be evaluated usefully, and is there
resolved evidence of folds in a bounded stationary branch?

- [Frozen diagnostic plan](iteration_01/03_plan.md): TR-001 radius atlas,
  TR-002 saved handoffs, TR-003 stopping and branch diagnostics.
- [Implementation and commands](../../../experiments/theory_radius/README.md).
- Evidence: `results/validation/theory_radius/`.

TR-001 is complete: 40/40 numerical rows qualify; damping enlarges the
high-contrast C's stage-2 empirical radius about 41x, while paired and full
truth-local radii are similar. See [results](iteration_02/01_results.md).
TR-002 and TR-003 remain in progress. This track changes no production default and makes
no new inverse-recovery or certified-convergence claim. Existing FM-003 work
remains owned by the cleaned-interface track.
