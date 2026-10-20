# Task: make the canonical inverse solver readable through A1–C12

## 1. Goal — reorganise the real implementation, without changing its job

Refactor the maintained inverse solver in place so that its structure follows the user's mathematical information chain: three main sections, A–C, and twelve subsections, A1–C12.

This is a behaviour-preserving readability refactor. It is NOT an algorithm change, a simplified teaching solver, a new experimental solver, or a new collection of options.

The user wants to understand and edit the code that actually runs. The intended reading path is:

**Outer operation/stage loop → `fit_stage()` → the relevant A1–C12 module → readable mathematical operations.**

The outer loop should expose how stages are selected and executed. `fit_stage()` should expose the actual iteration, damping-retry, backtracking, evaluation, acceptance and stopping sequence. The numbered modules should expose the mathematics. `checks.py` should expose the mathematical/numerical conditions.

The user does not yet have a complete mental model of the implementation. Do not require them to identify every disposable check or explain every dependency before you can start. Establish the dependencies from the code, preserve behaviour, and make that behaviour understandable. Potential deletions and numerical improvements are a separate future task.

**Success is not fewer lines. Success is that the user can follow the calculation and locate the mathematics they want to edit, in the canonical implementation.**

## 2. Read first and establish the current baseline

Read the local `AGENTS.md` and any applicable nested instructions, then:

- `docs/reference/inverse_information_chain.md` — canonical subsection definitions and notation.
- `solvers/bem_inverse/README.md` — maintained package, entry points and relevant tests.
- The actual implementations reached from `runner.fit()` and `continuation/lm_backend.fit_stage()`, including their selected physics, geometry, checks, policies and tests.

The primary readability target is the maintained `modal_muller` + `certified_spectral` path with `CumulativePolicy`, without localization. This does not authorise removing other supported paths or changing the defaults of existing entry points.

Inspect the actual local branch, commit and working-tree changes. The discussion used `feature/shape-frequency-continuation`; do not switch branches just because a document names a default. Do not create a branch/worktree without the approval required by local instructions. Do not reset, discard, overwrite, or silently stash user work.

Record the baseline commit and relevant uncommitted source changes before editing. The current working implementation, including intentional local edits, is the behavioural reference. The information-chain document defines the explanatory structure. If they disagree, report the discrepancy; do not silently repair numerical behaviour during the refactor.

Keep numerical code in the maintained package. Do not introduce runtime dependencies on `experiments/`, saved results, truth geometry, scene IDs, or root research drivers. Preserve reference solvers, frozen snapshots, inputs and historical evidence.

## 3. Non-negotiable refactoring rules

### 3.1 One canonical implementation

Move and clarify the implementation used by the existing entry points. Do not deliver `clean_fit_stage()` or a separate `solver_v2` that the user must later merge back.

Temporary parallel code during a small extraction is acceptable only as an implementation step, not the final architecture. Old import paths may remain as thin compatibility re-exports pointing to the new canonical implementation. The new readable functions must not just delegate the entire job to the old unreadable monolith.

Do not finish with an unintegrated demonstration. Existing callers and relevant tests must exercise the refactored implementation.

### 3.2 Preserve numerical and control-flow behaviour

Do not add, remove, weaken, strengthen, bypass, reorder, or change the frequency of any mathematical check. Do not change its tolerance, default, comparison strictness, failure category, fallback or consequence.

Preserve geometry construction, quadrature, coefficient truncation, normalization, weights, linear algebra, damping, clipping, backtracking, acceptance, stopping, stage progression and optional numerical responses. Do not replace the spectral-refit update with the N-update. Do not change a derivative formula or add a new linear-residual threshold because it seems desirable.

Do not silently fix suspected bugs. Record them separately, with file/function locations. Investigate a refactor-induced difference before changing expectations or tolerances to make it pass.

### 3.3 Expose the algorithm, not an abstraction framework

Keep the actual iteration, damping retries and backtracking visible in `fit_stage()`. Keep stage/operation progression visible in the outer runner. Calls should identify which subsection they execute and which mathematical objects enter and leave.

Do not shorten the function by hiding the entire trial loop inside `process_iteration()`, `run_strategy()`, or another opaque controller. Avoid generic task engines, new plugin systems, decorator-driven numerical control flow, or deep class hierarchies for this task.

Some necessary branches will remain. Group and name them clearly; do not delete optional behaviour to make the common path look short. Do not replace a large nested closure with an equally opaque mutable context containing everything.

### 3.4 The section boundary must lead to real mathematics

Use clearly identifiable modules corresponding to A1–C12, with the labels in module docstrings and call-site comments. The example filenames below express the intended granularity; exact paths may be adjusted to existing package conventions.

Opening a subsection should reveal its actual mathematical operations and meaningful intermediate variables, not a chain of forwarding wrappers. Shared low-level numerical primitives are fine. Do not create a helper for every multiplication or trivial expression.

A subsection may have several functions and may be invoked at several points. The chain describes dependencies, not an instruction to recompute all twelve sections, in strict order, on every retry. In particular, C11 reuses A and B5, and C12 may trigger B6–B8 again at the accepted state.

### 3.5 Explicit mathematical inputs and outputs

Use specific names and concise type/shape/unit documentation at subsection boundaries. Distinguish coefficient arrays, curve objects, forward results, derivative preparation and decision reports.

Prefer a few explicit arguments or small named records with a clear mathematical role. Avoid unstructured dictionaries, positional tuples with many unrelated fields, or `**kwargs` that obscure dependencies. Compatibility wrappers may retain old signatures where needed.

Do not pass the entire optimizer state into a low-level routine that only needs coefficients and a resolution. Do not let checks mutate the optimizer. Keep data ownership, cache scope and accepted-versus-trial state clear.

### 3.6 Preserve execution and bookkeeping, not just the final picture

Preserve cache identity and lifetime, frequency dispatch, CPU/CUDA selection and fallback, batching, array lifetime, and factor reuse. Do not materialize all frequency systems simultaneously merely to make A1–A4 look sequential. Do not recompute the forward solve or Jacobian when the original reused it.

Preserve work charging, actually dispatched solver calls, budgets, callbacks, checkpoint/resume behaviour, output fields and stopping reasons. Charged work and dispatched work are not necessarily the same thing. Separate reporting from mathematics without losing either's behaviour.

Logs and checkpoint packaging may move into focused support functions. They must not conceal a numerical decision. Preserve callback ordering, particularly when a callback can stop fitting. Preserve budget checks at their existing execution points.

### 3.7 Preserve optional paths explicitly

Inventory supported modes reached through the changed functions. Retain resolution promotion, qualified-modal responses, alternate objectives/working-frequency retries, stage-entry reuse, terminal-linearization options, stage-local updates, and pause/resume where the current code supports them.

Do not force these into the example's fixed-resolution path. Organise them in focused, named routines while leaving the calls and state transitions visible. Do not invent a new public API framework to achieve this.

### 3.8 Keep future editing and handoff straightforward

Update `docs/reference/inverse_information_chain.md` with actual new file AND function/class names. Keep the mathematical definitions stable.

Keep one short refactor-status document: baseline, completed moves, current canonical entry points, relevant test/comparison results, unresolved differences, and remaining work. Another local agent should continue from this, rather than inventing another clean solver. Do not create a large collection of process documents.

## 4. Canonical sections and their responsibilities

### A. Stored geometry → predicted measurements

| Section | Inputs → outputs and responsibility |
|---|---|
| **A1. Stored Cartesian Fourier/Laurent geometry** | Stored complex coefficients `c` → frequency-independent coefficient geometry: squared distances, divided differences, logarithmic geometry, speed-weighted normals and reusable wave arrays. Preserve exact geometry/cache identity. |
| **A2. Geometry arrays → modal Müller matrix** | A1 geometry plus exterior/interior wavenumbers at frequency `f` → radial/logarithmic kernel coefficients, Müller blocks and `A_f`. Preserve the existing direct exterior/interior differences and CPU/CUDA implementation. |
| **A3. Geometry + source/receiver positions → modal wave coefficients** | Geometry, frequency and acquisition → incident trace/flux coefficients, receiver-evaluation coefficients and reciprocal RHS. Preserve the existing Graf/addition-theorem construction. |
| **A4. Matrix + source RHS → boundary traces → predicted measurements** | Factor `A_f`, solve for stacked `u_D` and speed-weighted flux `q`, then evaluate receiver measurements. Retain factors, forward traces and reciprocal RHS for B7. Preserve per-frequency dispatch and storage behaviour. |

### B. Predicted measurements + geometry directions → residual Jacobian

| Section | Inputs → outputs and responsibility |
|---|---|
| **B5. Predicted data + observations → normalized real residual** | Predictions and observed data → normalized, weighted, real-stacked residual `r` and loss `Phi = 0.5 * r.T @ r`. Preserve the exact denominator floor, frequency weights and real/imaginary stacking. |
| **B6. Optimizer coordinates → complete-trial geometry derivatives** | Accepted `c`, local coordinates `a`, and update/storage bands → Cartesian coefficient velocities of the COMPLETE finite geometry trial at zero step, plus reusable trial preparation. Preserve the current projected-geometry finite differences where used; do not replace them with raw unit-normal directions. |
| **B7. Geometry derivatives + forward/reciprocal traces → complex data Jacobian** | B6 velocities → normal-displacement weights; existing factors → reciprocal traces; contraction with forward traces → complex data Jacobian. Reuse each frequency's factors and receiver-batched reciprocal solve across update directions. Do not casually replace reciprocity with a conjugate-transpose solve. |
| **B8. Complex data Jacobian → residual Jacobian → Gauss–Newton quantities** | Apply B5's exact normalization and stacking to obtain real `J`; form `g = J.T @ r` and `H_GN = J.T @ J`. Keep these formulas readable. Expose separate functions if preserving existing evaluation timing requires it. |

### C. Jacobian → LM proposal → accepted stored geometry

| Section | Inputs → outputs and responsibility |
|---|---|
| **C9. Gauss–Newton quantities → LM proposal** | Construct damping metric `D`, select trial damping `lam`, and solve `(H_GN + lam * D) a_raw = -g`. Preserve configured metrics, floors, damping rules and linear-solve failure handling. The result is an optimizer-coordinate proposal, NOT stored Cartesian coefficients. |
| **C10. LM proposal → finite geometry trial** | Apply step control and successive halvings; construct normal motion, spectral arclength refit, storage projection and centered increment. Return `c_trial` and the actually applied coordinates when the update modifies them. Call `checks.py` at the original intermediate-curve, refit-convergence and final-candidate locations. |
| **C11. Trial geometry → production/refined evaluation → accept or reject** | Reuse A and B5 to evaluate the trial. Only obtain additional refined evaluations when the existing path requires them. `checks.py` evaluates production decrease, field agreement and gain/margin conditions. Keep ordinary rejection, numerical failure and configured refinement responses distinct and explicit. |
| **C12. Accepted step → damping / stopping / continuation** | Commit the accepted state, update damping/model-agreement records, invoke callbacks, rebuild directions/Jacobian when required, and evaluate existing stopping conditions. Return the accepted endpoint and status to the outer runner. The runner retains policy-driven progression, cleanup/resizing and endpoint checks. |

These are the user's established separations. Do not replace them with an unrelated five-part forward/geometry/optimizer architecture.

### Fixed terminology

`c` / `c_m`: stored complex Cartesian coefficients. `a` / `a_i`: local optimizer amplitudes, in metres for the normal-harmonic path. `c_trial`: the newly constructed stored coefficients. Keep `a_raw`, `a_bounded` and `a_used` distinguishable when relevant.

`M`: update band. `K_geometry`: stored curve band. `K_trace`: physics trace cutoff. Geometry quadrature count and coefficient workspace are additional, distinct resolutions. Preserve existing external resolution tokens and conversions; do not rename them as physical node counts on a modal path.

`A_f`: Müller matrix at one frequency. `u_D`: Dirichlet trace. `q`: speed-weighted normal flux. `r`: normalized real residual. `J`: residual Jacobian. `g`: gradient. `H_GN`: Gauss–Newton matrix. `D`: damping metric. Use `lam` or `lambda_trial` in Python because `lambda` is reserved.

Document whether arrays carry frequency, receiver, source, coefficient or update-coordinate axes. Do not reuse `normal` to mean both a geometric normal and `H_GN`. Preserve public/serialized field names through compatibility mapping when necessary.

## 5. `checks.py`: one discoverable home for mathematical conditions

Put mathematical and numerical checks in one maintained `checks.py`, organised by A1–C12, with a separately labelled endpoint-check section. This includes checks inside lower-level numerical construction, not only the final LM acceptance tests.

Examples include area/orientation, regularity and self-intersection, coefficient certificates and their decisions, arclength monotonicity, refit agreement, geometry-domain containment, expansion/truncation convergence, cancellation limits, solve/prediction qualification, physics-resolution agreement, acceptance margins, and convergence/stagnation conditions.

Ordinary programming guards may stay inline: missing optional objects, empty containers, argument types, or expected array shape. Numerical admissibility and accuracy are not mere programming guards just because they are expressed by a one-line `if`.

Each check must expose its mathematical quantity, comparison formula, threshold source and interpretation. Check-specific calculations belong there; reusable numerical primitives can remain in the relevant mathematical modules. For example, forward solves remain in A; numerical evidence is passed into `checks.py`. Do not hide new forward solves or optimizer mutations in a function presented as a check.

Configuration remains the existing source of configured tolerances. Moving a comparison into `checks.py` does not mean copying its threshold into a second constant. Use explicit arguments and named, inspectable results or the existing appropriate exceptions.

The caller retains the response: continue backtracking, retry damping, promote resolution, stop the stage, or only record information. Preserve exception classes, status/reason strings and precedence where callers depend on them. Low-level checks may raise at their existing point, with the existing higher-level response retained.

**Moving a check's definition does not move when it runs.** C10 must still validate intermediate moved curves before a subsequent calculation that depends on their validity. A final `checks.validate(c_trial)` is not a substitute for all existing checks.

Do not merge distinct checks merely because they use similar formulas. C10's quadrature-refit agreement, C11's physics-resolution agreement, and endpoint derivative checks have different responsibilities. Preserve certificate-first/sampled-first behaviour exactly, including inconclusive certificates and optional shadow diagnostics.

## 6. Approved readability examples — NOT replacement algorithms

The user approved the following style: section-labelled calls, explicit mathematical objects, visible retry loops, and checks separated from the response to their results.

**The existing source is the authority for behaviour. These are non-executable interface sketches, with illustrative names and incomplete arguments. They omit optional paths and some lifecycle detail for display. Never replace the current solver by copying this pseudocode.**

### Section A: an orchestrator that opens directly into A1–A4

```python
# a_forward.py — interface sketch

def evaluate(c, problem, stage, resolution, *, work):
    """A1–A4. Stored coefficients → active-frequency forward results."""

    # A1. Build or retrieve frequency-independent geometry for this workspace.
    geometry = a1_geometry.build_or_reuse(c, resolution, work=work)

    def per_frequency(observation):
        # A2. Geometry + material wavenumbers → A_f.
        A_f = a2_muller.assemble(
            geometry, observation, problem.contrast, resolution, work=work,
        )

        # A3. Geometry + Tx/Rx → source, receiver and reciprocal wave coefficients.
        waves_f = a3_waves.build(
            geometry, observation, resolution, work=work,
        )

        # A4. Factorization → forward traces → receiver predictions.
        # Keep the factors/traces required by B7; discard only as before.
        return a4_fields.solve_and_predict(A_f, waves_f, work=work)

    # Retain the existing dispatch, batching, output order and ownership policy.
    return dispatch_forward(per_frequency, stage.observations, work=work)
```

The forward return value has named fields for the predictions and the per-frequency results needed downstream. A method that only returns data does not satisfy the B7 reuse contract.

### `fit_stage()`: visible A–B–C connections and retry loops

```python
# fit_stage.py — fixed-resolution readability sketch, NOT executable code

def fit_stage(c, problem, stage, settings, *, work, record):
    """Run one stage; retain and return the last accepted state."""

    # A1–A4. Initial forward state, unless existing entry/resume reuse applies.
    current = a_forward.evaluate(
        c, problem, stage, stage.production_resolution, work=work,
    )

    damping = settings.initial_damping
    history = []
    iteration = 0

    while True:
        # B5. Predictions + observations → real residual and loss.
        r, Phi = b5_residual.evaluate(current.prediction, problem, stage)

        # B6. Local update coordinates → complete-trial coefficient velocities.
        space = b6_geometry_derivatives.prepare(c, stage, settings)

        # B7. Forward/reciprocal traces + velocities → complex data Jacobian.
        J_data = b7_data_jacobian.evaluate(current, space, work=work)

        # B8. Complex Jacobian → real J, g and H_GN.
        J, g, H_GN = b8_gauss_newton.evaluate(J_data, r, problem, stage)

        # C12. This call illustrates visibility, not permission to move stop tests.
        reason = checks.stage_exit(Phi, g, history, iteration, stage, settings)
        if reason is not None:
            break

        # C9. Damping matrix and initial damping for this iteration.
        D = c9_lm.damping_matrix(H_GN, space, settings)
        lambda_trial = c9_lm.start_damping(
            damping, J, r, H_GN, D, settings,
        )
        accepted = None

        for damping_attempt in range(settings.max_damping_trials):
            # C9. Solve the damped Gauss–Newton system.
            try:
                a_raw = c9_lm.solve_proposal(g, H_GN, D, lambda_trial)
            except LinearSolveFailure:
                lambda_trial = c9_lm.increase_damping(lambda_trial, settings)
                continue

            # C10. Bound this proposal, then backtrack along it.
            a_bounded = c10_geometry_trial.control_step(a_raw, space, settings)

            for backtrack in range(settings.max_backtracks + 1):
                a_trial = 0.5**backtrack * a_bounded
                if checks.step_too_small(a_trial, space, settings):
                    continue

                # C10. Preserve internal checks and their construction order.
                try:
                    geometry_trial = c10_geometry_trial.build(
                        c, a_trial, space, settings,
                    )
                except GeometryRefused as refusal:
                    record.geometry_refusal(refusal)
                    continue

                c_trial = geometry_trial.c_trial
                a_used = geometry_trial.a_used

                if not checks.inside_domain(c_trial, settings):
                    record.domain_refusal(c_trial)
                    continue

                # C11 reuses A1–A4 and B5; it is not another forward solver.
                trial = a_forward.evaluate(
                    c_trial, problem, stage,
                    stage.production_resolution, work=work,
                )
                _, Phi_trial = b5_residual.evaluate(
                    trial.prediction, problem, stage,
                )
                checks.require_finite_evaluation(trial, Phi_trial)

                if not checks.production_loss_decreased(Phi, Phi_trial):
                    record.nondecreasing_trial(c_trial, Phi_trial)
                    continue

                # C11. Existing refined evaluations, including exact reuse.
                refined_pair = c11_trial_evaluation.refined_pair(
                    current, trial, problem, stage, work=work,
                )
                decision = checks.trial_acceptance(
                    current, trial, refined_pair, stage, settings,
                )
                record.trial(c_trial, geometry_trial, decision)

                if decision.stop_stage:
                    return StageResult(c, current, history, decision.reason)
                if not decision.accepted:
                    continue

                accepted = (c_trial, trial, Phi_trial, a_used)
                break

            if accepted is not None:
                break
            lambda_trial = c9_lm.increase_damping(lambda_trial, settings)

        if accepted is None:
            reason = checks.exhausted_trials_reason(record)
            break

        # C12. Accepted move → next damping and iteration records.
        c_next, next_forward, Phi_next, a_used = accepted
        damping, step_report = c12_iteration.accepted_step(
            Phi, Phi_next, g, H_GN,
            a_raw, a_used, lambda_trial, settings,
        )

        c, current = c_next, next_forward
        history.append(step_report)
        iteration += 1
        record.accepted_state(iteration, c, current, step_report)

    return StageResult(c, current, history, reason)
```

### Mandatory corrections when translating the sketch to real code

The sketch is a layout target, not a complete temporal specification. Preserve the original initial-state callbacks, accepted-state callbacks, checkpoint capture, derivative rebuilding and stopping order. An accepted endpoint may still need its gradient calculated before stopping; other configurations intentionally omit the terminal tangent. Do not introduce either an extra derivative evaluation or an omitted required one.

Preserve the distinction between an ordinary backtracking rejection and a numerical failure. Restore all configured refinement/promotion/restart branches, including retries that do not increment the iteration or reset carried damping. Failed production evaluation must not become an ordinary rejected trial unless that is already the selected behaviour.

Preserve update-adjusted coordinates (`a_used`), model-gain calculations, tiny-step and repeated-proposal handling, and work checks before geometry construction. Record rejected attempts as before, not only accepted ones.

Do not infer data model changes from sketch names such as `stage.production_resolution` or `StageResult(...)`. Adapt the structure to the actual API and preserve public fields and serialized contracts.

### The outer loop must also be readable

Retain the existing operation queue rather than replacing it with a fixed `for stage in stages` if operations can add or modify later stages.

Make queue progression, optional initialization, geometry cleanup/resizing, stage-local settings, `fit_stage()` calls, returned-status handling, noise stopping, frontier/adaptive continuation, and endpoint checks visible as named operations. Do not bury the whole runner in a new generic dispatcher or delete operations absent from the default example.

The outer runner chooses what comes next. `fit_stage()` executes one stage. A1–C12 routines compute their mathematical objects. `checks.py` evaluates mathematical conditions. Recording/checkpoint support preserves execution information.

## 7. Work in small, integrated steps

Start with a concise old-to-new map: A1–C12 → current file/class/function → proposed file/class/function. Add a compact check inventory: quantity, threshold source, call site, timing, failure consequence, and whether always active or optional. This is an implementation aid, not a long research report.

Then implement bounded extractions in the real path. Show the actual refactored outer loop and `fit_stage()` early, so readability can be assessed before every module is moved. Do not stop at producing another skeleton or a plan without integration.

Move check definitions without changing their invocation order. Move the numerical implementation into the corresponding section modules. Keep compatible imports where required, and remove superseded live duplication once its replacement is verified.

Use existing relevant tests and the smallest additional before/after comparisons that distinguish the changed behaviour. Do not launch the full benchmark, new inverse campaigns, a large new test framework, or unrelated experiments just because this is a refactor. Follow local test/runtime instructions. Use small branch-focused tests where they can exercise a failure or optional response without an expensive inverse run.

Before changing a region, capture relevant reference results from the baseline; comparing two aliases that now call the same refactored implementation is not a reference comparison.

Compare, as relevant to the extraction: intermediate arrays, proposed/applied updates, accepted coefficients, losses, accept/reject reasons, resolution changes, stop reasons, solver/reciprocal dispatch counts, work charges, callback sequence and checkpoint/resume behaviour. Similar final pictures are not enough.

For unchanged arithmetic under deterministic execution, expect exact equality first. Explain and investigate differences before permitting any numerical tolerance. Do not move arithmetic, vectorize, alter reduction order, or change precision as an incidental cleanup. CPU/GPU differences and unsupported hardware should be disclosed, not waved away.

Wall-clock-limited runs cannot be required to hit identical endpoints when overhead changes. Preserve their budget semantics; compare numerical behaviour under a nonbinding time allowance and test time-limit behaviour separately with controlled timing where practical. Do not alter production budget rules to force a match.

If a supported path is not exercised, say so and preserve it. Passing a small set of tests establishes only the covered behaviour, not universal equivalence.

## 8. Completion criteria and handoff

The task is complete when the real entry points use the refactored code; the user can read the outer loop and `fit_stage()` as the actual A–B–C algorithm; opening a numbered module reveals its mathematics; and mathematical conditions are discoverable in `checks.py` with their responses visible at the appropriate call sites.

There must be no unexplained behavioural differences, silent feature deletions, unintegrated clean solver, or substantive new wrapper around the old monolith. Preserve existing output and import compatibility where required. Clearly report any unfinished or unverified portions rather than claiming the entire repository is equivalent.

Deliver a short summary with the new canonical entry-point locations, the A1–C12 file/function map, the location of `checks.py`, the relevant comparisons/tests and their results, and any unresolved issues. Keep implementation notes in the one handoff document so another agent can continue the same codebase.

**Start with the current-code map, then refactor the actual implementation. Do not ask the user to design the numerical preservation rules or decide what checks to delete. No deletion of mathematical behaviour is authorised in this task.**
