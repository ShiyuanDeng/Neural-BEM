# CS-001 — Revised continuation on selected TG-002 scenes

2026-10-05. Preregistered before fitting. Implements the agreed
[four-phase schedule](CONTINUATION_SCHEDULE.md). The user's request approves
testing the revised strategy; the specific CS-001 ID is awaiting explicit
confirmation under AGENTS.md. No branch or worktree creation is proposed.
Use the existing checked-out feature/shape-frequency-continuation branch,
which contains the latest design and maintained solver.

## Frozen screen and paired comparison

Run these eight cases once per arm, from the sealed centred 65 mm circle:
circle__c4, kite__c4, peanut__c0.5, cog__c4, c_shape__c13.3,
hook__c13.3, aphex_twin__c4, aphex_twin__c13.3. This covers three contrasts,
a circle control, smooth shapes, high harmonics, and three previously failed
cases. Selection is fixed before fitting; retain every failed result.

Control: the current CumulativePolicy with the qualified DP-001 F options.
Candidate: the same options, changing only the continuation schedule and
the initial update subspace. Modal Müller, certified_spectral for all shape
updates and independent audits, localization none. CUDA, four frequency
threads, audit batches of two, one worker, one BLAS/OpenMP thread. Fresh
interpreter per case. Run control then candidate for each case; CUDA startup
and all audits count in output time. Process wall time is recorded separately.
Existing DP-001 results are context only,
not the paired timing control.

Shared options: required_accuracy=.003, damping_rule=agreement,
avoid_terminal_linearization=True, log_model=True; 13412 fit work units,
120 s fitting wall budget, 30 s aggregate audit budget (10 s reserved for
terminal audit), 30 s individual audit cap. Preserve stage field checks,
validity, line search, stopping thresholds and ordinary recovery gates.

## Concrete four-phase integration

1. Replace the ordinary 0.25 GHz damped warm-up with exact translation and
   uniform scale at that same lowest frequency. Three metre coordinates
   (tx, ty, dr) preserve the circle. K_geometry=4, nominal M=0 (no normal
   shape modes); 600 work units, 44 iterations; existing coefficient bounds
   give 18 mm translation coordinates and 12 mm radius change per proposal.
   Preserve the independent spectral start audit at M=1. Restricted-model
   convergence advances into the frequency ladder, never implies success.
2. Preserve the four cumulative damped frequency stages and explicit real
   return byte for byte: .5/.75/1/1.25 GHz, M=floor(3*max(real(k))),
   K_geometry=2*M+2, original quotas/iterations/weights. On TG-002 these are
   M=3/5/7/9, K=8/12/16/20. Keep the accepted circle/state between phases.
3. Four additional full-real-catalog stages: (M,K_geometry)=(11,24),
   (15,32), (19,40), (25,52). All 19 frequencies at every stage; 1500 work
   units and 22 iterations each. Increase storage by exact zero padding;
   do not crop or refit the inherited accepted boundary. These replace the
   old fixed-storage releases/fixed stages and adaptive frontier, rather
   than append to them.
4. Full configured release at M=95, K_geometry=192 (the existing validated
   frontier ceiling and storage maximum), all 19 real frequencies; 1500
   work units, 22 iterations. No cleanup or adaptive-frontier operations.

Backend resolution remains its unchanged function of geometry storage:
K_trace=64/96 through K_geometry=52 and 128/160 at K_geometry=192.
These are production/refined accuracies, separate from shape M/K.
Full-catalog audited discrepancy stopping may finish before later stages;
do not force extra optimization after success. Numerical failures remain
hard stops, followed by the unchanged independent spectral endpoint audit.

## Qualification, evidence, and decision

Before fitting, verify sealed TG-002 inputs, exact preservation of prefix
operations, strictly increasing full-catalog M/K, stage-specific update
selection and spectral auditing, and CPU/CUDA three-column similarity
derivatives on a TG-002-unit circle. Run the affected maintained-package
tests and bounded continuation suites. No truth data in fitting or policy.

Archive source hashes and a source tarball, plan and input hashes, approval,
environment, per-case executable plans, complete receipts/accepted states,
stdout and failed-run evidence. Recheck source/input hashes after the batch.
Score only after fitting/audit return: passed final audit, RMS <=1 mm,
Hausdorff upper bound <=2 mm, every frequency residual <=.003. Report
per-case recovery, geometry errors, worst residual, output time, stopping
stage/reason, and actual traversal of the new shape ladder. Compare paired
recoveries and successful-output times; a screen is not a 30-case claim.
Regressions or numerical stops are findings, not permission to tune/retry.
Validate, commit and push all code/docs/evidence, verifying remote HEAD and
the final working-tree status. No expanded campaign is authorized here.
