# RD-3 — expressibility against finite-step validity; what this means for the atlas

2026-09-24. Author: Claude (Opus 5.5). A review diagnostic following the user's
concern that RD-2 "challenges the foundation of our atlas idea". It uses saved
states only, with zero field solves. Script and data:
[`rd3_step_span_audit/`](rd3_step_span_audit/audit.py). Truth enters only as
the diagnostic target.

## Measurements

1. **The way back is expressible.** At each accepted stage-1 state, h is the
   move along the current normals that reaches the truth. The table gives the
   fraction of h (arclength L²) that a 7-direction step space captures.

   | Stage-1 path | Hybrid M = 3 space | SPD-L K4 space |
   |---|---|---|
   | Peanut | 0.99 → **0.83** at the 1.94 mm corner | 0.94 → **0.97** at its 3.3 mm overshoot → 1.00 |
   | Kite | 0.98 → 0.65 | 0.98 → 0.18 |
   | C | 0.89 → 0.24 | 0.89 → 0.25 |
   | Star | 0.92 → 0.00, smooth at 38 mm | 0.92 → 0.00, smooth |

   At its collapsed peanut state the hybrid can still express 83% of the
   correction. **RD-2's "state outside the step span" reading is therefore not
   supported**; it is withdrawn.
2. **What stops the hybrid is finite-step validity.** From the 4.25 mm state
   onward, every full LM proposal and its first halving are refused for
   `self_intersection`, and the next halvings for `unresolved_projection`.
   Only steps halved 3 to 7 times are accepted, and their size tracks the
   feature radius:

   | Radius (mm) | Largest accepted normal move (mm) |
   |---:|---:|
   | 4.25 | 1.33 |
   | 3.0 | 0.61 |
   | 2.45 | 0.29 |
   | 2.21 | 0.14 |
   | 2.1 | 0.07 |

   These small steps keep descending into the corner; iteration 11 refuses all
   40 trials. The geometric cause is classical: a parallel (offset) curve
   develops cusps where the offset reaches the local radius of curvature
   (Farouki & Neff, *CAGD* 7, 1990). RD-1's cusp index `max(−κh)` measures
   this. SPD's radial moves carry no such limit at a sharp feature while
   r(θ) > 0, and SPD-L left its 3.3 mm overshoot in one step (3.3 → 6.8 →
   13.2 mm).
3. **The corner is far below the resolvable scale.** SC-031's physical length
   ℓ = 1/(2.5 k_e) from the detectability frontier is 15.6 mm at 0.5 GHz. The
   hybrid's stage-1 corners are 1.9–2.2 mm. The peanut truth's tightest
   radius is 13.5 mm.
4. **The SC-029 first-band strategy acted on complexity only indirectly.**
   M = 2 lowered stage-1 bending energy in all four hard cases: C 6.5 → 3.9,
   peanut 4.0 → 1.8, hook 6.7 → 2.0 and kite 5.1 → 4.2 times a circle's. Yet the
   outcomes split: C 3.20 → 0.35 and peanut 2.94 → 0.13 mm, but hook 0.53 → 4.99
   and kite 2.98 → 5.54 mm.

## Reading for the atlas idea

- **What the atlas measures is sound.** By the Hadamard–Zolésio structure
  theorem, a shape derivative depends only on the normal velocity on the
  boundary (Delfour & Zolésio, *Shapes and Geometries*). Normal harmonics are
  therefore the chart-free first-order coordinates for data sensitivity.
- **What strategies assumed is not.** Choosing the update band M does not set
  the shape's complexity (RD-2), and the failure does not live in the band's
  expressibility (finding 1). It lives in the **finite-step validity** of the
  normal move near features that are sharper than the data can resolve
  (findings 2 and 3). A linear atlas cannot see that by construction; this is
  the brief's "a mode changes data ≠ a useful finite step exists".
- **Three different sizes of a shape have been conflated:**
  1. information: what the data at f can resolve (the atlas, and ℓ(k));
  2. representation: coefficients in a basis (SPD's K, the hybrid's storage);
  3. geometric regularity: curvature radius and bending spectrum, which set
     the normal-move horizon.

  Band strategies act on none of these directly for the state.
- **Proposed re-scoping (not approved):**
  - Keep the atlas as the information map, for frequency and direction choice
    and for "is the remaining error out-of-band?". Star at the end of stage 1
    is exactly that: 0% in-span, smooth. Peanut is 83% in-span but
    step-blocked.
  - Pair it with an explicit **geometry budget** tied to the information map:
    no feature sharper than a declared multiple of ℓ(k), or equivalently no
    bending energy above the detectability harmonic of the current frequency.
    This is the admissibility constraint Borges pairs with band-limited
    updates (eq. 13). It is coupled here to detectability rather than to M,
    because RD-2 shows the truths exceed M.
  - The smallest test is a hybrid arm with that budget, plus the three
    diagnostics above as its mechanism record. This supersedes both SC-033 as
    written and the SC-035 sketch.

## Limits

These are single stage-1 paths from one start. Refused trials do not record
their move field, so whether the refused full steps pointed toward the truth
is not measured. The Hadamard statement concerns first-order sensitivity
only.
