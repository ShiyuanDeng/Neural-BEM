# Review of the coefficient-space update proposal against the code

2026-10-01. Reviewer: Claude. Subject: [01_coefficient_space_update.md](01_coefficient_space_update.md),
written without access to the repository. Evidence:
[NU-001 control](../../../../../results/validation/cleaned_interfaces/NU-001-control/README.md).

## What the proposal gets right

- The trial map it replaces is `ProjectedUpdate` in
  [`geometry.py`](../../../../../experiments/cleaned_interface/geometry.py). `grid_size(192)` is 8192, and
  `prepare` makes 2(2M+1)+2 spline projections.
- **The physics needs no change.** `ModalMuller.derivative` already takes the
  coefficient velocities `space.derivatives` and forms Re(V conj N) with the
  same N = j z_j. `NodalKress` evaluates them through `update.velocities`. An
  update that fills `derivatives` with P_K(φ_q N)/(σ₀ L) plugs into both.
- Eq. 3 (ω_q = φ_q S) and Lemma 1 (tangential moves have zero weight) hold to
  1e-11 wherever the crop is inactive (K = 192), and the N-update trial is
  affine to 1.6e-10.

## Corrections

1. **The baseline already drifts.** The cleaned interface does not refit the
   accepted curve in arclength. It adds the arclength-gauge increment
   A(z+hn) − A(z) to z. On the six CI-001 core runs the speed ratio r_σ rises
   from 1 to 1.06–1.17 during the damped stages and then stays flat. The drift rules must be
   relative to the nodal arm, not to 1.

2. **The baseline basis is not the arclength harmonics of the accepted curve.**
   The increment is a function of the moved curve's arclength t, but it is
   added at coefficient index t of z, whose parameter is not arclength. The
   point z(θ) is therefore moved by the displacement computed for the
   arclength point z̃(θ). An exact first-order model of this
   (`baseline_linearization`: normal move, first-order change of normalised
   arclength, spline composition as in `project`) reproduces the FD columns to
   **≤ 2.3e-7 on all 72 saved states**. Against those weights:

   | Candidate weights | median of medians | worst column |
   |---|---:|---:|
   | cos(mα)σ, the proposal's "hybrid" | 1.6% | **66%** (hook, M=37) |
   | cos(mθ)σ, θ-harmonics with unit normal move | 0.4% | 25% |
   | N-update, arm A | 1.9% | 26% |
   | N-update, arm B | 1.5% | 26% |

   The hybrid columns cannot replace the baseline Jacobian. The proposal's
   third outcome is withdrawn. The baseline is closest to θ-harmonics with a
   unit normal move, which differs from the N-update by the factor σ/σ₀, so
   the N-update is closer to the baseline than the proposal assumed.

3. **The crop matters at the damped stages.** There the storage band is
   K = 2M+2, so g_a N (band K+M) loses up to 7% of its ℓ¹ norm to P_K, and
   eq. 3 is off by up to 10%. The derivative remains exact because it is the
   derivative of the cropped trial. At K = 192 the loss is ≤ 1.3e-8.

4. **The update class is hard-coded.** `runner.py:97` constructs
   `ProjectedUpdate`, and `runner.py` is a CI-001 frozen source. NU-001
   substitutes the class and policy for a run (`arm_substitution`) and modifies
   no frozen file. CI-001 `verify` still passes.

5. **Validity.** The O(K) certificate (Lemmas 3–4) needs the accepted curve's
   reciprocal Y. At window 64 that costs 0.6–0.8 s per prepare at K = 192
   (ρ_c ≤ 6e-5) and admits ν(Δz) up to 0.003–0.024, i.e. 0.17–1.2 mm at m = 1.
   That is far below the 6–18 mm clips, so it will decide only small late
   steps. NU-001 measures how often it does.

## Cost

`prepare` at K = 192 takes 2.87 s (median) for the nodal update, 2 ms for arm A
and 5 ms for arm B, plus the optional certificate. On this CPU host, however,
geometry was only 23 s of the 1067 s `circle_to_c` fit. Physics evaluation
dominates, so the wall-time gain is small here. On the GPU host geometry was
8.8 s of 63 s.
