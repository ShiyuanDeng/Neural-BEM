# Part 5 — prospective artefact-site prediction and a sensitivity-weighted update metric (frozen plan)

2026-09-26. Written and committed before any data, fit or map below exists.

## Motivation and honest prior art

Part 4: spurious features form at the acquisition's most informative
boundary sites (13/13), and those sites are already high-information on the
true boundaries. The closest precedent is **sensitivity (depth) weighting in
geophysical inversion** (Li & Oldenburg, 1996, *Geophysics* 61:394): model
structure concentrates where kernels are largest, and a model norm weighted
by the sensitivity counteracts it. This part tests (1) whether artefact sites
are predictable, truth-free, before they form, and (2) whether that
weighting, transferred to boundary continuation as the LM step metric,
suppresses spurious features without harming true sharp ones. Any positive
result is a transfer-and-validation claim with a prospective predictor, not
a new weighting principle.

## Cases (fixed now)

| Case | Data | Start (suffix entry) | Nodes |
|---|---|---|---|
| kite (development) | noiseless catalog | SC-035 stage-4 endpoint, K=20 (as SC-038) | 768/1536 |
| deep_c clean | SC-044 inputs | SC-044 prefix endpoint | 512/1024 |
| deep_c noise_seed_0 | SC-044 inputs | SC-044 prefix endpoint | 512/1024 |
| asymmetric_lobes clean (no-harm case) | SC-044 inputs | SC-044 prefix endpoint | 512/1024 |
| **hooked_tip clean (new, untouched)** | generated here as SC-044 does (2048 vs 1024 gate ≤ 1e-8) | its own SC-044-style prefix | 512/1024 |

hooked_tip truth: 0.8 × the band-4 curve drawn at index 41 of
`default_rng(47000)` with the fixed recipe in `infometric.py`, centred. One
convex tip of radius ≈1.9 mm and a concave flank (≈23 mm).

## Arms (suffix only; everything else as SC-044 `none`)

Stages release_M11 then release_M19 at K=192, all 19 frequencies, SC-044
weights and tolerances, quota 380 units each, 1,200 s wall per stage.
All arms use Hanke's regularizing damping (ratio 0.7) so only the step metric
differs:

- **A0 mass**: the projected update's physical mass metric.
- **A1 sensitivity**: mass metric weighted along the boundary by
  w(s) = sqrt(F(s)/F̄), clipped to [0.1, 10], where F(s) = Σ_f Σ_pairs
  |(k_i²−k²) u(s) v(s)|² / σ_f² is the Fisher density of a normal displacement
  at s, from the stage-start state's traces (σ_f = 1% convention of part 4).
  Recomputed at each stage start; its 19 field + 19 reciprocal solves are
  recorded as extra cost.
- **A2 curvature**: the curvature-change metric (mass + l⁴∫(δκ)², l = 1/(2.5
  k_max)), the SC-031 definition applied to the projected update.

## Read-outs and pass rules (fixed)

Truth only for scoring. Per final state: RMS, Hausdorff, spurious-curvature
ratio S = max_s |κ(s)| / max(|κ_truth(nearest)|, 1/(50 mm)), and true-tip
error: for each truth convex peak with radius < 5 mm, |r_state,min within
2 mm − r_truth| / r_truth.

- **Prediction (P1)**: for every A0 final state whose sharpest point is
  spurious (truth radius there > 3× state radius), is that point inside the
  top-10% of w(s) at the suffix-entry state? Supported if ≥ 75% of such
  states (chance ≈ 10%); reported with the count (it may be small).
- **Method vs A0 (P2)**: over the 5 cases, A1/A0 geometric-mean Hausdorff
  ratio ≤ 0.85, median S reduced ≥ 2×, RMS geometric-mean ratio ≤ 1.10, and
  no true-tip error worse than A0's by more than 0.25.
- **Method vs curvature (P3)**: A1/A2 geometric-mean Hausdorff ratio ≤ 1.0
  and median true-tip error of A1 ≤ A2's.

Verdict per rule: pass / fail, no partial credit. No weight exponent, clip,
noise level, stage, quota or case is changed after any fit starts. Failures,
stops and timeouts are reported as they occur.
