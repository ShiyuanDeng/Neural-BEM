# Implicit-MLP iterations: start here

This is the handoff for agents working on the implicit-MLP research cycle.
Read the current state below before choosing work. The shared folder convention
is in the [iterations README](../README.md).

## Current handoff

Updated 2026-09-08.

| Item | Current state |
|---|---|
| Active iteration | [Iteration 02](iteration_02/01_results.md) |
| Stage | Proposal review; agreed plan pending |
| Latest discussion | [Claude review](iteration_02/02_proposals/03_claude_review.md), following the ChatGPT guide and Codex review |
| Execution status | Reviewer diagnostics have been reported. No iteration-02 agreed plan or execution of that plan is recorded |
| Next expected research action | Reconcile the guide and both reviews, resolve the proposed ordering and checks, and record the agreed decisions in `iteration_02/03_plan.md` |
| Current scientific outcome | Full-MLP recovery remains unresolved; local controls and diagnostic improvements do not establish recovery |

Follow the user's requested task within this state. A request to review or
update documentation does not imply implementing a proposal or launching an
inverse. The latest numbered document is the latest contribution, not an
automatically adopted plan.

## Read in this order

1. [Iteration-02 results](iteration_02/01_results.md): the measured failures,
   comparison limits and evidence index that opened this cycle.
2. [Iteration-01 final decisions](iteration_01/03_plan.md): what is established,
   retained and deferred from the previous cycle.
3. The current discussion, in order:
   [ChatGPT guide](iteration_02/02_proposals/01_chatgpt_guide.md),
   [Codex review](iteration_02/02_proposals/02_codex_review.md), and
   [Claude review](iteration_02/02_proposals/03_claude_review.md).
4. The active iteration's `03_plan.md` once it exists, then the implementation
   and artifacts relevant to the assigned task.

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

The [iteration-02 results](iteration_02/01_results.md) state the measurements
inline and index the September 8 wrong-start suite, archived ellipse probe and
prior acquisition study. The
[Claude review diagnostics](../../../results/validation/implicit_mlp_adjoint/iteration-02-20260908/review-diagnostics/README.md)
contain its probe script, measurements and provenance. New recommendations in
either review remain proposals even when accompanied by measured diagnostics.

Raw run bundles live under `results/`, not inside the iteration folders. In
particular, `results/inverse/implicit_mlp/2026-09-08/` contains the current suite.
Some raw bundles, checkpoints, videos and per-weight arrays are local-only and
may be absent from a checkout. Use the self-contained iteration records to
review the conclusions; for reproduction, check artifact availability and
source provenance before claiming a replay or substituting a fresh run.

## Cycle history

| Iteration | Cycle | State |
|---|---|---|
| [01](iteration_01/01_results.md) | September 7–8 failures, repairs and matched acquisition controls | Closed; [final decisions](iteration_01/03_plan.md). Neural recovery unresolved |
| [02](iteration_02/01_results.md) | September 8 repaired 12-pair wrong-start suite | Active; guide and two reviews available; agreed plan pending |
