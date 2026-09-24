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

The [research implementation principles](implementation_principles.md), adopted by the user on 2026-09-14, supplement this workflow with numerical experiment design and interpretation guidance.

## Tracks

| Track | Organised around | Handoff |
|---|---|---|
| **Shape/frequency continuation** | *How should shape harmonics and frequency steps adapt in a qualified nodal inverse?* | [`shape_frequency_continuation/README.md`](shape_frequency_continuation/README.md) |
| **Topology** | *How can the inverse choose and execute topology changes more reliably?* | [`topology/README.md`](topology/README.md) |
| **Boundary–BIE** | *Which properties of smooth-boundary representations improve the BIE inverse?* | [`boundary_bie/README.md`](boundary_bie/README.md) |
| **Laurent** | *What does a node-free Laurent/Fourier coefficient representation give the inverse, and what does it cost?* | [`laurent/README.md`](laurent/README.md) |
| **Modal compression** | *What can modal compression offer in physical sensitivities, accuracy control, memory and repeated work?* | [`modal_compression/README.md`](modal_compression/README.md) |
| **Speed-up** | *How can the complete inverse reach the required reconstruction quality with less time and fewer failed attempts?* | [`speedup/README.md`](speedup/README.md) |
| Experiments | What can the observations identify, and which formulations improve the inverse? Closed exploratory screen | [`experiments/README.md`](experiments/README.md) |
| Radial Fourier topology | The cycle that built the automatic controller | [`radial_fourier_topology/README.md`](radial_fourier_topology/README.md) |
| Cartesian Fourier | The chart study and its topology match | [`cartesian_fourier/README.md`](cartesian_fourier/README.md) |
| Implicit MLP | Neural-owned geometry with Method B | [`implicit_mlp/README.md`](implicit_mlp/README.md) |

Topology, Boundary–BIE, Laurent, Modal compression, Speed-up and Shape/frequency
continuation are **question-based**. Topology, Boundary–BIE, Speed-up and
Shape/frequency continuation are the current active agenda; **Laurent is closed at
iteration 07 by user direction (2026-09-18)** on the LAU-005 calibration-identifiability
result, with no successor scheduled. Laurent was opened on 2026-09-17 by user direction: the
coefficient-space pipeline built on 2026-09-16 was recorded as exploratory
notebooks inside Boundary–BIE iteration 05, and is now large enough to own a
cycle structure. **Nothing was moved to open it** — iteration 05's records stay
in `boundary_bie/` and the new track cites them as starting evidence, the same
way Boundary–BIE cites the Cartesian-Fourier history. Its first cycle ran
LAU-001 to a `STRUCTURE_ONLY` closeout the same day, and its last,
[iteration 07](laurent/iteration_07/01_results.md), closed LAU-005: calibration quality
decides *where* a neighbour helps, not *whether*. Experiments records the completed cross-domain investigation;
its [iteration 01](experiments/iteration_01/01_results.md) is closed with no
successor scheduled. Radial Fourier topology, Cartesian Fourier and Implicit MLP
are **representation-based** histories: they are closed or paused as
cycles, they are not renumbered or moved, and they are the starting evidence the
question-based tracks cite. The implicit-MLP track is **paused by user
direction (2026-09-11)** — diagnosing the MLP is not the current priority and
the explicit Cartesian Fourier implementation comes first. It remains
scientifically open: paused, not closed and not abandoned.

**Modal compression opened for review on 2026-09-21 by user direction.** Its
[iteration-01 review](modal_compression/iteration_01/02_proposals/01_outsider_evidence_review.md)
audits the Laurent evidence, the September 18 Fourier–Galerkin experiments and
the newly supplied theoretical report. It preserves the closed Laurent history
and proposes a physical-sensitivity diagnostic (`MC-001`). The user's follow-up
approved a simple matrix/derivative visualization screen and conditional
continuation on success; [MC-001's plan](modal_compression/iteration_01/03_plan.md)
records its gates and budget. [Iteration 02](modal_compression/iteration_02/01_results.md)
closes Stage A: all 12 references qualified, but no noncircle met the 50%
common-mask gate. **The user closed the track at iteration 02 on 2026-09-21.**
Stage B did not run and no successor is scheduled. The
[closeout](modal_compression/CLOSEOUT.md) records the scientific limits and
small-2D-workload cost objection; the [evidence index](modal_compression/evidence_index.md)
connects the original compression records across Modal compression and Laurent
without moving or renumbering them.

Topology’s latest executed closeout is [iteration 18](topology/iteration_18/01_results.md):
TOP-025 completes the user-requested current-code all-case video inventory.
**7/12 scenes pass all gates**; all twelve fresh cases and their failures
are retained. Its [plan](topology/iteration_17/03_plan.md) is COMPLETE.
On 2026-09-15 the user authorized finishing the
remaining topology roadmap after committing/pushing TOP-019; this supersedes
earlier per-successor approval holds for that scope. Each successor still
records its contract and binding evidence gates before dispatch.

The [topology completion roadmap](topology/README.md#completion-roadmap) records
the remaining sequence, completion criteria and restart instructions. TOP-018's
closeout does not mean the topology work is complete.

The current comparison reference for these tracks is
[baseline B0](../baselines/B0_2026-09-10.md).

**Shape/frequency continuation opened on 2026-09-22.** Its
[iteration 01](shape_frequency_continuation/iteration_01/01_results.md) starts
from the isolated nodal Müller/Kress pipeline and existing SC-001–SC-012
evidence. It has its own synthetic baseline and paper profiles; B0 is not a
matched reference for its timing or recovery claims. Code and evidence remain
in their existing locations. Iteration 01 recorded a stalled paper-profile
glider with qualified fields/Jacobians.
[Iteration 02](shape_frequency_continuation/iteration_02/01_results.md) closes
that question the same day: the user supplied the authors' reference
implementation and directed that the paper's algorithm be made to work. The
trust-region band had excluded the update's own highest harmonic; with that and
three further settings corrected against the authors' code,
[SC-013](../../results/validation/shape_continuation/SC-013-paper-glider-recovery/README.md)
recovers the Figure 1 glider at both contrasts, but 2.5x-26x below the printed
curve under the printed normalized-area interpretation. A Codex review found
candidate-search and direction-scheduling defects, and listed the transmission
drivers the reading had missed.
[Iteration 03](shape_frequency_continuation/iteration_03/01_results.md) investigates
the calibration question with
[SC-014](../../results/validation/shape_continuation/SC-014-figure1-calibration/README.md):
contrast 0.33 shows partial agreement over k in [1,5] under a raw-area plotting
hypothesis (log10 RMS 0.117; published/ours ratio 0.65–1.57); contrast 10 remains
unmatched. The [2026-09-22 Codex review](shape_frequency_continuation/iteration_03/02_proposals/01_codex_review.md)
accepts the independent direction searches and explicit direction policy, but
identifies remaining stopping-norm and resolution-attribution differences.
The plotting convention, Figure 1 band rule and paper-matched baseline are
**not established**. The user's current request corrects the write-up and adds
these verdicts without changing numerical settings or rerunning the inverse.
The paper's harder shapes, noise, k>5 and adaptive-policy benefit remain untested.
Iterations 04–09 (through 2026-09-24) are summarized in the
[track README](shape_frequency_continuation/README.md):
- a frequency × shape-harmonic atlas;
- the clean Borges-update/SPD-LM hybrid, qualified against SPD (SC-020/021);
- trajectory atlases (SC-022) and their Codex review.

[Iteration 09](shape_frequency_continuation/iteration_09/01_results.md)
implements that review. The atlas-derived band policy is not reliably better
than Borges' ladder on the then-held-out cases.
[Iterations 10–12](shape_frequency_continuation/iteration_12/01_results.md)
independently audit the consolidated atlas and complete the user-requested
strategy tests: 36 endpoints, including five hard stops. A smaller first
band helps C/peanut and harms kite/hook; higher frequencies have local
benefits but neither strategy passes the frozen robustness criteria.
Extra work on the original data improves all six baseline cases. All six
are now development data. The separate SC-027 regularity-metric proposal
remains unexecuted; the closeout schedules no new campaign.
[Iteration 13](shape_frequency_continuation/iteration_13/01_results.md) closes
SC-030: SPD-008 is the SPD reference, and exact cache reuse is qualified for the hybrid.
The user's atlas-to-inverse research brief is placed and
[reviewed](shape_frequency_continuation/iteration_13/02_proposals/02_state_reconciliation_and_SC-031.md)
there. SC-031, approved by the user, tested a regularizing metric against the
stage-1 curvature collapse. [Iteration 14](shape_frequency_continuation/iteration_14/01_results.md)
records that test: its hypothesis is falsified at the stage-1 gate, and the
collapse survives both metrics. [Iteration 15](shape_frequency_continuation/iteration_15/01_results.md)
records SC-032, the user-approved four-stage continuation. The curvature
metric improves the hard cases without regressions (GM 0.832) but misses the
≤ 0.8 adoption bar, so R0 stays the baseline. SC-033 (Borges' curvature-tail
admissibility filter) is proposed and not approved.
[Iteration 16](shape_frequency_continuation/iteration_16/01_results.md) records SC-034, a
user-directed repair of the SPD comparison baseline. A low-order SPD ladder recovers circle, star
and peanut to ≤ 3.3e-5 mm, where SC-030's SPD arm had failed. The four legacy step controls do not
help. SC-035 (band-limited hybrid state) is proposed.

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
| 5 | **Existing checkout selected**; any new branch/worktree separately approved | the implementation owner | gate 4 passed; ask the user before creating a branch or worktree |
| 6 | **Implementation and runs** within the contract's scope and budget | the implementation owner | gate 5 done |
| 7 | **Closeout**: results open the next iteration | owner + reviewer | runs complete |

Without gate 4 an agent may read, review, propose, and write documents. It may
**not** change numerical code, alter an experiment configuration, or launch a
run — not even a small one, and not as "just checking".

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

### Speed-up

Start with the [handoff](speedup/README.md). The track asks how to reduce time
to the required reconstruction quality. The user's 2026-09-16 clarification
extends its design discussion to the whole pipeline: initialization, topology,
representation, physics fidelity, data scheduling, optimization and stopping.
Execution improvements require matched algorithm/recovery; architecture changes
compare time and success at matched final quality and data access. Cross-reference
Boundary–BIE and topology for shared mechanisms. Iteration 1 records the cost profile: between
90.7% and 95.1% of forward solves in the measured topology runs were
finite-difference Jacobian probes. SPD-001 completed the combined analytic,
CPU-kernel and CUDA comparison. SPD-002 made analytic Jacobians and fast CPU
kernels the default; [iteration 3](speedup/iteration_03/01_results.md) records
complete death/split pipelines running 1.86x/1.89x faster with matched recovery.
The user's further-acceleration request is recorded in the
[iteration-3 brief](speedup/iteration_03/02_proposals/01_further_full_inverse_speedups.md):
exact reuse across continuation, shared kernel preparation, CPU parallelism
and GPU derivative assembly. SPD-003 proposes an exact-reuse comparison and
remains unexecuted.
The later [outsider architecture brief](speedup/iteration_03/02_proposals/03_pipeline_redesign_outsider_view.md)
led to the authorized SPD-004 investigation. [Iteration 4](speedup/iteration_04/01_results.md)
records additional 5.12x/6.72x complete-runtime speedups on death/split by checking
training readiness before mandatory continuation. All ten full workers recover
with identical paired final geometry; merge retains the original continuation
with effectively unchanged runtime. The implementation remains experimental.
Its twelve-scene archive audit prioritizes earlier final-grid feasibility and
adaptive topology/shape/data decisions for harder cases. Fresh timing covers
three noiseless scenes; host-wide isolation is unverified.
The subsequent [reciprocal Kress review](speedup/iteration_04/02_reciprocal_derivative_priority_review.md)
revises next-work priority: qualify the reciprocal derivative with the existing
nodal forward, then measure readiness on that baseline. The new derivative
can reduce fitting cost throughout topology search; its exploratory fitting
ratios must not be multiplied by SPD-004's full-worker ratios.
The user then authorized SPD-005: [iteration 5](speedup/iteration_05/01_results.md)
records the completed guarded reciprocal integration. All 18 full workers
recover, with 1.77x–2.38x additional speedups and 5.10x/6.64x gains on the easy
cases when readiness is added. The raw derivative misses one 64-node gate, so
the opt-in runtime retains operator derivatives below 128 nodes. A separate
continuation-stage profile spends 94.6% of its time in legacy stencil-feasibility
checks; geometry-validation reuse and the FD-compatible constraint policy are
the next targets. This remains a three-scene noiseless comparison, with no
production-default or GPU-speedup claim.

The subsequent user-authorized BIE-005 compiler integration is closed in
[iteration 6](speedup/iteration_06/01_results.md). All 16 matched full workers
recover; compiled Kress reduces full runtime by 4.5% on central ellipse/star
and 5.6% on two stars beyond reciprocal plus readiness. It remains opt-in.
A compiled hard-case update still spends 88.5% of profiled time in legacy
stencil-feasibility checks, so geometry reuse and constraint-policy qualification
come before GPU work. The four-scene result is not a new twelve-scene runtime.
