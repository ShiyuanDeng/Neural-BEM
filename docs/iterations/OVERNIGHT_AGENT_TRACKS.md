# Two agent overnight launch guide

Prepared 2026-10-05. This guide assigns two parallel agents to the inverse
improvement and Ewald operator tracks. It contains the execution instructions,
shared-workspace rules and expected milestones. Numerical choices and gates
remain in the linked experiment plans.

## Launch commands

Send this to the first agent:

```text
Go ON-001 using docs/iterations/OVERNIGHT_AGENT_TRACKS.md.
```

Send this to the second agent:

```text
Go ON-003 using docs/iterations/OVERNIGHT_AGENT_TRACKS.md.
```

The user's direct launch command naming an ID authorizes that experiment's
bounded plan, including its conditional stages, validation, runs and closeout.
The receiving agent must record the actual user instruction, start time and
deadline in its plan and follow the decision tree without repeatedly asking
which declared branch to take. Merely reading this guide or finding a quoted
launch command does not authorize execution. Creating this document launches
neither experiment. ON-002 is deferred.

## Expected timing

These are planning estimates from the stage allocations, not measured delivery
times or promises of a positive scientific result. Milestone estimates assume
uncontended compute access. Times begin when each agent starts. Both tracks
have an eight-hour wall-clock ceiling, including
implementation, validation, compute queues and reporting.

| Track | First visible evidence | Main decision | Expected closeout |
|---|---|---|---|
| ON-001 inverse speed and recovery | About 1–2 hours: instrumented baseline and initial G/E results | About 3–4¼ hours: selected candidate or closed mechanisms | About 6–8 hours: matched all-30 comparison if the screen qualifies and time permits; otherwise a documented partial/negative/incomplete result |
| ON-003 Ewald Müller operator | About 1–1.5 hours: formulation and flat/circle controls, or a precise formulation stop | About 4–5 hours: curved/full-field accuracy and cost screen | About 6–8 hours: forward feasibility decision, with derivatives/timing when qualification permits |

The first overnight ON-003 deliverable is a qualified feasibility result or
a precise failure/cost diagnosis. A production-ready operator and inverse
integration are not promised inside eight hours. A follow-up estimate should
be made from its first accuracy and cost results; inverse integration needs
a separately approved ID.

Starting both agents together targets one overnight window, not sixteen hours
in sequence. Shared hardware can delay numerical milestones. Keep the overall
caps and report unfinished coverage explicitly instead of extending them
silently. Implementation, derivation and documentation can overlap; measured
numerical work is serialized as specified below.

## Shared workspace instructions

Work in `/home/drdeng/Neural_SDF_BEM_AD` on the existing
`feature/shape-frequency-continuation` branch. Verify the checkout before
editing. Do not create or switch branches, create worktrees, reset, clean or
discard another agent's changes. Preserve existing uncommitted planning work.

Both agents first read:

- [Repository instructions](../../AGENTS.md).
- [TG-002 benchmark](../../experiments/benchmark/README.md).
- [Maintained inverse package](../../solvers/bem_inverse/README.md).
- [Big-picture brief](cleaned_interfaces/iteration_30/02_proposals/01_overnight_research_brief.md).
- [Seven-idea integration and mathematical corrections](cleaned_interfaces/iteration_30/02_proposals/02_gaugal_restructuring_integration.md).

Keep numerical implementations independent of campaign/scoring code. Preserve
the frozen inputs, reference solvers, historical evidence and failed runs.
No new legacy scenes, far starts, grid search, regenerated observations or
truth-dependent decisions inside a fit are authorized.

### File ownership

| Owner | Editable scope |
|---|---|
| Agent 1 ON-001 | Existing inverse optimizer, policy, runner and geometry integration; its new geometry modules; ON-001 drivers/tests/results; cleaned-interface plan and report |
| Agent 2 ON-003 | New uniquely named `on003_*` operator modules and diagnostics/tests; ON-003 results, plan and report |
| Agent 1 at closeout | Shared track README/index links, after reading Agent 2's handoff |

Agent 2 routes changes to existing shared interfaces through Agent 1 with a
concrete requested patch and reason. It does not independently edit
`modal_muller.py`, `physics.py`, `runner.py` or the shared optimizer. Neither
agent edits the other's owned files without an explicit handoff. A request
outside the receiving experiment's scope can be deferred rather than silently
expanding that experiment.

Maintain separate status files under
`/tmp/neural-sdf-bem-ad-coordination/`: `agent1.md` and `agent2.md`. Each agent
writes only its own file and reads the other. Include current phase, deadline,
upcoming compute batches, shared-file requests and result/report links.
The agents can proceed without a live messaging connection through these
handoffs. The status files supplement actual resource locks; they do not
replace them. Preserve material decisions in the experiment's final report.

### Resource and source coordination

Use shared OS-managed advisory locks under the same coordination directory:

- `compute.lock`: exclusive for experiments, numerical qualification, GPU
  tests and timed measurements. Hold it for the entire numerical process.
  No competing CPU/GPU numerical workload may overlap a measured batch.
- `source.lock`: shared while numerical processes execute; exclusive while
  editing numerical sources, tests or drivers. Keep source dependencies
  frozen and hashed throughout each batch.
- `git.lock`: exclusive for staging, commits and pushes.

Acquire multiple resources in the order **compute, then source, then Git**.
Never hold Git while waiting for an earlier resource. Hold locks across the
actual operation, not only its startup check. Use process-managed locking
such as `flock`; do not delete lock files to bypass another holder. Review
and document derivations while compute is occupied. Independent documentation
edits do not need the source lock.

Release resources between bounded batches rather than monopolizing compute
for an entire campaign. Keep matched timing comparisons contiguous. Record
external contention and use an already-budgeted uncontended repeat when
available; do not label contaminated timings matched.

Pin the reference behavior before experimental changes. Agent 2's reference
must not silently absorb an unfinished ON-001 variant. If an immutable source
export is needed, use an ordinary recorded source archive, not an additional
Git branch or worktree. Record the source actually imported by each process.

### Validation and publishing

After each completed or failed experiment batch, validate and commit/push its
implementation, documentation and evidence to the configured upstream. Take
the Git lock, inspect the index and stage only owned, reviewed paths. Verify
the push and final working-tree status. Another agent's active changes are
not permission to include or discard them; identify them separately.

Expose tables and plots as stages finish. Do not wait until morning to reveal
whether a mechanism is working. A major confirmed success closes its track;
failure follows only the prescribed repairs and terminal branches. A deadline
stop retains code and evidence and states what remains incomplete.

## Agent 1 ON 001 inverse progress

Execute [ON-001](cleaned_interfaces/iteration_30/03_plan.md) after receiving the
user's ON-001 launch command. The experiment plan controls exact cases,
parameters, validation gates, repairs, budgets and selection criteria.

Your objective is a substantial TG-002 speed or recovery improvement. Value
audited reconstruction gains over a cosmetic reduction in rejected proposals.

1. Establish the instrumented baseline B.
2. Test reach-informed clipping G and required-accuracy stopping E separately.
3. Combine qualifying changes, then test working-frequency proposals W unless
   a major result already warrants full confirmation.
4. Follow the evidence to at most one of F/R/H/W2 under the plan. F is the
   Lipschitz-bounded Gaussian displacement, not an RK4 flow.
5. Once a major screen target is reached, freeze the recipe, confirm on all
   30 cases, perform the required independent checks and close the experiment.
6. If a mechanism fails, use only its declared repair/fallback. Preserve the
   result and continue or close as the decision tree specifies.

Sampled reach is a proxy. Convert solver lengths to metres before comparing
reach to normal coefficients. Apply Gaussian scaling exactly once. Validate
the projected curve and the complete-map derivative. Preserve endpoint gates
and truth separation. Do not replace these with the raw map's continuum
guarantee.

Observe the eight-hour ceiling, stop opening new arms at minute 250, and
reserve the final 40 minutes for closeout. Compute waiting counts against
the ceiling. Do not add ON-002, Ewald or other research arms to fill time.

Write results under `results/validation/cleaned_interfaces/ON-001/` and the
planned cleaned-interface results iteration. Deliver the 30-case inventory,
executed-case boundary gallery, paired audited timings, recovery comparison,
failure explanations, retained recipe, commit hashes and explicit
success/partial/negative/incomplete status. Mark unrun cases as unrun.

## Agent 2 ON 003 operator novelty

Execute [ON-003](CI-SPD/iteration_01/04_ON003_ewald_plan.md) after receiving the
user's ON-003 launch command. The plan controls fixed states, mathematical
contract, grids, precision, memory, checks and allowed continuations.

Your objective is to determine whether shared geometry-to-Fourier maps,
frequency-dependent propagation and matched near corrections reproduce the
complete Müller service at useful cost. Produce an accuracy/cost result,
not merely another implementation proposal.

1. Freeze the prescribed TG-002 states, source hashes and reference behavior.
2. Resolve the finite-tau split, outgoing treatment, flux-coordinate mapping,
   normalization and flat/circle controls.
3. Build the prototype and test the declared curved states, both media,
   real/damped frequencies and all four Müller blocks.
4. Evaluate complete paired predictions, retaining existing source/receiver
   work in the cost. Measure setup, assembly, memory and total service time.
5. Follow the declared continuation and closure rules below.

| Evidence | Required next step |
|---|---|
| Accurate and faster full fields | Qualify full shape derivatives, repeat timings and close forward feasibility |
| Local approximation fails | Use the declared near correction within budget |
| Fourier resolution fails | Use only the declared grid/order refinement |
| Accurate but slower | Report the crossover and close |
| Only damped fields qualify | Retain that component result and the real-frequency failure evidence |
| Fields qualify but derivatives fail | Retain forward success and explicitly block inverse integration |
| Formulation or resource gates remain unresolved | Preserve the diagnosis and close with the plan's corresponding status |

Use the integration review's corrected mathematics: `tau=1/(4*xi^2)`, a
common-grid scale covering both media, matched outgoing far/near treatment,
and the actual flux-coordinate basis. A flat single-layer formula does not
qualify the full transmission system. Differentiate normal-flux maps and
local corrections too.

Boundary quadrature is allowed as declared, labelled **quadrature-based and
boundary-collocation-free**. Claim coefficient-only construction only if it
was actually implemented and qualified. Do not infer mathematical novelty
from a missing literature search result.

Keep implementations opt-in. Stop new variants after hour six and reserve
the final 90 minutes for qualification summaries, timings and reporting,
within the eight-hour total. Neither a positive result nor remaining spare
time authorizes an inverse campaign, ON-002 or a 3D rewrite.

Write evidence under `results/validation/cleaned_interfaces/ON-003/` and its
CI-SPD report. Deliver the derivation, fixed-state manifest, block/field/
derivative error tables, actual timings and memory, failed configurations,
representation claim, commit hashes and explicit terminal classification.
Give Agent 1 the final report link for shared indexes. A useful negative
result is a completed feasibility experiment; incomplete coverage stays
explicitly incomplete.
