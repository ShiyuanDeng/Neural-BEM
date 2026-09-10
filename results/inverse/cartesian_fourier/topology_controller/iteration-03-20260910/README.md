# Automatic Fourier topology inversions — cartesian chart

The same controller receives data and initial geometry, with no target count or event policy.

Every accepted component is a polar-angle Cartesian Fourier curve, re-expressed in its own polar angle after each retraction. The cases, observations, oracle and budgets are those of the radial bundle, so the two compare directly.

| Inversion video | Component counts | Relative data error | Sampled Hausdorff (mm) | Parameters | Stop |
|---|---|---:|---:|---:|---|
| [repeated-birth](repeated-birth/inversion.mp4) | 0 → 1 → 2 → 3 | 1.62e-07 | 9.262e-06 | 18 | recovered |
| [death](death/inversion.mp4) | 3 → 2 | 1.1e-06 | 4.058e-05 | 20 | recovered |
| [split](split/inversion.mp4) | 1 → 2 | 1.12e-05 | 0.2959 | 76 | recovered |
| [merge](merge/inversion.mp4) | 2 → 1 | 7.88e-05 | 0.7241 | 38 | recovered |
| [mixed](mixed/inversion.mp4) | 2 → 3 → 2 | 4.28e-07 | 1.42e-05 | 12 | recovered |

[Watch all 5 inversions](topology_changes.mp4).

Each case contains `manifest.json`, `metrics.json`, `trajectory.json`, `topology_passes.json`, observations and sensitivity rasters. Videos contain actual accepted states; topology transitions are discrete. Both production and refined objectives must improve.

These are noiseless, same-material, 0.5-GHz demonstrations. Nested holes and touching boundaries are unsupported. Generated videos and array files follow the repository’s existing Git-ignore policy.
