# Experiment iterations

One iteration = one research cycle. Results from a change always start the next
iteration, so a folder is never rewritten after its plan is executed.

```text
<track>/iteration_NN/
  01_results.md    measurements from the runs that opened this cycle, the
                   problems they expose, and the candidate fixes
  02_proposals/    next-step guides and the reviews of them, numbered in the
                   order they were received
  03_plan.md       the agreed plan: decisions, what was validated, what is
                   deferred, and the experiment that opens the next iteration
```

Stages appear only once they exist — an iteration awaiting a proposal has just
`01_results.md`. A track's first iteration may instead open with a proposal or
implementation brief in `02_proposals/` when there is no prior cycle to produce
`01_results.md`; **do not manufacture a results file** to fill the slot. Run
reports, metrics and scripts stay with their artifacts under `results/`; the
stage files link to them rather than copying them.

This page holds the operating rules shared by every track. Track handoffs carry
state, not duplicate copies of these rules. Where this page and the repository
`AGENTS.md` differ, `AGENTS.md` wins. Its follow-up rules allow evidence-driven
experiments within authorized work without separate approval for each ID.

Earlier tracks and their histories were removed on this branch. Their conclusions
that still matter, with the supporting numbers, are in [the evidence page](../evidence.md).

The [research implementation principles](implementation_principles.md), adopted by the user on 2026-09-14, supplement this workflow with numerical experiment design and interpretation guidance.

## What to do at each stage

| Stage | Expected work | Record to leave |
|---|---|---|
| Results available; no proposal | Interpret the results and propose discriminating next checks | A numbered guide in `02_proposals/` |
| Proposal review | Compare the guide with evidence and prior decisions; resolve each material recommendation | The next numbered review in `02_proposals/` |
| Agreed plan; execution pending | Carry out the requested work within the plan's scope, controls and budget | Execution status in the handoff, artifacts under `results/` |
| Execution in progress | Continue from recorded progress; check existing artifacts before repeating work | Completed and remaining work, artifact paths, any obstruction |
| Execution complete; closeout | Assess outcomes against the plan and open the next cycle | Next iteration's `01_results.md`, updated handoff |

Update the track handoff whenever the stage, next action or execution status
changes. Do not infer the active cycle from the highest folder number.

## Approval rule

**Authorization follows the user's research question, not individual IDs.**

- A proposal, a review, a results record, or a candidate list is *not*
  authorisation to implement everything it mentions.
- A file named `03_plan.md` does not by itself establish that execution was
  approved, or that it happened. Both states must be written down explicitly —
  in the plan's own status block and in the track handoff.
- Every experiment carries an ID of the form `TOP-001`, `BIE-001`, … for
  traceability. Follow-ups on authorized work may receive new IDs without
  renewed approval. Follow `AGENTS.md` for scope, budgets and exclusions.
- After analysis, record the smallest justified follow-up before executing
  it. A new plan or dated amendment states the evidence, hypothesis, changed
  conditions, run count and stopping criteria; original results stay intact.
- Status vocabulary, used verbatim:

  | Approval status | Meaning |
  |---|---|
  | `PROPOSED — NOT APPROVED FOR EXECUTION` | Drafted; no authority to implement or run |
  | `APPROVED` | Covered by the user's requested work, including a documented follow-up within that authority; cite the request |
  | `SUPERSEDED` | Replaced by a later ID; say which |
  | `WITHDRAWN` | Not pursued; say why |

  | Execution status | Meaning |
  |---|---|
  | `NOT STARTED` / `IN PROGRESS` / `COMPLETE` / `ABANDONED` | With artifact paths once anything has run |

### From brief to execution

The steps below record progress. Continue through them within existing user
authorization; finishing analysis or assigning a new ID is not a reason to stop.

| # | Step | Who does it | What moves it |
|---|---|---|---|
| 1 | **Brief or results** exist | any agent | — |
| 2 | **Review** written, resolving material recommendations | an agent who is not the brief's author, where practical | part of the requested work; use a focused review or diagnostic |
| 3 | **Pre-registered `03_plan.md` or dated amendment** | an agent | evidence supports a bounded comparison within the authorized question |
| 4 | **Authorization recorded** | the implementation owner | cite the user's request covering the work; ask only for a new question or departure from explicit limits |
| 5 | **Existing checkout selected**; any new branch/worktree separately approved | the implementation owner | step 4 recorded; ask before creating a branch or worktree |
| 6 | **Implementation and runs** within the contract's scope and budget | the implementation owner | step 5 done |
| 7 | **Closeout**: results open the next iteration | owner + reviewer | runs complete |

Without a user request authorizing experiment work, an agent may read, review,
propose and write documents. A document alone grants no execution authority.
Existing authorization continues through follow-ups under `AGENTS.md`.

**User override adopted 2026-09-14:** work in the existing
`/home/drdeng/Neural_SDF_BEM_AD` checkout on `feature/ordered-boundary-nystrom`.
Before creating any branch or additional worktree, ask the user directly and
obtain explicit approval, even in full-access mode. Experiment/plan/ZIP approval
does not authorize branch creation. This replaces the previous one-branch-per-ID
rule. Run separate implementation tracks sequentially unless the user explicitly
approves separate checkouts; never let simultaneous writers share a checkout.

## Experiment contract template

Copy this into a proposal for each experiment. Keep it compact; link out for
detail rather than restating evidence.

```markdown
### <ID> — <one-line title>

- **Approval status:** PROPOSED — NOT APPROVED FOR EXECUTION
- **Execution status:** NOT STARTED
- **Question:** the one thing this experiment decides.
- **Falsifiable hypothesis:** what the result would have to look like for this
  to be wrong.
- **Baseline:** baseline record + commit; the reference runs compared against.
- **Intervention:** exactly what changes. One mechanism where possible.
- **Controls:** what must remain fixed (data, oracle, schedules, tolerances,
  seeds, resolutions, budgets).
- **Scope and shared interfaces:** files/APIs this may touch; shared geometry,
  objective or solver interfaces that must not change without review.
- **Metrics and comparison criteria:** what is measured and how the arms are
  compared.
- **Compute budget and stopping rules:** solve counts or wall-clock ceiling,
  and when to stop early.
- **Artifacts:** required outputs and their output directory (fresh).
- **Decision criteria:** what result means adopt / reject / investigate further.
- **Owner:** implementation owner. **Reviewer:** independent reviewer.
  Use `unassigned` — do not invent an assignment.
```

## Reviews resolve, they do not re-litigate

A review must resolve **each material recommendation** as exactly one of:

- **Accept** — adopt it, with any amendment stated.
- **Reject** — with the evidence or argument that decides it.
- **Defer** — to a named later cycle or ID, with the reason.
- **Resolve through a named diagnostic** — state the diagnostic, its scope and
  its budget.

Scientific disagreement should end in a decision or a discriminating test, not
another full-plan rewrite. Any diagnostic run during review needs its own
declared scope and budget, must be identified as a review diagnostic (not an
experiment result), and its artifacts belong beside the review.

## Collaboration and integration rules

- **One implementation owner and one independent reviewer per experiment.**
  Claude and Codex can rotate roles. Record actual assignments only; write
  `unassigned` otherwise.
- **Sequential implementation in the existing checkout by default.** Creating
  another branch or worktree requires the user's separate explicit approval.
- **No two agents modify the same working checkout at the same time.**
- **Shared-interface changes are declared before implementation** — geometry
  state, the objective, or the solver interface. A track may not silently alter
  something the other track's comparison depends on.
- **Preserve original observations, configurations, results and failed arms.**
  Failed arms stay with their comparison.
- **New runs get fresh output directories.** Never overwrite a bundle.
- **Changed tolerances, schedules or stopping rules must be visible** in any
  comparison that spans the change.
- **Distinguish solve-count comparisons from controlled wall-clock
  comparisons.** Concurrency and machine load must be declared for the latter.
