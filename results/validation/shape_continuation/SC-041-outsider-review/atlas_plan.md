# Atlas analysis — frozen plan (outsider review, part 2)

2026-09-26. Written and committed before any atlas below is computed.
Motivation (from the owner): the strategy runs in this folder were tried
before the atlas itself was analysed. This asks what the atlas heatmap
actually tracks, before any further strategy is proposed.

## Object studied

The historical atlas of `experiments/shape_continuation/atlas_video.py`,
unchanged: per frequency f, the relative Jacobian A_f with respect to unit-RMS
arclength normal ripples of orders 0..30, the relative residual r_f, a QR of
A_f, and per QR column the projection q = Qᵀr and the new-information size
c = |diag R|. Heat cell (f, m) = sqrt of the capped score min(|q|, c·a_f)²
summed over the order's cos/sin columns, a_f = 0.12/k_f. Amber box = the
step's active frequencies × orders 0..M. Joint column = the active
frequencies stacked with equal weights.

Shots are regenerated here with the SC-039 collector
(`trajectory_atlas.compute`) on the step's recorded grid. No solver, atlas or
threshold setting changes.

## States

- Star: all 25 states of `SC040/circle_to_star` (512 nodes), then SC-041
  star M=22/M=25 endpoints, and this review's M=31/M=37 K=64 endpoints.
- Kite (`F_released_m/kite`): stage_4 end, every `release_1`, `dense_2` and
  `remaining_m19` state (768 nodes where recorded), SC-041 kite M=19/M=22
  accepted states, and this review's `refit_K64` and `raise_kite_M28_K64`
  accepted states.

## Controls (a failure invalidates the affected state)

- C1: the regenerated curve's `shot_key` equals the step's recorded key.
- C2: the joint misfit²/2 reproduces the step's saved loss to 1e-8 relative
  (the videos' own check).
- C3: on 3 states per case, the 2×-grid atlas changes no displayed log10
  heat value by more than 1e-2 dex.

## Questions and fixed read-outs

Q1 Draining pattern. Within each stage, per cell of the amber box, the first
accepted step at which heat falls 1 dex below its stage-start value. Report
Spearman ρ of drain step against order m and against frequency; and, per
step, whether heat outside the box (orders M+1..24, active frequencies)
rises while heat inside falls ("spill").

Q2 Does dimming track progress? Over consecutive accepted pairs, the sign of
Δ(inside-box joint heat²) against the signs of Δloss, ΔRMS and ΔHausdorff.
Fixed wording: "tracks" if sign agreement ≥ 80% for that metric,
"does not track" if < 60%, otherwise "weak". Reported separately for star,
kite before the flank feature (min radius ≥ 1 mm) and kite after it.

Q3 Removed or unseen? For every box cell that dims by ≥ 1 dex over a
stage, split Δlog10 heat into the residual part (Δlog10|q|) and the
sensitivity part (Δlog10 c, only when the cap binds). "Removed" if the |q|
part is ≥ 80% of the drop.

Q4 Does the atlas see the kite flank feature? At SC-041 kite M=22 and
`remaining_m19` it4: expand the normal displacement between the state and
its K≤32 low-pass in arclength ripples up to order 192; report the energy
fraction in orders ≤ 24 (displayed), ≤ 30 (computed) and > 30; and
||A δ|| / ||r|| per frequency with the atlas's own A (orders ≤ 30 part).
"Invisible to the atlas" if < 20% of the feature's energy is in orders ≤ 30.

Q5 Is the colour where the error is? Using truth for scoring only: the
arclength-ripple spectrum (orders 0..30) of the normal error (truth minus
state) against the heat profile by order (active frequencies). Report the
cosine similarity of the two order profiles per state, and whether the
peak order agrees within ±2.

No strategy is proposed or run in this part.
