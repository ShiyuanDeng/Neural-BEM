# CI-001 all-36 campaign

2026-09-30. The user ran the documented campaign between 17:16 and 18:46:
`prepare`, `spd-pairs`, `augment`, `run` and `report`. Settings were
`nodal_kress`, `device=auto`, SPD-016 acceleration, 4 frequency threads and
1 worker, on the RTX 5090 host. Claude analysed the saved receipts; see the
[review bundle](../../../../results/validation/cleaned_interfaces/CI-001-campaign-review/README.md).

**Result: all 36 cases completed, and 28 pass the frozen comparison contract.
Requirement 1 is not satisfied.** Recovery is 34/36, the same count and the same
two failures as the historical references. Runtime retention is not established.

| Evidence | Location |
|---|---|
| Per-case comparison | [comparison.json](../../../../results/validation/cleaned_interfaces/CI-001/comparison.json), [comparison.csv](../../../../results/validation/cleaned_interfaces/CI-001/comparison.csv) |
| SPD extraction pairs | [spd_pairs/comparison.json](../../../../results/validation/cleaned_interfaces/CI-001/spd_pairs/comparison.json) |
| Regression summary (script output) | [summary.json](../../../../results/validation/cleaned_interfaces/CI-001-campaign-review/summary.json) |

## SPD extraction control

Both D pairs pass every same-backend gate. Stages, decisions, accepted
indices and work are identical. The relative difference in the final curve is at
most 9.1e-12, and the reference path reproduces the archive exactly. The
SPD-016 path saves 59.6% of the time on `far__shifted_star` (97.7 s against 242.0 s)
and 64.0% on `modal__c13.3__new_asymmetric` (139.6 s against 387.8 s). These
are two sequential pairs, not full-path or all-36 speedup evidence.

## What passes

- **Faithful extraction.** All 15 noiseless modal cases reproduce their MA-005 DF
  reference RMS to within a relative difference of 2e-8. This includes the two
  contrast-13.3 C failures (`development_c`, `opposite_c`), which end in
  `NUMERICAL_FAILURE` with the reference error (RMS 6.40 mm).
- **Improved core, fresh and far cases.** The references for these cases come
  from other strategies (SC-043, SC-044 and SC-050). The cumulative DF policy
  matches or improves most of them, for example: `fresh__deep_c__clean`
  0.073 → 0.004 mm, `far__new_thin_c` 0.033 → 0.003 mm, and `core__kite` 0.035 → 0.012 mm.
- **Budget.** No case approached the budget: at most 5,768 of 13,412 fit units
  and 313 of 1,800 s. The summed per-case time is 73 minutes.

## The eight regressions

| Case | Failed gates | RMS mm (ref; limit) | Last fit | Loss / expected noise (ref) |
|---|---|---|---|---|
| `core__circle_to_star` | residual | 0.0188 (0.0110; 0.0310) | fixed_M37, quota | noiseless |
| `fresh__asymmetric_lobes__noise_seed_0` | RMS, Hausdorff, residual | 0.0908 (0.0678; 0.0878) | release_M15 | 1.05 (1.03) |
| `fresh__asymmetric_lobes__noise_seed_1` | residual | 0.0934 (0.1134; 0.1334) | release_M15 | 1.04 (1.00) |
| `fresh__deep_c__noise_seed_0` | residual | 0.1154 (0.1580; 0.1780) | release_M15 | 1.13 (1.04) |
| `fresh__deep_c__noise_seed_1` | residual | 0.1096 (0.1073; 0.1273) | release_M15 | 1.12 (1.04) |
| `far__noisy_asymmetric` | residual | 0.1582 (0.2198; 0.2398) | release_M15 | 1.11 (0.98) |
| `modal__c4__noisy_asymmetric` | residual | 0.0600 (0.2283; 0.2483) | fixed_M25 | 0.96 (0.93) |
| `modal__c13.3__noisy_asymmetric` | residual | 0.0234 (0.0762; 0.0962) | fixed_M31 | 1.06 (0.92) |

**Seven noisy cases fail because of the declared noise-policy change.** Under the new policy,
fitting stops once the full real catalog reaches `1.1² * expected_noise_loss`.
The fits end at 0.96–1.13 times the expected noise loss, and five stop at M=15.
Their references kept fitting to 0.92–1.04 times that loss. Both endpoints are at the noise level. The
per-frequency residual gate allows only 5% above the reference at each
frequency, so a discrepancy stop is expected to fail it. The geometry
result is mixed: RMS improves in 5 of the 7 cases and worsens slightly in
`fresh__deep_c__noise_seed_1`, which stays within its limit.

**Two regressions are genuine:**

1. `fresh__asymmetric_lobes__noise_seed_0` is the only geometry regression.
   The fit stops at `release_M15` at 1.05 times the noise loss. The SC-044 reference fitted
   further, to 1.03 times, and reached RMS 0.068 mm against 0.091 mm.
2. `core__circle_to_star` is noiseless. Residuals are 2–3 times the SC-043
   reference; at the highest frequency they are 5.7e-6 against 2.2e-6. Geometry stays inside
   its limit (0.019 mm against 0.011 mm). `fixed_M31` and `fixed_M37`
   end at their stage quota. The measured frontier is 34, below the completed
   band of 37, so no tail runs.

## Interpretation

The extraction reproduces MA-005 DF. The cumulative policy passes 28 of the 29
noiseless configurations; the exception is one residual shortfall. The main source of failures is the noise rule. The frozen
contract records the rule's effect as a regression, and that result stands. Relaxing
the gate after the run would change the decision after seeing the data.

## Proposed next steps (not run)

1. **CI-002 contract.** Before any rerun, declare a noise-aware residual gate for
   discrepancy-stopped cases, keeping the geometry gates unchanged. For example: final loss at most
   `1.1² * expected_noise_loss`.
2. **Noise stop at M=15.** As a one-change test on the seven noisy cases, allow one further release (M19) after the
   discrepancy is reached, under the same threshold. It falsifies the
   hypothesis that the early M=15 stop causes the `asymmetric_lobes seed 0`
   geometry loss if RMS does not recover toward 0.068 mm.
3. **`circle_to_star` quota.** Compare the stage-by-stage residual path with
   SC-043 to locate where the two paths diverge, before changing any quota.
4. Still required for requirement 1: three matched reference/candidate runtime pairs
   (`compare-execution`). Qualifying a native modal Müller backend remains the next step after that.
