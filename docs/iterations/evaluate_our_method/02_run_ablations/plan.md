# Run ablations

Questions: what changes when contrast is supplied, damped data is added, the
backend is nodal, the shape band is fixed, or the frequency schedule changes?

## Status and shared conditions

All 200 ablation fits completed on 17 November 2026. This document separates the
ablation part of the [original combined plan](../../../../../Neural_SDF_BEM_AD/docs/iterations/baseline_generation/03_plan.md) after execution; it changes no pre-run choices.
Use the [default method and scoring protocol](../01_measure_clean_and_noisy_recovery/plan.md) as the control.

The user limited every ablation to the 20 cases at contrasts 0.5 and 4. Use the
same centred start, scoring and fit budgets. No case-specific tuning. Compare
against the matching clean default or noisy draw 0, reusing those saved fits.

## Run matrix and changed conditions

| Saved run under `results/bem/` | Change | Fits |
|---|---|---:|
| `default_clean_kc_fc` | Supply true contrast; fit shape only | 20 |
| `default_cleandamped_uc_fc` | Add damped data and retain the old schedule, including its 0.25 GHz warm-up | 20 |
| `nodal_clean_uc_fc` | Nodal backend on clean observations | 20 |
| `nodal_n1d0_uc_fc` | Nodal backend on shared noisy draw 0 | 20 |
| `fixedband37_clean_uc_fc` | Shape band 37 at every stage; no frontier or adaptive tail | 20 |
| `default_clean_uc_fs` | Start with all 19 frequencies at bands 11–37, then the adaptive tail | 20 |
| `default_clean_uc_sf0.5` | Only 0.5 GHz | 20 |
| `default_clean_uc_sf1` | Only 1 GHz | 20 |
| `default_clean_uc_sf1.5` | Only 1.5 GHz | 20 |
| `default_clean_uc_sf2` | Only 2 GHz | 20 |

Fixed-band runs keep the default stage quotas and iteration caps; ladder storage
is 76. Single-frequency runs use that frequency's initial band and measured
frontier, then release bands 11, 15, 19, … while below the frontier.

The damped arm changes both information and warm-up, so it does not isolate
one effect. The clean nodal arm uses the solver family that generated its data;
interpret its advantage with that in mind. The noisy pair is a separate comparison.

## Budget and commands

The original six-hour limit was shared with the other activities, not assigned
again here. It stopped the 1 GHz batch partway through. The user then authorized
completion of 1, 1.5 and 2 GHz and the remaining GauGal work. Record that extension
beside the results; do not describe all work as completed within six hours.

From the repository root, use the EMNerf Python. For each table entry:

```bash
python -m experiments.comparison run bem/<saved-run-name>
```

The exact ordered commands are also in
[the runner instructions](../../../../experiments/comparison/README.md).
Read each `results/bem/<run>/run.json` for the frozen settings and each case's
`score.json` for evidence. [raw metrics](../../../../results/metrics.csv) joins the results without rerunning fits.
