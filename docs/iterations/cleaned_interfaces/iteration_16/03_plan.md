# NF-001: outsider audit of the node-free claim

2026-10-02. The user authorized code fixes, integration and experiments without
further consultation. Owner: Codex. Independent reviewer: unassigned.
Baseline: `31f12978`, existing `feature/shape-frequency-continuation` checkout
(the older default branch contains no cleaned interface). No branch is created.

## Question and scope

Which parts of the maintained inverse actually avoid boundary nodes, and can
we remove a numerical approximation without changing its finite trial map?
Audit the modal operator, interval construction, NU-005/006 validity and
projection, and the public runner. Preserve all historical observations and
campaigns. Do not infer all-36 retention from local tests.

## Certain corrections and shared interfaces

- Describe modal physics as boundary-collocation-free, with sampled interval
  proposals and frontier geometry; describe NU-006 as spline-free quadrature.
- Expose certificate arithmetic assumptions in receipts. A coefficient residual
  inequality is a theorem; an undocumented FFT allowance is not an interval proof.
- Expose the retained NU-006 update through an explicit public geometry selection,
  including CLI, campaign identity, plans and result receipts. Keep the legacy
  spline selection as the default for old CI-001 callers and experiment wrappers.
- Correct any reproducible stale or misleading validity records.

## Diagnostics (declared before execution)

1. **Analytic projection tangent.** Differentiate the actual discrete arclength
   quadrature, including normalization, phase and FFT Nyquist removal. Compare
   with centered differences at several steps, refined grids, and a complete
   finite-trial data derivative. Circle, kite, elongated ellipse and a saved
   core endpoint; small and large bands. Gate: column difference <= 1e-5 versus
   the existing 1e-7 m FD, complete-trial directional error <= 1e-3, finite
   outputs. Compare bounded LM runs with the same policy/data/quotas. Retain as
   an opt-in experimental update only if those checks pass; no default switch.
2. **Adversarial certificate/aliasing checks.** Regular crossing `z=w+w^2`,
   near-cusp simple curves `z=w+a*w^2` with a<1/2, reversed orientation, and
   quadrature refinement on elongated curves. A failure to certify means
   inconclusive, not proof of intersection. Record errors and refusals.
3. **NU-007 gate analysis.** Independently recompute threshold-scaled differences
   from the saved host/device gap rows, including coverage and finite-value
   checks. Retain the original failed gate. This diagnostic cannot adopt NU-007
   or claim a new campaign pass.

Controls: float64, fixed seeds, single CPU BLAS thread, sequential numerical
comparisons, unchanged physics tolerances and observations. Diagnostic budget:
20 minutes for the focused suite and local experiments (excluding inspection
and implementation); no 36-case campaign. Required artifacts: executable script,
JSON with every tested arm and refusal, source hashes, environment, test results,
derivation and primary-literature links. Results open iteration 17 and live in
`results/validation/cleaned_interfaces/NF-001-outsider-review/`.
