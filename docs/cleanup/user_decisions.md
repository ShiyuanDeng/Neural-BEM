# User decisions and lessons for agents

Read this before proposing cleanup changes. Each entry records what an agent
proposed, what the user decided, the user's reason, and the rule that follows.
Add an entry whenever the user decides an item or corrects an agent. Quote the
user's words where they carry the reason. Do not reopen a decided item unless
the code now contradicts it.

Earlier geometry-update decisions (method-local files, flat classes, delivery
scope) are in
[iteration 01 concerns](../../../Neural_SDF_BEM_AD/docs/iterations/geometry_updates/iteration_01/04_concerns.md).

## Rules that follow from the decisions

1. A validity check belongs on the shape that is actually used. Trace every
   operation applied after the check; if a later step reshapes the object, the
   check guarantees nothing (D1).
2. Judge counters, timers and saved diagnostics one by one, like any other
   item. Do not keep or drop them as a group (D2).
3. Do not pass the same data twice and then check that the copies agree (D3).
4. A choice is made once, where the method is selected. Do not recover it
   later through binders, type checks or method lookup (D6).
5. No forwarding methods, compatibility aliases or kept class chains to save
   caller edits; change the callers (2026-10-21, before this log).
6. Before proposing to replace an object argument, list every attribute the
   function reads, writes and calls on it (L1).
7. Question the shape of an interface, not only the code inside it (L3).
8. The fit does not re-run physics or geometry at a finer resolution to
   check itself (D7).

## How the user wants findings presented

- One list. Label every item **OBVIOUS** (keeps the mathematics exactly the
  same) or **DECISION** (changes method, checks, tolerances, defaults or data
  ownership with a real tradeoff). Do not put decisions in a separate section.
- Write each item as short paragraphs with bold labels: **What it is now**
  (plain words, `path:line`), **The problem**, **The fix**, **What has to
  change** (every file and caller, named), **Math** (changes or not, exactly).
- For a decision, give each option with concrete consequences, then a
  recommendation. Prose, not multiple-choice prompts.
- Put counter, timer and diagnostic items at the end of the list.
- Do not volunteer which complexity is necessary. Explain it when asked, with
  a specific reason.
- Define any term the user may not share (for example "entry point").
- When the user is confused, explain with plain logic and precise technical
  terms: the actual call chain, step by step, not a reframed summary.
- When asked for open items, list only open ones.
- While the user is still deciding, record concerns next to the plan instead
  of pushing decision prompts.
- To explain a reorganisation, show a short pseudocode sketch of the resulting
  loop with each line tagged by its chain step. User: "its really the level of
  clarity of code that i hope to see in acc repo." Name every object in the
  sketch by what it does; explain any new object before using it.

## Decisions

Source for D1–D6: `geometry_update_methods/spectral.py` and its callers at
commit `7fc5ff932`, discussed and implemented on 2026-10-21 (uncommitted).

### D1. Checks on the pushed curve — removed

**Context.** The spectral trial pushed the accepted curve along its normal,
checked area, speed and self-intersection of that pushed curve, refitted it in
arclength, centred it (current curve + refit of pushed − refit of unmoved), and
checked the final curve again.

**Proposed.** Claude first recommended keeping all three pushed-curve checks
("each step is a valid motion of a non-crossing curve"), then keeping only the
speed check "because the refit needs it".

**Decided.** Remove all three. User: "the first check on the raw updated
coefficients does not represent the same boundary after refit, because of the
centering operation … you dont check on something then let it undergo some
other shape change."

**Why Claude was wrong.** It did not trace what happens to the pushed curve
after the check. The centring step means the pushed curve is never the boundary
that is used.

**Status.** Implemented in `spectral.py` (also used by `analytic_spectral`).
Final-curve checks stay. The crossing-refusal test, README and chain map were
updated.

### D2. Timers inside the trial — kept

**Proposed.** Claude recommended dropping the separate timers for checks and
refits so the trial reads as mathematics only.

**Decided.** Keep both. User: "i would keep counts on time spent on checks and
refits respectively, but this doesnt mean in other places i want every single
counts." Then: judge such items normally, as obvious or decision; "maybe you
can put all of the recording stuff at the end, but just dont treat them
differently when you are judging."

**Status.** Kept. After D1, the check timer covers only the final checks; the
refit timer also covers building the pushed curve.

### D3. Curve passed twice — removed (OBVIOUS, accepted)

Every trial function took `curve` and also `prepared`, which holds the same
curve; four methods checked that they matched. The trial now reads
`prepared.curve`. Implemented in all seven method files and in `fit_stage.py`,
`endpoint.py` and `experiments/trial_curves/replay.py`.

### D4. One move-and-refit function (OBVIOUS, accepted)

The push-along-normal-and-refit step existed twice in numpy
(`spectral_project` and inside the trial). Now one function,
`push_and_refit()`, used by spectral, analytic and certified preparation and by
the spectral trial.

### D5. Frozen preparation filled during trials (OBVIOUS, accepted)

`Prepared` was frozen but trials filled its `cache` with grid samples. Now
`prepare` stores both grids as plain fields (`grid`, `fine_grid`). Implemented
for spectral and analytic; certified keeps its own cache.

### D6. Binders — removed (provisional, review pending)

**User's view.** "why cant you pass geometry_update function, and forward
solver function into fit_stage()? the binder is soo dumb." Details and the
remaining choice: [binder note](geometry_update_forward_binders_2026-10-21.md).

**Status.** Implemented in step 3 of the
[architecture note](bem_inverse_architecture_2026-10-24.md) as D8 allowed.
`make_update(name)` returns the update object with its module's
`geometry_update`; `make_backend(solver)` returns the physics context with its
`forward_solve`. `fit_stage()` takes both functions; both binders, the one-line
`geometry_update` methods and the `evaluate` forwarders are gone. The user
reviews this shape after the build (D8).

### D7. Finer re-evaluations — remove (direction decided 2026-10-25)

Source: discussion of the 2026-10-24 architecture review of
`solvers/bem_inverse/` at commit `aeedb28ff`.

**Proposed.** Claude sketched the reorganised `fit_stage()` with a
resolution-response module (hard stop or promotion) returning a "verdict", and
a deepened `Objective` holding refined evaluations.

**Decided.** Remove everything that re-evaluates at a finer resolution. User:
"i was meaning to get rid of everything related to finer re-evaluations, this
includes running physics at finer resolutions, and checking geometry update
precisions at finer resolutions." The user also did not like the `Objective`
class ("i dont understand its use and name") or the unexplained `verdict`.

**What this covers.** C11 refined solves, the two-resolution gain test and
field agreement; resolution promotion (`ResolutionResponse`, `nodal_fixed` and
`modal_response` promotion); the geometry update's second, 2N-sample refit and
its agreement check; nodal stage selection; localization's two-resolution
qualification.

**Follow-up decisions (2026-10-25), accepting Claude's recommendations.**
The endpoint audit moves to `experiments/benchmark/` and runs after `fit()`
returns. The geometry update keeps only its N-point refit, so accepted trial
curves stay bit-identical. `Objective` and `WorkingObjective` are deleted;
`fit_stage()` uses local `evaluate` and `linearize` steps.

**C11 acceptance.** Claude proposed keeping the margin on the working gain.
The user first asked for a stall test, then decided: "damping and backtracking
loops only produce one accepted curve, hence no need for the stall test. just
keep the loss decrease requirement in backtracking candidates." A trial curve
is accepted when its loss is lower than the current loss; the margin goes.

**Status.** Implemented in step 2 (2026-10-25). NR-001 ran TG-002 on it; see the
[architecture note](bem_inverse_architecture_2026-10-24.md) for results.

### D8. Round-1 cleanup items (2026-10-25)

Accepted as Claude recommended: delete the unreachable research code rather
than move it (card A); delete the shims in the package and in `experiments/`,
drop the class module overrides, and map old names only when loading the one
saved pickle (card F); move only the Gaussian and similarity checks to their
method files (card G); three small fixes. The user asked for "a minimalist
glossary.md" in addition to the chain map's symbol table.

Passing `geometry_update` and `forward_solve` into `fit_stage()` (D6) and
charging only through `Ledger.calls` (card E) are provisional. User: "im not
100 percent sure but i will see how the build turns out."

Also accepted ("yes to all"): keep the three implementation steps separate so
the pure reorganisations can be checked for identical numbers; one full
TG-002 run after the maths change, with the 13,412-unit budget unchanged;
"trial curve" as the term, not "candidate"; the optional `agreement` damping
keeps its progress exits.

### D9. Departures from the plan, found while building (2026-10-25)

After the build, Claude listed where it went beyond the plan
([implementation notes](bem_inverse_architecture_2026-10-24.md#implementation-notes)).
User: "i agree with you on decisions."

Accepted: the spline update loses its doubled-grid check under D7 (Q12 did not
name it); each linearization reserves 2 units per frequency instead of 4;
`accuracy_exit`, `decision_gate`, `resolution_response`, `adaptive_resolution`
and `working_frequencies` go with their mechanisms, and `feedback` descends from
`baseline`; `make_update` returns `(update, geometry_update)` and `make_backend`
returns `(context, forward_solve)` because the runner builds stage-local updates
by name; localization keeps the best grid point after coordinate refinement.

Rule that follows: when a removed mechanism leaves a policy, option or check with
no remaining effect, delete it with the mechanism.

**Not decided.** Claude's review of the build raised three DECISION items and
gave options but no recommendation, so no choice is recorded; they stay in Open.

### D10. Continue from analysis to useful follow-up experiments

**Decided 2026-10-26.** The user asked to change the rule that stops agents
from doing further experiments after analysis.

**Reason.** The blanket stop prevents an agent from investigating the next
question exposed by its results within already requested research work.

**Rule.** Pre-register and run the smallest evidence-driven follow-up on the
same authorized question without per-ID reapproval. Keep explicit user-set
hard limits and exclusions; preserve earlier results and original criteria.

**Status.** Updated `AGENTS.md`, the iteration workflow and implementation
principles. Agent-written run counts can be amended prospectively; a different
research question or departure from explicit user limits still needs a decision.

### D11. Final two-resolution check — removed from recovery (2026-11-02)

**Context.** In the 2 November 2026 run comparison, three BEM runs had the right shape and
field residual but were marked "not recovered" by the endpoint check. That check
compares fields and Jacobian columns at the production and refined resolutions.

**Decided.** User: "dont mind it just delete that, and run the cases that were
previously identified as false by that check again real quick. replace currect
data with that version".

**Reason.** It is the last finer re-evaluation left after D7. Recovery should
rest on the shape limits and the field residual only.

**Rule.** TG-002 runs no longer call the endpoint check. Recovery is RMS <= 1 mm,
Hausdorff upper bound <= 2 mm and per-frequency field residual within its limit,
with the residual computed at the fit's own resolution. The nine affected MR-001
case folders were overwritten (user: "just rewrite data in those cases"); the
earlier versions stay in git history.

**Status.** `campaign.run_case` and `mr001.run_case` call `final_residual`
instead. `audit.py` stays for the two studies that import it directly
(`frequency_interpolation`, `geometry_charts`). 2 November 2026 run amendment B1 reran the
nine affected runs.

### D12. Stage-one baseline comparison scope (2026-11-17)

**Context.** The extracted 2 November 2026 run plan put TG-002-F in Stage 1, included
top-frequency and gradient-descent ablations, and retained the existing
longest-contour scoring path. The user revised the required actions.

**Decided.** Move TG-002-F and production plane-wave support to Stage 2.
User's reason: "It shouldn't delay the first baseline comparison."
The first comparison remains on sealed TG-002.

**Decided.** Prioritise four ablations: real-only versus real+damped;
modal versus nodal BEM; adaptive versus fixed-bandwidth continuation;
frequency continuation versus simultaneous inversion.

**Rule.** Gradient descent and top-frequency-only are no longer mandatory.
Reuse matching core runs for the ablations. Keep data, backend, bandwidth
and frequency-schedule comparisons distinct.

**Decided.** Count all reconstructed components, include material-field
error, and make unaligned area difference the primary region metric.
User: "not just the largest contour."

**Rule.** Smaller reconstructed components remain in scoring. Freeze the
support threshold, component convention and material-error definition;
do not hide extra regions by scoring only a selected contour.

**Decided.** Remove damped observations from the entire real-only inversion,
including initial localisation. User: "This requires changing the current
Problem interface."

**Rule.** Represent the absent catalog explicitly in `Problem`; initialization,
material estimation, warm-up and all fitting stages must use only real data.
Keep TG-002's centred start and localization `none`.

**Decided.** Keep report corrections, clean and 5% noisy multi-seed cases,
independent forward validation and a frozen evaluation protocol.
Freeze the protocol before external baselines, without waiting for every ablation.

**Rule.** The protocol and core reference results prepare the first comparison;
unfinished ablations and Stage 2 plane-wave work do not delay it.
Record any later protocol change before the affected runs.

**Status.** Revised the [stage-one actions](../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/02_proposals/01_stage_one_actions_verified.md).
This revision changes the action list; implementation and new experiments
have not started.

### D13. Keep GauGal native-scene and TG-002 timings separate (2026-11-17)

**Context.** Asked for GauGal's cost, the agent gave the TG-002 adaptation's
340-second median. The user reminded it that GauGal took seconds per scene
on its own scenes.

**Evidence.** Original cylinder cases 8, 13 and 14 took 0.814, 1.265 and
0.865 seconds of optimization for 300 iterations at 0.4 GHz on the RTX 5090.
[Saved results](/home/drdeng/Gau-Gal/docs/iterations/GGB-001/results.md).

**Rule.** Retain the original seconds-per-scene result when discussing cost.
Label the 340-second median as the 19-frequency, 80-iteration TG-002
adaptation. The settings alone do not explain the full timing gap.

**Status.** Added both timing contexts to the stage-one source checks.
No new experiment was run.

### D13. 17 November 2026 run stage-one runs, scoring and storage (2026-11-17)

**Context.** Interview on the D12 stage-one proposal. The plan is
[17 November 2026 run](../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/03_plan.md).

**Decided.** Stage 1 is a fair evaluation of our own method and makes no
claims. User: claims "should wait until we see how baselines perform in
stage 2." Other external baselines are Stage 2.

**Decided.** The default method is real-only with recovered contrast, and has
no warm-up. User: "stop calling it headline-arms, just default method";
"scratch warm up completely."

**Decided.** Only the default runs all 30 scenes. Every other run drops the
contrast 13.3 scenes (20 scenes). User's reason: other baselines "dont have
scenes with that high contrast and i couldnt justify it."

**Decided.** Add single-frequency recoveries at 0.5, 1, 1.5 and 2 GHz on
clean data. Noisy data and damped data never appear together.

**Decided.** Start with 1% noise, three draws; raise to 5% only if 1% is good
and time remains. User: "we have not used noise before." GauGal runs last on
noisy cases with no tuning effort, and the report must say so.

**Decided.** Success is area error alone, provisionally at most 5%, slightly
loose, adjustable once all raw metrics exist. It is a data-analysis choice
and never affects stopping during a fit.

**Decided.** Run limit is 6 hours. An agent explores next steps in the
remaining time, named or as it sees fit.

**Decided.** Storage root is `results/`, which the user is clearing. Layout:
`<family>/<variant>_<data>_<contrast>_<frequency>/<case>/`. User: this "would
help us distinguish our methods with many more methods to come."

**Rule.** Use the name "default method". Every run folder carries all four
tags in fixed order. Save raw metrics per fit so a changed cut-off is a
recount, not a rerun. Do not tune the default or GauGal in Stage 1.

**Status.** Plan written; implementation and runs have not started.

### D14. Separate development evidence from new results (2026-11-17)

**Decided.** User: "sure leave these, rename to archive_results or more suitable
names to reflect these are for development use, not final results. then leave the
new results folder blank".

**Reason.** The retained runs explain development choices and earlier comparisons;
they are not the final results of the revised baseline protocol.

**Rule.** Keep the agreed evidence in `development_results/`. Leave `results/`
empty for new runs. Preserve complete historical runs in the recorded Git revision;
do not relabel old runs as new final results.

**Status.** Retained the sealed benchmark, selected BEM/GauGal reconstructions,
settings, failures and compact checks. Updated active readers and evidence links.
Details are in [the reorganisation record](development_results.md).

### D15. 17 November 2026 run: write the code first, a cheaper agent runs it (2026-11-17)

**Context.** Before any 17 November 2026 run run, the user asked how to split the work.

**Decided.** Write the code first, then run everything with a cheaper agent.
User: "we should prob write code first then run everything with a dumber agent."

**Decided.** The code writer tests little. User: "do minimal testings here,
leave more comprehensive tests to the agent that acc runs all these methods."

**Rule.** Hand over one command per planned run that resumes and stores results
itself. The running agent does not edit solver or scoring code; it reports a
crash instead. Wider checks belong to the runs, not to the code-writing step.

**Status.** Code is in `experiments/comparison/`; see the
[implementation record](../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/03_plan.md#implementation-record-17-november-2026).
No planned run has started.

### D16. Retain Stage 1 documentation and code reference (2026-11-17)

**Decided.** User: "only retain a few iterations" and "for now i want to only
leave the relevant stage 1 work". General README and other documents outside
iteration folders can go. Keep `reference/`: "that helps with code understanding".
Update `cleanup/` to record the change.

**Reason.** Apply the results-folder cleanup approach to documentation: keep the
current work easy to find and remove old development material from the active tree.

**Rule.** Under `docs/`, retain the Stage 1 proposal and 17 November 2026 run plan, code reference,
and cleanup decisions. Preserve removed history in Git. Do not delete uncommitted
Stage 2 decisions without first settling their preservation.

**Status.** Completed under D17 and D18: the Stage 1 files use the descriptive
name, and unwanted docs have moved to the original workspace. See
[the documentation cleanup record](documentation.md).

### D17. Descriptive iteration names and dated run names (2026-11-17)

**Decided.** User: "stop using this letter name that have no information in it"
and "just call it the run we had at <when>". Name the current iteration
`baseline_generation`.

**Reason.** Run names should communicate when the work happened; iteration
folders should communicate what the work does.

**Rule.** Use the run date in current prose and the purpose when needed to
distinguish runs. Keep original strings in saved evidence and source paths.
Do not conflate the November TG-002 comparison with the October SingleTX work.

**Status.** Moved the Stage 1 proposal and plan to
[`baseline_generation/`](../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/03_plan.md), updated
links and current labels, and renamed the saved-fit import command to
`import-gaugal-2026-11-02`. Numerical settings and saved results are unchanged.

### D18. Move removed docs and results into the original workspace (2026-11-17)

**Decided.** User: "delete, but when you do that can you move those that were
not in the original unorganised foler to the unorganised folder" so that
"all legacy docs and results will be there", including earlier cleanups.

**Reason.** Historical documentation and results should remain directly available
in one legacy workspace, rather than being recoverable only from Git history.

**Rule.** Before deletion in `organised`, preserve missing historical material in
`/home/drdeng/Neural_SDF_BEM_AD`. Keep both versions when a path differs. Include
the four uncommitted Stage 2 documents; their transfer is now authorized.
Use existing branches and worktrees.

**Status.** Completed: 7,116 files preserved, including 204 differing versions,
and 61 unwanted documentation files removed here. Sources, destinations and
verification are recorded in [the documentation cleanup record](documentation.md).

### D19. Remove the remaining legacy-result copies (2026-11-17)

**Decided.** User: "also move legacy results to there if you havent".

**Reason.** Legacy outputs should live in the original workspace, rather than
remaining duplicated under the organised workspace's `development_results/`.

**Rule.** Verify the remaining legacy copies in the original workspace before
removing them here. Keep the sealed TG-002 input bundle used by current runs.
Read historical comparison outputs from the original workspace.

**Status.** Removed 486 verified legacy duplicates and replaced the development
README with an input-location note. The import and historical figure readers
load all 30 cases from the original workspace. Current results and sealed inputs
are unchanged; no fitting or rescoring was performed.

### D20. Agent instructions follow the cleaned layout (2026-11-17)

**Requested.** User: "help me clean up agents.md ... and the one about
iteration structure of docs, and other problems related to agentic workflow."

**Reason.** After D14–D18, `AGENTS.md` and the readability reviewer still sent
agents to the legacy checkout, deleted workflow pages, removed compatibility
imports and the old `spectral` default.

**Rule.** `AGENTS.md` carries the short iteration layout and the experiment
rules the deleted workflow pages held. This log is the one place for shared
decisions and lessons; agent memories point here rather than copy it.

**Follow-up.** After checking the Claude Code and Codex guidance, the user
said: "yes i think we should mke it shorter." `AGENTS.md` keeps only rules an
agent cannot find in the code or READMEs. Claude Code now asks before
commands that create a branch or worktree.

**Status.** Implemented; see [the agent instructions record](agent_instructions.md).

### D21. Action-based iteration folders with adjacent plans and results (2026-11-17)

**Decided.** The user requested folders that name "what is to be done or what
is done, so always with an action", then approved the minimal instruction
draft: "yep write this".

**Rule.** Use `docs/iterations/<action>/<NN>_<activity>/`, with `plan.md` and
`results.md` together. Both folder names describe actions; run dates and
settings belong in the documents. Keep earlier conditions and findings.

**Status.** Saved the iteration instructions as `docs/iterations/AGENTS.md`
(merged into the root `AGENTS.md` under D23) and
replaced the root instruction's old folder convention with a pointer there.
The instruction file was saved first; D22 records the subsequent migration.

### D22. Apply the action-based structure to current iterations (2026-11-17)

**Decided.** User: "reorganise current iterations" after approving D21.

**Rule.** Separate the completed study into clean/noisy recovery, ablations and
its untuned GauGal reference. Give each activity a `plan.md` and `results.md`.
Preserve the original combined documents before rewriting their organisation.

**Status.** Completed under `evaluate_our_method/`, with six plan/result files.
The original combined plan and proposal are in the legacy workspace; the
results summaries use all 370 saved scores without fitting or rescoring.
See [the cleanup record](documentation.md#reorganise-current-iterations-2026-11-17).

### D23. Iteration rules live in the root instructions (2026-11-17)

**Decided.** Merge `docs/iterations/AGENTS.md` into the root `AGENTS.md`.
User: "i agree we should merge". Codex loads only the root file when it starts
at the root, and Claude Code loads a folder's file only after reading inside
it. Starting an iteration is the user's most common request.

**Decided.** User: "if results.md are present, definitely start a new
numbered iteration. if not, default to editing current plan."

**Rule.** If an activity has `results.md`, further work opens the next
numbered activity. Otherwise edit that activity's `plan.md`. This replaces
dated plan amendments. The investigation the user starts covers its
follow-up activities; ask before leaving its topic or exceeding the user's
limits.

**Status.** Implemented in the root `AGENTS.md` "Iterations" section; the
separate file was removed.

## Lessons from agent mistakes

### L1. Proposal built on half the facts

Claude proposed "pass the length unit, tolerance and name instead of the whole
`settings` object". The trial also writes counters and calls `_checked` and
`measure` on that object, so three numbers cannot replace it. Rule 6.

### L2. Unverified claim

Claude said "each method needs different settings". A check afterwards showed
all methods read the same three numbers. The real difference was counters and
helpers. State only what a grep or read has confirmed.

### L3. Anchored on the existing interface

Claude framed the choice as "method or module function" because it assumed
`fit_stage()` must find the function from the object. The user's simpler idea,
passing the selected functions in, was missed. Rule 7.

### L4. Unclear explanation

The user had to ask "what reads??" and "settings on what?". Name the
function, the object and the attribute; never use "it" for a code element.

## Open

- **D6 and card E, after the build.** Both are implemented provisionally (D8):
  functions passed into `fit_stage()`, and every charge through `Ledger.calls`.
  The user reviews them; see the architecture note's implementation notes.
- **Exact-match test (DECISION).** `test_geometry_update_methods.py` requires
  the spectral and certified trials to match bit for bit. Since D1, some runs
  differ by 3e-17 with identical inputs; before D1, 20 of 20 runs matched.
  Options: a 1e-15 absolute tolerance, or leave it failing like the two older
  exact-equality failures. Claude recommends the tolerance.
- **`_project` counting wrapper (OBVIOUS).** In `spectral.py` and
  `certified_spectral.py` it only adds 1 to `geometry_projections` before
  calling `push_and_refit`. Count once, as the batched path does.
- **Band-matched nodal endpoint check (DECISION).** The moved audit takes both
  resolutions from `resolution_profile()` and dropped the old 2048-node floor
  and independent N1024/2048 reference. Options: restore that rule in
  `experiments/benchmark/audit.py`, or accept it (band-matched is experimental;
  `modal_fixed` is unaffected).
- **Failure records in `Ledger.calls` (DECISION).** It records a failure for any
  exception, including derivative failures, so failure receipts differ from the
  step 2 code on crash paths only. Options: keep, or record numerical
  exceptions only.
- **Strict dispatch switch (DECISION).** `runner.fit` still turns it on only for
  `nodal_resolution_profile='band_matched'`, a link left from the deleted nodal
  stage selection. Options: an explicit `Execution` or `Ledger` option, or drop it.
- **Legacy CI-001 runner (OBVIOUS).** `experiments/cleaned_interface/benchmark.py`
  reads `final_audit_passed` from `fit()`, which no longer returns it. Run the
  endpoint audit there or delete the runner; CI-001 inputs are not on this branch.
- **Repeated code (OBVIOUS).** The single-call charge pattern appears three
  times (`audit.py`, twice in `runner.py`), and the settings → method lookup
  three times in `campaign.py`.
