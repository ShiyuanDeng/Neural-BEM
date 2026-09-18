# Iteration 03 — compression after independent qualification and fixed-count checks

Opened by the completed [LAU-001-R1 repair](../iteration_02/03_plan.md),
authorized by the user on 2026-09-17 after the outsider review.
Measurements: [qualified bundle](../../../../results/validation/laurent/LAU-001-R1-20260917-151900-qualified/README.md).

**Verdict: STRUCTURE_ONLY, narrowed.** The validation defects are repaired;
the results do not establish practical compression on the star fixtures.

- Independent Kress derivatives qualify all eight ka=2/5 native controls.
  Native physical derivative error is at most 6.64e-11, so the large masked
  derivative errors were not an unqualified native derivative reference.
- The objective gate is enforced everywhere and residuals use the promised
  fixed flux scaling. All 128 smallest-step finite-difference checks pass.
- The ellipse passes at a fixed 30% remainder budget. Both star fixtures fail
  the 30% and 50% fixed entry budgets, including after trace refinement.
- The star's refined 30% result survives independent K/B refinement and local
  held-outs, but uses approximately 19% more entries than the entire smaller
  qualified remainder. The earlier “retention improves under refinement”
  interpretation was insufficient evidence of useful compression.
- Breaking the star's symmetry reduces forward-only derivative error from
  order one to 6.43e-6 / 4.88e-5 at ka=2/5 and 30% retention. Both retention
  rules still fail the residual gate. The enormous original derivative-aware
  advantage does not generalize to this asymmetric control.
- The continuous Hadamard check can be physically accurate when the discrete
  masked derivative fails. They must remain separate acceptance questions.
- B=64, 28 terms passes all numerical gates on the eight primary cases;
  20 terms passes at ka=2 but fails at ka=5. This is coefficient-window
  qualification, with no matched timing or default-promotion claim.
- All four ka=10 native controls remain UNQUALIFIED. Their failure does not
  establish a fundamental limit of Laurent or Fourier representations.

Validation: **66 tests passed**. The independent artifact read-back checks
528 comparisons, 3,168 directional rows, 283 masks, 73 source hashes and the
resource ceilings. The campaign completed in 129 seconds at 0.89 GiB peak RSS.
Original LAU-001 and intermediate repair bundles remain unchanged.

The sparse-assembler proposal is not justified by the retained-fraction result
alone. The narrower useful next question is whether an independently qualified
coefficient-window budget reduces actual work against the current nodal
reciprocal/compiled path. No sparse prototype or production change was made.

Remaining scope limits: one asymmetric control, six directions, limited local
offsets, lossless equal-permeability single interfaces, no inverse campaign,
and no separate compression sweep of the projected-Nystrom operator.
