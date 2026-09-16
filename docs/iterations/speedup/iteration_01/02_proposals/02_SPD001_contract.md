# SPD-001 — analytic Jacobian in the production topology inverse

Contract drafted 2026-09-15 against the
[iteration-01 brief](01_cost_profile_and_analytic_jacobian_brief.md), using the
experiment-contract template in the [iterations README](../../../README.md).

### SPD-001 — replace the finite-difference residual Jacobian with the qualified coupled analytic Jacobian

- **Approval status:** `PROPOSED — NOT APPROVED FOR EXECUTION`
- **Execution status:** `NOT STARTED`

- **Question:** does replacing the finite-difference residual Jacobian with
  BIE-004's coupled analytic Jacobian reduce topology-run wall clock by the
  predicted 1.73x–1.79x **without changing the geometry the inverse recovers**?

- **Falsifiable hypothesis:** it does not. The result is wrong if end-to-end
  speedup on the measured scenes is below 1.3x; or if, with the finite-difference
  active-set semantics reproduced, the two arms' iterates diverge beyond the
  declared tolerance — which would mean the two Jacobians are not the same
  object and the comparison is not a cost comparison at all.

- **Baseline:** [B0 — 2026-09-10](../../../../baselines/B0_2026-09-10.md),
  commit `345038a`, plus the cost profile in the brief. The reference arm is the
  unmodified `feasible_fd_jacobian` path at its production step of `1e-4`. The
  accuracy reference is
  [BIE-004](../../../../../results/validation/boundary_bie/BIE-004-20260915-coupled-02/README.md);
  the derivative itself is not re-qualified here, only extended in coverage and
  integrated.

---

## Intervention

One mechanism: the source of the residual Jacobian. Everything else — the
formulation, the discretisation, the gauge, the residual map, the damping
policy, the acceptance rule, the feasible set — is held fixed.

### The seam

The topology path takes finite differences in exactly one place. This was
verified, not assumed:

- `solvers/sdf_inverse/radial_topology.py:943` — `run_multiradial_fd_inverse`;
  its inner `jacobian()` closure at **`:1085`–`:1155`** is the only site. It
  returns `(matrix, basis, unresolved, one_sided)` with matrix shape
  `(2 · num_pairs · num_frequencies, 34)`.
- Callers: `solvers/sdf_inverse/topology_controller.py:710`
  (`bandwidth_refinement`), `:762` (`fixed_refinement`), `:867`
  (`candidate_refinement`), plus `run_top016_pilot.py:126` and
  `run_top017.py:293`. Both the H phase and the F continuation therefore go
  through this one function.
- `run_parameter_fd_inverse` (`solvers/sdf_inverse/optimization.py:947`) is
  **not** on this path — it serves the single-component Torch-implicit inverse.
  It is out of scope and must not be touched.

Three properties make the substitution exact rather than approximate:

1. `normalized_complex_residual` (`optimization.py:119`) is **affine** in the
   prediction — `(predicted − observed) / column_scales · sqrt(weights)`, where
   `column_scales` depends only on `observed`. The residual Jacobian column is a
   closed-form linear map of `dY`; no approximation is introduced by the
   residual layer.
2. The gauge-fixed set is a **linear** subspace of coefficient space
   (`curve_updates.py:1398`, `polar_angle_gauge_tangent_basis`, `lru_cache`d per
   bandwidth), so the retraction contributes no first-order correction along
   basis directions, and analytic columns are directly comparable to FD-measured
   ones.
3. The forward chain the optimizer uses is the same code BIE-004 differentiated:
   `predict_multicomponent_kress_paired_boundary_response`
   (`solvers/sdf_bem_multicomponent/forward.py:592`) → `_solve_paired_boundary:542`
   → `gpr_bem_kress.multicomponent.solve_multicomponent_kress_tmz_total_field_batch`.
   Acquisition is paired/diagonal (`np.diag(item.scattered_receiver)`), which
   BIE-004's `pair()` helper already handles.

### Stage 1 — promote the derivative

New `solvers/gpr_bem_kress/coupled_shape_derivative.py`, sitting beside
`multicomponent.py` exactly as `shape_derivative.py` sits beside `operators.py`.

This is a **graft, not a move**. The primal side of BIE-004 already calls
production unmodified; the derivative side calls production only at the
sub-primitive level and has no production counterpart at all — there is no
multi-component analytic derivative in `solvers/` today.

Promoted from `experiments/bie004_multi_derivative/operators.py`:

- `exterior_cross_jets` (`:45`) — the one genuinely new kernel differentiation,
  the jet counterpart of `multicomponent._exterior_cross_blocks_from_adapters`
  (`multicomponent.py:681`), which exists only as a primal.
- `component_jets` (`:24`) and `directional_operators` (`:66`) — the
  active/frozen block orchestration and the global
  `[[I−dK, dV], [−dT, I+dKp]]` assembly.
- Keep reusing `shape_derivative._difference_matrices` for self-blocks, as the
  experiment already does, and keep the per-call 2e-11 primal-reassembly
  self-check (`operators.py:133`). Three experiments now import the private
  `_Jet`/`_norm`/`_sum`/`_special`/`_stack` helpers; promoting them to a
  documented internal surface is in scope, changing their behaviour is not.

Also required:

- **A factor-exposing solve.** `solve_multicomponent_kress_tmz_total_field_batch`
  uses `np.linalg.solve` and `MultiComponentKressForwardResult` carries no LU
  factors, which is why BIE-004 had to write its own `lu_factor`/`lu_solve`
  (`support.py:197`). Add a sibling entry point that returns factors. Do **not**
  thread factors through `MultiRadialObjectiveEvaluation` in this experiment;
  instead let the analytic Jacobian re-solve its own base with factors retained.
  That spends one extra assembly to save 68, and keeps the change local.
- **The state bridge.** Promote `support.state_directions` / `state_boundary`
  (`experiments/bie004_multi_derivative/support.py:151`) — the
  `MultiRadialFourierState` → per-component `KressDirection` adapter, where a
  gauge basis row becomes a geometric direction.
- **Hoist geometry jets out of the frequency loop.** Jets are
  frequency-independent; production trains on four cumulative frequencies, so
  BIE-004's per-call construction would recompute them four times. This is upside
  the single-frequency benchmark could not see, and it must be reported
  separately from the 1.87x rather than silently folded into it.

### Stage 2 — wire it in

`solvers/sdf_inverse/radial_topology.py`:

- Add `jacobian_mode` to `run_multiradial_fd_inverse`, with `"fd"` preserving
  today's behaviour bit-for-bit and `"analytic"` selecting the new path. The
  default flips to `"analytic"` only after the Stage-3 and Stage-4 gates pass.
- **Keep the function name.** `experiments/top024/run.py:139` monkeypatches
  `m.rt.run_multiradial_fd_inverse`; renaming it breaks in-flight experiment code
  silently. Record the misnomer in the docstring instead.
- The analytic closure returns the same four-tuple. Per frequency: assemble and
  factor once, then for each basis direction build the per-component
  `KressDirection`s, form `dA`/`dB`/`dC`, tangent-solve `A dU = dB − dA U`,
  evaluate `dY = dC U + C dU`, take the paired diagonal, and apply the affine
  residual map.
- **Preserve the refusal contract.** The analytic path still evaluates the base
  state through `evaluate()`, so feature-radius, clearance and
  `feasibility_geometry_configs` refusals behave identically. What disappears is
  the *per-column* bookkeeping. Keep the
  `one_sided_jacobian_column_count` / `unresolved_jacobian_column_count` fields —
  the convergence gate at `radial_topology.py:1194` reads them, and deleting a
  counter a stopping rule depends on would silently change when the optimizer
  claims convergence.

### Stage 3 — Tier 1, saved-state equivalence

Cheapest first, and one part is free:
`results/validation/topology/TOP-023-20260915-181302-terminal-model/model.json`
already stores a measured **192 × 34 finite-difference Jacobian** at TOP-022's
terminal state, with its `basis`, `singular_values`, `reduced_gradient` and
`state_sha256`. Diffing the promoted analytic Jacobian against it costs no new
physical solves and is the first gate.

Then extend BIE-004's coverage — two states, one frequency, two components — to
the configuration production actually runs:

- all four cumulative training frequencies (0.5 / 0.75 / 1.0 / 1.25 GHz) with
  their weights, stacked as 192 rows. BIE-004 only ever exercised a single
  unweighted column, so the multi-column row ordering and the `sqrt(weights)`
  factor are genuinely untested;
- one, two and three components (`far-three-shapes` supplies three);
- K=9 per component and K=17 single-component (33 directions);
- 256 and 512 nodes;
- **states where the constrained stencil actually fires**, recovered from the
  H-phase trajectories that logged the 281 one-sided and 2 unresolved columns.

### Stage 4 — Tier 2, matched trajectory

From a saved state, run a bounded number of LM updates under both modes, with
the analytic arm reproducing the finite-difference active-set decisions. Assert
the iterates agree to the declared tolerance and record per-iteration wall clock.
This is what makes the claim *"same path, less time"* rather than *"different
run, different number"*.

Then repeat with the **true analytic column** and report where the trajectories
diverge, how many columns differ, and whether the endpoint improves.

### Stage 5 — Tier 3, bounded scene A/B

Scenes: `split`, `merge`, `central-ellipse-star`, `far-two-stars`. The first two
exercise topology events; `central-ellipse-star` carries the highest one-sided
count in the suite (55); `far-two-stars` is the standing hard recovery case.

**This is explicitly not a twelve-scene v1 performance claim.** The frozen
benchmark requires all twelve scenes with candidate and reference for a topology
performance claim, and this experiment does not make one. It makes a cost claim
at matched recovery on four scenes, and says so in the bundle.

---

## Constraint semantics — the decision, stated in full

At an active constraint the analytic column and the production feasible-FD
stencil disagree by construction. The finite-difference path either one-sides the
quotient — first-order accurate and biased, where the central quotient is
second-order — or, when both probes are refused, freezes the column to zero. The
governing test says it plainly: *"A probe the constraint refuses is not a
derivative of zero"* (`pytest/sdf_inverse/test_feasible_finite_differences.py`).
The analytic column has no sides to lose and is simply available.

Across TOP-020/022/025 this affects **281 one-sided and 2 unresolved columns**,
in twelve `topology/topology_passes.json` files and **no F-continuation file at
all** — the question is entirely about the H phase.

Three options were considered:

| Option | What it does | What it buys | What it costs |
|---|---|---|---|
| **A. Match FD** | reproduce the freeze/one-side decisions exactly | iterates coincide, so the claim is purely cost | temporarily keeps a known defect |
| **B. True analytic column** | exact derivative regardless of probe feasibility | removes the 283 degraded columns outright | trajectories diverge from all FD history; speed and direction effects confound |
| **C. Permanent FD semantics** | keep the fallback forever | strict drop-in, all history comparable | inherits a defect the analytic derivative need not have |

**Decision: B is the end goal, reached through A.** Stage 4 uses A to isolate the
saving, then measures B as a separate, attributable change and reports whether
it improves recovery. C is rejected: it would permanently reproduce a
finite-difference artefact in a path that has no finite differences in it.

Whether B improves the inverse is an **open question this experiment answers**,
not an assumption it is built on. A null or adverse result for B is a publishable
outcome and does not affect the cost result from A.

---

## Controls

Identical scenes, initial coefficients, observations, acquisition, materials,
frequency schedule, node schedule, damping policy, acceptance rule, feasible set
and recovery gates. The only difference between arms is `jacobian_mode`.

**Fix iterations, not call budgets.** Equal call budgets would hand the analytic
arm substantially more iterations and confound cost with progress. Both arms run
the same number of accepted updates, or the same stage schedule.

Sequential execution, single-thread BLAS (`OMP_NUM_THREADS=1` and siblings), no
concurrent numerical worker, hardware and load recorded at every arm boundary.
A concurrent run disqualifies the timing claim for the affected rows.

---

## Scope and shared interfaces

Write scope: `solvers/gpr_bem_kress/coupled_shape_derivative.py` (new), a
factor-exposing entry point in `solvers/gpr_bem_kress/multicomponent.py`, the
`jacobian_mode` dispatch in `solvers/sdf_inverse/radial_topology.py`, new
counters in `solvers/sdf_inverse/work_accounting.py`, a new
`experiments/spd001_analytic_jacobian/`, new tests under `pytest/`, and
speed-up-track documentation.

**Declared shared-interface changes**, per the collaboration rules — the topology
track's comparisons depend on all three:

1. **The default flips.** Every subsequent TOP experiment inherits the analytic
   path. `"fd"` remains available and tested.
2. **`work_accounting.COUNTERS` is a fixed tuple** and `record_work` raises on
   unknown keys, so adding `factorization_count` and `tangent_solve_count` is a
   shared edit, not an additive one.
3. **The unit of work changes.** A finite-difference Jacobian is `2 × 34`
   systems; an analytic one is one assembly plus one factorization plus 34
   directional assemblies and 34 tangent solves, per frequency. Therefore:
   - `jacobian_batch_callback` (`radial_topology.py:1100`) charges
     `1 + n_directions` assembly-equivalents, matching BIE-004's own conservative
     convention of charging one full assembly per directional recomputation.
     Every existing `solve_cap` then remains a valid conservative ceiling.
   - **Historical call counts stop being comparable across this change.** Every
     bundle spanning it must say so and give the conversion. This is a reporting
     obligation, not a footnote.

Nothing in this experiment changes a recovery gate, a tolerance, a scene, an
observation, or a historical bundle.

**Sequencing.** TOP-025 is mid-campaign in this checkout under a 7-hour watchdog
with up to four numerical workers. No file under `solvers/`, `experiments/` or
`results/` is touched and no numerical process starts until it completes and its
bundle is verified. Documentation is unaffected.

---

## Metrics and comparison criteria

- **Accuracy (Tier 1):** full-matrix and worst-column relative error against
  `1e-5` central FD, threshold `1e-4`, matching BIE-004's gates; primal
  reassembly to `2e-11`. Replay against TOP-023's stored Jacobian first.
- **Equivalence (Tier 2):** per-iteration coefficient difference between arms
  under option A, against a declared tolerance; count of columns where option B
  differs from A, and by how much.
- **Cost:** wall clock per arm, plus solve, factorization and tangent-solve
  counts, plus the measured derivative share `s` recomputed for the analytic arm.
  Report the realised speedup against the pre-registered 1.73x–1.79x.
- **Recovery (Tier 3):** boundary error (mm), IoU, training error, development
  error, object count, topology event margins, optimizer stop reason — every row,
  including failures, timeouts and refusals, retained.

---

## Compute budget and stopping rules

Declared before dispatch as hard ceilings, not targets, per
[implementation principles §5](../../../implementation_principles.md):

- Tier 1: assembly, factorization and directional-call caps plus a wall ceiling,
  sized from BIE-004's actual usage (703/800 assembly equivalents, 595 s).
- Tier 2: a fixed number of LM updates per arm, both arms counted.
- Tier 3: per-scene solve cap and wall ceiling per arm, mirroring the topology
  contracts' structure, with an outer per-scene `timeout` and a campaign
  watchdog.

Staged stopping: a failed Tier-1 accuracy gate stops before any inverse runs. A
failed Tier-2 equivalence gate stops before Tier 3. Failed attempts consume
budget; no silent extension, rerun or case replacement. Budget-limited runs are
reported as inconclusive within the declared budget.

---

## Artifacts

Fresh `results/validation/speedup/SPD-001-<timestamp>-analytic-jacobian/`, never
overwritten: frozen plan and inputs, source snapshots and SHA-256 hashes,
pre-dispatch test log and validation record, work ledger, accuracy and
equivalence tables, timing rows with declared hardware and load, per-scene
scorecards, retained failures, artifact manifest and a short verdict.

Registration: `results/catalog.csv`, `results/README.md`, the
[speed-up handoff](../../README.md), and a cross-reference from the topology
handoff recording the declared shared-interface change. Results open speed-up
iteration 02.

---

## Decision criteria

- **Adopt** — Tier-1 and Tier-2 gates pass, end-to-end speedup ≥1.3x on the
  measured scenes with non-overlapping ranges, and no adverse change in recovered
  geometry. The analytic path becomes the default; `"fd"` is retained as the
  validation reference.
- **Reject** — slower than FD in practice, or recovery regresses. Record it and
  stop; BIE-004's per-Jacobian result stands regardless, as a benchmark rather
  than a capability.
- **Investigate further** — faster but trajectory-divergent under option A, which
  would mean the two Jacobians differ where they should not, and is a correctness
  question before it is a cost one.

Option B is reported on its own terms and does not gate adoption of A.

---

## Known risks, recorded before execution

1. The 1.87x was measured at one frequency, one scene, one state. Four
   frequencies change the balance between factorization and directional
   assembly; jet hoisting should help, and the measurement decides.
2. BIE-004's FD arm used 69 factorizations where production uses 68, since the
   production base point is cached. The like-for-like per-Jacobian figure is
   about **1.84x**, not 1.87x.
3. `exterior_cross_jets` becomes production code with no primal counterpart to
   check against — its only validation is finite differences. BIE-004's
   1008-comparison operator screen must become a permanent test, not a one-off.
4. The derivative share was measured on FD runs. Once the Jacobian is cheap,
   everything else is a larger fraction, so 1.73–1.79x is an upper estimate for a
   repeat run rather than a floor.
5. Flipping a default changes the baseline under an active track. Mitigated by
   `"fd"` remaining exact and tested, and by the flip landing only after Tiers 1
   and 2 pass.

---

- **Owner:** `unassigned`. **Reviewer:** `unassigned`.

## Deferred

Material and source-strength derivatives; topology-event derivatives (the
derivative *of* a birth, death, split or merge, as distinct from the Jacobian
used during candidate refinement); off-subspace re-gauging; lossy and magnetic
media; parallelism across directions; the full twelve-scene v1 A/B; and the
shared experiment-harness refactor the three BIE experiment directories are
asking for.
