# Starting evidence and revised closure assessment

2026-10-03. This cycle opens the standalone relaxed-BIE track from completed
FM-001/FM-002 evidence and the user's subsequent literature and GPU questions.
**No new inversion has run in this cycle.** The original
[FM-002 report](../../cleaned_interfaces/iteration_19/01_results.md) remains
unchanged; this is a dated qualification of its recommendation to close the
tested variant.

## What has been established

FM-001's real relaxed prefix combined two changes: adding relaxation and
removing early complex-frequency damping. Its frozen-weight gradient was
incomplete. At the saved high-contrast C warmup, that gradient and the complete
loss gradient had cosine −0.9987266.

FM-002 corrected the gradient and independently varied the two factors. All
twelve runs completed their declared attempt, including four numerical stops.
Both damped arms recovered 3/3 cases; both real-prefix arms recovered 1/3.
The corrected implementation passed 477 tests and saved-state finite
differences/refinement checks. Ordinary damped controls reproduced FM-001
coefficients, accepted-step counts, stage stops and units exactly.

Relaxation improved the failed real-prefix endpoint errors (C: 23.0 to
10.8 mm; star: 7.7 to 5.6 mm), without achieving recovery. Recorded runtime
increased. These selected cases are development evidence, not an untouched
generalization set. See the [evidence index](../evidence_index.md) for the
authoritative tables, timings, plots and original receipts.

## What the stop actually means

The four last acceptance checks show positive loss reductions at both N512
and N1024. The production/refined prediction discrepancy nevertheless
exceeded a frozen per-frequency threshold, so the implementation raised
`NUMERICAL_FAILURE` immediately. It did not attempt a finer evaluation or
continue that proposal's smaller-step search after the exception.

| Case / arm | Stage | Production loss reduction | Refined loss reduction |
|---|---|---:|---:|
| C / R0 | fixed_M49 | 7.07648e-4 | 7.07648e-4 |
| C / R1 | release_M11 | 1.68866e-3 | 1.68866e-3 |
| Star / R0 | fixed_M49 | 1.39913e-4 | 1.39917e-4 |
| Star / R1 | fixed_M49 | 7.18665e-5 | 7.18663e-5 |

These figures come from the final `acceptance_checks` entry in the four
[stage receipts](../evidence_index.md#four-stopped-trajectories-to-replay).
They show available decreasing proposals at the evaluated resolutions; they
do not establish accurate derivatives at those candidates, eventual recovery,
or permission to ignore the accuracy gate. All stops occurred after the
relaxed prefix, in ordinary-loss stages.

## Current interpretation

Keeping the ordinary damped default is supported by the measured outcomes.
Calling the broader relaxed-BIE research question scientifically closed is
premature: none of these four failures establishes convergence to a wrong
stationary point, and the resolution obstruction has not been tested with
the established remedies discussed in the
[literature/GPU review](02_proposals/01_literature_and_gpu_review.md).

The next discriminating question is whether the stopped candidates become
numerically qualified at higher resolution, and whether continuing with
error-controlled refinement or smaller steps changes recovery. RB-001 tests
that question equally for R0 and R1. An improvement in both would identify a
shared numerical limitation; it would not by itself establish a relaxation
advantage. No new penalty, Hessian, acquisition or all-36 campaign is needed
to answer this first question.
