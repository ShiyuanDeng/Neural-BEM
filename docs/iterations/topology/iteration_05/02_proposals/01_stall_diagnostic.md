# Why the surviving failures fail — a review diagnostic

**Scope and budget:** read-only. It reads saved TOP-007 states and performs
geometry evaluations only — no inversion, no forward solve, no BIE work. This
is a **review diagnostic, not an experiment result**; the script beside it
([`stall_diagnostic.py`](stall_diagnostic.py)) reproduces the Jacobian probe.

## The training residual separates three different failures

| Scene | Refined training error | Worst holdout | Matched error | Failing gates |
|---|---:|---:|---:|---|
| repeated-birth, death, split, mixed, far-two-circles | 1e-7 … 7e-6 | ≤1.1% | ≤0.18 mm | none |
| merge | **7.9e-05** | 9.4% | 0.554 mm | holdout only |
| far-two-stars | **1.4e-02** | 100% | 7.60 mm | boundary, overlap, training, holdout |
| far/empty-ellipse-star | **3.1e-02** | 140% | 18.62 mm | boundary, overlap, training, holdout |

Passing runs fit the training data to 1e-6. The three noncircular failures sit
three to four orders above that, on data they were given and did not use. Only
`merge` fits its training data and still predicts badly.

## 1. merge — information

Training residual 7.9e-05, geometry 0.554 mm, holdout 9.4%. The 0.5-GHz,
24-pair acquisition cannot see the remaining boundary error; the held-out
1.5/2.5-GHz predictions can. This is the one failure where more information is
the answer, and it caps the accuracy of everything else once the others are fixed.

## 2. far-two-stars — shape capacity

Both final components are **mode-1 circles** (feature radius 30.9 and 30.0 mm,
22 mm of headroom over the floor, nothing pinned). The targets are five- and
seven-lobed stars with radii from 23.4 to 38.4 mm. A circle cannot represent
them, the optimizer fits as well as a circle can, and stops on
`loss_change_tolerance` with 1.4% of the training data unexplained. Births seed
circles and no mechanism promotes a surviving component's bandwidth.

## 3. far/empty-ellipse-star — a constraint, not a shortage

The one component that does carry bandwidth is pinned:

| Component | Mode | Mean radius | Feature radius | Headroom over the 8-mm floor |
|---|---:|---:|---:|---:|
| `t001.birth` | 1 | 35.93 mm | 35.93 mm | 27.93 mm |
| `t005.merge1` | 9 | 35.68 mm | **8.000 mm** | **0.000 mm** |

Probing the 20 gauge-tangent directions at that state, **15 are refused by the
feature-radius floor** and none by the clearance guard, the retraction or the
production/refined admissibility checks. A refused probe freezes its Jacobian
column to zero, so three quarters of the shape directions are corrupted; the
optimizer stops `infeasible_jacobian` and the cycle ends `topology_stationary`.

The trajectory shows where the pinned shape came from:

| Accepted state | Components | Feature radii (mm) |
|---|---:|---|
| after third birth | 3 | 35.34, 32.61, **11.84** |
| before merge | 3 | 35.89, 32.47, **12.09** |
| **after merge** | 2 | 35.89, **8.80** |
| after refinement | 2 | 35.89, **8.00** |

The merge contour fit of a two-lobed mask is a peanut whose neck is already
within 0.8 mm of the floor; refinement then drives it onto the floor exactly.
The resulting component spans 8.25–61.8 mm about its centre, a radius ratio of
7.5, where the true ellipse is 26–45 mm, a ratio of 1.73. It is a spike bridging
two regions, not an ellipse.

## Ranking, and what each would take to settle

1. **Candidate construction meeting the feature-radius floor.** The merge
   candidate was scored on objective decrease alone; nothing asks whether the
   winning geometry has room to be refined afterwards. A feasibility headroom
   term in acceptance, or a floor-aware contour fit, is the most direct test.
2. **How the FD Jacobian handles an active constraint.** Freezing a refused
   column to zero silently corrupts every direction that coefficient
   contributes to. One-sided differences, or a projection onto the active
   constraint's tangent, would keep the direction usable. This is cheap to test
   and independent of (1).
3. **Shape capacity after birth.** Circles never become stars. Worth doing, but
   the ellipse-star scenes show that handing a component nine modes is not by
   itself enough — (1) and (2) decide whether those modes can be used.
4. **Acquisition.** Only `merge` is decided by it today. A frequency schedule is
   a separate comparison and must not be folded into the v1 benchmark.

Suspects 1 and 2 are about the *same stalled state* and can share one
experiment; 3 and 4 are separate contracts. None of this is approved.
