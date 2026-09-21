# Modal compression closure — 2026-09-21

**Decision: CLOSED by user direction at iteration 02.** The user's instruction
was “okay close it here then.” No further numerical work is scheduled.
MC-001 Stage A is complete; Stage B and its possible inverse trial did not run.
This is the final research decision following the results and discussion, not
a new numerical result or an additional experiment ID.

## Why we stopped

The [entry screen](iteration_02/01_results.md) established real modal structure,
but no noncircular case met the chosen common forward/derivative mask gate of
50% represented slots at the required output accuracy. All 12 independent
reference qualifications passed; the failure was not an unresolved baseline.

The subsequent discussion identified a separate practical objection: the
current smooth, moderate-electrical-size 2D systems are small, and there is no
demonstrated complete-inverse performance benefit from reducing their operator
entries. The MC-001 qualified full systems had only 66–194 complex unknowns.
Counting fewer entries does not establish a binding memory or solve bottleneck.

The historical [BIE-002 matched timing](../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md)
supports this concern on its ellipse fixture. Median nodal assembly was
11.10 ms, LU 0.16 ms, the 24-RHS solve 0.09 ms and complete forward 14.14 ms.
From its [saved timing rows](../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/timings.csv),
eliminating LU and those solves would yield only about 1.8% forward speedup.
The projected modal implementation was 3.44 times slower overall. These are
local historical CPU observations, not a current GPU or universal crossover
measurement. Later [inverse profiles](../speedup/README.md) likewise expose
substantial geometry/validation costs outside linear algebra.

This does not prove that compression never pays in 2D. No hardware-specific
crossover was measured, and a universal “ten points per wavelength” or
“sub-millisecond GPU LU” assertion was not adopted as a measured fact. Directly
avoiding expensive assembly, larger coupled systems or a different reuse
workload could have different economics. Those possibilities do not establish
a benefit for the workload tested here.

## Scientific conclusions to preserve

- Forward sparsity, individual derivative sparsity and common-pattern sparsity
  are different properties. Symmetry can hide entries whose derivatives are
  nonzero; difficult shapes can also be dense without relying on symmetry.
- Adjoint/Hadamard shape calculus can obtain physical sensitivities from
  forward/adjoint traces without constructing each derivative matrix. The
  common-mask failure is not a proof that gradients rule out compression.
- An adjoint of the masked discrete model differentiates that model. Physical
  gradients evaluated from approximate traces target a different approximation;
  their consistency with the objective and inverse steps remains to be checked.
- The latest screen found encouraging physical derivatives from compressed
  ellipse traces. Off-anchor reuse, unseen directions/acquisition and a local
  Gauss–Newton trial were not released. These remain hypotheses, not successes.
- Lower represented counts, theoretical decay and cheaper matrix actions do
  not establish faster construction, factorization or a complete inverse.
- LAU-001-R1's validation repairs and the September 21 audit of the September 18
  studies remain part of the evidence. Preserve them alongside the original
  results rather than replacing the history with an unqualified negative.

## Archive and future interpretation

The [evidence index](evidence_index.md) connects original experiments, code,
results and PDFs across Modal compression, Laurent and Boundary–BIE. Nothing
was relocated or renumbered for closure. The Laurent cycle remains independently
closed at iteration 07 on its calibration-identifiability result.

Earlier proposals and the “next decision” section of the MC-001 results record
what was being considered before this closure. They are not pending tasks or
continuing authorization. No new branch, worktree, commit or push was requested.

Any future reopening would need new user direction and a specific benefit to
test. For a speed claim, the relevant evidence would be a measured workload
crossover at independently qualified, realistic dimensions, with assembly,
compression construction, all RHS/adjoints, geometry refresh and total inverse
cost included. Oversampling an already resolved problem would not establish
that crossover. No such benchmark is scheduled by this note.
