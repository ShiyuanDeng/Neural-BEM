# Iteration-2 third-review diagnostics — 2026-09-08

Six read-only probes over the saved September 8 bundles, run to support the
[third review](../../../../../docs/iterations/implicit_mlp/iteration_02/02_proposals/03_claude_review.md).
[probe.py](probe.py) runs all six and writes [probe.json](probe.json). No
inverse was launched, no weights were changed, and no saved artifact was
modified. Probes 4 and 5 solve Kress on curves built from saved node sets and
never touch the neural field.

| Probe | Question | Headline measurement |
|---|---|---|
| 1 | What does one candidate evaluation cost? | Star: geometry build **13.50 s**, Kress solve at both training frequencies **0.195 s**. Circle: **5.42 s** and **0.0157 s**. `polygon_self_intersection_count` is **81.6%** (star) and **88.4%** (circle) of the profiled build |
| 2 | Does the field stay a distance function? | On-contour \|grad f\| spread rises from **1.50** to **10.14** over the star run and **1.02** to **1.87** over the circle run |
| 3 | Where is the fixed Eikonal sample set? | **0 of 512** samples within 1 mm of the star's final contour; nearest is 1.63 mm |
| 4 | Is there a data-misfit barrier to the truth? | Straight contour-space paths to the exact target fall **0.235146 → 0** and **1.451200 → 0**; no barrier |
| 5 | Do single-mode corrections descend? | No single-mode correction above 1 mm RMS lowers the loss; the joint 5% step does |
| 6 | What sets the accepted step length? | Star: a geometry constraint in **47 of 47** accepted iterations. Circle: Armijo in 33 of 60 |

Probe 4 is self-checked: at `alpha = 0` it reproduces the recorded final star
training loss `0.23514630500246692` and relative L2 `0.4824132144160508`. Its
`target_curve_points` endpoint lies within `2.086e-6 m` of the saved exact
boundary. The trigonometric interpolant reproduces its nodes to `1.2e-15 m`.

`probe.json` records full precision values, per-state spectra and gradient
norms, the transect and modal tables, environment and package versions, the
git commit and dirty flag, and SHA-256 hashes of the cited sources and of the
bundle files read.

Run from the repository root, in the thread environment the September 8 suite
recorded:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/implicit_mlp_adjoint/iteration-02-20260908/review-diagnostics/probe.py
```

The script refuses to replace `probe.json`; preserve the saved record under a
different name before repeating it. Compare the recorded source hashes when
reproducing after code changes.

Caveats are recorded in `probe.json` and repeated in the review: timings are
single-machine engineering measurements and the cProfile totals are inflated by
profiling overhead, so only their shares are meaningful; the radial spectra use
a polar decomposition about the polygon centroid rather than the arc-length
modal basis the proposals specify; the transect is one straight path in node
coordinates and ignores MLP reachability, the conversion audit and the motion
cap by construction; and the modal sensitivities are finite 1 mm RMS
differences in Cartesian node-index modes, in which mode 0 is a rigid
translation.
