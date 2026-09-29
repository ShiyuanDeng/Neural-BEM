# MA-003 plan: two diagnosed repairs for denser-than-host targets

2026-09-29. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
Authority: the user's 2026-09-29 instruction ("go next steps as you see fit,
you have my approval to stop only until genuine good news or hit every
wall"). Frozen before any MA-003 attempt ran. No production default, branch
or worktree changes; the repairs are opt-in arms of an isolated driver.

## Question

[MA-002](01_results.md) found two mechanisms behind the high-contrast
failures. Do their one-change repairs recover the failures without harming
what already works, and do they transfer to scenes MA-002 never touched?

- **B, exterior band.** Stages 1–4 of the prefix use `M = ⌊3 k_e⌋` at the
  stage's highest frequency, with `K = 2M + 2`. This is exactly the
  contrast-0.5 schedule. It sits inside the observable frontier, which MA-002
  found insensitive to contrast. Every other stage (warm-up, releases, fixed
  M = 25/31/37) is already contrast-independent and unchanged. For contrast
  ≤ 1, B is identical to the frozen policy.
- **L, dense exact-Mie localization.** SC-050's objective (equal-weight
  relative residuals at 0.25/0.375/0.5 GHz) and constraints (radius
  15–75 mm, circle inside [0.2, 0.8]² m, sources/receivers exterior), searched
  on a dense grid: centres every 4 mm over [0.28, 0.72]², radii every 1 mm.
  The data come from exact Mie series, which reproduce SC-050's BIE losses to
  ≤ 4.6e-15. The grid optimum is refined with SC-050's own coordinate search
  (12 rounds, six neighbours, halve on no improvement), on Mie, starting from
  steps (4, 4, 1) mm. The final circle must then pass SC-050's BIE 512/1024
  field gate (≤ 1e-7) at the three frequencies. If it fails, the next-best
  distinct grid minima are tried, up to five. Charged units: the BIE
  qualification solves. Mie time is reported as localization time.
- **LB, both.**

Frozen policy otherwise: SC-050's `localize_low` (0.25 GHz M=1 warm-up,
prefix, releases 11/15/19, one-off cleanup, fixed 25/31/37), cap 13,412
fit+localization units and 1,800 s per attempt, SC-050's recovery definition,
truth loaded only after the final audit.

## Stage 1: development attribution (MA-002 scenes)

B at contrasts 2, 4 and 13.3 (9 attempts); L and LB at 0.5, 2, 4 and 13.3
(12 each). The frozen arm is MA-002, not rerun. A replay check first reruns
MA-002's contrast-4 C with the new driver's `frozen` arm. Its accepted states
must be identical to MA-002's before any other attempt counts.

Predictions, written before running:

- B alone recovers contrast-4 C and contrast-13.3 asymmetric.
- L alone recovers none of the four failures. The star's localization is
  repaired, but its band is still over-released.
- LB recovers contrast-4 C, 13.3 star and 13.3 asymmetric.
- The 13.3 C fails in every arm, because its circle model is inadequate.
- No arm loses a recovery at contrast 0.5 or 2.

**Gate G1 (releases stage 2):** LB recovers at least 2 of the 4 frozen
failures, and all 8 frozen recoveries still recover under LB.

## Stage 2: transfer (untouched scenes)

SC-050's `opposite_c`, `shifted_rotated_c`, `new_thin_c` and
`noisy_asymmetric` (1% noise, seed 50061, SC-050's noise model and residual
limits), at contrasts 4 and 13.3, with the frozen policy and with LB. That
is 16 attempts, one each, with inputs qualified as in MA-002. The transfer
arm is LB, fixed here before any development outcome.

**Gate G2 (the claim):** LB recovers at least 4 of the 8 transfer attempts,
and at least 2 more than the frozen policy. Every recovered endpoint passes
its final audit (part of the recovery definition).

If G1 fails, stage 2 does not run, and the record says which prediction failed.
If G2 fails, the repairs are recorded as development-only.

## Not claimed in advance

A pass supports these two repairs for this acquisition and these
permittivities. It would not show that the manuscript's band rule is wrong
for far-field data, a general high-contrast method, or robustness to unknown
permittivity. The 13.3 C is expected to remain open: circle localization
cannot represent it.
