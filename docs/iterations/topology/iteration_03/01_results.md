# Topology iteration 03 — selective refinement qualified

TOP-005 completed 2026-09-11. [Full report and reproduction commands](../../../../results/validation/topology/TOP-005-20260911/README.md).

The opt-in `--include-simplest-candidate` policy passes the declared quality and
summed-work gates. Across ten Cartesian split replays, worst sampled Hausdorff
falls from 175.21 µm to 30.80 nm and summed BIE frequency solves fall
6,567→3,787. All ten radial trajectories and their 2,641 solves are exactly
unchanged. Four of the five full-controller trajectories are exactly baseline;
the split improves, and total work falls 4,655→4,323. All five quality gates pass.

This qualifies a selective refinement option, not a universal default change.
It spends extra work on four controller cases where the final trajectory does
not change. The initial hope of no birth/death overhead was therefore not met.
Keep the baseline default, the failed top-two/three-candidate studies, and their
original thresholds. 533 inverse tests pass; saved-event margins, monotonicity,
paired observations and source hashes pass independent artifact checks.

## Next discriminating questions

1. **Generalization:** does selective inclusion help when a split's children
   are noncircular, so the simple candidate is useful only as an initializer or
   is correctly rejected? Design that comparison before changing the default.
2. **Cost of unused probes:** can a training-only signal predict when the
   extra lowest-dimension candidate is worth refining? Current overhead is
   96/28/24/76 solves on death/merge/mixed/repeated-birth respectively.
   Do not tune a raw-gap threshold solely against these five cases.
3. **Construction and label stability:** F remains geometrically stable on
   the split while some corridor labels change. Separate equivalent candidate
   geometry from a genuinely different basin before changing construction.

TOP-002 (trigger), TOP-003 (construction) and TOP-004 (acceptance) remain deferred.
No further numerical change or experiment is silently approved by this results
record. Independent scientific review remains unassigned.
