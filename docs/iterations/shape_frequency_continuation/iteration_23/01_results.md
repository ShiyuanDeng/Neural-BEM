# Iteration 23 — test what the atlas can decide

2026-09-26. **SC-041 COMPLETE.** Owner: Codex; independent reviewer: unassigned.
[Contract](../iteration_22/03_plan.md),
[measurements, theory and reproducible artifacts](../../../../results/validation/shape_continuation/SC-041-atlas-decisions/README.md).

The atlas can now support a narrow, qualified action comparison. It does not
yet justify a general continuation controller. Five matched continuations
from saved star/kite endpoints separate local fitting capacity, finite-step
validity and geometric recovery. All five returned endpoints pass numerical
audits; both kite arms stop before convergence.

## What changes in decision making

1. **Compare complete actions with a common physical metric.** The old video
   score caps QR components separately, which need not represent a feasible
   joint step or its loss decrease. The new opt-in diagnostic solves one
   physical-metric constrained least-squares problem using the derivative of
   the actual projected update. Coordinate changes preserve that problem.
   Historical scores remain intact and are explicitly labelled heuristic.
2. **Use capacity to nominate a band, then test a finite update.** Star's
   M=19 forecast is negligible; M=22/25 forecast about 95%/99% reduction.
   Finite probes agree closely. Continuation reaches RMS 0.142/0.110/0.0476
   mm at M=19/22/25, supporting release on this endpoint. M=25 still leaves
   blunt tips (7.00 mm minimum radius against truth 5.11 mm).
3. **Do not identify a physical RMS radius with finite validity.** Kite M=19
   forecasts 90% reduction, yet its full probe increases loss to 16.4 times
   the starting value. M=22 forecasts 99.8%, yet its full probe self-intersects.
   Useful probes require scales 1/8 and 1/2 respectively. The 0.12/k test
   radius is inactive for all five linear minimizers and is not a guarantee.
4. **Separate data progress from geometry quality.** Kite M=22 reaches RMS
   0.0730 mm versus M=19's 0.1023 mm, and wins at a common work ceiling.
   Its minimum radius worsens to 0.0817 mm against truth 2.1379 mm. Its
   accepted gain ratios fall 0.760 → 0.408 → 0.159 before a numerical stop.
   Higher M helps average error but does not repair the sharp feature.

## What is proved, and what remains empirical

For a trial residual r + Jp + e with ||e|| <= epsilon, direct expansion gives

    actual decrease >= predicted decrease - ||r + Jp|| epsilon - epsilon²/2.

This exact conditional inequality shows what an acceptance certificate would
need: a useful bound on the finite remainder. Here the remainder is measured
after evaluating each probe, so the bound is an a-posteriori check. Neither
that check nor grid agreement certifies unseen steps or continuum PDE error.
Likewise, nested linear spaces can improve data fitting without improving
shape error; SC-041 observes that distinction directly on kite.

The corrected diagnostic is therefore an action-screening component. Its
predicted decrease must be paired with actual decrease, geometry admissibility
and numerical qualification. A general strategy additionally needs a
prospective remainder/step mechanism and evidence that its regularity control
protects meaningful geometry across cases and noise levels. No new policy,
prior, frequency schedule or production default is adopted here.

## Validation and scope

All five complete-update derivative qualifications and endpoint audits pass;
61 provenance/consistency checks and 24 targeted tests pass. Total work is
2,634 units (874 screen, 1,190 inverse, 570 audit), including failures.
The kite M=22 numerical stop is retained: its next candidate exceeds the
1e-7 refinement tolerance by 0.44%; its last accepted endpoint qualifies.
M=19 hits its 900-second ceiling. No tolerance relaxation or resolution retry.

A report-only missing-status exception was repaired after numerical completion;
the exact executed source/contract and all numerical records are preserved and
audited in the bundle. These are two development cases on existing observations,
with truth used only after fitting. They establish no noisy-data robustness,
stable recoverability frontier or general controller superiority. The bounded
comparison is closed; the unresolved question is how to control kite's local
geometry while preserving useful, numerically resolved progress.
