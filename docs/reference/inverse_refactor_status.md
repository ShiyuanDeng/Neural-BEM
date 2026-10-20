# Inverse readability refactor

Questions: can the running solver be read directly as A1–C12? Can the
implementation move without changing arrays, decisions, dispatch, work,
callbacks, or restart behavior?

## Baseline

- Branch: `organised`; commit: `060aaaddface29a1cb6d0e8af617aff46761b854`.
- The only initial untracked file was the user's
  `inverse_solver_refactor_agent_prompt.md`; there were no source edits.
- A separate filesystem snapshot of the source and tests was captured before
  editing. It is a reference copy, not a Git branch or worktree.
- Numerical reference: the actual source, including its supported optional
  paths. No benchmark campaign is part of this refactor.

## Current-to-new map

All new modules below live in `solvers/bem_inverse/`.

| Section | Baseline implementation | Canonical destination |
|---|---|---|
| Outer loop | `runner.fit` | `runner.fit`, visible operation queue |
| Stage loop | `continuation.lm_backend.fit_stage` | `fit_stage.fit_stage`, visible iteration/retry/backtracking loops |
| A1 | `modal_geometry.ModalGeometry`, `ModalMuller._geometry` | `a1_geometry`, with the exact service cache retained |
| A2 | `modal_operator.radial_coefficients`, `kernel_matrix`, `muller_matrix` | `a2_muller`; device arithmetic retained in `modal_cuda` |
| A3 | `modal_operator.point_kernels`, Graf/regular-wave helpers | `a3_waves` |
| A4 | `ModalMuller._evaluate` factorization, solves, prediction | `a4_fields`; service sequencing in `a_forward` |
| B5 | `lm_backend.normalize`, `Objective._evaluation` | `b5_residual` |
| B6 | `batched.batched_projection`, `BatchedCertifiedUpdate.prepare` | `b6_geometry_derivatives` |
| B7 | `ModalMuller.derivative`, `_contract`, `modal_operator.hadamard` | `b7_data_jacobian` |
| B8 | `Objective.jacobian`, `gradient_frame`, iteration body | `b8_gauss_newton` |
| C9 | `hanke_damping`, damping metric and proposal solve | `c9_lm` |
| C10 | `control_step`, spectral projection, certified finite trial | `c10_geometry_trial` |
| C11 | `Objective.refined`, `validate`, `checked_pair` | `c11_trial_evaluation`, with response branches visible in `fit_stage` |
| C12 | accepted damping, callbacks, rebuilds, stopping | `c12_iteration`, with state transitions visible in `fit_stage` |
| Conditions | numerical comparisons throughout the above | `checks`, grouped by subsection and endpoint checks |

## Check inventory

Definitions move; their call timing and consequences do not.

| Quantity | Threshold source | Invocation / timing | Consequence / mode |
|---|---|---|---|
| Positive area, regularity, intersections | Existing zero / speed ratio | A1 geometry; C10 intermediate and final curves | Existing exception; all paths |
| Log-modulus interval and reciprocal residual | Modal settings and existing rounding allowance | A1 before using coefficient expansion | Refuse or recompute interval; modal |
| Radial coefficient decay and omitted tail | `radial_tolerance` | A2 within existing expansion retries | Extend or refuse; modal |
| Graf convergence, source separation, cancellation | Modal settings | A3 before wave contraction | Extend or refuse; modal |
| Finite predictions / Jacobian | Existing finite checks | A4 / B7 immediately after contraction | Existing numerical failure |
| Arclength monotonicity | Existing strict positivity | B6 / C10 before projection | Existing geometry failure |
| Area / increment / full certificate / sampled fallback | Existing certificate constants | C10 at coarse, fine, final-curve points | Preserve tier order, shadow mode and refusal |
| Coarse/fine projection discrepancy | Update `projection_tolerance` | C10 before final candidate validation | Refuse geometry trial |
| Domain containment | Configured `domain_box` | Stage start and C10 before physics | Existing failure / trial refusal |
| Tiny step / repeated proposal | Existing relative tolerance / exact bytes | Before each C10 construction | Skip; repeated-proposal rule is optional |
| Production decrease | Existing strict comparison | C11 before refined evaluation | Ordinary backtracking rejection |
| Field agreement and gain margin | Stage tolerances / optimizer config | C11 after existing refined evaluations | Preserve hard failure, rejection or optional promotion |
| Loss, gradient, relative step, progress | Existing optimizer config | Original C12 points, after required callback/rebuild | Preserve stop reason and precedence |
| Endpoint field, column Jacobian, directional derivative | Existing endpoint tolerances | Initial / requested early / terminal checks | Existing returned qualification |
| Work / wall / stage quota | Existing ledger limits | Existing reserve/dispatch points | Existing stop category |

## Supported branches to retain

Nodal and modal physics; registered geometry updates; ordinary, relaxed and
working-frequency objectives; fixed and responding resolution; qualified modal
controller; stage-local geometry; entry reuse; pause/resume; terminal tangent
omission; all damping modes; both validity orders and shadow checks.

## Completed implementation

All twelve numbered modules contain the running mathematics. The canonical
entry points are `runner.fit` and `fit_stage.fit_stage`. The visible stage loop
uses `J`, `g`, `H_GN`, `D`, `lambda_trial`, `a_raw`, `a_bounded` and `a_used`.
The old module paths are compatibility imports, with no second solver.

`checks.py` contains the primary numerical conditions, coefficient validity
tiers, sampled intersection predicate, and supported optional-path conditions.
`objective.py` owns dispatch and refined caches; `work.py` owns accounting;
`stage_types.py` preserves public fields and historical checkpoint type names.
`endpoint.py` retains the independent endpoint calculations and their batching.

The outer queue, optional resolution responses, callback/rebuild order and
accepted-state commitment remain visible. No algorithm, threshold, schedule,
precision, device choice, default, benchmark input or existing test was changed.

## Comparisons and tests

The retained [comparison report](../../pytest/bem_inverse/data/refactor_comparison.json)
contains exact counts, platform information and test results. The paired
`refactor_baseline_arrays.npz` / `refactor_rewritten_arrays.npz` beside it retain
21 intermediate/endpoint arrays. `refactor_reference.py` can capture either
source tree in a separate process; references came from the original snapshot,
not from two aliases of the new implementation.

- All 17 scalar/control/geometry records match exactly: ordinary refusal,
  promotion, backtracking, exhausted accuracy, failed finer base, pause/resume,
  damping modes, terminal tangent omission, alternate gradient, working-set
  retry, qualified-modal acceptance/refusal, callback stop, quota and wall stop.
- Modal comparison: 17/21 arrays match exactly. Matrix, RHS, receiver rows,
  forward/reciprocal traces, coefficient velocities and finite trial match.
  Differences are at most 1.78e-15 in J, 5.69e-14 in H_GN, and 2.67e-14 in
  endpoint coefficients. All trial statuses, acceptance decisions, callback
  indices, dispatched counts and work charges match.
- Repeating the untouched baseline itself changes J by 1.78e-15 and H_GN by
  2.14e-14 on this arm64 environment. The unchanged validity-order test also
  produces coefficient-byte differences up to 2.52e-17 with identical decisions.
  Bitwise modal equivalence is therefore not claimed; no tolerance was relaxed.
- Initial package suite: 80 passed, 6 failed, 4 skipped. The six failures are
  the existing extended-precision Bessel comparisons; local `longdouble` has
  only 52 mantissa bits.
- Broader retained suites: 162 passed, 10 failed, 15 skipped. One new fixture
  comparison needed JSON list/tuple normalization; its reference numbers and
  solver were unchanged. Corrected control/resolution rerun: 11 passed.
- The other nine failures in that broader run reproduce on the original
  snapshot: the six Bessel cases, validity coefficient equality, and two
  unchanged multicomponent exact-equality tests. A separate nodal resume
  exact-equality failure also reproduces on the baseline and is intermittent.
- After moving optional conditions: similarity, nodal qualification and the
  control/import contract tests give 11 passed, 4 skipped.

## Verification limits and remaining work

No implementation step remains for the A1–C12 refactor. There is no new inverse
campaign or performance claim. The arithmetic, frequency dispatch, factor/cache
reuse and work counts are preserved; full benchmark recovery/runtime was not
remeasured. CUDA is unavailable here, so device arithmetic was not executed.

The comparison exercises optional control hooks with small deterministic
fixtures. It does not qualify every physical relaxed/Gaussian/analytic or
adaptive-controller configuration; their supported paths and decisions remain.
The pre-existing platform precision failures remain unresolved by design.

Baseline documentation discrepancies: the package README says modal response
does not exist, but `pipelines.modal_response` is implemented. It also references
tests and research packages removed by the earlier branch organization.
These are documentation differences, not permission to change solver behavior.
