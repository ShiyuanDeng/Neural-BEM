# TOP-019 results — both capacity-qualified merge arms recover

Completed 2026-09-15 under the [approved iteration-12 plan](../iteration_12/03_plan.md).
The user replied “go” to the named audit/conditional-pair request. Codex `/root`
owns implementation and closeout; review is an owner review, with no independent
review claimed. The existing checkout and branch were used.

**Both S and F recover the merge control at K=17 and 256/512 nodes.** The
cumulative-frequency F arm gives better boundary and development-prediction
accuracy, while S already passes every recovery gate at lower cost.

| Prescribed stage-4 endpoint | Boundary error (mm) | Sampled IoU | Worst development-evaluation error | Frequency solves | Recovery / numerical gates |
|---|---:|---:|---:|---:|---|
| S: 0.5 GHz only | 0.0860067 | 0.9998001 | 0.0116406 | 1,284 | Pass / Pass |
| F: cumulative 0.5/0.75/1.0/1.25 GHz | 0.0214283 | 0.9994006 | 0.00229358 | 4,844 | Pass / Pass |

[Full bundle][bundle] · [all stages and diagnostics][scorecard] ·
[saved-state figure][figure] · [owner closeout review][review].

## What this comparison decides

The initial boundary was already within 1 mm, but its worst evaluation error
was 0.0939802, above the 0.05 gate. Both new arms started from that same original
controller endpoint, extended from K=9 to K=17 by zero padding. They did not
start from either later TOP-016 inverse endpoint or the truth projection.
Both complete stage-1 trajectories and their endpoint hashes match exactly.

The shared stage-1 endpoint already passes all recovery gates at 0.0943892 mm
and 0.0121415 worst evaluation error. S then makes one further accepted update
and ends at its configured gradient tolerance. F improves boundary accuracy
another **4.01× relative to final S**, and worst evaluation error **5.08×**, for
**3.77× the frequency solves**. Thus this control establishes no binary recovery
advantage for F. Report the precision gain alongside its cost.

F's sampled IoU is slightly lower than S's, although both are above 0.999 and
comfortably pass the original 0.90 gate. Some lower-frequency errors increase
when stage 4 adds 1.25 GHz, while that stage's aggregate objective decreases.
Each stage retains its own active set, normalization and both-resolution
objectives; there is no claim that every frequency improves monotonically.
The prescribed stage-4 endpoints remain the final answers.

## Numerical qualification and stopping

Phase A passed with **104 attempted/completed solves**: 36 fixed-state calls,
four repeatability calls and 64 directional calls. Original and padded starts
have identical predictions at both resolutions. All three audit states qualify
at all six frequencies; the fixed, evaluation-only K=17 projection retains its
representation and recovery gates. Its coefficients never enter fitting.

The first/last reduced-gauge directions pass the inherited two-scale and
numerical-floor checks. Their largest scale discrepancies are about 1.09e-5
and 8.70e-6, well inside the 0.25 limit. No threshold, frequency, observation,
derivative formula or numerical method was changed during execution.

Every prescribed stage endpoint is numerically qualified. S stage 1 and F
stages 1–3 end at planned quotas, with complete usable models and qualified
accepted states; they do not establish convergence. Both final stages stop at
`gradient_tolerance`, with endpoint-associated reduced infinity norms
5.56326e-8 (S) and 7.29494e-8 (F), against 1e-7. The aggregate schedule
convergence flags remain `UNCONFIRMED` because earlier stages were quota-limited.
Missing gradients at quota endpoints remain explicitly missing; earlier
gradients are not relabelled as terminal measurements.

## Work and reproducibility

Total new work is **6,232 attempted/completed frequency solves, zero failed**:
audit 104, S 1,284, F 4,844. Every endpoint-inclusive stage quota and hard cap
passes. The sequential campaign elapsed **1,292.738 s (21.55 min)**; summed
active numerical time was 1,290.920 s. Both workers exited successfully. These
times describe this single-thread campaign, not a controlled historical speedup.

All **84 pre-dispatch tests pass**, using mocked physical calls and geometry.
The source-bound validation covers the new driver, inherited optimizer/ledger,
failure checkpoints, metadata associations and saved-artifact replay. Final
verification reconstructs frequency errors and objectives from saved complex
predictions, checks source/input/state/gradient/acceptance associations and
reconciles the work without new physical solves. The figure was visually checked.

The source manifest pins base revision `8cbf207` plus the two new experiment
Python files, copied into the bundle before dispatch. All 197 hashed source
files remained unchanged through numerical completion. Historical numerical
drivers/defaults and previous result bundles remain unchanged.

## Decision and next step

**Close TOP-019 as BOTH_ARMS_RECOVERED.** The new matched protocol passes the
merge control, resolving its recovery blocker for this development comparison.
Retain S as a successful lower-cost merge control. Keep cumulative F as the
candidate for the next fresh two-star integration check: its earlier central
and two-star benefits remain relevant, and this qualified merge comparison
introduces no new recovery-gate failure.

This does not identify bandwidth as the sole cause of the historical regression:
both new arms also share finer resolution and qualified quota transitions.
The TOP-016 K=9 adverse result remains preserved. K=17 on this control is not
a newly qualified universal bandwidth policy.

**Next decision:** scope one fresh automatic far-circle-to-two-star run through
the controller and continuation, without a supplied count or saved COMMON
checkpoint, preserving the fresh central success as a regression control.
Freeze its capacity, resolution, schedules and work before approval. No such
run, successor ID, twelve-scene suite or production promotion is authorized by
TOP-019. The [completion roadmap](../README.md#completion-roadmap) remains open.

[bundle]: ../../../../results/validation/topology/TOP-019-20260915-144340-qualified-merge/README.md
[scorecard]: ../../../../results/validation/topology/TOP-019-20260915-144340-qualified-merge/scorecard.json
[figure]: ../../../../results/validation/topology/TOP-019-20260915-144340-qualified-merge/endpoints.svg
[review]: ../../../../results/validation/topology/TOP-019-20260915-144340-qualified-merge/closeout_review.md
