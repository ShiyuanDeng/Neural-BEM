# Automatic Fourier topology inversions

The same controller receives data and initial geometry, with no target count or event policy.

| Inversion video | Component counts | Relative data error | Sampled Hausdorff (mm) | Stop |
|---|---|---:|---:|---|
| [repeated-birth](repeated-birth/inversion.mp4) | 0 → 1 → 2 → 3 | 1.62e-07 | 9.251e-06 | recovered |
| [death](death/inversion.mp4) | 3 → 2 | 1.1e-06 | 4.054e-05 | recovered |
| [split](split/inversion.mp4) | 1 → 2 | 2.89e-07 | 1.56e-05 | recovered |
| [merge](merge/inversion.mp4) | 2 → 1 | 7.98e-05 | 0.7227 | recovered |
| [mixed](mixed/inversion.mp4) | 2 → 3 → 2 | 4.27e-07 | 1.418e-05 | recovered |

[Watch all five inversions](topology_changes.mp4).

Each case contains `manifest.json`, `metrics.json`, `trajectory.json`, `topology_passes.json`, observations and sensitivity rasters. Videos contain actual accepted states; topology transitions are discrete. Both production and refined objectives must improve.

These are noiseless, same-material, 0.5-GHz demonstrations. Nested holes and touching boundaries are unsupported. This named evidence bundle includes its videos, figures, observations and sensitivity rasters in Git.
