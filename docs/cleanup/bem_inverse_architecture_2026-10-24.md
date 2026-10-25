# `bem_inverse` reorganisation after the 2026-10-24 architecture review

Started 2026-10-25. Source: an architecture review of `solvers/bem_inverse/`
at commit `aeedb28ff` (branch `organised`), discussed with the user one
question at a time. User decisions and their reasons also go into
[the decision log](user_decisions.md) (D7, D8). Terms are in
[GLOSSARY.md](../../GLOSSARY.md).

Status: plan final (2026-10-25). Nothing implemented.

## Questions this work answers

1. Can `fit_stage()` read at the level of the target sketch below, with each
   line one step of the A1–C12 chain?
2. Which code can go without changing the default pipeline's mathematics?
3. How does TG-002 behave once the fit judges every curve at its working
   resolution only (D7)?

## Review cards and their status

| Card | Proposal | Status |
|---|---|---|
| A | Delete unreachable research code and its hooks | Decided: delete (step 1) |
| B | One resolution-response module | Dropped: D7 removes promotion |
| C | One route from a curve to its evaluation | Replaced by Q13: delete `Objective` (step 2) |
| D | One file per forward solver, owning its context | Step 3; follows Q3 |
| E | `Ledger.calls` as the only way to charge work | Step 3; provisional (Q4) |
| F | Delete pass-through shims and forwarders | Decided (step 1) |
| G | Move optional-method checks out of `checks.py` | Decided: Gaussian and similarity only (step 3) |
| H | Merge two-resolution comparisons | Dropped: D7 removes nodal selection |

## Decided

- **D7. No finer re-evaluations in the fit.** Remove C11 refined solves, the
  two-resolution gain test and field agreement; resolution promotion;
  nodal stage selection; localization's two-resolution qualification.
- **Q10.** The endpoint audit moves to `experiments/benchmark/` and runs after
  `fit()` returns. Same numbers, same TG-002 recovery rule.
- **Q11.** A trial curve is accepted when its loss is lower than the current
  loss. The acceptance margin goes. No stall test is added.
- **Q12.** The geometry update keeps only its N-point refit.
- **Q13.** `Objective` and `WorkingObjective` are deleted; `fit_stage()` uses
  local `evaluate` and `linearize` steps.
- **Q1.** A minimalist root `GLOSSARY.md`; decisions in the decision log;
  no ADRs.
- **Q2.** Card A code is deleted, not moved.
- **Q3 (provisional).** `fit_stage()` takes `geometry_update` and
  `forward_solve` functions chosen in `pipelines.py`. Revisit after step 3.
- **Q4 (provisional).** Card E as proposed. Revisit after step 3.
- **Q5, Q6.** Shims go in the package and in `experiments/`; class module
  overrides go; one old-name map in `experiments/trial_curves/cache.py`.
- **Q7.** Gaussian and similarity checks move to their method files.
- **Q9.** Three small fixes (below).
- **Q14.** Steps 1, 2 and 3 stay separate, so steps 1 and 3 can be checked
  for identical numbers.
- **Q15.** One full TG-002 run after step 2, budget unchanged at 13,412 work
  units.
- **Q16.** The glossary term is "trial curve"; "candidate" is avoided.
- **Q17.** The optional `agreement` damping keeps its two progress exits
  (`insufficient_progress`, `shortened_stagnation`).

## Plan

Three code steps, ordered so that each pure reorganisation can be checked
bit for bit against saved results. Only step 2 changes numbers.

### Step 1 — delete code nothing runs (OBVIOUS; default unchanged)

**Card A.** Delete `four_control_policy.py`, `four_control_adaptive.py`,
`modal_accuracy.py`, `full_matrix.py`, `relaxed_gradient.py`, `n_update.py`;
`fit_stage.run_policy` and `FixedSchedule`; `continuation/forward.Work`.
Remove their hooks: every `qualified_controller` branch and
`adopt_qualification` in `fit_stage.py`; `qualify_candidate`,
`qualify_linearization`, `respond_resolution_failure` and `relaxation_*` in
`physics.py`; the relaxed-objective, adaptive-slot and controller branches in
`runner.py`. Remove the matching fakes in `pytest/bem_inverse/refactor_reference.py`
and their entries in `data/refactor_control_reference.json`.

**Working-frequency objective (Q13).** Delete `working_frequency.py`, the
`working_frequencies` policy (`policies.py:121`), `working_anchors`
(`policy.py:74`), its branch in `runner.py:272-279`, the `hasattr(objective, …)`
branches in `fit_stage.py`, and the four `working_*` checks.

**Card F.** Point every importer at the real module, then delete the 16
top-level shims, `continuation/{globalization,lm_backend,updates,validation}.py`,
the ten shims in `experiments/`, `trial()` on the method classes, uncalled
forwarders, and the re-exports at `fit_stage.py:29-35`. Change
`experiments/benchmark/cleaned_interface/benchmark.py:22-31`. Delete the
`__module__` overrides (`stage_types.py:266-268`, `work.py:130`,
`errors.py:53-54`) and the alias test (`test_refactor_contract.py:14-31`).
Add the old-name map for `results/trial_curves/aphex_c13.3.pkl` in
`experiments/trial_curves/cache.py`.

**Q9.** Fix the message at `physics.py:97-99`; rename the runner's
`checkpoint` closure to `accepted_state`; remove unused imports in
`runner.py` and the second `checks` import in `fit_stage.py`.

**Check.** `python3 -m pytest pytest/bem_inverse -q`, then rerun one TG-002
case and compare its accepted curves and work units with the saved
`results/validation/cleaned_interfaces/PC-001/M1` case. Use a case that ends
before the wall-clock limit. Expect identical numbers.

### Step 2 — remove finer re-evaluations (DECISION; numbers change)

**C11 (D7, Q11).** In `fit_stage.py` delete `validate`, `qualified_base`,
`finer_objective`, `promote`, `_PromoteBase` and `resolution_events`.
Acceptance becomes "trial loss lower than current loss". Delete
`c11_trial_evaluation.py`; in `checks.py` delete `resolution_check`,
`acceptance`, `fields_agree`, `fields_unresolved`. In `BackendConfig` and
`policy.py` delete `acceptance_absolute_margin`, `acceptance_relative_margin`,
`cross_resolution_factor`, `resolution_gate`, and the policy that sets
`resolution_gate='decision'` (`policies.py:114`).

**Promotion.** Delete `ResolutionResponse`, the `resolution_response`
argument of `fit_stage()` and `fit()`, its plumbing in `runner.py`, the
`resolution_response` field and function in `pipelines.py`, the
`modal_response` pipeline, and the `resolution_response` policy
(`policies.py:138`). `nodal_fixed` keeps sampled spectral geometry without
promotion. Trim `test_resolution_resume.py` to what remains.

**Geometry update (Q12).** In `spectral.py`, `analytic_spectral.py`,
`certified_spectral.py` and `gaussian_lipschitz.py`, drop the 2N-point grid,
`fine_base_projection`, the second refit, `require_projection_agreement` /
`unresolved_gaussian_projection` and `projection_tolerance`. Trial records
lose `projection_error` and `projection_relative`.

**Nodal stage selection.** Delete `nodal_resolution.py`,
`physics.select_stage` and its call at `runner.py:222`.

**Localization.** Delete the two-resolution qualification in
`localization.py:70-83`; localization keeps its first candidate.

**Endpoint audit (Q10).** Move `endpoint.py` to
`experiments/benchmark/audit.py`. `runner.py` drops the initial audit, early
audits, `audit_adapter`, `required_accuracy` and `RequiredAccuracyReached`.
`fit()` returns its final stage and settings; `campaign.py` runs the audit
after `fit()` and records `final_audit_passed` as today. The audit takes its
resolution pair from `physics.resolution_profile()` and builds its own
tolerances (as `endpoint.py:47` does now). `audit_seconds` and
`audit_aggregate_seconds` move to the benchmark contract.

**Stage data.** `FitStage` loses `refined_nodes` and
`discrepancy_tolerances`; `StageEntry` loses `refined_prediction`.

**Objective (Q13).** Delete `objective.py`. `fit_stage()` gets `evaluate`
(A1–A4 via `solve_frequencies`, then `b5_residual.evaluate`) and `linearize`
(B6 `update.prepare`, B7 derivatives through `ledger.calls`, B8
`residual_jacobian` and `gradient`). Stage-entry reuse becomes one `if`.

**Check.** Update the tests for removed paths and run
`python3 -m pytest pytest/bem_inverse -q`. Then the TG-002 run (see Runs);
its saved results become the reference for step 3.

### Step 3 — one route to each piece (OBVIOUS against step 2)

**Q3 / D6.** `fit_stage(..., geometry_update, forward_solve)`; `pipelines.py`
picks both next to the objects it builds. Delete `bind_geometry_update` and
`bind_forward_solve`. Change `runner.py`, `experiments/benchmark/audit.py`
and `experiments/trial_curves/replay.py`.

**Card D.** Move `NodalKress` from `physics.py` to
`forward_solvers/nodal_kress.py`. Each forward-solver file owns its context,
forward solve, derivative and resolution profile; `physics.py` keeps
`Execution`, the registry and the protocol. Replace the `physics.evaluate()`
route (frontier, localization, audit) with the forward solve. Write the
shared `_record` / `ordered_calls` helpers once. The import cycle goes.

**Card E (Q4).** Every charged solve goes through `Ledger.calls`:
`forward_batch.py` (no `ledger._lock`), the runner's frontier step,
`localization.py`. The strict-dispatch rule moves inside `Ledger`. Delete
`endpoint_scope`. `test_resolution_resume.py` uses `Ledger.restore`.

**Card G (Q7).** Move the Gaussian checks to `gaussian_lipschitz.py` and the
similarity checks to `similarity.py`.

**Check.** `python3 -m pytest pytest/bem_inverse -q`, then rerun the step 1
case and compare with its saved step-2 result. Expect identical numbers.
Then review Q3 and Q4 with the user.

### Step 4 — documents

Update the chain map (C11 text, the reading section, the B6 and C11 rows),
`solvers/bem_inverse/README.md`, `experiments/benchmark/README.md` (audit
location, pipeline list), `GLOSSARY.md` and this file's status.

### Runs

One TG-002 case after step 1, the TG-002 run after step 2, one case after
step 3.

The step-2 run is the full benchmark (10 scenes × 3 contrasts, default
`modal_fixed`, `--localization none`) with the unchanged 13,412-unit budget.
It gets a pre-registered plan in `docs/iterations/` and is compared with
PC-001 M1. It answers question 3.

## Expected result

- `fit_stage.py`: about 640 lines → my estimate 300; nested helpers 10 → 4
  (`evaluate`, `linearize`, `record`, `capture`); 13 objective type or
  attribute checks → 0; no exception used for control flow.
- About 20 classes leave the package (85 → about 65), including
  `Objective`, `WorkingObjective`, `ResolutionResponse`, `_PromoteBase`,
  `FixedSchedule` and the research classes.
- Top-level modules 61 → about 35; `continuation/` keeps its three real
  modules.
- One route each to a forward solve, a geometry update, a work charge and a
  module name.
- Not addressed: `runner.py` length, the policy registry, and trial-record
  bookkeeping inside the loop (kept under D2).

## Open

None before implementation. Q3 and Q4 are reviewed with the user after
step 3.

## Target sketch of `fit_stage()`

`resume` and `pause_after` checkpointing, trial records and observers are
kept but not shown.

```python
def fit_stage(curve, stage, contrast, update, config, ledger, *,
              geometry_update, forward_solve,        # chosen once in pipelines.py (Q3)
              on_accept=None, resume=None, pause_after=None, entry=None, retain_final=False):
    observed = stack(stage.observations)

    def evaluate(curve):                                           # A1–A4 → B5
        prediction, forwards = solve_frequencies(curve, stage.observations, contrast,
                                                 stage.nodes, forward_solve, ledger)
        return b5_residual.evaluate(curve, prediction, forwards, observed,
                                    stage.weights, config.residual_floor)

    def linearize(evaluation):                                     # B6–B8
        space = update.prepare(evaluation.curve, stage.update_modes, stage.curve_modes)
        J = residual_jacobian(evaluation.forwards, update, space, observed, stage.weights)
        return space, J, gradient(J, evaluation.residual)

    current = entry.evaluation if entry matches curve else evaluate(curve)
    on_accept(0, current)
    space, J, g = linearize(current)
    record(0); test loss and gradient limits

    while iteration < stage.iterations and not converged:
        H_GN = curvature(J); D = damping_matrix(...); lambda_trial = starting_damping(...)  # B8, C9
        for retry in range(config.max_damping_trials):                                  # C9 retry
            a_bounded = control_step(solve_proposal(g, H_GN, D, lambda_trial), ...)
            for backtrack in range(config.max_backtracks + 1):                          # backtracking
                a_used = 0.5**backtrack * a_bounded
                c_trial, info = geometry_update(a_used, prepared=space)   # N-point refit; refused → halve
                if c_trial is outside the domain: halve
                trial = evaluate(c_trial)                                               # A1–A4 → B5
                if trial.loss >= current.loss: halve                                    # C11
                accepted = trial; break
            if nothing accepted: lambda_trial *= damping_increase
        if nothing accepted: stop "no_decreasing_step"
        current = accepted                                                              # C12
        damping = next_damping(...); on_accept(iteration, current)
        space, J, g = linearize(current); record(iteration); capture()
        stop if the loss or gradient is below tolerance or the step is too small
    return StageResult(...)
```
