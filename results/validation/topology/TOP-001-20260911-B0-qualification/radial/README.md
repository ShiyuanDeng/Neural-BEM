# Automatic Fourier topology inversions — radial chart

The same controller receives data and initial geometry, with no target count or event policy.

| Case / inversion video | Component counts | Relative data error | Sampled Hausdorff (mm) | Parameters | Stop |
|---|---|---:|---:|---:|---|
| [split](split/metrics.json) | 1 → 2 | 6.78e-07 | 2.33e-05 | 6 | recovered |

Each case contains `manifest.json`, `metrics.json`, `trajectory.json`, `topology_passes.json`, observations and sensitivity rasters. When rendered, videos contain actual accepted states; topology transitions are discrete. Both production and refined objectives must improve.

These are noiseless, same-material, 0.5-GHz demonstrations. Nested holes and touching boundaries are unsupported. Generated videos and array files follow the repository’s existing Git-ignore policy.
