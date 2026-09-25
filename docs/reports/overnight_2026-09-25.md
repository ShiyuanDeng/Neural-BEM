# Overnight briefing — 25 September 2026

**In progress:** three bounded studies following the new atlas/geometry brief,
with no approval pauses or branch/worktree creation. Work remains on the
existing `feature/shape-frequency-continuation` branch. The final kite and
non-star C comparisons are still running; this briefing will be finalized
when all dispatched work is accounted for.

The substantive finding so far is that controlling the intermediate boundary
can help much more than changing the finite path alone. A centred state-band
restriction with the derivative of the complete trial construction reduces
peanut RMS error from **2.944 to 0.1415 mm**, and non-star C error from
**3.20 to 0.4717 mm**, using the same solver and observations. It also exposes
a real tradeoff: star error increases from 0.522 to 0.607 mm. A wider later
state ladder restores star to 0.530 mm but increases C to 0.602 mm, missing its
predeclared 25% protection limit (27.6% increase). No threshold was retuned.

What changed:

- **SC-036:** implemented and tested ray and normal paths with identical
  initial normal velocities. Early peanut steps obtain 3.15x more actual
  decrease through the ray path, but both paths fail at the final collapsed
  peanut state. Complete outcomes are case-dependent; local feasibility does
  not establish recovery.
- **SC-035:** implemented a zero-preserving, deliberately projected state
  update and differentiated the entire construction. The low K ladder is
  8/12/16/20, followed by a same-data release to 192. Its matched high-K
  controls use the same construction. They differ from the old hybrid and
  their numerical stops are retained.
- **SC-037:** tested one wider later ladder, 8/16/32/64/192, from identical
  saved stage-one prefixes. This is a fixed comparison, not a parameter sweep.
- Corrected RD-4's degree-only curvature-radius guarantee. Truncated arclength
  fits need a speed-dependent bound; the K=8 kite is a concrete counterexample
  to the old claim. Coordinate controls distinguish changes of basis from
  different physical subspaces, including rigid translations and non-star C.

What did not change: the Müller/Kress forward solver, physical observations,
materials, topology, production defaults, and SPD-L comparison reference.
There is no demonstrated superior atlas-driven controller, no conformal
inverse, and no new-shape/noise generalization claim. SPD-L remains much more
accurate on the star-shaped peanut; its chart cannot represent the C.

Checks so far: 30 regression tests pass; all ten matched-path derivatives
pass; all four projected-update qualification cells and all eight actual
pilot endpoint derivative audits pass. Completed original-normal replays are
bitwise identical. Source/input hashes agree. One reporting TypeError and a
SIGTERM interruption are preserved; completed results were kept and only
unfinished comparisons restarted. Runtime observations overlap in execution,
so no isolated wall-clock speedup is claimed.

Evidence: [SC-036](../../results/validation/shape_continuation/SC-036-matched-finite-paths/README.md),
[SC-035](../../results/validation/shape_continuation/SC-035-state-band/README.md),
[coordinate review](../../results/validation/shape_continuation/SC-036-coordinate-review/README.md),
[current research handoff](../iterations/shape_frequency_continuation/README.md).
