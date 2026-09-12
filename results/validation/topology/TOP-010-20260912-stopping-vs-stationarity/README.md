# TOP-010 — stopped, not stationary, and the geometry does not care

Executes the diagnostic proposed in the
[independent review](../../../../docs/iterations/topology/iteration_07/02_proposals/01_independent_review.md)
of TOP-008 and TOP-009.
[Plan](../../../../docs/iterations/topology/iteration_07/03_plan.md).

**Neither saved state is stationary. Both are halted by absolute constants that
are the wrong size at these loss levels.** Fixing that recovers 1.7× in the
objective using the **unmodified optimizer and no source change at all** — and
moves the reconstruction not at all.

Observations and saved states come from the
[TOP-008](../TOP-008-20260912-feasible-fd/README.md) and
[TOP-009](../TOP-009-20260912-bandwidth-capacity/README.md) bundles. No new
oracle solve, no controller default change, no new arm, no source change. Truth
and holdout scored results only after every training decision was final; neither
selected a direction, a start or a step.

## Stage A — terminal audit

At each state, the Jacobian is assembled with the feasible-side stencil at FD
steps 1.0e-4, 5.0e-5 and 2.5e-5, and steps are then probed along the normalized
negative-gradient and Levenberg–Marquardt directions at the optimizer's own
trust bounds, damping ladder and backtracking scales.

| | Ladder endpoint | Restart plateau |
|---|---:|---:|
| Production loss | 3.8613e-09 | 2.2755e-09 |
| Terminal ‖g‖∞ | 4.0134e-04 | 8.2449e-05 |
| …against the optimizer's 1.0e-07 gradient tolerance | **4013×** | **824×** |
| Gradient stability across FD scales | 3.4e-06 | 3.5e-06 |
| Jacobian rank | **34 / 34** | **34 / 34** |
| Condition number | 1.383e+05 | 1.205e+05 |
| One-sided / unresolved columns | 0 / 0 | 0 / 0 |
| Best LM step, relative to the acceptance margin | **10.29×** | **0.54×** |
| Feasible descent above the margin | **yes** | no |

**The gradient test could never have fired.** At the ladder endpoint the
terminal gradient is four thousand times the optimizer's own tolerance, stable to
3e-06 across three step scales, with a full-rank well-posed local model. The run
stopped on `loss_change_tolerance`, which — as the review identified — bounds
nothing about the gradient, because `_optimizer_config` uses the same absolute
`1e-10` for the loss target and the accepted loss change and that branch precedes
the gradient check.

**A descent direction was sitting there.** One LM step at the existing damping
cuts the objective by 1.0299e-09 — a **26.7% relative decrease** — with both
resolutions improving past the margin, and it works at every damping level in
the ladder.

## Stage B — restart continuation, unmodified optimizer

The cheapest possible intervention, requiring no source change: restart the
unmodified optimizer from the saved state under the recorded stopping rules, and
repeat until a restart makes no further progress.

| Restart | Iterations | Stop | Production loss | Relative decrease |
|---:|---:|---|---:|---:|
| *start* | | | 3.8613e-09 | |
| 0 | 3 | `loss_change_tolerance` | 2.6332e-09 | **31.8%** |
| 1 | 2 | `loss_change_tolerance` | 2.2755e-09 | **13.6%** |
| 2 | 1 | `loss_change_tolerance` | 2.2211e-09 | 2.4% — below margin, stop |

Three restarts, 627 solves, 45 seconds, **1.7× better objective**, zero source
change. Each one halted again on the same rule, and each time simply starting
over found more to do. That is an operational demonstration of premature
stopping, not an inference from a gradient probe.

## What actually binds

Three absolute constants sit at the same order of magnitude as the **entire
remaining objective**:

| Constant | Value | Role |
|---|---:|---|
| `loss_tolerance` | 1.0e-10 | absolute loss target **and** accepted loss change |
| `acceptance_absolute_margin` | 1.0e-10 | acceptance floor |
| *total remaining objective at the plateau* | *2.2755e-09* | |

A 1e-10 threshold is **4.3% of everything left to gain**. At the plateau the best
available LM step is 5.4379e-11 — genuinely downhill, and 0.54× the margin, so
it is refused. Twenty-five of the probes there are `decrease_below_margin`: not
an absence of descent, but descent the acceptance rule will not take. The
gradient is still 824× its tolerance and the Jacobian still full rank.

So the plateau is not stationarity either. It is an acceptance floor meeting a
very flat, ill-conditioned valley.

## The finding that matters more

**Geometry does not follow the objective here.** Across the whole of stage B:

| | Start | After 3 restarts |
|---|---:|---:|
| Production loss | 3.8613e-09 | 2.2755e-09 |
| Matched boundary error | 11.849 mm | **11.991 mm** |
| Union IoU | 0.7088 | **0.7088** |

A 1.7× improvement in the training objective moved the boundary error the wrong
way by 0.14 mm and left the IoU identical to four decimals. And 2.2755e-09 is
still **43,703×** above the 5.2068e-14 the true geometry attains.

Resolving the stopping rules entirely would therefore not recover these shapes.
At this scale the objective and the gated geometry are close to decoupled, which
is a statement about sensitivity and conditioning — and it is the thing that
actually blocks recovery.

## The gated stage was not implemented, deliberately

The review gated an optimizer option isolating loss-change stopping — a `1e-14`
absolute loss target — behind a separate review before numerical implementation.
Stages A and B make that option uninformative rather than premature: at the
plateau the **acceptance margin binds before the loss-change threshold**, so
disabling loss-change stopping would let the run grind out sub-margin steps
without changing what the acceptance rule accepts, and stage B already shows the
geometry does not respond across a 1.7× objective change. Implementing it now
would spend a reviewed source change to confirm something two unmodified runs
already establish.

That is a decision to report, not a gate to route around: the option remains
available and unreviewed, and anyone who wants it has the evidence above to argue
from.

## Decision criteria, as declared

| Criterion | Outcome |
|---|---|
| A stable measured descent direction rejects a stationarity claim | **Met at both states.** The "local minimum" reading of TOP-009 is refuted operationally |
| A lower objective from local continuation rejects the claim that a restart is already necessary | **Met.** Plain restarts recovered 1.7×, so no restart *mechanism* is yet warranted |
| If local progress stalls with unresolved FD estimates, resolve those first | Not applicable — zero unresolved and zero one-sided columns at both states |
| If stable local diagnostics find no descent, design a separate restart experiment | Not reached — descent exists at both states |

## Budget and verification

Declared before execution and respected: stage A used 224 and 239 solves against
a 500-per-state cap; stage B used 627 against 2500; 110 seconds total against a
600-second ceiling. Solves are counted by category at solver-call boundaries.

The [manifest](manifest.json) records 155 hashed numerical sources at commit
`b82ad3f`. `pytest/sdf_inverse` reports **581 passed** ([log](tests.log)).

This is analysis by the implementation owner, not independent scientific review.
Reviewer: unassigned.

[Stage A record](stageA_terminal_audit.json) · [script](stageA_terminal_audit.py) ·
[stage B record](stageB_restart_continuation.json) · [script](stageB_restart_continuation.py) ·
[execution log](execution_stageA.log)

Reproduce from the repository root:

```bash
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/stageB_restart_continuation.py
env PYTHONPATH=solvers /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/stageA_terminal_audit.py
```
