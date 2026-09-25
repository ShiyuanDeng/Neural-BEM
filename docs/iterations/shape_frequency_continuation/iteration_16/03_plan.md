# SC-036 — matched finite paths (2026-09-25)

Owner: Codex. Independent reviewer: unassigned. Authorized by the user's
2026-09-25 instruction to follow the new brief and continue between iterations
until substantive results or research blockers. Existing checkout only;
`feature/shape-frequency-continuation`, starting at `e28ee3d`. SC-035 remains
reserved for the distinct state-regularization question.

## Decision and reconciliation

Question: does the finite path itself prevent a useful step when the normal
velocity, current shape, Jacobian, data, optimizer and numerical regime agree?
The new high-level brief supersedes RD-3's causal certainty: refusals establish
an obstruction, not that removing it produces reconstruction progress.

Compare `z + h n` with `z + h e_r/(e_r dot n)` at the SAME accepted shape and
SAME arclength-normal LM coefficients. The centre is the current curve's mean
parameter position (no truth input). Restrict rays to star-shaped current
curves with `min(e_r dot n) > 0.05`; require positive new radii. Both paths have
normal velocity h, although their finite shapes differ at second order. Do
not project h into a radial Fourier band. Both use the identical resolved
arclength refit, storage K=192 and relative truncation gate 1e-5. This changes
no state-band regularizer. A non-star current state is an explicit chart
limitation, not a failed normal-method comparison.

API map: add an opt-in update in `finite_paths.py` using `BorgesUpdate`'s
prepare/velocities/metric and the existing `_refit_samples`; a bounded driver
in `finite_path_study.py` reuses `Objective`, `fit_stage` and existing frozen
SC-029 observations/histories. No forward or backend defaults change. Add
actual-trial derivative, circle-equivalence and non-star refusal tests.

## Frozen screen

- Reconstruct stage-1 LM proposals at peanut states 3, 4 and the final accepted
  state; kite state 4; star state 2. Use saved next damping, existing coefficient
  clips, M=3 and the unchanged backend objective. Select states by this rule
  before measuring the new path. Retain missing/chart-refused cases.
- Try step multipliers 1, 1/2, ..., 1/128. Record geometry refusals, projection
  error, radius, physical step, production/refined objective and model error.
  Score all valid trial shapes against truth afterwards, never choose the
  direction, damping or accepted trial by truth.
- Qualify identical first-order velocities to roundoff, actual-trial central
  field differences to relative 1e-3 (refinement/check step sweep on failure),
  and the existing stage field discrepancy bounds. Geometric translations on
  circle, peanut and non-star C distinguish coordinate bandwidth from shape
  complexity; compare low-order arclength/radial spaces with physical L2(ds)
  weights. No arbitrary coefficient singular-value ranking.
- Screen ceiling: 1,800 field/reciprocal units and 45 minutes, qualification
  included; count rejected valid trials and evaluation fields. Save commands,
  source/input hashes, all failures and derivative measurements.

## Conditional complete-inverse comparison

Release only if a qualified ray trial gives at least twice the largest
normal-path actual decrease on one difficult state, AND that trial improves
truth distance (evaluation-only mechanism check). Otherwise close the
finite-path-only claim as unsupported in this screen and use the coordinate
study to choose the next bounded question.

If released: same-start four-stage inversions, normal versus ray update,
peanut/kite/star/C, M=3/5/7/9, same data and backend; each path 8,012 units,
45 minutes, maximum total 20,000 units. Ray mode falls back to the normal path
only where the CURRENT curve is outside the ray chart; trial-specific
refusals do not trigger fallback. Record every use. Compare total inverse
work, stage traces, final truth distances, unseen-catalog prediction (now
explicitly development evaluation), and final numerical agreement. SPD-L is
context; the matched normal arm determines causal attribution.

A useful local path result does not establish an adaptive controller. Keep
conformal mapping conditional; review SC-035's full-construction derivative
and correct its parametrization-speed qualification before any execution.
