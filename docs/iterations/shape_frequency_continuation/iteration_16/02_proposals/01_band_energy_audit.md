# RD-2 — does the update band limit the boundary's harmonics?

2026-09-24. Author: Claude (Opus 5.5). A review diagnostic that answers the
user's question: "did we verify the assumption that if we limit update band,
we are in fact limiting boundary harmonics? … measure their elastic energy."
It uses saved states only, with zero field solves.
Script and data: [`rd2_band_energy_audit/`](rd2_band_energy_audit/audit.py)
(`audit.txt`, `audit.json`).

## What had been checked before

- **Discussed, with the single-step effect verified.** The Codex review
  ([iteration 08, §5](../../iteration_08/02_proposals/01_codex_outsider_review.md))
  states that an update band is "a local tangent restriction, not a global
  spectral invariant". It derives that one normal move `ε cos mθ` creates a
  doubled harmonic `ε²/(2R) cos 2mθ`. Iteration 09 confirmed that formula to
  0.07%.
- **Near truth, the band did act as a limit.** In SC-020 the error above M = 16
  stayed unchanged through all four stages.
- **Far from truth, content was measured only at the storage ceiling.** SC-023
  Q0 and RD-1 recorded the top of K = 192 storage, the curvature tail above
  96, and the tightest radius. **Out-of-band bending energy relative to the
  current M was never measured along a trajectory.**

## Measurement

`tail(M)` is the fraction of the bending energy ∫κ² ds that lies above
arclength harmonic M (Borges eq. 13, `geometry.curvature_tail`). It is
computed for every accepted state of hybrid R0 (the SC-029 baseline) and of
SPD-L (SC-034 arm L), in the same arclength measure for both.

| Stage 1 (M = 3) | Truth tail(3) | Hybrid R0: max tail, min radius | SPD-L: max → end tail, min radius |
|---|---:|---|---|
| Circle | 0.000 | 0.027, 35.7 mm | 0.007 → 0.000, 37.8 mm |
| Star | 0.943 | 0.014, 37.7 mm | 0.006 → 0.000, 38.5 mm |
| Peanut | 0.267 | **0.595**, 1.94 mm | **0.485 → 0.267**, 3.28 mm |
| Kite | 0.613 | 0.557, 2.18 mm | 0.763 → 0.376, 0.66 mm |
| C | 0.143 | 0.517, 2.14 mm | 0.887, 0.46 mm (stopped) |
| Hook | 0.202 | 0.167, 7.88 mm | 0.870, 0.34 mm (stopped) |

Peanut, state by state (tail, radius in mm):

- hybrid: 0 (65) → 0.03 (34) → 0.24 (10.8) → 0.42 (4.3) → … → 0.595 (1.94),
  climbing every step;
- SPD-L: 0 (65) → 0.00 (38) → 0.14 (15.3) → **0.485 (3.3)** → 0.34 (6.8) →
  0.27 (13.2) → 0.267 (13.5 = truth).

> **Superseded in part by [RD-3](02_step_span_audit.md):** finding 3's "state outside the step span"
> reading is withdrawn. At the collapsed peanut state, 83% of the correction is still in the M = 3 span.
> What blocks the hybrid is finite-step validity: normal moves near a sharp feature self-intersect.

## Findings

1. **No: the update band does not limit the boundary's harmonics.** At
   M = 3, the hybrid's stage-1 states carry 52–60% of their bending energy
   above harmonic 3 on C, kite and peanut. Their bending energy is 4–6.5×
   that of a circle, against 2.15× for the peanut truth.
2. **In this measure, a limited state band does not limit bending energy
   either.** SPD-L's state is radial order ≤ 3, yet it reaches 0.34–0.66 mm
   radii and 76–89% out-of-band energy on kite, C and hook. A low-order radial
   shape with large amplitudes can be nearly cusped. The truths also exceed
   the band in arclength: peanut has 27% above M = 3, kite 61%. Capping the
   hybrid's arclength storage at a small multiple of M would therefore
   exclude true shapes.
3. **What differs on peanut is reversibility, not avoidance.** Both methods
   overshoot into a 3–4 mm feature within 3–4 steps. SPD-L's next steps undo
   it and land on the truth. The hybrid keeps sharpening. SPD-L's whole state
   lies inside the space its steps can move (7 directions at K4), so every
   feature it creates can be steered back. The hybrid's state holds content
   outside its M-harmonic step span, and SC-020 showed such content persists
   unchanged. SC-031 showed the hybrid's descent into the corner is well
   modelled (ρ ≈ 1): within the hybrid's reachable set, sharpening really
   does lower the misfit.

## Corrections

- The SC-034 bundle and iteration 16 attribute peanut to "the hybrid limits the
  band of each step, SPD-L limits the band of the state". That wording is
  accurate as a description but was offered as the mechanism, and RD-2
  refines it. The operative difference is a **state that stays inside the
  step span**, so its features remain reversible, not a smaller bending
  energy.
- The SC-035 sketch (a storage band of κ·M) is revised. A small storage band
  would exclude the truths (finding 2). The faithful single change is to make
  the hybrid's step space and state space coincide at each stage. One way is
  to express the stage's state in a fixed global basis of the stage's band and
  update those coefficients directly, as SPD does. This is proposed only.

## Limits

This is one start and six development cases, with truth used only for the
reference rows. The reversibility reading rests on one clean case (peanut)
and a consistent contrast. It is a hypothesis for SC-035, not a measured
single-change effect.
