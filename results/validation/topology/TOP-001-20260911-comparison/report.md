# TOP-001 closeout — 2026-09-11

**Do not adopt raw top-two refinement.** All 60 prespecified replays and 20
exploratory E replays completed. Top-two refinement does not remove the split's
ranking sensitivity; reducing its per-candidate budget saves refinement work
but spends more on later optimization. The original default remains available.

An expanded three-candidate shortlist gives a useful clue: all ten Cartesian
split replays then reach nanometre geometry with lower summed work. It is not
ready as a universal policy: the five-case controller qualification increases
total work and fails the death case's declared training-error comparison.

## Design and provenance

[Contract](../../../../docs/iterations/topology/iteration_01/03_plan.md),
[reference amendment](../../../../docs/iterations/topology/iteration_01/04_execution_amendment.md),
[exploratory E declaration](../../../../docs/iterations/topology/iteration_01/05_expanded_shortlist_diagnostic.md),
[five-case qualification contract](../../../../docs/iterations/topology/iteration_01/06_controller_qualification.md).

Both charts replay fresh **unmodified `345038a` (B0)** pre-event states.
Historical radial qualification failed because its candidate list no longer
reproduces at B0; that failure and the clean-source qualification remain in
[separate bundles](../README.md). A uses one candidate × 3 LM iterations;
B uses two × 3; C uses two × 1. E, declared after the unperturbed results, uses
three × 1. Each chart/arm has one unperturbed replay and nine perturbations:
relative coefficient magnitudes 1e-4, 1e-3, 1e-2; seeds 11, 29, 47.

Within each chart, arms have identical initial states and observations. The
two charts' pre-event states differ, so this is not a pure chart substitution
experiment. Candidate cap 48, 64/128 nodes, optimizer, gauge, construction,
objective and acceptance are fixed. Holdout at 1.5/2.5 GHz never enters the
inverse. Truth only qualifies outputs.

## Measured split results

Ten replays per row; geometry is the maximum sampled Hausdorff across those
replays. Costs are summed BIE frequency solves, including TD and excluding
independent oracles and final audits.

| Chart | Arm | Worst geometry (µm) | Worst holdout relative L2 | Total BIE solves |
|---|---|---:|---:|---:|
| Radial | A | 0.033749 | 3.4347e-6 | 2,641 |
| Radial | B | 0.033749 | 3.4347e-6 | 4,586 |
| Radial | C | 0.032230 | 2.8898e-6 | 2,852 |
| Radial | E, exploratory | 0.032230 | 2.8898e-6 | 4,398 |
| Cartesian | A | 175.210848 | 9.6843e-3 | 6,567 |
| Cartesian | B | 175.453467 | 1.1021e-2 | 9,633 |
| Cartesian | C | 126.339373 | 8.3401e-3 | 7,408 |
| Cartesian | E, exploratory | 0.029554 | 2.7351e-6 | 4,696 |

[Quality/work figure](comparison.svg), [every replay and event sequence](suite_metrics.json),
[paired comparisons, stability and audits](analysis.json).

The Cartesian unperturbed A/B winners are the two nearly tied K9 contour fits.
The circular seed ranks third, so neither A nor B refines it. C still refines
only those contour fits: candidate work falls 429→420, but later fixed
optimization rises 621→759. Total work rises 1,109→1,238. E reaches the third
candidate: candidate work rises to 476, later optimization falls to 39, and
total work falls to **574**, with Hausdorff **25.123360 nm** instead of
**175.210848 µm**.

The reference construction is selected in only 4/9 perturbed Cartesian A/B/C
runs. E selects its own reference construction in 6/9; remaining label changes
are not evidence of poor reconstruction, since all E geometries remain below
30 nm. Radial construction-match fractions are A 8/9, B 6/9, C/E 5/9, while
every radial geometry remains below 34 nm. Exact candidate identity and
physical recovery stability therefore need separate interpretation.

## Broader E qualification

All five A and all five E Cartesian full-controller runs stop `recovered` with
the correct component count. E passes the geometry and holdout comparison on
all five. It fails the death training comparison: 1.5973e-6 versus A's
1.1025e-6, outside the predeclared 10%/1e-6 floor. Summed inversion work rises
**4,655→4,766**, despite the split improvement. No thresholds were relaxed.
[Complete qualification](../TOP-001E-controller-20260911/qualification.json).

Decision: retain E as an opt-in diagnostic. The next discriminating mechanism
is to retain baseline refinement and add the cheapest-dimensional candidate
only when the raw winner is more complex. This directly addresses the missed
family without paying for extra candidates in every group.

## Verification and limits

- **527 inverse tests passed.** [Log](tests.log). The accounting/replay/allocation
  tests include invalid budgets, empty domains, TD RHS batches, frozen states,
  gauge validity and a candidate whose polished order reverses its raw order.
- All 80 saved replays have paired inputs, source hashes matching their recorded
  implementation, monotone trajectories and valid production/refined event
  margins. No rejection is left unclassified. Eligible losers are reported
  separately from failed candidates. [Audit](analysis.json).
- An independent observer of actual complex batched `numpy.linalg.solve` calls
  counted **1,109**, matching the Cartesian A ledger exactly, stage by stage.
  [Accounting audit](../TOP-001-accounting-audit-20260911/verification.json).
- Work counts are not weighted for matrix size; TD batches have twice the source
  RHSs. All frequency/node/candidate controls are fixed and stage counts remain
  available. No controlled wall-time claim: the recorded launchers used extra
  disjoint cohorts, and other qualifications overlapped.
- Two orchestration failures occurred after/beside successful numerical work:
  the original worker encountered a directory owned by the last extra shard,
  and the qualification stdout printer rejected a NumPy boolean after saving
  its case comparison. The owning shard completed; all 60 primary metrics and
  all five case comparisons exist. Summaries were rebuilt from those files,
  without rerunning or replacing observations. Original logs are preserved.
- These are noiseless, separated, same-material synthetic scenes. The result
  does not establish behavior for noise, nested holes, multiple materials,
  non-star-shaped components, or unseen acquisitions. Independent reviewer:
  unassigned; no independent scientific review is claimed.
