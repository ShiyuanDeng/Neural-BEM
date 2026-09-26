# SC-043 — can the action diagnostic earn its decision cost?

2026-09-26. Owner: Codex. Independent reviewer: unassigned. Authorized by
the user's request to run successive strategy iterations. No new checkout.

Question: does a prospective complete-update prediction select an update
band more usefully than two cheap rules, once all diagnostic work is charged?
The frozen rules below are not tuned to this study's outcomes. These remain
six development shapes; no claim of independent shape generalization.

Use SC-042's six portable starts. Apply one initial K64 cleanup, then evolve
at K192 for every policy. This is a common platform for the policy ablation,
not a declaration that SC-042 selected a universal best state strategy.
Use all 19 measured frequencies, inherited weights, grids and tolerances.
Initial M is 25 for star, 22 for kite, 19 otherwise.

Three decisions per path, each allowed 304 solve/reciprocal work units and
22 LM iterations. At a decision the choices are current M or M+6:

- `fixed`: always release to M+6.
- `stagnation`: release if the previous stage stopped for gradient, small
  step or no decreasing step, accepted no step, or its last accepted step
  reduced loss by less than 5%; otherwise
  continue at M. Initial flags come from the saved parent stop, or from
  its last two history losses if no stop is stored. A numerical stop is not
  treated as convergence. Save every initial flag and subsequent decision.
- `atlas`: compute the complete high-M trial Jacobian and physical mass
  metric. The low-M model is its corresponding cos/sin principal subspace,
  checked against separately prepared physical velocities in the tests.
  At the common test radius .12/k_max, release only when the higher band's
  additional optimal predicted decrease is at least 10% of the present
  loss, and loss exceeds 1e-14. Otherwise continue. This radius is not a
  finite-validity guarantee; the existing LM acceptance controls the steps.

The atlas uses the full coupled matrix, not the historical capped QR heatmap.
Qualify every diagnostic against N/2N fields and all Jacobian columns;
inherited field gates, relative derivative gate 1e-3. Failure blocks that
policy path and remains in its denominator. Two base solves and two
reciprocal batches cost 76 units per decision. These are included in 304,
leaving 228 for fitting; simple policies retain all 304. No backend cache
reuse is claimed. Record decision and qualification before fitting or truth
scoring. The common radius, threshold and increment never change mid-study.

At most 18 paths, 16,416 fitting/diagnostic units plus 2,340 endpoint-audit
units. The audit is SC-042's full-trial N/2N/J/FD check. Decision diagnostics
have a 900 s emergency ceiling; each fit has 3600 s; all limits are retained
as distinct from convergence. At most six numerical workers in total on the
shared host. Failed policies do not receive extra work or easier tolerances.

Compare last returned states against BOTH fixed and stagnation controls:
RMS/Hausdorff, work (diagnostics separated), bands, actual stage improvement,
failures and audit results. Use 0.01 mm floors. A promising atlas requires
geometric-mean RMS ratio <=0.8 against each baseline, no geometry ratio >1.25,
no additional failure, and all diagnostics/endpoints qualified. Otherwise
reject this rule as a superior continuation method under this cost model.
Do not reinterpret a failed 10% threshold retrospectively as a success.

This is a short continuation-suffix decision test. A positive result releases
fresh-shape/noise tests of the policy; a negative result redirects attention
to simple regularization and full-pipeline robustness. It neither settles all
  possible atlas policies nor justifies tuning another threshold on these runs.

Preflight revision before any SC-043 diagnostic or fit: use the last accepted
step's improvement for stagnation, rather than total stage improvement. The
SC-042 trial logs expose why the latter is weak: a stage can improve greatly
initially and then spend many trials below the acceptance margin. Thresholds,
costs and atlas rules are unchanged. The initial code/contract/manifest are
preserved in `preflight_v1/`; the active manifest records their digests.
