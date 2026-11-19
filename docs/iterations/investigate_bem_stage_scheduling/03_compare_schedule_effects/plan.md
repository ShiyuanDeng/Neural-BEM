# Compare schedule effects on TG-002 and the Fresnel cylinder

19 November 2026. The user asked whether missing warm-up or early stops explain the clean TG-002 misses and the poor BEM result on measured `dielTM_dec8f`. The joint report will compare the strength of evidence for each explanation.

| Investigator | Question and evidence |
|---|---|
| `tg002_recovery` | Compare all 14 clean misses with all 16 passes at the existing 5% area-error threshold. Check whether warm-up or more time or steps changes recovery in the matched cases. [Worker plan](../02_compare_clean_failures_and_passes/plan.md) |
| `fresnel_cylinder` | Check the eight measured frequencies, the completed GPU run and the separate CPU timeout. Test the leading explanations against the GPU fit and report both data loss and error against the nominal cylinder. [Worker plan](../../adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule/plan.md) |

Both workers use the current `organised` checkout. Each checked access to the checkout, Git directory, origin and RTX 5090. The coordinator schedules GPU use around tests whose results depend on a wall limit.

## Comparisons and budget

Use the saved clean scores and fit histories, the contrast-4 stage tests and the original measured CPU and GPU receipts. Each worker records fit commands, budget, settings and raw output locations in its plan before fitting. The joint report uses those records and adds zero fits.

A warm-up test must reuse the original observations and preserve the rest of the schedule. A cap test must preserve the initialization and other controls. Report any other change that bears on a comparison. Count each selected test case once and retain the full 30-case control denominator. Keep the measured result separate because its reference outline and permittivity are nominal.

An explanation gains support for a case if changing that factor moves its matched endpoint. Report the size of the change, whether it crosses the recovery threshold on TG-002 and the actual stop. Where no matched test exists, give the scope of the saved evidence. The user chose the two leading suspects, the two datasets and matched comparisons with the original measurements.

## Evidence checks and output

Work from the repository root. Use `git log --oneline` and `git status --short --branch` to verify delivery. Read the two worker reports and their cited raw fit, score and stage records. Check case counts, reported endpoints and whether the observations match across each tested pair. Record discrepancies and limits in [the joint results](results.md). Each worker commits and pushes every run, including failures.
