# Part 6 — do entry-state information maps predict where artefacts form? (frozen plan)

2026-09-26. Written and committed before any data, fit or map for the new
shapes (fresh_a, fresh_b) exists; hooked_tip's prefix exists (part 5) but its
suffix has not been run.

## Regularity under test (found after the fact on two sites, parts 4–5)

At the suffix-entry state (end of the SC-044 prefix, K ≤ 20), the site where
the default pipeline's final state develops its spurious sharpest point lies
in the **bottom 10%** (arclength-weighted) of the pointwise Fisher density
F(s) (part 5's definition). Secondary: bottom 10% of part 4's posterior
ratio ρ(s) (white prior).

## Shapes (unseen)

- hooked_tip: part 5 truth and data; prefix already complete.
- fresh_a, fresh_b: the first valid draw with a concavity and a convex
  minimum radius in [2, 6] mm from `default_rng(47001)` and
  `default_rng(47002)`, using part 5's band-4 recipe scaled by 0.8
  (index 0: 3.36 mm; index 18: 4.32 mm). Data generated as SC-044 does
  (2048 vs 1024 nodes, gate 1e-8). Clean data only.

## Pipeline (unchanged SC-044 `none` path)

SC-044's prefix (stages 1–4) and suffix (M 11/19/31, K = 192, 380 units and
3,600 s per stage), default damping and metric. No setting is changed.

## Order of operations (the prediction precedes the outcome in Git)

For each shape: prefix → entry maps F and ρ → the predicted region (bottom
10% of each, as arclength intervals) is written and **committed** → suffix →
scoring. A prediction file committed after its suffix started is excluded.

## Read-out and verdict (fixed)

A shape counts if the final state's sharpest point is spurious (truth radius
at the nearest truth point > 3× the state's radius there). Its site is the
nearest point on the entry state; report its percentile of F and ρ.

- **Supported** if every counting shape's site is in the bottom 10% of F
  and there are ≥ 2 counting shapes (chance ≤ 1%).
- **Refuted** if at least half of the counting shapes are outside the
  bottom 25% of F.
- Otherwise, or with fewer than 2 counting shapes, **inconclusive**.

The ρ read-out is reported under the same rule but is secondary.
