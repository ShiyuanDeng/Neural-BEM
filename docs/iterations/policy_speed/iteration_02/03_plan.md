# PS-003: explain and reduce GPU-slider fit time

## Questions

1. Does hook need many iterations because M is too small, because the optimizer
   makes small moves, or because it keeps trying poor trial curves?
2. Which existing policy reduces time while keeping hook c13.3 recovered?
3. Does GPU slider, with and without that policy, work on other TG-002 scenes?

**Plan finalized on 2026-10-26. Scope confirmed by the user:** "sounds good.
finalise the plan". **Execution authorized on 2026-10-26:** the user requested implementation
of this plan. The original finalization request did not launch the fits.

Work in the existing `organised` checkout. No new branch or worktree.
The limit is **13 new fits**, including every failed or interrupted fit.

## Saved evidence

Reuse [GU-002](../../../../results/validation/cleaned_interfaces/GU-002/README.md)
and [PS-002](../../../../results/validation/cleaned_interfaces/PS-002/README.md).
Do not rerun either reference.

GU-002 recovered hook in 30.3 s and 125 accepted iterations. M11/M15 took
15.9 s, with no backtracking. PS-002 cut the count to 58, but failed recovery;
later rejected trials consumed much of the time saved by early exits.

The first job is to explain these differences using the saved stage records.
This requires no new fits. Treat the old timings as reference measurements,
not as controls run beside the new fits.

## 1. Three policy comparisons on hook

Run each once on `hook__c13.3`, using modal Muller and GPU slider:

| Run | Existing policy | Main changes from the baseline |
|---|---|---|
| H1 | `feedback` | Agreement damping, stopping after shortened low-progress iterations, less terminal Jacobian work |
| H2 | `four_phase` | Feedback plus similarity warm-up, a different M sequence and compact K |
| H3 | `compact_release` | Feedback plus stage-entry reuse and K=2M+2 |

Use [the policy registry](../../../../solvers/bem_inverse/policies.py), retaining
each policy's declared options. A small campaign adapter must select slider
explicitly: the named-policy entry point currently binds spectral geometry.

`four_phase` uses similarity for its warm-up only. Its later stages use slider.
Record this exception. Its full-catalog (M,K) pairs are (11,24), (15,32),
(19,40), (25,52), then (95,192); their Ku values are 64,64,64,64,128.

Skip `validity_first`, which has no effect on slider, and `exact_fast`, which
duplicates entry reuse here. Do not add `reach_clip` or a threshold sweep.
The three policy runs compare bundles; they do not isolate individual causes.

## 2. At most two comparisons to separate causes

Run these after H1-H3. Write each run's resolved settings and reference into
its manifest before starting it. Do not replace a failed comparison with tuning.

**D1: release M earlier.** Start from the GU-002 baseline policy and change
only `release_bands` from (11,15,19) to (19,). Keep the earlier stages, K192,
Ku128, full F, damping and subsequent fixed-stage rules unchanged.

This asks whether M11/M15 are useful preparation or expensive restrictions
on the available update directions. Compare with GU-002. Later trajectories
and the measured final frontier can change; that is an outcome of this change.

**D2: choose one comparison using H1-H3, in this order.**

| Observed result | Single change for D2 | Question |
|---|---|---|
| The fastest recovering H1-H3 policy is `four_phase` or `compact_release` | Repeat that policy with Ku fixed at 128 in every full-real-catalog fit stage; retain its K, M, F and other settings | How much of its result comes from lower physics resolution? |
| Otherwise, `feedback` recovers | Repeat `feedback` with `minimum_relative_progress=0`; keep agreement damping and all other options | Does its shortened-progress exit help? |
| None of H1-H3 recovers | Use the baseline policy with the PS-002 5% / two-iteration exit only from M11 onward | Can earlier exits help while preserving the earlier-stage path? |

For the Ku comparison, keep prefix resolution and the final checks unchanged.
The normal coefficient workspace follows Ku as usual. This isolates the
physics-resolution setting, not Ku from its required workspace cost.

For the feedback comparison, zero minimum progress disables the shortened-
progress exit because accepted losses never increase. It does not enable the
plain progress exit or change LM damping.

D2 can be omitted if its selected comparison adds no useful distinction to
the recorded settings. No substitute fit is added. Two comparisons cannot
separate every bundled effect; state what remains uncertain.

## 3. Four other cases

After the hook comparisons, select the recovering alternative with the lowest
hook fit time among H1-H3 and D1-D2. It must be faster than saved GU-002's
30.294 s. For an exact time tie, prefer fewer actual forward/reciprocal calls,
then the earlier run ID. Freeze the selected settings before the next cases.

Run baseline GPU slider and the selected policy once on each:

| Case | What it checks |
|---|---|
| `circle__c4` | Easy shape |
| `kite__c0.5` | Expensive shape that earlier fits recovered |
| `c_shape__c13.3` | Deep concavity that earlier fits recovered |
| `aphex_twin__c13.3` | Hard shape that the earlier spectral pipeline did not recover |

That is eight fits. If no alternative is both faster and recovering on hook,
run baseline GPU slider alone on the four cases. This still checks slider
beyond hook. Do not select a fast failed policy for this comparison.

Total: **3 hook policy fits + at most 2 cause comparisons + at most 8 other-
scene fits = 13**. No other scenes, seeds, starts, retries or budget extensions.
An interrupted run consumes its slot and its evidence is preserved.

## Shared settings and run limits

- TG-002 frozen data; one centred start; no localization or grid search.
- Explicit CUDA for modal assembly and slider preparation, four frequency
  threads, single-threaded BLAS, and one fit at a time.
- Each new fit: **13,412 work units and 120 seconds**. Use the same limits
  for every policy. GU-002 completed within this time, so remains eligible
  as the saved reference. A timeout is a result, not a reason to rerun.
- Final numerical checks: **300 seconds**, retaining the existing tolerances.
  Report their time separately from fit time.
- Keep material, physical units, geometry/physics checks and recovery criteria.
  K/M/Ku/F and optimizer behavior change only as the chosen policy or the
  declared single-control comparison specifies.
- Reuse the existing default rule settings. Do not add the PS-002 exit to
  every arm. Only the explicit D2 fallback uses its 5% / two-iteration rule.

## Record the explanation during the runs

Keep existing histories and counters. Add only missing scalar records; do
not compute extra forward solutions or save large matrices for this study.

| Record | What it tells us |
|---|---|
| K, M, Ku, F and loss at each stage entry | Whether the problem or update space changed |
| Accepted loss, recent decrease, gradient and elapsed time | Where progress becomes slow |
| Raw, clipped and used movement sizes; damping and backtracks | Whether damping, bounds or rejected trials shorten the move |
| Damping retries and tiny-proposal skips | Work absent from the existing trial list |
| Actual forward/reciprocal calls and charged units, separately | Whether reuse avoids solves without changing the accounting |
| Existing expansion-size and geometry-bound diagnostics | Whether particular curves make physics more expensive |
| Preparation and physics timing from existing call boundaries | Whether cost moves between geometry and physics |

Use accepted-history timestamps for iteration elapsed time and stage timers
for stage elapsed time. Do not add overlapping frequency-thread timers and
call the sum wall time. Compare losses and gradients within fixed stages.

Use the same lightweight recording in all new fits. Saved GU-002 lacks some
of these records; report those gaps without rerunning it solely for recording.

## Decide and report

Recovery retains the TG-002 rules: passed final numerical checks, RMS at most
1 mm, Hausdorff upper bound at most 2 mm, and every frequency residual at most
0.003. A faster failure is not an improvement.

For hook, report recovered fit time first, then accepted iterations, actual
physics calls, charged work and the stage-by-stage explanation. Show losses
against both accepted iterations and elapsed time, with stage boundaries.

For the four other cases, report each outcome and time separately. Preserve
any baseline successes and identify new recoveries or regressions. Do not
claim a 30-case result or a repeatable small speed difference from one fit.

Use the controlled comparisons to state which change affected the outcome.
Where bundled effects or missing old records prevent an explanation, say so.
Do not add fits just to remove the remaining uncertainty.

## Implementation and saved work

Keep numerical controls in `solvers/bem_inverse/` and campaign selection,
case names and truth scoring in `experiments/benchmark/`. Keep the registry's
default spectral policy intact; expose its slider adaptation explicitly.

Before the fits, use only small checks that the adapter selects the intended
geometry and policy options, and that added recording leaves decisions
unchanged. Reuse existing solver/GPU evidence; no broad test campaign.

Save manifests, source revision, settings, histories, failures and reports
under `results/validation/cleaned_interfaces/PS-003/`, with a fresh folder for
every run. Preserve GU-002 and PS-002. Commit and push each completed run to
`organised`, then verify the push and working-tree state.

The next results document belongs in `iteration_03/01_results.md`. Update the
track README with completed run IDs and the exact next run; the 13-fit limit
does not authorize an open-ended search or promotion of a new default.
