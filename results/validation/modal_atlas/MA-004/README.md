# MA-004: damped (complex-frequency) start for denser-than-host targets

2026-09-29. [Plan](../../../../docs/iterations/modal_atlas/iteration_04/03_plan.md),
[interpretation](../../../../docs/iterations/modal_atlas/iteration_05/01_results.md).
Driver: `experiments/modal_atlas/damped_screen.py`; report: `damped_report.py`;
post-gate diagnosis: `damped_diagnose.py`.

**Result: gate G1 failed (2 of 4 failures repaired; 3 needed), so transfer was
withheld.** D recovers the contrast-4 C (0.0011 mm) and the contrast-13.3
asymmetric scene (0.011 mm). It keeps all 8 earlier recoveries. The 13.3 star
ends 0.022 mm from the truth but misses the 0.3% residual criterion (0.69%).
The 13.3 C fails (6.4 mm). The control arms: R (extra undamped pass) repairs
nothing; DP (damped prefix, real-data localization) matches D except the
13.3 C.

| File | Contents |
|---|---|
| `manifest.json` | Parent commit `81895c97`, 77 frozen source digests, 56 sealed input digests. |
| `damped_mie_check.json` | Damped Kress solve against exact Mie at every contrast and frequency, γ = 0.25 (worst 7.7e-15). |
| `inputs/` | Real transfer data and damped data (1,024/2,048 ≤ 1e-8 per frequency). |
| `replay.json`, `replay/` | `frozen` = MA-002 and `LB` = MA-003 `both` on the contrast-4 C, state for state. |
| `runs/<arm>/c*/<scene>/` | Per-stage records, localization, audits, `result.json` (24 development attempts). |
| `logs/`, `development.log` | Process logs. |
| `gate_G1.json` | G1: 2 repaired, all 8 kept, FAIL. |
| `summary.json` | Per arm and attempt; frozen rows are MA-002's, LB rows MA-003's. |
| `MA-004_development.png` | Returned boundaries of all five arms against the targets. |
| `diagnosis_trajectory.json` | Boundary error after localization and after every stage (evaluation only). |
| `diagnosis_crossfit.json` | The 13.3 star data evaluated at the truth and at D's star endpoints from every contrast. |
| `diagnosis_frontier_star.json` | 1% observable frontier at the star truth, top four frequencies, contrasts 0.5/4/13.3. |

**Crash and rerun.** The first development launch (04:11, `--workers 6`)
exhausted host memory within 20 s. The OS killed the terminal session and
every worker, before any worker had finished its initial audit. The six
partial folders held only `configuration.json` and were removed. Development
was rerun from scratch at 11:12 with 3 workers and `SC_FREQUENCY_THREADS=4`,
under a memory guard. Results do not depend on either setting: frequency
threading is bit-identical by test, and no attempt approached its wall
limit. Peak memory was 24 GB.

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 SC_FREQUENCY_THREADS=4
python -m experiments.modal_atlas.damped_screen check
python -m experiments.modal_atlas.damped_screen prepare
python -m experiments.modal_atlas.damped_screen generate
python -m experiments.modal_atlas.damped_screen replay
python -m experiments.modal_atlas.damped_screen development --workers 3
python -m experiments.modal_atlas.damped_screen gate
python -m experiments.modal_atlas.damped_report
python -m experiments.modal_atlas.damped_diagnose trajectory
python -m experiments.modal_atlas.damped_diagnose crossfit
python -m experiments.modal_atlas.damped_diagnose frontier
```
