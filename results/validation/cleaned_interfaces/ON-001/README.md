# ON-001 — useful partial result

All 30 fresh matched TG-002 pairs: B/E **26/30**, same historical set, no
regressions or additions. E median paired speedup **1.545838x**;
p10 **1.225445x**. The 2x major-speed target was not reached.
E is the retained opt-in recipe; G/W closed negative and F failed qualification.

- [Final report](../../../../docs/iterations/cleaned_interfaces/iteration_31/01_results.md)
- [All-30 table](final_table.md) and [structured comparison](final_comparison.json)
- [All-30 boundaries](confirmation_boundaries.png) and [audited-output timings](confirmation_timings.png)
- [Frozen recipe](frozen_finalist.json), [all matched pairs](all_paired.json)
- [Development inventory](table.md), [screen comparisons](report.json)
- [Original F qualification](qualification_F/qualification.json) and [exact-active correction](qualification_F_exact/qualification.json)
- [Repeat 1](repeat1_paired.json), [repeat 2](repeat2_paired.json), [uncontended circle replacement](repeat_circle_uncontended_paired.json)
- [Publication receipts](publication_receipts.json), [closeout](closeout.json), [validation logs](validation/)

`all_B`, `all_E` and repetition folders preserve every fit/stage/audit/result,
source/config/receipt hash and failed case. `source_archives/` preserves exact
numerical sources. The first repeated circle timing is excluded for report-
generation contention; its numerical evidence is retained. No new hard-case
recovery exists, so conditional finer nodal checks are not triggered.

| Quantity | B | E |
|---|---:|---:|
| All-30 audited output seconds | 803.352 | 550.986 |
| All-30 fit seconds | 685.959 | 438.032 |
| All-30 audit seconds | 95.961 | 93.737 |
| Median common-success fit seconds | 18.435 | 9.976 |
| Median common-success audited output seconds | 22.408 | 13.724 |
| All-30 fit plus audit units | 63619 | 41531 |
| Proposals | 2511 | 2145 |
| Accepted | 1826 | 1572 |
| Geometry refusals | 43 | 43 |

Timing distributions use common recoveries; suite totals include failures.
Geometry component timers overlap and physics timers sum threaded calls.
Development and qualification costs are separate from deployment and included
in the 101.91-minute overnight elapsed time. No numerical defaults changed.
