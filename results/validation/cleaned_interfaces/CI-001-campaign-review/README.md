# CI-001 campaign review

2026-09-30. A reproducible summary of the user's CI-001 campaign in
[`../CI-001`](../CI-001). The campaign output itself is unchanged.

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/cleaned_interfaces/CI-001-campaign-review/summarize.py
```

The script reads `comparison.json` and each regression's `result.json`, then writes
[`summary.json`](summary.json). For each of the eight regressions, the summary records:

- the failed gates and the geometry against its limit;
- the last fitted stage;
- the final loss of the candidate and the reference, divided by the expected noise loss
  (`0.5*mean(r^2)` over the 19 per-frequency relative residuals);
- the source of the historical reference.

Build checks made before the review:

| Check | Result |
|---|---|
| Focused suite recorded in [verification.json](../CI-001-implementation/verification.json) | 61/61 pass, CUDA, 19.6 s |
| Other `experiments/shape_continuation` and `pytest/gpr_bem_kress` tests | 241/241 pass |
| Implementation hashes and the 235 sources frozen by `prepare` | All match the committed tree |
| CLI `inventory`, `verify`, `plan`; `--solver modal_muller` | Work as documented; modal Müller refuses before fitting |
| `report` rerun on a copy of the campaign | `comparison.json` and `comparison.csv` are byte-identical |

Interpretation: [iteration 03 results](../../../../docs/iterations/cleaned_interfaces/iteration_03/01_results.md).
