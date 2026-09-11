# Cartesian-Fourier topology challenges

The three user-directed extensions of the topology-birth benchmark, run with
every accepted component held as a polar-angle Cartesian Fourier curve. Same
cases, observations, oracles, schedules, budgets and declared gates as the
[radial bundle](../../radial_fourier/topology_challenges/README.md); only the
chart differs. Truth geometry is used only for qualification and the dashed
video overlays, never for a proposal or an accepted step.

| Case | Outcome | Train rel L2 (radial → Cartesian) | Holdout (radial → Cartesian) | Worst geometry error | Video |
|---|---|---|---|---|---|
| [Far wrong circle → two circles](challenge-suite-20260910/far-circle/README.md) | **full_pass** | `1.928e-07` → `1.931e-07` | `1e-06` → `1e-06` | `10.79 nm` → `10.83 nm` | [MP4](challenge-suite-20260910/far-circle/far-circle.mp4) |
| [Large enclosing circle → two circles](challenge-suite-20260910/large-split/README.md) | **full_pass** | `1.928e-07` → `1.931e-07` | `1e-06` → `1e-06` | `10.79 nm` → `10.83 nm` | [MP4](challenge-suite-20260910/large-split/large-split.mp4) |
| [Middle circle → diagonal ellipse and star](challenge-suite-20260910/ellipse-star/README.md) | **full_pass** | `5.678e-03` → `5.678e-03` | `5.245e-02` → `5.245e-02` | `551.6 um` → `551.6 um` | [MP4](challenge-suite-20260910/ellipse-star/ellipse-star.mp4) |

The ellipse/star case is eight staged optimizations deep and the two charts
agree at every stage — `0.20782`, `0.19355`, `0.18752`, `0.17020`,
`6.154e-03`, `7.326e-07`, `3.359e-10`, `7.108e-05` — with one additional Cartesian update in the pre-topology stage and matching
accepted-update counts in the later recorded stages. That agreement is not a coincidence of the endpoint: the
gauge-fixed Cartesian chart's reachable set *is* the radial chart one band
lower, so once the trust region and the feature-radius certificate are
expressed in matching coordinates the two optimizers trace the same path.

Reproduce with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/topology-matplotlib \
  python run_radial_fourier_topology_challenges.py --chart cartesian --profile full
```

Analysis: `docs/iterations/cartesian_fourier/iteration_03/`.
