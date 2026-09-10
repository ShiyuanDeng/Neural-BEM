# Cartesian Fourier versus radial Fourier

A like-for-like comparison of the two explicit charts on the same inverse
problem. Recorded 2026-09-10.

- Cartesian: `cartesian-k6-ellipse-to-star-nystrom-kress-20260910/`
- Radial: `../radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/`

## What is held fixed, and what differs

Both runs solve the same problem with the same code below the chart: wrong
ellipse (semi-axes `0.072 / 0.038 m`, rotation `0.4 rad`) to a five-lobed star
(mean radius `0.05 m`, relative amplitude `0.25`), Kress solver, the same
independent Nyström observation oracle, 24 paired angles, training at
`0.5 / 1.5 / 2.5 GHz` with three-stage cumulative continuation, holdout at
`0.25 / 1.0 / 2.0 GHz`, geometry bounds `0.3–0.7` on a `257²` grid with 128
nodes and validation resolution 1024, and the same Levenberg optimizer settings
(`initial_damping 1e-3`, `curvature_penalty_weight 1e-4`, `k**4` prior,
`max_stencil_shrinks 4`, `max_backtracks 6`, Armijo `1e-4`, `2 mm` trust
region). Both take derivatives by central finite differences.

Three differences, all consequences of the chart:

| | Radial | Cartesian |
|---|---|---|
| State | gauge-fixed radial Fourier, `K=5` | Cartesian Fourier in polar angle, `K=6` |
| Search coordinates | 11 | 26 stored, 25 after the phase gauge |
| Neural field | present as a re-distanced representation audit | **absent entirely** |

The band differs because the charts are related by an exact identity:
multiplying radius harmonics through `K` by `(cos t, sin t)` raises the
Cartesian bandwidth to `K + 1`, and for this target that bound is tight.

The initial contour is the same extracted ellipse, but each chart projects it
into its own coordinates once, so the starting curves are not identical: the
radial projection leaves `0.727 mm` RMS / `1.196 mm` maximum, the Cartesian
polar-angle projection `0.514 mm` / `0.853 mm`. Initial maximum boundary error
agrees to the printed precision, `4.181e-02 m`.

## Final state

| Quantity | Cartesian K6 | Radial K5 | Ratio |
|---|---:|---:|---:|
| Maximum boundary error | `2.761e-09 m` | `2.570e-10 m` | 10.7× |
| Train relative L2 | `1.296e-07` | `1.068e-08` | 12.1× |
| Holdout relative L2 | `1.127e-07` | `1.339e-08` | 8.4× |
| Accepted updates | 41 | 44 | 0.93× |
| Forward evaluations | 1879 | 863 | 2.18× |
| Accepted backtracks, whole run | 0 | 0 | — |
| Maximum linear-system residual | `1.289e-14` | `1.226e-14` | — |
| Stop reason | `stable_data_and_geometry` | `representation_limited_stationary` |

Both charts reach the nanometre regime. The Cartesian arm lands about ten times
coarser and needs about 2.2 times the forward solves. The two runs also stop for
different reasons: the radial run is halted by its neural representation audit,
while the Cartesian run, having no representation, stops on genuine
data-and-geometry stationarity two updates into a stage-3 budget of 111.

Accepted updates are counted as the sum over continuation stages — `19 + 20 + 2`
for Cartesian and `19 + 20 + 5` for radial. Each trajectory holds three extra
rows, one iteration-zero baseline per stage.

## Per update the Cartesian chart is ahead; per solve it is behind

This is the substantive result of the comparison, and the two views disagree.

**Matched accepted updates** (comparable only within a stage, since each stage
changes the objective; all rows below are same-stage):

| Accepted update | Cartesian | Radial |
|---|---:|---:|
| 5 | `9.535e-01` | `9.486e-01` |
| 10 | `7.019e-01` | `7.247e-01` |
| 19 (end of stage 1) | **`1.413e-01`** | `3.340e-01` |
| 30 | **`9.559e-02`** | `2.489e-01` |
| 38 | **`9.758e-07`** | `4.159e-03` |

**Matched work**, by cumulative forward evaluations:

| Evaluations | Cartesian | Radial |
|---|---:|---:|
| 300 | `8.140e-01` | `8.438e-01` |
| 600 | `3.088e-01` | **`1.827e-01`** |
| 863 | `7.822e-01` (stage-2 baseline) | **`1.068e-08` (finished)** |
| 1879 | `1.296e-07` (finished) | finished at 863 |

The Cartesian chart converts each accepted update into more progress, which is
what the extra degrees of freedom buy. It pays for them in the finite-difference
Jacobian, at 52 solves per iteration against 22. On this problem the second
effect dominates: radial finishes in less than half the work.

## Parameterization behaviour

| | Cartesian | Radial |
|---|---:|---:|
| Parameter speed ratio, range over run | `1.891 – 3.035` | `1.392 – 2.230` |
| Gauge projection per accepted state, maximum over run | `2.915e-03 m` | none needed |
| Same, final state | `7.232e-09 m` | none needed |
| Arc-length refit | never | never |

The radial chart has no reparameterization freedom — its parameter *is* the
polar angle by construction — so it needs no gauge control and its speed ratio
simply follows the shape. The Cartesian chart has that freedom and does not
survive it unaided: left free, the speed ratio compounded from `1.92` to `226`
within fifteen updates while the boundary error stalled near `34 mm`. Both runs
here stay bounded only because the Cartesian retraction re-expresses each state
in its own polar-angle parameter.

That gauge projection is also the most likely accuracy floor. Its final
truncation, `7.232e-09 m`, sits at the same scale as the residual boundary error
`2.761e-09 m`, which is a plausible account of the factor of ten — but the two
quantities are merely at the same scale, and nothing here isolates the cause.

## Recovered shape

The radial chart represents the target exactly at `K=5` by construction. The
Cartesian chart had to find its representation, and did:

| Mode | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Initial, mm | 707.672 | 73.010 | 0 | 11.579 | 0 | 2.708 | 0 |
| Final, mm | 707.107 | 70.711 | 0 | `1e-06` | 8.8388 | 0 | 8.8388 |

Modes 2, 3 and 5 are driven to zero and the survivors match the closed form
exactly: `0.5·√2` for the centre, `r₀·√2` for mode one, `r₀·ε·√2/2` for modes
four and six. The chart recovered the analytic Cartesian representation of the
star, not merely a fit to the data.

## Reading this comparison

On accuracy the two charts are in the same regime, radial by a factor of ten.
On cost radial wins by a factor of two. Neither margin is the interesting part:
what the comparison isolates is that the Cartesian chart's difficulty is its
gauge, not its bandwidth or its conditioning, and that once the gauge is fixed
the chart converges cleanly, without a single backtrack, to the exact analytic
coefficients.

Limits: one target, one initial shape, one acquisition. Band six is an algebraic
property of this target and does not transfer. The radial arm carried a neural
representation audit and the Cartesian arm carried none, so their stop criteria
are not the same test. Cost was not equalized by design, and the Cartesian
Jacobian is the obvious place to reclaim it — analytic columns through
`linearize_kress_forward` rather than central differences.

Full record: `../../docs/iterations/cartesian_fourier/iteration_02/01_results.md`.
