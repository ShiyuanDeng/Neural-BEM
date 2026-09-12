# Topology iteration 08 — the optimizer was stopped, and the shapes still did not move

TOP-010 completed on 2026-09-12, executing the diagnostic the
[independent review](../iteration_07/02_proposals/01_independent_review.md)
proposed.
[Full results](../../../../results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/README.md).
No source change, no controller default change, no new arm, no new oracle solve.

## The result

**Neither saved state is stationary.** Both are halted by absolute constants that
are the wrong size at these loss levels. Three restarts of the **unmodified**
optimizer recover 1.7× in the objective — and move the reconstruction not at all.

## Stopped, not stationary

At the TOP-009 ladder endpoint the terminal gradient is ‖g‖∞ = 4.0134e-04,
**4013× the optimizer's own 1.0e-07 tolerance**, stable to 3e-06 across FD steps
1.0e-4 / 5.0e-5 / 2.5e-5, with a full-rank 34/34 Jacobian and zero one-sided or
unresolved columns. A single LM step at the existing damping cuts the objective
by 26.7%, with both resolutions improving past the margin.

The run stopped on `loss_change_tolerance`, which bounds nothing about the
gradient — exactly as the review said, because `_optimizer_config` uses the same
absolute `1e-10` for the loss target and the accepted loss change, and that
branch precedes the gradient check.

Restarting the unmodified optimizer three times gives 31.8%, 13.6% and 2.4%
relative decreases, 3.8613e-09 → 2.2755e-09, in 627 solves and 45 seconds. That
is premature stopping demonstrated operationally, not inferred.

## What binds, precisely

Three absolute constants sit at the same order as the entire remaining
objective: `loss_tolerance = 1e-10` serving as both the loss target and the
accepted loss change, and `acceptance_absolute_margin = 1e-10` as the acceptance
floor — against a plateau objective of 2.2755e-09. **A 1e-10 threshold is 4.3%
of everything left to gain.**

At the plateau the best available LM step is 5.4379e-11: genuinely downhill, and
0.54× the margin, so it is refused. Twenty-five probes there are
`decrease_below_margin` — not an absence of descent, but descent the acceptance
rule will not take, while the gradient is still 824× its tolerance and the
Jacobian still full rank. The plateau is an acceptance floor meeting a flat,
ill-conditioned valley, not stationarity.

## The finding that matters more

Across the entire 1.7× objective improvement, matched boundary error went
**11.849 → 11.991 mm** — the wrong way — and union IoU stayed at **0.7088**, to
four decimals. The plateau is still 43,703× above the objective the true geometry
attains.

**So repairing the stopping rules would not recover these shapes.** At this scale
the training objective and the gated geometry are close to decoupled. That is a
sensitivity and conditioning statement, and it is the thing that actually blocks
recovery.

It also re-reads TOP-009's stage-2 result. Enrichment drove the objective down
248× while geometry worsened, and this cycle shows the same decoupling at a finer
scale with the mechanism removed: the objective simply is not a proxy for shape
in this regime.

## The gated stage was not implemented

The review gated an optimizer option isolating loss-change stopping — a `1e-14`
absolute loss target — behind a separate review. Stages A and B make it
uninformative rather than premature: the **acceptance margin binds before the
loss-change threshold**, so disabling loss-change stopping would let the run
grind out sub-margin steps without changing what the acceptance rule accepts, and
the geometry does not respond across a 1.7× objective change anyway. The option
stays available and unreviewed; this is a reported decision, not a gate routed
around.

## Where the track stands

Four explanations tested, each real and none sufficient:

1. **The derivative** — genuine defect, fixed in TOP-008.
2. **Capacity** — genuinely missing, restored in TOP-009.
3. **Ladder truncation** — real, corrected in TOP-009 stage 4.
4. **Premature stopping** — real, demonstrated here, worth 1.7×.

Every one improved the objective. **Not one improved the reconstruction.** The
benchmark still passes 5/12.

The open question is no longer which optimizer defect to fix next. It is **why
the gated geometry is insensitive to four orders of magnitude of training
objective**, and that is a question about sensitivity, conditioning and what the
0.003 data tolerance actually certifies — the final K=9 state satisfies that
tolerance at 8.7878e-05 while sitting 11.849 mm from the truth.

Two candidates, now written as contracts, **neither approved**:

1. **[TOP-011 — how much geometry hides inside the data tolerance](02_proposals/01_sensitivity_and_conditioning.md).**
   Diagnostic only, no source change. For each singular direction of the
   Jacobian, how far can the boundary move while the data fit stays inside the
   frozen 0.003 tolerance? The plateau's singular values already span 2.085e-04
   to 28.83, but nobody has converted that into millimetres. This is the direct
   successor, it reuses everything built, and it is the cheaper question.
2. **[TOP-012 — richer acquisition, and what it costs the benchmark](02_proposals/02_acquisition_change.md).**
   Better motivated than when the verdict deferred it, and explicitly gated
   behind TOP-011 so we do not buy data to fix a problem not yet shown to be
   about data. It also documents a route the earlier discussion missed: adding
   **source/receiver pairs at 0.5 GHz** enriches the acquisition **without
   touching the 1.5/2.5 GHz holdout**, unlike adding frequencies, which destroys
   it. Any route creates a v2 benchmark; v1 stays immutable. **Requires the
   user's decision.**

No controller default, gate, scene or budget changed in this cycle.
TOP-002–TOP-004 remain deferred proposals.
