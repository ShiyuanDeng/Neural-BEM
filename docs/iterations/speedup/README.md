# Speed-up track: start here

This is the handoff for agents working on the **cost of the inverse**. Read the
current state below before choosing work. The shared folder convention, approval
rule, experiment-contract template and collaboration rules are in the
[iterations README](../README.md).

## Research question and scope

> **How can the complete inverse reach the required reconstruction quality
> with less total time and fewer failed attempts?**

The track is organised around that question, not around one mechanism. The
analytic Jacobian is the case in hand, but preconditioning, cheaper line
searches, reduced acquisition, warm starts and parallelism are the same
question.

**Scope clarification, 2026-09-16:** the user explicitly requested an outsider's
big-picture view of what can change in the pipeline. The discussion now includes
initialization, representation, topology/shape scheduling, intermediate physics
accuracy, data selection, optimization and stopping. This supersedes the earlier
restriction of proposals to executing the same pipeline faster. Keep shared
mechanism changes visible to [Boundary–BIE](../boundary_bie/README.md) and
[topology](../topology/README.md); their ownership is not a reason to omit an
architectural opportunity from this handoff.

Two consequences follow, and both are binding:

1. **Every cost claim carries a matched quality claim.** Execution changes
   compare the same algorithm and recovered geometry. Pipeline redesigns may
   change intermediate states, schedules and iteration counts; compare time
   and success rate at the same final accuracy requirements and data access.
   Declare which comparison is being made and retain failures. SPD-001/002's
   historical contracts and results are unchanged.
2. **Solve-count savings and controlled wall-clock savings are different
   claims.** The iterations README already requires this distinction; here it is
   the primary output, so concurrency and machine load are declared for every
   timing row.

## Baseline

[B0 — 2026-09-10](../../baselines/B0_2026-09-10.md). Commit `345038a` on
`feature/ordered-boundary-nystrom`. B0 pins the forward, the optimizer and the
gauge; this track adds one thing B0 does not record — a **cost profile**, the
measured breakdown of where forward solves are spent. That profile is in
[the iteration-01 brief](iteration_01/02_proposals/01_cost_profile_and_analytic_jacobian_brief.md)
and is derived from existing work ledgers, with no new numerical work.

The historical FD profile: in the production topology runs measured for that brief,
**90.7%–95.1% of all forward solves are finite-difference Jacobian probes.**
Nothing else in the run is close. That single number is why this track exists and
why the analytic Jacobian is its first candidate.

## Prior art this track cites but does not own

- [BIE-004](../../../results/validation/boundary_bie/BIE-004-20260915-coupled-02/README.md)
  — `ANALYTIC_JACOBIAN_QUALIFIED_AND_FASTER`. The coupled analytic shape
  Jacobian, qualified on two saved two-star states at 1.4e-7 relative error and
  measured at 1.87x per full Jacobian. Its own closeout recommends exactly one
  next action: "prepare one opt-in integration and matched inverse validation."
  **`SPD-001` is that action.** The derivative itself remains BIE's result.
- [BIE-006](../../../results/validation/boundary_bie/BIE-006-20260915-205942-operator-reuse/README.md)
  — `STOP_FIRST_ORDER_OPERATOR_REUSE`. A closed negative result: solving
  first-order approximated operators neither widened the accurate region nor
  produced a qualifying saving. This track does not reopen first-order operator
  surrogates without new grounds, and cites the result so that a future proposal
  cannot rediscover it as if it were open.

Neither result is re-litigated here. Moving `SPD-001` into this track does not
renumber, move or supersede any Boundary–BIE iteration.

## Current handoff

Updated 2026-09-17.

| Item | Current state |
|---|---|
| Active iteration | Iteration 07 — [SPD-007 default promotion](iteration_07/01_results.md), following the SPD-006 full-inverse qualification |
| Stage | **SPD-007 COMPLETE / DEFAULT PROMOTED**, authorized by the user’s “yes” on 2026-09-17. Compiled + reciprocal + readiness is now the normal full-inverse path. Earlier sealed results are unchanged |
| Approved experiment IDs | **SPD-001**, **SPD-002**, **SPD-004**, **SPD-005**, **SPD-006**, **SPD-007** (direct “yes” to default promotion, 2026-09-17) |
| Next expected action | Qualify geometry-validation reuse and separately compare the true-analytic constraint policy. The [concrete follow-up](iteration_05/02_proposals/02_geometry_cost_followup.md) identifies reusable component checks/adapters and certified separation. No new numerical follow-up has been dispatched |
| Owner / reviewer | Codex `/root` / self-review; no independent reviewer claimed |
| Dependencies | SPD-007: 249 tests pass (one CUDA skip); 2/2 fresh default-CLI workers recover with exactly matching prior endpoints/steps; 312 artifact hashes verify. SPD-006: 33 compiled qualification checks, 1340 angular checks and 16/16 recovered workers. Maximum paired boundary difference 1.047e-13 m; original source/input hashes and work counts verify |
| Evidence limits | SPD-007 checks dispatch/quality; no new matched speedup claim. SPD-006 measured four noiseless scenes with two workers per arm/scene and one profiled update. Host-wide isolation unverified. No all-scene, noisy-data or GPU speedup claim |
| Git scope | Existing checkout, branch `feature/ordered-boundary-nystrom`. Ask the user explicitly before any new branch or worktree, even in full-access mode |

### Current default: compiled + reciprocal + readiness

[SPD-007](iteration_07/01_results.md) promotes the qualified setup to the normal
full pipeline. No extra flag is needed. `compiled` supplies guarded reciprocal
Jacobians and reduced multi-object fits; TOP-025 checks training-only readiness
before continuation and always retains independent endpoint checks. Unready
states run the existing schedule. Single objects, coarse grids and unsupported
compiled states retain their validated fallbacks. `--inverse-runtime fast`,
`reciprocal`, and `reference` retain the comparison paths without readiness.
An explicit environment setting or Python context still overrides the default.

### Latest result: compiled Kress helps, but geometry still dominates an update

[SPD-006](iteration_06/01_results.md) integrates the BIE-005 nodal scattering
compiler as `--inverse-runtime compiled` / `SDF_INVERSE_RUNTIME=compiled`.
All 16 matched fresh full workers recover. Median complete runtimes, with the
same readiness shortcut in both arms, are:

| Scene | Reciprocal + readiness | Compiled + readiness | Time reduction |
|---|---:|---:|---:|
| Death | 46 s | 46 s | Unchanged |
| Merge | 2m52s | 2m52s | Unchanged |
| Central ellipse/star | 18m18s | 17m29s | 4.5% |
| Two stars | 22m48s | 21m32s | 5.6% |

The full gauge, controller and geometry/constraint rules are preserved.
For those SPD-006 measurements, compiled continuation was opt-in and readiness
was enabled by the experiment wrapper. SPD-007 now makes their combination the
default; coarse topology and independent validation retain full Kress. The 2.48x local-fit prototype result does not transfer to
the full inverse. No full twelve-scene compiled runtime has been measured.

A compiled central-case update spends **88.5% of its profiled 26.96 seconds in
legacy stencil-feasibility checks**, versus 0.50 seconds in the compiled
evaluator. This is one update, not a whole-inverse percentage. The
[geometry follow-up](iteration_05/02_proposals/02_geometry_cost_followup.md)
therefore comes before GPU work. Exact validation reuse and the separate
true-analytic constraint-policy comparison are the next targets.

### Previous result: reciprocal Kress exposes geometry-validation cost

The user's “then go” authorized SPD-005. The
[completed results](iteration_05/01_results.md) establish a guarded production
integration and matched full-inverse gains. Use `--inverse-runtime reciprocal`
or `SDF_INVERSE_RUNTIME=reciprocal`; `fast` remains the operator comparison.
Below 128 nodes the new runtime uses the existing operator derivative, so the
current 64-node topology search is unchanged. The remaining-cost profile now
puts geometry/admissibility reuse and the FD-compatible policy ahead of GPU
work. The 94.6% stencil-check share applies to the one profiled continuation
stage, not the entire inverse.

### Compiled scattering review that led to SPD-006

The user-requested [BIE-005 compiled-version review](iteration_05/02_proposals/01_compiled_scattering_integration_review.md)
recommends the **nodal-compiled deformation backend with fresh changed-shape
compilation**; the subsequent “go” authorized [SPD-006 execution](iteration_05/03_plan.md).
Its noisy four-object local inverse takes 0.242 s versus 0.602 s
for accuracy-qualified full reciprocal Kress. The review found all 54 saved fits
converged and matched 43 benchmark source hashes. Saved-coefficient checks show all eight
TOP-025 handoffs satisfy the prototype's bounding-circle requirements.
SPD-006 subsequently qualified angular resolution and the full production
shape derivatives, then measured the complete workers above.

The review called for an opt-in continuation backend preserving the Cartesian
chart and optimizer, with full Kress for topology fields and final validation. Native
Laurent compilation and local linear models are slower than fresh compiled
Kress in these tests. Geometry-validation work stays a priority because the
compiled solver does not remove stencil feasibility checks. These local fits
are not a new full-topology runtime claim. SPD-006's production qualification
passed; its matched full workers are complete. The review remains the record
of why the nodal backend was selected.

### Earlier priority revision: reciprocal Kress derivatives

This was the recommendation before SPD-005; its executed results are above.

The user's follow-up prompted a review of the latest
[Boundary–BIE coupled results](../boundary_bie/iteration_05/02_coupled_modes_and_measurements.md).
**Qualify and integrate reciprocal derivatives with the existing nodal Kress
forward first, then remeasure the combined pipeline.** The single-object
controls show 18.8–19.0x faster fitting than the nodal operator-derivative
control, with matched evaluation counts; the coupled nodal derivative agrees
with a refined operator reference to about 4e-14. The current 16 experimental
tests pass. This evidence has not yet established a full automatic-topology
speedup, and the published fitting times exclude final validation.

The derivative change can help inner fits throughout topology search and
continuation. It removes much of the work targeted by old assembly/GPU
proposals, and overlaps SPD-004's skipped Jacobians: **do not multiply the
reported speedup factors**. Keep readiness as a compatible outer decision and
measure its incremental benefit after the derivative change. See the
[priority review](iteration_04/02_reciprocal_derivative_priority_review.md) for
scope, provenance, numerical qualification and the revised sequence.

### Further acceleration: 2026-09-16 investigation

The user's latest clarification puts **pipeline architecture** first. Read the
[outsider view](iteration_03/02_proposals/03_pipeline_redesign_outsider_view.md)
before selecting a local optimization: it asks which entire fits or stages
can be avoided, what simpler models should run first, and how progress should
choose the next action. [SPD-004](iteration_04/01_results.md) now measures the
first architectural intervention: check full-training readiness before launching
mandatory continuation. It removes 340 derivative assemblies on each measured
easy case while retaining independent endpoint assessment. The completion
contract explicitly leaves skipped stage exposure and stationarity unmeasured.

| Full inverse | Fast CPU baseline | Experimental readiness | Additional speedup |
|---|---:|---:|---:|
| death | 236.26 s | 46.12 s | 5.12x |
| split | 222.32 s | 33.10 s | 6.72x |
| merge | 406.34 s | 403.52 s | Effectively unchanged; one fallback pair |

Death/split use medians of two pairs each. All original reconstruction gates
pass and all paired final coefficients and sampled boundaries agree exactly.
Merge still needs continuation: the screen adds eight physical systems, with
its small observed runtime difference within the uncertainty of a single pair.
These ratios compare against the already accelerated analytic CPU pipeline;
do not multiply them by historical FD ratios or extrapolate to all scenes.

The earlier implementation-level
[ranked brief](iteration_03/02_proposals/01_further_full_inverse_speedups.md)
records eight candidates, including CPU parallelism and GPU assembly. Its
evidence remains useful:

- In both saved full fast cases, all four continuation stages differentiate
  the same boundary. Exact per-frequency reuse could reduce their continuation
  derivative assemblies from 340 to 136. This is a work-count opportunity,
  not a measured runtime improvement.
- At a new geometry, unchanged special-function values are recomputed for each
  Jacobian direction. Derivative assembly consumed 85.3% of the saved fast-CPU
  update, while CUDA linear algebra reduced that update's wall time by only
  2.2%. A useful GPU successor should address assembly itself.

SPD-003 proposed a narrower reuse comparison against the then-current fast default
and remains unexecuted. SPD-004's saved all-scene audit finds a different next
priority for harder cases: final-grid feasibility can fail after expensive
topology fitting, and unsuccessful candidate refinements can consume hundreds
of historical FD systems. Bring future numerical requirements into topology
acceptance and investigate when to change topology, frequency information or
shape capacity. These are proposed search changes, not measured recovery gains.
After removing unnecessary continuation, topology dominates the measured easy
cases; reprofile that remaining work before selecting GPU implementation work.

## Concurrency: why this track waits

The repository rule is that no two agents modify the same working checkout at
the same time, and that controlled wall-clock claims declare machine load.
Both bind here harder than usual, because this track's *output is a timing
number*.

TOP-025 and its video renderer finished before SPD-001 numerical edits began.
Its PASS verification and all 774 final artifact hashes were checked first.
SPD-001 arms run sequentially, with frozen source hashes and process checks at
every arm boundary. Future controlled timings need the same isolation:
overlapping numerical work would invalidate both runs' machine-load conditions.

## Reading order

1. This handoff.
   For current next work, read the [SPD-006 results and profile](iteration_06/01_results.md),
   the [concrete geometry follow-up](iteration_05/02_proposals/02_geometry_cost_followup.md),
   then the [SPD-005 results and profile](iteration_05/01_results.md),
   then the [reciprocal Kress priority review](iteration_04/02_reciprocal_derivative_priority_review.md),
   then the [SPD-004 results](iteration_04/01_results.md)
   and linked architecture audit, then the
   [outsider architecture brief](iteration_03/02_proposals/03_pipeline_redesign_outsider_view.md),
   then the [implementation options](iteration_03/02_proposals/01_further_full_inverse_speedups.md)
   and [SPD-003 proposal](iteration_03/02_proposals/02_SPD003_exact_continuation_reuse_contract.md).
2. [The iteration-01 brief](iteration_01/02_proposals/01_cost_profile_and_analytic_jacobian_brief.md)
   — the cost profile, and why the Jacobian is the first candidate rather than
   parallelism or a cheaper line search.
3. [The `SPD-001` contract](iteration_01/02_proposals/02_SPD001_contract.md).
4. [Baseline B0](../../baselines/B0_2026-09-10.md) — §5 (acceptance and stopping
   rules), §6 (what the two optimizer paths actually are), §8 (limitations).
5. Mechanism sources, in this order:
   - `solvers/sdf_inverse/radial_topology.py:943` — `run_multiradial_fd_inverse`,
     and its `jacobian()` closure at `:1085`–`:1155`, the only place finite
     differences are taken on the topology path;
   - `solvers/sdf_inverse/topology_controller.py:710`, `:762`, `:867` — its three
     callers;
   - `solvers/sdf_inverse/analytic_jacobian.py` — the production bridge and guarded runtime dispatch;
   - `solvers/gpr_bem_kress/reciprocal_shape_derivative.py` — reciprocal coupled trace contractions;
   - `solvers/gpr_bem_kress/coupled_shape_derivative.py` — the discrete operator derivative and shared base solve;
   - `solvers/gpr_bem_kress/shape_derivative.py` — the production
     **single-interface** analytic derivative the coupled version extends.
6. [The frozen topology scene benchmark](../../benchmarks/topology_scenes.md) —
   what a *topology performance* claim requires, which a bounded speed-up
   comparison is explicitly not.

## Starting work on this track

A speed-up experiment is proposed, reviewed, agreed and then approved by name,
exactly as elsewhere: see the gate table in the [iterations README](../README.md).
Without gate 4 an agent may read, review, propose and write documents, and may
**not** change numerical code, alter an experiment configuration, or launch a
run.

Three additional rules specific to this track:

- **Declare the unit of work before comparing arms.** A mechanism that changes
  what one "solve" costs makes historical call counts incomparable. Say so in
  the bundle, and give the conversion.
- **Match controls to the claim.** For execution-only A/B tests, fix iterations
  rather than call budgets: equal call budgets can grant the cheaper arm extra
  progress. For pipeline redesign, compare time to the same quality target
  and success under the same outer time limit; changed iteration counts and
  schedules are part of the declared intervention.
- **Report the share, not only the speedup.** A mechanism that halves 5% of the
  runtime is not a result; the profile is what makes a number meaningful.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| 01 | Cost profile and combined analytic/CPU/CUDA plan | `SPD-001` COMPLETE under the combined [plan](iteration_01/03_plan.md) |
| 02 | Measured runtime and matched one-update evidence | SPD-001 [closeout](iteration_02/01_results.md); subsequent SPD-002 default-promotion plan COMPLETE |
| 03 | Fast default, full pipeline controls and further acceleration | [SPD-002 closeout](iteration_03/01_results.md): death/split 1.86x/1.89x faster; latest [outsider architecture brief](iteration_03/02_proposals/03_pipeline_redesign_outsider_view.md) broadens the earlier CPU/GPU and SPD-003 exact-reuse proposals |
| 04 | Training-only readiness and full-pipeline architecture audit | [SPD-004 closeout](iteration_04/01_results.md): additional 5.12x/6.72x full-runtime speedups on death/split, preserved merge fallback, and a twelve-scene audit of next architectural changes |
| 05 | Guarded reciprocal Kress integration and compiler review | [SPD-005 closeout](iteration_05/01_results.md): all 18 workers recover; reciprocal fitting and readiness improve full runtime, with geometry checks exposed as remaining cost |
| 06 | Compiled Kress continuation in complete inverse workers | [SPD-006 closeout](iteration_06/01_results.md): all 16 workers recover; 4.5%/5.6% additional hard-case time reductions, with geometry/constraint work still the next priority |
| 07 | Promote the qualified full-pipeline default | [SPD-007](iteration_07/01_results.md): compiled + reciprocal + readiness, with comparison profiles and fallback/reporting checks |
