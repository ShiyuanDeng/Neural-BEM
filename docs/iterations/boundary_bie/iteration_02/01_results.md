# BIE-002 — completed modal/structure diagnostic

2026-09-15. These completed results open Boundary–BIE iteration 02.
Author/reviewer: Codex / self-review; no independent reviewer claimed.

**Decision: stop/defer the simple projected-field and centered-band prototype;
retain tuned nodal Kress. No successor is released.**

The [iteration-01 plan](../iteration_01/03_plan.md) ran five fixed geometries at
0.5 and 1.25 GHz within all hard budgets. All ten forward references and full-mode
coordinate controls qualified. Analytic single-interface tangent checks and
noncircular Taylor tests passed. Multi-component sensitivities remain
**FORWARD_ONLY / SENSITIVITY_UNQUALIFIED**.

- **H2-FIELD — NO_USEFUL_SIMPLE_COMPRESSION.** Circle and ellipse tolerate
  reduced fields; star and both saved two-star geometries fail the full-space
  residual gate at every declared truncation. A smaller nodal Kress grid already
  provides accurate results. The qualified high-frequency ellipse's dense modal
  prototype is 3.44x slower for forward evaluation and 3.50x slower including one
  analytic JVP, with full parent/derivative setup and wrapper costs included.
- **H2-OPERATOR — ORACLE_STRUCTURE_ONLY.** Sorted full-matrix coefficient
  profiles show structure, but the predeclared centered bands fail the required
  accuracy/storage combination across noncircular tests. Dense cross-component
  interactions further limit savings. No predictable sparse assembly algorithm
  or sparse-solve speedup was demonstrated.

The numerical measurements, tolerances, sampled sensitivities, three-pair timing
ranges, cost ledger, limitations and preserved startup failures live in the
[result bundle](../../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/README.md).
[Machine-readable summary](../../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/summary.json)
and [reporting validation](../../../../results/validation/boundary_bie/BIE-002-20260915-modal-diagnostic-02/reporting_validation.json)
support the closeout without replaying physical solves.

This negative result concerns the tested simple projection and band patterns;
it does not refute all spectral BIE techniques. There is no inverse-recovery,
production-integration, new geometry-basis, BIE-004 or geometry-reuse claim.
All shared numerical modules were read-only and retained identical hashes.
Other topology work was preserved on the existing branch.
