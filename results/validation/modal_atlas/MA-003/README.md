# MA-003: exterior band and dense exact-Mie localization repairs

2026-09-29. [Plan](../../../../docs/iterations/modal_atlas/iteration_03/03_plan.md),
[interpretation](../../../../docs/iterations/modal_atlas/iteration_04/01_results.md).
Driver: `experiments/modal_atlas/repair_screen.py`; report: `repair_report.py`.

**Result: gate G1 failed, so transfer was withheld.** The exterior band (B),
the Mie localization (L), and both together (LB) recover none of the four
MA-002 failures. All eight earlier recoveries are kept in every arm. The
contrast-4 C stall is a wrong basin (`basin_check_*.json`). Post-gate,
evaluation-only probes show that complex-frequency damping restores the
horizons and repairs the 13.3 circle localization (`probe_damped_*.json`).
That motivates MA-004.

| File | Contents |
|---|---|
| `manifest.json` | Parent commit `1693b0a5`, 74 frozen source digests, SC-050 input digests. |
| `replay.json`, `replay/` | The `frozen` arm reproduces MA-002's contrast-4 C accepted states exactly. |
| `runs/<arm>/c*/<scene>/` | Per-stage records, localization, audits, `result.json` (33 development attempts). |
| `logs/`, `development.log` | Process logs. |
| `gate_G1.json` | G1: 0 repaired, all 8 earlier recoveries kept, FAIL. |
| `summary.json` | Per arm and attempt: outcome, metrics, localization, work. Frozen rows are MA-002's. |
| `MA-003_development.png` | Returned boundaries of all four arms against the targets. |
| `basin_check_band_c4_development_c.json` | Stage losses at the stall against the truth truncated to each stage's band (`basin_check.py`). |
| `probe_damped_horizon.json` | Horizons at `k + iβ` at the contrast-4 C start state (`damped_probe.py horizon`). |
| `probe_damped_localization.json` | Dense Mie localization optimum at contrast 13.3 with data at `k(1 + iγ)` (`damped_probe.py localization`). |

Attempts ran four at a time on the 24-core host with the RTX 5090. The
evaluation-only diagnostics partly overlapped them. Work units are exact.

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m experiments.modal_atlas.repair_screen replay
python -m experiments.modal_atlas.repair_screen development --workers 4
python -m experiments.modal_atlas.repair_screen gate
python -m experiments.modal_atlas.repair_report
python -m experiments.modal_atlas.basin_check band 4.0 development_c
python -m experiments.modal_atlas.damped_probe horizon
python -m experiments.modal_atlas.damped_probe localization
```
