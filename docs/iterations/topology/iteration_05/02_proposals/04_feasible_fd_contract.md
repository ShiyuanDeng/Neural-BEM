# TOP-008 — feasible finite differences at an active constraint

Contract for rank 1 of the [literature verdict](03_literature_verdict.md). The
verdict accepts exactly one narrow correction now: **retain the derivative
information that is actually available on the feasible side of an active
constraint, and stop reporting convergence that was assembled from information
that was never measured.** Everything else it ranks is deferred or rejected,
and this contract implements nothing else.

## The defect, stated as code

`run_multiradial_fd_inverse.jacobian()` in
[radial_topology.py](../../../../../solvers/sdf_inverse/radial_topology.py) has
two faults, both local and both unambiguous:

1. **Shared abandonment.** The two retractions sit in one `try`. If either
   raises, both are discarded and the column is frozen to zero.
2. **Manufactured zeros.** If either evaluation returns `None`, the column is
   frozen to zero. A refused probe is evidence that a step is inadmissible, not
   evidence that the derivative vanishes. `matrix.T @ matrix` and
   `matrix.T @ residual` then consume a number nothing measured.

A third fault is in the stopping semantics. The `loss_change_tolerance` and
`relative_step_tolerance` branches already refuse to call a run converged while
columns are frozen; **both `gradient_tolerance` branches do not**. A gradient
whose small norm comes from zeroed columns is not a stationarity certificate.

## What the census already establishes

A geometry-only per-side census at the two saved guarded final states,
recorded before any implementation:

| Saved state | Gauge directions | Both sides feasible | Exactly one side | Neither side |
|---|---:|---:|---:|---:|
| `far-ellipse-star` (mode-9 component pinned) | 20 | 5 | **15** | **0** |
| `far-two-stars` (nothing pinned) | 6 | 6 | 0 | 0 |

This settles the open question the verdict flagged — it was *not* known that the
refused directions admit a usable one-sided stencil. They all do: every one of
the 15 is refused on exactly one side by the radius floor, and none is blocked
both ways. So the correction recovers every frozen column at this state rather
than some fraction of them.

It also separates the two accepted work items cleanly. `far-two-stars` has no
derivative defect at all; its failure is the rank-2 capacity problem and is out
of scope here.

**This is a statement about the derivative model, not about reconstruction.**
Recovering 15 columns does not establish that the resulting step decreases the
objective, that the pinned component moves, or that the scene passes.

## Intervention

One mechanism, opt-in, default off, named `feasible_fd_jacobian`:

- Attempt each retraction and each evaluation **independently**.
- Both sides usable → central difference, exactly as today, bit-for-bit.
- Exactly one side usable → the one-sided quotient on that side, using the
  actual scalar step that was taken.
- Neither side usable → the column is **unresolved**: still zero, but counted
  and reported under its own name, never conflated with a measured zero.
- `gradient_tolerance` may not declare convergence while unresolved columns
  exist, matching the two branches that already check.

Unchanged: the gauge and its tangent basis, the 8-mm radial certificate, the
production/refined admissibility rules and the refined feasibility guard, the
retraction, the step clipping, the damping ladder, the acquisition, mode counts,
topology candidate construction and acceptance, all margins, and every default.
The feasible set is **not** touched. This contract does not relax the floor, add
a headroom rule, or change what states are admissible — the verdict rejects the
first two as the next fix and the census gives no reason to revisit that.

## Stages, in order, each able to stop the line

**Stage 1 — is the derivative model valid?** No topology search. At the saved
`far-ellipse-star` final state (pinned) and the saved `far-two-stars` final
state (interior control), record for every gauge direction: both feasibility
verdicts and their refusal reasons, the actual perturbation size, the stencil
selected, and the derivative estimate. Check each estimate against a
**predeclared three-size sequence — 5.0e-5, 1.0e-4 (the configured step) and
2.0e-4 m** — and against an independently formed feasible directional
difference. Agreement means the one-sided estimates and the central estimates
for the same direction track each other across that sequence, and that the
interior control reproduces its central differences. Indefinite reduction of `h`
is not evidence and is not performed.

**Stop the line if** the estimates do not stabilise across the declared
sequence. That outcome says the derivative construction is unresolved, and it
does not license weakening the floor.

**Stage 2 — does a trustworthy model produce a feasible decrease?** One bounded
fixed-topology continuation from the saved `far-ellipse-star` state. At most the
existing 22 fixed iterations, the existing 600-second ceiling, and a declared cap
of **1200 BIE solves**. Require a genuine objective decrease at both
resolutions under the existing margin convention, and record whether the pinned
mode-9 component actually moves.

**A change of stop reason alone is a failure of the hypothesis**, not a result.
If training error improves while geometry or holdout error worsens, that is
reported as an optimization improvement and nothing more.

**Stage 3 — does it hold on the frozen benchmark?** All twelve unchanged v1
scenes, saved observations and initial states reused byte-for-byte, original
gates and per-scene limits. Arm **G** (guard only) against new arm **H** (guard
plus `feasible_fd_jacobian`). Report every gate separately, plus stop reasons,
exceptions, timeouts, BIE solve counts, and the new one-sided and unresolved
column counts. A comparison against the historical default A is not run here; G
is the reference the verdict names, and A stays the historical default.

## What would falsify this

Stage 1 estimates that will not stabilise; or stage 2 finding no feasible
decrease from a model whose columns are now measured. Either outcome is
recorded as a negative result for the narrow mechanism. Neither is grounds for
proceeding to relax the constraint, and neither is evidence about rank 2.

The honest prior: the census proves the columns are recoverable and says
nothing about whether the recovered step escapes. The verdict's own confidence
here is **medium** for escaping the ellipse-star stall and **low** for the suite.
This contract is written to find out which, not to confirm either.

## Artifacts

Fresh bundle `results/validation/topology/TOP-008-20260912-feasible-fd/` with a
manifest and source hashes, the stage-1 per-direction record as JSON, the
stage-2 trajectory, the stage-3 suite metrics, an `analyze.py` that regenerates
the report and verification from saved artifacts, and a test log. No hashed
source is edited while any suite is running.
