# DP-001: damping feedback and repeated-work repairs

Pre-registered 2026-10-05. **Pending explicit user approval of DP-001; no
inverse campaign has run.** Preparation and bounded regression checks are
permitted before approval. The implementation follows priorities 1 and 2 of
the [latest CI-SPD audit](INVERSE_PIPELINE_AUDIT.md). This plan does not reopen
the GGB far-start case.

## Question and fixed information contract

Does model-agreement damping plus exact reuse retain recovery and reduce
time to independently audited output, compared with the already-qualified
ON-001 E recipe? Faster failed returns are reported separately from recovery.

Use only the frozen TG-002 inputs: ten scenes at contrasts 0.5, 4, 13.3; the
same 65 mm centred circle, paired acquisition, 19-frequency real/damped
catalogs, and continuation releases. `modal_muller`, `certified_spectral`,
localization `none`. No truth access during fitting. No initialization search,
new observations, geometry gate relaxation or resolution changes.

## Two arms

- **E:** pre-fix numerical package from Git commit `334699bd`, extracted from
  `git archive` into an ordinary source directory. This is the retained
  ON-001 E recipe, not an archived timing substituted for a fresh run.
- **F:** current maintained implementation with `damping_rule="agreement"`,
  `avoid_terminal_linearization=True`, and `audit_frequency_batch=2`. Exact
  geometry-grid, assembly-index and incremental-wave reuse is active. New
  instrumentation records failed phases and candidate exceptions.

Both use `required_accuracy=.003`, fit wall allowance 120 seconds, per-audit
allowance 30 seconds, aggregate audit allowance 30 seconds with the existing
ten-second terminal reservation, and `log_model=True`. One fresh interpreter
per case, one case worker, four frequency threads, single-thread BLAS, CUDA
explicitly selected with no silent CPU fallback. No excluded warm-up. E and F
use the same driver, input/scoring code and machine; the worker verifies its
actual imported numerical package. No new Git branch or worktree is needed.

F keeps the bounded line search and both physics resolutions. Its damping
floor is `1e-6` times a scaled-curvature infinity-norm bound, at least machine
epsilon. Accepted fractions at or below 0.25 increase damping by ten; poor
model agreement below 0.25 also increases it. Fractions below 0.75 or agreement
below 0.75 retain damping; full, well-predicted steps multiply it by 0.3.
Coordinate clipping is included in the accepted fraction. Exact repeated
proposals within an iteration skip duplicate geometry construction. Check
deadline and work allowances before each proposal; cap actual constructions
at 2000 per stage. Stop a stage when at least three of the last five accepted
steps are severely shortened and their combined relative loss improvement
is below 1%. These values are fixed before the first inverse run.

The terminal tangent omission applies only to loss/iteration exits without
pause/resume or resolution-response requirements, after the accepted-state
callback. Checkpoint and endpoint derivative checks remain intact.

## Preselected screen and conditional full suite

Screen both arms on these nine cases, without reruns:

`aphex_twin__c0.5`, `aphex_twin__c4`, `aphex_twin__c13.3`, `hook__c13.3`,
`circle__c4`, `c_shape__c13.3`, `kite__c0.5`, `star__c13.3`, `cog__c13.3`.

This includes the four historical E failures plus five successful controls.
Run E's screen then F's screen. Continue to the remaining 21 cases in each
arm only if all nine pairs are present and F introduces no recovery failure
relative to E. Reuse those screen results in the full 30-pair report. A screen
regression closes this plan; preserve it, report it, and do not tune or rerun
under the same ID. Approval of this ID covers this conditional continuation.

## Acceptance and reporting

Unchanged recovery gates: passed final field/Jacobian/full-trial audit,
RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm and every real-frequency residual
≤ max(0.003, 3 × noise). Qualification tolerances and projected-candidate
validity remain unchanged. Require no new recovery failures for promotion;
retain the ordinary legacy default until this comparison is assessed.

Report every case and failure outcome, shape error, maximum field residual,
new recoveries/regressions, paired successful-output speedups and summed
output time with failed-run totals separately. Prefer the median paired
successful speedup for the runtime conclusion. No statistical confidence or
case-8 competitiveness claim follows from one execution per pair.

Time begins before problem construction/fit and ends at returned audited
numerical output; truth scoring is separate. Case time also includes scoring.
F receipts split initial audit, fit/localization, early audits and terminal
audits. E retains its original receipts; its legacy phase timers must not be
treated as equivalent to F's new exclusive timers. Geometry and physics
timers remain nested, cumulative and overlapping across frequency threads.
GPU assembly records lock queue wait, prior-work synchronization, CUDA-event
device span, synchronized host span and matrix host transfer separately.
Failed phase durations are retained. Record actual geometry constructions,
trial records, geometry refusals, shortened accepts, physics dispatch ledger
and exception type/message/complete candidate coefficients and SHA-256.

Seal baseline/candidate source archives, the plan and the frozen input
manifest; verify imports, hashes and source stability around every batch.
Keep process crashes, partial outputs and logs. Acquire the existing shared
compute and source coordination locks. Validate, commit and push after each
arm/cohort batch and verify remote and working-tree status; preserve unrelated
work. Do not rewrite an older campaign seal to accept this implementation.

## Deferred work and decision

Priority 3 (accuracy-selected modal resolution and bounded promotion, then
adaptive refined acceptance) needs a separate qualification/plan based on
this outcome. Priority 4 (rigid translation coordinates with a matching
derivative) is conditional on continuing feasibility problems. Neither is
silently folded into F. Exact cross-fit initial-audit sharing and a new early
certificate rejection screen are also deferred pending equivalence evidence.

## Commands after approval

Use `/home/drdeng/miniconda3/envs/EMNerf/bin/python` with `PYTHONPATH=solvers:.`
and single-thread BLAS. `prepare` archives sources and verifies inputs only;
it never regenerates benchmark inputs or solves an inverse problem.

```bash
python -m experiments.benchmark.dp001 prepare
python -m experiments.benchmark.dp001 verify
python -m experiments.benchmark.dp001 run --arm E --cohort screen --approved-id DP-001
python -m experiments.benchmark.dp001 run --arm F --cohort screen --approved-id DP-001
# Only after the saved screen gate passes:
python -m experiments.benchmark.dp001 run --arm E --cohort remaining --approved-id DP-001
python -m experiments.benchmark.dp001 run --arm F --cohort remaining --approved-id DP-001
python -m experiments.benchmark.dp001 report
```
