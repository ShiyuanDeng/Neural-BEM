# Overnight briefing — 25 September 2026

**Complete:** three bounded studies (SC-036, SC-035, SC-037) followed the new
atlas/geometry brief, without approval pauses or new branches or worktrees.
Work remains on the existing `feature/shape-frequency-continuation` branch.
All dispatched work finished and nothing is running. The Codex session was
interrupted at 02:22 BST, before it finalized this briefing and committed.
Claude committed its files unchanged (`33d9866`), then corrected the stale
in-progress wording in the handoff and indexes. No result was changed.

The substantive finding is that controlling the intermediate boundary can
help much more than changing the finite path alone. A centred state-band
restriction with the derivative of the complete trial construction reduces
peanut RMS error from **2.944 to 0.1415 mm**, non-star C from **3.20 to
0.4717 mm**, and kite from **2.983 to 0.574 mm** (iteration-limited). It uses
the same solver and observations. It also exposes a real tradeoff: star error
increases from 0.522 to 0.607 mm. A wider later state ladder restores star to
0.530 mm but increases C to 0.602 mm, missing its predeclared 25% protection
limit (27.6% increase). No threshold was retuned.

What changed:

- **SC-036:** implemented and tested ray and normal paths with identical
  initial normal velocities. Early peanut steps obtain 3.15x more actual
  decrease through the ray path, but both paths fail at the final collapsed
  peanut state. Complete outcomes are case-dependent (normal → ray: peanut
  2.944 → 1.739, star 0.522 → 0.240, kite 2.983 → 6.165, C 3.202 → 12.177 mm).
  Local feasibility does not establish recovery; the ray path is not adopted.
- **SC-035:** implemented a zero-preserving, deliberately projected state
  update and differentiated the entire construction. The low K ladder is
  8/12/16/20, followed by a same-data release to 192. Its matched high-K
  controls use the same construction. They differ from the old hybrid, and
  their numerical stops (peanut, C, kite) are retained. The final release
  adds almost no reconstruction value.
- **SC-037:** tested one wider later ladder, 8/16/32/64/192, from identical
  saved stage-one prefixes. This is a fixed comparison, not a parameter sweep.
  Its adoption gate fails on C alone.
- Corrected RD-4's degree-only curvature-radius guarantee. Truncated arclength
  fits need a speed-dependent bound; the K=8 kite is a concrete counterexample
  to the old claim. Coordinate controls distinguish changes of basis from
  different physical subspaces, including rigid translations and non-star C.

What did not change: the Müller/Kress forward solver, physical observations,
materials, topology, production defaults, and SPD-L comparison reference.
There is no demonstrated superior atlas-driven controller, no conformal
inverse, and no new-shape/noise generalization claim. SPD-L remains much more
accurate on the star-shaped peanut; its chart cannot represent the C.

Checks: 30 regression tests pass during the run, and the full 152-test
shape-continuation suite passes afterwards. All ten matched-path derivatives
pass. All four projected-update qualification cells, all eight actual pilot
endpoint derivative audits and all four final low-K endpoint audits pass.
Original-normal replays are bitwise identical. Source/input hashes agree. One
reporting TypeError and a SIGTERM interruption are preserved; completed
results were kept and only unfinished comparisons restarted. Runtime
observations overlap in execution, so no isolated wall-clock speedup is
claimed. SC-035–037 have no independent review yet.

At the overnight closeout, nothing further was dispatched. Iteration 19
recommended freezing one explicit state-family policy for new-shape/start/noise
tests. Standing autonomous authorization remained valid.

**Later user-requested follow-up — SC-038:** the old final K release kept M=9
and only four frequencies. Releasing M=11/15/19 on all 19 frequencies now
reaches C **0.0241 mm** and kite **0.1096 mm**, versus matched M=9 controls
**0.4895 / 0.5518 mm**. Kite required a denser-grid replay, remains time-limited,
and has a sharp feature (sampled radius 0.091 mm versus truth 2.138 mm). All
numerical audits pass. This qualifies the original release interpretation;
it does not make kite a complete regularity success.
[Full result and figures](../../results/validation/shape_continuation/SC-038-update-band-release/README.md).

Evidence: [SC-036](../../results/validation/shape_continuation/SC-036-matched-finite-paths/README.md),
[SC-035](../../results/validation/shape_continuation/SC-035-state-band/README.md),
[SC-037](../../results/validation/shape_continuation/SC-037-later-state-release/README.md),
[coordinate review](../../results/validation/shape_continuation/SC-036-coordinate-review/README.md),
iterations [17](../iterations/shape_frequency_continuation/iteration_17/01_results.md),
[18](../iterations/shape_frequency_continuation/iteration_18/01_results.md) and
[19](../iterations/shape_frequency_continuation/iteration_19/01_results.md),
[current research handoff](../iterations/shape_frequency_continuation/README.md).
