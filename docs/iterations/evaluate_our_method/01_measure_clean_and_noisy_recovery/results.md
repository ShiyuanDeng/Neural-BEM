# Clean and noisy recovery — run on 17 November 2026

The default recovered **16/30 clean cases** and **16/30, 17/30 and 17/30** across
three 1% noise draws. On contrasts 0.5 and 4, that is 16/20 clean and 50/60 noisy
case-draws. No contrast-13.3 case recovered, clean or noisy.

All 120 fits have saved scores. This report was assembled from [raw metrics](../../../../results/metrics.csv)
during the documentation reorganisation; no fitting or rescoring was performed.
The [plan](plan.md) records the method and criteria.

## Recovery

Success is area error ≤5%. The old count adds the boundary and residual conditions
specified in the plan. Medians below include failed fits and cover all 30 cases.

| Data | Contrast 0.5 | Contrast 4 | Contrast 13.3 | Area success | Old count | Median fit s |
|---|---:|---:|---:|---:|---:|---:|
| [Clean](../../../../results/bem/default_clean_uc_fc/run.json) | 9/10 | 7/10 | 0/10 | 16/30 | 15/30 | 26.1 |
| [1% draw 0](../../../../results/bem/default_n1d0_uc_fc/run.json) | 9/10 | 7/10 | 0/10 | 16/30 | 16/30 | 11.8 |
| [1% draw 1](../../../../results/bem/default_n1d1_uc_fc/run.json) | 10/10 | 7/10 | 0/10 | 17/30 | 17/30 | 11.5 |
| [1% draw 2](../../../../results/bem/default_n1d2_uc_fc/run.json) | 10/10 | 7/10 | 0/10 | 17/30 | 16/30 | 15.7 |

These three draws are repeated measurements of the same 30 cases, not 90 distinct
scenes. The counts alone do not establish that noise improves the method.

## Failures and limits

On clean data, `cog__c0.5`, `kite__c4`, `c_shape__c4`, `aphex_twin__c4` and all
10 high-contrast cases fail the area criterion. The contrast-4 and high-contrast
failures persist across all three noisy draws. At contrast 0.5, noisy draw 0 fails
`aphex_twin`; draws 1 and 2 recover all ten shapes.

Saved stop reasons include numerical failures and trial wall limits. These identify
how fitting ended; they do not, on their own, establish why the wrong shape was
recovered. Clean records contain 9 numerical failures and 6 trial wall limits;
therefore a fit's stop label and its area-success label must be read separately.

Five-percent noise was not run. The current evidence answers recovery at 1%
noise and these three seeds only. Explaining the persistent failures remains
separate work; this reorganisation authorizes no new runs.

## Independent forward check

The [saved RegPy comparison](../../../../results/_checks/forward_regpy/asymmetric__c4.json)
passed all 19 frequencies for `asymmetric__c4`: worst relative difference
9.775e-11 against the predeclared 1e-6 limit. This checks one forward case,
not inverse convergence across the benchmark.

## Execution and evidence

Core fits ran from 04:51 to 07:48 UTC on 17 November. Noise generation and the
forward check preceded them. Per-case work, errors, contrast estimates and stopping
records remain in `results/bem/<run>/<case>/`; table links open the run manifests.

The [initial execution record](../../../../results/_execution/ggb003/execution_final.json)
describes the later six-hour stop during ablations. The
[continuation record](../../../../results/_execution/ggb003/continuation/session.json)
records the user's extension and completion at 15:32 UTC. The entire study did
not finish inside the original limit. Recorded fit times exclude setup and scoring.
