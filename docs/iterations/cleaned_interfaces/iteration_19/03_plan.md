# FM-002: corrected relaxed gradient and a four-arm control

2026-10-03. User: "then implement whats left out" after the outsider review.
Existing branch/workspace retained; no branch or worktree creation. FM-001
and all failed evidence remain unchanged. This plan is written before any
FM-002 trajectory is run. No parameter sweep or outcome-based tuning.

## Question

Does relaxation help once its complete reduced-loss gradient is supplied,
and when early damping is varied independently? FM-001's frozen-weight
gradient points almost opposite the true gradient at the saved C warmup.
Its loss values and algebra tests remain valid; its optimization failure
does not close the mathematical idea.

## Implementation and qualification

For each source, minimize `0.5 ||Cq-d||² + lambda/2 ||Aq-b||²` over q.
Recover the minimizing field with the existing LU and receiver adjoints.
Differentiate this objective holding the minimizing field fixed (the
stationarity/envelope identity), including A, b, C, normals, quadrature,
and the shape-dependent median-row-norm penalty. Compose the reverse
geometry covectors with the complete projected-update tangent.

The LM gradient is complete. The old frozen-weight receiver sensitivity is
retained only as a positive curvature approximation, not advertised as an
exact residual Jacobian or exact Hessian. Near/direct kernel branches and
median ordering are fixed locally; the median is only piecewise smooth.
The ordinary objective and its decisions must remain unchanged.

Gates before trajectories:

- Complete-loss finite differences for paired/full, real/damped, multiple
  penalty values and noncircular geometry; relative directional error <=2e-5
  with an absolute 1e-7 allowance for small derivatives.
- Saved high-contrast C warmup: reproduce the old loss/gradient, match the
  complete finite-difference gradient, and accept a decreasing corrected step.
- CPU/CUDA forward-factor paths agree on the corrected derivative; qualify
  a multi-frequency gradient and production/refined gradients on saved states.
- Maintained package, cleaned-interface, shared continuation and lower-level
  numerical regressions pass. Record failures and subsequent fixes.

## Fixed experiment

Three cases, in this order:

1. `modal__c13.3__development_c` (original failure).
2. `modal__c13.3__shifted_star` (previously recovered case lost by FRr).
3. `modal__c4__development_c` (easier control).

The opposite C start is omitted because FM-001 localized both starts to the
same circle; it is not an additional independent shape trajectory.

All arms reuse exactly the same qualified FM-001 full-matrix real/damped
observations and original prescribed starts. Localization always uses the
same damped paired data. Thus "real prefix" does not mean no damping anywhere.

| Arm | Early fitting frequencies | Relaxation |
|---|---|---|
| D0 | damped | off |
| D1 | damped | corrected gradient |
| R0 | real | off |
| R1 | real | corrected gradient |

For D1/R1 the five early penalty values are 3,3,10,30,100 (FM-001).
Frequency sets, shape bands, per-stage iteration/work limits, 13412 global
fit units, 1800-second fit cap, numerical gates and final ordinary real-data
audits remain the baseline settings. Every extra correction/adjoint solve is
charged; reverse assembly is measured in wall time and backend receipts.
Use N512/1024, four frequency threads, sequential cases, CUDA forward solves
when available and CPU reverse geometry assembly. All four arms run on each
selected case, even if an arm fails; no inference from unrun arms.

## Reporting and interpretation

Record ordinary real-data recovery under full and unchanged-paired contracts,
shape errors, per-stage loss/decisions, first numerical obstruction, units,
wall time and gradient qualification. Compare D1 versus D0 and R1 versus R0
to attribute relaxation; compare D0 versus R0 and D1 versus R1 for damping.
No universal smoothing, matched-runtime speedup or all-36 claim follows.

A failed fixed-resolution trajectory remains a numerical obstruction, not
proof of convergence to a wrong stationary point. A corrected-gradient pass
would justify further testing; a fair negative result applies to these
three cases, penalty schedule, curvature model and compute budget.

Bundle: `results/validation/cleaned_interfaces/FM-002/`. Seal numerical
sources, driver, plan and input hashes before the first trajectory. Refuse
changed seals and incomplete-run overwrites. Preserve every attempt.
