# Does posterior uncertainty localize spurious features? — frozen plan (part 4)

2026-09-26. Written and committed before any quantity below is computed.

## Why this direction

Part 3 found no truth-free *shape* signal; detail grows with progress, true
and spurious alike. Part 2 found kite's flank feature is data-supported yet
93% above the atlas's orders. The claims review lists as open
"acquisition-specific, noise-scaled sensitivity; separate uncomputed modes
from measured null directions". Regularity priors (filtering, curvature
spectrum, curvature penalties) have close prior art; this direction does not
propose a new prior. It asks whether the **data's own information**, scaled
by the declared noise, says where the boundary is undetermined, and whether
spurious features form there.

## Quantity (truth-free)

At a state: arclength normal ripples φ_m, orders 0..128 (257 columns, mm of
unit-RMS ripple). Per frequency f, the SC-039 Hadamard Jacobian J_f (unchanged
`trajectory_atlas.jacobian`) with the acquisition used by the run, divided by
the per-entry noise σ_f = 0.01·||d_f|| / sqrt(2 n_f) (SC-044's declared 1%
complex-RMS convention; applied to clean data as a nominal level). Gaussian
prior a ~ N(0, P). Posterior C = (Σ_f J_fᵀJ_f/σ_f² + P⁻¹)⁻¹.

Local information ratio along the boundary:
ρ(s) = sqrt(φ(s)ᵀ C φ(s) / φ(s)ᵀ P φ(s)) ∈ (0, 1]; 1 = data say nothing there.

Two declared priors, fixed now, results required under both:
- P1: independent, std 1 mm for every coefficient.
- P2: std_m = 1 mm · (1 + m/8)^(-1.5).

## States

- Screen (development, no decision power): SC-035 kite stage-4 end, SC-038
  kite `remaining_m19` it4, SC-041 kite M22 endpoint, this review's kite
  refit_K64 endpoint; SC-041 star M25 endpoint (768 nodes kite, 512 star).
- Test (untouched): the last accepted state of each SC-044 suffix path:
  2 shapes × 3 data profiles × 3 treatments = 18 states (512 nodes).
  Acquisition `catalog_only('kite')`; data norms from `inputs/<case>/clean.json`.

## Read-outs and pass rule (fixed)

Truth used only here, via the normal error e(s) from state to truth.

- R1 localization: Spearman correlation along the boundary (4096 uniform
  arclength samples) between ρ(s) and |e(s)|.
- R2 feature check: percentile of ρ at the state's sharpest point, for
  states whose sharpest point is spurious (truth radius at the nearest
  truth point > 3× the state's radius there).

**Pass** (the hypothesis is supported) if on the 18 test states, under both
priors: median R1 ≥ 0.4, R1 > 0 in ≥ 14 of 18, and median R2 ≥ 75th
percentile over the spurious-feature states (reported with their count).
**Fail** if median R1 < 0.2 under either prior. Otherwise **inconclusive**.

Controls: the regenerated shot key equals the recorded key where one
exists; on 2 test states the 2×-grid ρ(s) changes by < 0.02 in max abs.
No prior, noise level, order limit or threshold is changed after results.
