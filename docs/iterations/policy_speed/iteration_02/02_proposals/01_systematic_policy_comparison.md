# Why hook takes so many iterations, and how to shorten the fit

## Questions

1. Which stages cost the time: small improvements, rejected trials, or expensive physics solves?
2. Which existing policy works best with GPU slider on hook c13.3, while keeping recovery?
3. Does GPU slider, and any policy improvement, also work on other TG-002 scenes?

**Status: scope accepted and consolidated into the [PS-003 plan](../03_plan.md),
2026-10-26.** The user accepted the three hook alternatives, at most two cause
comparisons and four other cases. The text below preserves the discussion draft.

## What we already know

- GU-002 GPU slider recovered hook in 30.3 s, with 125 accepted iterations.
  M11 and M15 used 15.9 s: 53% of the fit. Neither stage backtracked.
- PS-002 used the 5% / two-iteration rule everywhere. It took 25.5 s and
  58 accepted iterations, but failed recovery. Do not repeat this fit.
- PS-002 saved 10.2 s at M11/M15, then spent 7.9 s more at M43/M49 than
  GU-002. Those later stages had eight rejected trials; GU-002 had none.
- D3 has a slow patch followed by useful progress. Fewer iterations there
  can change the later path. A small recent loss decrease is not enough to
  prove a stage has become unnecessary.

Sources: [GU-002](../../../../../results/validation/cleaned_interfaces/GU-002/README.md),
[PS-002](../../../../../results/validation/cleaned_interfaces/PS-002/README.md).
The stored physics timers overlap across frequency threads; their sum is not
elapsed time. The two fits also ran on different days.

## Existing policies

The list is in [policies.py](../../../../../solvers/bem_inverse/policies.py).
Its historical results used spectral geometry, not GPU slider.

| Policy | What it changes | Proposed use |
|---|---|---|
| `baseline` | Current cumulative stages and scheduled LM damping | Reuse GU-002 |
| `feedback` | Agreement damping, stopping after shortened low-progress iterations, less final Jacobian work | Run on hook |
| `four_phase` | Feedback plus similarity warm-up, a different M sequence and compact K | Run on hook |
| `compact_release` | Feedback plus exact stage-entry reuse and K=2M+2 | Run on hook |
| `entry_reuse` | Reuses stage-entry fields; preserves accepted decisions of feedback | Possible follow-up about time, not iteration count |
| `validity_first` | Reorders certificate checks | Skip: slider does not use those checks |
| `exact_fast` | Entry reuse plus that check-order change | Skip: equivalent to entry reuse for slider |
| `reach_clip` | Further limits proposed movement | Defer: historically unsuccessful and not the first suspected cause |

These policies bundle changes. Comparing them can show which policy helps;
it cannot by itself prove whether damping, stopping, M or physics cost caused
the improvement. Keep that distinction in the conclusions.

In `four_phase`, only warm-up uses the similarity update; later stages use
slider. Its full-catalog (M,K) pairs are (11,24), (15,32), (19,40), (25,52),
then (95,192). The first four use Ku64; the last uses Ku128.

`compact_release` also lowers Ku when K is smaller. It can therefore reduce
both slider preparation and physics cost without reducing iteration count.
K, M, Ku and F must remain visible in every comparison.

## Proposed work

### 1. Compare the three useful policy alternatives on hook

Run `feedback`, `four_phase` and `compact_release` once each with GPU slider
on hook c13.3. Reuse GU-002 and PS-002 as the two saved references. No threshold
sweep, repeat seeds or new starts.

Use the existing policy builders and execution settings. A small campaign
adapter must select slider explicitly: the named-policy entry point currently
binds spectral geometry. Record the resolved policy and actual geometry method.
Do not silently run the named spectral pipeline or change its other options.

Use the same explicit fit and final-check budgets for the three new fits.
GU-002 used 13,412 work units, 1,800 fit seconds and 300 final-check seconds;
the named-policy defaults differ. Choose the common budget before execution.
Run one case at a time, four frequency threads and single-threaded BLAS.

Keep TG-002 inputs, one centred start, no localization and all existing
physics and recovery checks. Physical damping, K/M/Ku/F and LM controls change
only where the selected policy declares that change.

### 2. Separate the likely cause with a small follow-up

Recommendation: allow at most two further hook fits after the first comparison,
each changing one control relative to a named reference. Fix their exact
settings and question before running; unused runs are not replaced with tuning.

Possible questions are whether earlier M release helps with K/Ku/F held fixed,
whether damping helps with the stage-exit behavior held fixed, or whether a
gain comes from fewer physics solves versus cheaper solves. Select the question
from the recorded behavior, rather than running every combination.

If no follow-up can separate the effects within this budget, state what is
still uncertain. A faster bundled policy is not proof of one underlying cause.

### 3. Check a few other scenes

Recommendation: four additional cases covering different behavior:

| Case | Why include it |
|---|---|
| `circle__c4` | Easy control |
| `kite__c0.5` | Costly successful fit in earlier runs |
| `c_shape__c13.3` | Deep concavity, previously recovered |
| `aphex_twin__c13.3` | Hard case that the previous spectral pipeline did not recover |

Run the baseline GPU-slider policy and the best faster recovering hook policy
once on each: eight fits. If no alternative improves recovered hook runtime,
run baseline GPU slider alone on these four. This still answers whether slider
works beyond hook. Do not infer a 30-case result from these four cases.

Proposed maximum: 3 initial hook fits, up to 2 cause comparisons, and up to
8 fits on other scenes: **13 new fits**. The exact scope remains a user choice.
The existing spectral runs provide recovery context, not a fresh timing control.

## Evidence to save during those fits

Reuse existing history and counters. Add only missing scalar records, with
no extra forward solves or saved large matrices.

- Per stage: K, M, Ku, F, elapsed time, accepted iterations and rejected trials.
- Per accepted iteration: loss, recent relative decrease, gradient size,
  elapsed time and physics work. Compare loss and gradients within a stage.
- Per trial: proposed, clipped and used movement sizes, LM damping, damping
  retries, backtracks and tiny proposals skipped before a physics solve.
- Separate actual forward/reciprocal calls from charged work units. Exact
  stage-entry reuse saves calls but deliberately keeps the original charges.
- Keep existing physics diagnostics about expansion size and geometry bounds
  to identify curves that make each solve expensive.
- Report fit time and final-check time separately, with unchanged TG-002
  recovery, RMS, Hausdorff bound and frequency residual criteria.

The main result is elapsed time to a recovered answer. Iteration counts and
physics work explain that time; a faster failure is not an improvement.
Use only relevant small checks for the adapter or added recording, not broad
solver testing. Preserve failed runs and commit/push each completed run.

## First decisions to settle

1. Use the three useful existing policy alternatives on hook, rather than all
   eight registry names? Recommendation: yes.
2. Reserve at most two controlled hook comparisons to separate the causes,
   rather than treating the bundled-policy ranking as an explanation? Yes.
3. Start other-scene testing with the four cases above and at most two policies
   per case, rather than all 30 TG-002 cases? Yes.

The user answered "sounds good. finalise the plan" on 2026-10-26. Budgets,
follow-up choices, selection rules and required records are fixed in the
linked plan. Execution has not started.
