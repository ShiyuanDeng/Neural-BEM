# MA-002: the frozen SC-050 policy on denser-than-host targets

2026-09-29. [Plan](../../../../docs/iterations/modal_atlas/iteration_02/03_plan.md),
[interpretation](../../../../docs/iterations/modal_atlas/iteration_03/01_results.md).
Driver: `experiments/modal_atlas/contrast_screen.py`; report:
`contrast_report.py`; diagnosis: `diagnose.py`, `poles.py`, `mie_localize.py`.

**Result:** recovered 3/3 at contrast 0.5 (SC-050 reproduced exactly), 3/3 at
2, 2/3 at 4 and 0/3 at 13.3. The failures come from band over-release and, at
13.3, circle-localization failures. Resonance shortens the linearization
horizon but does not cause the failures.

| File | Contents |
|---|---|
| `manifest.json` | Parent commit `91f046c4`, 69 frozen source digests, SC-050 input digests. |
| `circle_pole_census.json` | Exact Mie poles of the 5 cm disk in the catalog band at contrasts 2, 4, 10, 13.3. |
| `mie_check.json` | Kress against Mie on the disk: ≤ 4.2e-14 at every contrast and frequency. |
| `inputs/c*/<scene>/` | Observations (2,048 nodes) and 1,024/2,048 qualification. |
| `runs/c*/<scene>/` | Per-stage records (history, trials, acceptance checks), localization, audits, `result.json`. |
| `logs/`, `campaign.log` | Process logs. |
| `summary.json` | One row per attempt: outcome, metrics, work, LM trial counts. |
| `MA-002_reconstructions.png` | Returned boundaries against targets. |
| `diagnosis_frontier.json` | Released band against the 1%/0.1% frontier and `K_U + K_V`, per attempt and stage; one-factor contrast sweep. |
| `diagnosis_horizon.json` | Per-harmonic horizons, nearest pole, pole shifts, smooth and pole predictions. |
| `diagnosis_localization.json` | Dense exact-Mie localization landscape optimum against SC-050's search and the truth-equivalent circle. |
| `diagnosis_resolution.json` | The contrast-4 C numerical stop, one factor at a time. |

Attempts ran four at a time on a 24-core host with one RTX 5090. The
diagnostics ran partly concurrently, so wall-clock times are not a
controlled comparison. Work units are exact.

```bash
export PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m experiments.modal_atlas.contrast_screen census     # pole census
python -m experiments.modal_atlas.contrast_screen mie        # solver check
python -m experiments.modal_atlas.contrast_screen prepare    # refuses to overwrite this manifest
python -m experiments.modal_atlas.contrast_screen generate
python -m experiments.modal_atlas.contrast_screen campaign --workers 4
python -m experiments.modal_atlas.contrast_report
python -m experiments.modal_atlas.diagnose frontier|horizon|localization|resolution
```
