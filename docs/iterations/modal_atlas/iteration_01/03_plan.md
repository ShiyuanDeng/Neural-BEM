# MA-001 plan: test the wavefield-pair bridge before building an atlas on it

2026-09-28. Owner: Claude (Opus 5.5). Approved by the user in the same message
that supplied the [vision](02_proposals/01_research_vision.md) ("go ahead for
next steps as you see fit. you have my approval"). Rationale:
[independent review](02_proposals/02_independent_review.md).

**Honest ordering note.** Part A (circle) was explored before this plan was
written, and its questions were sharpened by what it showed. Part B's
questions and thresholds were fixed before its analysis ran. No threshold was
changed afterwards.

## Questions

- **A1 (identity).** Does `J_p = Δ L Σ U_n V_{−p−n}` reproduce an independent
  exact sensitivity? On the circle: an exact Mie dilation difference.
- **A2 (frontier).** Does the highest detectable harmonic track the combined
  trace support `K_U + K_V`? Is `frontier/k` constant, as iteration 04's
  `2.53k` fit assumes, or does it fall toward 2?
- **A3 (resonance).** Near trapped poles (`k_i > k_e`), does the 10%
  linearization radius obey the single-pole law
  `ε ≈ 0.1 · |k − k*| / |k*|`? How does the horizon distribution differ at
  contrasts 0.33, 0.5, 3 and 10?
- **B1 (qualification).** On noncircular BIE states: modal pair sum versus
  nodal quadrature versus production `shape_jacobian`, 512 versus 1024 nodes.
  Also check the projected-truncation bound of the review, item 1.
- **B2 (frontier).** Per frequency: the frontier of `‖J_p‖` (relative to the
  strongest column, `τ = 1e-2, 1e-3, 1e-4`) versus `K_U + K_V`. Where do the
  endpoints' released update bands `M` sit relative to it?
- **B3 (trace band).** The smallest projected `K` giving each column to
  `1e-3` / `1e-6` of the strongest column, versus `p` and versus the
  trace-only band.
- **B4 (cancellation).** Is `κ_p = Σ|pair terms| / |J_p|` large? Does atlas
  brightness `‖J_p‖` vary with `p` mainly because the available product
  magnitude `A_p` varies, or because of cancellation?

## States and settings

- Circle: unit radius, monostatic points at radius 10 (iteration 04's
  receiver radius), contrasts 0.33, 0.5, 3 and 10.
- BIE: the five noncircular truths (star, C, kite, peanut, hook), plus six
  trajectory endpoints: `A_hybrid/kite`, `G_fixed_m9/kite`,
  `F_released_m/kite`, `F_released_m/circle_to_c`, `A_hybrid/circle_to_star`
  and `E_wider_ladder/circle_to_star`. All 19 catalog frequencies
  (0.25–2.5 GHz), contrast 0.5, the 24-position acquisition, and paired data.
  Solver and reciprocal solve are exactly SC-039's.

## Non-goals

No continuation policy, threshold or default changes. No Galerkin-cutoff
(Schur-feedback) study; that is the natural next experiment. No claim that
the frontier or resonance mechanism improves reconstructions. The circle
resonance result is not transferred to the contrast-0.5 benchmark.
