# Refined feasibility and shape capacity — next discriminating checks

[Iteration 04 results](../01_results.md) left three questions. This guide turns
the first two into experiment contracts and states what each one decides. The
third — information beyond the training frequency — needs a declared frequency
schedule and is not proposed here.

## What the benchmark failures actually are

Four of the twelve-scene runs aborted. The cause is now located exactly. In
`far-ellipse-star` and `empty-ellipse-star` the fixed-topology optimizer drove
two born components to a separation the **production** discretization measures
as admissible and the **refined** discretization does not:

| Discretization | Measured minimum clearance | Solver floor |
|---|---:|---:|
| 64 nodes (production) | 1.000359e-02 m | 1.0e-02 m |
| 128 nodes (refined) | 9.971374e-03 m | 1.0e-02 m |
| 256 nodes | 9.961368e-03 m | 1.0e-02 m |

An inscribed polygon overstates the gap between two components, and it
overstates it more at 64 nodes than at 128. The optimizer is therefore free to
park a state on its own feasibility boundary, where the next refined evaluation
— `refined_base`, which is not inside any `try` — raises and kills the run.
The saved checkpoints reproduce this without rerunning any physics
([bundle](../../../../../results/validation/topology/TOP-006-20260911-scenes-v1/README.md)).

Two facts follow. The separation floor is not the problem: the true curves are
genuinely closer than 10 mm, the sequence above converges from above, and
relaxing the floor would hide a real quadrature limit. And the feasible set the
optimizer searches is not the feasible set the controller then evaluates on.

The second failure class is different in kind. Birth seeds are circles of mode
one, and the fixed-topology optimizer moves only the parameters a component
already has. A component born as a circle can never become an ellipse or a
star. `far-two-stars` finds the right count and the right places and returns two
circles; the ellipse/star scenes show the same limit wherever they get far
enough to show anything.

## TOP-007 — refined-discretization feasibility inside the optimizer

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Question:** does requiring every accepted optimizer step to be admissible
  at the refined discretization, not only the production one, remove the
  uncaught refined-separation aborts without changing runs that never approach
  the floor?
- **Falsifiable hypothesis:** wrong if guarded runs still abort on refined
  geometry, or if any scene that is unaffected by the guard returns a different
  trajectory, or if a scene that passed in TOP-006 stops passing.
- **Baseline:** TOP-006 (`116b9b3`) on `config/topology_scenes_v1.json`, with
  its observations and initial states reused byte-for-byte.
- **Intervention:** one mechanism. A trial state is feasible for
  `run_multiradial_fd_inverse` only if its boundary passes the multicomponent
  adapter's curve, topology and clearance checks at *both* the production and
  the refined discretization. The extra check is geometry only — no forward
  solve — so it costs curve evaluations, not BIE solves. Behind the same opt-in
  flag, a state that is still refined-inadmissible rolls back to the last
  refined-feasible state, and a refined base evaluation that raises anyway
  stops the run with a reason instead of an uncaught exception.
- **Controls:** the v1 scenes, acquisition, materials, 64/128 nodes, raster,
  iteration and event budgets, candidate budgets and all five gates unchanged.
  Both arms run `include_simplest_candidate=False`; the guard is the only
  difference. Default behaviour stays off, so every existing result and test
  keeps its meaning.
- **Scope and shared interfaces:** `solvers/sdf_inverse/radial_topology.py`
  (new admissibility predicate, new optional optimizer argument),
  `solvers/sdf_inverse/topology_controller.py` (new config flag and its
  guarded paths), the two drivers' flags and arms, and tests. No geometry
  state, objective, solver interface or default is changed.
- **Metrics and comparison criteria:** all twelve scenes, arm A (reference) and
  arm G (guarded), reporting every gate, stop reason and BIE solve count.
  Additionally: number of runs aborting with an uncaught exception; number of
  optimizer trials rejected by the guard; and, for every scene where no trial
  is rejected, whether the two arms agree exactly.
- **Compute budget and stopping rules:** 24 inversions, four single-thread
  workers, ten-minute per-inversion ceiling, 45-minute suite ceiling. Timeouts
  and exceptions are outcomes, not reasons to retry.
- **Artifacts:** fresh `results/validation/topology/TOP-007-20260911-refined-feasibility/`.
- **Decision criteria:** adopt as the default if no guarded run aborts, every
  guard-inert scene reproduces arm A exactly, and no TOP-006 pass is lost.
  Reject if the guard changes untouched scenes. Investigate further if aborts
  become timeouts with no other change — that is progress in reporting only.
- **Owner:** Claude. **Reviewer:** unassigned.

## TOP-008 — shape capacity after birth

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Question:** does a data-driven bandwidth promotion for surviving
  components recover noncircular shapes the current controller can only place
  circles at?
- **Falsifiable hypothesis:** wrong if promotion does not reduce matched
  boundary error on `far-two-stars` and the ellipse/star scenes, or if it
  degrades the circular controls, or if its cost is not repaid.
- **Intervention (one mechanism):** when a fixed-topology refinement stalls
  with a component still at its birth bandwidth, raise that component's
  bandwidth by one step and continue, accepting the promotion only on the same
  cross-resolution decrease rule that governs topology events. No truth shape,
  count or schedule enters the decision.
- **Depends on:** TOP-007. Promotion lengthens runs, and a longer run on the
  current code is a run more likely to abort on refined geometry.
- **Owner:** unassigned. **Reviewer:** unassigned.

Neither contract changes the frozen v1 benchmark, its data, its budgets or its
gates. TOP-002–TOP-004 remain deferred.
