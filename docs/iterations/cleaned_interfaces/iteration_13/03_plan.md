# NU-005: validity without samples (pre-registered)

2026-10-02. Implementation owner: Claude. Written and committed **before** the pre-check and
before any campaign run. The decision rules below are fixed.

## Approval

[Iteration 12](../iteration_12/01_results.md) proposed NU-005 as its first next step. The user
replied **"keep up to NU005"**. I read that as approval for NU-005 only, ending this sequence
there. NU-006 (cheaper quadrature) and the all-36 campaign are not part of this plan.

## Question

NU-004-MS runs modal Müller physics with the spline-free trial map. Validity is still decided
by the sampled test from CI-001. Within each trial it runs three times:

| Role | Curve | Sampled test |
|---|---|---|
| `moved_coarse` | z + h n fitted on the `count` grid (band count/2 − 1) | area, min speed, polygon self-intersection |
| `moved_fine` | the same on the `2·count` grid | the same |
| `candidate` | c = z + P_K[R(moved) − R(z)] (band K) | `FourierCurve.validate` |

**Question:** can coefficient certificates decide these checks without changing any decision,
and how many curves still need the sampled test?

## What changes

The trial map, the curves it builds and the order of the checks are all unchanged. Each
sampled test is preceded by three tiers (proposal §5, iteration 08). The first decisive tier
ends the check:

1. **Exact area** π Σ j|x_j|². If it is ≤ 0, the curve is refused with the same reason the
   sampled test gives (`irregular_parameterization`). For a band-limited curve, the sampled
   trapezoid area equals this sum to round-off.
2. **Increment (Lemmas 3–4).** The bound is ρ_c + (2ν(z)ν(D) + ν(D)²)‖Y‖₁ < 1, with
   D = x − z. Y is the window-64 reciprocal of the accepted curve's |W|² (the NU-001 window),
   built once per prepared space when it is first needed.
3. **Full certificate.** `curve_certificate` is applied to x_B = P_B x, with B = max(K, 64)
   (for a candidate, x_B = x). The tail x − x_B is absorbed by Lemma 3 against x_B's own
   certificate. The window is 64, escalating once to 128 if 64 is not decisive.
4. **Fallback.** Otherwise the unchanged sampled test runs and its decision stands.

Tiers 2 and 3 only accept. They accept only when the bound certifies |W_x|² ≥ λ > 0 on the
torus, which makes x simple and regular, and λ ≥ 10⁻¹² Σ j²|x_j|². Parseval gives
mean|x′| ≤ (Σ j²|x_j|²)^½, so λ at this level implies the sampled test's speed condition
min|x′| ≥ 10⁻⁶ mean|x′|. Inconclusive checks fall through to the sampled test, so refusals
and their reasons cannot change.

**Not implied by a certificate.** A certified simple curve can, in principle, have a sampled
polygon that self-intersects if the sampling is far too coarse. The pre-check therefore runs
the sampled test in shadow on every certified curve. Also, `log_modulus` proposes its
interval β from |W|² values on an FFT grid. That grid only proposes β; the coefficient residual
decides. This matches the proposal's definition of node-free (grids used only as transform engines).

Code: [`nu005.py`](../../../../experiments/cleaned_interface/nu005.py), `CertifiedSpectralUpdate`
(a subclass of NU-003's `SpectralProjectedUpdate`), with tests in
[`test_nu005.py`](../../../../experiments/cleaned_interface/test_nu005.py). No frozen source is
modified.

## Disclosure

Before this plan was written, smoke tests ran on four NU-004-MS states: `hook` and `kite`, at
`stage_4_damped` and `fixed_M37`. Every decision matched. Two design choices were made from those
runs:
- At K = 20, cropping a moved curve to K left a tail too large for Lemma 3 (bound 1.3–24 at
  1–6 mm). This set B = max(K, 64).
- On `kite` `fixed_M37`, a 6 mm random step failed the window-64 certificate (residual 1.78) and
  passed at window 128 (residual 0.41). This added the single escalation to 128.

The smoke tests also showed that the certificates cost about 0.1–7 s per trial, against
0.004–0.08 s for the sampled test.

## Stage 1: offline pre-check (no physics)

States: the last accepted state of every stage of the six NU-004-MS core runs (72 states). At
each state, 12 random steps (seed 5): three directions at each of 10⁻⁷ m, 1 mm, 6 mm and 18 mm
maximum normal displacement. Each step is built with `SpectralProjectedUpdate` (sampled) and with
`CertifiedSpectralUpdate`. In the second, the sampled test also runs in shadow on every certified
curve.

Pass requires both:
1. **Same decisions.** Every trial has the same status and refusal reason, and accepted
   candidates have bit-identical coefficients.
2. **No shadow disagreement.** Every curve accepted by tier 2 or 3 is also accepted by the
   sampled test.

Coverage by tier, role and step size is reported but does not gate. If the pre-check fails,
stop: the campaign is not run.

## Stage 2: six-case campaign (only if stage 1 passes)

Campaign `NU-005` (arm MC), prepared after this plan and the tests are committed, with
augmentation reused from CI-001. The settings are those of NU-004-MS, unchanged: `modal_muller`,
NU-001's `ArmPolicy`, the CI-001 schedule, `device=auto` on the RTX 5090, four frequency threads,
one case at a time, from the original start. The shadow test is off.

**Decision rule (fixed).**
- **Retained** if both hold:
  - the NU-001 rule against nodal CI-001 (no drift flag and ≥ 5/6 matches), and
  - **decision identity with NU-004-MS**: the same accepted steps in every stage and the same
    total units in every case.
- If retained, the outcome is set by the fallback count over all validity checks in the six runs:
  - **0**: *validity was decided without samples on the six core cases*;
  - **> 0**: the sampled fallback is still needed. Report the fraction and, for each fallback,
    its role, step stage and failed bound.
- If not retained: the tiers changed a decision (this contradicts stage 1). Locate the first
  differing stage. The tiers are not adopted.

**Logged, not decisive:** tier counts by role, certificate and sampled seconds, total wall time
against MS's 292.6 s, and the final-curve distance from MS.

## Predictions

- Decision-identical to NU-004-MS. Stage 1 checks the mechanism, and the candidate curves are
  computed by the same code.
- The fallback count is above zero, concentrated in the K = 192 stages of `hook`, `kite` and
  `circle_to_c`, where the smoke test needed it at 6 mm. It is below 20% of checks, because LM
  steps are smaller and smoother than random full-band steps.
- Wall time is higher than MS (prediction: 400–900 s), because each certificate costs 10–100×
  a sampled test.

## Not in scope

Refusing invalid curves without samples (NU-004-MS refused no trial on these cases, so this is
untested), all-36 retention, matched runtime pairs, and reducing the certificate cost (for
example, reusing the |W|² certificate that modal physics already builds for every curve it
evaluates).
