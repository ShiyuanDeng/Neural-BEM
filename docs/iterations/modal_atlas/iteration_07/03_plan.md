# The three questions this study must answer

1. **What is the effective useful upper bound of each control — F, M, K, and K_u — beyond which our continuation policy gains nothing material?**
2. **What does each control influence, and through what mechanism? Explain the answer in plain language that someone unfamiliar with the method can understand.**
3. **Given those limits and mechanisms, how should we combine the four controls into a continuation policy?**

**The atlas is a required scientific output. Retain the raw information needed to explain successes, failures, numerical limitations, and interactions; plots and aggregate scores alone are insufficient.**

# MA-007 — Useful continuation limits, mechanisms, and trajectory atlas

Date: 2026-10-13.

Approval status: **PROPOSED — NOT APPROVED FOR EXECUTION**. The current user request is to write this implementation-ready plan. Execution status: **NOT STARTED**. No numerical experiment was run while preparing this document.

Revision, 2026-10-13 (before approval, after review):

- The recording contract now retains the trajectory, data-space evidence, and bounded operator snapshots (sections 8 and 10). It no longer stores every operator and all-direction dense derivatives, which needed about 0.5 TB per fit even at the smallest cutoff, against about 179 GiB free.
- Section 7.2 adds a no-gain bound that can be measured on failing runs.
- Every research rung now ends by a plain progress exit (section 5.2), and rungs identical to the previous one are skipped. Phase C, formerly sixteen cap combinations on one scene under one stop rule, is now a comparison of rung-exit rules.
- Section 7.3 adds F decision rules.
- The retention route for raw arrays is a user decision (section 10).

A subsequent user instruction to implement/run this work authorizes all conditional stages below; it need not name MA-007. The current AGENTS.md supersedes the older experiment-ID approval wording in the shared iteration documents. Do not seek another approval at each conditional stage. Branch or worktree creation still requires specific, direct user approval.

This document owns the scientific choices. The executing agent may choose APIs, array layouts within the schema, batching, and exact implementation techniques. It may not select different scenes, objectives, thresholds, intervention levels, atlas coverage, or favorable results. Explicit unresolved/resource outcomes below are valid closeouts, not permission to improvise another study.

## 1. Deliverable and interpretation

Produce an evidence-backed answer to all three questions, in that order. The answer must distinguish:

- **Catalog limit:** the measurements available to this experiment end at 2.5 GHz.
- **Local numerical saturation:** increasing K or K_u changes neither the calculation nor the relevant move materially at a named boundary.
- **Local information saturation:** additional frequencies/update directions reveal no material additional usable information at a named boundary.
- **No-gain bound:** raising the cap beyond a named value changes neither the outcome class, the first obstruction, nor the endpoint materially, where the larger caps were actually exercised (section 7.2A). On failing runs it is conditional on that failure.
- **Recovery-sufficient cap:** a complete capped fit recovers the scene, and larger checked caps establish the operational plateau defined in section 7.2B.
- **Unresolved limit:** the tested range, numerical qualification, effective intervention exposure, or budget was insufficient.

A configured maximum is not a measured useful upper bound. Identical results at caps that were never binding or exercised establish nothing. Identical failures at exercised caps establish a no-gain bound conditional on that failure, not a recovery-sufficient ceiling. Numerical saturation at an incorrect shape does not establish successful reconstruction. A result on this one development scene does not establish a benchmark-wide policy.

The final answer should include a four-row bound table. For each control it gives the no-gain bound and the recovery-sufficient ceiling, with numerical intervals, exposure, conditioning information, evidence references, and an explicit "not established" where appropriate. Also provide a plain-language account of each limiting mechanism and a concrete recommended schedule or a documented reason no schedule can yet be recommended.

## 2. Fixed scope, inputs, and ownership

### 2.1 Exactly one scene

- Use only TG-002 case **hook__c13.3**.
- Start every full fit from the sealed 65 mm circle centered at (0.5, 0.5) m.
- Use all existing acquisition metadata unchanged: 24 paired source/receiver measurements; the frozen 19-frequency catalog 0.25, 0.375, ..., 2.5 GHz; real and gamma=0.25 damped observations.
- Physics: modal_muller. Geometry update: certified_spectral. Localization: none. Material and physical units remain those of the sealed Problem.
- No grid search, alternative start, far-start case, truth initialization, new noise draw, new frequency, new damping value, contrast change, or replacement scene.
- Historical cases may be read as evidence but must not be rerun. Numerical probes and derivative qualification in this study use only the initial curve, actual accepted states, or actual proposed moves of this selected scene.
- The known hook truth band must not enter any controller, cap selector, or initialization. Truth is accessed only after a numerical run/probe returns for the existing geometric scoring.

Read [the benchmark contract](../../../../experiments/benchmark/README.md) before implementation. Do not regenerate its sealed inputs.

### 2.2 Repository and execution

- Work in the existing /home/drdeng/Neural_SDF_BEM_AD checkout. At authoring, HEAD is on feature/shape-frequency-continuation. Do not create or switch branches/worktrees as part of this plan.
- Preserve unrelated work. At authoring, NG-004 files and test_coefficient_geometry.py are already modified/untracked; they do not belong to MA-007. Record actual status again at execution.
- Maintained implementation belongs in solvers/bem_inverse/. Scene selection, scoring, study orchestration, and reports belong in experiments/benchmark/.
- Proposed driver: experiments/benchmark/ma007.py, with a separate read-only ma007_report.py if needed. Do not create a second optimizer or duplicate the modal forward solver.
- Evidence root: results/validation/modal_atlas/MA-007/. Fresh immutable directory per configuration/attempt. Resume only an exact interrupted configuration with validated checkpoint/source identity.
- Use the existing EMNerf environment, CUDA explicitly, four frequency threads, audit_frequency_batch=2, one worker, and OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1. No simultaneous fit/atlas GPU workers.
- Use the existing compute/source coordination locks under /tmp/neural-sdf-bem-ad-coordination. A source hash change invalidates the affected prepared comparison; preserve it, repair, reseal, and rerun the matched comparison.

### 2.3 What the controls mean

| Control | Plain-language meaning | What it cannot do |
|---|---|---|
| F | Which wave measurements the optimizer uses; higher frequencies can reveal finer detail. | More frequency labels do not create measurements beyond the frozen catalog. |
| M | How detailed a change the outline may make in one step. | Extra directions cannot create information or fix inaccurate sensitivities. |
| K | How much detail the stored outline retains after its update and reparameterization. | Extra storage does not by itself produce useful shape detail. |
| K_u | How accurately the boundary wavefields and their consequences are calculated. | More accurate calculation does not add measurements or release shape directions. |

K_u is called K_trace in current code. Physical damping gamma and LM regularization lambda are not study factors.

## 3. Fixed comparison contract

### 3.1 Primary fit budget and accounting

Every primary full fit uses:

- 13,412 fitting work units and 120 seconds of fitting computation.
- 30 seconds aggregate initial/early/terminal audit computation, with 10 seconds reserved for the terminal audit; 30 seconds individual audit ceiling.
- Existing stage validity, absolute field agreement, step bounds, line search, and backend stopping tolerances.
- The DP-001 feedback options: required_accuracy=.003, damping_rule=agreement, avoid_terminal_linearization=True, log_model=True. Keep optimizer initial regularization, Marquardt metric, clipping, and all other BackendConfig defaults.
- Every online controller probe, candidate resolution selection, and speculative branch counts against the fitting budget. No free online atlas or uncharged adaptive search.

Raw-output capture and file I/O must be timed separately from numerical fitting computation, with the ledger suspended only around pure serialization. Additional atlas calculations are performed after the primary fit from immutable saved states; they cannot modify the original fit or its decisions. Report fitting compute, audits, recording I/O, offline atlas compute, and total elapsed time separately. Never call fit-only time end-to-end runtime.

Do not start a batch that exceeds a known remaining work allowance. Save before a resource limit. An in-flight indivisible solve that crosses a wall deadline is reported as an overrun, followed by termination of further fitting work.

### 3.2 Common measurement of progress

For every scored checkpoint, compute the common merit

    L_real = (1/2) * (1/19) * sum_f ||prediction_f - data_f||^2 / max(||data_f||^2, floor^2)

using the existing lm_backend normalization/floor implementation, not a parallel normalization formula. Save its exact assembled real residual vector, weights, complex residuals, and maximum per-frequency relative residual.

This monitor always uses all 19 real frequencies. It is an evaluation metric, not extra fitted data. Cap and fixed-order arms may not consult omitted-frequency measurements to choose moves. Their terminal recovery audit uses them, as the benchmark requires. The adaptive arm explicitly uses this full-real monitor and must be described as using the full catalog for selection; it cannot support a claim of reduced data access.

For active subset objectives use equal frequency weights summing to one. Losses from different subsets/catalog kinds are not directly comparable.

The common monitor is an independent evaluation: use K_u=320 and its 352 witness, at the epoch's common workspace, for all 19 real frequencies. Both must pass the field thresholds below. Save both losses. Monitor solves may exceed an arm's production cap, but cannot provide its production fields, Jacobian, or moves. A failed monitor is MONITOR_UNRESOLVED, never a valid policy-selection score. In O8, useful/not-useful classification and winning candidate must agree at both monitor cutoffs; otherwise retain the base and record MONITOR_SELECTION_UNRESOLVED for that slot. Fixed-arm offline monitors are separately charged offline work; every O8 monitor is charged online work.

### 3.3 Recovery and sufficient numerical accuracy

Recovery requires all original TG-002 conditions:

1. Independent numerical endpoint audit passes.
2. Boundary RMS <=1 mm.
3. Hausdorff upper bound <=2 mm.
4. Every real-frequency relative residual <=0.003.

Use the existing campaign scoring implementations. Do not select a best-truth iterate instead of the returned endpoint.

Numerical qualification retains these thresholds:

| Quantity | Threshold |
|---|---:|
| Production/refined field discrepancy at each f<=0.5 GHz | <=1e-5 |
| Production/refined field discrepancy at each higher f | <=1e-7 |
| Complete-trial normalized Jacobian, every column | <=1e-3 |
| Complete-trial centered finite-difference check | <=1e-3; optimizer-coordinate increment 1e-7 m, seed 42001 |

Use the existing audit definitions of relative column error, including zero/weak-column treatment. Save both arrays, normalization denominators, and error values.

For comparison of two physical moves at the same base, require BOTH inequalities in each row:

| Error | Relative condition with near-zero floor | Absolute ceiling |
|---|---:|---:|
| RMS difference | <=max(1e-6 m, .01 * reference RMS move) | <=1e-5 m |
| Maximum difference | <=max(5e-6 m, .01 * reference maximum move) | <=5e-5 m |

These are preregistered discrimination tolerances, not physical constants. Compare actual physical displacement fields with a common base parameterization. Also record the existing certified Hausdorff upper bound between the two resulting boundaries as a diagnostic; it adds no separate equivalence gate. Resolve the diagnostic quadrature by doubling until its reported displacement differences change by <=1e-7 m RMS and <=5e-7 m maximum; ceiling 65,536 points, otherwise mark the comparison unresolved. Save coordinate increments and resulting physical RMS amplitudes separately.

## 4. Necessary implementation boundary: make the controls independent

Before drawing any mechanism conclusion:

1. F chooses actual Observation objects; M chooses the normal-update space; K chooses geometry storage; K_u explicitly chooses the modal trace cutoff.
2. Changing K must not implicitly change K_u. Changing M must not silently change K or F.
3. The existing modal token 8*K_u inherits a nodal guard requiring token>2*K. Give the experimental modal path a backend-appropriate validation route. Preserve nodal guards. A token-interface failure is an implementation defect, not physical evidence.
4. Expose intermediate coefficient workspace B_work separately. It is numerical assembly accuracy, not a fifth experimental control.
5. Research-arm workspace is fixed at B_work=512 for the initial matrix, including K_u comparisons. Independently check against B_work=768 at the first actual state of each fit, each atlas checkpoint, and any unresolved calculation. A workspace check must hold F, geometry, M, K, and K_u fixed.
6. If 512/768 fails field/Jacobian/step agreement, compare 768/1024. If that passes, restart the complete still-required research comparison matrix at B_work=768 under a new workspace epoch; retain all previous attempts. Only one such common epoch promotion is allowed. If 768/1024 fails, close with WORKSPACE_UNRESOLVED. Do not diagnose a K_u mechanism using unequal/unqualified workspaces.
7. Keep all other radial/log/Graf tolerances at current ModalSettings defaults. Their failures remain separately classified.
8. Do not impose K=2M+2 as a theorem or silently clamp M. High-M/small-K combinations may project away directions; record the complete tangent/rank loss and actual validity outcome. They are part of the interaction question.

The workspace checks can be collected offline from saved states for the fixed-cap fits; a subsequently failed workspace check disqualifies the affected epoch and invokes the fixed restart rule. Online adaptive branches must qualify their workspace before being selected.

## 5. Exact research schedules and cap ladders

### 5.1 Historical control C0

Run the named feedback policy with modal_fixed, its current executable stage sequence, and the contract in section 3. Retain its implicit K-to-K_u mapping. This reproduces the actual failing recipe. The historical DP-001 record is context, not the fresh timing control.

C0 differs from research arms in several explicitly declared schedule details. Its comparison measures the complete recipe difference; single-control attribution comes from comparisons within the research matrix.

### 5.2 Common initialization and nominal schedule S0

Every research full fit starts independently from the same sealed circle. Use the existing 0.25 GHz damped M=1/K=4 warm-up with a backstop of 44 iterations and 600 work units under the rung-exit rule below, and nominal K_u=64 subject to the assigned cap and the qualification rule below. Do not share a prefix that has used frequencies above another arm's cap.

The subsequent common nominal sequence is:

| Slot | Maximum fitted frequency, GHz | M | K | Catalog |
|---:|---:|---:|---:|---|
| 1 | 0.5 | 3 | 8 | damped |
| 2 | 0.75 | 5 | 12 | damped |
| 3 | 1.0 | 7 | 16 | damped |
| 4 | 1.25 | 9 | 20 | damped |
| bridge | same as slot 4 | same | same | real |
| 5 | 1.5 | 11 | 24 | real |
| 6 | 1.75 | 19 | 40 | real |
| 7 | 2.0 | 37 | 96 | real |
| 8 | 2.5 | 95 | 192 | real |
| terminal | current generous target G_F, capped per arm | G_M, capped per arm | G_K, capped per arm | real |

F means all supplied frequencies <=the stated maximum, including 0.25 GHz. This deliberately differs from the historical four-anchor prefix and is identical across research-cap arms. Slots 1–4 are always damped and slots 5 onward real. The bridge always occurs after slot 4, independent of which controls have advanced. No intermediate/new gamma is introduced.

For cap studies, replace nominal F/M/K by min(nominal, assigned cap). Skip any rung whose resolved settings (active frequencies, catalog, M, K, and K_u floor) equal those of the previous rung; record it as SKIPPED_IDENTICAL. It uses no work. K grows by exact zero-padding; no stage-entry crop, cleanup, or re-fit of the accepted boundary. The update itself remains the selected centered certified spectral map.

**Rung-exit rule.** It applies to the warm-up, every numbered slot, the bridge, and the terminal slot of every research arm. A rung ends at the first of:

1. the existing convergence tolerances (loss, gradient, relative step) or the required-accuracy exit;
2. stall: no decreasing step remains under the existing refusal/backtracking logic;
3. **progress exit:** the rung's own active loss improves by less than 1% over its last 5 accepted iterations, (L[i-5]-L[i])/L[i-5] < .01, whatever the step lengths. This is a new plain option; the existing shortened_stagnation stop also requires at least 3 of the 5 steps to be shortened;
4. backstop: 60 iterations or 3,000 work units for a numbered slot or the bridge, 44 iterations or 600 units for the warm-up, and the remaining global budget for the terminal slot;
5. global work/time exhaustion, which stops the fit.

Record which condition ended each rung. A rung ended by the backstop while still improving by at least 1% per 5 iterations is BACKSTOP_WHILE_PROGRESSING. Numerical/geometry failure follows the existing refusal/backtracking logic and the resolution rule below. No frontier-dependent extra stages in S0.

Evidence for this rule: replayed on the 244 recorded rungs of DP-001 F (1,567 iterations), it ends 53 rungs early and removes 226 iterations. After its exit point the recorded runs removed at most 12.9% more loss (cog c0.5, damped stage 2), and about 0.1% or less elsewhere except cog c13.3 (6.8%). Hook's undamped return used all 22 iterations while still improving by more than 1% per 5, so the old 22-iteration limit cut a progressing rung. Phase C tests the rule on this scene.

Initialize LM regularization at the existing BackendConfig default on entry to each stage/bridge/terminal slot. Within a stage, preserve the ordinary carried controller state. Resolution comparisons and speculative branches begin from identical copies of that carried state; none receives a favorable reset. Record the resolved default value in the manifest.

Research K_u starts at 64 and is carried monotonically forward. It is selected from 64, 96, 128, 160, 192, 256, 320. At each new accepted-state linearization and when a candidate fails the field gate, compare the current cutoff with the next 32 modes, holding B_work fixed. Check fields, complete Jacobian, and the first bounded LM proposal at identical carried lambda/controller state. For the eventual accepted candidate also check the physical move and accept/refuse decision. If insufficient, advance to the next production ladder entry and re-solve.

In a hard-cap arm, production K_u may never exceed its assigned cap. A larger solve may witness failure but cannot supply the accepted production result. At the cap, reject the offending trial and continue the same bounded backtracking; if no qualified candidate remains, return KU_CAP_UNRESOLVED. If the base itself cannot be qualified, stop immediately. Existing validity/assembly exceptions are retained distinctly.

For a declared local K_u saturation result, require confirmation at both K_u+32 and K_u+64; these witness solves do not change the production cap. The largest witness cutoff is 384 when production is 320. If a witness is unresolved, saturation is unproved.

### 5.3 Initial and extension levels

| Axis | Initial cap levels (low, middle, generous) | Ordered extension levels |
|---|---|---|
| F, GHz | 1.0, 1.5, 2.5 | 1.25, 1.75, 2.0, 2.25, used in increasing order where an interval needs filling; never exceed 2.5 |
| M | 19, 37, 95 | 49, 61, 79 for interval filling; 127 above 95 |
| K | 32, 64, 192 | 96, 128 for interval filling; 256, 384 above 192 |
| K_u | 64, 128, 192 | 96, 160 for interval filling; 256, 320 above 192 |

Initial generous vector G=(2.5 GHz,95,192,192). Its values are exploration limits, not prior claims of sufficiency. Values >the last nominal S0 level are reached in the terminal slot; log that distinction.

After the nine initial fits and their required section 7.1 mechanism probes, process axes in F,M,K,K_u order. At most TWO new extension configurations per axis, eight total; keep an immutable dispatch queue. Apply these rules in order:

1. If a recovery-sufficient ceiling is already established for this axis, add no extension.
2. Otherwise, if any tested level recovers, let c be the smallest recovered level. Let b be the largest tested lower level, or the smallest initial level if none is lower. Run the smallest untested listed extension strictly between b and c. If none exists, run the smallest untested listed extension above c, to obtain plateau witnesses. Repeat the rule once after its result; a failed intermediate level updates b. Do not extend beyond the listed range.
3. If no level recovers, an above-maximum extension is allowed only when the largest tested cap was reached AND either (a) its first resolution refusal is explicitly a K-storage or K_u-cutoff failure supported by the corresponding fixed-state comparison, or (b) the section 7.1 next-level probe at its returned endpoint is QUALIFIED_USEFUL or QUALIFIED_NUMERICAL_RESCUE. The probe must change this axis alone. For M, also require p_new>.01 for a useful-information justification. Run the smallest listed untested level above the maximum. A failed geometry proposal, wrong endpoint, or unqualified Jacobian alone does not satisfy this rule.
4. Otherwise record EXTENSION_NOT_TRIGGERED. An exhausted ladder or extension quota leaves the ceiling unresolved; it does not establish saturation.

Each new cap changes only that axis relative to the current G. Promote G on that axis only if the extension exceeds G and passes its production numerical qualification, regardless of whether geometry recovery succeeds. On promotion, increment the cap epoch, recompute G, and rerun every previously completed one-axis cap configuration in F,M,K,K_u order, ascending cap order, holding all OTHER axes at the new G. Reuse only exact source/workspace/schedule/budget identities. Preserve superseded results, exclude unmatched old epochs from contrasts, and finish this queue before another extension decision. A promoted G changes the common uncapped terminal target; configurations affected by that schedule change must also rerun. All reruns count toward section 11's hard attempt limit. Mandatory probes used by a decision must finish before dispatch; no retrospective extension selection from a favorable plot.

### 5.4 Effective intervention exposure

Record CAP_REACHED when a production linearization/trial at that exact cap completes; record CAP_BINDING when the uncapped request exceeds it and computation at the capped value completes. These are distinct. A completed controlled terminal comparison requires CAP_REACHED; a claim that restricting a proposed schedule changed behavior additionally requires CAP_BINDING. Record neither as NOT_REACHED. Early audited recovery can establish that a larger cap was unnecessary for that recovered trajectory, but does not establish a general numerical/information ceiling. CAP_BINDING at c, together with production computation above c in the larger-cap fits, are the exposure conditions of the section 7.2A no-gain bound.

Research fits with a strict F subset cannot claim success from the subset loss. At return, their full-catalog audit decides recovery. Do not feed that audit back into the fit.

## 6. Execution phases and exact comparison matrix

### Phase A — preparation, qualification, and resource pilot

1. Verify sealed TG-002 inputs, checkout status, environment, source boundaries, and output-path freshness. Save source archive/hashes, plan hash, input manifest hash, resolved settings, and all environment facts.
2. Implement the independent slots, complete recording, and source/decision replay checks. Validate serialization, settings, schedule generation, and absence of truth access without numerical toy experiments.
3. Numerical qualification uses hook's actual prescribed initial circle and the archived DP-001/F_screen hook prefix endpoint/failure endpoint. Use recorded curves, not truth geometry. Save source paths/hashes and label these as old-trajectory states evaluated by the new implementation. Verify the section 8.3 sub-block property on these states.
4. Run pilot step 1 of section 10 (maximum-dimension cells). It is explicitly partial, never policy or ceiling evidence. If it fails its limits, preserve it and close RESOURCE_BLOCKED; do not launch the matrix.
5. Run C0 with recording. With its complete atlas, this is pilot step 2 of section 10, whose release gate decides whether Phase B starts. Compare it with the archived failure descriptively. Instrumentation must preserve the same numerical accepted decisions and final coefficients when replayed with recording disabled from the same fresh source; pure I/O timing may differ. This one paired instrumentation check is the only compulsory duplicate before the matrix. Its recording-disabled replay is the sole exception to section 8.1: preserve ordinary coefficients/decisions/timing, and link to the recorded run's exactly matching five-role atlas instead of recomputing it. It is not an independent atlas sample.
6. Check actual-hook complete derivatives at the initial, last damped, and failed endpoint; retain infeasible finite differences as such. Apply the declared K_u/workspace ladders before labeling a state unresolved. Implementation/integrity failures stop launch. At least the initial production directions must qualify before Phase B. An archived failed endpoint that remains numerically unresolved is retained as that outcome; it does not forbid fresh qualified trajectories. High-P diagnostic failures terminate their cells as unqualified and do not abort the whole study. The explicit WORKSPACE_UNRESOLVED/resource rules still apply.

### Phase B — nine initial capacity configurations

Use S0 and section 3 for:

| ID | F cap GHz | M cap | K cap | K_u cap |
|---|---:|---:|---:|---:|
| G | 2.5 | 95 | 192 | 192 |
| F0 | 1.0 | 95 | 192 | 192 |
| F1 | 1.5 | 95 | 192 | 192 |
| M0 | 2.5 | 19 | 192 | 192 |
| M1 | 2.5 | 37 | 192 | 192 |
| K0 | 2.5 | 95 | 32 | 192 |
| K1 | 2.5 | 95 | 64 | 192 |
| U0 | 2.5 | 95 | 192 | 64 |
| U1 | 2.5 | 95 | 192 | 128 |

Execution order is G,F0,M0,K0,U0,F1,M1,K1,U1. This prevents an agent from dropping low-cap corners because they appear unfavorable. Perform the bounded extension rules only after these nine return.

### Phase C — rung-exit comparison

Run one additional fit, G_E0. It is the final G with the historical rung exit: stall, 22 iterations, or 1,200 work units per numbered slot and bridge; 44 iterations for the terminal slot; and no skipping of identical rungs. Everything else is identical to G. C0 retains its own historical exits throughout.

Compare G with G_E0 rung by rung. Report each rung's exit condition, iterations, work, active loss, full-real monitor loss, and offline boundary RMS at exit. Flag rungs where the next control level was released from a stalled state whose shape error had not improved over the rung. Report endpoint outcomes, total work to recovery or failure, and the first obstruction for both.

A one-scene comparison of two single fits is descriptive. It decides only whether the progress exit is retained as this study's default. If G_E0 recovers and G does not, report this explicitly and run the Phase D orderings under both exit rules. That conditional run adds up to eight fits, within the hard attempt limit.

### Phase D — eight ordering policies

Select the common terminal vector C* as follows. Among recovered research configurations from Phases B and C and their extensions, find the minimum total fitting work units; retain candidates within 1% of that minimum, then choose fewer active frequencies, smaller M, K, K_u, and lexicographic configuration ID, in that order. If none recovers, use the final generous vector G and label the ordering study as investigating an unresolved case.

Use the same initialization, catalog-switch position, rung-exit rule, bridge, global budgets, and terminal slot as S0. Starting levels are F=.5 GHz, M=3, K=8, K_u=64. Release each control monotonically through the levels below, truncated to C* and including C* exactly:

    F: 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5 GHz
    M: 3, 5, 7, 9, 11, 15, 19, 25, 31, 37, 49, 61, 79, 95, 127
    K: 8, 12, 16, 20, 24, 32, 40, 52, 64, 96, 128, 192, 256, 384
    K_u: 64, 96, 128, 160, 192, 256, 320

For a control's list of length n, fractional release q selects index floor(q*(n-1)), with index 0 the starting level. Skip identical rungs as in S0. Pair-first controls use q=min(s/4,1), pair-second controls q=max((s-4)/4,0), at slots s=1,...,8. Diagonal uses q=s/8. The bridge reuses slot-4 settings with the real catalog.

| ID | Nominal ordering |
|---|---|
| O1 | (F,K_u) first, then (M,K) |
| O2 | (M,K) first, then (F,K_u) |
| O3 | (F,M) first, then (K,K_u) |
| O4 | (K,K_u) first, then (F,M) |
| O5 | (F,K) first, then (M,K_u) |
| O6 | (M,K_u) first, then (F,K) |
| O7 | all four advance diagonally |
| O8 | adaptive rule below |

These are new research arms. They intentionally reopen the frequency/shape sequencing that older CS-001 documentation held fixed. C0 preserves that historical control; do not call these arms the previously agreed four-phase implementation.

In O1–O8, the nominal K_u schedule is a floor: qualification may force an earlier increase up to C*_u. Record every override. If this collapses two nominal orders to the same actual path, report that finding; do not count them as independent mechanisms. At C*_u, use the same bounded unresolved-trial rule as the cap matrix.

### Phase E — deterministic adaptive policy O8

O8 has eight decision slots, the same bridge after slot 4, and the same terminal slot. At a decision:

1. Qualify the current state; raise K_u only as needed within C*_u. This is an accuracy repair, not a contest with information/geometry actions.
2. Form candidates HOLD, next F level, next M level, next K level; omit only a candidate already at its cap. K increases by padding. Use the next level in section 6D, not an arbitrary jump.
3. From the identical saved base and carried controller state, each candidate receives at most TWO optimizer iterations and 200 fitting work units, including its production qualification/repairs. Evaluate the section 3.2 common monitor at the base and each endpoint. All branches, monitor solves, accuracy repairs, and rejected work count against O8's ledger. No reciprocal is needed for the loss-only monitor; its 19 frequencies at two cutoffs cost 38 field-solve work units per state under the existing ledger.
4. Before branching, reserve n_candidates*(200+38)+38 work units against BOTH the slot's remaining backstop and the global remainder. If insufficient, do not run a partial contest; return CONTROLLER_BUDGET_CENSORED and audit the retained base. If a deadline, exception, or indivisible overrun interrupts a contest, discard its eligibility for selection, retain every branch's evidence, restore the original base, and return the corresponding censored/failed outcome. Never choose among only the completed branches.
5. Among numerically qualified branches whose common loss decreases by BOTH >=1% and >=1e-8 absolute, choose greatest loss decrease per charged branch work unit, including its endpoint monitor. The shared base monitor is charged globally, not repeatedly in each score. Using work rather than seconds prevents machine-load fluctuations from selecting different trajectories. Keep scores within 1% of the maximum, then choose smaller raw branch work, then HOLD,F,M,K. Apply the monitor agreement rule in section 3.2.
6. Commit exactly the winning saved branch endpoint and controller state. If no branch qualifies for selection, keep the original state and advance the slot without a fabricated accepted move. Never retain the lowest truth-error branch.
7. After slot 8, advance to C* and use the common terminal slot. Report the forced terminal release distinctly from adaptive choices.

O8 tests whether a charged, data-driven controller is useful; it is not an isolated single-factor experiment.

## 7. Ceiling and mechanism rules

### 7.1 Common comparison labels

Before dispatch, enumerate the following mandatory local-probe manifest at every distinct designated checkpoint of EVERY recorded full fit (the five roles in section 8.2). Deduplicate only exact configuration/controller/source identities. Run HOLD, then two F levels, two M levels, two K levels, and two K_u levels, in that order. For each axis, use the first and second strictly larger values from the section 6D ladder, with all other controls fixed at the checkpoint's actual values. The second compares against the first as well as HOLD. If fewer values remain, mark the absent entry RANGE_LIMITED; do not invent a larger value. These are offline diagnostic interventions and may exceed the parent arm's cap, within the overall study maximum.

F adds all catalog frequencies up to the selected threshold to the existing active set; retain any original gaps in HOLD and identify every newly added frequency. Catalog kind follows the saved stage. M changes only the trial band. K zero-pads the identical base; no cropping. K_u performs new solves at the selected cutoff. Freeze production K_u in F/M/K probes: a witness can disqualify a calculation but cannot silently promote it. Workspace is common. Use the saved active objective, lambda, controller, and validity settings; at the original circle use the specified warm-up settings/default lambda. Missing/invalid bases have explicit not_reached/failed entries, not substituted geometries.

Each branch has the same opportunity: at most two optimizer iterations and 200 fitting work units. Charge the common real monitor separately in its offline probe ledger. A probe cannot mutate the parent fit. Compare branch endpoints under this shared allowance, record actual cost, and do not describe different actual costs as identical work. Let d=L_lower-L_higher and relative gain=d/max(L_lower,1e-30). Classify in this priority order:

1. Artifact/input/resource failures, geometry refusals, budget censoring, and unavailable levels keep their distinct outcome classes.
2. Failed numerical qualification is UNRESOLVED_NUMERICS, with regression_from_passed if appropriate. A lower branch's numerical refusal repaired by the higher branch is QUALIFIED_NUMERICAL_RESCUE; it is not yet evidence of better reconstruction.
3. For jointly qualified endpoints only, QUALIFIED_USEFUL requires d>=1e-8 AND relative gain>=.01. QUALIFIED_HARMFUL requires the corresponding negative differences of those magnitudes. QUALIFIED_EQUIVALENT requires neither material loss change, equivalent physical moves, and matching accept/refuse decisions. Otherwise use QUALIFIED_DIFFERENT_UNRESOLVED.

For progress-versus-work plots, use the fixed allowance grid 0,50,100,150,200 units. At W use only the last accepted state computed at or before W; never interpolate or borrow a later state. Compare at W only when both branches have worked through W or normally converged. Two-iteration termination before W is ITERATION_LIMITED, not convergence. No positive common eligible W means no matched-work progress claim. Ceiling decisions use the shared-opportunity endpoint labels above, with cost reported separately.

### 7.2 Upper bounds: no-gain bound and recovery-sufficient ceiling

Report two bounds for each axis. Both remain conditional on the other controls, objective, start, and tested path.

**A. No-gain bound.** It answers question 1 whether or not the scene recovers. An axis cap c earns NO_GAIN_BOUND only when:

1. The fit capped at c records CAP_BINDING at c. Otherwise the larger caps could not have differed; label the comparison NOT_EXPOSED.
2. TWO larger completed caps on the same axis, with identical other settings, budget, and source/workspace epoch, each completed production computation at a value above c. Record their actual peaks.
3. Across c and every tested larger cap, all of the following hold:
   - the same outcome class: recovered, or the same failure outcome and first obstruction under section 7.7;
   - final boundary RMS and Hausdorff upper bound each within 0.2 mm;
   - maximum full-real relative residual within max(0.0003, 1% of the larger value);
   - no material difference in the qualified common-monitor L_real (relative >=.01 and absolute >=1e-8, as in section 7.1). A MONITOR_UNRESOLVED endpoint leaves this condition unresolved.
4. No numerically qualified, budget-matched larger-cap result, including extensions, contradicts conditions 1–3.

Select the smallest c satisfying all four. When the compared fits failed, label it NO_GAIN_BOUND_ON_FAILURE. It means raising this control beyond c did not change that failure; it is not evidence that c suffices once the obstruction is removed.

**B. Recovery-sufficient ceiling.** An axis cap c earns this label only when:

1. Its full fit passes every recovery gate.
2. CAP_REACHED holds, or early audited recovery establishes explicitly that it was unnecessary on that trajectory. Report CAP_BINDING separately.
3. TWO larger completed caps with identical other settings and budget also recover.
4. Across c and every tested larger qualified cap, final boundary RMS differs by <=0.2 mm, Hausdorff upper bound differs by <=0.2 mm, and maximum full-real residual differs by <=0.0003.
5. There is no numerically qualified, budget-matched larger-cap result that contradicts the plateau.

Select the smallest c satisfying all five. This is an ACCURACY-SUFFICIENT ceiling. Additionally label it an effective useful upper bound only if no larger qualified cap reduces charged work to qualified recovery by more than 10%, and the two successive fixed-state comparisons support the relevant local mechanism plateau. Use the earliest recorded accepted checkpoint that passes the full recovery audit; if intermediate recovery time is unknown, efficiency saturation is unresolved. Wall time is reported separately and checked in confirmations; it does not replace charged-work evidence. Thus a larger cap that recovers three times faster prevents a claim of "nothing material gained" even when endpoint accuracy is unchanged.

These tolerances concern the benchmark's required accuracy, not equality of coefficients or performance at a tighter target. Always publish the raw errors, work, and conditioning. Ceilings remain conditional on the other controls, objective, state, and tested path.

One larger comparison yields a PROVISIONAL_BRACKET, not a confirmed bound of either kind. F=2.5 GHz is always CATALOG_LIMITED; it needs no fictional higher-frequency experiment. At the maximum planned M/K/K_u range, report RANGE_LIMITED unless lower values already established the plateau.

### 7.3 F mechanism

At each atlas checkpoint evaluate every supplied real frequency, including ones absent from the fitted subset (section 8.2). Gradients, information matrices, and cross-frequency alignment are computed at report time from the stored per-frequency residuals and Jacobians. Compare conditional fits with and without the next frequency group using the same physical update space and resolved K_u.

Additional frequencies may help by adding independent directions, improving conditioning, or changing the nonlinear route. Rank alone cannot establish saturation. A subset-fit success must still pass all full-catalog gates. Never describe monitor frequencies as unseen holdouts after O8 has used them for selection.

Two measurements classify each F probe group g of section 7.1; the second group is also compared against the first. Let S be the active frequency set and S+g the set with g added. Use the checkpoint's actual update directions, the stage's catalog kind, and the section 7.4 physical normalization. Scale each frequency's rows by the existing lm_backend normalization but not by the subset weight 1/|S|, so adding frequencies only appends rows; both measurements are invariant to that uniform scale. Both use arrays that the checkpoint atlas and the probe branches already compute.

1. **New directions.** Let V_old hold the right singular vectors of J_phys,S above a common threshold tau, the larger of the section 7.4 tau values for S and S+g. Form J_added_dirs = J_phys,S+g * (I - V_old V_old^T), let Q_new_F hold its left singular vectors above tau, and compute

       p_new_F = ||Q_new_F^T r||^2 / max(||r||^2, 1e-30)

   with r the realified, row-scaled residual on S+g. p_new_F>.01 labels g ADDS_DIRECTIONS: it makes usable shape directions that the current frequencies cannot resolve, and the current residual has material weight along them. Also record the smallest singular value of J_phys*V_old for S and for S+g as a descriptive conditioning gain; it has no gate.
2. **Local-model fidelity.** Classify the lm_backend gain ratio (actual/predicted decrease) of the first evaluated proposal of the HOLD branch and of the +F branch with the agreement controller's own thresholds: GOOD >=.75, FAIR [.25,.75), POOR <.25 or undefined. A geometry-validity refusal is recorded as such, not as POOR; a branch with no evaluated proposal is unavailable. A lower class for +F labels g ROUGHENS: with g added, the optimizer's local model no longer predicts the step it would take. Record both physical RMS step sizes, because larger steps tend to lower the ratio. For attribution, record each frequency's linearization error ||y_f(c+delta)-y_f(c)-J_f*delta|| / ||J_f*delta|| along each branch's proposal delta, from evaluations the branch already performed.

Two successive groups with p_new_F<=.01 and QUALIFIED_EQUIVALENT F probes establish local F information saturation at that state. In the plain-language account, ADDS_DIRECTIONS means the new frequencies reveal detail the current ones cannot; ROUGHENS means they change too fast for the current step; neither, with an equivalent probe, means nothing is gained from them at that state yet.

### 7.4 M mechanism

Use the complete projected-trial Jacobian, not only ideal normal harmonics. Keep the optimizer unchanged; mass normalization here is diagnostic.

Let H be the physical RMS-normal mass metric from the existing update.metric(space,'mass'). Remove its diagnostic null directions only below 1e-10 times its largest eigenvalue; record the removed eigenspace and do not remove optimizer variables. Define the realified, normalized Jacobian for a 1 mm RMS move:

    J_phys = 1e-3 * J * H^(-1/2)
    tau = max(1e-3*sigma_max, 10*||J_phys_refined-J_phys_production||_2, 1e-4)

Align column coordinates and use the same H transformation in a production/refined comparison. Reliable singular vectors exceed tau. For an old/expanded M comparison, construct J_phys_old using the restricted old J and its restricted mass metric, and J_phys_full using the full J and full metric. Use one common threshold: the maximum tau computed for the old and full problems. Let Q_old contain the old reliable left singular vectors. Form

    J_added_data = (I - Q_old Q_old^T) * J_phys_full

and let Q_new contain its left singular vectors above that common threshold. Full mass whitening mixes harmonic coordinates; never identify "added columns" by slicing the whitened matrix. Compute:

    p_new = ||Q_new^T r||^2 / max(||r||^2,1e-30)

p_new>.01 indicates locally available extra residual reduction; it does not prove a valid finite step exists. At two successive band increases, p_new<=.01 plus qualified equivalent burst results supports local M saturation. A large p_new with no accepted finite progress is an optimization/validity obstruction, not missing information.

Every conditional M step must solve its own restricted normal equations at the same lambda. Do not obtain it by slicing a larger solved vector. Retain full complex J, residual, H, singular values/vectors, and the complete off-diagonal information matrices.

### 7.5 K mechanism

Use an identical physical base, zero-padded to larger K, and an identical requested normal-coordinate proposal. Specifically replay HOLD's first bounded LM proposal at every compared K, using the same base and backtracking factor; if HOLD has no qualified proposal, mark this replay unavailable. Use these replays for projection/storage equivalence, and separately optimized K bursts only for progress. Compare the actual centered projected finite maps and complete tangents. Require the move-equivalence thresholds in section 3, tangent-column relative RMS differences <=1e-3, field/Jacobian qualification, and matching validity/acceptance decisions.

Save intended versus realized normal displacement, Cartesian coefficient tails, derivative/curvature diagnostics, and projection error. Small position coefficients alone do not certify normal/curvature accuracy. The existing intentional_projection_mm scalar alone is insufficient because centered updates can cancel base/gauge effects.

Two successive qualified increases with equivalence establish local K saturation at that state/move. If the base itself cannot fit into a lower K, do not crop it to pretend a matched-state comparison; mark that lower comparison unavailable and rely on its independent full fit.

### 7.6 K_u mechanism

At fixed geometry, K, physical directions, frequency, workspace, objective scaling, and carried lambda, perform actual re-solves at production and higher cutoffs. A projection of a fine solution is an optional additional diagnostic, never a replacement for a smaller-system solve.

Require fields, full Jacobian, gradient, first bounded LM proposal, and accepted physical move to satisfy the specified comparisons. Where section 8.3 selected derivatives exist, preserve the discrete-model and trace-Hadamard derivatives separately; elsewhere the complete-trial finite-difference audit is the data-space check of the discrete model. Explain any cutoff difference with the section 8.2 omitted-mode feedback record. Two qualified confirmation levels establish local numerical saturation.

Use g_phys=J_phys^T*r with a common physical metric and require ||g_phys_hi-g_phys_lo||_2 <=1e-3*max(||J_phys_hi||_2*||r_hi||_2,1e-12). This avoids division by a nearly canceled gradient. Gradient qualification applies only to identical objectives/coordinate spaces; cross-M mechanism comparisons use section 7.4 instead.

Do not use K_u=M/2, a small wavefield tail, a small matrix residual, or M<=2*K_u as a universal sufficient-resolution rule. The shape basis, trace parameterization, geometry factors, and high-mode feedback matter.

### 7.7 Failure classification and scientific selection

For each failed run record the first causal obstruction supported by its receipts, plus coexisting obstructions: input/model inconsistency; workspace; field cutoff; derivative; projection/storage; geometric validity; uninformative directions; qualified optimizer stagnation; work/time/resource exhaustion.

Use "wrong basin" only as an interpretation when a qualified trajectory fits its active objective but remains geometrically wrong under offline scoring. Do not infer it solely from failure to recover.

Select a provisional winner using PRIMARY-budget research fits only: find the minimum fitting work among recovered candidates, retain candidates within 5% of that minimum, then prefer fixed schedules over O8, smaller actual peak K_u, K, M, and finally lexicographic configuration ID. Extended-budget diagnostics are ineligible. Confirm this one candidate and C0 under section 11. Recommend the candidate only if all three candidate attempts recover, production numerical gates pass, recording is complete under section 9, and the evidence used to justify that recommendation qualifies. An unrelated unqualified high-P diagnostic cell does not veto a qualified recovery, but its mechanism remains unresolved. If confirmation fails, report NO_CONFIRMED_WINNER; do not substitute an unconfirmed runner-up. If none initially recovers, recommend the next mechanism to investigate using the recorded first-obstruction evidence, with no declared winner or production promotion.

## 8. Atlas contract: retained evidence, regenerable operators, and cadence

Retain everything that cannot be recomputed: the trajectory, decisions, controller state, timing, and failures. Also retain every array a conclusion cites, at the resolution the conclusion uses. Do not retain operators that are deterministic functions of a saved state, observation, K_u, B_work, settings, and the archived source. For those, record the regeneration identity and verify regeneration under section 8.4. The only stored operators are the bounded snapshots and selected derivatives of section 8.3. The pre-review contract stored A/B/R at every evaluation plus all-direction dense derivatives, and section 10 shows it could not be stored; this section replaces it.

### 8.1 Complete recording of work actually performed

Every field evaluation, reciprocal solve, linearization, geometry proposal, cutoff/workspace attempt, and failure must have an indexed record. Capture the listed arrays before transient solver handles are discarded. Missing data must use one of: not_computed, failed, unqualified, not_reached, not_triggered, missing_artifact. Only the last is an integrity defect. An operator that section 8 deliberately does not retain is recorded as regenerable, with its identity; that is not missing data.

Required records:

| Layer | Contents |
|---|---|
| Run | Exact resolved policy, budgets, source archive/hashes, input hashes, observations, acquisition, units, material, environment/device/threading, seeds |
| State | Complex geometry coefficients, parameterization, parent/occurrence IDs, stage/iteration, intended and actual F/M/K/K_u, B_work, time/work checkpoint |
| Field evaluation | Complex prediction and residual per frequency; system residual; production/refined discrepancy when computed; trace-tail energies per source and trace unknown, for forward traces and for reciprocal traces when computed, in the mode bands K_u-32<\|m\|<=K_u and K_u-64<\|m\|<=K_u-32, plus totals; resolution/scaling/order metadata; regeneration identity (state, observation, K_u, B_work, settings, source hash) |
| Linearization | Full complex complete-trial J at the active M and frequencies; weights/floors; lambda and controller state; gradient; regularized step. Velocities, ideal basis, and physical metric are regenerable from the state and update space; they are stored at section 8.2 checkpoints |
| Trial | Raw optimizer proposal, clipping/backtracking, intended displacement, projected/reparameterized candidate coefficients, certificates/validity, projection loss, predicted/actual gain, decision and reason |
| Failure | Exception/traceback, last valid state, attempted settings, failed phase, charged/actual work; for every numerical-resolution refusal, complete forward and reciprocal traces at the production and refined cutoffs |
| Cost | Assembly, factorization, RHS, reciprocals, Jacobians, geometry, refinement, controller probes, audits, I/O, offline atlas; inclusive/exclusive timer meanings |

For paired measurements, record the channel-selection definition, source strengths, and reciprocal conventions in the regeneration identity; a full R*X cross-channel matrix is not itself the measured 24-vector. The section 7.1 probes and section 3.2 monitors are recorded under this same table.

### 8.2 Fixed additional atlas checkpoints for EVERY full fit

Designate exactly these five roles:

1. Original prescribed initial circle.
2. Last accepted damped state immediately before the real bridge; if the damped portion fails, its returned endpoint.
3. First accepted state evaluated with all 19 real frequencies in the fitted objective; otherwise not_reached.
4. The base state of the first numerical-resolution refusal; otherwise not_triggered.
5. Returned final state.

Also retain all section 8.1 records from every intermediate accepted/rejected state. The five roles define the ADDITIONAL atlas, not permission to discard intervening evidence. Deduplicate identical geometry/parameterization arrays but keep every occurrence and controller state.

At each of the five roles compute all 19 real frequencies. For a role reached in a damped stage, additionally compute all 19 frozen damped frequencies. The original initial circle role is real-only; actual damped initial computations are still recorded under 8.1.

Diagnostic normal band P=127 for response atlases, providing 255 real directions beyond the ordinary M=95 range. If a run actually uses M=127, use P=159 (319 directions) at ALL its designated checkpoints. Export order is constant, cos1,sin1,...; the optimizer's grouped order differs. Save the exact permutation for J, velocities, H, proposals, and selected-derivative directions. Pilot indices refer to export order.

Retain both intrinsic normalized-arclength sensitivities and complete projected-trial sensitivities at the state's actual K, with the Cartesian and normal velocities, ideal basis, and metric H used. Record intrinsic-to-realized velocity error, including directions projected almost to zero.

At each checkpoint/frequency select the smallest K_u in the study ladder whose field and ALL declared P response columns pass against BOTH its +32 and +64 witnesses. This is a single-frequency RESPONSE certificate, not a certificate for a production optimizer step. Use one common qualified workspace. Start the upward search at the run's actual cutoff (64 at the original circle); after an upper qualified reference exists, test lower ladder entries ascending and choose the smallest that passes. For every attempted cutoff, save fields and per-column response errors against the witnesses. Save full response Jacobians at the selected cutoff and its two witnesses. Save complete forward and reciprocal traces at the selected cutoff and at the largest cutoff evaluated at that cell, K_top. If none passes, record the cell unresolved with all computed arrays.

**Omitted-mode feedback.** At each cell, use the K_top system as the reference. For every attempted cutoff K<K_top, let L be the rows/columns with |m|<=K in each block and H the remaining ones, and evaluate the MA-006 identity

    x_L(reduced) - x_L(reference) = A_LL^(-1) A_LH x_H(reference)

Save, per source and trace unknown, the norm of the retained-solution difference relative to x_L(reference), and the identity residual. At the selected cutoff, also save the full feedback vector A_LH x_H(reference). This record is the K_u mechanism evidence. It is computed in memory from the reference system, which is stored only under section 8.3.

Separately qualify cutoff-dependent actual steps on the checkpoint's complete ACTIVE objective, actual M/K, and saved lambda/controller; this is the certificate used by section 7.6. The all-19-real merit is the independent section 3.2 monitor. Never substitute a single-frequency high-P certificate for either of these. Atlas responses, feedback records, and snapshots use the response-qualified cutoff even if it exceeds the parent fitting cap; they are explicitly offline diagnostics.

### 8.3 Operator snapshots and selected derivatives

**Sub-block property.** With B_work fixed, the modal system at cutoff K should equal the |m|,|n|<=K rows/columns of each block of the system at any K'>K. The kernel_matrix entries depend on the mode pair and the coefficient window, not on the cutoff. Phase A verifies this on the states of its step 3, at 0.25 and 2.5 GHz in both catalogs, comparing K=64 and K=192 against K'=384. Each block must agree to <=1e-12 relative Frobenius error. If the check fails, store the snapshots below at every cutoff a conclusion uses, and recompute the section 10 forecast before Phase B.

**Snapshots.** The designated fits are C0, plus the first completed G and U0 of the final workspace epoch: the historical recipe, the generous vector, and the lowest K_u cap. Superseded snapshots are preserved. At each of their five roles, for every computed frequency/catalog cell, retain the complex A, B_s, B_r, and R at K_top, with the solved forward and reciprocal traces. Every smaller-cutoff system at that state is a sub-block of this snapshot.

**Selected derivatives.** At roles 4 and 5 of each designated fit, choose the real-frequency cell with the largest production-versus-(+32) response discrepancy; ties go to the higher frequency. At that cell, compute directional derivatives of A, B_s, B_r, and R at the selected production cutoff and at its +32 refinement. Use the constant direction and the two P directions with the largest production-versus-(+32) column error.

Use analytic directional derivatives when an existing validated implementation supplies all terms; they must pass the same finite-difference qualification below. Otherwise use centered directional differences of the actual assembled A/B/R. Perturb coefficients c by c +/- h*V, where V is the saved complete Cartesian tangent in package-length units per metre of optimizer coordinate. Start h=1e-7 m and halve to 5e-8, 2.5e-8, and 1.25e-8 m, at most three halvings. This is a coordinate increment, NOT a prescribed RMS displacement; record the resulting physical amplitudes. Apply existing validity checks to perturbed geometries.

For EACH T in {A,B_s,B_r,R}, define h_ref=1e-3 m and

    E_T = ||h_ref*(D_h T-D_(h/2) T)||_F /
          max(||h_ref*D_(h/2) T||_F, 1e-12*||T(base)||_F, 1e-30)

with the floor expressed in that array's saved units. Never concatenate arrays with different units for this norm. Accept the first adjacent pair with every E_T<=1e-3 and discrete-response consistency <=1e-3 under the existing normalized column-error definition. Retain both estimates of the accepted pair, every E_T, step, and physical amplitude, and the perturbed data values y(c +/- h*V). The perturbed operators themselves are not retained. If no pair qualifies, retain the estimates of the last pair and label the derivative unqualified. An exactly zero saved tangent may be certified zero; a small nonzero tangent or finite difference that rounds to zero is unresolved below numerical resolution, not proof of zero sensitivity.

The full response identity to check is:

    D_p y = (D_p R) X + R A^(-1) [D_p B_s - (D_p A) X]

with the recorded paired-channel selection applied. Its data finite difference uses the SAME straight Cartesian perturbation c +/- h*V. Separately compare against centered finite differences of the actual nonlinear projected trial map.

Save four independent flags: operator-FD convergence; discrete-data consistency; Hadamard consistency; and refinement/step fidelity. Hadamard and actual-trial comparisons each require normalized column error <=1e-3. A passed discrete identity alone establishes internal discrete-model consistency. Physical-sensitivity conclusions require the Hadamard/actual-trial gates too; usable-cutoff or optimizer conclusions also require the relevant refinement/step gate. Retain all discrepancies and both derivatives when a flag fails. Normwise qualification does not certify every small tensor entry individually; preserve raw absolute errors and mark entries below numerical resolution accordingly.

Operator-level derivative claims are limited to these selected directions and cells. Dense derivatives elsewhere are regenerable from saved states; computing them later is a new charged computation, recorded as such.

### 8.4 Persistence, regeneration, and read-back

Use float64/complex128, lossless compressed chunks independently flushable by checkpoint/frequency/cutoff, and a schema-versioned manifest. Store array name, axes/order, dtype, units, shape, hash, byte counts, coordinate definitions, qualification, and exact retrieval path. Content-addressed sharing of bitwise-identical data is allowed. Committed JSON carries no array payloads.

Derived-array cache identity includes source/workspace epoch, geometry AND parameterization, catalog/wavenumber, material/acquisition, K_u, coordinate band/map, normalization, and solver tolerances. Geometry identity alone does not authorize reusing a response/operator record.

Read-back must establish:

- Exact hashes, shapes, dtypes, and real/imaginary components.
- Objective rebuilt from stored predictions, raw data, and weights agrees to 1e-12 relative, absolute floor 1e-15.
- Gradient and regularized step rebuilt from stored J, residual, lambda, and the clipping/backtracking rules agree to 1e-10 relative where well-conditioned. When that tolerance is unattainable, retain exact inputs and condition/residual evidence and flag replay qualification instead of loosening the threshold.
- For snapshots: the stored A*X-B residual equals the recorded residual, and a large residual remains a numerical failure, not an artifact failure. Prediction rebuilt from R and X plus channel selection agrees to 1e-10 relative, floor 1e-14 in normalized units.
- **Regeneration:** re-run evaluations from stored states and the archived source, on the production device and settings. Cover every role-5 2.5 GHz real cell, plus 20 field evaluations and 5 linearizations per fit drawn with seed 42007 from the recorded indices. Predictions and J must agree with the stored values to 1e-10 relative, floor 1e-14 in normalized units. A failure is a REGENERATION_DEFECT: retain both results, and do not treat that fit's unretained operators as regenerable until the defect is explained.
- All decision flags, parent/child states, work totals, and saved outcomes reconcile.

The report must be regenerable without rerunning the inverse or the atlas. Recreating a plot from stored arrays is allowed. Computing an operator that section 8.3 does not retain is a new charged computation and must be recorded as such.

## 9. Full-atlas completeness and required reports

The atlas index lists every expected checkpoint/catalog/frequency/cutoff response cell, feedback record, snapshot, and selected-derivative cell before its collection starts. Completion means each cell has either the required arrays or an explicit numerical failure terminal record. A missing artifact, resource interruption, or intentionally omitted entry cannot be called a complete atlas.

Required reports:

1. Three-question executive answer, with a plain-language four-control explanation.
2. Bound table: tested values, exposure, no-gain bounds, local plateaus, recovery-sufficient caps, confirmation levels, phase/geometry dependence, uncertainty/outcomes.
3. All-configuration table including every failure, exposure, actual peaks, work, timings, memory, and retained-evidence sizes.
4. Actual-path plots in F/M/K/K_u versus work, showing nominal versus forced resolution changes and the fixed catalog switch.
5. Per-frequency/per-direction response atlas with magnitude AND signed/complex residual alignment; correlations/independent directions; intrinsic versus realized shape motion; section 7.3 F labels (p_new_F, gain-ratio classes) per checkpoint and group.
6. Trace-tail and omitted-mode feedback atlas for every fit, plus operator snapshots and selected derivatives for designated fits, with absolute scales and phase retained in raw data. Normalized visualization scales are labeled.
7. Progress at common work checkpoints, full-catalog residuals, offline RMS/Hausdorff, accepted/rejected move histories, and first obstruction.
8. A decision table for retaining/rejecting each scheduling idea; explicit unresolved interactions.
9. Resource, source, input, read-back, regeneration, and retention/push verification receipts.

The final scientific report must not use truth-based plots or offline full-catalog probes as evidence that a controller had access to that information while fitting.

## 10. Resource pilot and retention gate

The previous estimate was 3–6 days end-to-end, with only about 1–2 hours for the nominal primary fits. It is a planning estimate, not a deadline or measured guarantee. Offline atlas computation dominates.

At authoring, this workspace reported about 179 GiB available. This is not a storage reservation.

One modal system matrix (complex128, N=2(2K_u+1) unknowns) is 1.1 MB at K_u=64, 9.5 MB at 192, 26 MB at 320, and 38 MB at 384. The pre-review contract stored A/B/R at every evaluation plus all-direction dense derivatives. That needed about 0.5 TB per fit even at K_u=64, and 1.3–3.7 TB at K_u=128–192. Its own pilot needed about 57 GB against a 20 GiB limit.

Section 8 replaces it. Its worst-case planning forecast is <=2 GB per fit, plus <=7.5 GB of snapshots and <=0.7 GB of selected derivatives per designated fit. That is about 85 GB for the nominal queue and 155 GB for the hard envelope. Measured pilot values replace these numbers. Do not quietly reduce P, frequencies, checkpoints, precision, or failure retention.

Pilot:

1. **Maximum-dimension cells.** This step is explicitly partial and is never policy or ceiling evidence. Use the prescribed initial hook circle and the archived DP-001/F_screen hook last-damped and failed endpoints, zero-padded to K=384 without changing their shape. At 0.25 and 2.5 GHz in BOTH frozen real/damped catalogs, evaluate fields and the P=159 response at K_u=320, 352, and 384 with B_work=512. Add one B_work=1024 evaluation per state at 2.5 GHz real. Write and read back one K_u=384 snapshot; the section 8.3 sub-block check itself runs in Phase A step 3. No toy geometry or synthetic residual is introduced. Limits: 60 minutes wall, 10 GiB new artifacts, one worker.
2. **Recording pilot** = Phase A step 5. Run C0 with full section 8.1 recording, its complete section 8.2 atlas and section 7.1 probes, and its section 8.3 snapshots and selected derivatives (C0 is designated). Limits: 3 hours offline computation and 20 GiB new artifacts. This is a required fit, not a partial substitute.

Measure peak memory, assembly/derivative/solve/I/O time separately, and compressed bytes per retained category. If a limit stops a pilot step before its measurement is complete, the resource gate remains unqualified; preserve the evidence and close RESOURCE_BLOCKED. Do not extrapolate from a convenient smaller matrix as if it qualified the maximum.

Publish two forecasts: the currently released nominal queue and the hard authorized envelope. The envelope includes:

- 64 fit attempts, including workspace restarts and confirmations, of which at most eight are extended-budget fits;
- five checkpoint roles per attempt, with up to 38 frequency/catalog cells per role;
- P=159 responses, all cutoff witnesses, and failed attempts;
- nine local-probe branches per checkpoint;
- the designated snapshots and selected derivatives.

Count recording from work-limited evaluation counts and the largest measured bytes per charged work unit; never assume unsuccessful trials are free or sparse. Include input/source archives, manifests, and read-back/regeneration scratch capacity. Exact-identity deduplication can reduce the nominal forecast only where identity is already established.

Estimate runtime from the slowest measured per-unit/per-cell costs at the dimensions each configuration can reach, plus fixed costs, with a factor of two. Estimate storage from the largest measured lossless retained bytes per category plus 25% headroom; do not add that 25% twice. The initial release must fit the nominal queue within the 72-hour offline budget and verified storage.

Recompute this gate BEFORE every conditional extension, workspace restart, Phase C, and confirmation, using completed actual costs plus the entire enlarged outstanding queue. The hard-envelope forecast is disclosed rather than silently treated as funded. If a required enlarged queue fails its gate, stop RESOURCE_BLOCKED with outstanding work identified; conditional authorization does not manufacture capacity.

To release Phase B:

- Verified writable capacity must exceed the forecast including its 25% headroom and leave at least 20 GiB filesystem free. The forecasted outstanding offline compute must fit the remaining 72-hour allowance; otherwise the gate fails before launch.
- Peak pilot RAM/VRAM must remain below 80% of available capacity; lower thread batching is an implementation adjustment only if applied to the entire matched comparison epoch and recorded.
- The retention route below must be decided.
- A round-trip retrieval/hash check of pilot chunks must pass before long collection.

**Retention route: user decision required before Phase B.** GitHub cannot hold the arrays. results/\*\*/\*.npz is gitignored, no Git LFS files are tracked, and MA-006's 452.8 MiB of NPZ arrays exist only on this machine.

The proposed default follows MA-006:

- Array chunks stay under the evidence root on this machine.
- The committed manifest records each chunk's path, bytes, and SHA-256, plus the schema and regeneration identities.
- Receipts, reports, code, and figures are committed and pushed under AGENTS.md. Each committed file stays below 50 MB, and every README-linked figure is allow-listed in .gitignore.
- Every report states that raw arrays are retained on a single machine.

If the user requires an off-machine copy, the user names the destination. Do not invent one, silently discard arrays, or pretend a local ignored file has been pushed. Phase A may run before the decision; Phase B may not.

All pilot evidence is preserved and its code/docs/receipts committed and pushed under AGENTS.md even when the gate fails. A resource-blocked study has a concrete completion condition: sufficient verified capacity with the SAME section 8 contract. Changing that contract is a new research amendment, not an implementation optimization.

## 11. Extensions, timing confirmation, and hard limits

The advertised nominal count is C0 +9 capacity fits +1 rung-exit fit +8 order fits =19. It excludes the paired instrumentation check, bounded extensions, duplicates removed by exact configuration identity, and timing/endpoint confirmations.

Hard limits for this plan:

- At most 64 full-fit attempts, including restarts, extended-budget runs, and confirmations.
- At most 8 independent cap-extension configurations (section 5.3).
- One common workspace-epoch promotion.
- Production M<=127, K<=384, K_u<=320; atlas K_u witness<=384; workspace check<=1024.
- Offline atlas/probe aggregate: 72 computation hours and the verified archive capacity, whichever is reached first. Stop cleanly with partial coverage recorded; do not declare the study complete or erase outstanding cells.

Budget extension rule: if an indispensable cap or rung-exit comparison returns ONLY a fitting work/time limit before its differing cap is exposed, run the pair again at 67,060 units/600 seconds, same 30-second aggregate audit allowance. Extend both sides, not only a promising arm. At most FOUR matched pairs. These are separately labeled extended-budget diagnostics; never count them as primary-budget recovery. Numerical/validity failures do not trigger this extension.

Confirmation rule: if any research arm recovers, select the provisional winner by section 7.7, then run winner,C0,winner,C0 from the original centered start. Report all three outcomes per recipe and median/IQR times/work; three observations do not establish broad timing confidence. Require 3/3 recovery for a confirmed research recommendation. If confirmation fails, do not chase another candidate under this plan. If no arm recovers, do not spend confirmations on a false winner.

If an exact duplicate is reused, it counts once as a fit, retains every role, and cannot count as an independent timing repeat.

A cap/resource ceiling reached without a scientific plateau ends that branch as unresolved. No adjacent scene campaign, new representation, different optimizer, or automatic default promotion is included.

## 12. Implementation map and acceptance

Read solvers/bem_inverse/README.md before editing. Expected narrow implementation touchpoints:

| Area | Required responsibility |
|---|---|
| policy / continuation policy | Explicit independent stage values, exact S0/O1–O8 rules, resolved plan receipts |
| modal_muller / ModalSettings | Explicit K_u and workspace; trace and trace-tail export before handles expire; snapshot and selected-derivative hooks for designated fits |
| physics / FitStage validation | Modal-specific accuracy specification without nodal token coupling |
| runner / lm_backend | Immutable trial/accepted-state recording, carried controller snapshots, charged branching and qualification; plain progress-exit option, rung backstops, identical-rung skipping |
| normal_basis / selected geometry update | Exact coordinate maps, physical metrics, intended/realized velocities; no new geometry algorithm |
| experiments/benchmark/ma007.py | Scene boundary, matrix enumeration, gates, manifests, execution/resume, scoring |
| ma007_report.py | Read-only reconstruction of all claims from saved evidence |

No test-only alternate physical model. Structural assertions and artifact/schema tests may use metadata; all numerical derivative, solver, and continuation validation for this study must use the actual hook scene/states specified above. Do not run legacy scene campaigns or synthetic inverse test scenes to qualify these policies.

Before launching Phase B, validate:

- C0 instrumentation equivalence on this actual scene.
- All four controls can change independently; the requested/actual values and any qualification override reconcile.
- No truth or unavailable-frequency observation enters a fixed-cap controller.
- Production/refined and workspace comparisons hold the other physical/numerical definitions fixed.
- Initial production-direction complete-trial derivative checks pass. Archived-state and high-P failures follow Phase A's explicit unresolved-state rules; an implementation/integrity failure stops launch.
- Failed and interrupted records remain readable; metadata/hash verification distinguishes not_computed from lost data.
- The section 8.3 sub-block property holds on the actual hook states, or its fallback is applied and the section 10 forecast is recomputed.
- The section 8.4 regeneration check passes on the C0 recording pilot, and the section 10 retention route is decided.
- Dry enumeration of all configurations, cap ceilings, bridge positions, rung-exit backstops, skipped identical rungs, ties, and extension branches matches this document.

A conventional test suite is not recovery evidence. Static/import/schema checks are permitted; new inverse validation is confined to hook__c13.3. The user's actual-scene-only instruction takes precedence over older generic instructions to run legacy numerical suites.

## 13. Progress reporting, commit/push, and agent handoff

Maintain a machine-readable state file with next phase, prepared source epoch, completed/failed/pending configurations, atlas coverage, remaining work/storage budgets, and gate decisions. Reports should allow an agent to resume without relying on chat context.

After each new experiment run or closed pilot/probe batch:

1. Validate the run/artifact receipts and preserve failures.
2. Commit the MA-007 code, plan amendments, docs, manifests, reports, and retained results to the current branch.
3. Push to its configured remote and verify remote HEAD and final working-tree status.
4. Preserve and identify unrelated pre-existing changes; never discard them for cleanliness or include another active agent's work without coordination.

Do not rewrite a frozen executed plan. Corrections after dispatch are dated amendments with source/config changes identified; scientifically affected comparisons are rerun under a new immutable attempt/epoch.

If the retention gate prevents retaining the section 8 evidence, report it explicitly and stop further production; do not replace section 8 evidence with summaries. Operators outside section 8.3 are regenerable by design, verified by section 8.4, and are not part of the retained evidence.

## 14. Completion criteria and decisions already made

Complete only when all authorized, gate-released configurations and declared atlas cells have terminal records, validation/retention checks pass, and the three-question report is written. A blocked or budget-limited closeout must enumerate unfinished work and cannot claim full study completion.

Research choices fixed by this plan:

- Scene/start/acquisition/material/physical damping and numerical backends.
- Separation of cap studies from ordering studies.
- Exact initial cap matrix, extension ladders, rung-exit rule and its comparison, eight order policies, and adaptive tie rules.
- Accuracy, saturation, material-improvement, recovery, and selection thresholds.
- Numerical/workspace failure handling and difference between hard caps and scheduled floors.
- Retained-evidence scope (section 8), regeneration check, snapshot designation, checkpoint roles, response direction coverage, missingness semantics, and retention gate.
- No-gain bound and recovery-sufficient ceiling definitions, and the F-mechanism rules.
- Work/time/attempt limits, permitted restarts/extensions, confirmation rules, and allowed claims.

The implementing agent may not trade away one of these to save time. When a fixed rule cannot be met, execute its specified failure/blocked outcome and retain the evidence. That is the decision; inventing a replacement research policy is not.

## 15. Evidence and reading order

1. [AGENTS.md](../../../../AGENTS.md): current authorization, branch, benchmark, and automatic commit/push rules.
2. [Maintained inverse README](../../../../solvers/bem_inverse/README.md): API/dependency/validation boundaries.
3. [TG-002 benchmark README](../../../../experiments/benchmark/README.md): frozen scene/data/recovery contract.
4. [Research implementation principles](../../implementation_principles.md): identifiable comparisons, truth boundary, negative evidence.
5. [Four-control research vision](../iteration_01/02_proposals/01_research_vision.md): definitions and three atlas levels.
6. [DP-001 results](../../CI-SPD/DP-001_results.md): hook feedback failure and timing.
7. [CS-001 results](../../CI-SPD/CS-001_results.md): K/K_u confounding, unvisited M95 full release.
8. [MA-006 results](01_results.md): reduced-solve feedback and field/Jacobian versus update accuracy.
9. [Existing modal implementation](../../../../solvers/bem_inverse/modal_muller.py): K_trace/workspace coupling and available state.
10. [Existing policy](../../../../solvers/bem_inverse/policy.py): actual current schedule rather than historical prose.

Authoring note: thresholds and schedules in this plan are preregistered proposals. Their inclusion is not a claim they are already implemented, qualified, or optimal.
