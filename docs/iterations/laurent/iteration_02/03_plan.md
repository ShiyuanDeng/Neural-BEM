# LAU-001-R1 — repair and independently recheck the compression screen

**Approval:** APPROVED by the user's 2026-09-17 instruction, “just keep fixin
and testin”, following the outsider review. This authorizes the bounded repairs
and checks below and supersedes the earlier hold for this work.
**Execution:** COMPLETE. Owner: Codex. Reviewer: unassigned.
Evidence: [qualified rerun](../../../../results/validation/laurent/LAU-001-R1-20260917-151900-qualified/README.md).
66 tests pass; all 528 saved comparisons pass the artifact-consistency audit.
Results open [iteration 03](../iteration_03/01_results.md).

Question: does the reported derivative-preserving compression survive correct
physical references, every acceptance gate, independent resolution changes,
and nearby asymmetric geometry?

- Keep the current branch and checkout. Change only `experiments/laurent_compression/`
  and its records. Prior result bundles and imported solvers remain unchanged.
- Preserve the original numerical gates. Qualify nodal receiver **and derivative**
  references at N=256/384; use nodal reciprocal traces with independent centered
  Kress finite differences as a check. Enforce physical derivative qualification
  before testing masks. Record compression-only errors separately.
- Compute residuals in fixed oracle flux coordinates `(u, J*d_n u)`. Include the
  objective derivative in a single common acceptance function for all stages.
- Retain circle, ellipse and star; add a fixed asymmetric perturbation of the
  star. Primary sizes remain ka=2 and 5. ka=10 remains a qualification-only
  stress test. All fixture coefficients and physical frequencies are frozen.
- At fixed B double K; at fixed K double B. Test both fixed fraction and fixed
  absolute per-block entry counts. Count protected storage separately.
- Test frozen masks at the two planned star offsets (0.005 and 0.01 RMS radius)
  and with a declared separate illumination set; no held-out result selects masks.
- Check the continuous Hadamard expression on compressed traces separately from
  the derivative of the discrete masked solve.
- Preserve finite-difference failures. Qualify centered differences by step
  refinement; do not relax tolerances to obtain a desired verdict.
- No sparse assembler, optimizer change, production promotion or speed claim.

Budget per numerical run: 45 minutes, 8 GiB, 500 physical assemblies, 1,200
factorizations and 2,500 RHS batches. Account at the operations, reserve before
execution, checkpoint after each case, record actual environment/source hashes,
and refuse to overwrite any output directory. Pilot before campaign.

Fresh artifacts go under `results/validation/laurent/LAU-001-R1-<timestamp>/`.
The conclusion will report precisely which gates and cases pass. A failed
retention rule does not refute all modal representations. Results open iteration 03.
