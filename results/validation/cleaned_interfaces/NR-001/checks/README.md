# NR-001 checks: identical-numbers runs for the `bem_inverse` reorganisation

These are the single-case checks from
[the reorganisation plan](../../../../../docs/cleanup/bem_inverse_architecture_2026-10-24.md).
Steps 1 and 3 should leave every number unchanged. Each check reruns one TG-002
case and compares accepted curves, losses, trial decisions and work units.

Case: `peanut__c4`, pipeline `modal_fixed` (modal Müller, sampled spectral),
`--localization none`, default `CumulativePolicy`, `device=auto`, 4 frequency
threads. Machine: Apple M1 Pro, CPU only (no CUDA), Python 3.12.1,
torch 2.3.1, numpy 1.26.3, BLAS threads 1. Each run uses
`experiments.benchmark.campaign.run_case` on a copy of the source tree.

## Why there is a reference run here

The plan named the saved PC-001 M1 case as the reference. That run used
`certified_spectral` on CUDA, so it cannot match a CPU run of the current
`spectral` default bit for bit. Instead, `reference_peanut__c4` reruns the
unchanged code (commit `78a9dc5a7`) on this machine. A second run of the same
unchanged code, `reference_repeat_peanut__c4`, measures how much this machine
varies between identical runs.

## Step 1 result

| Run | Code | Outcome | Accepted states | Fit units | Total units | Largest coefficient difference vs reference |
|---|---|---|---:|---:|---:|---:|
| `reference_peanut__c4` | `78a9dc5a7` | recovered | 46 | 1,260 | 1,488 | — |
| `reference_repeat_peanut__c4` | `78a9dc5a7` | recovered | 46 | 1,260 | 1,488 | 1.6e-10 |
| `step1_peanut__c4` | `105af6380` | recovered | 46 | 1,260 | 1,488 | 1.3e-10 |

- Every trial decision, every stage's work units and the accepted path are identical.
- The curves are not bit-identical, even between two runs of the unchanged code.
  The first accepted step already differs by 3e-16 and the ill-conditioned
  0.25 GHz warm-up grows this to about 1e-10. Step 1 sits inside this spread.
- PC-001 M1 (CUDA, `certified_spectral`) also used 1,488 total units on this case.

`comparison.txt` is the output of `compare_runs.py` for every pair.

## Step 3 result

Step 3 is compared with the same case from the NR-001 TG-002 run (step 2 code,
`a373a8ea5`, run with 2 workers on this machine).

| Run | Code | Outcome | Accepted states | Fit units | Total units | Largest coefficient difference |
|---|---|---|---:|---:|---:|---:|
| `../M1/runs/peanut__c4` | `a373a8ea5` | recovered | 50 | 937 | 1,051 | — |
| `step3_peanut__c4` | step 3 | recovered | 50 | 937 | 1,051 | 8.6e-11 |

- Every trial decision, every stage's work units and the accepted path are
  identical; so are the endpoint audit's units and charges (114).
- The difference sits inside the 1.6e-10 run-to-run spread measured above.
- The deterministic control-path fixtures match the step 2 reference exactly
  (`pytest/bem_inverse/test_refactor_contract.py`).
