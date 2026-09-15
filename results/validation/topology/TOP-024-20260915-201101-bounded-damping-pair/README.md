# TOP-024 — bounded two-star damping continuation

**NEITHER_ARM_RECOVERED.** One matched pair completed under the
[approved plan](approved_plan.md) and the user's bounded-continuation instruction.
All recovery and numerical gates are unchanged. This is an archived-start,
fixed-topology comparison from TOP-022's failed endpoint, not a fresh circle-start run.

| Prescribed state | Boundary error (mm) | Sampled IoU | 0.5-GHz relative error | Worst development error | Recovery / numerical gates |
|---|---:|---:|---:|---:|---|
| Shared TOP-022 start | 9.755053 | 0.830130 | 0.0019287484 | 0.61918485 | Fail / Pass |
| A: baseline damping | 9.628346 | 0.828473 | 0.001996214 | 0.62852257 | Fail / Pass |
| B: initial reset to 1e-2 | 9.532729 | 0.827740 | 0.0019993654 | 0.62748754 | Fail / Pass |

Original gates: correct count, boundary <=1 mm, IoU >=0.90, 0.5-GHz relative
error <=0.003, worst development error <=0.05, plus the unchanged 256/512
numerical checks. Failed reconstruction gates: **A: boundary, evaluation, iou; B: boundary, evaluation, iou**.

The reset gives a slightly smaller boundary error than plain continuation,
but both endpoints retain roughly 9.5–9.6 mm error against the 1 mm gate.
Both have worse IoU and worst development prediction than the shared start,
despite reducing the four-frequency training objective. The saved figure shows
the remaining mismatch concentrated on the upper star's lobes. This is an
observed shape-recovery failure under the stated horizon, not a numerical
resolution failure or evidence of stationarity.

## Controlled comparison and stopping

Both arms use identical K9 polar-gauge geometry, four training frequencies,
observations, optimizer equations, step limits, damping updates and gates.
Only initial damping differs: A=3.138105960899997e-15 and B=1e-2. Each has
12 maximum updates, 4000 endpoint-inclusive calls and 3600 active seconds.
No diagnostic candidate initialized either arm and no extra reset was applied.

- **A**: 12 accepted updates; `maximum_iterations`; terminal reduced gradient 0.0157360044; 3,748 calls, 1796.977 active seconds; configured convergence `UNCONFIRMED`.
- **B**: 12 accepted updates; `maximum_iterations`; terminal reduced gradient 0.00731822206; 3,756 calls, 1790.181 active seconds; configured convergence `UNCONFIRMED`.

A: 3.689% training-objective reduction; B: 4.126% training-objective reduction. These training decreases are distinct from recovery.
The prescribed terminal states determine the table; no best-iterate selection
or intermediate truth/development scoring was used. Terminal gradients are
reported only when associated with the exact endpoint.

## Work and verification

**7,504 new attempted calls; 7,504 completed systems; 0 failed/refused.**
The shared initial score reuses 12 historical systems. Campaign elapsed time
was 1798.097 seconds (29.97 minutes), with two isolated workers,
BLAS 1; this is descriptive timing, not a controlled speed comparison.
Both worker exits and exact timeout commands are in [campaign.json](campaign.json).

All **98 pre-dispatch tests pass**. First accepted steps reproduce TOP-023's
training-only witnesses: maximum coefficient difference
1.17e-14 m, maximum boundary-point difference
3.11e-14 m, maximum relative objective difference
1.28e-12.
All 205 frozen source hashes and input hashes pass.
Saved prediction errors/objectives, state/gradient associations, acceptance
margins, monotonicity and work replay without new BIE solves.

[Scorecard](scorecard.json) · [verification](verification.json) ·
[saved endpoint figure](endpoints.png) · [owner review](closeout_review.md).
The figure uses only saved states and evaluation truth, with no new solves.

## Decision and earlier reliability requirements

Neither arm recovers within the declared bounds. The initial damping reset does not resolve the fresh two-star recovery blocker. No fresh integration or full-suite run is released. Further work needs a separately declared bounded diagnosis of the remaining failure; this experiment does not establish non-recoverability at arbitrary cost or from other starts.

The earlier [TOP-018 saved-start two-star recovery](../TOP-018-20260915-resolution-qualified-pair/README.md)
remains valid at 256/512: F boundary error 0.00167644 mm, IoU 1.0 and worst
development error 3.323707e-6. It starts from a different saved common endpoint.

The [TOP-019 corrected merge control](../TOP-019-20260915-144340-qualified-merge/README.md)
also remains valid: both K17 arms pass; S/F boundary errors are 0.0860067/0.0214283 mm,
and worst development errors 0.0116406/0.00229358. The earlier K9 truth projection
passed the shape gate but failed the prediction gate (0.0898651); K17's projection
passed (0.00234457). This identified an inadequate capacity assumption and the
new inverse comparison corrected the merge recovery failure. It does not isolate
bandwidth as the sole cause: resolution and quota transitions also changed.
The historical TOP-016 regression remains preserved.

The overall automatic method remains unqualified while fresh two-star and
the frozen twelve-scene comparison are unresolved. No redesign or successor
experiment was run as part of TOP-024.
