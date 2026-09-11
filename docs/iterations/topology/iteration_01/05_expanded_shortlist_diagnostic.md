# TOP-001E — expanded-shortlist diagnostic

**Approval status:** APPROVED within the user's request to advance Track A.
**Execution status:** COMPLETE. Owner: Codex; independent reviewer: unassigned.

This is an **exploratory follow-up**, declared after the unperturbed A/B/C
results became available and before running E. It is not a fourth prespecified
arm of the original comparison. The original 60-replay suite continues unchanged.

## Evidence and question

The unperturbed Cartesian `(split, 2)` group ranks two K9 contour fits first,
then the circular seed third. B refines both contour fits, spends 1,538 BIE
frequency solves versus A's 1,109, and slightly worsens geometry. C spends 1,238
and improves sampled Hausdorff from 175.21 to 126.34 µm, with the same selected
construction. C's refinement cost is lower (420 versus 429), but later fixed
refinement consumes the saving (759 versus 621). That fails the total-cost
adoption criterion.

Question: does reaching the third-ranked, simpler candidate recover geometry
more cheaply overall? **E selects the best three raw candidates per group and
gives each one LM iteration.** This uses the existing implemented controls;
there is no change to candidate construction, objective, gauge, physics, or
acceptance, and no shape/count supplied from truth.

## Controls, budget and decisions

Reuse the fresh B0 references and the exact TOP-001 perturbation magnitudes and
seeds. First run the unperturbed Cartesian E replay. Continue only if its final
geometry and holdout error improve over A; otherwise stop and preserve the
negative result. If it passes, complete the ten conditions in each chart
(20 E replays total), with a one-hour wall ceiling. Compare measured total and
candidate-refinement BIE counts separately against the matching A/C records.

The output is fresh: `results/validation/topology/TOP-001E-20260911/`.
Its recorded launcher contains the E arm declaration and its own SHA-256, and
each replay records the unchanged numerical source hashes and all usual outputs.
One E process may overlap the two original A/B/C chart processes; no wall-time
comparison is made. This adds at most 20 exploratory replays to the original
contract, explicitly rather than silently expanding its primary sample.

Evidence for a useful follow-up is substantially improved geometry and holdout
at fewer total BIE solves. Refinement-only cost need not decrease, and any such
increase must be reported. Do not change the default based only on this split
diagnostic: broader automatic-event regressions are required for adoption.
