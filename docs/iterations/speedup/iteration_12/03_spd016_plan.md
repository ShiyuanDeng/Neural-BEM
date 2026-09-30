# SPD-016 — damped forward and Mie localization speedups

2026-09-30. **Approval status: APPROVED. Execution status: COMPLETE.**
The user asked Claude to investigate these speedups in SPD while avoiding edits
to code being reorganised, then asked Codex to “keep it going” after the exact
interruption point and outstanding work were recovered. This authorizes resuming
the investigation; it does not promote a new production default.

- **Question:** Do the two scratch prototypes reduce complete damped-attempt
  time while preserving recovery, accepted trajectories and work?
- **Baseline:** current commit `143dda87`, unchanged MA-004 D driver and inputs;
  fresh CPU-damped/reference-Mie runs, with ordinary real-frequency CUDA enabled.
- **Intervention:** Mie Hankel order recurrence plus GPU contraction; piecewise
  Chebyshev tables on the fixed `1+0.25i` ray for complex-frequency GPU assembly
  and device LU. Conditional follow-up: use the same table for source/receiver
  fields if the initial gates pass and that remains material cost.
- **Controls:** original schedules, node counts, data, initial circles, optimizer,
  geometry checks, work ceilings, scoring and audit rules. No truth in updates.
  Four frequency threads, one BLAS thread, one numerical worker at a time.
- **File/API map:** preserve Claude's scratch files and failed logs in the new
  bundle; only bundle-local scripts patch `damped.solve`, the Mie landscape and
  CUDA direct kernel in-process. No solver or existing experiment source edits.
- **Numerical gates:** table error <=1e-11; matrix relative max error <=1e-11;
  prediction and same-coordinate Jacobian relative errors <=1e-10. Mie finite
  mask and selected starts must match, loss relative error <=1e-11.
- **Full replay gate:** contrast 0.5 shifted star and contrast 13.3 asymmetric,
  accelerated and baseline, sequentially. Same outcome/recovery, stage sequence,
  accepted-step counts and work counts; compare every saved accepted curve and
  stage loss (relative norm <=1e-7), endpoints (RMS difference <=1e-5 mm), and
  residuals (relative norm <=1e-7). Preserve and diagnose deviations without
  silently loosening gates. A failed gate ends the corresponding adoption claim.
- **Cost gate:** >=20% total-time saving on each of the two fresh matched pairs.
  Report all timings, startup exclusions, machine load and unaccelerated stages.
  These are development cases, not a generalization or complete DF-tail campaign.
- **Budget:** <=45 minutes sequential numerical runtime, <=10 minutes per D
  attempt (existing tighter work/time ceilings retained). Four primary attempts;
  at most two additional field-accelerated attempts if direct checks pass. Stop
  on numerical gate failure, or preserve an inconclusive budget-limited result.
- **Artifacts:** `results/validation/speedup/SPD-016-20260930-damped-gpu/`:
  original failures, scripts, reference/source hashes, commands, environment,
  fresh results, numerical receipts and rebuildable comparisons.
- **Decision:** qualify only the tested opt-in prototype if all gates pass;
  preserve failures otherwise. Production integration is outside this request.
- **Owner:** Codex. **Reviewer:** unassigned; no independent review claimed.

Claude's preliminary measurements predate this contract. They motivate the gates
but do not replace the fresh numerical and end-to-end comparisons below.

**Closeout:** [iteration 13](../iteration_13/01_results.md). Grid-plus-assembly
passes every numerical, quality/work and cost gate on both D attempts (2.43x
and 2.75x). The conditional field extension passes correctness but adds no
consistent saving and is not selected. All six attempts recover; numerical
subprocesses total 23.19 minutes. Existing solver/experiment sources are unchanged.
