# SC-041 — qualify atlas decisions against finite updates

2026-09-26. Owner: Codex. Independent reviewer: unassigned.

- **Approval status: APPROVED.** The user's `go` accepts the preceding review
  and its bounded star/kite comparisons. This direct instruction supersedes the
  older named-ID approval wording for this scope. Existing checkout and branch
  only; no branch or worktree creation.
- **Execution status: COMPLETE.** Both screens and all five continuations
  returned; see iteration 23 and the SC-041 completion/audit artifacts.
- **Question:** does local fitting capacity, computed for the complete projected
  update with one physical displacement constraint, predict useful finite progress?
- **Baseline:** SC-040 star endpoint and SC-038 dense final kite endpoint,
  identified by SC-040's `trajectories.json`. Identical saved starts per case.
- **Intervention:** star M=19/22/25; kite M=19/22. K=192 and all 19 frequencies,
  observations, equal weights, ProjectedUpdate, optimizer and tolerances fixed.
  Star uses 512/1024 nodes; kite retains 768/1536. No resolution retry.
- **Scope/API map:** new opt-in `experiments/shape_continuation/action_atlas.py`
  solves a metric-constrained linear least-squares diagnostic and reports a
  conditional remainder bound. New algebraic tests cover coordinate invariance,
  correlated/rank-deficient columns, physical feasibility and the bound. One
  driver in `results/validation/shape_continuation/SC-041-atlas-decisions/`
  reuses SC-035/038's update, objective and fitter. Existing renderer wording is
  corrected to label the old QR scores as heuristic; historical numbers and
  rendered artifacts remain preserved with a dated qualification.
- **Prediction recorded before new solves:** star has almost no local M=19
  decrease, about 95% at M=22 and 99% at M=25; kite has about 90% at M=19 and
  99.8% at M=22. These came from the preceding read-only review. They are local
  predictions on development cases, not a prospective generalization test.

## Stage A: model and finite-step qualification

Rebuild the residual and complete-construction Jacobian from saved traces,
including the update's physical mass metric. Use the full matrix in one
constrained least-squares problem with RMS radius `0.12/k_max` in package
length units. This is a **test radius**, not a proven validity radius. Save
coefficients, spectrum, predicted decrease and physical norm before trials.

Every candidate must pass: stored loss reproduction <=1e-8 relative; fresh
backend residual/Jacobian reproduction <=1e-8 relative; N/2N fields within
the inherited per-frequency tolerances; every Jacobian column refinement
<=1e-3; full-trial central FD at 1e-7 m <=1e-3 relative. The same direction is
used on both grids. No failed direction is replaced.

Probe the diagnostic step at scales 1, 1/2, 1/4, 1/8, stopping at the first
trial with resolved fields, the backend's existing cross-grid acceptance,
actual/predicted decrease >=0.5, and actual decrease >=10% of starting loss.
Record refusals, model remainder and all costs. A case releases Stage B only
if all its candidate derivatives qualify and at least one candidate passes
the finite probe. Truth is absent from qualification, decisions and fitting.
Do not start an inverse from a diagnostic trial.

Stage A caps: **2,000 work units total**, **1,500 seconds per case** (1,000
units each). Retain partial/failing cases and stop them. At most two numerical
workers; one implementation owner; no concurrent source edits.

## Stage B: matched continuation

Run one independent existing-LM stage per arm from the frozen saved endpoint,
with 22 iterations, a 1,500-unit cap and 900-second wall ceiling per arm.
Only `log_model=True` is enabled, to record predictions without changing steps.
Thus maximum new inverse work is **7,500 units**. Use at most two workers;
compare solve work, and do not claim controlled wall-clock superiority.
Hard stops and stage quotas remain distinct from convergence.

Each returned endpoint gets the same N/2N field/Jacobian/FD audit (130-unit,
600-second cap each; total 650). Geometry scoring reads truth only after
fitting and cannot select an iterate. Report RMS, Hausdorff estimate, sampled
minimum curvature radius (8192/16384 points), all-frequency residual, accepted
steps, stop, work, rejected trials and actual/predicted decrease. Reuse audited
fine predictions for residual scoring; no uncounted scoring field solves.
Save accepted-state progress for comparisons at common observed work budgets.

## Decision and limits

- Star supports band release only if qualified released-M continuation beats
  M=19 in both loss and RMS; report whether the forecast gain is realised.
- Kite supports further useful work only with improved loss and RMS; a lower
  loss with unchanged/worse sharp-feature radius does not settle geometry.
- A finite prediction failure narrows the diagnostic; it does not trigger a
  new optimizer, prior, frequency sweep or another experiment.
- This study can qualify a narrow action comparison. It cannot establish a
  general atlas controller, stable resolution frontier or geometric convergence.

Artifacts: frozen source/input hashes, fitting data, diagnostic matrices/steps,
trial measurements, runs, audits and rebuildable summary under the new SC-041
bundle. Results open iteration 23. No solver or production default promotion.
