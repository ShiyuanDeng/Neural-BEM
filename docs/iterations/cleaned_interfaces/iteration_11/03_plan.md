# NU-003: spectral increment map (pre-registered)

2026-10-02. Implementation owner: Claude. Written and committed **before** the
pre-check and before any campaign run; the decision rules below are fixed.

## Approval

[Iteration 10](../iteration_10/01_results.md) proposed NU-003. It also listed the §8
options of the [proposal](../iteration_08/02_proposals/01_coefficient_space_update.md)
already tested. The user replied **"go"**.

## What changes

One step of the CI-001 trial map T_z(a) = z + P_K[A(z + h n) − A(z)]. The resampler A
(spline inversion θ(α) plus spline interpolation at uniform arclength) is replaced by
the eq. 9 quadrature R(w)_k = ⟨w α′ e^{−ikα}⟩₀, |k| ≤ K, on the same uniform grid
(`count`, and `2·count` for the refinement check). Everything else is unchanged and
inherited from `ProjectedUpdate`: the normal move h(α) n on the uniform grid, the FFT
fit, the central-difference columns (ε = 10⁻⁷ m), the 10⁻⁵ projection tolerance, the
validation, the clips, the damping and the schedule. The map then uses no splines or
interpolation, which is the proposal's definition of node-free.

Code: [`nu003.py`](../../../../experiments/cleaned_interface/nu003.py), tests in
[`test_nu003.py`](../../../../experiments/cleaned_interface/test_nu003.py). No frozen
source is modified. `nu003.substitution` swaps the runner's update class and uses
NU-001's `ArmPolicy`, so time caps are identical to NU-001 arms A and B and work-unit
caps are unchanged.

## Disclosure

Before this plan was written, a smoke test ran `precheck_state` on two CI-001 `hook`
states (`stage_2_damped`, `release_M11`). Spectral self-refinement was ≤ 5·10⁻¹⁴
and spline refinement 2·10⁻¹⁵ – 9·10⁻¹⁰; the spectral–spline difference was ≤ 1·10⁻⁹ σ₀
and the column difference ≤ 1.4·10⁻⁷. At 10⁻⁷ m steps the spline refinement was
smaller than the spectral one, both at round-off. Gate 2 therefore gets a round-off
floor of 10⁻¹² σ₀, set after seeing these two states.

## Stage 1: offline pre-check (no physics)

States: the last accepted state of every stage of the six CI-001 core runs (72 states).
At each state, both updates are prepared. Nine random steps are drawn (seed 3): three
directions at each of 10⁻⁷ m, 1 mm and 6 mm maximum normal displacement. For each
step the trial is built with the spline map and the spectral map, each at `count` and
`2·count`. Distances are the maximum over a 2·count grid, divided by σ₀ = L/2π.

Pass requires all three:

1. **Trial agreement:** max |T_spectral − T_spline| ≤ 10⁻⁵ σ₀ (the projection
   tolerance CI-001 already treats as noise).
2. **Spectral at least as accurate:** in ≥ 90% of trials,
   |T_spectral(count) − T_spectral(2·count)| ≤ max(|T_spline(count) − T_spline(2·count)|, 10⁻¹²).
3. **Jacobian agreement:** max relative column difference ≤ 10⁻³ (the frozen
   per-column audit gate).

If the pre-check fails, stop: the campaign is not run.

## Stage 2: six-case campaign (only if stage 1 passes)

`NU-003` campaign, prepared from the commit that adds this plan, with augmentation
reused from CI-001. Six core configurations from the original start, `nodal_kress`
physics, `device=auto` on the RTX 5090, four frequency threads, one case at a time.
The nodal arm is the archived CI-001 campaign, as in NU-001.

**Decision rule, copied unchanged from NU-001:**
- **Drift flags:** max r_σ > 1.5; max r_σ > 1.1 × nodal; or log|W|² degree > 1.3 × nodal at any stage.
- **Match:** (passes frozen gates or nodal does not) and (recovers or nodal does not).
- **Adopt** the spectral increment map if there is no drift flag and it matches on ≥ 5/6.
  Otherwise keep the spline resampler.

**Logged, not decisive:** per-stage accepted steps against nodal, the final-curve
distance from the nodal final curve, geometry preparation and trial seconds, and total wall time.
The prediction is decision-identical or near-identical runs, because the two maps differ only by
spline error (≤ 10⁻⁹ σ₀ in the smoke test).

## Scope of a pass

A pass establishes that the CI-001 trial map can run without splines on the six core
cases. It does not establish all-36 retention or a runtime gain. Combining it with the
modal Müller forward solver (a fully node-free inverse) is a separate step.
