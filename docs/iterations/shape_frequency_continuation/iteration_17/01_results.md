# Iteration 17 — SC-036: matched paths, coordinate consistency and limits

2026-09-25. Owner: Codex. Independent reviewer: unassigned.
**SC-036 COMPLETE:** screen and eight full inverses. No method promoted.
[Contract](../iteration_16/03_plan.md).

A radial ray path with the identical first-order arclength normal motion
increases useful finite progress at early peanut and kite corners, but fails
at the terminal peanut corner too. At peanut state 3 it permits scale 1/2
versus 1/8, 3.15x the refined objective decrease, and 3.90 versus 5.25 mm RMS.
It also sharpens the corner to 1.90 mm: a local gain is not a recovery claim.
The smooth star is nearly unchanged. The 131-unit screen passed its declared
full-inverse gate; all five states and all refused trials are retained.
A first attempt encountered a reporting TypeError after 7 units; fixed and
retained separately. Five update tests pass.

Coordinate controls show equal seven-dimensional spaces on a circle and
increasingly different spaces off it. M=3 captures only 59.7% of each rigid
translation's normal energy on the five-lobe star. This is coordinate
bandwidth, not added geometric complexity. The C and hook controls reject a
radial chart. Same-motion chain-rule checks through the normal atlas converge
with representation resolution and use the pulled-back physical metric.

[SC-035 review](../iteration_16/02_proposals/04_state_band_qualification.md)
corrects RD-4's radius claim and defines a zero-preserving projection with a
complete-construction derivative for a separate state-restriction pilot.


Full inverses confirm a mixed finite-path effect: normal → ray RMS (mm) is
peanut 2.944 → 1.739, star 0.522 → 0.240, kite 2.983 → 6.165, and C
3.202 → 12.177. All schedules complete; all original-normal accepted curves
and work counts replay bitwise. The ray alternative is not a general repair.
Screen derivatives pass; 30 regression tests pass. An external SIGTERM
interrupted two attempts; those partial artifacts and conservative costs are
retained, and only missing endpoints were rerun without numerical changes.

Required Priority A outcome: a finite path changes usable progress causally,
but that local gain does not guarantee a better full inverse or explain all
normal-method failures. Priority B outcome: coordinate conversions preserve
physical information when resolved and metrically transformed; low-order
spaces are different priors. Retain the qualified atlas and test state
regularization separately. No universal gauge ranking is supported.
