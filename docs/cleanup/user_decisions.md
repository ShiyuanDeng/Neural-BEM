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

### D6. Binders — open

**User's view.** "why cant you pass geometry_update function, and forward
solver function into fit_stage()? the binder is soo dumb." Details and the
remaining choice: [binder note](geometry_update_forward_binders_2026-10-21.md).

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

- **D6, binders.** See the binder note.
- **Exact-match test (DECISION).** `test_geometry_update_methods.py` requires
  the spectral and certified trials to match bit for bit. Since D1, some runs
  differ by 3e-17 with identical inputs; before D1, 20 of 20 runs matched.
  Options: a 1e-15 absolute tolerance, or leave it failing like the two older
  exact-equality failures. Claude recommends the tolerance.
- **`_project` counting wrapper (OBVIOUS).** In `spectral.py` and
  `certified_spectral.py` it only adds 1 to `geometry_projections` before
  calling `push_and_refit`. Count once, as the batched path does.
