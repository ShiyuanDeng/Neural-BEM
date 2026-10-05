# Historical runtime-profile draft and proposed lean LM

2026-10-05, Claude. User request: "documents findings especially about current
runtime share of each component, with little judgments. also record our
proposed cut with justifications."

**Accounting correction added before archival commit:** the raw saved
summary reproduces this draft's calculations, but its geometry/physics
counters include audit work whereas the fit timer excludes audits. Therefore
subtracting those counters from fit-only time does not establish the claimed
component partition. The 82%/18% split and lean-LM forecasts below retain
that accounting limitation; they are historical, uncorrected model outputs,
not validated timing guidance. Use the
[corrected pipeline audit](../../CI-SPD/INVERSE_PIPELINE_AUDIT.md) for the
scope-aware interpretation. Original figures and proposal are preserved.

This is a read-only analysis of saved receipts: ON-001 `all_B`/`all_E`, RG-001,
GC-001, EW-001, and GGB-001 case 8. No solves or fits were run. The numbers are
recomputed by `experiments/benchmark/runtime_profile.py`; its output is in
[runtime-profile-20261005](../../../../results/validation/cleaned_interfaces/runtime-profile-20261005/README.md).

## 1. Where the E recipe spends time today

Physics is timed per frequency thread (four threads), so its wall time is not
measured directly. It is estimated as fit time minus geometry time.

| 26 recovered cases | Seconds | Share |
|---|---:|---:|
| Audited output | 435 | 100% |
| Audits and setup (initial and terminal audits, CUDA start, output) | 99 | 23% |
| Fit | 336 | 77% |
| — physics (estimated) | 276 | 82% of fit |
| — geometry trial checks: certificates 19 s, projections 13 s, other 9 s | 41 | 12% of fit |
| — geometry preparation | 19 | 6% of fit |

Inside physics, by thread time:

| Component | Device | Share |
|---|---|---:|
| Assembly | GPU | 29% |
| Graf waves | CPU | 22% |
| LU | CPU | 20% |
| Fields | CPU | 6% |
| Modal geometry | GPU | 7% |
| Unnamed overhead | — | 16% |

The Jacobian and derivatives add another 2% on top of evaluation time.
Frequency solves split 51% production (10% stage-entry, 41% candidates) and
49% refined acceptance re-solves.

The four failures (102 s of fit) differ:

- Geometry trial checks take 47% of their fit, almost all certificates
  (46 of 48 s). Physics takes 51%.
- All 43 refusals came from the coarse moved-curve check.

## 2. What each check decided (B and E receipts)

| Mechanism | Decisions it changed |
|---|---|
| Coarse moved-curve validity | All 43 refusals. Under RG's relaxed gate: 203 of 205. |
| Fine refit (2N) and its agreement test | 0 refusals; never fired. |
| Fine moved-curve validity | 0 refusals (2 only under RG's relaxed gate). |
| Final candidate validity | 0 refusals, in every arm. |
| Certificate tiers | In successes: 75–78% of checks settled by the cheap increment tier, the rest by a full certificate. No sampled fallbacks. |
| Refined acceptance re-solve | 0 decisions in the 26 E successes. All 347 rejections were tiny gains below the fixed margin. Production and refined gains agree to a median of 1.5e-6. |
| Step halving | 1288 of 1313 accepted steps (98%) were full length; 25 needed one halving. 40 trials did not decrease the loss. |

Three external results are also relevant:

- **GC-001:** sampled validity made the same decisions as certified validity on
  all 279 replayed moves, at 66 ms against 487 ms on a 6 mm move.
- **EW-001:** GPU assembly per 19-frequency service is 0.106 s at K_trace 128
  and 0.111 s at 160.
- **RG-001:** with the fatal gate relaxed, 3 of 4 failures ran to the 120 s cap.
  The suite total rose from 554 s to 841 s.

## 3. GGB-001 case 8 (single frequency, far start)

- **Timing.** The BEM fit took 348 s, of which recorded physics calls were
  29 s. GauGal's optimization took 0.81 s.
- **Start.** The object has an equivalent radius of 0.17 m and is centred 0.62 m
  off-centre. It does not overlap the 0.35 m centred start.
- **Data.** The data are one real frequency at 0.4 GHz.
- **Progress.**
  - The first 12 updates reduced the residual from 264% to 134% in 4.5 s.
  - The remaining 87 updates and about 800 proposals took about 343 s and
    reached 88%. 669 proposals were refused for self-intersection and 73
    physics evaluations failed.
  - GauGal reached 5.3%.
- **Stopping rules.** TG-002's 22-iteration stage cap would have ended the
  first stage (M3) at 23 s. A rule of less than 2% gain over 5 updates would
  have ended it at 38 s.
- **Follow-up.** GGB-002, approved and in progress at the time of writing,
  reruns case 8 with four real frequencies to test the single-frequency
  explanation. Its plan is `CI-SPD/GGB-002_plan.md`.

## 4. Proposed cut: lean LM (proposed ID GN-001, not approved)

| Change | Justification |
|---|---|
| Keep one geometry check: the coarse moved curve, by increment tier then sampled test | It made every refusal (section 2). GC-001 shows sampled validity reaches the same decisions as certified validity at lower cost. |
| Drop the fine refit, its agreement test, and the fine and candidate validity checks | 0 refusals in B and E |
| Drop step halving. A rejected step raises damping (×10, at most 5 tries) | 98% of accepted steps were full length. LM damping is itself a globalization (Moré 1978; Nocedal and Wright 2006, §10.3). |
| Drop the per-trial refined re-solve. Accept on production gain above the existing margin. | 0 decisions changed in successes. Inexact trust-region theory (Kouri et al. 2014) requires error that is small relative to the reduction. |
| Keep the endpoint audit and the margin test | The audit caught the unresolved RG-001 endpoints. The margin test ends stages (347 rejections). |
| Add one early stop for failing runs, for example a refined check at stage end | Without the fatal gate, failures run to the cap (RG-001) |

Predicted effect on the 26 successes, plus suite totals. This is a model, not a
measurement.

| Quantity | Low | Central | High |
|---|---:|---:|---:|
| Success fit time (336 s now) | 193 s | 154 s | 139 s |
| Median fit speedup vs E | 1.75x | 2.17x | 2.41x |
| Median audited-output speedup vs E | 1.46x | 1.64x | 1.73x |
| Median audited-output speedup vs B (10th percentile) | 2.24x (1.75x) | 2.54x (1.90x) | 2.73x (1.97x) |
| Suite of 30, failures stopped early (E: 551 s, B: 803 s) | 408 s | 369 s | 354 s |
| Suite of 30, failures run to the cap | 697 s | 659 s | 643 s |

Model assumptions:

- A refined solve costs 1.0, 1.3 or 1.6 times a production solve (low,
  central, high). LU runs on the CPU and scales as N³; assembly runs on the GPU
  and costs about the same at either resolution.
- 55%, 66% or 70% of trial geometry time is removed.
- Physics wall time is fit minus geometry (central and high). The low case uses
  thread time divided by 4.
- Accepted paths and audits are unchanged.

Not modelled: at most 5 tries per update instead of up to 40, and the cheaper
sampled check in heavy cases.

What remains after the central cut, of 253 s audited output:

- production physics: 121 s (48%)
- audits and setup: 99 s (39%)
- geometry: 33 s (13%)

## 5. Open measurements

- The refined-to-production solve cost ratio. It sets the range above; timing
  both resolutions on saved curves would fix it.
- The split of certificate time by tier. It is not recorded, so the share spent
  on failed full-certificate attempts is unknown.
- Whether the initial audit can be shared per contrast. The same start circle is
  audited in every case, giving 3 distinct audits instead of 30.
