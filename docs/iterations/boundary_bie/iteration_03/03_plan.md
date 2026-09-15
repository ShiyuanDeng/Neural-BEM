# BIE-006 — bounded local operator reuse

- **Approval status:** APPROVED — user's “then go”, 2026-09-15, accepting the
  bounded Idea 3 diagnostic discussed in this session.
- **Execution status:** COMPLETE — [BIE-006 result bundle](../../../../results/validation/boundary_bie/BIE-006-20260915-205942-operator-reuse/README.md);
  `STOP_FIRST_ORDER_OPERATOR_REUSE`, 2026-09-15.
- **Owner:** Codex. **Reviewer:** self-review; independent reviewer unassigned.
- **Question:** does first-order operator reuse earn its factorization cost
  through a wider accurate region or finite-reuse savings beyond tangent data?
- **Baseline:** existing branch at `a5fb5ac`; BIE-002/BIE-004 and the accepted
  single-interface refined derivative audits. No branch/worktree creation.

## Frozen design

Read `TOP-012-20260912-acquisition-route-a/suite/runs/H/central-ellipse-star/trajectory.json`.
Base = row 1. Directions = row 2 minus base, row 3 minus base, row 4 minus base,
each normalized by its maximum point displacement on 4096 fixed native samples.
No truth, loss or held-out value selects a direction. K=3 Cartesian coefficients,
unchanged native period/origin, no re-gauge or node redistribution. The replay
uses straight coefficient paths; no claim about a controller retraction.

Scene length = 0.1 m. Maximum sampled physical displacements = 1e-5, 1e-4,
1e-3, 5e-3 m (0.01, 0.1, 1, 5 mm). Report RMS as well as maximum displacement.
Frequencies = 0.5 and 1.25 GHz, independent models per frequency. Use BIE-004's
frozen TOP-018 acquisition: 24 paired source/receiver selections, 24 RHS,
source strength 1e-6, lossless nonmagnetic epsr 6 exterior / 3 interior;
constants and all coordinates copied verbatim from the saved observations.
No truth observations enter this comparison.

N=128 with N=256 exact reference at **every** base and candidate. Analytic
directions also checked across both N at the base. Geometry: existing 1024-point
validation, fixed [0.2,0.8]^2 bounds, sources/receivers outside with clearance
greater than both 0.01 m and twice the largest nodal weight. Infeasible steps
remain recorded and are not replaced. No inverse run.

E: fresh production operator assembly plus LU solve. T: base LU tangent solve
and Y0+h*dY. O: A0+h*dA, B0+h*dB, C0+h*dC plus **new** LU solve. Derivative
construction includes its primal kernel recomputation. No scaling changes,
modal projection, explicit inverses, high-order library or optional P arm.

## Gates and decision

Production parity <=2e-11; primal recomputation <=2e-11; exact/approximate solve
residual <=1e-10. Forward 128/256 discrepancy <=2e-7; tangent discrepancy
<=2e-5. Failed quality gates stop promotion and retain data. Report paired and
full receiver relative/absolute error; primary norm is paired scattered data
relative to the refined answer with a 1e-12 incident-norm floor. Also report
O's residual against exact A/B, which is distinct from its approximate residual.

Primary useful-error gate =1e-3 (0.1%); contextual gates 1e-6 and 1e-2. Useful
range is the contiguous passing prefix of the frozen amplitude ladder, with
no extrapolation. A range advantage means at least one ladder level, with O
reaching >=1 mm, in at least 4/6 direction-frequency cases spanning both
frequencies. An encouraging successor additionally requires >=1.3x finite-reuse
saving over E after setup and one exact validation per four predictions. Within
a region where T qualifies, O must justify any extra cost; matching T more
expensively is a stop result. No automatic controller promotion from one base.

Measure second-order error slopes over the two smallest non-roundoff errors;
these are explanatory, not new derivative qualification. Save every arm's data
and exact matrix residual. Report only qualified rows as accuracy evidence.

## Cost and bounds

Separate cold setup, already-available base, fresh direction, cached direction
and four-point ray scenarios. No free full Jacobian assumption. Include geometry
generation/validation in online cost. Exact/refined accuracy audits are recorded
separately and in all-audited totals. Show break-even only when online cost is
below E, and disclose that audit-free savings need an unimplemented validity
policy. Count nearby actual saved states as a geometric upper bound, not proof
that other directions inherit the measured accuracy. No infinite-reuse claim.

Three additional sequential timing repeats: 1.25 GHz, direction to row 2,
1 mm; fresh base, analytic direction and E/T/O each repeat. Rotate arm order.
Single-thread BLAS. Record hardware, library versions, load and numerical
workers before/after arms; concurrent runs disqualify controlled timing claims.

Hard caps, checked before each operation: **60 exact assemblies, 24 analytic
assemblies, 100 LU factorizations, 150 batched solves, 30 updated O solves,
900 seconds, 4 GiB RSS**. Expected work: 60 exact, 15 analytic (with 15 primal
kernel recomputations), 87 factorizations, 102 solves, 27 updated solves.
Check shared numerical hashes at frequency and timing boundaries. Failed
attempts consume budget; do not silently expand limits or replace cases.

Artifacts: fresh `results/validation/boundary_bie/BIE-006-<timestamp>-operator-reuse/`
with frozen inputs/plan, source snapshots/hashes, ledger, actual complex data,
accuracy/refinement/timing/geometry rows, reporting audit, static error plot,
manifest and decision. Tests are algebra/geometry-only; no uncounted physical
solves. Results open iteration 04 only after execution. Shared topology/solver
files remain read-only; this is permitted concurrent isolated BIE work.

## Closeout

Completed without scope or numerical threshold changes. Expected work counts
matched exactly; all quality gates passed and benefit gates failed. See
[iteration 04](../iteration_04/01_results.md). No shared numerical changes,
branch/worktree creation, inverse run or successor execution.
