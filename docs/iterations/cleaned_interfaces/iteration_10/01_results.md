# NU-002 arclength-reset pre-check: an in-place reset cannot repair drift where it starts

2026-10-02. Offline replay only; no inverse run, no physics evaluation.

## Approval and the stated condition

After the NU-001 result ([iteration 09](../iteration_09/01_results.md)), Claude proposed
an offline test of the [proposal's](../iteration_08/02_proposals/01_coefficient_space_update.md)
eq. 9 spectral reparameterization on saved NU-001 states. A three-case run of arm B
with a threshold-triggered reset (r_σ > 1.2) was to follow **only if** the reset kept
the shape within the 10⁻⁵ L/2π refit tolerance and brought r_σ back to about 1 at
a usable band. The user replied **"go"**. The condition was stated before the replay
ran. It fails (below), so the three-case run was **not** started.

## Method

[`n_reparam.py`](../../../../experiments/cleaned_interface/n_reparam.py) computes the arclength
coefficients z̃_k = ⟨z α′ e^{−ikα}⟩₀ (eq. 9 before integration by parts) by trapezoid
quadrature on a uniform θ grid, doubling the grid until two results agree. It uses no
interpolation, no inversion θ(α) and no splines. `shape_distance` measures the
largest distance from the reset curve to the original curve by Newton projection
with exact Fourier evaluation. Tests: [`test_n_reparam.py`](../../../../experiments/cleaned_interface/test_n_reparam.py)
(ellipse: r_σ 2 → 1 + 2·10⁻⁹ at band 64, shape kept to 3·10⁻¹¹; crop error decays with band;
idempotent; circles kept exactly; a reset that would move the shape is refused).

The replay resets the last accepted state of every stage of the six core runs of
the three arms (nodal = CI-001, A and B = NU-001) at that state's own storage band K:
196 states. Quadrature changed by at most 2·10⁻¹⁰ relative between the last two grids.

```bash
PYTHONPATH=solvers:. python -m experiments.cleaned_interface.n_reparam
```

Record: [`NU-002-reset-replay/replay.json`](../../../../results/validation/cleaned_interfaces/NU-002-reset-replay/replay.json).

## Result

Shape change is max distance / σ₀, σ₀ = L/2π. Gate: ≤ 10⁻⁵.

| Arm | States | Band | r_σ before | r_σ after | Shape change | Within gate |
|---|---:|---|---|---|---|---:|
| nodal | 19 | K = 8–20, r_σ > 1.02 | 1.06–1.17 | 1.009–1.142 | 2.2·10⁻⁴ – 2.2·10⁻³ | 0/19 |
| A | 21 | K = 8–20, r_σ > 1.02 | 1.37–288 | 1.001–1.764 | 3.3·10⁻⁵ – 4.1·10⁻² | 0/21 |
| B | 24 | K = 8–20, r_σ > 1.02 | 1.09–8.04 | 1.000–1.739 | 1.7·10⁻⁶ – 3.0·10⁻² | 3/24 (peanut only) |
| nodal | 36 | K = 192 | 1.00–1.15 | 1.000 | ≤ 8.1·10⁻¹² | 36/36 |
| A, B | 43 | K = 192, r_σ ≤ 3.4 | 1.00–3.38 | ≤ 1.001 | ≤ 1.8·10⁻⁶ | 43/43 |
| A, B | 12 | K = 192, r_σ ≥ 4.6 | 4.56–3915 | 1.008–3.34 | 2.4·10⁻⁵ – 1.8·10⁻³ | 0/12 |

Two worked rows (arm B, `hook`): the end of `stage_2_damped` (K = 12, r_σ = 7.06) resets
to r_σ = 1.74 and moves the shape by 3.0% of σ₀. At `release_M15` (K = 192,
r_σ = 12.87) the reset gives r_σ = 1.82 and moves the shape by 0.18%.

## Interpretation

1. **Measurement.** At the damped stages (K = 8–20) no drifted state of any arm,
   except three peanut states of arm B, can be reset without moving the shape by more
   than 10⁻⁵ σ₀. This includes the **nodal** arm's own curves, whose r_σ of 1.06–1.17
   costs 2·10⁻⁴ – 2·10⁻³ σ₀ to remove.
   **Interpretation.** This is Lemma 2 at finite band: the arclength curve of
   these shapes needs more than K = 8–20 modes. At those bands, r_σ ≈ 1.1 is close to
   the floor any band-K curve can reach, not drift that a reset could remove. NU-001's
   drift begins at exactly these stages (iteration 09), so a stage-boundary or
   threshold reset would act there as a shape filter, not a gauge change.
2. **Measurement.** At K = 192 the reset is exact to ≤ 8·10⁻¹² on every nodal state and
   to ≤ 1.8·10⁻⁶ on every arm A/B state with r_σ ≤ 3.4. It fails from r_σ ≈ 4.6 upwards.
   **Interpretation.** The spectral reparameterization is a usable node-free tool
   once the band is large, provided the curve is never allowed to drift far. It cannot
   recover a curve that has already reached r_σ ≈ 5–13.
3. **Why the nodal map works.** The nodal trial z + P_K[A(z + hn) − A(z)] never stores
   a cropped arclength curve. It adds the **difference** of two cropped projections,
   so the crop error of the arclength curve (about 10⁻³ σ₀ here) cancels to first order.
   NU-001's coefficient updates lack both this cancellation and any arclength restoring
   force. This replay shows that a separate reset cannot supply them at low K.

## Decision

The condition for the arm B + threshold-reset run is not met, so that run is not
started. The NU-001 decision stands: keep the nodal trial map.

## Proposed next (not run)

**NU-003: spectral increment map.** Keep the nodal construction and replace only its
spline resampler A by the eq. 9 quadrature R:
T_z(a) = z + P_K[R(z + h_a(α) n̂) − R(z)], with h_a(α) n̂ evaluated on a uniform grid and
fitted back by FFT, as `project` already does. This has no splines and no interpolation, which
meets the proposal's definition of node-free ("grids used only as exact convolution
engines"), and it keeps the increment cancellation that NU-002 shows is required at
low K. Falsifiable pre-check, offline and with no physics: on the 72 saved nodal states,
compare T_z(a) with `ProjectedUpdate.trial` for random steps at the clip sizes, and the
shape directions with the CI-001 finite-difference columns. Predicted agreement is at the
spline error, well below the 10⁻⁵ projection tolerance. If the pre-check passes, run the six core
cases with the decision rule copied from NU-001 (match ≥ 5/6, no drift flag). If it fails, the
spline resampler is not the only thing doing the work.
