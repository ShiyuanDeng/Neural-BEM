# Geometry-side signal — frozen plan (outsider review, part 3)

2026-09-26. Written and committed before any signal below is computed.
Part 2 found the atlas heat tracks the loss, not the geometry. This asks
which **truth-free** quantity, computable at every accepted state, does track
the geometry error. Analysis only: no fitting, no field solves, no strategy.

## Data

The 79 states of part 2 (`atlas_index.json`, arrays in `atlas_local/`), with
their truth scores (RMS, Hausdorff) used only as the target.

## Candidate signals (truth-free)

With cutoff Kc = max(48, 2M) and δ = normal displacement from the state to its
|n| ≤ Kc low-pass (mm, along the state normal):

- S0 atlas: joint heat² inside the amber box (part 2's quantity; baseline).
- S1 high-band amplitude: RMS of δ.
- S2 high-band peak: max |δ|.
- S3 minimum radius of curvature (inverted, 1/r_min, so larger = worse).
- S4 curvature roughness: RMS over arclength of dκ/ds, in units of 1/mm².
- S5 high-band data signature: max over frequencies of ||A_f a|| / ||r_f||,
  a = δ's ripple coefficients of orders ≤ 30 (part 2's Q4 measure, at every
  state).
- S6 loss (baseline).

## Read-outs (fixed)

Per case (star: 41 states; kite: 38 states):

- Spearman ρ of each signal against Hausdorff and against RMS across states.
- Over consecutive accepted pairs within a stage (part 2's pairs), the sign
  agreement of Δsignal with ΔHausdorff and with ΔRMS.

Verdict per signal: **useful** if ρ ≥ 0.6 against Hausdorff on both cases
and pairwise Hausdorff agreement ≥ 70% on both; **case-specific** if that
holds on one case only; otherwise **not useful**. The same wording is applied
to RMS separately.

## Caveat fixed in advance

Across-state ρ mixes stages: the loss and many signals fall along a whole
trajectory, so a high across-state ρ can reflect "later is better" rather
than a signal that can steer. The pairwise agreement is the steering-relevant
number; it is reported beside ρ, not merged into it.

## Amendment, before any computation (same day)

The strategy campaign (SC-042..SC-046) landed on the branch while this plan
was being written. Its closeout asks for "a prospective, truth-free
intervention trigger", evaluated away from the development cases. So:

- **Screen** (development): the 79 states above, all six signals S0–S6.
  Each signal's verdict there only decides whether it goes forward.
- **Test** (untouched): every accepted state in SC-044 (`runs/*/*/*/accepted.json`,
  two fresh shapes × clean + two noise draws, prefix and three suffix
  treatments; 392 states), scored against `inputs/<case>/truth.json`.
  Only the geometry signals S1–S4 and S6 are evaluated there (no field
  solves); S0 and S5 need atlas arrays and are screen-only.
- A signal passes the test if, on **both** SC-044 shapes pooled over data
  profiles, ρ ≥ 0.6 against Hausdorff and pairwise ΔHausdorff agreement ≥ 70%.
  Results are reported per shape × data profile as well; no threshold or
  cutoff is changed after seeing SC-044.
- SC-044 pairs are consecutive accepted states within one stage of one path.
  The cutoff Kc = max(48, 2M) is unchanged; M is the state's recorded M.
