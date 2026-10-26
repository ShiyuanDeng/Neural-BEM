# PS-002: loose stage progress exits on hook c13.3

## Questions

1. Does advancing when loss falls less than 5% over two accepted iterations
   speed up GPU slider on hook c13.3 while keeping TG-002 recovery?
2. How do the stage lengths and loss trajectory change from saved GU-002?

## Authorization and scope

Approved by the user on 2026-10-26: "just use my rule: 5% in the last two
iterations for now ... you can run it right now". This settles the earlier
proposal: apply the rule in **every stage**, including warm-up and D1-D4.
No extra guard against the previously discussed D3 slow patch is added.

One new inverse fit: TG-002 `hook__c13.3`, modal Muller, GPU slider preparation,
one centred start, no localization. Use the existing `organised` checkout.
Reuse the saved GU-002 GPU slider baseline; do not rerun it or other scenes.

## Exact change

At C12, after at least two accepted iterations in the current stage, compare
current loss with loss two accepted iterations earlier. If their combined
relative decrease is strictly below 5%, end the stage with `progress_exit`
and carry its accepted curve into the next stage. Reset history at stage entry.
Rejected trials do not count in the window. Existing loss convergence wins.

Make the existing plain progress condition independent of agreement damping.
Expose its enable flag, window and threshold through `CumulativePolicy` and
record the options in the benchmark manifest. Defaults stay unchanged.
Retain the existing terminal Jacobian calculation to isolate the stopping rule.

Keep K/M/Ku/F selection rules, physical damping, scheduled LM damping,
backtracking, geometry checks, physics checks and TG-002 recovery criteria.
Keep the 13,412-unit / 1,800-second fit limits and 300-second endpoint allowance.
Later selected frontier bands may differ because the accepted curve changes.

## Run and minimum checks

Run alone on RTX 5090, four frequency threads and one case worker, with BLAS
threads fixed to one. Use `python -m experiments.benchmark.ps002 run` from
the existing EMNerf environment with `PYTHONPATH=solvers:.`.

Before running, use one scalar-stage regression for the stopping condition
under scheduled damping and the existing bounded policy checks. No broad
solver checks or new GPU qualification. Preserve code revision and run settings.
Afterward inspect its saved stop reasons, final recovery checks and work totals.

Pre-run validation: the scheduled-damping scalar regression and policy tests
passed, 12 tests in 0.21 s. The policy test covers prefix and appended stages.

Save all evidence, including a failed fit, to
`results/validation/cleaned_interfaces/PS-002/`. Report fit time, accepted
iterations, physics work, recovery, stage outcomes and loss plots against GU-002.
Use saved results for reporting; no automatic tuning or extra fits after failure.

Commit and push implementation, documentation and results to `organised`, then
verify the remote and working tree. This is a one-case comparison, not a change
to the default policy or evidence for other TG-002 scenes.
