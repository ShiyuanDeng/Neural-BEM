# Iteration 16 — SC-034: the SPD baseline recovers the star-shaped cases once its state starts band-limited

2026-09-24. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
**SC-034 execution: COMPLETE.** Evidence:
[SC-034 bundle](../../../../results/validation/shape_continuation/SC-034-spd-legacy-controls/README.md).
Contract: [iteration-15 plan](../iteration_15/03_plan.md). Assessment:
[legacy controls](../iteration_15/02_proposals/01_spd_legacy_controls.md).
This was the user's direction: the SPD baseline could not recover single
star-shaped objects that the legacy inverse recovers.

**Amendment, 2026-09-24 (RD-2):** a saved-state audit of out-of-band bending energy
([RD-2](02_proposals/01_band_energy_audit.md)) refines the peanut mechanism and the SC-035 sketch below.
SPD-L's band-limited state does not keep bending energy low (0.3–0.7 mm radii on kite/C/hook). On peanut,
both methods overshoot into a 3–4 mm feature; SPD-L reverses it, the hybrid does not. The operative
difference is a state that stays inside the step span (reversible features). A small storage band would
exclude the truths, so SC-035 is re-scoped to make the step and state spaces coincide.

## What changed

- `StepSafeguards` (opt-in; default `None` replays SC-030 bitwise): m⁴ step
  ridge, damping floor, 2 mm normal trust region enforced through the
  damping, and Armijo. It lives in the SPD LM (`radial_topology.py`) and is
  passed through `run_top017.fit_stage`.
- A new driver runs the SPD fitter with a Cartesian K ladder of 4/6/8/10
  (radial orders 3/5/7/9, the hybrid's M).
- No production default changed. Topology, TOP-025 and SPD-008 behaviour is
  untouched.

## What the measurement established

| Symmetric RMS, mm (* hard stop) | Circle | Star | Peanut | Kite | C† | Hook† |
|---|---:|---:|---:|---:|---:|---:|
| SPD-008 (SC-030) | 7.49* | 7.34* | 13.8* | 21.3 | 19.0 | 12.6 |
| **L — ladder only** | **7.6e-6** | **3.3e-5** | **1.2e-5** | **1.25*** | 10.1* | 9.36* |
| S — step controls at K17 | 18.5* | 1.67 | 27.3* | 29.2* | 25.3 | 18.8* |
| LS — both | 1.6e-5 | 4.7e-5 | 0.137 | 8.63* | 11.2* | 9.58* |
| Hybrid R0 / R2 | 0.0026 / 0.0018 | 0.52 / 0.52 | 2.94 / 2.39 | 2.98 / 1.55 | 3.20 / 2.75 | 0.53 / 0.49 |

† Truth not star-shaped. The SPD polar chart cannot represent it.

1. **The baseline failure is fixed, and the ladder is what fixes it.** H1
   passes: LS recovers circle and star. L alone recovers circle, star and
   **peanut** to ≤ 3.3e-5 mm, at 51–111 units. That is the legacy level
   (SC-018: 0.031 mm bound).
2. **Peanut, a stage-1-collapse case for the hybrid, is solved by the band-limited
   SPD.** Its truth is exactly radial mode 2. From the same 0.5 GHz data, L
   reaches it in 7 stage-1 steps. The hybrid, with the same first band, falls
   into a 1.9 mm corner (SC-031). The hybrid limits the band of each step; SPD-L
   limits the band of the state.
3. **The four legacy step controls did not help this fitter.** At K17 they
   leave 9.1–12.6 mm of radial content above mode 5 at the end of stage 1,
   against 6.5–9.9 mm without them. Each accepted move stays within 2 mm, but
   the ripple accumulates, and GM(S/SPD-008) is 1.20. Combined with the ladder,
   the 2 mm trust region uses all 22 iterations in stage 1 on every case and
   in all four stages on peanut. LS peanut (0.137 mm) is therefore
   iteration-limited, which counts as inconclusive under the plan. The
   legacy inverse had 150 iterations; this schedule allows 22 per stage.
4. **The remaining SPD stops are all its conservative 8 mm radius
   certificate.** It blocks both sides of FD-compatible stencils
   (`UNRESOLVED_DERIVATIVE`). On L kite the certificate reads 8.02 mm while
   the actual minimum centre distance is 18 mm; on every S path it is 30–36 mm.
5. **On the non-star-shaped truths, the hybrid is the only method that
   works.** On C and hook it reaches 0.49–3.2 mm against SPD's 9–25 mm.

## What remains uncertain

- Whether the state band alone explains the peanut contrast. L and the hybrid
  also differ in chart (polar radial against arclength normal moves), LM
  details and guards. The attribution is a mechanism hypothesis with one
  clean supporting case. It is consistent with SC-029: a smaller hybrid first
  band (M = 2) took peanut from 2.94 to 0.129 mm.
- Whether L's kite would go further without the certificate stop. Kite's truth
  lies 8.75 mm from its Cartesian centre, and the polar gauge does not converge
  on its band-8 truth.
- Whether LS would match L with a legacy-sized iteration budget. That would
  be a new contract.
- These are single runs on six noiseless development cases with one start.

## Claims

- **Established (development evidence):** the SPD comparison fitter recovers
  the star-shaped single objects once it starts in a low-order state and
  widens the band by stage. **The SC-030 SPD failures were a baseline
  configuration problem**, not a limitation of that fitter.
- **Revised:** the SC track's "hard cases" are not all hard. Peanut, and to a
  lesser degree kite (L 1.25 mm, better than R2's 1.55 mm), are handled better
  by the band-limited SPD than by any hybrid variant tested in SC-029 to
  SC-032. **The SC work has partly been fixing a problem the baseline already
  solves.** SC-031/032's finding still holds for the hybrid's own update space:
  no step rule removes the collapse. SC-034 adds that the collapse is **not** a
  property of the 0.5 GHz data. With a band-limited state, the same data
  recover peanut exactly.
- **Rejected for this fitter:** the four legacy step controls as a baseline
  repair. They stay available as opt-in only.
- **Unchanged:** C and hook are the hybrid's own ground. SPD cannot represent
  them.

## Decisions

- **Rule outcome:** H1 passes, so LS qualifies as the SC SPD comparison
  reference.
- **Adopted by the user (2026-09-24, verbatim: "ladder as baseline yes"):** **SPD-L** is the SC
  SPD comparison reference. The recommendation it answers follows.
- **Recommended amendment.** Adopt **L**
  ("SPD-L": the SPD fitter with the K 4/6/8/10 ladder, no step controls) as
  the reference instead. Its RMS is lower than LS's on every case, and it costs
  fewer units on circle, star and peanut (kite: 869 against 372, both stopped). From now on, SC recovery claims on circle, star, peanut
  and kite are measured against the better of SPD-L and hybrid R0.
- SC-033 (Borges eq. 13 curvature-tail filter) stays proposed and unapproved.
  Its intent, keeping the state's curvature within the band, is exactly what
  SC-034 points to, so it should be re-scoped against the successor below
  rather than run as written.

## Smallest next decisions (proposed, not approved)

1. **SC-035 — a band-limited hybrid state.** One change to the hybrid: after
   each accepted step, hold the curve in a state band tied to the ladder
   (storage band κ·M with κ declared up front, instead of the fixed K = 192),
   so the state, not only the step, is band-limited.
   - *Prediction:* peanut avoids the stage-1 corner and C still improves over
     R0.
   - *Risk:* kite's legitimate tip needs a high band; kite and star are the
     controls.
   - *Why:* it tests the one mechanism SC-034 exposes, in the hybrid, which is
     the only method that also handles the non-star-shaped C and hook.
2. **SPD-L certificate stops.** For fixed-topology fits, replace the
   coefficient-sum radius certificate with a sampled bound, or shrink the
   stencil as the legacy inverse did. Then check whether L's kite continues
   beyond 1.25 mm. This is a small SPD-side follow-up; it does not bear on
   the hybrid's question.
3. **Rescope the SC comparison set.** The hybrid-versus-baseline question is
   most informative on C, hook and kite, and on new non-star-shaped shapes.
   Circle, star and peanut become regression checks.
