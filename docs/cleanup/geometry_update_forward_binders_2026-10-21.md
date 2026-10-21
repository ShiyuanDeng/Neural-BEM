# How `fit_stage()` reaches the geometry update and forward solve

2026-10-21. Source: commit `7fc5ff932` plus uncommitted working-tree changes,
including geometry-update items 1, 4, 5 and 7. Status: open, not implemented.

## Problem: where it is now

`fit_stage()` receives two objects, `update` and `physics`, and recovers the
function to call from each.

- **Geometry update.** `fit_stage.py:69` calls `bind_geometry_update(update)`
  (`geometry_update_methods/__init__.py:5`). It returns `update.geometry_update`,
  or wraps `update.trial` for objects without that method.
  That method is one line (e.g. `spectral.py:247`): it calls the module function
  `geometry_update(normal_update, prepared=..., settings=self)`. The function
  reads back from `settings` the length unit, tolerance, name, counters,
  `_checked` and `measure`.
  `trial()` (`spectral.py:250`) is a second entry to the same function.
  Analytic's module function (`analytic_spectral.py:181`) only calls spectral's.
- **Forward solve.** `fit_stage.py:70` calls `bind_forward_solve(physics)`
  (`forward_solvers/__init__.py:5`). It checks the type of `physics` and returns
  `partial(modal_muller.forward_solve, context=physics)`, the nodal equivalent,
  `physics.evaluate`, or a fallback solver. It is called again when `physics`
  changes (`fit_stage.py:129`, `:221`) and in `objective.py:45`.
- Other binder calls: `endpoint.py:43`, `modal_accuracy.py:230`,
  `experiments/trial_curves/replay.py:38`.

## Why it is dumb

- The method is chosen twice: once by the caller that builds `update` and
  `physics`, again by the binder through method lookup or type checks.
- Round trip: object → one-line method → module function → back into the same
  object through `settings` or `context`.
- Hops that do no work: binder, forwarding method, `trial()`, analytic's
  forwarding function.
- The binders keep old interfaces (`trial()`, `evaluate`) alive for test fakes
  and research objects.

## User's thoughts

- Pass the selected `geometry_update` and `forward_solve` functions into
  `fit_stage()`. Drop both binders.

Checked fact: the functions do not replace `update` and `physics`.
`fit_stage()` also uses `update` for `prepare`, `velocities`, `metric`,
`measure`, `length_unit_m` and `regauge`. It uses `physics` for the `Objective`,
`qualify_candidate`, `qualify_linearization`, `respond_resolution_failure`,
observers and the resolution swap. The functions are passed alongside, and each
caller must pass a function that matches its object.

## Open

Pass the functions (user's proposal), or make them methods on the objects:
`update.geometry_update(...)`, `physics.forward_solve(...)`. Methods need no
extra arguments and cannot mismatch. But analytic must then call spectral's
method, and the forward solvers move into their classes. Claude recommends
passing the functions.
