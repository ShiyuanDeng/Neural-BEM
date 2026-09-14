# TOP-016 — fixed-topology recovery, bounded preflight and paired pilot

**inconclusive within declared budgets or numerics.** At least one main arm did not complete its four-stage contract. F promotion: **False**.

[Approved plan](../../../../docs/iterations/topology/iteration_09/03_plan.md) · [Preflight and independent review](preflight.md) · [Frozen contract](contract.json) · [Screen](sensitivity.json) · [Complete scorecard and work](pilot_metrics.json)

## Information and numerical gates

Original 24-pair observation files and prescribed retained states were preserved byte-for-byte. K=9 padding preserved IDs, curves and predictions. The retained gauge-constrained Cartesian chart approximated the principal truths to **0.001675 mm** and **0.039482 mm**, below 0.1 mm. The smallest qualifying common training pair was **128/256 nodes**. New-frequency oracle and frozen-pair evaluation-geometry convergence checks passed. Details: [Phase 0](phase0/preflight.json) and [Phase 1](phase1/sensitivity.json).

The weak directions were fixed from the 0.5-GHz reduced Jacobian, scaled by arclength-weighted RMS normal displacement, then measured at both signs, both amplitudes, and both resolutions. Gains use base-subtracted data changes and equal per-frequency normalization.

| Principal case | Usable directions | Median F/S gain | Gate passed |
|---|---:|---:|---|
| central-ellipse-star | 8 | 17.626368390093777 | True |
| far-two-stars | 8 | 21.403753423165092 | True |

The screen establishes useful added local sensitivity under this protocol. It does not establish reconstruction success.

## Paired pilot and bounded controls

| Trial | Stages reached | Status | Boundary error, initial → last accepted (mm) | Final IoU | Worst evaluation error, initial → final | Frequency solves |
|---|---:|---|---:|---:|---:|---:|
| far-two-stars S | 1/4 | INCONCLUSIVE | 11.991 → 12.033 | 0.71419 | 1.4217 → 1.4137 | 939 |
| far-two-stars F | 1/4 | INCONCLUSIVE | 11.991 → 12.033 | 0.71419 | 1.4217 → 1.4137 | 939 |
| central-ellipse-star S | 1/4 | INCONCLUSIVE | 9.2226 → 8.8154 | 0.90969 | 0.89216 → 0.5214 | 960 |
| central-ellipse-star F | 1/4 | INCONCLUSIVE | 9.2226 → 8.8154 | 0.90969 | 0.89216 → 0.5214 | 960 |
| merge S | 4/4 | COMPLETE | 0.55416 → 0.53551 | 0.99344 | 0.09398 → 0.098072 | 996 |
| merge F | 4/4 | COMPLETE | 0.55416 → 1.1082 | 0.98788 | 0.09398 → 0.16795 | 2259 |
| local far-two-stars S | 1/4 | INCONCLUSIVE | 2.2376 → 2.3275 | 0.95994 | 0.40239 → 0.15473 | 236 |
| local far-two-stars F | 1/4 | INCONCLUSIVE | 2.2376 → 2.3275 | 0.95994 | 0.40239 → 0.15473 | 236 |

Stage IDs, accepted coefficients, per-frequency errors, aggregate objectives, measured gradients, actual stops and refined-validation decisions are retained under [runs](runs/). These rows describe the final **retained** endpoint, including budget-limited ones. A budget-limited endpoint is not a completed negative reconstruction experiment. The 1.5/2.5-GHz data remained unfitted development evaluation data, and endpoint scores never selected training updates, directions, restarts or stages.

The principal S/F pairs stopped during the shared 0.5-GHz first stage, before the acquisitions diverged. Their equal endpoints cannot establish a frequency-continuation advantage or failure. The completed F-merge control **does** establish a regression for that case: 0.554 → 1.108 mm creates a new boundary gate failure, and worst evaluation error rises from 0.09398 to 0.16795. This independently prevents promotion.

The local rows, if present, use only the prescribed truth representation translated by (+2 mm, −1 mm). They are truth-assisted local controls and cannot count as automatic recovery. The archived machine-readable `recovered` semantics and v1/v2 benchmarks were not changed.

## Work, implementation and limitations

**10,306 attempted frequency solves; 10,306 completed; 0 failed.** Phases 0/1: **2,781 solves / 777.98 s**, below 5,000/1,200. Sum of active pilot/control worker times: **910.33 s**; concurrent worker times are not end-to-end elapsed time. All per-trial/stage work ceilings are verified from artifacts. Phase 0/1 used one worker; pilot/control used at most two, each with single-thread BLAS. [Hardware/environment](environment.json).

The only solver-side source changes are opt-in fixed-topology optimizer hooks for independent loss-change stopping, candidate validation, batch reservations, checkpointing before Jacobians and cache accounting. LM equations and defaults remain unchanged. Candidate acceptance uses both-resolution decreases and the factor-5 disagreement allowance. Runtime resolution failures stop a trial. The tests include exact comparison with the archived default trajectory; all focused tests use mocked physical forwards or geometry only. [Tests](pilot_tests.log). The [independent closeout review](closeout_review.md) verified source/input hashes, paired coefficients, stage work including endpoint scoring, and wall ceilings, with zero new physical solves.

Diagnostics have explicit limits: rejected-gain logs cover only production-decreasing candidates that reached refined validation, not every rejected production trial. Full feasibility rejection counts were not preserved; interrupted runs also lack complete one-sided/unresolved column totals. A capped endpoint's `terminal.json` correctly records its gradient as unavailable. An older `terminal_gradient.json` is the **last measured pre-terminal gradient**, not endpoint stationarity evidence; its association is documented in [gradient associations](gradient_associations.json). These gaps do not invalidate retained states, scores or exact physical-solve counts, and no completed trial was repeated to fill them.

No topology policy, physical BIE solver, representation chart, original observations or historical result bundle was modified. No full twelve-scene suite was run. This experiment does not establish global identifiability, a unique failure cause, or that frequency diversity succeeds or fails outside the measured scope.

## Reproduction and summary rebuild

[Commands](commands.md), manifests and per-worker logs preserve execution provenance. The Phase-0 driver and pre-hook optimizer source are archived alongside their evidence. The final source hashes and original producing revision are in [manifest.json](manifest.json).

Rebuild this report and the full scorecard **without rerunning an inverse or forward**:

```bash
python summarize_top016.py --bundle results/validation/topology/TOP-016-20260914-fixed-topology
```

Fresh numerical reruns must use fresh directories and the approved scripts with the recorded single-thread environment. Do not repeat completed runs merely to regenerate a report.

## Single next decision

Review whether a revised fixed-topology contract is warranted, addressing both the merge-control regression and the stage-1 budget obstruction before committing more compute. TOP-016 is closed; no successor cycle is automatically executed. Validated changes are committed locally on `track/topology-TOP-016`; push and merge require a separate user instruction.
