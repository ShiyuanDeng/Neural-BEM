# Proposal — a regularity-controlled step metric (SC-026, not approved)

2026-09-24. Owner: Claude. Status: **proposed; needs the user's go-ahead**,
because it opens a successor experiment.

## Why

- **Roughening goes with failure** (SC-025). The tightest curvature radius
  reached rank-correlates with the final error at −0.88 over 18 runs.
- **Frozen runs were rough.** Every frozen run had sharpened to radii of
  1–4 mm, far below its truth's, before the refit gate froze it. Examples:
  the ladder on the kite, peanut and C; SC-022's C.
- **Runs that stayed smooth succeeded, whatever the band rule.** The atlas
  rule on the peanut stayed at 19 mm; the ladder on the hook at 8 mm.
- **Bounding displacement does not stop sharpening** (SC-024 V1). The C still
  reached 3.4 mm. A bound in displacement does not bound curvature: a
  normal move of amplitude a at harmonic p changes curvature by about
  a(p²−1)/R².
- **The damping is scale-invariant.** The backend uses Marquardt scaling,
  D = diag(JᵀJ), so a weakly determined high harmonic is damped relative to
  its own tiny sensitivity. Nothing penalizes roughness per unit of data
  explained.

## Theory

Choosing a Sobolev inner product for the shape velocity is the standard way
to make shape flows regular. It favours coherent motion over high-frequency
motion, and it reduces sensitivity to some local minima:
- [Sundaramoorthi, Yezzi & Mennucci, *Sobolev Active Contours*, IJCV 73 (2007)](https://link.springer.com/article/10.1007/s11263-006-0635-2);
- [Burger, *A framework for the construction of level set methods for shape optimization and reconstruction*, Interfaces Free Bound. 5 (2003)](https://ems.press/journals/ifb/articles/13).
  This paper constructs velocities from a scale of norms.

Borges' own admissibility check (eq. 13 in
[the manuscript](https://arxiv.org/html/2210.11607v1)) is a constraint on the
curvature spectrum. It serves the same purpose, but as a filter, not as a
metric.

## One change, shared by every arm

Replace the LM scaling D = max(diag G, 1) with an arclength Sobolev metric:
D_p = w_p (1 + (p/p₀)²)^s, in physical coordinates, where w is the Fourier
mass. The candidates are s = 2 (an H² metric, which penalizes curvature)
with p₀ fixed per stage, for example the ladder's M. Everything else stays
as V2.

The alternative is a curvature trust region: scale each step so that the
linearized max |Δκ| stays under a bound. It is simpler, but it has one more
free constant.

## Test design, to be frozen before any run

- **Arms:** ladder and A2, each with Marquardt scaling (the SC-025 control)
  and with the Sobolev metric.
- **Development cases:** the six SC-022/SC-025 cases. The kite, peanut and
  hook are now development data.
- **New held-out cases:** three truths, declared in the frozen plan before
  any run. Examples are a bean, a rounded triangle and a second non-star arc
  at a new orientation, each with a second start circle.
- **Primary measure:** final symmetric RMS and Hausdorff distance, with work
  units.
- **Mechanism measures:** the tightest radius along the trajectory, and
  refit refusals.
- **Decision:**
  - the metric is kept if it improves the ladder's geometric-mean error on
    the new held-out cases without losing any case by more than 1.5×;
  - A2 is reconsidered only if the metric removes its held-out losses.

**Budget:** about 2 h of compute on 12–24 cores. The held-out observations
need about 30 min.

## What it would not settle

- Frequency selection: the schedule stays SPD's.
- Noise.
- Multi-object scenes.
