# Speed-up track: start here

This is the handoff for agents working on the **cost of the inverse**. Read the
current state below before choosing work. The shared folder convention, approval
rule, experiment-contract template and collaboration rules are in the
[iterations README](../README.md).

## Research question and scope

> **Where does the inverse actually spend its time, and which of that can be
> removed without changing what it recovers?**

The track is organised around that question, not around one mechanism. The
analytic Jacobian is the case in hand, but preconditioning, cheaper line
searches, reduced acquisition, warm starts and parallelism are the same
question.

**The scope boundary is deliberate and narrow: this track changes cost at fixed
recovered geometry.** A change that alters the formulation, the discretisation,
the feasible set or what the optimizer converges to is not a speed-up result,
even if it happens to be faster — it belongs to
[Boundary–BIE](../boundary_bie/README.md) or [topology](../topology/README.md).
The three resolutions that track distinguishes — `K_gamma`, `K_u`, `N` — are not
this track's variables.

Two consequences follow, and both are binding:

1. **Every cost claim carries a matched recovery claim.** "Faster" with a
   changed endpoint is not a result of this track; it is an uncontrolled
   comparison. Where a faster mechanism does change the trajectory, the change
   must be measured and attributed separately from the saving.
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

The short version: in every production topology run measured so far,
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

Updated 2026-09-16.

| Item | Current state |
|---|---|
| Active iteration | Iteration 03 — [default promotion and complete pipeline timings](iteration_03/01_results.md) |
| Stage | **SPD-002 COMPLETE / PASS** — fast analytic CPU default; complete death/split pipelines are 1.86x/1.89x faster, both recover |
| Approved experiment IDs | **SPD-001** (2026-09-15), **SPD-002** (2026-09-16 direct default-promotion instruction) |
| Next expected action | Use the fast default for current Cartesian topology runs; reference profile remains available. Broader scene coverage is a separate validation scope |
| Owner / reviewer | Codex `/root` / self-review; no independent reviewer claimed |
| Dependencies | 261 tests pass; four complete pipeline arms pass recovery, geometry, counts and integrity checks; numerical defaults are now fast analytic CPU |
| Blockers | None at dispatch: TOP-025 and renderer exited; PASS verification and all 774 artifact hashes checked before numerical edits |
| Git scope | Existing checkout, branch `feature/ordered-boundary-nystrom`. Ask the user explicitly before any new branch or worktree, even in full-access mode |

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
   - `experiments/bie004_multi_derivative/operators.py` — the coupled derivative
     as it exists today;
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
- **Fix iterations, not call budgets, in an A/B.** Equal call budgets hand the
  cheaper arm more iterations and confound cost with progress.
- **Report the share, not only the speedup.** A mechanism that halves 5% of the
  runtime is not a result; the profile is what makes a number meaningful.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| 01 | Cost profile and combined analytic/CPU/CUDA plan | `SPD-001` COMPLETE under the combined [plan](iteration_01/03_plan.md) |
| 02 | Measured runtime and matched one-update evidence | SPD-001 [closeout](iteration_02/01_results.md); subsequent SPD-002 default-promotion plan COMPLETE |
| 03 | Fast default and complete topology/continuation controls | [SPD-002 closeout](iteration_03/01_results.md): death/split 1.86x/1.89x faster with matched recovered boundaries |
