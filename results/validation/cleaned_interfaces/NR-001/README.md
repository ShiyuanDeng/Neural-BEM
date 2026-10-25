# NR-001: TG-002 with no finer re-evaluations in the fit

Plan: [iteration 01](../../../../docs/iterations/bem_inverse_reorganisation/iteration_01/03_plan.md),
pre-registered with the step 2 code (`a373a8ea5`). Run 2026-10-25 on an Apple M1
Pro (CPU only), `--pipeline modal_fixed --localization none --workers 2`, default
`CumulativePolicy` (13,412 units, 1,800 s fit), 300 s endpoint audit. One run, no
reruns. `checks/` holds the identical-numbers checks for steps 1 and 3.

## Result

**26/30 recovered (9 / 9 / 8), the same 26 cases as PC-001 M1.** The four failures
are the same four: aphex_twin at all three contrasts and hook__c13.3.

| Reading | Result |
|---|---|
| R1 retention | 26 of 26 PC-001 M1 recoveries kept; none lost, none gained |
| R2 the four gate failures | Still `NUMERICAL_FAILURE`, now for a different reason (below); none recovers |
| R3 audit failures | 4: exactly the four failures |
| R4 fit work | Median fit units over the 26 kept cases 1,849 → 1,330 (−28%); every kept case uses fewer |

| Prediction | Outcome |
|---|---|
| P1 at least 25 of 26 kept | Holds (26) |
| P2 no stop at the resolution gate; at least one refused endpoint | Holds |
| P3 lower median fit units | Holds |

**Why the four still fail.** In PC-001 M1 they stopped when a trial curve left
the refined-resolution agreement ("candidate leaves the frozen
numerical-resolution regime"). Without that check, the fit accepts lower-loss
trial curves until the modal forward solve itself refuses one: its A1 lower
bound on the curve's distance function `|W|^2` fails ("|W|^2 lower bound not
certified", coefficient residual 1.05–1.36). That is the signature of a nearly
self-touching curve. The stage then stops with "production evaluation failed
at candidate state". The returned endpoints are far from truth (RMS 4.0–8.3 mm),
and their audits fail on field agreement.

| Case | Last stage | Accepted steps in it | Fit units (PC-001 → NR-001) | RMS mm |
|---|---|---:|---:|---:|
| aphex_twin__c0.5 | stage_3_damped | 2 | 231 → 149 | 3.95 |
| aphex_twin__c4 | stage_2_damped | 4 | 1,068 → 65 | 5.27 |
| aphex_twin__c13.3 | stage_4_undamped | 2 | 414 → 632 | 4.28 |
| hook__c13.3 | release_M11 | 2 | 1,180 → 695 | 8.28 |

Compared with PC-001 M1, aphex_twin__c4 now stops four stages earlier (it reached
`release_M11`), aphex_twin__c13.3 one stage later, and the other two in the same stage.

Wall time: median 206 s per case and 7,674 s summed on this CPU (PC-001 M1 on
CUDA: 31 s and 1,031 s). These are not comparable; work units are.

## Files

- `M1/` — the run (`manifest.json`, `summary.json`, `runs/<case>/`, each with
  `final_audit.json` from `experiments/benchmark/audit.py`).
- `compare_pc001.py` → `comparison.json`: the readings above, per case.
- `logs/run.log` — the campaign output.
- `checks/` — single-case identical-numbers checks.
