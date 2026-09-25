# RD-4 — restrict the storage band K by stage?

**Amendment, 2026-09-25 (SC-035 review):** the degree-only radius guarantee below
requires exact constant speed and does not hold for a general truncated
arclength fit. A measured K=8 kite fit violates the stated nominal bound.
[The correction and derivative requirement](04_state_band_qualification.md)
give the speed-dependent bound. The centred-projection test ran under the user's
autonomous instruction as SC-035 ([iteration 18](../../iteration_18/01_results.md))
and SC-037 ([iteration 19](../../iteration_19/01_results.md)). Original
measurements/proposal are preserved below; “not approved” records the earlier
proposal status.

2026-09-24. Author: Claude (Opus 5.5). A review diagnostic for the user's
question: "what if we restrict K anyways? … the true ellipse requires many
modes but that doesnt mean optimisation process should always bookkeep that
much". It uses saved states only, with zero field solves. Script and data:
[`rd4_storage_band_audit/`](rd4_storage_band_audit/audit.py).

## Why K is the right lever

For a curve stored in arclength with Fourier band K, Bernstein's inequality
for trigonometric polynomials (‖T′‖∞ ≤ K‖T‖∞, applied to z′(s)) gives
curvature ≤ 2πK/L. Equivalently, the tightest radius is at least L/(2πK).
Neither the update band M (RD-2) nor SPD's radial band (RD-2 finding 2) gives
such a bound. K has only ever been set for accuracy:

- 96/192 in SC-020 onward, "a representation requirement, not extra shape
  freedom";
- Borges eq. 12 grows K with frequency at about 70 samples per wavelength,
  with regularity handled separately by the eq. 13 curvature filter.

So K has never been tested as a per-stage regularity control.

## Measurements

`K_eff` is the smallest K whose arclength projection stays within 0.05 mm.

| | Stage-1 K_eff along the path | Result |
|---|---|---|
| Hybrid R0, peanut | 3 → 8 → 16 → **48** → 64 … (step 4: radius 4.2 mm) | collapse, 2.94 mm |
| Hybrid R0, C / kite | 3 → 12 → 16 → **32–48** → 64+ | collapse, 3.20 / 2.98 mm |
| Hybrid M = 2 (SC-029), peanut | 3 → 6 → 8 → **12** and stays | 0.129 mm |
| Hybrid R0, circle / star | ≤ 8 throughout | smooth |
| SPD-L, peanut | 3 → 6 → 24 → **48** (3.3 mm overshoot) → 24 = truth | recovers |

What the truths themselves need (maximum error, mm, of the band-K projection):

| K | Peanut | C | Hook | Kite | Star |
|---:|---:|---:|---:|---:|---:|
| 8 | 0.46 | 0.75 | 0.79 | 1.39 | 1.85 |
| 12 | 0.16 | 0.16 | 0.21 | 0.69 | 1.12 |
| 16 | 0.062 | 0.093 | 0.065 | 0.39 | 0.48 |
| 24 | 0.012 | 0.008 | 0.010 | 0.17 | 0.20 |
| K_eff(0.05 mm) | 24 | 24 | 24 | 48 | 48 |

## Reading

- **Early stages do not need to store the truth.** A stage-1 cap of K = 8–12
  still admits shapes within 0.2–1.4 mm of every truth. That is far closer
  than where hybrid R0 ends (≈ 3 mm RMS). The collapse states need K ≥ 48
  within four steps. The one hybrid path that kept K_eff ≤ 12 (M = 2 on peanut)
  is the one that recovered.
- **The final accuracy decides the last K.** Reaching 0.05 mm needs K = 24
  (peanut, C, hook) or 48 (kite, star). The ladder must end there, or a
  final stage must release it.
- **Not proven harmless.** SPD-L's successful peanut path passed through a
  state that needs K = 48. The hybrid's M = 2 run on C passed through K = 64
  and still ended at 0.35 mm. A cap changes the path, and these data cannot
  show where the changed path leads.
- **Implementation constraint.** The refit gate (1e-5 relative, about 0.5 µm)
  would refuse even the smooth star states at K = 8 (0.023 mm projection
  error). Restricting K therefore means *accepting the band-K projection* of
  each trial as the new state, a smoothing retraction, with the gate
  checking numerics only.

## Proposal (supersedes the RD-3 geometry-budget wording; not approved)

**SC-035 — a storage-band ladder in the hybrid.** One change to hybrid R0:
each trial is projected onto a stage storage band K_s, and that projection
becomes the state. Arms, fixed before any run:

- **K_s = 2M + 2** (8/12/16/20), tied to the update band;
- **K_s = ⌈L / (2π · ℓ(k) / 2)⌉**, tied to the detectability scale; about
  7/10/13/16 for L ≈ 300 mm;
- a final release stage at K = 192 with no new data.

Truth-derived numbers (the table above) are not used to choose K_s.

- *Prediction:* no stage-1 corner on peanut or C (Bernstein bound 7–9 mm at
  K = 8–12). Stage-4 RMS below R0's on the four cases where R0 is worst.
- *Controls:* star and kite, whose legitimate detail needs K = 48.
- *Mechanism record:* the RD-2, RD-3 and RD-4 metrics along each path.
