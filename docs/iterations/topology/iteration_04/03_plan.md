# TOP-007 — refined-discretization feasibility in the fixed-topology optimizer

- **Approval status:** APPROVED under the user's 2026-09-11 direction to take
  Track A as far as possible and to continue from the latest fixes.
- **Execution status:** IN PROGRESS.
- **Owner:** Claude. **Independent reviewer:** unassigned.
- **Baseline:** `116b9b3` (TOP-006) on `feature/ordered-boundary-nystrom`.
- **Branch:** continue `feature/ordered-boundary-nystrom`; no new branch, no
  concurrent implementation track.
- **Proposal:** [guide](02_proposals/01_feasibility_and_shape_capacity.md) ·
  **Review:** [decisions](02_proposals/02_feasibility_review.md).

## Question and frozen comparison

Four TOP-006 runs died on a state the production discretization calls
admissible and the refined one does not. Does requiring both resolutions inside
the optimizer remove those aborts while leaving every unaffected run exactly as
it was?

Two arms on the frozen v1 matrix: **A**, the current default, and **G**, the
same policy with `refined_feasibility_guard=True`. Twelve scenes, 24 Cartesian
inversions, observations and initial states copied byte-for-byte from the
TOP-006 bundle through `--reference-data` with zero new oracle solves. The
0.5-GHz training acquisition, 1.5/2.5-GHz evaluation-only holdout, materials,
64/128 production/refined nodes, raster 121, 22 fixed iterations, three
candidate steps, ten cycles, seven events, candidate cap 48 and tolerance
0.003 are unchanged, and so are all five success gates. `include_simplest_candidate`
is `False` in both arms.

## Intervention

One mechanism, opt-in, default off: a trial state is feasible for
`run_multiradial_fd_inverse` only if its boundary passes the multicomponent
adapter at the refined discretization as well as the production one. The check
is geometric and performs no forward solve. Two guarded consequences follow it:
a state that is refined-inadmissible on entry to a cycle rolls back to the last
refined-feasible state, and a refined base evaluation that raises anyway ends
the run with stop reason `refined_infeasible` rather than an uncaught
exception. With the flag off, every code path, work count and recorded field is
what it was at `116b9b3`.

## Measures, budget and artifacts

Report all twelve scenes for both arms with every gate separately, plus stop
reasons, BIE solve counts, guard-rejected trial counts and the minimum refined
clearance of each final state. Three specific checks decide the experiment:
no guarded run aborts with an uncaught exception; every scene in which the
guard rejects nothing reproduces arm A's final state exactly; and no TOP-006
pass is lost. Arm A is rerun rather than copied, and its outcomes are checked
against the TOP-006 rows.

Maximum 24 inversions, four single-thread subprocess workers, ten-minute
per-inversion timeout, 45-minute suite wall ceiling. Timeouts and exceptions
are recorded outcomes. Elapsed times are not a controlled speed comparison;
solve counts for aborted runs are lower bounds.

Touch only `solvers/sdf_inverse/radial_topology.py`,
`solvers/sdf_inverse/topology_controller.py`, the two topology drivers, new
tests and documentation. No scene, gate, budget, default or solver-interface
change. Artifacts: fresh
`results/validation/topology/TOP-007-20260911-refined-feasibility/`. Results
open iteration 05.
