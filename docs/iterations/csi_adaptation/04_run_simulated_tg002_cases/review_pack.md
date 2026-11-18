# Review the full-band first batch

Updated 2026-11-18T02:03:25.045369+00:00; old launcher exited naturally and push bff0fd4a8 is confirmed.
All three fits ran 2048 iterations at 1–8 GHz. No further fit is authorized; wait for the new go and frequency list.

Area error is symmetric-difference area over true area. Main threshold is 0.5 of the signed peak; 0.3/0.7 are sensitivity rows.
Mean permittivity and contrast error are measured in each threshold support. Contrast error is relative to 4.
All components and holes count. Earlier snapshots are evidence and never replace the final 2048 result.

## circle

| Iterations | Threshold | Area error % | Mean permittivity | Contrast error % | Native elapsed s |
|---:|---:|---:|---:|---:|---:|
| 256 | 0.3 | 22.9996 | 3.060485 | 23.4879 | 1105.367 |
| 256 | 0.5 | 12.8730 | 3.149505 | 21.2624 | 1105.367 |
| 256 | 0.7 | 12.1953 | 3.214354 | 19.6412 | 1105.367 |
| 512 | 0.3 | 23.8557 | 3.192607 | 20.1848 | 2146.683 |
| 512 | 0.5 | 14.1663 | 3.284899 | 17.8775 | 2146.683 |
| 512 | 0.7 | 5.8657 | 3.333810 | 16.6547 | 2146.683 |
| 1024 | 0.3 | 23.5511 | 3.277249 | 18.0688 | 4461.090 |
| 1024 | 0.5 | 14.4157 | 3.370549 | 15.7363 | 4461.090 |
| 1024 | 0.7 | 5.9715 | 3.424349 | 14.3913 | 4461.090 |
| 2048 | 0.3 | 22.2923 | 3.342965 | 16.4259 | 9711.300 |
| 2048 | 0.5 | 13.6723 | 3.431334 | 14.2166 | 9711.300 |
| 2048 | 0.7 | 4.6535 | 3.488687 | 12.7828 | 9711.300 |

## kite

| Iterations | Threshold | Area error % | Mean permittivity | Contrast error % | Native elapsed s |
|---:|---:|---:|---:|---:|---:|
| 256 | 0.3 | 74.2569 | 2.616498 | 34.5875 | 1099.235 |
| 256 | 0.5 | 45.3774 | 2.748332 | 31.2917 | 1099.235 |
| 256 | 0.7 | 22.7211 | 2.915245 | 27.1189 | 1099.235 |
| 512 | 0.3 | 61.8082 | 2.775198 | 30.6200 | 2136.472 |
| 512 | 0.5 | 32.6994 | 2.927617 | 26.8096 | 2136.472 |
| 512 | 0.7 | 32.7018 | 3.160515 | 20.9871 | 2136.472 |
| 1024 | 0.3 | 50.3492 | 2.931356 | 26.7161 | 4427.208 |
| 1024 | 0.5 | 21.0530 | 3.104678 | 22.3830 | 4427.208 |
| 1024 | 0.7 | 48.5235 | 3.433532 | 14.1617 | 4427.208 |
| 2048 | 0.3 | 41.0256 | 3.067628 | 23.3093 | 9682.229 |
| 2048 | 0.5 | 16.1103 | 3.254061 | 18.6485 | 9682.229 |
| 2048 | 0.7 | 44.4193 | 3.573827 | 10.6543 | 9682.229 |

## peanut

| Iterations | Threshold | Area error % | Mean permittivity | Contrast error % | Native elapsed s |
|---:|---:|---:|---:|---:|---:|
| 256 | 0.3 | 47.9490 | 2.763326 | 30.9169 | 1099.544 |
| 256 | 0.5 | 29.8680 | 2.876776 | 28.0806 | 1099.544 |
| 256 | 0.7 | 13.7126 | 2.943798 | 26.4051 | 1099.544 |
| 512 | 0.3 | 44.6862 | 2.886836 | 27.8291 | 2137.732 |
| 512 | 0.5 | 28.0041 | 2.998777 | 25.0306 | 2137.732 |
| 512 | 0.7 | 10.5718 | 3.072975 | 23.1756 | 2137.732 |
| 1024 | 0.3 | 40.7798 | 2.995417 | 25.1146 | 4447.877 |
| 1024 | 0.5 | 25.2977 | 3.107005 | 22.3249 | 4447.877 |
| 1024 | 0.7 | 15.6203 | 3.213821 | 19.6545 | 4447.877 |
| 2048 | 0.3 | 36.0732 | 3.097269 | 22.5683 | 9700.709 |
| 2048 | 0.5 | 21.1298 | 3.209469 | 19.7633 | 9700.709 |
| 2048 | 0.7 | 25.7329 | 3.385943 | 15.3514 | 9700.709 |

## Final native costs and timing

| Case | FS | FD | FC | Reported fsb | Native s | Wall s | Native s/iteration | Wall s/iteration |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| circle | 8.91e-05 | 0.00688 | 0.000276 | 0.055712 | 9711.300 | 9723.766 | 4.741846 | 4.747933 |
| kite | 0.00014 | 0.00647 | 0.000546 | 0.052586 | 9682.229 | 9695.568 | 4.727651 | 4.734164 |
| peanut | 0.000244 | 0.0103 | 0.00076 | 0.084144 | 9700.709 | 9714.341 | 4.736674 | 4.743331 |

Costs retain native log precision. FS/FD/FC are frequency averages before the contrast step;
reported fsb is the logged line-search total after that step, so it is not their displayed sum.
Native ChiErr is against the initial back-propagated image, not truth; it is not the contrast-error score above.
Native timers include checkpoint I/O. Wall time also includes startup/configuration/export.
The fits overlap one another, BRG/BEM work and the later low-priority forward prefetch; times are not isolated.

## Figure and checks

Final batch figure: [figures/batch_1.png](figures/batch_1.png). Absolute path: `/home/drdeng/Neural_SDF_BEM_AD_organised/docs/iterations/csi_adaptation/04_run_simulated_tg002_cases/figures/batch_1.png`.
Return codes, all four finite raw arrays, exact frequency/reference metadata, data/driver hashes and final iteration were checked.
The unchanged MATLAB wrapper verifies exact final-array equality against checkpoint 2048 before writing its summary.

## Anything odd

- circle: main-threshold area error is not monotone across saved iterations.
- circle: final area errors span 17.64 percentage points across thresholds 0.3/0.5/0.7.
- kite: final area errors span 28.31 percentage points across thresholds 0.3/0.5/0.7.
- kite, threshold 0.7: 3 components, 0 holes; all count in scoring.
- peanut: final area errors span 14.94 percentage points across thresholds 0.3/0.5/0.7.
- peanut, threshold 0.7: 1 components, 2 holes; all count in scoring.

The known circle-table errors at 1–8 GHz are 0.1723, 0.1260, 0.3034, 1.1396, 0.8228, 1.6782, 2.2946, 5.9136 percent.
Its independent best-contrast shifts and common equivalent-circle fit are in [grid_check/results.md](grid_check/results.md).
Those diagnostic fits do not change any table or CSI result. Other shapes still need their BEM-side forward check.

## Original first-batch forecast

```json
{
  "utc": "2026-11-18T02:00:15.045505+00:00",
  "observed_seconds_per_iteration": [
    4.74184578125,
    4.727650699707032,
    4.736674220703125
  ],
  "conservative_rate": 4.74184578125,
  "elapsed_seconds": 9801.41659526527,
  "remaining_forecast_seconds": 29472.29821983166,
  "total_forecast_hours": 10.909365226415813,
  "budget_hours": 9,
  "method": "elapsed + three remaining batches at slowest completed first-batch wall + seven forward generations at 43 s",
  "exceeds_budget": true
}
```

The old nine-hour forecast check is historical. All three fits finished before the launcher exited; no agent stopped it.
Current policy treats time as a target. All future fits are held for user review and a new coordinator go.
