# TOP-018 owner closeout review

Completed 2026-09-15 by Codex `/root`. Owner source/artifact review; no
independent-agent review is claimed. **Accepted with the post-schedule reporting
failure and its repair explicitly preserved.**

## Verified result

Both numerical schedules completed stages 2–4 from the coefficient-identical
COMMON start at 256/512 and qualified every six-frequency endpoint audit.
F's prescribed final state passes all original recovery gates: boundary
0.001676436985 mm, sampled IoU 1.0, original-training error 1.1148795e-8 and worst
development-evaluation error 3.3237074e-6. S fails geometry and evaluation gates:
11.793168154 mm, IoU 0.73828125, worst evaluation error 1.306218218. S's 0.5-GHz
fit is 4.8607495e-5. S stops at the maximum iteration count; F stops at the loss
target. No best-stage selection, central rerun, topology update or new count
claim is made.

## Artifact and budget checks

- All **196 measured source hashes**, **13 frozen input hashes** and **571
  historical artifact hashes** matched through numerical completion, before any
  reporting-code edit. The measured revision is `9bde9d1`. The two later
  reporting-source changes match the explicit repair record; their measured
  originals also match Git at that revision.
- All six stage endpoint states/checkpoints/scores agree. Nine current or last
  gradient-record associations match their saved trajectory states, coefficient
  arrays, frequency sets and resolutions. Unavailable endpoint gradients at
  quota stops remain unavailable; no extra derivative was run for closeout.
- Phase A checked only the prescribed states and basis rows 0/33. Both rows pass
  the inherited scale and floor tests. Its gate passed with 86 new solves and
  89.044 s. The earlier 54 solves are recorded separately as reused evidence.
- Endpoint-inclusive stage work: S **1,249 / 1,743 / 1,803**; F **1,176 / 1,707 /
  572**. All quotas pass. New totals: **8,336 attempted, 8,336 completed, zero
  failed**. Per-frequency and category accounting agree with these totals.
- S used 2,475.894 s, F 1,625.719 s. Summed active time including Phase A was
  4,190.657 s; campaign elapsed was 2,565.869 s. All phase/trial/campaign solve
  and wall ceilings pass. Two numerical workers, single-thread BLAS; no claim
  of a controlled runtime advantage over TOP-017.
- **87 pre-dispatch tests passed.** The list/tuple reporting seam was then
  reproduced by two zero-physics tests, and **89 final tests passed** after the
  repair. [Before-repair failures](reporting_regression_before.log),
  [final tests](final_tests.log), [machine-readable closeout checks](closeout_verification.json).
- The [endpoint figure](endpoints.svg) was rendered and visually inspected from
  saved coefficients only. Its source/state/figure hashes are recorded in
  [figure_manifest.json](figure_manifest.json).

## Reporting failure retained

Both workers exited with the same metadata type error after their complete
numerical schedules and final scores had been saved. This was a Python
list-versus-tuple equality check in the new annotation loop, not a frequency
value or physical-model mismatch. It was not caught by the initial mocks; the
new regression exercises the inherited tuple and gradient list together.

The original metrics are preserved beside the annotated ones as
`metrics_before_reporting_repair.json`; both worker logs and exit codes remain
visible. The [reconciliation](reporting_repair.json) verifies every original
scientific field is unchanged and guards against any physical call. It adds
missing objective associations and the verified integrity metadata.
No new physical solve, gradient, inverse or restart occurred. The numerical
result is complete; the original process execution was not error-free.

## Decision and limits

Retain this as a successful two-star **fixed-count development-case** recovery
under cumulative frequencies relative to the matched bounded S control.
Preserve TOP-017 central recovery, the fresh central engineering validation,
and the unresolved TOP-016 merge inverse regression. No production/controller
promotion, automatic two-star count recovery or twelve-scene qualification is
established.

**One next decision:** prepare a separately approved K=17 merge-control S/F
comparison with qualified representation capacity. The earlier K=17 projection
is a capacity witness, not an inverse result. No successor numerical work is
authorized or started here.
