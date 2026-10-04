# FM-005 evidence

FM-004's continuations rerun with RB-001's opt-in `ResolutionResponse(1024, 2048)`.
Plan: [iteration 24](../../../../docs/iterations/cleaned_interfaces/iteration_24/03_plan.md).
Results: [iteration 25](../../../../docs/iterations/cleaned_interfaces/iteration_25/01_results.md).

- `implementation.json`, `implementation.tar.gz`: source/input seal and source archive.
- `runs/<case>/<start>/`: ledger, stage records with resolution events, and scored `result.json`.
- `summary.json` (`fm005 report`): rows, readings P1–P5 and costs. Its `promoted` field is
  null because the runner records `resolution_promoted` only on resumed fits.
- `review.json` (`fm005_review`): derived promotion stage, pre-stop identity with FM-004,
  per-stage rejections and quota use.
- `campaign.json`, `run.log`: campaign time and event log.

Headline: paired recoveries rise from 4/11 to 7/11 (82, 30, 479 added). The four
FM-004 recoveries are unchanged. The contrast-4 control still fails.
