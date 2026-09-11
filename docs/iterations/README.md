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
state, not duplicate copies of these rules.

## Tracks

| Track | Organised around | Handoff |
|---|---|---|
| **Topology** | *How can the inverse choose and execute topology changes more reliably?* | [`topology/README.md`](topology/README.md) |
| **Boundary–BIE** | *Which properties of smooth-boundary representations improve the BIE inverse?* | [`boundary_bie/README.md`](boundary_bie/README.md) |
| Radial Fourier topology | The cycle that built the automatic controller | [`radial_fourier_topology/README.md`](radial_fourier_topology/README.md) |
| Cartesian Fourier | The chart study and its topology match | [`cartesian_fourier/README.md`](cartesian_fourier/README.md) |
| Implicit MLP | Neural-owned geometry with Method B | [`implicit_mlp/README.md`](implicit_mlp/README.md) |

The first two are **question-based** and are the current active agenda. The
last three are **representation-based** histories: they are closed or paused as
cycles, they are not renumbered or moved, and they are the starting evidence the
question-based tracks cite. The implicit-MLP track is **paused by user
direction (2026-09-11)** — diagnosing the MLP is not the current priority and
the explicit Cartesian Fourier implementation comes first. It remains
scientifically open: paused, not closed and not abandoned.

The current comparison reference for both active tracks is
[baseline B0](../baselines/B0_2026-09-10.md).

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

**Approval applies to named experiment IDs, and to nothing else.**

- A proposal, a review, a results record, or a candidate list is *not*
  authorisation to implement everything it mentions.
- A file named `03_plan.md` does not by itself establish that execution was
  approved, or that it happened. Both states must be written down explicitly —
  in the plan's own status block and in the track handoff.
- Every experiment carries an ID of the form `TOP-001`, `BIE-001`, … Approval
  is granted per ID: "approve BIE-001" authorises that contract, at that scope
  and budget, and nothing adjacent to it.
- Status vocabulary, used verbatim:

  | Approval status | Meaning |
  |---|---|
  | `PROPOSED — NOT APPROVED FOR EXECUTION` | Drafted; no authority to implement or run |
  | `APPROVED` | The user approved this ID; implementation may begin within its declared scope and budget |
  | `SUPERSEDED` | Replaced by a later ID; say which |
  | `WITHDRAWN` | Not pursued; say why |

  | Execution status | Meaning |
  |---|---|
  | `NOT STARTED` / `IN PROGRESS` / `COMPLETE` / `ABANDONED` | With artifact paths once anything has run |

### From brief to execution

The gates, in order. A track states which one it is at; an agent picking up a
track does the next one and nothing beyond it.

| # | Gate | Who does it | What moves it |
|---|---|---|---|
| 1 | **Brief or results** exist | any agent | — |
| 2 | **Review** written, resolving every material recommendation | an agent who is not the brief's author, where practical | the user saying *"review TOP-001"* — or any request to review the track |
| 3 | **Agreed `03_plan.md`** consolidating the review | an agent | the user accepting the review's recommendation |
| 4 | **Approval of a named ID** | **the user only** | the user saying *"approve TOP-001"*. No agent may grant this, infer it, or treat silence as it |
| 5 | **Branch or worktree** created for the track | the implementation owner | gate 4 passed |
| 6 | **Implementation and runs** within the contract's scope and budget | the implementation owner | gate 5 done |
| 7 | **Closeout**: results open the next iteration | owner + reviewer | runs complete |

Without gate 4 an agent may read, review, propose, and write documents. It may
**not** change numerical code, alter an experiment configuration, or launch a
run — not even a small one, and not as "just checking".

Use one branch per experiment ID, named `track/<track>-<ID>` — for example
`track/topology-TOP-001` or `track/boundary-bie-BIE-001`. Two tracks must never
share a working checkout.

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
- **Separate branches or worktrees** for concurrent implementation tracks.
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

### Intended integration comparison

When both tracks produce candidate improvements, the comparison design is the
2×2:

| | Baseline solver | New solver |
|---|---|---|
| **Baseline topology** | reference | solver effect |
| **New topology** | topology effect | combined |

This is a **future evaluation design**, recorded so the tracks stay
comparable. It is not an instruction to run four suites now, and no arm of it
is approved.

## Track histories

### Radial Fourier topology

Start with the [handoff](radial_fourier_topology/README.md). Iteration 1's
agreed plan was executed with a full G0–G5 pass; its results opened iteration 2,
where proposals are pending. The controller iteration 2 built is shared: the
Cartesian-Fourier cycle's iteration 3 runs the same code under a `--chart` flag,
and every radial path is unchanged.

### Cartesian Fourier

Start with the [handoff](cartesian_fourier/README.md). Iteration 1 is a chart
study: the optimization state is a Cartesian Fourier curve and the MLP is
dropped entirely. Its plan was executed and its results opened iteration 2.
Iteration 3 is a user-directed implementation that gives the chart the radial
cycle's automatic topology controller and matches it on all eight inverse cases.

### Implicit MLP

Start with the [handoff](implicit_mlp/README.md) for the active iteration,
stage, reading order, next expected action, execution status and cycle history.
That handoff is the maintained entry point; proposal numbering alone does not
identify the agreed plan or authorize execution.
