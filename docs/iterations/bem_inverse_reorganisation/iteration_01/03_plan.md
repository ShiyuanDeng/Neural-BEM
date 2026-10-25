# NR-001: TG-002 once the fit stops re-solving at a finer resolution

Pre-registered 2026-10-25, committed with the step 2 code before any NR-001 fit.
Approval: the user asked to implement every change in
[the reorganisation plan](../../../cleanup/bem_inverse_architecture_2026-10-24.md)
("implement all changes proposed"). That plan includes this run (Q15). Branch:
the existing `organised`. No new branch or worktree. Owner: Claude.

**Executed 2026-10-25**, one run, no setting changes:
[results](../../../../results/validation/cleaned_interfaces/NR-001/README.md).
26/30 recovered (the same 26 as PC-001 M1); P1–P3 hold.

## Question

How does TG-002 behave once the fit judges every trial curve at its working
resolution only (decision D7)? This is question 3 of the reorganisation plan.

## What changed (step 2)

- **Acceptance (C11).** A trial curve is accepted when its loss is lower than the
  current loss (Q11). There are no refined solves, no gain margin and no
  field-agreement gate. The PC-001 M1 failures all stopped at that gate
  ("candidate leaves the frozen numerical-resolution regime").
- **Geometry update (Q12).** Only the N-point refit remains. The 2N-point refit
  and its agreement check are gone, so no trial is refused as
  `unresolved_projection`. Accepted trial curves are otherwise built exactly as
  before.
- **Reservation.** Before each linearization the fit reserves room for the
  Jacobian and one trial evaluation: 2 units per active frequency instead of 4,
  because the two refined trial solves no longer exist. Stage quotas therefore
  end slightly later.
- **Localization** keeps its first candidate (`--localization none` does not use it).
- **Endpoint audit (Q10).** It moved to `experiments/benchmark/audit.py` and runs
  after `fit()` returns, with the same numbers and the same recovery rule. Its
  resolution pair comes from `physics.resolution_profile()` of the returned curve,
  which equals the last stage's pair. The initial audit of the start circle and
  the early audits are gone. PC-001 M1 ran no early audits, and its initial
  audit passed on all 30 cases.

## Run

```bash
export PYTHONPATH=solvers:.
python -m experiments.benchmark run --pipeline modal_fixed --cases all \
  --run-dir results/validation/cleaned_interfaces/NR-001/M1 --workers 2
```

- TG-002: 10 scenes × contrasts 0.5/4/13.3, the centred 65 mm start,
  `--localization none`, default `CumulativePolicy`.
- Budget unchanged: 13,412 work units and 1,800 s fit wall time per case;
  300 s for the endpoint audit.
- `device=auto`, 4 frequency threads, 2 workers.
- One run, no reruns. A wall-limit stop is a recorded outcome.

**Platform caveat.** This machine is an Apple M1 Pro without CUDA. PC-001 M1 ran
on an RTX 5090 with `certified_spectral`; peanut__c4 takes about 10× longer here
(187 s against 18.6 s). Cases near the 1,800 s fit limit on this CPU may stop at
`TRIAL_WALL_LIMIT` where a CUDA run would not. Wall times are not comparable with
PC-001; work units and recovery are.

## Comparison and readings

Reference: PC-001 M1, 26/30 recovered (9 / 9 / 8), with failures on aphex_twin
at all three contrasts and hook__c13.3, all `NUMERICAL_FAILURE` at the resolution gate.

- **R1 (retention).** Of the 26 PC-001 M1 recoveries, how many NR-001 keeps. Any
  lost case is listed with its outcome, last stage and final audit.
- **R2 (the four gate failures).** For aphex_twin ×3 and hook__c13.3: outcome,
  last stage, final audit, RMS and Hausdorff bound. Do they now recover, stop
  elsewhere, or return an endpoint that the audit refuses?
- **R3 (audit).** Count of endpoints whose final audit fails. Without the in-fit
  gate the audit is the only resolution check, so this count shows where the
  working resolution was not enough.
- **R4 (work).** Per-case fit work units (`fit_and_localization_units`) against
  PC-001 M1. Total units also fall by the initial audit (median 114 units).

## Predictions

- **P1:** at least 25 of the 26 PC-001 M1 recoveries are kept.
- **P2:** none of the four gate failures ends with `NUMERICAL_FAILURE` at the resolution
  gate (that gate no longer exists). At least one of them returns an endpoint whose
  final audit fails.
- **P3:** the median fit work units over the kept cases is lower than PC-001 M1's
  over the same cases, because each accepted step no longer pays for two refined solves.

No setting changes after any result. A failed prediction is reported as failed.
