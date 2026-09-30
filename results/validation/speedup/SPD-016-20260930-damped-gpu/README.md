# SPD-016: damped forward and Mie localization speedups

2026-09-30. **COMPLETE / PASS for grid + assembly acceleration.** The optional
field-table extension passes correctness but is **not selected**: it supplies no
consistent incremental saving. This bundle resumes Claude's interrupted scratch
investigation under the [approved contract](../../../../docs/iterations/speedup/iteration_12/03_spd016_plan.md).
Existing solver and experiment files are unchanged; all runtime overrides live
in this bundle and affect only their worker process.

## Provenance and interrupted work

- Parent checkout: `143dda87`, `feature/shape-frequency-continuation`.
- `claude_original/` preserves all five scratch scripts and the four failed
  replay logs. The original import bug remains in this preserved copy.
- `claude_probe_records.json` preserves the original profiling and numerical
  stdout recovered from Claude's session, with timestamps and session identity.
- `reference_manifest.json` hashes the reference sources and inputs before any
  fresh run. The original dirty documentation state is retained in
  `workspace_before.txt` and `workspace_before.patch`.
- All **163** reference source/input hashes and both script manifests verify.
  `executed_plan.md` retains the contract before its final status amendment;
  `plan_record.json` records when that snapshot was saved. `versions.json`
  records Python, NumPy, SciPy, PyTorch and CUDA versions.
- The active `scripts/mie_grid.py` guards its command-line loop. Fresh drivers
  use new output directories, propagate failures and enforce wall-clock limits.

## What changes in the prototype

1. Mie grid: compute H0/H1 with SciPy, recur over integer orders, then perform
   contraction and loss norms on CUDA. Radial coefficients, clearance masks,
   objective and coordinate refinement remain the reference implementation.
2. Damped solve: interpolate J0/J1/J2/H0/H1/H2 on the fixed `1+0.25i` ray using
   111 degree-24 Chebyshev panels on `[0.01,100]`. Keep the existing near-pair
   series, Kress weights, diagonal terms and geometry validation. Use existing
   device LU factors and the original residual guard.
3. Conditional field arm: replace only H0/H1 evaluation in the existing source
   and receiver factories with the same table. Preserve their validation and
   weights, including the reciprocal source traces used by the Jacobian.
   Unsupported arguments use the original special-function dispatch.

The table is an approximation qualified on a fixed ray and finite interval.
The combined experiments do not establish general complex-frequency support.

## Fresh numerical qualification

All 27 checks pass: one table screen including panel boundaries, 24
matrix/prediction/Jacobian comparisons (two contrasts, initial and endpoint
geometries, three frequencies, N=512/1024), and two complete localization grids.
Maximum relative differences: matrix `4.84e-15`, prediction `2.23e-14`, Jacobian
`7.98e-14`. Both grids retain exactly the finite mask and selected starts; their
loss differences are at most `2.79e-15`. See `qualification.json` and
`qualification_summary.json`.

The grids take 52.34 -> 2.42 seconds and 63.24 -> 2.84 seconds. These local
measurements are distinct from the whole-attempt measurements below.

## Complete matched attempts

| Scene / contrast | Fresh reference | Grid + assembly | Speedup | Time saved | Units per arm | Endpoint RMS |
|---|---:|---:|---:|---:|---:|---:|
| Shifted star / 0.5 | 245.45 s | 101.11 s | 2.43x | 58.8% | 1,536 | 0.01824086 mm |
| New asymmetric / 13.3 | 396.52 s | 143.95 s | 2.75x | 63.7% | 2,321 | 0.01136343 mm |

Both pairs pass every predeclared quality/work gate and the >=20% cost gate.
Outcomes, recovery, configurations, localization starts, stage/accepted-step
counts, trial decisions, acceptance checks and work counters match exactly.
All 123 saved accepted curves agree within `1.83e-11` relative coefficient norm;
maximum relative stage-loss difference is `1.18e-9`, residual-vector difference
`4.78e-9`, and absolute RMS difference `8.24e-13` mm. Initial and final audits pass.
Both fresh baselines also reproduce their archived numerical results and
accepted curves exactly; archived times are not used for the speedup ratios.

| Component | Star reference -> accelerated | Asymmetric reference -> accelerated |
|---|---:|---:|
| Localization, including refinement/qualification | 59.05 -> 3.42 s | 73.69 -> 3.91 s |
| Damped stages | 98.32 -> 9.80 s | 198.62 -> 16.80 s |
| Undamped stages | 71.12 -> 71.19 s | 107.26 -> 106.29 s |

Other time belongs to the unchanged audit/scoring work and driver overhead.
The remaining runtime is predominantly undamped work, so the next substantial
gain cannot be inferred from another damped-kernel microbenchmark alone.

## Conditional source/receiver-field extension

All 24 additional forward/Jacobian/field comparisons pass, with maximum
prediction error `2.24e-14`, Jacobian error `8.01e-14`, and source/receiver
array errors `3.07e-15`. Five unsupported-input checks retain the reference
dispatch exactly. Both complete field-arm replays also pass the same quality,
work and recovery gates; the table is exercised 544 and 896 times respectively.

| Scene | Grid + assembly | Plus field table | Incremental time saving |
|---|---:|---:|---:|
| Shifted star | 101.11 s | 107.81 s | -6.6% |
| New asymmetric | 143.95 s | 143.44 s | 0.4% |

**Decision:** retain the grid-plus-assembly prototype. The field extension is
numerically sound on this screen but has no consistent end-to-end advantage.
Do not interpret its combined gain over the original baseline as evidence of an
incremental field benefit. There is one run per arm/scene on a shared host, so
the small field-arm difference is not a statistically established effect.
Both the negative incremental result and all field scripts remain preserved.

The complete candidate and reference JSONs are under `runs/`; logs and exact
commands are under `logs/`, `campaign.json` and `fields_campaign.json`.
`comparison.json` is rebuilt by `scripts/compare.py`; `report.json`, rebuilt by
`scripts/report.py`, includes both candidate variants, process times and hash
verification. These check configurations, localization starts, stage and
trial decisions, acceptance checks, work counters, every accepted curve, stage
losses, endpoint RMS and all-frequency residuals.

## Timing scope

One sequential worker at a time on a shared RTX 5090 host; four frequency
threads and one BLAS thread. These are complete MA-004 D attempts starting from
the original circles, including localization and audits. They do **not** include
the subsequent MA-005 DF tail. These two noiseless single-object scenes are
development cases, not a new robustness/generalization campaign.

`result.json.seconds` is the original driver's attempt timer. Process startup,
table construction and frozen-input verification are outside that timer; command
timestamps and `WALL_SECONDS` retain the larger scopes. No iteration, budget,
acceptance threshold or reconstruction criterion was changed.

Including whole-process startup, the primary pairs take 246.63 -> 102.86 s
(2.40x) and 397.74 -> 145.26 s (2.74x). All numerical subprocesses total
**1,391.27 seconds (23.19 minutes)**, within the 45-minute budget. All six
attempts finish below their 10-minute ceilings; there are no fresh failed runs.
There are 51 passing numerical comparison records plus the fallback checks;
no broad production regression suite is claimed because production files were
not edited.

**Final disposition:** qualified experimental grid-plus-assembly acceleration
on these two D attempts, with no production integration or default change.
Field-table extension not selected. No successor campaign is scheduled.

## Reproduction

Use the EMNerf Python environment and run commands from the repository root.
`scripts/run_campaign.py` sets all environment controls and runs qualification
then the four primary replays. It refuses existing logs/output directories;
reproduce in a fresh bundle containing the scripts and reference manifest, not
by deleting or overwriting this evidence. The conditional field runner requires
both primary quality and cost gates to pass. The numerical ceiling is 45 minutes
across both phases, with at most six D attempts.

To regenerate comparisons without running numerical workers:

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/speedup/SPD-016-20260930-damped-gpu/scripts/compare.py
/home/drdeng/miniconda3/envs/EMNerf/bin/python results/validation/speedup/SPD-016-20260930-damped-gpu/scripts/report.py
```

Owner: Codex. Independent reviewer: unassigned.
