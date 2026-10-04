# FM-004: continue every below-gap FM-003 stage-2 endpoint

Frozen before execution, 2026-10-04. **APPROVED** by the user, who replied "go" to the
recommendation "continue a fixed set of top candidates through the suffix". Baseline:
`feature/shape-frequency-continuation` at `aec5f335` or later; record the hash. No new branch
or worktree. Owner: Claude. Independent reviewer: unassigned. Production defaults, CI-001,
FM-001, FM-003 and TR sources and archived results are not changed.

## Question

FM-003 recovered the paired contrast-13.3 C from **one** loss-selected stage-2 endpoint
(start 289). Is that a property of the low-loss, near-truth stage-2 basins, or did one start
get lucky? And is there a truth-free signal at the end of the suffix that says whether a
continued candidate recovered? If so, a census can stop at its first certified success.

## What is already known (stated so the test is not mistaken for a blind one)

The FM-003 paired census was truth-scored after it finished. The stage-2 truth distances of
every candidate below are therefore already known: eight are within 5 mm (2.70–4.70 mm), one
is at 5.22 mm, and one (start 399) is a wrong shape 18.6 mm from truth with the third-lowest
loss. This experiment is a **retrospective** test of a selection rule on a census whose stage-2
geometry is known. A blind test needs fresh seeds and is not part of FM-004.

## Fixed definitions

- **Candidate rule (truth-free):** paired contrast-13.3 census endpoints from FM-003 Phase 1
  whose stage-2 loss is ≤ 0.9 × the loss of the cluster containing start 0 (z1's own basin,
  the census mode: 266/512 starts, loss 0.004520901647). Threshold 0.00406881. The selected
  losses end at 0.00383 and the next endpoint is at 0.00438. The rule selects 11 endpoints, in
  loss order: 289, 82, 399, 142, 139, 431, 30, 383, 443, 262, 479. Start 289 is the existing
  FM-003 Phase 2 run and is reused, not rerun.
- **Control:** the FM-003 Phase 4 (paired contrast-4 C) loss winner, start 166 (stage-2 truth
  distance 5.32 mm). CI-001 itself recovers this case from z1.
- **Suffix:** exactly FM-003 Phase 2. `fm003.ContinuationPolicy` (CI-001 operations from
  `stage_3_damped` on), fit budget 13,250 units / 1,784.5 s, 900 s deadline per run, and the
  `fm003_suffix.SuffixAudit` entry (historical CI-001 original-start qualification for the
  case, no new entry gate, real final audit). For the contrast-4 control, the same budget is
  used; it is not binding (CI-001 spent 1,922 fit units on that case in total).
- **Execution:** EMNerf, `PYTHONPATH=solvers:.`, single-threaded BLAS, one worker, four
  frequency threads, `device=auto`, as FM-003.
- **Recovered:** the frozen contract, `fm001.scored(...)['recovered']`: final audit passed,
  RMS ≤ 1 mm, Hausdorff upper bound ≤ 2 mm, every per-frequency relative residual ≤ 0.003.
- **Certified (truth-free):** final audit passed and every per-frequency relative residual
  ≤ 0.003. That is `recovered` without the two truth metrics.

## Runs (order fixed: loss order, then the control; ≤ 15 min each, ≤ 2.75 h in total)

    python -m experiments.cleaned_interface.fm004 seal
    python -m experiments.cleaned_interface.fm004 run
    python -m experiments.cleaned_interface.fm004 report

Each run writes to `results/validation/cleaned_interfaces/FM-004/runs/<case>/<start>/`. An
existing run folder is refused, never overwritten. Exceptions and timeouts are recorded as
`CONTINUATION_EXCEPTION` with the traceback and count as not recovered.

## Readings (pre-registered)

- **R1 (basin or luck):** recoveries among the eight new candidates whose stage-2 endpoint was
  within 5 mm (82, 142, 139, 431, 30, 383, 443, 262). At least 6/8: near-truth stage-2 basins
  generally continue to recovery, and FM-003's paired success was not luck. At most 2/8: the
  winner was unusual, and stage-2 distance below 5 mm is not sufficient. In between: mixed,
  report per-candidate stage departures.
- **R2 (truth-free certificate):** `certified` equals `recovered` for every one of the 12
  continuations (11 paired plus the control). If so, a census can stop at the first certified
  continuation for this case. A certified-but-not-recovered run falsifies the certificate and
  is reported as such.
- **R3 (wrong low-loss basin):** start 399. Prediction: not recovered and not certified. If it
  recovers, stage-2 boundary distance is a poor proxy for basin quality.
- **R4 (control):** start 166 at contrast 4. Prediction: recovered. A failure shows that
  loss-minimum selection can lose a case that the fixed initialisation recovers.
- **Cost:** for each candidate, suffix units and seconds. The implied paired cost per
  recovery is census cost ÷ number of recovered paired candidates, plus mean suffix cost. Also
  report the cost of a loss-ordered sequential stop: census cost, plus the suffix runs in loss
  order up to and including the first certified one.

## Constraints

- No change to the threshold, candidate list, order, budgets or suffix after any FM-004
  result is seen. FM-003 evidence is read-only.
- New code lives in new files (`fm004.py`, `test_fm004.py`). Sealed FM-003 and CI-001 sources
  are not edited.
- Results open `iteration_23/01_results.md`. Commit and push after the run, as `AGENTS.md`
  requires, including failed or timed-out runs.

## Not tested here

Fresh-seed censuses (including the post-hoc observation that 8/9 near-truth paired hits came
from ρ ≥ 0.2), other shapes, and any production change.
