# Iteration 02 results — one-component topological birth

**Project:** Radial Fourier topology  
**Experiment:** execution of the [iteration-01 plan](../iteration_01/03_plan.md)  
**Run:** [iteration-01-20260908-234231](../../../../results/inverse/radial_fourier/topology_birth/iteration-01-20260908-234231/README.md)  
**Date:** 2026-09-08  
**Outcome:** full pass, G0–G5

Iteration 01 implemented and qualified the requested hybrid path:

\[
\text{fixed-topology radial-Fourier refinement}
\longleftrightarrow
\text{one discrete topological-derivative component birth}.
\]

All topology decisions and optimizer acceptances used only the frozen 0.50-GHz
training data. The 1.50- and 2.50-GHz results below are evaluation-only
holdouts. Observations came from the independent analytic/cylindrical-harmonic
references; candidate fields came from the direct multi-component Kress seam.

## Gate results

| Gate | Outcome | Key measurement |
|---|---:|---|
| G0 direct forward | PASS | Maximum one-/two-circle oracle error `1.32e-13`; maximum linear residual `4.51e-15`; 64→128 change at most `3.51e-14` |
| G1 production TD | PASS | All three probes reproduce the saved oracle values; empty-domain relative error `7.04e-10`; chunk difference `2.84e-14`; source and objective scaling checks exact to recorded precision |
| G2 localization | PASS | One region on both rasters; minimum error `3.33 mm`; centroid errors `3.33/3.69 mm`; centroid shift `0.358 mm` |
| G3 finite birth | PASS | Production centroid `(0.573333, 0.500000) m`; selected `r_eq = 15.622 mm`; objective `0.194789 → 0.101573`; all four declared ladder candidates passed both resolutions |
| G4 core recovery | PASS | Four accepted LM steps; training relative L2 `4.54e-10`; centre/radius errors below `1.8e-11 m`; holdouts `2.92e-9` and `3.58e-9` |
| G5 wrong-A qualification | PASS | Pre-stage stopped at loss-change tolerance; one TD region and accepted birth; four post-birth steps; training relative L2 `1.61e-10`; holdouts below `1.31e-9` |

The accepted objectives are strictly monotone, and the final production versus
refined objective difference is `2.65e-13` relative. The physical 10-mm
component-clearance floor stayed active at both node counts.

## Implemented path

The new opt-in implementation provides:

- immutable, ordered `MultiRadialFourierState` geometry with persistent IDs
  and deterministic flatten/unflatten slices;
- direct one-/multi-component Kress objective evaluation without SDF
  extraction;
- empty- and non-empty-domain topological derivatives with a single combined
  physical/reciprocal RHS solve per frequency and chunked receiver evaluation;
- the frozen inspection raster, four-connected region selection, equivalent
  radius seed and four-entry finite birth ladder;
- a fixed-topology multi-radial central-FD LM optimizer with strict objective
  decrease, backtracking, geometry rejection and exact accepted-state rollback;
- regression tests and a reproducible artifact/video driver.

The implementation remains deliberately limited to one same-material,
disjoint component birth. It does not add deletion, repeated births,
merge/split surgery, holes, touching components or differentiation through a
topology event.

## Visual evidence

- [Core one-circle → two-circle video](../../../../results/inverse/radial_fourier/topology_birth/iteration-01-20260908-234231/t3_one_circle_to_two_circles.mp4)
- [Wrong-A one-circle → two-circle video](../../../../results/inverse/radial_fourier/topology_birth/iteration-01-20260908-234231/t4_wrong_circle_to_two_circles.mp4)
- [TD heatmap](../../../../results/inverse/radial_fourier/topology_birth/iteration-01-20260908-234231/td_heatmap.png)
- [Objective trajectory](../../../../results/inverse/radial_fourier/topology_birth/iteration-01-20260908-234231/objective_trajectory.png)
- [Complete metrics](../../../../results/inverse/radial_fourier/topology_birth/iteration-01-20260908-234231/metrics.json)

## Immediate candidate directions for iteration 02

Because G5 passed, the next cycle can begin from Outcome A in the iteration-01
plan. Candidate work, pending proposal and review, is:

1. repeated births with unknown `M > 2` while preserving component IDs and
   resolution-qualified acceptance;
2. an automatic, measurable stagnation trigger for requesting a TD event;
3. low-band multifrequency accumulation or continuation, with high-frequency
   TD failure retained as an explicit adverse regime;
4. bounded adverse cases (unequal radii, off-axis centres and mild noise)
   before any claim beyond the declared two-circle benchmark.

No iteration-02 algorithm or experiment is authorized by this results record
alone. The next expected action is proposal/review.

## User-directed topology challenges — 2026-09-09

The user subsequently authorized three bounded extensions. Their curated
[result index](../../../../results/inverse/radial_fourier/topology_challenges/README.md)
contains complete metrics and MP4 trajectories.

| Initial state → target | Outcome | Key measurements |
|---|---:|---|
| Large enclosing circle → two circles | PASS | Training `1.93e-7`; holdouts at most `1.19e-6`; symmetric Hausdorff `1.08e-8 m` |
| Far wrong circle → two circles | PASS | Objective-qualified replacement removes the ghost; final field and geometry measurements match the circle split above |
| Middle circle → diagonal ellipse and star | PASS | K5/K5 final state; training `5.68e-3`; unseen 2.5-GHz error `5.25e-2`; symmetric Hausdorff `0.552 mm` |

These cases add an explicit, truth-free `background_td_replacement` proposal:
an empty-background low-frequency TD seeds the first component, a
current-domain TD seeds the second, and the replace-one-by-two transition is
accepted only when it decreases the production and refined objectives. For
the non-circular case, the first detected component is fitted through radial
K1→K2→K5 continuation before the second TD search. Both components are then
refined at 0.5 GHz before activating the declared 0.5/1.5-GHz training band;
2.5 GHz remains a holdout.

The adverse exploratory trajectories remain informative but are not curated
result bundles: an additive birth did not remove a far-away ghost component,
and a TD accumulated over 0.5/1.5 GHz selected a star-edge hotspot. Those
failures motivated the accepted replacement and low-frequency topology
policies. This establishes three additional clean, separated, noiseless
cases. It still does not establish topology recovery with noise, touching or
nested components, holes, arbitrary non-star-shaped objects, or neural-owned
geometry.
