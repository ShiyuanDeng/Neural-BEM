# SPD-004 — investigate avoidable phases in the full inverse

2026-09-16. **Approval: APPROVED** by the user's direct “investigate go”
instruction following the outsider architecture brief. That instruction
authorizes this bounded investigation without a second naming/approval round.
**Execution: COMPLETE; performance and recovery contract PASS.**
[Measured results](../iteration_04/01_results.md): death/split 5.12x/6.72x
additional full-runtime speedups against fast CPU, with identical saved final
geometry in every pair; merge preserves fallback and has effectively unchanged
runtime. All ten workers complete within the declared limits. The dispatch-time
plan is retained in the result bundle as `approved_plan.md`.
Owner/reviewer: Codex `/root`, self-review;
independent reviewer unassigned. Existing checkout/branch only.

## Question and intervention

Can a training-only full-accuracy readiness check remove unnecessary frequency
continuation while preserving the original reconstruction requirements?
Also audit where the existing all-scene pipeline spends work on topology,
candidate search, automatic shape-capacity expansion and continuation.

The experiment changes the pipeline's completion contract: a qualified fit may
return without a stationarity certificate or mandatory stage exposure. It must
not report those skipped stages as executed. Original event checks and final
geometry, training, evaluation and numerical recovery gates remain in force.
No production default is changed. SPD-003 exact caching remains unexecuted.

The predeclared conservative gate requires finite relative L2 prediction errors
<= **1e-5 at every training frequency**, at both 256 and 512 nodes, and
production/refined discrepancies <= the existing per-frequency tolerances
`[1e-5, 1e-7, 1e-7, 1e-7]`. The fit threshold is the existing oracle accuracy
scale, stricter than the task's 0.003 original-training gate; it is not tuned
against evaluation errors. Validate geometry at both grids first. The gate
receives state, training observations and solver/configuration only, with no
truth, scene identity, target count or independent evaluation observations.
If it does not pass, run the existing continuation unchanged and charge the
screening overhead. A looser 0.003 threshold may be reported as an explicitly
unselected sensitivity diagnostic, never used to select this gate after seeing
evaluation outcomes.

## Bounded stages

1. Read saved TOP-025 and SPD-002 artifacts, hash every consumed file, and
   report handoff readiness, subsequent accepted steps, shape dimensions,
   stage work and independent endpoint quality. Missing handoffs remain
   failures/unavailable, not negative predictions. This replay dispatches no
   physical solves and provides development evidence, not a new campaign.
2. Qualify the pure gate, invalid inputs, training/evaluation separation,
   early-return reporting, fallback and accounting with focused tests. Recompute
   readiness on at most four saved handoffs, including central-ellipse-star
   and far-two-stars negative controls, if needed. Ceiling: 64 physical systems
   and 300 s for these handoff-only checks.
3. After qualification, fresh complete sequential fast-CPU baseline/readiness
   runs from original starts: two paired repetitions each of death and split,
   with alternating order, plus one complete baseline/readiness merge pair
   exercising real continuation. At most ten workers, 3,600 s total timed
   campaign, and 1,200 s per worker. Retain original topology/continuation
   watchdogs and work caps; explicitly charge up to eight extra training
   screening systems to the intervention. Stop on false early recovery,
   numerical/integrity failure or exhausted budget; preserve partial evidence.

Baseline and intervention use the same fast runtime, observations, original
starts, capacity policy, topology settings and fallback optimizer. Historical
FD times are context, not the new comparator. Timings include startup, full
topology, screening, retained continuation and independent endpoint checks.
Existing evaluation predictions may be reused only after a training-only gate
decision; evaluation data must not influence that decision. Returning an
unchanged state may reuse exact training predictions in final assessment.

## Evidence and decision

Use a fresh `results/validation/speedup/SPD-004-<timestamp>-pipeline-readiness/`
bundle with plan, source/input snapshots and hashes, archive-audit tables,
tests, raw arm timings, states, events, all gate decisions, work ledgers,
independent recovery metrics and verification. Record host/load/thread state;
if process visibility is restricted, disclose that timing limitation rather
than assert full host isolation. Single CPU BLAS thread; one experiment worker
at a time. Source and input integrity checked at every arm boundary.

For death/split, require all original recovery gates and identical retained
geometry within 1 micrometre; target >=1.5x complete-runtime speedup. For merge,
require the same fallback endpoint/recovery and report its added cost; target
<=10% median/single-pair overhead, with single-pair uncertainty stated. Archive
gate positives must pass independent endpoint recovery checks. No all-scene
timing or noise-robustness claim follows from this bounded experiment.

Use the findings to revise architectural priorities. If the gate fails,
document that result and its cause; do not silently tune it on evaluation data.
Record new findings in speed-up iteration 04 and update the handoff. Numerical
implementation is confined to experiment modules and focused tests; the shared
production solver/controller remains unchanged.
