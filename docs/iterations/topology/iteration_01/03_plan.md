# TOP-001 execution contract — 2026-09-11

- **Approval status:** APPROVED under the user's 2026-09-11 instruction,
  “see track A in readme. i want you to go as for as you could”. This session
  authorizes progressing the topology track without an additional ID approval.
- **Execution status:** COMPLETE. Closed 2026-09-11; see [iteration 02 results](../iteration_02/01_results.md).
- **Owner:** Codex. **Independent reviewer:** unassigned.
- **Branch:** `track/topology-TOP-001`.
- **Baseline:** [B0](../../../baselines/B0_2026-09-10.md), executable source
  `345038a`; starting HEAD `5353cab`.
- **Review:** [decisions and scope amendments](02_proposals/02_codex_review.md).

## Fixed design

First check A against both historical split events with the saved configurations.
Stop and diagnose if either event is not reproduced. Then use both saved
pre-event geometries, cap 48, the saved acquisition, fixed 64/128 nodes, and the
unchanged inner optimizer, candidate construction and acceptance rules.

| Arm | Candidates per group | LM iterations per candidate |
|---|---:|---:|
| A | 1 | 3 |
| B | 2 | 3 |
| C | 2 | 1 |

Use magnitudes `0, 1e-4, 1e-3, 1e-2` relative to the pre-event mean radius and
seeds `11, 29, 47`; zero is run once. Draw a unit isotropic Gaussian direction
in the chart's accessible coefficient space (gauge tangent basis for Cartesian),
scale its Euclidean norm by magnitude times mean radius, then retract in the
existing gauge. Reuse the identical state across A/B/C. Record actual sampled
boundary displacement and all parameters. Perturbations are paired across arms
within each chart; they are not claimed to be the same deformation across charts.

Ceiling: two historical qualification replays plus 60 comparison replays
(3 arms × 2 charts × (1 zero + 3 magnitudes × 3 seeds)), with an overall
two-hour wall ceiling. Each keeps maximum 10 cycles and 7 events. Historical
qualification and final measurement work are reported separately from inversion
cost. Stop on a failed historical event reproduction or exhausted ceiling;
preserve failures and completed work. No parameter tuning after observing results.

## Measurements and decisions

Every replay writes its observations in portable JSON, manifest with source and
input hashes, metrics, trajectory, candidate trials, per-stage work and rejection
classes in a fresh `results/validation/topology/TOP-001-<stamp>/` directory.
Evaluation-only holdout frequencies are 1.5 and 2.5 GHz. Report training and
holdout relative L2, sampled Hausdorff, relative geometry RMS, event identity and
sequence, and stability against the same arm's unperturbed event.

C is evidence for allocation only when both its measured refinement cost and
total inversion cost do not exceed A. Report unmatched pairs explicitly. Adopt
only if C changes the event and improves geometry under that condition, without
degrading training/holdout qualification. B alone cannot justify adoption.
If useful candidates are excluded by raw ranking, open TOP-003 from these
measurements. Keep the default at A unless the evidence supports adoption.

Run focused accounting/replay/allocation regressions, then the full inverse
suite. Closeout opens `iteration_02/01_results.md`; do not rewrite this contract
to anticipate results. The dashboard and handoff will link the resulting evidence.
