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
TR-002 is complete: 24 handoffs checked, 17 outside the local argument's scope,
seven evaluable indicators and no sufficient-inequality passes. The scalar
estimate does not establish a useful scheduling gate. TR-003 is complete:
four positive-curvature endpoint audits, two confirmed turns on the contrast-4
data homotopy, and a wrong-shape contrast-13.3 stationary endpoint reached
without an observed turn. The adapter and unrelated-source-guard failures are
preserved with the [qualified closeout](../../../results/validation/theory_radius/TR-003-branches/QUALIFIED_REPORT.md).
This track changes no production default and makes
no new inverse-recovery or certified-convergence claim. Existing FM-003 work
remains owned by the cleaned-interface track.
