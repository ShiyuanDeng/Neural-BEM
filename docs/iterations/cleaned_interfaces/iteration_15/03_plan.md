# NU-007: certificates on the GPU (pre-registered)

2026-10-02. Implementation owner: Claude. Written and committed **before** the pre-check and
before any campaign run. The decision rules below are fixed.

## Approval

[Iteration 14](../iteration_14/01_results.md) proposed three next steps. The first was
certificate cost: reuse the physics certificate, or run the certificate's 2-D convolutions on the
GPU. The user replied **"go"**. I read that as approval for the first proposal only, NU-007. The
other two proposals (batched LU and Graf waves on the GPU, and the all-36 campaign) are not part
of this plan.

**Why not reuse.** Sharing the certificate that modal physics builds would mean editing
`modal_geometry.py` or `modal_muller.py`. Both are hashed into the NU-004, NU-005 and NU-006
campaign seals, so editing them would break those campaigns' `verify`. NU-007 therefore takes the
GPU route.

## Question

In NU-006, the certificates are 104 s of 242 s wall time. Can they run on the GPU without changing
any validity tier or decision?

## What changes

One method, `_certificate`. NU-005/NU-006 call `n_update.curve_certificate`, which runs
`modal_geometry.log_modulus` on scipy FFTs. NU-007's `device_certificate` is the same construction
in torch float64 on the RTX 5090:
- the divided-difference coefficients of W, and |W|² by FFT convolution;
- Λ = ‖|W|²‖₁, and β = half the sampled minimum on the same FFT grid size;
- the same scalar Chebyshev degree bound;
- the windowed multiplier, with the polynomial cropped to 2B and linear-convolution padding;
- the reciprocal series;
- the untruncated residual ‖1 − |W|²Y‖₁, with the same rounding allowance 80·size·ε·Λ‖Y‖₁.

It refuses under the same three conditions: a sampled minimum ≤ 0, a degree above 4000
(including after the one recomputation), or a lower bound ≤ 0. The log|W|² series itself is not
formed, because no tier uses it. A device out-of-memory error falls back to the CPU certificate
and is counted. Everything else is NU-006 unchanged.

Code: [`nu007.py`](../../../../experiments/cleaned_interface/nu007.py) (`DeviceCertifiedUpdate`,
a subclass of NU-006's `BatchedCertifiedUpdate`), with tests in
[`test_nu007.py`](../../../../experiments/cleaned_interface/test_nu007.py). No frozen source is
modified.

## Disclosure

Before this plan, a prototype compared the port with `curve_certificate` on 36 curves: the
accepted curve and 1 mm and 6 mm trials, on three cases and two stages, each at windows 64 and
128. ‖Y‖₁ agreed to ≤ 4·10⁻¹³ relative and the degrees were equal. The same two curves failed on
both. At K = 192 the port was 10–30× faster (for example 3.47 s against 0.27 s). The unit test
showed that ρ can sit at the FFT round-off floor (about 6·10⁻⁹, absolute difference 10⁻¹⁴), so
the gate below is on the bound, not on ρ.

## Stage 1: offline pre-check (no physics)

The design is NU-005's: 72 states (the last accepted state of every NU-006 stage) with 12 random
steps each (seed 5; three directions at each of 10⁻⁷ m, 1 mm, 6 mm and 18 mm). Every trial is
built with `BatchedCertifiedUpdate` (CPU certificates) and with `DeviceCertifiedUpdate`.

Pass requires all three:
1. **Same decisions:** the same status and refusal reason, and bit-identical accepted candidates.
2. **Same tiers:** each curve's tier sequence is the same in both.
3. **Bounds:** increment and full bounds agree to ≤ 10⁻⁹ relative.

If the pre-check fails, stop: the campaign is not run.

## Stage 2: six-case campaign (only if stage 1 passes)

Campaign `NU-007` (arm MD), prepared after this plan and the tests are committed, with
augmentation reused from CI-001. The settings are those of NU-006, unchanged.

**Decision rule (fixed).**
- **Retained** if the NU-001 rule against nodal CI-001 holds: no drift flag and ≥ 5/6 matches.
- **Adopt device certificates** if they are retained *and* identical to NU-006 in decisions (the
  same accepted steps in every stage and the same units) *and* in the validity tier counts of
  every case.
- **Otherwise:** report the first difference. Do not adopt.

**Logged, not decisive:** certificate seconds, total wall time, the final-curve distance from
NU-006, and fallbacks.

## Predictions

- Identical to NU-006 in decisions and tier counts. The final curves are bit-identical, because
  certificates do not enter the curve arithmetic.
- Certificate time falls from 104 s to ≤ 15 s.
- Wall time falls from 242 s to 140–160 s.

## Not in scope

Certificate reuse with physics, batched LU, Graf waves on the GPU, the trial projections,
all-36 retention, and matched runtime pairs.
