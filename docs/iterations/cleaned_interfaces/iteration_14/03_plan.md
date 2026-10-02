# NU-006: GPU-batched spectral prepare (pre-registered)

2026-10-02. Implementation owner: Claude. Written and committed **before** the pre-check and
before any campaign run. The decision rules below are fixed.

## Approval

After [iteration 13](../iteration_13/01_results.md), the user asked whether GPU speedups could be
combined with the current pipeline. I proposed NU-006 as a GPU-batched spectral `prepare`, in
place of iteration 12's NUFFT proposal. The user replied **"yes go"**. That approves NU-006 only.
The other ideas raised in the same answer (batched LU, Graf waves on the GPU, certificate reuse)
are not part of this plan.

## Question

In NU-004-MS, geometry preparation is 154 s of 293 s wall time (52%). Can it move to the GPU
without changing any decision?

## What changes

One method. `ProjectedUpdate.prepare` builds 2(2M+1) + 2 independent projections: the base
projections at `count` and `2·count`, and central differences (ε = 10⁻⁷ m) for every coordinate.
NU-003/NU-005 evaluate them one at a time on the CPU with `spectral_project`. NU-006's
`batched_projection` evaluates the same mathematics for all of them in one torch float64 call on
the RTX 5090:
- the normal move h(α)n on the uniform grid;
- the FFT fit without the Nyquist mode;
- the moved curve's speed and normalised arclength, with the same monotonicity refusal;
- the eq. 9 quadrature, with e^{−ikα} evaluated directly instead of by recurrence, in chunks of
  at most 512 MiB.

A device out-of-memory error falls back to the CPU `prepare` and is counted. Everything else is
NU-005 unchanged: trials, the certificate validity tiers, LM, the schedule, policy and modal
physics.

Code: [`nu006.py`](../../../../experiments/cleaned_interface/nu006.py) (`BatchedCertifiedUpdate`,
a subclass of NU-005's `CertifiedSpectralUpdate`), with tests in
[`test_nu006.py`](../../../../experiments/cleaned_interface/test_nu006.py). No frozen source is
modified. The update uses CUDA whenever it is available. Its device is independent of the physics
`--device` and is recorded in the update settings.

**Expected difference.** The arithmetic changes only in rounding (the FFT library, the summation
order, and direct exponentials instead of a recurrence). Divided by 2ε, that rounding perturbs the
Jacobian columns by about 10⁻⁹ relative, so the runs will not be bit-identical.

## Disclosure

Before this plan, a prototype ran on two NU-004-MS `kite` states (`stage_4_damped`, `fixed_M37`).
The projections agreed to 5·10⁻¹⁵ and the columns to 6·10⁻⁹ relative. Time fell from 1.97 s to
0.038 s at K = 192, M = 37. The 10⁻⁷ column gate below is the NU-003 spectral-versus-spline column
difference (1.4·10⁻⁷), which left every decision identical. It is set after seeing the prototype.

## Stage 1: offline pre-check (no physics)

States: the last accepted state of every stage of the six NU-005 core runs (72 states). At each
state, `CertifiedSpectralUpdate.prepare` (CPU) and `BatchedCertifiedUpdate.prepare` (GPU, timed
after one warm-up) are compared.

Pass requires all three:
1. **Columns:** the maximum relative column difference is ≤ 10⁻⁷.
2. **Base projections:** the coarse and fine base projections differ by ≤ 10⁻¹² σ₀.
3. **No fallback:** there is no CPU fallback.

If the pre-check fails, stop: the campaign is not run.

## Stage 2: six-case campaign (only if stage 1 passes)

Campaign `NU-006` (arm MG), prepared after this plan and the tests are committed, with
augmentation reused from CI-001. The settings are those of NU-005, unchanged: `modal_muller`,
NU-001's `ArmPolicy`, the CI-001 schedule, `device=auto`, four frequency threads, one case at a
time, from the original start.

**Decision rule (fixed).**
- **Retained** if the NU-001 rule against nodal CI-001 holds: no drift flag and ≥ 5/6 matches.
- **Adopted as the default `prepare`** if it is retained *and* decision-identical to NU-005: the
  same accepted steps in every stage and the same total units in every case.
- **Retained but not decision-identical:** report the first differing stage and the final-curve
  distance from NU-005. Do not adopt it as the default.

**Logged, not decisive:** geometry preparation seconds, total wall time, the final-curve distance
from NU-005, and the validity tier counts.

## Predictions

- Decision-identical to NU-005, with final curves within 10⁻⁸ σ₀ of it.
- Six-case geometry preparation falls from NU-005's 150 s to ≤ 15 s.
- Wall time falls from 390 s to 230–270 s. The NU-005 certificates (103 s) remain. Without them,
  the same saving would put MS at about 145 s.

## Not in scope

The trial projections (still the CPU `spectral_project` path, two per trial), certificate cost,
batched LU, Graf waves on the GPU, all-36 retention, and matched runtime pairs.
