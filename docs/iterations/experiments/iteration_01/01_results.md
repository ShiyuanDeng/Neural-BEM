# Iteration 01 — cross-domain methods and their limits

Numerical work: 2026-09-16. Filed in the iteration structure: 2026-09-17.
**Execution status: COMPLETE. Decision: close this exploratory cycle.**

## Why this cycle exists

The user asked for ideas with theoretical foundations in other domains and
potential novelty in GPR FWI, explicitly allowing a departure from Laurent and
asking for independent judgment about existing documents. The stopping direction
was: “keep going until genuinely big (good) findings that genuinely need my next
steps. or stop after you hit all the walls.”

Three routes were investigated through numerical implementation, stronger
controls, qualification and primary-source checks. None established a result
that warranted a new user task. “Closed” applies to these investigations, not to
all possible GPR methods or the entire literature.

The authoritative measurements and detailed interpretation remain in the
[research report](../../../../results/experiments/outsider_research_20260916/README.md).
This iteration record summarizes decisions and links evidence rather than
duplicating the report's result tables.

## Findings and decisions

| Route | What survived | Limitation that decides the next action |
|---|---|---|
| Photonic-design duality → support exclusion | A global finite-model residual lower bound can exclude an entire candidate support under explicit material constraints, with conductive layered physics | The strongest comparison shrinks the incremental gain, broader materials admit wrong-support fits, and a uniform continuum modelling-error bound is missing. Retain as conditional research evidence; no integration |
| Data-derived operator ROM → inversion objective | The implemented fixed-projection operator agrees with an independent interior construction; some selected ranks improve a depth basin | Gains are inconsistent across rank, noise and source configurations, and close electromagnetic prior art narrows novelty. Demote this direction |
| Passive spectra → shape/material separation | Independent full-wave calculations confirm small-target radius/material ambiguity, including frequencies not used in fitting | Passivity alone does not resolve that tradeoff. Retain the counterexample; no shape-identifiability claim |

All three are inverse-method questions. None measures an improvement to the
automatic topology controller, establishes a complete-worker speedup, or
qualifies a new production boundary solver. Their use of existing BEM code for
independent checks does not make them Boundary–BIE implementation results.

## Evidence and reproducibility

- [Joint report, figures and source citations](../../../../results/experiments/outsider_research_20260916/README.md).
- [Validation and source/result hashes](../../../../results/experiments/outsider_research_20260916/validation.json): 10 focused tests passed and eight saved final dual certificates were freshly checked.
- [Support-certificate code and commands](../../../../experiments/support_certificates/README.md), including broader-material fits and their refinement failures.
- [Operator-ROM code and commands](../../../../experiments/operator_rom/README.md), distinguishing the initial exploratory objective from the published fixed-projection construction.
- [Passive-shape code and commands](../../../../experiments/passive_shape/README.md), including the independent BEM checks and statistical limits of residual comparisons.

The code stays under `experiments/`; detailed numerical bundles stay under
`results/experiments/`. No files or measurements were moved or rerun for this
filing step. Production code and the earlier Laurent records are preserved.

## Closeout

No successor proposal or execution plan is scheduled. The support-exclusion
method has the strongest remaining case, but broader material uncertainty and
credible modelling-error control are unresolved scientific requirements, not
an assigned implementation task. Reopening any route should identify new
evidence or a discriminating hypothesis that addresses its recorded limitation.
