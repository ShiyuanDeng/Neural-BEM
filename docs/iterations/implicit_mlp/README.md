# Implicit-MLP iterations: start here

This is the handoff for agents working on the implicit-MLP research cycle.
Read the current state below before choosing work. The shared folder convention
is in the [iterations README](../README.md).

> **Agenda status: PAUSED by user direction, 2026-09-11.** Diagnosing the
> implicit MLP is **not** the current priority; the explicit Cartesian Fourier
> implementation comes first. The active work is the
> [topology](../topology/README.md) and [boundary–BIE](../boundary_bie/README.md)
> tracks.
>
> This track is **scientifically open** — paused, not closed and not abandoned.
> Neural recovery remains unresolved and the questions below are still live.
> Iteration 3's [agreed plan](iteration_03/03_plan.md) was never executed and is
> paused as written, not withdrawn. Baseline
> [B0](../../baselines/B0_2026-09-10.md) covers the explicit pipelines and does
> **not** pin this track's reference runs.

## Current handoff

Updated 2026-09-11.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 03](iteration_03/01_results.md) |
| Stage | **Paused.** Results recorded; one proposal, two reviews and a gradient diagnosis recorded; `03_plan.md` consolidated 2026-09-08 and never executed |
| Latest completed decisions | Iteration-2 [user-approved final plan](iteration_02/02_proposals/04_final_plan.md), followed by the evidence-based [long acquisition decision](iteration_02/05_acquisition_review.md) |
| Execution status | Diagnostics, repairs, short acquisition comparison and both long star inverses completed. Long command exited 0; no posthoc errors. Paired accepted 42 updates, multistatic 31; both stopped at `no_decreasing_neural_step` |
| Next expected research action | **None while paused.** Work resumes only on a user decision. When it does, the first step is to settle whether [`03_plan.md`](iteration_03/03_plan.md) stands as written or is re-consolidated to absorb the [gradient diagnosis](iteration_03/02_proposals/04_claude_gradient_diagnosis.md), which arrived after the plan and removes the gradient hypotheses it budgeted for. The two reviews still disagree on three numbers — the active band's chart, the frozen-tail floor and the Gauss-Newton cost — which any resumed plan must settle. No implementation has begun |
| Current scientific outcome | Multistatic improves geometry at matched work but does not recover the star. Final symmetric raw RMS: 9.506 mm versus paired 14.097 mm; multistatic mode-5 amplitude is 1.530 mm versus 12.5 mm truth |

Follow the user's requested task within this state. A request to review or
update documentation does not imply implementing a proposal or launching an
inverse. The latest numbered document is the latest contribution, not an
automatically adopted plan.

### The iteration-3 plan's status

`iteration_03/03_plan.md` **exists**. It is titled "final plan and decisions",
was consolidated on 2026-09-08 from the ChatGPT guide and the first two Claude
reviews, and its own handoff section states that iteration 3 has "an agreed plan
and execution pending". The handoff table above previously recorded the agreed
plan as still pending, because the
[gradient diagnosis](iteration_03/02_proposals/04_claude_gradient_diagnosis.md)
arrived after the plan and changed the inputs it consolidated.

**Resolved on 2026-09-11:** the user directed that diagnosing the implicit MLP
is not the current priority and the explicit Cartesian Fourier implementation
comes first. The plan is therefore **paused as written** — not adopted for
execution now, and not withdrawn, superseded or rewritten. It carries a
[pause notice](iteration_03/03_plan.md) recording this.

**Still unresolved, deliberately:** whether that plan stands as written or is
re-consolidated to absorb the gradient diagnosis. That is a question for
whoever resumes the cycle, and the pause does not answer it.

Not in dispute either way: nothing was executed under the plan, and no
implementation began.

## Read in this order

1. [Iteration-03 results](iteration_03/01_results.md): completion, measured
   long-run outcomes, exact stopping mechanisms, evidence limits and candidate
   checks. This is the current research state.
2. Iteration-2's [final plan](iteration_02/02_proposals/04_final_plan.md),
   [diagnostic repairs](iteration_02/04_diagnostic_fixes.md), and
   [short acquisition review / long-run decision](iteration_02/05_acquisition_review.md).
3. The [long-run evidence index](../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/README.md),
   then the saved run and diagnostic artifacts relevant to the assigned task.
4. Iteration-3's numbered proposals, in order: the
   [ChatGPT direct Method-B Fourier guide](iteration_03/02_proposals/01_chatgpt_guide.md),
   the [first Claude review](iteration_03/02_proposals/02_claude_review.md) of it,
   whose read-only probes are indexed at
   [`review-diagnostics/`](../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/review-diagnostics/README.md),
   the [second Claude review](iteration_03/02_proposals/03_claude_second_review.md),
   whose forward-solve probes are indexed at
   [`review-diagnostics-identifiability/`](../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/review-diagnostics-identifiability/README.md),
   and the [gradient diagnosis](iteration_03/02_proposals/04_claude_gradient_diagnosis.md),
   whose frozen-state probes are indexed at
   [`review-diagnostics-gradient/`](../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/review-diagnostics-gradient/README.md).
   Then [`03_plan.md`](iteration_03/03_plan.md), reading its status caveat
   below before treating it as current. For older context, use
   [iteration-02 opening results](iteration_02/01_results.md) and
   [iteration-01 final decisions](iteration_01/03_plan.md).

Results establish what was measured. Proposals and reviews contribute
recommendations and may disagree; record which recommendations are accepted,
amended or deferred when consolidating the plan. The agreed plan governs
execution, subject to the user's instructions. Its existence alone does not
mean its experiments have run: check the execution status and linked evidence.

## What to do at each stage

| Stage | Expected work | Record to leave |
|---|---|---|
| Results available; no proposal | Interpret the results and propose discriminating next checks | A numbered guide in `02_proposals/` |
| Proposal review | Compare the guide with evidence and prior decisions; identify agreements, corrections and open questions | The next numbered review in `02_proposals/` |
| Agreed plan; execution pending | Carry out the requested work within the plan's scope, controls and budget | Execution status here and artifacts under `results/` |
| Execution in progress | Continue from recorded progress; check existing artifacts before repeating work | Completed and remaining work, artifact paths and any obstruction here |
| Execution complete; closeout | Assess outcomes against the plan and open the next research cycle | Next iteration's `01_results.md`, updated active pointer and handoff here |

Before execution, `03_plan.md` should state the question, accepted decisions,
bounded checks, deferred work, experiment controls, success criteria and work
limits. During proposal review, creating that agreed plan is the transition to
execution pending; do not silently promote a review into execution authority.
Iteration 2 used the user's explicitly selected
`iteration_02/02_proposals/04_final_plan.md` as its controlling plan. Its location
inside the proposal folder does not override that recorded user instruction.

Results from executing the plan open the **next** iteration. Preserve the
completed cycle's results, numbered discussion and plan as historical records;
do not replace them with the next run's conclusions. Create stages only when
they exist, without placeholder plans that look agreed. Diagnostic probes made
to inform a review may accompany that review and must be identified as such.

Update this handoff whenever the stage, next action or execution status changes.
At a cycle transition, update the active iteration, reading links and evidence
pointers together. Do not infer the active cycle from the highest folder number.
The project handoff lives here; the parent README describes the shared format.

## Evidence for the current cycle

The [iteration-03 results](iteration_03/01_results.md) state the measurements
inline. The completed long run is
`results/validation/implicit_mlp_adjoint/iteration-02-final/long-acquisition-20260908T174300326691Z/`.
Its `metrics.json` reports completion, and `run.log` ends with exit 0.
The [iteration-3 evidence index](../../../results/validation/implicit_mlp_adjoint/iteration-03-20260908/README.md)
links completion checks, actual terminal candidates, signed geometric motion,
matched-work comparisons, optimizer snapshots and reproducible saved-data
reviews. Those reviews performed no new inverse or BEM evaluations. The three
proposal-review diagnostic folders are separate from them and differ from
each other: `review-diagnostics/` is read-only over saved contours;
`review-diagnostics-identifiability/` runs about 700 Kress **forward** solves on
frozen analytic curves; `review-diagnostics-gradient/` re-runs derivative
correctness checks at frozen saved accepted states, and is the only one that
loads a model. None ran an inverse, took an optimizer step, changed production
code, or modified a saved artifact.

The main unresolved findings are multistatic lobe collapse and late conversion
distance constraints, paired contour distortion and candidate topology
detection, and field deterioration in both arms. Intermediate paired Adam
distortion is now measured; the same defect is not established for multistatic.
Late finite proposal probes fail geometry and must not be described as verified
admissible motion. Candidate fixes in the results document are not an adopted
iteration-3 plan. Candidate 5 is now split rather than bounded: the second
review finds multistatic-24 indistinguishable from multistatic-8 over twelve
low-order modes, so added source angles are not the multistatic arm's missing
ingredient, while six frequencies at eight angles measurably improve low-mode
conditioning. That is evidence at those modes and states only, and leaves the
neural-metric half untouched. The gradient diagnosis then clears both leading
gradient hypotheses: the Kress shape gradient converges at the finite-difference
truncation rate at every audited state, the composite agrees to between `1e-9`
and `6.4e-6`, and the Method-B reverse is better than `2e-6` outside two late
paired states where the production map is itself branch-noisy. It also records that both
arms finished on the admissibility boundary — E0 state 42 splits into two
components under a random weight perturbation the size of a median accepted
step, and E1 state 31 fails its own `200 um` conversion gate on rebuild at
`200.007 um` against the recorded `199.955 um`. That promotes candidate 1.

Raw run bundles live under `results/`, not inside the iteration folders. In
particular, `results/inverse/implicit_mlp/2026-09-08/` contains the earlier suite
and the saved initialization used by the acquisition comparisons.
Some raw bundles, checkpoints, videos and per-weight arrays are local-only and
may be absent from a checkout. Use the self-contained iteration records to
review the conclusions; for reproduction, check artifact availability and
source provenance before claiming a replay or substituting a fresh run.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| [01](iteration_01/01_results.md) | September 7–8 failures, repairs and matched acquisition controls | Closed; [final decisions](iteration_01/03_plan.md). Neural recovery unresolved |
| [02](iteration_02/01_results.md) | September 8 repaired-suite failures, frozen diagnostics, measurement/audit repairs and controlled acquisition inverses | Closed; [final plan](iteration_02/02_proposals/04_final_plan.md) executed through the supported acquisition branch. Conditional sampling/high-band/neural-GN branches were not run |
| [03](iteration_03/01_results.md) | Completed long paired-8 / multistatic-8 star comparison | **Paused 2026-09-11 by user direction**; results, one proposal, two reviews and a gradient diagnosis recorded; [plan](iteration_03/03_plan.md) agreed 2026-09-08 and never executed. Multistatic helps but full neural recovery remains unresolved |
