# FM-005: FM-004 numerical-refusal stops with RB-001's resolution response

Frozen before execution, 2026-10-04. **APPROVED** by the user, who replied "go" to the
FM-005 proposal in [iteration 23](../iteration_23/01_results.md). Baseline: the head after
FM-004 (`19c6e8c4` or later; record the hash). No new branch or worktree. Owner: Claude.
Independent reviewer: unassigned. Production defaults and all earlier sources and results are
unchanged.

## Question

In FM-004, seven of eleven below-gap paired stage-2 endpoints, and the contrast-4 control,
ended at the CI-001 hard stop `candidate leaves the frozen numerical-resolution regime`. Six of
those paired runs were within 0.14–1.8 mm RMS when they stopped. If one unresolved trial
step no longer ends the run, do they recover? If so, the obstruction after a good stage 2 is
the numerical gate, not the basin.

## One change

Each run is FM-004's continuation (same start, `fm003.ContinuationPolicy`, 13,250-unit /
1,784.5 s fit budget, `SuffixAudit` entry, real final audit, scoring) with
`resolution_response=ResolutionResponse(1024, 2048, physics)`, the mechanism RB-001
implemented and qualified (`lm_backend.py`). Behaviour:

- An unresolved trial is rejected and the step backtracks.
- If the retained base itself is unresolved at N512/1024, the stage is promoted once to
  N1024/2048, and later stages stay there.
- A failure at N1024/2048 is still a hard stop.

The finer physics is `NodalKress(Execution(device='auto', frequency_threads=4,
resolution=1024))`. RB-001 used one frequency thread; thread count does not change results.

Two execution settings differ from FM-004, both forced by the slower promoted solves:

- The per-run deadline is 2,400 s instead of 900 s. The policy's own 1,784.5 s fit wall
  budget still applies and binds first.
- A whole-campaign cap of 3 h, after which no new run starts.

Each run starts from its stage-2 endpoint. It is not resumed from the FM-004 stop.

## Runs (order fixed)

1. **Primary, 8 runs:** paired starts 82, 399, 139, 431, 30, 383, 479 (FM-004 order), then the
   contrast-4 control 166.
2. **Non-regression, 4 runs (secondary, added within the approval's scope):** the FM-004
   recoveries 289, 142, 443, 262. The response can change a trajectory that FM-004 left
   unchecked, because it also checks the accepted base. These runs test whether successes
   survive.

    python -m experiments.cleaned_interface.fm005 seal
    python -m experiments.cleaned_interface.fm005 run
    python -m experiments.cleaned_interface.fm005 report

Output: `results/validation/cleaned_interfaces/FM-005/runs/<case>/<start>/`. An existing run
folder is refused. Exceptions and timeouts are recorded and count as not recovered.

## Readings (pre-registered)

- **P1 (gate or basin):** recoveries among the six near-truth refused paired runs (82, 139,
  431, 30, 383, 479).
  - At least 5/6: the numerical gate was the operative obstruction.
  - At most 1/6: it was not. Report each new stop and stage.
  - In between: mixed.
- **P2 (control):** start 166 at contrast 4. Prediction: recovered.
- **P3 (wrong basin):** start 399. Prediction: not recovered and not certified.
- **P4 (non-regression):** 289, 142, 443 and 262 remain recovered. Any loss is reported per run.
- **P5 (certificate):** certified (final audit passed at the final resolution, and every
  residual ≤ limit) equals recovered on all 12 runs.
- **Descriptive, not gating:**
  - For each run: promotions, rejected unresolved trials, new stop reason, and the first
    accepted state that differs from FM-004.
  - Updated census cost per paired recovery across all 11 candidates under the response.

## Constraints

- No change to candidates, order, budgets, policy or response settings after any FM-005
  result is seen.
- New code only (`fm005.py`, `test_fm005.py`). FM-003, FM-004, CI-001 and RB-001 artifacts
  are read-only.
- Results go in `iteration_25/01_results.md`, including any failed or capped runs. Commit and
  push after the run.

## Not tested here

Fresh-seed censuses, other shapes, enabling the response by default.
