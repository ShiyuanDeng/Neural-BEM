# Readability reviewer memory

## Lessons from rejected recommendations

1. **Check the shape that is used (2026-10-21).** I recommended keeping the
   checks on the pushed curve in the spectral trial, then keeping only its
   speed check "because the refit needs it". The user: the centring step means
   the pushed curve is not the resulting boundary; "you dont check on something
   then let it undergo some other shape change". Rule: trace what happens after
   a check before defending it.
2. **Judge each recorded quantity on its own (2026-10-21).** I recommended
   dropping the spectral trial's separate timers for checks and refits so the
   trial reads as math only. The user keeps both, but does not want every
   count elsewhere. Rule: judge each counter or timer like any other item,
   OBVIOUS or DECISION; list them at the end; never keep or drop them as a group.

## Decisions on `geometry_update_methods/spectral.py` (commit 7fc5ff932)

Made 2026-10-21. None implemented yet.

- **DECISION, decided:** drop the area, speed and crossing checks on the pushed
  curve (`spectral.py:271–277`); keep the final-curve checks (:293–301).
  `pytest/bem_inverse/test_geometry_update_methods.py:35–51` expects a
  `self_intersection` refusal and needs updating.
- **DECISION, decided:** keep the timers for check time and refit time.
  Other counters are judged on their own.
- **OBVIOUS, not contested:**
  - Merge the two numpy copies of move-and-refit (`spectral_project` :62 and the trial :262–284).
  - Pass the length unit, tolerance and name instead of the whole `settings` object.
  - Drop the `curve` argument that repeats `prepared.curve`. This changes all seven method files plus `fit_stage.py:428`, `endpoint.py:118` and `experiments/trial_curves/replay.py:73`.
  - Build both grids' arrays in `prepare`, dropping `cache` and `_base_grid`.
  - Remove `bind_geometry_update`, the method forwarder, `trial()` and `ProjectedSpace`. `n_update.py:252` needs its own entry point.
