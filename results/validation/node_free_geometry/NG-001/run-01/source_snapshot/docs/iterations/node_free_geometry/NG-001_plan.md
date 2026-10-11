# NG 001 coefficient geometry comparison

2026-10-11. Pre-registration before numerical runs. User requests code and
numbers against current geometry and authorizes experiments without further
approval. Existing checkout and branch are retained.

## Question and intervention

Can a curve-quadrature-free implementation retain the centred arclength
increment and complete directional derivative at the current accuracy, and
what does it cost? Can coefficient/interval certificates decide its geometry
without a polygon fallback? Derivation and literature:
[research note](../../reports/node_free_geometry_research_2026-10-11.md).

Implement an isolated engine under `solvers/bem_inverse/`. Finite products
use padded linear convolution. Speed/reciprocal speed use scalar binomial
polynomials composed in coefficients with complete residual checks. Arclength
phases use a coefficient exponential and cropped harmonic recurrence, checked
against the complete phase differential residual. Arclength output uses the
integration-by-parts contraction. Preserve the centred zero-step cancellation.
Differentiate the actual finite polynomial algorithm with forward tangents.
No maintained selector or default changes in this component study.

Validity uses a directed interval verifier for the exact finite stored curve:
coefficient Taylor enclosures of arcs, separation of nonadjacent arc boxes,
and monotone derivative projections for nearby arcs. It returns valid,
proved inadmissible, or unresolved. Reuse its divided-difference bound with
the new direct increment inequality; compare to the old scalar inequality.
No sampled fallback in the new engine. Construction accuracy residuals are
ordinary float64 and must not be described as interval-verified approximation
error bounds. The admissibility verifier's arithmetic claim is separate.

## Frozen panels and controls

- Use GC-001's saved TG-002 panel: the centred start and last accepted states
  for all 30 cases, with its nine fixed moves per state (three directions at
  0.1 micrometre, 1 mm and 6 mm). Copy/hash the manifest and move inputs into
  the fresh evidence directory. No truth geometry or new inverse fitting.
- Compare finite updates with `certified_spectral` (current CPU trial and CUDA
  preparation when available), and independently refined spectral quadrature
  at N and 2N. Saved GC-001 receipts provide an additional cross-check.
- Full tangent preparation cost of the current implementation remains charged.
  The new implementation initially computes three directional derivatives;
  report its directional cost separately, never as a full-Jacobian speedup.
- Analytic controls: circles, ellipses, and `z=w+a*w**2` at a=0.2, 0.49, 0.5,
  1.0. Compare known regularity/simplicity and interval outcomes. A cusp or
  unresolved contact is not a transverse-crossing proof.
- Complete directional derivatives on start, circle c4, kite c4, hook c4,
  aphex c4: compare to the current complete tangent, independently refined
  analytic quadrature tangent, and central differences of the new finite map
  at 1e-7 and 5e-8 m. Include all three frozen directions.

## Accuracy and budgets

Production comparison gate: maximum coefficient-sum update discrepancy no
larger than 1e-5 times base mean speed. Also report the tighter 1e-7 gate,
nanometres, coefficient L2 and independently sampled maximum error. Reference
refinement must meet 1e-7 times mean speed; otherwise its ranking is unresolved.
Tangent gate: relative coefficient L2 error <=1e-3 against a qualified complete
reference; report 1e-5 separately. Near-null denominators have an absolute
1e-10 package-units/metre floor and are listed separately.

Initial working band B=max(256,4K), fine band 2B. Maximum scalar degree 512;
phase degree at least 8 and selected by a real-axis Taylor remainder target
1e-13. Full scalar residual tolerance 1e-10 relative. Phase residual target
1e-8 in uniform phase. No tuning by comparison errors or truth. One later
changed construction is allowed only with a new plan amendment stating the
observed mechanism, preserving the first-run evidence.

Interval verifier: 30 decimal digits, initial 16 arcs, maximum depth 18,
20,000 pair cells and 5 seconds per curve. Omitted small coefficients remain
charged through interval tail norms. Strict positive area and regularity
floor use the current 1e-12 mean-squared-speed convention. Resource exhaustion
is unresolved. Capture failed nonlinear construction and certificate attempts.

Run once per fresh output; incremental per-state receipts and traceback on
failure. Measure synchronized wall times, preparation, finite update,
nonlinear residual checking, and validity separately. Use one CPU worker and
single BLAS/OpenMP threads. CUDA control falls back only with a recorded
reason. Timing warm-up is recorded separately from measured calls.

## Decision and closeout

Report qualified counts, maximum/median errors, tangent retention, changed
validity decisions, unresolved counts, and paired cost distributions. A
working-band or certificate budget failure refutes only this practical
construction. Do not infer inverse recovery from geometry components. Only
after component qualification may a separately registered TG-002 inverse
comparison be proposed or run. Validate, commit and push code, documentation
and all results after every run, including failure evidence.
