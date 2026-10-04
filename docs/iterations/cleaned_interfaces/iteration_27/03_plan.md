# PC-001: node-free versus nodal pipelines on TG-002, each with its applicable fixes

Pre-registered 2026-10-04 and committed at `af3cd068` before any PC-001 fit. The user asked
for the three-arm comparison and for code that is ready to run it ("go ahead … i expect the
code to be ready to run the three arms on the same 10 scenes and give side by side
comparison"). **APPROVED 2026-10-04:** asked to reply "go PC-001", the user replied **"go"**.
That approves PC-001 only; NL-001 remains unapproved. Branch: the existing
`feature/shape-frequency-continuation`. No new branch or worktree. Owner: Claude.
Independent reviewer: unassigned. No production default or earlier source/result changes.

## Why

Every numerical fix since CI-001 is in `solvers/bem_inverse/`, but each one attaches to one
slot of `fit()`: physics, geometry update, or the response to an unresolved trial. The
node-free pipeline (modal Müller + `certified_spectral`) was qualified only on the six core
cases at contrast 0.5 (NU-003 to NU-007a). The nodal pipeline's resolution response
(RB-001) lifted FM-005's paired recoveries from 4/11 to 7/11, but it has only run on
continued endpoints, never from a start. No experiment compares the two pipelines, each
with its own applicable fixes, on one benchmark.

## Arms (named recipes in `solvers/bem_inverse/pipelines.py`)

| Arm | Pipeline | Physics | Geometry update | Unresolved trial |
|---|---|---|---|---|
| **N0** | `nodal_baseline` | nodal Kress (CUDA, SPD-016) | `spline` (CI-001) | hard stop (CI-001) |
| **N1** | `nodal_fixed` | nodal Kress (CUDA, SPD-016) | `certified_spectral` (NU-003/005/006/007a) | one promotion to N1024/2048, then ordinary backtracking (RB-001) |
| **M1** | `modal_fixed` | modal Müller (scaled Graf, 128/160 profile) | `certified_spectral` | hard stop: no modal response exists |

The resolution response is a nodal-only fix. Modal Müller sets its trace cutoff from the
storage band, and `Pipeline` refuses a modal response. This asymmetry is intentional: the
comparison is "each pipeline with the fixes that apply to it". Full-matrix acquisition and
relaxed BIE are excluded because they change the data contract or showed no benefit
(FM-002). The FM-003 census and the grid search are excluded as start searches.

Shared by every arm: TG-002 inputs (10 scenes × contrasts 0.5/4/13.3, sealed), the centred
65 mm start, `localization='none'` (`campaign.keep_start`), the default `CumulativePolicy`
(MA-005 path, per-case caps 13,412 units, 1,800 s fit, 300 s per audit), `device=auto`
(CUDA), 4 frequency threads and the unchanged CI-001 recovery gates. N1 audits a promoted
endpoint at both resolutions; its recovery uses the promoted audit, as in FM-005.

## Execution

```bash
export PYTHONPATH=solvers:.
python -m experiments.benchmark.pc001 run --arm all   # M1, then N1, then N0
python -m experiments.benchmark.pc001 report          # also runs after each `run`
```

Output: `results/validation/cleaned_interfaces/PC-001/{N0,N1,M1}/runs/<case>/` and, from
`report`, `report.md` (side-by-side tables), `report.json`, `comparison.csv` and
`comparison.png` (final curves of all three arms over each truth, 3 contrasts × 10 scenes).
Two workers per arm (cap 3, about 8 GB per fit). An existing case result is reused and an
incomplete folder is refused. Exceptions count as not recovered.

Budget: worst case 90 fits × about 2,400 s / 2 workers ≈ 30 h. M1 is expected to be much
shorter. N1 may approach the per-case caps when it promotes, because N1024/2048 solves are
slower. A time-cap stop is a recorded outcome, not a reason to rerun with a larger budget.

## Pre-registered readings (evaluated by `pc001.readings`)

- **R1, headline (M1 vs N1):** at each contrast, M1 recovers at least (N1 − 1) of the 10
  scenes. If this holds at all three contrasts, the node-free pipeline retains the best
  nodal pipeline on TG-002. Otherwise report the contrasts and scenes where it does not.
- **R2 (do the fixes help nodal, N1 vs N0):** N1 recovers at least as many scenes as N0 at
  every contrast, and no case that N0 recovers is lost by N1. Any such regression is listed
  and must be explained before N1 is called an improvement.
- **R3 (is modal resolution-limited):** count the cases where M1 stops with
  `NUMERICAL_FAILURE` and N1 recovers after promotion. A non-zero count is the evidence
  for building a modal resolution response (a curve-adaptive trace cutoff, iteration 07).
- **R4 (cost):** the median total seconds of M1, over cases that all three arms finished,
  is lower than that of N0 and of N1.

## Predictions

- **P1:** at contrast 0.5, every arm recovers at least 8/10 (NU-004 found modal and nodal
  decision-identical on the six core cases).
- **P2:** R1 holds at all three contrasts.
- **P3:** N1 promotes at least once, mostly at contrast 13.3.
- **P4:** `c_shape__c13.3` fails in every arm (FM-003 to FM-005 needed a stage-2 census).
- **P5:** R4 holds. NU-004 measured modal at 2.0× faster than nodal and NU-007a reduced the
  six-case median sum from 247 s to 150 s.
- **Reported, not predicted:** outcome categories, last stage reached, RMS, Hausdorff
  bound, maximum residual, units and seconds per case and arm.

No scene, arm setting or budget changes after any result. A failed prediction is reported
as failed.

## Relation to NL-001

M1 has the same physics, update and localization as NL-001 arm A, but its run-directory
settings name the pipeline, so the two directories are not interchangeable. If both are
approved, run PC-001 M1 and treat NL-001 arm A as a duplicate to skip or to run as a
reproducibility check; that choice belongs to the user.

## Implementation (committed with this plan; no fit run)

- `solvers/bem_inverse/pipelines.py`: `Pipeline`, `PIPELINES`, `pipelines.fit`. It calls
  the unchanged `runner.fit` with the slots filled and records `pipeline` and
  `resolution_promoted` (derived from stage resolutions; `fit` records it only on resume).
- `experiments/benchmark/campaign.py`: `run(..., pipeline=)` and `--pipeline` in the CLI;
  the NL-001 solver/update form is unchanged. Summaries add `resolution_promoted`,
  `last_stage` and a one-line `detail`.
- `experiments/benchmark/pc001.py`: arms, run order and the report.
- Tests: `pytest/bem_inverse/test_pipelines.py` and `experiments/benchmark/test_benchmark.py`
  (arm mapping, mixed-selection refusal, routing, report on synthetic results).
- Smoke check before commit: `circle__c0.5` through each arm into a scratch directory
  outside `results/` (recorded in the commit message, not PC-001 evidence).
