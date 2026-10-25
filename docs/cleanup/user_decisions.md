# User decisions and lessons for agents

Read this before proposing cleanup changes. Each entry records what an agent
proposed, what the user decided, the user's reason, and the rule that follows.
Add an entry whenever the user decides an item or corrects an agent. Quote the
user's words where they carry the reason. Do not reopen a decided item unless
the code now contradicts it.

Earlier geometry-update decisions (method-local files, flat classes, delivery
scope) are in
[iteration 01 concerns](../iterations/geometry_updates/iteration_01/04_concerns.md).

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
