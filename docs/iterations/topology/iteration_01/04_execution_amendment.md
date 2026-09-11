# TOP-001 qualification amendment — 2026-09-11

The historical radial replay failed the plan's event-identity prerequisite.
The comparison stopped: no perturbation arms were run against that failed
qualification. [Failed replay](../../../../results/validation/topology/TOP-001-20260911-replay-01/historical/radial/A/m0-s0/metrics.json).

The pre-event objective reproduced exactly (`0.24272693110006`), but B0's
candidate construction retained a different set. With the historical cap 12,
the winning B0 circle seed is width 32 mm, angle π/4, zero offset, whereas the
historical bundle selects width 12 mm, zero angle, offset −0.25. Both recover,
but they are different searches. The Cartesian audit replay reproduces its
event and final geometry, including the 175.210848-µm sampled Hausdorff error.

The radial historical bundle records no producing commit. B0 is a later source
snapshot, and the brief's assumption that it reproduces this earlier candidate
list was not justified. The historical source/run identity cannot be repaired
by retuning the current search. Preserve both records.

## Bounded diagnostic and revised comparison reference

Extract the **unmodified commit `345038a`** with `git archive` into
`/tmp/topology-B0-20260911`, and run the original full-profile split driver once
in each chart with cap 48. Artifacts:
`results/validation/topology/TOP-001-20260911-B0-qualification/{radial,cartesian}/split`.
Source hashes, exact commands and runtime are recorded separately in that bundle.
This costs two additional full inversions; all other experiment budgets stay
as written. The two baseline processes may overlap; wall time is not a comparison.

The unmodified B0 radial run selects the same 32-mm/π/4/zero-offset circle seed
as the failed historical replay, and reaches 23.297878-nm sampled Hausdorff.
This isolates historical drift from the new allocation mechanism.

Use these fresh B0 bundles as the comparison references via
`--reference-root`, and repeat the A replay prerequisite before any A/B/C
perturbation comparison. This restarts the qualification stage with a pinned
reference; it does not count a mismatched historical replay as passing. The
comparison has a fresh output directory and the original failed qualification
is retained. Owner: Codex; independent reviewer remains unassigned.
