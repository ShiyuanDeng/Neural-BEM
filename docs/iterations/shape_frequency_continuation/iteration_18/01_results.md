# Iteration 18 — SC-035: state regularization helps, late release is not automatic

2026-09-25. Owner: Codex; independent reviewer unassigned.
**SC-035 COMPLETE:** eight paths returned; all four low-K schedules completed,
and three high-K controls stopped on numerical refinement.
[Contract](../iteration_17/03_plan.md),
[evidence](../../../../results/validation/shape_continuation/SC-035-state-band/README.md).

The low-state-band arm reaches 0.1415 mm peanut and 0.4717 mm non-star C,
against 2.9443 and 3.20 mm in the original hybrid. Its matched high-K centred
projection controls stop on numerical refinement in stage two (2.5606 and
8.9509 mm). Those are hard stops, not stationary solutions. The low-K arm
retains the full derivative, same solver, same data and same update-band rule.
A correction based only on finite ray paths improves peanut less and harms
kite; SC-036's complete campaign is still running.

The sharp-detail star control regresses: 0.6067 mm low K against 0.5222 high K.
The final K=192 release/repeat takes no step in either arm. Thus a final release
does not automatically erase earlier coarse-stage bias. This warrants one
small timing-of-release comparison using the SAME centred construction and
saved K=8 stage-one prefixes. No new optimizer or prior is proposed.


Final kite is 0.5743 mm low K versus 3.6164 mm in the stopped high-K control,
and 2.9826 mm in the original hybrid. Low K uses 1,160 units through stage four
versus the original four-case total 1,729. The final release spends another
404 units with negligible shape change (a slight kite regression); final
low-K work is 1,564. Kite uses both final 22-iteration caps. See the bundle's
full table, stage plot, work accounting and endpoint numerical audits.

**Causal assessment:** state restriction is beneficial on three hard cases
in this matched construction, with a real star tradeoff. This is stronger
than saved-state smoothing or fewer geometry refusals, and does not validate
RD-4's withdrawn degree-only radius guarantee. A final release alone does
not erase bias. No atlas policy, new representation, or production default
is promoted. SC-037 tests only whether loosening the later restriction gives
a better development compromise.
