# First known-contrast B1 fit: circle__c4

## Coordinator review stop, 18 November 2026

Completed once, on CUDA. No later inverse fit has started. The manifest
watcher remains running for the three unfinished cases: cog__c4 and
aphex_twin at both contrasts. Cog__c0.5 passed while this report was prepared;
17 cases now pass all 37 checks. At fit launch 16 cases were qualified; the coordinator
explicitly allowed this first fit without waiting for the remaining four.

System UTC: worker launch 2026-11-18T02:06:07.580121+00:00; end 2026-11-18T02:06:15.927304+00:00.
Fit source commit: `f11a78a9f3eca37ef0ec53e40917530f45ca9596`. Solver sources were clean and
unchanged at both endpoints. Input hashes match the passing forward check.

| Item | Measured value |
|---|---:|
| Outcome | COMPLETED_SCHEDULE |
| Last fitted stage | full_6_M37, M=37, geometry storage=192 |
| Work units | 274 / 13,412 |
| Fit time | 6.694823 s |
| Seconds per work unit | 0.024433662 |
| Worker process wall | 8.346927 s |
| Peak host high water | 1.935860 GiB |
| Peak GPU, sampled process | 1.369141 GiB |
| Peak GPU, Torch allocated / reserved | 0.569606 / 0.937500 GiB |
| Minimum available host memory | 33.491199 GiB |
| Raw area error | 7.31658833248e-07 |
| Area error, percent | 7.31658833e-05% |
| Known contrast | 4 |

The final frontier did not request another band. Last accepted full-catalog
maximum stage residual was 7.627347738e-6. This is a saved stage value;
no extra endpoint forward solve was performed. No time or memory stop occurred.

## Forecast and limits

Forty identical fits would take 267.793 s
(4.463 min) of fitting, or 333.877 s
(5.565 min) including the observed worker startup cost.
This circle needed only 274 units and is an easy case, so that projection
is not a representative campaign prediction. If every fit used 13,412 units
at this measured unit cost, fitting would take
3.641 h. That is a cost scenario,
not a time bound: other shapes/stages can have a different unit cost.

Keep one B1 fit at a time. A 3 GiB expected host peak plus 1 GiB margin
remains conservative against this 1.936 GiB first measurement. The launch
had 35.266 GiB available. Floor stays 14 GiB.
No elapsed-time target stops a fit, and only the coordinator may raise
concurrency. Known fits on checked cases precede recovered fits; late cases
run known then recovered after qualification. No further fit before this stop.

## Scoring failure and repair

The numerical fit returned normally. Initial scoring could not import
`gaugal`, because this wrapper omitted the path supplied by the comparison
entry point. The original `scoring_failure.json` is retained. Added only that
same import path to the owned wrapper, then scored the saved endpoint with
unedited `experiments/comparison/scoring.py`. No fit or forward solve was rerun.
Postprocessing completion took 0.941 s; its provenance is saved.

[Raw scores](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/circle__c4/known/attempt_01/raw_scores.json),
[metrics](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/circle__c4/known/attempt_01/metrics.json),
[supervisor](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/circle__c4/known/attempt_01/supervisor.json),
and [postprocessing receipt](../../../../results/bem/baseline_data/brg_tg002/2026-11-18/circle__c4/known/attempt_01/postprocessing_completion.json).
Bulk optimizer states/logs remain local with SHA-256 in the fit manifest.

## Watcher handoff

The active watcher PID 858819 predates the first-fit report changes. It is
still reading new baseline manifests and never starts a fit. Its in-memory
report writer can replace results.md with a checks-only summary after a new
manifest arrives. This immutable first-fit report and raw metrics remain safe.
The on-disk writer now includes saved fit metrics. Refresh the idle watcher
before the next batch to load that reporting fix; no numerical job should be
stopped. This is flagged for coordinator review at the first-fit stop.
