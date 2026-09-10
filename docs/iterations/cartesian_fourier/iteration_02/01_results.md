# Cartesian Fourier — iteration 2 results

Recorded 2026-09-09 after executing the
[iteration-1 plan](../iteration_01/03_plan.md). No neural field participated in
any part of this cycle.

## Outcome

**The Cartesian Fourier chart reaches the radial chart's accuracy regime on the
same problem: `2.761e-09 m` maximum boundary error in 41 accepted updates,
against the radial reference's `2.570e-10 m` in 44.** It converged on its own
stopping criterion rather than exhausting its budget.

Two of the three pre-declared parity gates are missed, narrowly:

| Quantity | Cartesian K6 | Radial reference K5 | Gate | Met |
|---|---:|---:|---:|:--:|
| Train relative L2 | `1.296e-07` | `1.068e-08` | `<= 1e-07` | no, by 30% |
| Holdout relative L2 | `1.127e-07` | `1.339e-08` | `<= 1e-07` | no, by 13% |
| Maximum boundary error | `2.761e-09 m` | `2.570e-10 m` | `<= 1e-08 m` | **yes** |
| Accepted updates | 41 | 44 | — | — |

Initial state is identical to the reference by construction: maximum boundary
error `4.181e-02 m`, train relative L2 `1.197`, holdout `1.136`. The geometric
gate passes; the two data gates miss by less than a factor of two. This is
reported as **parity in regime, not a met-gates parity claim**.

Stop reason `stable_data_and_geometry`, reached two accepted updates into a
stage-3 budget of 111. Accepted updates are `19 + 20 + 2` across the three
continuation stages; the trajectory holds 44 rows because each stage records
its own iteration-zero baseline, and the reference is counted the same way.

## The final spectrum confirms the band prediction exactly

The plan fixed band six from an algebraic identity rather than a search. The
recovered coefficients are the strongest available check on it. Mode amplitudes
of the final state, in millimetres:

| Mode | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Initial | 707.672 | 73.010 | 0 | 11.579 | 0 | 2.708 | 0 |
| Final | 707.107 | 70.711 | 0 | `1e-06` | 8.8388 | 0 | 8.8388 |

The optimizer drove modes 2, 3 and 5 to zero and converged on exactly the three
predicted active modes. The values are the closed form: `0.5 * sqrt(2) = 0.70711`
for the centre, `r0 * sqrt(2) = 0.070711` for mode one, and
`r0 * eps * sqrt(2) / 2 = 0.0088388` for modes four and six. The residual
`1e-06 mm` in mode three is one nanometre, consistent with the boundary error.

So the chart did not merely fit the data; it recovered the analytic Cartesian
representation of the target.

## What actually decided the outcome

Not the bandwidth. **Parameterization drift**, and the plan's §4 was wrong about
it — the amendment recorded in
[§4.1](../iteration_01/03_plan.md) documents the measurements. Left free, the
parameter speed ratio compounded at about `1.4` per accepted update, reaching
`226` within fifteen while the boundary error stalled near `34 mm`. Six accepted
steps of `1.9 mm` moved the boundary by `2.3 mm` in total: the trust region was
being spent on motion the data cannot see.

Three softer controls were measured and all failed — a tangential energy cap had
no effect, a direct speed-ratio cap pinned the iteration against itself, and a
tangential Tikhonov prior improved monotonically with weight but still stalled at
loss `0.219` against the reference's `0.056`. What worked was making the
retraction gauge-fixing: re-expressing every retracted state in its own
polar-angle parameter, by exact Newton solution rather than interpolation.

With that single change and both other controls disabled, the speed ratio stayed
between `1.90` and `2.75` for the whole run — the analytic target's own value is
`2.13` — and every accepted update in the entire run took **zero backtracks**.

## The accuracy floor is the re-gauge truncation

Re-gauging is a band truncation, and its measured size tracks the final error:

| Trajectory row | 3 | 7 | 38 | 40 | 43 |
|---|---:|---:|---:|---:|---:|
| Re-gauge maximum, µm | 379.05 | 684.42 | 0.23 | 0.03 | 0.01 |

It rises while the curve is far from the target and collapses as it approaches,
because the exact target is a fixed point of the map — verified independently at
`9.7e-17 m`. The final truncation, `1e-8 m`, sits at the same scale as the
residual boundary error `2.761e-09 m`. That is the most likely explanation for
the remaining factor of ten against the radial chart, and it is a testable claim
rather than a settled one.

## Limits of this result

- One target, one initial shape, one acquisition. The band-six choice is an
  algebraic property of *this* target; it does not generalize without redoing
  the identity.
- The re-gauge floor is identified by correlation of two quantities at the same
  scale, not by a controlled test. Nothing here isolates it.
- Cost was not matched and is not claimed: 26 coefficients against 11 means
  roughly 52 forward solves per Jacobian against 22.
- Convergence stopped the run with 109 of the stage-3 budget unused, so this is
  not evidence about what a longer run would reach.
- No neural field was involved, so nothing here speaks to the implicit-MLP
  cycle, which remains open at its own
  [iteration-3 plan](../../implicit_mlp/iteration_03/03_plan.md).

## Candidate next checks

| Priority | Question | Cheapest discriminating check |
|---|---|---|
| 1 | Is the re-gauge truncation the accuracy floor? | Re-run from the converged state with the re-gauge disabled for a few updates, and separately at a higher band, and see whether the boundary error falls below `2.761e-09 m` |
| 2 | Does the chart hold up away from a band-exact target? | A target whose polar-angle spectrum does not terminate, where re-gauging truncates at every step and the floor is intrinsic |
| 3 | Is the gauge-fixed Cartesian chart distinguishable from the radial chart in what it can represent? | Compare reachable shape sets directly: re-gauging projects onto curves that are band-`K` in polar angle, which is close to, but not identical with, the radial chart |
| 4 | Does the cost gap close with analytic Jacobian columns? | `linearize_kress_forward` columns instead of central differences; the pattern already exists in `run_star_observability.py` |

## Evidence

Side-by-side comparison with the radial chart, including matched-work and
matched-update views:
`results/inverse/cartesian_fourier/comparison_with_radial_fourier.md`.

Run bundle:
`results/inverse/cartesian_fourier/cartesian-k6-ellipse-to-star-nystrom-kress-20260910/`
containing `metrics.json`, `kress_trajectory.csv`, `kress_responses.npz` and
`summary.md`. Reference:
`results/inverse/radial_fourier/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/`.

Command:

```text
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
python run_explicit_cartesian_fourier_inverse.py --target star --initial-shape ellipse \
  --train-ghz 0.5,1.5,2.5 --holdout-ghz 0.25,1.0,2.0 --num-pairs 24 \
  --maximum-mode 6 --outer-iterations 150 --maximum-modal-update-mm 2.0 --overwrite
```

Validation gates A–E are enforced as regression tests in
`pytest/sdf_inverse/test_cartesian_fourier_chart.py`, including the band-six
identity, the arc-length counter-example, the phase-gauge invariance and the
assertion that no neural field is ever touched.
