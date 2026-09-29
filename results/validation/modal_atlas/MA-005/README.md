# MA-005: damped start plus a frontier tail

2026-09-29. [Plan](../../../../docs/iterations/modal_atlas/iteration_05/03_plan.md),
[interpretation](../../../../docs/iterations/modal_atlas/iteration_06/01_results.md).
Driver: `experiments/modal_atlas/frontier_tail.py`; report: `frontier_report.py`.

**Result: both gates pass.**

- **G1 (development):** DF repairs 3 of the 4 MA-002 failures and keeps all
  8 earlier recoveries (11 of 12).
- **G2 (transfer):** DF recovers 7 of 8 transfer attempts, frozen SC-050
  0 of 8, and every recovered endpoint passes its final audit.

Disclosure found after the run: `opposite_c` has the development C's target
and identical data (8.6e-16). Only its initial curve differs, and
localization discards that. Excluding it, DF recovers 6 of 6 and frozen 0
of 6. The one DF miss is `opposite_c` at contrast 13.3, which is the
development 13.3 C.

| File | Contents |
|---|---|
| `manifest.json` | Parent commit `54ace2e6`, 79 frozen source digests, the MA-004 manifest digest, the 12 D development results DF starts from. |
| `replay.json`, `replay/` | D rerun from scratch equals MA-004's contrast-4 C, all 75 accepted states. |
| `runs/DF/c*/<scene>/` | Frontier, tail stages, audits, `result.json` (12 development, 8 transfer). |
| `runs/frozen`, `runs/D` | Transfer attempts from scratch with MA-004's driver. |
| `logs/`, `replay.log`, `development.log`, `transfer.log` | Process logs. |
| `gate_G1.json` | G1: 3 repaired, all 8 kept, PASS. |
| `summary.json` | Per arm and attempt; gate G2 and the `opposite_c` disclosure. |
| `MA-005_development.png`, `MA-005_transfer.png` | Returned boundaries against the targets. |

Attempts ran three at a time with `SC_FREQUENCY_THREADS=4` under a memory
guard (peak 26 GB). Work units are exact.

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 SC_FREQUENCY_THREADS=4
python -m experiments.modal_atlas.frontier_tail prepare
python -m experiments.modal_atlas.frontier_tail replay
python -m experiments.modal_atlas.frontier_tail development --workers 3
python -m experiments.modal_atlas.frontier_tail gate
python -m experiments.modal_atlas.frontier_tail transfer --workers 3
python -m experiments.modal_atlas.frontier_report
```
